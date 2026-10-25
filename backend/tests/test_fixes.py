"""
CoverageGuard — Fixes 1-7, 9-10 Regression & Safety Test Suite.
Validates:
1. AI extraction safety (no invented values, strict completeness checks)
2. Multimodal document processing (multipage PDF, scanned pages, page 3 extraction, error handling)
3. Shared deterministic rule matching (no substring matches, insurer/plan boundaries)
4. Policy lifecycle (delays, cancellations, multi-issue claims, duplicate approval prevention)
5. Claim evaluation & what-if preview (empty store behavior, side-effect-free preview)
"""

import pytest
import io
import pypdf
from datetime import date, datetime
from typing import Dict, Any, List

from app.domain.models import (
    ProposedPolicyChange,
    Rule,
    Target,
    RuleCategory,
    RuleEffect,
    RuleStatus,
    Case,
    CaseItem,
    ItemVerdict,
    CaseCheckResult,
)
from app.engine.matcher import (
    normalize_code,
    match_insurer,
    match_plan,
    match_proposal_to_target,
    match_proposal_to_rule,
    is_rule_applicable_on_date,
)
from app.engine.checker import evaluate_case
from app.intelligence.policy_extractor import (
    extract_policies_with_gemini,
    _deterministic_fallback_extractor,
    _map_dict_to_proposal,
)
from app.intelligence.evidence_validator import (
    verify_evidence_in_document,
    validate_extracted_policy,
)
from app.intelligence.document_processor import (
    process_uploaded_document,
    DocumentProcessingError,
    detect_file_type,
    MAX_FILE_SIZE_BYTES,
)
from app.intelligence.impact_previewer import preview_claim_impact
from app.db.store import store


# ===========================================================================
# 1. AI EXTRACTION SAFETY (FIX 1 & FIX 6)
# ===========================================================================

def test_unfamiliar_insurance_doc_no_invented_fields():
    """
    Unfamiliar document with Ozempic mention but no insurer, billing code, or effective date.
    MUST NOT invent 'DRUG-A', 'demo-insurer', 'NOTICE-2026', or '2026-11-01'.
    """
    unfamiliar_text = (
        "Clinical Policy Bulletin: Ozempic will require additional documentation regarding BMI "
        "and HbA1c levels prior to coverage confirmation."
    )
    doc_data = {
        "raw_text": unfamiliar_text,
        "pages": [{"page": 1, "text": unfamiliar_text}],
        "filename": "unfamiliar.txt",
        "document_id": "DOC-UNFAMILIAR",
    }
    proposals, _, _ = extract_policies_with_gemini(doc_data)

    assert len(proposals) >= 1
    p = proposals[0]

    # Verify no fabricated values
    assert p.target_code is None or p.target_code == ""
    assert p.target_code != "DRUG-A"
    assert p.insurer_id != "demo-insurer"
    assert p.policy_reference != "NOTICE-2026"

    # Missing mandatory fields must be detected
    assert not p.is_complete
    assert "target_code" in p.missing_fields
    assert p.requires_code_mapping is True


def test_missing_mandatory_fields_blocks_store_approval():
    """
    Incomplete proposal MUST raise ValueError if approval is attempted before reviewer fixes it.
    """
    incomplete_prop = ProposedPolicyChange(
        proposal_id="PROP-INCOMPLETE-TEST",
        document_id="DOC-INCOMPLETE",
        document_name="notice.pdf",
        policy_title="Incomplete Notice",
        insurer_id=None,  # Missing insurer
        target_name="Novel Biologic",
        target_code=None,  # Missing code
        effective_from=None,  # Missing date
        proposed_effect=RuleEffect.REQUIRES_PRIOR_APPROVAL,
        supporting_quote="Novel Biologic requires PA.",
        is_complete=False,
        missing_fields=["insurer_id", "target_code", "effective_from"],
    )
    store.save_proposal(incomplete_prop)

    with pytest.raises(ValueError) as excinfo:
        store.approve_proposal("PROP-INCOMPLETE-TEST", reviewer_notes="dr_reviewer")
    assert "incomplete" in str(excinfo.value).lower()


