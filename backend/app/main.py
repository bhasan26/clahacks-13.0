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
import secrets
from contextlib import asynccontextmanager
from starlette.responses import JSONResponse
import os
import uuid
from pathlib import Path
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Literal
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Automatically load .env if present
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from app.db.store import store
from app.domain.models import (
    Alert,
    AlertStatus,
    AlertTask,
    Case,
    CaseItem,
    CaseStatusType,
    Diagnosis,
    ExtractedDocumentResult,
    ImpactPreviewResult,
    InsurerConnectionInfo,
    InsurerUpdateEntry,
    ItemVerdict,
    OfficialPolicySource,
    PolicyBulletin,
    PolicyDiff,
    ProposedPolicyChange,
    Rule,
    SourceCheckHistory,
    utc_now,
)
from app.connectors.change_detector import check_source_for_changes
from app.engine.checker import evaluate_case
from app.intake.analyzer import (
    analyze_clinical_document,
    analyze_insurance_card,
    get_fallback_sample,
)
from app.intelligence import (
    process_uploaded_document,
    DocumentProcessingError,
    extract_policies_with_gemini,
    compute_policy_diff,
    preview_claim_impact,
)

@asynccontextmanager
async def lifespan(app):
    from app.connectors.scheduler import acquire_worker_lock, release_worker_lock, start_source_scheduler, stop_source_scheduler
    acquire_worker_lock()
    try:
        store.load_checkpoint()
        from app.connectors.registry import ensure_sources
        ensure_sources(store)
        if os.environ.get("COVERAGEGUARD_SCHEDULER_ENABLED", "false").lower() == "true":
            start_source_scheduler(int(os.environ.get("COVERAGEGUARD_CHECK_INTERVAL", "86400")))
        yield
    finally:
        stop_source_scheduler()
        store.save_checkpoint()
        release_worker_lock()


