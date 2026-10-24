"""
FastAPI Main Application for CoverageGuard.
Matches the specification:
- Header connection chip and popover: "Demo Insurance Co.", "Access active", "Read-only" in popover only.
- Page 1: Dashboard (Row 1: 3 cards; Row 2 Left: Clean claims & target; Row 2 Right: Cases by specialty; Row 3: Latest 3 updates).
- Page 2: Cases (Table, filters, upload patient file).
- Page 3: Case detail (Plain sentence, rule reference, what to do).
- Page 4: Updates (Reverse-chronological, filter by type).
- Mock insurer service: GET /v1/rules/snapshot, GET /v1/rule-changes?since=
- "Run check now" admin button triggers check and moves 3 open cases from Approved to Needs attention.
"""

import json
import os
import uuid
from pathlib import Path
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Literal
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Automatically load .env if present
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from app.db.store import store
from app.domain.models import (
    Case,
    CaseItem,
    CaseStatusType,
    Diagnosis,
    InsurerConnectionInfo,
    InsurerUpdateEntry,
    ItemVerdict,
    PolicyBulletin,
    Rule,
    utc_now,
)
from app.engine.checker import evaluate_case
from app.intake.analyzer import (
    analyze_clinical_document,
    analyze_insurance_card,
    get_fallback_sample,
)