def test_unrelated_document_produces_no_fabricated_rules():
    """
    Unrelated document (hospital cafeteria or parking notice) must not generate valid drug rules.
    """
    unrelated_text = (
        "Hospital Cafeteria Schedule: Breakfast 7:00 AM - 10:00 AM. Lunch 11:30 AM - 2:00 PM. "
        "Visitor parking garage B is undergoing surface maintenance next Tuesday."
    )
    doc_data = {
        "raw_text": unrelated_text,
        "pages": [{"page": 1, "text": unrelated_text}],
        "filename": "cafeteria.txt",
        "document_id": "DOC-UNRELATED",
    }
    proposals, _, _ = extract_policies_with_gemini(doc_data)

    for p in proposals:
        assert p.target_code != "DRUG-A"
        assert p.is_complete is False


def test_multiple_policy_rules_no_loop_variable_leakage():
    """
    Two distinct rules must map independently without loop variable leakage or cross-contamination.
    """
    item1 = {
        "policy_title": "Oncology Pembrolizumab Exclusion",
        "insurer_id": "uhc",
        "target_type": "drug",
        "target_code": "KEY-01",
        "proposed_effect": "excluded",
        "effective_date": "2027-01-01",
        "supporting_quote": "Drug KEY-01 is excluded.",
    }
    item2 = {
        "policy_title": "Spinal Fusion PA",
        "insurer_id": "uhc",
        "target_type": "procedure",
        "target_code": "PROC-99",
        "proposed_effect": "requires_prior_approval",
        "effective_date": "2027-02-01",
        "supporting_quote": "PROC-99 requires PA.",
    }
    pages = [{"page": 1, "text": "Drug KEY-01 is excluded. PROC-99 requires PA."}]
    p1 = _map_dict_to_proposal(item1, "DOC-1", "notice1.pdf", pages, "doc text")
    p2 = _map_dict_to_proposal(item2, "DOC-2", "notice2.pdf", pages, "doc text")

    assert p1.target_code == "KEY-01"
    assert p1.target_type == "drug"
    assert p1.proposed_effect == RuleEffect.EXCLUDED

    assert p2.target_code == "PROC-99"
    assert p2.target_type == "procedure"
    assert p2.proposed_effect == RuleEffect.REQUIRES_PRIOR_APPROVAL


# ===========================================================================
# 2. MULTIMODAL DOCUMENT PROCESSING (FIX 4 & FIX 5)
# ===========================================================================

def test_multipage_pdf_page_identification():
    """
    Acceptance test for FIX 5:
    3-page PDF where:
      Page 1: Introduction
      Page 2: General Information
      Page 3: Policy exclusion with effective date
    The rule on page 3 must be correctly extracted with source_page == 3.
    """
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)

    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    doc = process_uploaded_document(pdf_bytes, filename="policy_notice_3pages.pdf")
    assert doc["page_count"] == 3
    assert len(doc["pages"]) == 3

    doc["pages"][0]["text"] = "UnitedHealthcare Clinical Bulletin Introduction. Overview of hospital services."
    doc["pages"][1]["text"] = "General Billing Guidelines for Outpatient Care and Standard Claim Formats."
    doc["pages"][2]["text"] = (
        "Section 8: Commercial Formulary Notice. Effective November 1, 2026, DRUG-A "
        "is no longer covered under PLAN-GOLD commercial plans. DRUG-A is no longer covered."
    )
    doc["raw_text"] = "\n".join(p["text"] for p in doc["pages"])

    proposals, _, _ = extract_policies_with_gemini(doc)
    assert len(proposals) >= 1

    drug_a_prop = next((p for p in proposals if p.target_code == "DRUG-A"), None)
    assert drug_a_prop is not None
    # Crucial acceptance test: source_page must be page 3!
    assert drug_a_prop.source_page == 3


def test_evidence_verification_strict_matching():
    """
    Evidence verification must reject partial prefix match and require full normalized quotation.
    """
    source_text = "Prior authorization is required for high-cost biologic therapies effective November 1, 2026."
    pages = [{"page": 1, "text": source_text}]

    # Exact match -> Verified
    is_v, page, snippet, label = verify_evidence_in_document(
        "Prior authorization is required for high-cost biologic therapies effective November 1, 2026.",
        pages,
        source_text,
    )
    assert is_v is True
    assert "verified" in label.lower()

    # Partial prefix with fabricated suffix -> Must FAIL verification
    is_v2, page2, snippet2, label2 = verify_evidence_in_document(
        "Prior authorization is required for high-cost biologic therapies without any exceptions.",
        pages,
        source_text,
    )
    assert is_v2 is False
    assert "not fully verified" in label2.lower()


