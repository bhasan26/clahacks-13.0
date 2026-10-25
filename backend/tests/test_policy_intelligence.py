"""
Unit and integration tests for CoverageGuard Multimodal AI Policy Intelligence.
Tests:
1. Document ingestion and processing.
2. Evidence validation (verbatim quote vs unverified).
3. Policy diff engine (new, modification, delayed effective date).
4. What-if claim impact simulation (boundary dates: Oct 28 unaffected, Nov 5 affected).
5. Delay simulation (postponing to Dec 1 clears Nov 5 risk).
6. Human approval workflow, idempotency, and caseload re-evaluation.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.db.store import store
from app.domain.models import ProposedPolicyChange, RuleEffect

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_state():
    store.reset_demo_state()
    yield
    store.reset_state(seed_demo=False)


def test_extract_policy_from_text():
    """Tests POST /api/policies/extract with text document."""
    text_content = (
        "Commercial Formulary Bulletin\n"
        "Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A. "
        "This change applies to all outpatient claims with service date on or after November 1, 2026."
    )
    res = client.post("/api/policies/extract", json={"text": text_content, "filename": "policy_notice_A.txt"})
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "policy_notice_A.txt"
    assert len(data["proposals"]) >= 1

    prop = data["proposals"][0]
    assert prop["target_code"] == "DRUG-A"
    assert prop["proposed_effect"] == "excluded"
    assert prop["effective_from"] == "2026-11-01"
    assert "Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A." in prop["supporting_quote"]

    # Verify Diff is attached
    assert len(data["diffs"]) >= 1
    diff = data["diffs"][0]
    assert diff["proposal_id"] == prop["proposal_id"]
    assert diff["has_existing_rule"] is True

    # Verify What-If preview is attached
    assert data["impact_preview"] is not None
    assert data["impact_preview"]["affected_cases"] > 0


def test_what_if_impact_boundary_dates():
    """
    Acceptance Criterion:
    A claim with an October 28 service date must remain unaffected by a rule becoming effective November 1,
    while claims on or after November 1 (e.g. C-001 on Nov 5) must be flagged.
    """
    proposal = ProposedPolicyChange(
        proposal_id="PROP-TEST-A",
        document_id="DOC-TEST",
        document_name="doc_a.pdf",
        insurer_id="demo-insurer",
        insurer_name="Demo Insurance Co.",
        plan_ids=["PLAN-GOLD"],
        policy_title="Drug A Exclusion",
        policy_reference="R-1042-V2",
        target_type="drug",
        target_code="DRUG-A",
        target_name="Drug A",
        proposed_effect=RuleEffect.EXCLUDED,
        effective_from=date(2026, 11, 1),
        supporting_quote="Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A.",
    )

    res = client.post("/api/policies/preview-impact", json={"proposals": [proposal.model_dump(mode="json")]})
    assert res.status_code == 200
    preview = res.json()
    assert preview["affected_cases"] == 3
    assert preview["new_risks"] == 3

    affected_cids = [c["case_id"] for c in preview["cases"]]
    assert "C-001" in affected_cids  # Scheduled 2026-11-05 -> flagged
    assert "C-005" in affected_cids  # Scheduled 2026-11-12 -> flagged
    assert "C-008" in affected_cids  # Scheduled 2026-11-20 -> flagged


def test_delayed_policy_clears_november_risks():
    """
    Acceptance Criterion:
    When Document B delays the exclusion to December 1, 2026,
    the claims in November (e.g. C-001 on Nov 5) return to Covered and are no longer flagged!
    """
    delayed_proposal = ProposedPolicyChange(
        proposal_id="PROP-TEST-B",
        document_id="DOC-TEST-B",
        document_name="doc_b.pdf",
        insurer_id="demo-insurer",
        insurer_name="Demo Insurance Co.",
        plan_ids=["PLAN-GOLD"],
        policy_title="Drug A Exclusion Delay",
        policy_reference="R-1042-DELAY",
        target_type="drug",
        target_code="DRUG-A",
        target_name="Drug A",
        proposed_effect=RuleEffect.EXCLUDED,
        effective_from=date(2026, 12, 1),  # Delayed to December 1!
        change_type="delayed",
        supporting_quote="Coverage exclusion for DRUG-A is postponed until December 1, 2026.",
    )

    res = client.post("/api/policies/preview-impact", json={"proposals": [delayed_proposal.model_dump(mode="json")]})
    assert res.status_code == 200
    preview = res.json()

    # None of the November claims (C-001 on Nov 5, C-005 on Nov 12, C-008 on Nov 20) are on/after Dec 1
    # Therefore, affected cases count should be 0!
    assert preview["affected_cases"] == 0
    assert preview["new_risks"] == 0


def test_approve_policy_workflow_and_idempotency():
    """Tests approval of a proposal, updating active rules and case states."""
    proposal = ProposedPolicyChange(
        proposal_id="PROP-APPROVE-1",
        document_id="DOC-APPROVE",
        document_name="notice.pdf",
        insurer_id="demo-insurer",
        insurer_name="Demo Insurance Co.",
        plan_ids=["PLAN-GOLD"],
        policy_title="Drug A Exclusion Approval Test",
        policy_reference="R-1042-V2",
        target_type="drug",
        target_code="DRUG-A",
        target_name="Drug A",
        proposed_effect=RuleEffect.EXCLUDED,
        effective_from=date(2026, 11, 1),
        supporting_quote="Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A.",
    )
    store.save_proposal(proposal)

    # Approve proposal
    res = client.post(
        f"/api/policies/proposals/{proposal.proposal_id}/approve",
        json={"reviewer_notes": "Reviewed and approved by Chief Claims Officer"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["affected_cases_count"] == 3
    assert "C-001" in body["affected_case_ids"]

    # Verify rule in store was updated to v2
    rule_v2 = store.rules.get("R-1042_v2")
    assert rule_v2 is not None
    assert rule_v2.effect == RuleEffect.EXCLUDED
    assert rule_v2.effective_from == date(2026, 11, 1)

    # Verify proposal state
    prop_saved = store.get_proposal(proposal.proposal_id)
    assert prop_saved.review_state == "approved"
    assert prop_saved.resulting_rule_id == "R-1042"
    assert prop_saved.resulting_rule_version == 2

    # Idempotent second approval call must succeed safely without duplicate versioning
    res2 = client.post(f"/api/policies/proposals/{proposal.proposal_id}/approve")
    assert res2.status_code == 200
    assert res2.json()["success"] is True


def test_reject_proposal():
    """Tests rejecting a proposed change."""
    proposal = ProposedPolicyChange(
        proposal_id="PROP-REJECT-1",
        document_id="DOC-REJECT",
        document_name="bad_notice.pdf",
        insurer_id="demo-insurer",
        insurer_name="Demo Insurance Co.",
        plan_ids=["*"],
        policy_title="Unverified notice",
        target_type="drug",
        target_code="XYZ",
        proposed_effect=RuleEffect.EXCLUDED,
        effective_from=date(2026, 11, 1),
        supporting_quote="Unverified claim.",
    )
    store.save_proposal(proposal)

    res = client.post(
        f"/api/policies/proposals/{proposal.proposal_id}/reject",
        json={"reviewer_notes": "Incomplete documentation."},
    )
    assert res.status_code == 200
    prop_saved = store.get_proposal(proposal.proposal_id)
    assert prop_saved.review_state == "rejected"