app = FastAPI(
    title="CoverageGuard API",
    description="Hospital insurance-claims agent for coverage verification.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Health & Status Telemetry
# ---------------------------------------------------------
@app.get("/health")
@app.get("/api/health")
def get_health():
    return {
        "status": "healthy",
        "service": "CoverageGuard",
        "timestamp": utc_now().isoformat(),
        "total_cases": len(store.cases),
        "total_rules": len(store.rules),
    }


# ---------------------------------------------------------
# Header Connection Chip & Popover
# ---------------------------------------------------------
@app.get("/api/connection", response_model=InsurerConnectionInfo)
def get_connection_info():
    """Returns connection chip and popover data. 'Read-only' appears only in popover."""
    return store.get_connection_info()


@app.post("/api/connection/toggle-fail")
def toggle_connection_failure():
    """Toggles simulated check failure to test the amber chip and warning banner."""
    is_failed = store.toggle_check_failure()
    return {
        "is_check_failed": is_failed,
        "status": "Check pending" if is_failed else "Access active",
    }


# ---------------------------------------------------------
# Page 1: Dashboard
# ---------------------------------------------------------
@app.get("/api/dashboard")
def get_dashboard():
    """
    Returns exact metrics for the 3 dashboard rows:
    Row 1: Approved, Needs attention, Missing or wrong info.
    Row 2 left: Clean claims submission % and target.
    Row 2 right: Cases by specialty horizontal bars.
    Row 3: Latest 3 updates.
    """
    return store.get_dashboard_summary()


class TargetPayload(BaseModel):
    target: float


@app.post("/api/settings/target")
def update_target(payload: TargetPayload):
    """Admin editable clean claims submission target percentage."""
    new_target = store.set_clean_claims_target(payload.target)
    return {"success": True, "target": new_target}


# ---------------------------------------------------------
# Page 2: Cases & Case Detail
# ---------------------------------------------------------
@app.get("/api/cases")
def list_cases(
    status: Optional[str] = Query(None, description="Approved, Needs attention, Missing or wrong info"),
    specialty: Optional[str] = Query(None, description="Cardiology, Oncology, etc."),
):
    """Table view: Case ID, Specialty, Status, Items (count). Filter by status and specialty."""
    all_cases = list(store.cases.values())

    if status and status.lower() != "all":
        all_cases = [c for c in all_cases if c.status.lower() == status.lower()]

    if specialty and specialty.lower() != "all":
        all_cases = [c for c in all_cases if c.specialty.lower() == specialty.lower()]

    return [
        {
            "case_id": c.case_id,
            "specialty": c.specialty,
            "status": c.status,
            "items_count": len(c.items),
            "member_ref": c.member_ref,
            "service_date": c.service_date.isoformat(),
            "items": [it.model_dump() for it in c.items],
            "prior_approval_ref": c.prior_approval_ref,
        }
        for c in all_cases
    ]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    """
    Page 3: Case detail.
    Header: Case ID, specialty, status badge.
    Item list: Covered, Not covered, Prior approval needed, Document missing, Value wrong.
    Each issue gets one plain sentence, rule reference, and what to do.
    """
    data = store.check_case_detail(case_id)
    if not data:
        raise HTTPException(status_code=404, detail="Case not found")
    return data


# ---------------------------------------------------------
# Official Insurer Policy Bulletins
# ---------------------------------------------------------
@app.get("/api/bulletins/{rule_id}", response_model=PolicyBulletin)
def get_policy_bulletin(rule_id: str):
    """
    Returns official insurer clinical policy bulletin, circular rationale,
    coverage criteria, and appeal guidance so claims officers can verify citations.
    """
    b = store.get_bulletin(rule_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Policy bulletin not found for rule {rule_id}")
    return b


# ---------------------------------------------------------
# Multimodal AI Intake & Live Pre-Check
# ---------------------------------------------------------
class AnalyzeIntakePayload(BaseModel):
    sample_id: Optional[str] = None
    card_image_b64: Optional[str] = None
    card_text: Optional[str] = None
    clinical_doc_b64: Optional[str] = None
    clinical_text: Optional[str] = None


@app.post("/api/intake/analyze")
def analyze_intake_files(payload: AnalyzeIntakePayload):
    """
    Multimodal AI Intake:
    1. Uses Gemini 3 Flash to read insurance card (payer, member ID, plan).
    2. Reads clinical documents (specialty, diagnoses, drugs, procedures, attached docs).
    3. Runs the deterministic coverage engine against active payer rules.
    4. Attaches official policy bulletin citations and officer action instructions.
    """
    if payload.sample_id:
        preset = get_fallback_sample(payload.sample_id)
        card_data = preset["card"]
        clinical_data = preset["clinical"]
    else:
        card_data = analyze_insurance_card(
            image_b64=payload.card_image_b64,
            text_content=payload.card_text,
        )
        clinical_data = analyze_clinical_document(
            doc_b64=payload.clinical_doc_b64,
            text_content=payload.clinical_text,
        )

    # Build provisional case for instant rule evaluation
    sdate = date(2026, 11, 10)
    if clinical_data.get("service_date"):
        try:
            sdate = datetime.strptime(clinical_data["service_date"], "%Y-%m-%d").date()
        except Exception:
            pass

    raw_items = clinical_data.get("items", [])
    case_items = [
        CaseItem(
            type=item.get("type", "drug"),
            code=item.get("code", "DRUG-A"),
            name=item.get("name", "Prescribed Item"),
            quantity=item.get("quantity", 1),
        )
        for item in raw_items
    ]
    if not case_items:
        case_items = [CaseItem(type="drug", code="DRUG-A", name="Standard Care Item", quantity=1)]

    dx_code = clinical_data.get("diagnosis_code") or "DX-100"
    dx_desc = clinical_data.get("diagnosis_desc") or "Clinical Order Intake"

    provisional_case = Case(
        case_id="PROVISIONAL",
        insurer_id=card_data.get("insurer_id") or "demo-insurer",
        insurer_name=card_data.get("insurer_name") or "Demo Insurance Co.",
        plan_id=card_data.get("plan_id") or "PLAN-GOLD",
        member_ref=card_data.get("member_ref") or f"M-{uuid.uuid4().hex[:6]}",
        group_number=card_data.get("group_number"),
        specialty=clinical_data.get("specialty") or "Cardiology",
        service_date=sdate,
        visit_type="outpatient",
        diagnoses=[Diagnosis(code=dx_code, description=dx_desc)],
        items=case_items,
        documents=clinical_data.get("documents", []),
        prior_approval_ref=clinical_data.get("prior_approval_ref"),
        status="Approved",
    )

    eval_result = evaluate_case(provisional_case, list(store.rules.values()))

    # Find matching policy bulletin if an issue is flagged
    matching_bulletin = None
    for verdict in eval_result.results:
        if verdict.rule_id:
            matching_bulletin = store.get_bulletin(verdict.rule_id)
            if matching_bulletin:
                break

    return {
        "success": True,
        "card": card_data,
        "clinical": clinical_data,
        "check_result": eval_result,
        "bulletin": matching_bulletin,
    }


# ---------------------------------------------------------
# File Upload: Save Case to Caseload
# ---------------------------------------------------------
class UploadCasePayload(BaseModel):
    specialty: str = "Cardiology"
    patient_text: Optional[str] = ""
    prescription_text: Optional[str] = None
    insurer_id: Optional[str] = "demo-insurer"
    insurer_name: Optional[str] = "Demo Insurance Co."
    plan_id: Optional[str] = "PLAN-GOLD"
    member_ref: Optional[str] = None
    group_number: Optional[str] = None
    item_name: Optional[str] = None
    item_type: Optional[str] = "drug"
    item_code: Optional[str] = None
    service_date: Optional[str] = None
    prior_approval_ref: Optional[str] = None
    diagnosis_code: Optional[str] = None
    diagnosis_desc: Optional[str] = None
    documents: Optional[List[str]] = None


@app.post("/api/cases/upload")
def upload_patient_file(payload: UploadCasePayload):
    """Upload patient file and prescription; extracts items and deterministically checks coverage."""
    new_id = f"C-{len(store.cases) + 1:03d}"

    # Use specified item or extract from text
    itype = payload.item_type or "drug"
    icode = payload.item_code or ("DRUG-A" if "drug a" in (payload.patient_text or "").lower() else "STD-CARE")
    iname = payload.item_name or ("Drug A" if icode == "DRUG-A" else "Standard Care Protocol")

    sdate = date(2026, 11, 15)
    if payload.service_date:
        try:
            sdate = datetime.strptime(payload.service_date, "%Y-%m-%d").date()
        except Exception:
            pass

    member_id = payload.member_ref.strip() if payload.member_ref and payload.member_ref.strip() else f"M-{uuid.uuid4().hex[:6]}"
    ins_id = payload.insurer_id or "demo-insurer"
    ins_name = payload.insurer_name or "Demo Insurance Co."
    p_id = payload.plan_id or "PLAN-GOLD"

    dx_code = payload.diagnosis_code or "DX-100"
    dx_desc = payload.diagnosis_desc or f"{payload.specialty} Intake"
    docs = payload.documents or []

    new_case = Case(
        case_id=new_id,
        insurer_id=ins_id,
        insurer_name=ins_name,
        plan_id=p_id,
        member_ref=member_id,
        group_number=payload.group_number,
        specialty=payload.specialty,
        service_date=sdate,
        visit_type="outpatient",
        diagnoses=[Diagnosis(code=dx_code, description=dx_desc)],
        items=[CaseItem(type=itype, code=icode, name=iname, quantity=1)],
        documents=docs,
        prior_approval_ref=payload.prior_approval_ref,
        status="Approved",
    )

    # Evaluate deterministically
    eval_res = evaluate_case(new_case, list(store.rules.values()))
    new_case.status = eval_res.status
    store.cases[new_id] = new_case

    store.record_audit("CASE_UPLOADED", {"case_id": new_id, "specialty": payload.specialty}, actor="claims-officer")

    return {
        "success": True,
        "case": new_case,
        "check_result": eval_res,
    }


# ---------------------------------------------------------
# Page 4: Updates
# ---------------------------------------------------------
@app.get("/api/updates", response_model=List[InsurerUpdateEntry])
def list_updates(
    item_type: Optional[str] = Query(None, description="drug, procedure, document, approval, or all"),
):
    """
    Reverse-chronological list of recent updates from the insurer.
    Each entry: what changed, item type, effective date, status, affects N open cases.
    """
    updates = store.updates
    if item_type and item_type.lower() != "all":
        updates = [u for u in updates if u.item_type.lower() == item_type.lower()]
    return updates


# ---------------------------------------------------------
# Admin Demo Trigger: "Run check now"
# ---------------------------------------------------------
@app.post("/api/check/run-now")
def run_check_now():
    """
    Daily check scheduled job / demo button:
    Pulls rule update from insurer (Drug A excluded from 1 Nov 2026),
    re-checks all open cases, and moves 3 open cases from Approved to Needs attention.
    """
    return store.run_check_now()


# ---------------------------------------------------------
# Mock Insurer Service
# ---------------------------------------------------------
@app.get("/v1/rules/snapshot")
def insurer_rules_snapshot():
    """Mock insurer endpoint exposing current rules snapshot (server-to-server)."""
    return {
        "insurer_id": "demo-insurer",
        "timestamp": utc_now().isoformat(),
        "rules": list(store.rules.values()),
    }


@app.get("/v1/rule-changes")
def insurer_rule_changes(since: Optional[str] = None):
    """Mock insurer endpoint exposing rule changes delta."""
    return {
        "insurer_id": "demo-insurer",
        "since": since,
        "updates": store.updates,
    }


@app.post("/api/simulator/reset")
@app.post("/api/simulate/reset")
def reset_demo():
    """Instantly resets back to initial seed data."""
    store.reset_demo_state()
    return {"success": True, "message": "Demo state reset to baseline."}