def test_evidence_verification_scanned_page():
    """
    For scanned pages where OCR text might be absent or approximate, must flag visual evidence.
    """
    is_v, page, snippet, label = verify_evidence_in_document(
        quote="Section 4 exclusion policy",
        pages_text=[],
        raw_document_text="",
        is_scanned_doc=True,
    )
    assert is_v is False
    assert "visual evidence" in label.lower()


def test_document_processor_corrupted_pdf():
    """Corrupted PDF bytes must raise DocumentProcessingError gracefully."""
    with pytest.raises(DocumentProcessingError) as excinfo:
        process_uploaded_document(b"not a real pdf content", filename="corrupted.pdf")
    assert "corrupted" in str(excinfo.value).lower() or "pdf" in str(excinfo.value).lower()


def test_document_processor_unsupported_file_format():
    """Unsupported extension must raise DocumentProcessingError."""
    with pytest.raises(DocumentProcessingError) as excinfo:
        process_uploaded_document(b"binary data", filename="malicious.exe")
    assert "unsupported" in str(excinfo.value).lower()


def test_document_processor_oversized_file():
    """Files exceeding 10MB must be rejected."""
    oversized = b"0" * (MAX_FILE_SIZE_BYTES + 1024)
    with pytest.raises(DocumentProcessingError) as excinfo:
        process_uploaded_document(oversized, filename="large.pdf")
    assert "exceeds" in str(excinfo.value).lower()


# ===========================================================================
# 3. DETERMINISTIC RULE MATCHING (FIX 3)
# ===========================================================================

def test_matcher_exact_code_no_substring():
    """
    PROC-1 must NOT match PROC-10.
    DRUG-A must NOT match DRUG-AB.
    """
    prop = ProposedPolicyChange(
        proposal_id="P-1",
        document_id="DOC-1",
        document_name="notice.pdf",
        policy_title="PA for PROC-1",
        insurer_id="uhc",
        plan_ids=["*"],
        target_type="procedure",
        target_code="PROC-1",
        effective_from=date(2026, 11, 1),
    )

    # Exact match -> True
    assert match_proposal_to_target(prop, insurer_id="uhc", plan_id="commercial", item_code="PROC-1", item_type="procedure") is True
    # Substring match -> Must be FALSE
    assert match_proposal_to_target(prop, insurer_id="uhc", plan_id="commercial", item_code="PROC-10", item_type="procedure") is False
    assert match_proposal_to_target(prop, insurer_id="uhc", plan_id="commercial", item_code="PROC-100", item_type="procedure") is False


def test_matcher_insurer_isolation():
    """
    Same drug code (DRUG-A) under UHC must not match Aetna claim.
    """
    prop_uhc = ProposedPolicyChange(
        proposal_id="P-UHC",
        document_id="DOC-UHC",
        document_name="notice.pdf",
        policy_title="UHC exclusion",
        insurer_id="uhc",
        plan_ids=["*"],
        target_type="drug",
        target_code="DRUG-A",
        effective_from=date(2026, 11, 1),
    )

    assert match_proposal_to_target(prop_uhc, insurer_id="uhc", plan_id="standard", item_code="DRUG-A", item_type="drug") is True
    assert match_proposal_to_target(prop_uhc, insurer_id="aetna", plan_id="standard", item_code="DRUG-A", item_type="drug") is False
    assert match_proposal_to_target(prop_uhc, insurer_id="bcbs", plan_id="standard", item_code="DRUG-A", item_type="drug") is False


def test_matcher_plan_wildcard():
    """
    Wildcard plan '*' matches any plan for that insurer.
    Specific plan only matches exact plan.
    """
    prop_wildcard = ProposedPolicyChange(
        proposal_id="P-WILD",
        document_id="DOC-WILD",
        document_name="notice.pdf",
        policy_title="All plans",
        insurer_id="uhc",
        plan_ids=["*"],
        target_type="drug",
        target_code="DRUG-A",
    )
    assert match_proposal_to_target(prop_wildcard, insurer_id="uhc", plan_id="PLAN-GOLD", item_code="DRUG-A", item_type="drug") is True
    assert match_proposal_to_target(prop_wildcard, insurer_id="uhc", plan_id="PLAN-BRONZE", item_code="DRUG-A", item_type="drug") is True

    prop_specific = ProposedPolicyChange(
        proposal_id="P-SPEC",
        document_id="DOC-SPEC",
        document_name="notice.pdf",
        policy_title="Gold only",
        insurer_id="uhc",
        plan_ids=["PLAN-GOLD"],
        target_type="drug",
        target_code="DRUG-A",
    )
    assert match_proposal_to_target(prop_specific, insurer_id="uhc", plan_id="PLAN-GOLD", item_code="DRUG-A", item_type="drug") is True
    assert match_proposal_to_target(prop_specific, insurer_id="uhc", plan_id="PLAN-SILVER", item_code="DRUG-A", item_type="drug") is False


