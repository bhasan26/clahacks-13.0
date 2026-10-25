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
from pydantic import BaseModel

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
        if os.environ.get("COVERAGEGUARD_SCHEDULER_ENABLED", "false").lower() == "true":
            start_source_scheduler(int(os.environ.get("COVERAGEGUARD_CHECK_INTERVAL", "3600")))
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
        if request.url.path in {"/api/policies/extract", "/api/intake/analyze", "/api/cases/upload"} and request.headers.get("x-synthetic-data") != "true":
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
    selected_insurer_id: Optional[str] = None
    selected_insurer_name: Optional[str] = None
    selected_plan_id: Optional[str] = None


@app.post("/api/intake/analyze")
def analyze_intake_files(payload: AnalyzeIntakePayload):
    """
    Multimodal AI Intake:
    1. Reads insurance card (optional). If card is absent, auto-detects payer from clinical order or selector.
    2. Reads clinical documents (specialty, diagnoses, drugs, procedures, attached docs).
    3. Runs the deterministic coverage engine against active payer rules.
    4. Attaches official policy bulletin citations and officer action instructions.
    """
    from app.intake.analyzer import extract_base64_and_mime
    for encoded in (payload.card_image_b64, payload.clinical_doc_b64):
        if encoded:
            try:
                clean, mime = extract_base64_and_mime(encoded)
                import base64
                process_uploaded_document(base64.b64decode(clean), "intake", mime)
            except (ValueError, DocumentProcessingError):
                raise HTTPException(status_code=400, detail="Invalid, unsupported, or oversized intake file.")
    if payload.sample_id:
        try:
            preset = get_fallback_sample(payload.sample_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        card_data = preset["card"]
        clinical_data = preset["clinical"]
    else:
        if payload.card_image_b64 or (payload.card_text and payload.card_text.strip()):
            card_data = analyze_insurance_card(
                image_b64=payload.card_image_b64,
                text_content=payload.card_text,
            )
        else:
            card_data = {}

        clinical_data = analyze_clinical_document(
            doc_b64=payload.clinical_doc_b64,
            text_content=payload.clinical_text,
        )

        # Robust Payer Resolution (Insurance card is completely optional):
        # 1. User explicitly picked an insurer from selector dropdown
        if payload.selected_insurer_id and payload.selected_insurer_id != "auto":
            ins_id = payload.selected_insurer_id
            ins_name = payload.selected_insurer_name or (
                "UnitedHealthcare" if ins_id == "uhc" else (
                    "Aetna Health" if ins_id == "aetna" else (
                        "Blue Cross Blue Shield" if ins_id == "bcbs" else "Demo Insurance Co."
                    )
                )
            )
        # 2. Card was uploaded and gave a valid payer
        elif card_data.get("insurer_id") and card_data["insurer_id"] not in ("demo-insurer", ""):
            ins_id = card_data["insurer_id"]
            ins_name = card_data.get("insurer_name") or (
                "UnitedHealthcare" if ins_id == "uhc" else (
                    "Aetna Health" if ins_id == "aetna" else (
                        "Blue Cross Blue Shield" if ins_id == "bcbs" else ins_id.upper()
                    )
                )
            )
        # 3. Clinical document gave an insurer (e.g. from header or encounter note)
        elif clinical_data.get("insurer_id"):
            ins_id = clinical_data["insurer_id"]
            ins_name = clinical_data.get("insurer_name") or (
                "UnitedHealthcare" if ins_id == "uhc" else (
                    "Aetna Health" if ins_id == "aetna" else (
                        "Blue Cross Blue Shield" if ins_id == "bcbs" else "UnitedHealthcare"
                    )
                )
            )
        # Payer and plan must be supplied by source text/card or the reviewer.
        else:
            ins_id, ins_name = "", None
        card_data["insurer_id"] = ins_id
        card_data["insurer_name"] = ins_name
        card_data["plan_id"] = payload.selected_plan_id or card_data.get("plan_id") or clinical_data.get("plan_id") or ""

    # Build provisional case for instant rule evaluation
    sdate = None
    if clinical_data.get("service_date"):
        try:
            sdate = datetime.strptime(clinical_data["service_date"], "%Y-%m-%d").date()
        except Exception:
            pass

    raw_items = clinical_data.get("items", [])
    case_items = [
        CaseItem(
            type=item.get("type", "drug"),
            code=item.get("code") or "",
            name=item.get("name", "Prescribed Item"),
            quantity=item.get("quantity", 1),
        )
        for item in raw_items
    ]


    dx_code = clinical_data.get("diagnosis_code")
    dx_desc = clinical_data.get("diagnosis_desc") or "Clinical Order Intake"

    if not sdate:
        clinical_data.setdefault("validation_warnings", []).append("Missing service date; coverage cannot be assessed.")
    provisional_case = Case(
        case_id="PROVISIONAL",
        insurer_id=card_data.get("insurer_id") or "",
        insurer_name=card_data.get("insurer_name"),
        plan_id=card_data.get("plan_id") or "",
        member_ref=card_data.get("member_ref") or f"M-{uuid.uuid4().hex[:6]}",
        group_number=card_data.get("group_number"),
        specialty=clinical_data.get("specialty") or "Cardiology",
        service_date=sdate,
        visit_type="outpatient",
        diagnoses=[Diagnosis(code=dx_code, description=dx_desc)] if dx_code else [],
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


@app.post("/api/cases/upload")
def upload_patient_file(payload: UploadCasePayload):
    """Upload patient file and prescription; extracts items and deterministically checks coverage."""
    new_id = f"C-{uuid.uuid4().hex[:12].upper()}"

    required = ("insurer_id", "plan_id", "member_ref", "item_code", "service_date", "item_type")
    missing = [field for field in required if not getattr(payload, field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Verified values required: {', '.join(missing)}")
    try:
        sdate = date.fromisoformat(payload.service_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid service date.")
    itype, icode, iname = payload.item_type, payload.item_code, payload.item_name
    member_id, ins_id, ins_name, p_id = payload.member_ref, payload.insurer_id, payload.insurer_name, payload.plan_id
    dx_code, dx_desc, docs = payload.diagnosis_code, payload.diagnosis_desc, payload.documents or []

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
        diagnoses=[Diagnosis(code=dx_code, description=dx_desc)] if dx_code else [],
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