app = FastAPI(
    title="CoverageGuard API",
    description="Hospital insurance-claims agent for coverage verification.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("COVERAGEGUARD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def local_synthetic_boundary(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = os.environ.get("COVERAGEGUARD_REVIEW_TOKEN")
        supplied = request.headers.get("x-reviewer-token", "")
        peer = request.client.host if request.client else ""
        origin = request.headers.get("origin")
        allowed_origins = os.environ.get("COVERAGEGUARD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin and origin not in allowed_origins:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        if (expected and not secrets.compare_digest(expected, supplied)) or (not expected and peer not in {"127.0.0.1", "::1", "testclient"}):
            return JSONResponse({"detail": "Reviewer authorization required."}, status_code=403)
        if request.url.path in {"/api/policies/extract", "/api/intake/analyze", "/api/cases/upload", "/api/claims/import", "/api/demo/import-hospital"} and request.headers.get("x-synthetic-data") != "true":
            return JSONResponse({"detail": "Synthetic data only. Confirm with X-Synthetic-Data: true."}, status_code=400)
        # Bound actual bytes, including chunked/base64 and multipart requests.
        limit = 14 * 1024 * 1024
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return JSONResponse({"detail": "Request exceeds upload limit."}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 400:
        store.save_checkpoint()
    return response


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
            "service_date": c.service_date.isoformat() if c.service_date else None,
            "insurer_id": c.insurer_id, "insurer_name": c.insurer_name, "plan_id": c.plan_id,
            "jurisdiction": c.jurisdiction, "policy_environment": c.policy_environment,
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
class ReviewedIntakeClaim(BaseModel):
    insurer_id: Optional[str] = None
    insurer_name: Optional[str] = None
    plan_id: Optional[str] = None
    plan_name: Optional[str] = None
    member_ref: Optional[str] = None
    group_number: Optional[str] = None
    jurisdiction: Optional[str] = None
    service_date: Optional[str] = None
    specialty: Optional[str] = None
    patient_name: Optional[str] = None
    diagnosis_code: Optional[str] = None
    diagnosis_desc: Optional[str] = None
    prior_approval_ref: Optional[str] = None
    documents: List[str] = Field(default_factory=list, max_length=100)
    items: List[CaseItem] = Field(default_factory=list, max_length=50)


class AnalyzeIntakePayload(BaseModel):
    sample_id: Optional[str] = None
    card_image_b64: Optional[str] = None
    card_text: Optional[str] = Field(default=None, max_length=1000000)
    clinical_doc_b64: Optional[str] = None
    clinical_text: Optional[str] = Field(default=None, max_length=1000000)
    selected_insurer_id: Optional[str] = None
    selected_insurer_name: Optional[str] = None
    selected_plan_id: Optional[str] = None
    policy_environment: Literal["official", "demo"] = "official"
    reviewed_claim: Optional[ReviewedIntakeClaim] = None


@app.post("/api/intake/analyze")
def analyze_intake_files(payload: AnalyzeIntakePayload):
    """Local extraction → editable claim details → the same approved-policy findings as Claims."""
    from app.intake.local_parser import (
        INSURER_NAMES,
        claim_missing_fields,
        normalize_date,
    )
    from app.engine.matcher import normalize_insurer_id
    from app.engine.findings import claim_findings, eligible_policy_rules

    try:
        if payload.reviewed_claim is not None and not any(
            (
                payload.card_image_b64,
                payload.card_text,
                payload.clinical_doc_b64,
                payload.clinical_text,
                payload.sample_id,
            )
        ):
            card, clinical = {}, {}
        elif payload.sample_id:
            preset = get_fallback_sample(payload.sample_id)
            card, clinical = preset["card"], preset["clinical"]
        else:
            card = analyze_insurance_card(payload.card_image_b64, payload.card_text)
            clinical = analyze_clinical_document(
                payload.clinical_doc_b64, payload.clinical_text
            )
    except (ValueError, DocumentProcessingError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid intake document: {exc}")
    warnings = list(card.get("validation_warnings", [])) + list(
        clinical.get("validation_warnings", [])
    )
    details = dict(clinical)
    for field in (
        "insurer_id",
        "insurer_name",
        "plan_id",
        "plan_name",
        "member_ref",
        "group_number",
        "jurisdiction",
    ):
        card_value, clinical_value = card.get(field), clinical.get(field)
        if card_value and clinical_value and card_value != clinical_value:
            details[field] = None
            warnings.append(
                f"Conflicting {field.replace('_', ' ')} in the card and clinical document. Enter the confirmed value manually."
            )
        else:
            details[field] = card_value or clinical_value
    if payload.selected_insurer_id and payload.selected_insurer_id != "auto":
        details["insurer_id"] = payload.selected_insurer_id
        details["insurer_name"] = payload.selected_insurer_name or INSURER_NAMES.get(
            normalize_insurer_id(payload.selected_insurer_id)
        )
    if payload.selected_plan_id is not None:
        details["plan_id"] = payload.selected_plan_id
    if payload.reviewed_claim is not None:
        details.update(payload.reviewed_claim.model_dump(exclude_unset=True))
    insurer_id = normalize_insurer_id(details.get("insurer_id"))
    insurer_name = details.get("insurer_name") or INSURER_NAMES.get(insurer_id)
    service = normalize_date(details.get("service_date"))
    if details.get("service_date") and not service:
        warnings.append("Invalid service date. Enter YYYY-MM-DD.")
    authorization = (details.get("prior_approval_ref") or "").strip() or None
    if authorization:
        import re

        if re.match(
            r"^(?:pending|not\b|none\b|no\b|missing\b|requested\b|unavailable\b)",
            authorization,
            re.I,
        ):
            authorization = None
            warnings.append(
                "Prior authorization is pending or not supplied; no authorization reference was confirmed."
            )
    items = [CaseItem.model_validate(item) for item in details.get("items", [])]
    for item in items:
        item.code = item.code.strip().upper()
        item.type = item.type.strip().lower()
        item.code_system = (
            item.code_system.strip().upper() if item.code_system else None
        )
    provisional = Case(
        case_id="PROVISIONAL",
        policy_environment=payload.policy_environment,
        insurer_id=insurer_id,
        insurer_name=insurer_name,
        plan_id=(details.get("plan_id") or "").strip(),
        member_ref=(details.get("member_ref") or "").strip(),
        group_number=details.get("group_number"),
        jurisdiction=(details.get("jurisdiction") or "").strip().upper() or None,
        service_date=date.fromisoformat(service) if service else None,
        specialty=details.get("specialty") or "Unspecified",
        items=items,
        diagnoses=[
            Diagnosis(
                code=details["diagnosis_code"],
                description=details.get("diagnosis_desc"),
            )
        ]
        if details.get("diagnosis_code")
        else [],
        documents=details.get("documents") or [],
        prior_approval_ref=authorization,
    )
    missing = claim_missing_fields(provisional)
    report = claim_findings(provisional, store)
    evaluation = evaluate_case(
        provisional, eligible_policy_rules(provisional, store)[0]
    )
    if missing:
        report["status"] = "Unable to verify / insufficient policy information"
        report["engine_status"] = "Missing or wrong info"
        evaluation.status = "Missing or wrong info"
    warnings.extend(row["message"] for row in missing)
    report["validation_warnings"] = list(dict.fromkeys(warnings))
    return {
        "success": True,
        "policy_environment": provisional.policy_environment,
        "privacy_notice": "Clinical files and identifiers stay local. Scanned-image OCR is unavailable; correct unresolved fields manually.",
        "extraction_method": "local_structured_text"
        if not payload.reviewed_claim
        else "reviewed_local_fields",
        "claim": provisional,
        "card": {
            key: getattr(provisional, key, None)
            for key in (
                "insurer_id",
                "insurer_name",
                "plan_id",
                "member_ref",
                "group_number",
                "jurisdiction",
            )
        }
        | {"plan_name": details.get("plan_name")},
        "clinical": {
            **details,
            "service_date": service,
            "items": items,
            "specialty": provisional.specialty,
        },
        "validation_warnings": list(dict.fromkeys(warnings)),
        "missing_fields": missing,
        "findings": report,
        "check_result": evaluation,
        "bulletin": None,
    }


# ---------------------------------------------------------
# File Upload: Save Case to Caseload
# ---------------------------------------------------------
class UploadCasePayload(BaseModel):
    jurisdiction: Optional[str] = None
    code_system: Optional[str] = None
    policy_environment: Literal["official", "demo"] = "official"
    specialty: str = "Unspecified"
    patient_text: Optional[str] = ""
    prescription_text: Optional[str] = None
    insurer_id: Optional[str] = None
    insurer_name: Optional[str] = None
    plan_id: Optional[str] = None
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
    items: Optional[List[CaseItem]] = Field(default=None, max_length=50)


@app.post("/api/cases/upload")
def upload_patient_file(payload: UploadCasePayload):
    """Upload patient file and prescription; extracts items and deterministically checks coverage."""
    new_id = f"C-{uuid.uuid4().hex[:12].upper()}"

    required = ("insurer_id", "plan_id", "member_ref", "service_date") + (
        () if payload.items is not None else ("item_code", "item_type")
    )
    missing = [
        field for field in required if not (getattr(payload, field) or "").strip()
    ]
    if missing:
        raise HTTPException(
            status_code=422, detail=f"Verified values required: {', '.join(missing)}"
        )
    try:
        sdate = date.fromisoformat(payload.service_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid service date.")
    case_items = (
        payload.items
        if payload.items is not None
        else [
            CaseItem(
                type=payload.item_type,
                code=payload.item_code,
                name=payload.item_name,
                code_system=payload.code_system,
            )
        ]
    )
    if not case_items or any(
        not item.code.strip() or item.type not in {"procedure", "drug", "service"}
        for item in case_items
    ):
        raise HTTPException(
            status_code=422,
            detail="Every requested item requires an explicit type and billing code.",
        )
    if payload.items is not None and (
        not (payload.jurisdiction or "").strip()
        or any(not (item.code_system or "").strip() for item in case_items)
    ):
        raise HTTPException(
            status_code=422,
            detail="State/jurisdiction and each item's code system are required for reviewed intake.",
        )
    member_id, ins_id, ins_name, p_id = (
        payload.member_ref,
        payload.insurer_id,
        payload.insurer_name,
        payload.plan_id,
    )
    dx_code, dx_desc, docs = (
        payload.diagnosis_code,
        payload.diagnosis_desc,
        payload.documents or [],
    )

    new_case = Case(
        case_id=new_id,
        jurisdiction=payload.jurisdiction,
        policy_environment=payload.policy_environment,
        insurer_id=ins_id,
        insurer_name=ins_name,
        plan_id=p_id,
        member_ref=member_id,
        group_number=payload.group_number,
        specialty=payload.specialty,
        service_date=sdate,
        visit_type="outpatient",
        diagnoses=[Diagnosis(code=dx_code, description=dx_desc)] if dx_code else [],
        items=case_items,
        documents=docs,
        prior_approval_ref=payload.prior_approval_ref,
        status="Approved",
    )

    # Evaluate deterministically
    from app.engine.findings import claim_findings, eligible_policy_rules

    eval_res = evaluate_case(new_case, eligible_policy_rules(new_case, store)[0])
    new_case.status = eval_res.status
    store.cases[new_id] = new_case

    store.record_audit(
        "CASE_UPLOADED",
        {"case_id": new_id, "specialty": payload.specialty},
        actor="claims-officer",
    )

    return {
        "success": True,
        "case": new_case,
        "check_result": eval_res,
        "findings": claim_findings(new_case, store),
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


@app.delete("/api/cases")
@app.post("/api/cases/clear")
def clear_cases():
    """Clear claims while preserving policy evidence, versions and audit history."""
    store.clear_all_cases()
    for alert in store.alerts.values():
        if alert.status == "open":
            alert.status = AlertStatus.CLOSED
            alert.closed_reason = "Synthetic caseload cleared."
    store.record_audit("CASES_CLEARED", {"cases_count": 0}, actor="claims-officer")
    return {"success": True, "message": "Caseload cleared; policy history retained."}


@app.post("/api/simulator/reset")
@app.post("/api/simulate/reset")
def reset_demo(seed_demo: bool = Query(True, description="Seed mock demo cases")):
    """Resets data. If seed_demo=True, loads 40 test cases for QA test runners."""
    store.reset_state(seed_demo=seed_demo)
    store.demo_mode = seed_demo
    return {"success": True, "message": f"Demo state reset (seed_demo={seed_demo})."}


@app.get("/api/audit")
def get_audit_history():
    return store.audit_log


# ---------------------------------------------------------
# Multimodal AI Policy Intelligence
# ---------------------------------------------------------
class PreviewImpactPayload(BaseModel):
    proposals: List[ProposedPolicyChange]


class ApproveProposalPayload(BaseModel):
    reviewer_notes: Optional[str] = None
    edited_fields: Optional[Dict[str, Any]] = None


class RejectProposalPayload(BaseModel):
    reviewer_notes: Optional[str] = None


@app.post("/api/policies/extract", response_model=ExtractedDocumentResult)
async def extract_policy_document(request: Request):
    """
    Multimodal Policy Extraction:
    1. Accepts PDF (selectable or scanned), images (PNG/JPG/WebP), or pasted text.
    2. Enforces 10MB file limit and extracts page text / rendered previews.
    3. Invokes Gemini to extract proposed policy rule changes.
    4. Validates evidence quotations against original text.
    5. Computes policy difference against currently active rules.
    6. Simulates claim impact on hospital caseload.
    7. Saves proposals for human review.
    """
    content_type = request.headers.get("content-type", "")
    file_bytes: bytes = b""
    filename: str = "policy_document"
    mime_type: Optional[str] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        pasted_text = form.get("text")

        if uploaded_file and hasattr(uploaded_file, "read"):
            file_bytes = await uploaded_file.read(10 * 1024 * 1024 + 1)
            filename = uploaded_file.filename or "uploaded_policy.pdf"
            mime_type = uploaded_file.content_type
        elif pasted_text:
            text_str = str(pasted_text).strip()
            file_bytes = text_str.encode("utf-8")
            filename = "pasted_policy_notice.txt"
            mime_type = "text/plain"
        else:
            raise HTTPException(status_code=400, detail="No file or text provided in form upload.")
    else:
        # JSON payload
        try:
            body = await request.json()
        except Exception:
            body = {}

        if body.get("text"):
            file_bytes = str(body["text"]).encode("utf-8")
            filename = body.get("filename", "pasted_notice.txt")
            mime_type = "text/plain"
        elif body.get("file_b64"):
            import base64
            try:
                file_bytes = base64.b64decode(body["file_b64"], validate=True)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid base64 file data.")
            filename = body.get("filename", "uploaded_doc.pdf")
            mime_type = body.get("mime_type")
        else:
            raise HTTPException(status_code=400, detail="Invalid request. Provide a file or text payload.")

    try:
        doc_data = process_uploaded_document(file_bytes, filename, mime_type)
    except DocumentProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to process document.")

    # Extract policy changes via Gemini
    proposals, used_ai, ai_err = extract_policies_with_gemini(doc_data)

    # Compute difference with existing active rules
    diffs = [compute_policy_diff(p) for p in proposals]

    # Pre-compute What-If claim impact preview
    impact_preview = preview_claim_impact(proposals)

    result = ExtractedDocumentResult(
        document_id=doc_data["document_id"],
        filename=doc_data["filename"],
        file_type=doc_data["file_type"],
        page_count=doc_data["page_count"],
        pages_text=doc_data["pages"],
        raw_text=doc_data["raw_text"],
        proposals=proposals,
        diffs=diffs,
        impact_preview=impact_preview,
        extracted_at=utc_now(),
        extraction_method="gemini" if used_ai else "deterministic",
        extraction_error=ai_err, warnings=doc_data.get("warnings", []),
    )

    store.save_extracted_document(result)
    return result


@app.post("/api/policies/preview-impact", response_model=ImpactPreviewResult)
def preview_impact_endpoint(payload: PreviewImpactPayload):
    """
    What-If Claim Impact Simulator:
    Calculates affected hospital claims without persisting any rules or side effects.
    """
    return preview_claim_impact(payload.proposals)


@app.get("/api/policies/proposals", response_model=List[ProposedPolicyChange])
def list_proposals():
    """Lists all extracted policy proposals pending human review."""
    return store.get_all_proposals()


@app.get("/api/policies/proposals/{proposal_id}", response_model=ProposedPolicyChange)
def get_proposal_endpoint(proposal_id: str):
    """Retrieves a single policy change proposal."""
    prop = store.get_proposal(proposal_id)
    if not prop:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found.")
    return prop


@app.get("/api/policies/documents/{doc_id}", response_model=ExtractedDocumentResult)
def get_extracted_doc_endpoint(doc_id: str):
    """Retrieves the extracted document text, rendered page previews, and proposals."""
    doc = store.get_extracted_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return doc


@app.post("/api/policies/proposals/{proposal_id}/approve")
def approve_proposal_endpoint(
    proposal_id: str,
    payload: Optional[ApproveProposalPayload] = None,
):
    """
    Human Approves Proposed Policy:
    1. Applies any corrections from reviewer.
    2. Saves new rule version into immutable store.
    3. Automatically re-evaluates all affected open claims.
    4. Publishes update entry to alerts feed and records audit log.
    """
    notes = payload.reviewer_notes if payload else None
    edits = payload.edited_fields if payload else None
    try:
        rule, affected_cases = store.approve_proposal(
            proposal_id,
            reviewer_notes=notes,
            edited_fields=edits,
        )
        return {
            "success": True,
            "message": f"Policy approved: Rule {rule.rule_id} v{rule.version} is now active.",
            "rule": rule,
            "affected_cases_count": len(affected_cases),
            "affected_case_ids": affected_cases,
        }
    except ValueError as e:
        raise HTTPException(status_code=422 if store.get_proposal(proposal_id) else 404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Approval failed; no provider details are exposed.")


@app.post("/api/policies/proposals/{proposal_id}/reject")
def reject_proposal_endpoint(
    proposal_id: str,
    payload: Optional[RejectProposalPayload] = None,
):
    """Human rejects proposed policy change."""
    notes = payload.reviewer_notes if payload else None
    try:
        prop = store.reject_proposal(proposal_id, reviewer_notes=notes)
        return {
            "success": True,
            "message": f"Proposal {proposal_id} rejected.",
            "proposal": prop,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Explainable Action Center & Alerts (Phase 7)
# ---------------------------------------------------------------------------
class UpdateAlertTaskPayload(BaseModel):
    status: Literal["open", "in_progress", "completed"] = "completed"
    completed_by: Optional[str] = "Claims Officer"


class AcknowledgeAlertPayload(BaseModel):
    officer_note: Optional[str] = None


@app.get("/api/alerts", response_model=List[Alert])
def get_alerts_endpoint(status: Optional[str] = None):
    """Returns alerts for affected hospital claims, newest first."""
    return store.get_all_alerts(status=status)


@app.get("/api/alerts/case/{case_id}", response_model=List[Alert])
def get_case_alerts_endpoint(case_id: str):
    """Returns all alerts for a specific claim."""
    return store.get_alerts_for_case(case_id)


@app.post("/api/alerts/{alert_id}/tasks/{task_id}")
def update_alert_task_endpoint(alert_id: str, task_id: str, payload: UpdateAlertTaskPayload):
    """Updates the administrative task status on an alert."""
    alert = store.update_alert_task(
        alert_id=alert_id,
        task_id=task_id,
        task_status=payload.status,
        completed_by=payload.completed_by,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} or task {task_id} not found.")
    return {"success": True, "alert": alert}


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert_endpoint(alert_id: str, payload: Optional[AcknowledgeAlertPayload] = None):
    """Marks an alert as acknowledged."""
    note = payload.officer_note if payload else None
    alert = store.acknowledge_alert(alert_id=alert_id, officer_note=note)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return {"success": True, "alert": alert}


@app.post("/api/alerts/{alert_id}/draft")
def get_alert_draft_endpoint(alert_id: str):
    """Generates an administrative draft follow-up message for clinical staff."""
    alert = store.alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    draft = alert.draft_message or (
        f"Notice regarding Claim {alert.case_id}: Policy update for {alert.item_code} "
        f"effective {alert.effective_date or 'soon'}. Please review the attached coverage rule "
        f"({alert.rule_id}) and verify any required documentation or prior authorization before submission."
    )
    return {
        "success": True,
        "alert_id": alert_id,
        "case_id": alert.case_id,
        "draft_message": draft,
        "disclaimer": "Draft requires human review by hospital staff before sending. External automated transmission disabled.",
    }


# ---------------------------------------------------------------------------
# Official External Insurer Policy Sources (Feature 8)
# ---------------------------------------------------------------------------
class CheckSourceRequest(BaseModel):
    source_id: Optional[str] = None
    override_content: Optional[str] = None
    override_filename: Optional[str] = None


class DemoModePayload(BaseModel):
    demo_mode: bool


@app.get("/api/sources", response_model=List[OfficialPolicySource])
def list_sources_endpoint():
    """Returns all configured official external insurer policy sources."""
    return store.get_sources()


@app.post("/api/sources/check", response_model=SourceCheckHistory)
def check_source_endpoint(payload: Optional[CheckSourceRequest] = None):
    """
    Checks an official external source for changes.
    Computes SHA-256 fingerprint; if changed, parses proposals and stages for human review.
    """
    source_id = payload.source_id if payload else None
    sources = store.get_sources()
    if source_id:
        source = store.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source {source_id} not found.")
    elif sources:
        source = sources[0]
    else:
        raise HTTPException(status_code=400, detail="No official sources configured.")

    if payload and payload.override_content is not None and os.environ.get("COVERAGEGUARD_ALLOW_SOURCE_FIXTURES") != "true":
        raise HTTPException(status_code=403, detail="Source fixture overrides are disabled outside explicit test mode.")
    override_bytes = payload.override_content.encode("utf-8") if (payload and payload.override_content) else None
    override_file = payload.override_filename if payload else None

    history = check_source_for_changes(
        source,
        override_content=override_bytes,
        override_filename=override_file,
    )
    return history


@app.get("/api/sources/history", response_model=List[SourceCheckHistory])
def get_source_history_endpoint(source_id: Optional[str] = None):
    """Returns fingerprint check history for official policy sources."""
    return store.get_source_history(source_id=source_id)


@app.get("/api/sources/status")
def get_sources_status_endpoint():
    """Returns aggregate status of official external sources."""
    sources = store.get_sources()
    history = store.get_source_history()
    return {
        "total_sources": len(sources),
        "connected_sources": len([s for s in sources if s.status in {"connected", "pending_review", "unchanged"}]),
        "sources": sources,
        "latest_check": history[0] if history else None,
        "is_real_external_connection": any(s.processed_at and s.is_real_external_source and not s.last_check_simulated for s in sources),
        "scheduler_enabled": os.environ.get("COVERAGEGUARD_SCHEDULER_ENABLED", "false") == "true",
    }


@app.get("/api/settings/demo-mode")
def get_demo_mode_endpoint():
    """Returns current demo mode setting."""
    return {"demo_mode": store.demo_mode}


@app.post("/api/settings/demo-mode")
def set_demo_mode_endpoint(payload: DemoModePayload):
    """Enables or disables synthetic demo mode."""
    store.set_demo_mode(payload.demo_mode)
    return {"success": True, "demo_mode": store.demo_mode}




from app.sync_api import router as workflow_router
app.include_router(workflow_router)