def test_matcher_effective_date_boundaries():
    """
    Rule effective 2026-11-01:
    - Service date 2026-10-31 is NOT applicable.
    - Service date 2026-11-01 IS applicable.
    - Service date 2026-11-15 IS applicable.
    """
    rule = Rule(
        rule_id="R-TEST",
        version=1,
        insurer_id="uhc",
        plan_ids=["*"],
        category=RuleCategory.DRUG,
        target=Target(type="drug", code="DRUG-A", name="Drug A"),
        effect=RuleEffect.EXCLUDED,
        status=RuleStatus.EFFECTIVE,
        effective_from=date(2026, 11, 1),
        source_ref="TEST-REF",
    )

    assert is_rule_applicable_on_date(rule, date(2026, 10, 31)) is False
    assert is_rule_applicable_on_date(rule, date(2026, 11, 1)) is True
    assert is_rule_applicable_on_date(rule, date(2026, 11, 15)) is True


# ===========================================================================
# 4. POLICY LIFECYCLE & MULTI-ISSUE RECALCULATION (FIX 10)
# ===========================================================================

def test_multi_issue_claim_adjudication_on_exclusion_delay():
    """
    Acceptance test for FIX 10:
    Patient claim has two problems:
      1. DRUG-A exclusion (effective 2026-11-01)
      2. Missing prior authorization for PROC-1
    When the insurer delays the DRUG-A exclusion to 2027:
      - The DRUG-A exclusion alert resolves.
      - But the claim STILL requires attention because of the missing authorization!
      - It must NOT be automatically marked Approved!
    """
    rule_drug = Rule(
        rule_id="R-DRUG-NOV",
        version=1,
        insurer_id="demo-insurer",
        plan_ids=["standard"],
        category=RuleCategory.DRUG,
        target=Target(type="drug", code="DRUG-A", name="Drug A"),
        effect=RuleEffect.EXCLUDED,
        status=RuleStatus.EFFECTIVE,
        effective_from=date(2026, 11, 1),
        source_ref="NOTICE-1",
    )
    rule_proc = Rule(
        rule_id="R-PROC-PA",
        version=1,
        insurer_id="demo-insurer",
        plan_ids=["standard"],
        category=RuleCategory.PROCEDURE,
        target=Target(type="procedure", code="PROC-1", name="Procedure 1"),
        effect=RuleEffect.REQUIRES_PRIOR_APPROVAL,
        status=RuleStatus.EFFECTIVE,
        effective_from=date(2026, 1, 1),
        source_ref="NOTICE-2",
    )

    test_case = Case(
        case_id="C-MULTI-TEST",
        specialty="Oncology",
        insurer_id="demo-insurer",
        insurer_name="Demo Insurer",
        plan_id="standard",
        member_ref="MBR-999",
        service_date=date(2026, 11, 5),
        status="Needs attention",
        prior_approval_ref=None,
        items=[
            CaseItem(item_id="it-1", type="drug", code="DRUG-A", name="Drug A"),
            CaseItem(item_id="it-2", type="procedure", code="PROC-1", name="Procedure 1"),
        ],
    )

    base_coverage = rule_drug.model_copy(update={"rule_id": "BASE-COVERAGE", "effect": RuleEffect.COVERED, "effective_from": date(2026, 1, 1)})
    rules = [base_coverage, rule_drug, rule_proc]
    eval_before = evaluate_case(test_case, rules)
    assert eval_before.status == "Needs attention"
    verdict_drug = next(v for v in eval_before.results if v.item.code == "DRUG-A")
    verdict_proc = next(v for v in eval_before.results if v.item.code == "PROC-1")
    assert verdict_drug.result == "Not covered"
    assert verdict_proc.result == "Prior approval needed"

    # Simulate delaying DRUG-A exclusion to 2027-01-01
    delayed_rule_drug = rule_drug.model_copy()
    delayed_rule_drug.effective_from = date(2027, 1, 1)

    eval_after = evaluate_case(test_case, [base_coverage, delayed_rule_drug, rule_proc])

    verdict_drug_after = next(v for v in eval_after.results if v.item.code == "DRUG-A")
    assert verdict_drug_after.result == "Covered"

    # Overall claim status MUST NOT be 'Approved' because PROC-1 still needs prior approval
    assert eval_after.status == "Needs attention"
    verdict_proc_after = next(v for v in eval_after.results if v.item.code == "PROC-1")
    assert verdict_proc_after.result == "Prior approval needed"


def test_duplicate_proposal_approval_rejected():
    """Attempting to approve the same proposal twice must be handled idempotently."""
    prop = ProposedPolicyChange(
        proposal_id="PROP-DUP-TEST",
        document_id="DOC-DUP",
        document_name="notice.pdf",
        policy_title="Single Approval Only",
        insurer_id="uhc",
        plan_ids=["*"],
        target_type="drug",
        target_name="Test Drug",
        target_code="DRUG-X",
        effective_from=date(2026, 11, 1),
        proposed_effect=RuleEffect.EXCLUDED,
        is_complete=True,
        supporting_quote="UHC excludes DRUG-X for all plans effective November 1, 2026.",
    )
    store.save_proposal(prop)

    # First approval succeeds
    r1, aff1 = store.approve_proposal("PROP-DUP-TEST", reviewer_notes="Initial approval")
    assert r1 is not None

    # Second approval is idempotent and does not create duplicate rule
    r2, aff2 = store.approve_proposal("PROP-DUP-TEST", reviewer_notes="Duplicate approval")
    assert r2.rule_id == r1.rule_id
    assert aff2 == []


# ===========================================================================
# 5. WHAT-IF PREVIEW & DEMO MODE (FIX 2 & FIX 9)
# ===========================================================================

def test_empty_caseload_in_non_demo_mode_returns_zero_cases():
    """
    Acceptance test for FIX 2:
    Clear all cases, disable demo mode.
    Preview impact must yield:
      Total cases checked: 0
      Affected cases: 0
      Synthetic claims created: 0
    """
    original_demo_mode = store.demo_mode

    try:
        store.clear_all_cases()
        store.set_demo_mode(False)

        prop = ProposedPolicyChange(
            proposal_id="PROP-EMPTY-TEST",
            document_id="DOC-EMPTY",
            document_name="notice.pdf",
            policy_title="Exclusion Policy",
            insurer_id="demo-insurer",
            target_code="DRUG-A",
            effective_from=date(2026, 11, 1),
            proposed_effect=RuleEffect.EXCLUDED,
            is_complete=True,
        )

        preview = preview_claim_impact([prop])

        assert preview.total_cases_checked == 0
        assert preview.affected_cases == 0
        assert preview.new_risks == 0
        assert len(preview.cases) == 0
        assert len(store.get_all_cases()) == 0
        assert preview.notice is not None
        assert "no pending claims" in preview.notice.lower()
    finally:
        store.reset_demo_state()
        store.set_demo_mode(original_demo_mode)


def test_what_if_preview_side_effect_free():
    """
    Acceptance test for FIX 9:
    Preview impact must be strictly read-only and side-effect-free:
    - No changes to real rules database
    - No persistent alerts generated in store
    """
    store.reset_demo_state()
    rules_before = len(store.get_all_rules())
    alerts_before = len(store.get_open_alerts())

    prop = ProposedPolicyChange(
        proposal_id="PROP-SIDE-EFFECT-TEST",
        document_id="DOC-SIDE",
        document_name="notice.pdf",
        policy_title="Simulation Only",
        insurer_id="demo-insurer",
        target_code="DRUG-A",
        effective_from=date(2026, 11, 1),
        proposed_effect=RuleEffect.EXCLUDED,
        is_complete=True,
    )

    # Run preview twice
    p1 = preview_claim_impact([prop])
    p2 = preview_claim_impact([prop])

    assert p1.affected_cases == p2.affected_cases
    assert p1.new_risks == p2.new_risks

    rules_after = len(store.get_all_rules())
    alerts_after = len(store.get_open_alerts())
    assert rules_before == rules_after
    assert alerts_before == alerts_after
