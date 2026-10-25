"""Independent regression coverage for the final engineering audit."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.store import store, DataStore
from app.domain.models import Case, CaseItem, ProposedPolicyChange, Rule, RuleEffect, Target, OfficialPolicySource
from app.engine.checker import evaluate_case
from app.engine.matcher import match_insurer, match_plan
from app.intelligence.document_processor import process_uploaded_document, DocumentProcessingError
from app.intelligence.policy_extractor import _map_dict_to_proposal, _deterministic_fallback_extractor
from app.intelligence.impact_previewer import preview_claim_impact
from app.intelligence.policy_diff import compute_policy_diff
from app.connectors.change_detector import check_source_for_changes
from app.connectors.official_policy_source import CMSMedicareConnector
from app.connectors.base import SourceAccessError, SourceError

client = TestClient(app, headers={"X-Synthetic-Data": "true"})


@pytest.fixture(autouse=True)
def isolated_state():
    store.reset_state(seed_demo=False)
    store.demo_mode = False
    yield
    store.reset_state(seed_demo=False)
    store.demo_mode = False


def rule(code="J1234", insurer="aetna", plans=None, effect="covered", **overrides):
    fields = dict(rule_id="BASE-"+code, version=1, insurer_id=insurer, plan_ids=plans or ["PLAN-A"],
                  category="drug", target=Target(type="drug", code=code), effect=effect,
                  status="effective", effective_from=date(2026, 1, 1), source_ref="synthetic baseline")
    fields.update(overrides)
    return Rule(**fields)


def claim(cid="C-A", code="J1234", insurer="aetna", plan="PLAN-A", **overrides):
    fields = dict(case_id=cid, member_ref="SYNTHETIC-MEMBER", insurer_id=insurer, plan_id=plan,
                  service_date=date(2026, 11, 10), items=[CaseItem(type="drug", code=code)])
    fields.update(overrides)
    return Case(**fields)


def proposal(pid="P-A", code="J1234", **overrides):
    fields = dict(proposal_id=pid, document_id="DOC-A", document_name="synthetic-unfamiliar.pdf",
                  insurer_id="aetna", plan_ids=["PLAN-A"], target_type="drug", target_code=code,
                  proposed_effect="excluded", effective_from=date(2026, 11, 1),
                  supporting_quote="Aetna: PLAN-A excludes drug J1234 effective November 1, 2026.")
    fields.update(overrides)
    return ProposedPolicyChange(**fields)


def seed():
    baseline = rule()
    store.rules = {"BASE-J1234_v1": baseline}
    store.cases = {"C-A": claim()}
    return baseline


@pytest.mark.parametrize("insurer,plan,item_type,code,service_date,expected", [
    ("aetna", "PLAN-A", "drug", "J1234", date(2026, 11, 10), "Not covered"),
    ("uhc", "PLAN-A", "drug", "J1234", date(2026, 11, 10), "No rule found, verify with the insurer"),
    ("aetna", "PLAN-B", "drug", "J1234", date(2026, 11, 10), "No rule found, verify with the insurer"),
    ("aetna", "PLAN-A", "procedure", "J1234", date(2026, 11, 10), "No rule found, verify with the insurer"),
    ("aetna", "PLAN-A", "drug", "J12340", date(2026, 11, 10), "No rule found, verify with the insurer"),
    ("aetna", "PLAN-A", "drug", "J1234", date(2026, 10, 31), "No rule found, verify with the insurer"),
])
def test_engine_boundaries(insurer, plan, item_type, code, service_date, expected):
    r = rule(effect="excluded", effective_from=date(2026, 11, 1))
    c = claim(insurer=insurer, plan=plan, service_date=service_date, items=[CaseItem(type=item_type, code=code, name="J1234 matching name must not bypass code")])
    assert evaluate_case(c, [r]).results[0].result == expected


@pytest.mark.parametrize("rule_system,item_system,expected", [
    ("HCPCS", "HCPCS", "Not covered"),
    ("hcpcs", "HCPCS", "Not covered"),
    (None, None, "Not covered"),
    ("HCPCS", "CPT", "No rule found, verify with the insurer"),
    ("HCPCS", None, "No rule found, verify with the insurer"),
    (None, "HCPCS", "No rule found, verify with the insurer"),
])
def test_code_system_must_match_when_declared(rule_system, item_system, expected):
    r = rule(effect="excluded", target=Target(type="drug", code="J1234", code_system=rule_system))
    c = claim(items=[CaseItem(type="drug", code="J1234", code_system=item_system)])
    assert evaluate_case(c, [r]).results[0].result == expected


@pytest.mark.parametrize("unknown", [None, "", "unknown", "*", "none"])
def test_missing_insurer_never_matches(unknown):
    assert not match_insurer(unknown, "aetna")
    assert not match_insurer("aetna", unknown)


def test_aliases_and_wildcard_require_explicit_scope():
    assert match_insurer("UnitedHealthcare", "uhc")
    assert not match_insurer("united-random-payer", "uhc")
    assert not match_insurer("payer-a", "payer_a")
    assert match_plan(["*"], "PLAN-A")
    assert not match_plan([], "PLAN-A")
    assert not match_plan(["*"], None)
    assert not match_plan(["*"], "*")


@pytest.mark.parametrize("field,value", [("insurer_id", None), ("insurer_id", "unknown"), ("plan_ids", []),
    ("target_type", None), ("target_code", None), ("proposed_effect", None), ("effective_from", None), ("supporting_quote", "")])
def test_incomplete_proposals_cannot_preview_or_approve(field, value):
    seed()
    p = proposal(**{field: value})
    store.save_proposal(p)
    before = deepcopy(store.rules)
    preview = preview_claim_impact([p])
    assert preview.affected_cases == preview.new_risks == 0
    assert preview.notice and "Missing mandatory fields" in preview.notice
    with pytest.raises(ValueError, match="incomplete"):
        store.approve_proposal(p.proposal_id)
    assert store.rules == before
    assert store.proposals[p.proposal_id].review_state == "pending_review"


def test_plan_scopes_and_types_do_not_version_each_other():
    seed()
    for p in [proposal(plan_ids=["PLAN-B"]), proposal(target_type="procedure"), proposal(insurer_id="uhc")]:
        assert not compute_policy_diff(p).has_existing_rule
    p = proposal()
    assert compute_policy_diff(p).existing_rule_id == "BASE-J1234"


def test_preview_multiple_changes_counts_claims_and_has_no_side_effects():
    seed()
    store.rules["BASE-J5678_v1"] = rule("J5678")
    store.cases["C-A"].items.append(CaseItem(type="drug", code="J5678"))
    store.cases["C-B"] = claim("C-B", insurer="uhc")
    snapshot = deepcopy((store.rules, store.cases, store.alerts, store.audit_log))
    result = preview_claim_impact([proposal(), proposal("P-B", "J5678")])
    assert result.total_cases_checked == 2
    assert result.affected_cases == result.new_risks == 1
    assert len(result.cases) == 2
    assert (store.rules, store.cases, store.alerts, store.audit_log) == snapshot


def test_existing_risk_is_not_counted_as_new():
    seed()
    store.rules["BASE-J1234_v1"].effect = RuleEffect.REQUIRES_PRIOR_APPROVAL
    assert preview_claim_impact([proposal()]).new_risks == 0
    assert preview_claim_impact([proposal()]).affected_cases == 1


def test_full_delay_cancellation_alert_and_history_workflow():
    baseline = seed()
    original = baseline.model_dump()
    pa = rule("PROC-1", rule_id="AUTH", category="procedure", target=Target(type="procedure", code="PROC-1"), effect="requires_prior_approval")
    store.rules["AUTH_v1"] = pa
    store.cases["C-A"].items.append(CaseItem(type="procedure", code="PROC-1"))
    p = proposal()
    store.save_proposal(p)
    new_rule, affected = store.approve_proposal(p.proposal_id)
    assert affected == ["C-A"]
    assert baseline.model_dump() == original  # no mutation of v1
    exclusion_alert = next(a for a in store.get_open_alerts() if a.item_code == "J1234")
    assert exclusion_alert.evidence_quote == p.supporting_quote
    assert any(a.item_code == "PROC-1" for a in store.get_open_alerts())
    prior_time = new_rule.received_at
    delay = proposal("P-DELAY", change_type="delayed", effective_from=date(2026, 12, 1))
    store.save_proposal(delay)
    preview = preview_claim_impact([delay])
    assert preview.affected_cases == 1 and preview.new_risks == 0
    delayed_rule, _ = store.approve_proposal(delay.proposal_id)
    assert delayed_rule.version == 3
    assert store.cases["C-A"].status == "Needs attention"
    assert store.alerts[exclusion_alert.alert_id].status == "closed"
    assert any(a.item_code == "PROC-1" and a.status == "open" for a in store.alerts.values())
    # Historical knowledge snapshot remains reproducible after the delay.
    old = evaluate_case(store.cases["C-A"], store.get_all_rules(), as_of=prior_time)
    assert old.results[0].result == "Not covered"
    cancellation = proposal("P-CANCEL", change_type="cancelled", effective_from=date(2026, 12, 15))
    store.save_proposal(cancellation)
    store.approve_proposal(cancellation.proposal_id)
    c = claim(service_date=date(2026, 12, 20))
    assert evaluate_case(c, store.get_all_rules()).results[0].result == "Covered"
    assert any(e["action"] == "ALERT_CLOSED" for e in store.audit_log)
    assert sum(e["action"] == "POLICY_PROPOSAL_APPROVED" for e in store.audit_log) == 3


def test_concurrent_approval_is_idempotent_and_bad_edits_are_atomic():
    seed()
    p = proposal()
    store.save_proposal(p)
    original = p.model_dump()
    with pytest.raises(ValueError):
        store.approve_proposal(p.proposal_id, edited_fields={"effective_from": "not-a-date", "insurer_id": "uhc"})
    assert store.proposals[p.proposal_id].model_dump() == original
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.approve_proposal(p.proposal_id), range(4)))
    assert {r.version for r, _ in results} == {2}
    assert len(store.rules) == 2
    assert len(store.updates) == 1
    assert sum(e["action"] == "POLICY_PROPOSAL_APPROVED" for e in store.audit_log) == 1
    with pytest.raises(ValueError, match="cannot be rejected"):
        store.reject_proposal(p.proposal_id)


def test_empty_caseload_api_does_not_create_demo_cases():
    client.post("/api/settings/demo-mode", json={"demo_mode": False})
    client.delete("/api/cases")
    result = client.post("/api/policies/preview-impact", json={"proposals": [proposal().model_dump(mode="json")]}).json()
    assert result["total_cases_checked"] == result["affected_cases"] == 0
    assert not result["is_demo_mode"]
    assert not store.cases


def test_html_form_keeps_policy_and_removes_navigation_and_scripts():
    html = b'<html><head><title>CMS policy</title></head><body><form><nav>Random menu</nav><input value="secret"><main><h1>Coverage NCD</h1><h2>Indications</h2><p>Drug &amp; policy criteria.</p><script>bad()</script></main><footer>Version 99</footer></form></body></html>'
    result = process_uploaded_document(html, "ncd.aspx", "text/html")
    assert result["file_type"] == "html"
    assert "Drug & policy criteria." in result["raw_text"]
    assert "Indications" in result["raw_text"]
    assert "Random menu" not in result["raw_text"]
    assert "bad()" not in result["raw_text"]
    assert "Version 99" not in result["raw_text"]
    assert result["policy_title"] == "Coverage NCD"


def source():
    s = OfficialPolicySource(source_id="CMS-TEST", name="CMS test", insurer_name="CMS", official_url="https://www.cms.gov/policy")
    store.save_source(s)
    return s


HTML = b'<html><body><form><nav>Menu 1</nav><main><h1>CMS Test</h1><p>CMS policy for all plans: drug J1234 is excluded effective November 1, 2026.</p></main></form></body></html>'


def test_successful_download_failed_extraction_retries_then_stages_exactly_once():
    s = source()
    with patch("app.connectors.change_detector.CMSMedicareConnector.fetch_latest_document", return_value=(HTML, "policy.html", {"source_url": s.official_url})), \
         patch("app.connectors.change_detector.extract_policies_with_gemini", side_effect=[RuntimeError("provider failed"), ([proposal()], True, None)]) as extractor:
        first = check_source_for_changes(s)
        assert first.status == "extraction_failed"
        assert s.content_hash is None and s.downloaded_content_hash
        second = check_source_for_changes(s)
        assert second.status == "pending_review"
        third = check_source_for_changes(s)
        assert third.status == "unchanged"
        assert extractor.call_count == 2
    assert len(store.proposals) == 1
    assert s.processed_at and s.last_checked_at and s.fetched_at
    assert store.proposals["P-A"].source_url == s.official_url


def test_gemini_failure_with_fallback_remains_retryable():
    s = source()
    with patch("app.connectors.change_detector.extract_policies_with_gemini", return_value=([proposal()], False, "AI service temporarily unavailable")):
        result = check_source_for_changes(s, HTML)
    assert result.status == "extraction_failed"
    assert s.content_hash is None and not store.proposals


def test_html_policy_fingerprint_ignores_chrome_but_detects_revision():
    s = source()
    rules_before = deepcopy(store.rules)
    initial = check_source_for_changes(s, HTML)
    assert initial.status == "pending_review"
    changed_menu = check_source_for_changes(s, HTML.replace(b"Menu 1", b"New unrelated navigation"))
    assert changed_menu.status == "unchanged"
    revised = check_source_for_changes(s, HTML.replace(b"November 1", b"December 1"))
    assert revised.status == "pending_review"
    assert initial.content_hash != revised.content_hash
    assert len(store.proposals) == 2
    assert store.rules == rules_before
    assert all(p.review_state != "approved" for p in store.proposals.values())


def test_concurrent_source_checks_do_not_duplicate_proposals():
    s = source()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: check_source_for_changes(s, HTML), range(4)))
    assert sum(r.status == "pending_review" for r in results) == 1
    assert len(store.proposals) == 1


@pytest.mark.parametrize("url", ["http://www.cms.gov/policy", "https://127.0.0.1/", "https://www.cms.gov.evil.com/", "https://evil.com/", "https://www.cms.gov:8443/", "https://user:password@www.cms.gov/", "file:///etc/passwd"])
def test_ssrf_urls_rejected_before_fetch(url):
    with patch("httpx.Client.get") as fetch, pytest.raises(SourceAccessError):
        CMSMedicareConnector().fetch_latest_document(url)
    fetch.assert_not_called()


def response(status, content=b"", headers=None):
    result = MagicMock(status_code=status, content=content, headers=headers or {})
    return result


def test_redirect_to_private_host_is_rejected():
    with patch("httpx.Client.get", return_value=response(302, headers={"location": "https://127.0.0.1/private"})) as fetch:
        with pytest.raises(SourceAccessError):
            CMSMedicareConnector().fetch_latest_document()
        assert fetch.call_count == 1


def test_official_pdf_link_uses_existing_pdf_pipeline():
    landing = b'<main><h1>Official CMS policy</h1><a href="/policy.pdf">Download coverage policy PDF</a></main>'
    import fitz
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((50, 50), "Synthetic CMS policy PDF: J1234 is excluded.")
    content = pdf.tobytes()
    with patch("httpx.Client.get", side_effect=[response(200, landing, {"content-type": "text/html"}), response(200, content, {"content-type": "application/pdf"})]):
        data, filename, meta = CMSMedicareConnector().fetch_latest_document("https://www.cms.gov/landing")
    assert filename.endswith(".pdf")
    assert meta["source_url"] == "https://www.cms.gov/landing"
    assert meta["document_url"] == "https://www.cms.gov/policy.pdf"
    assert "J1234" in process_uploaded_document(data, filename)["raw_text"]


@pytest.mark.parametrize("content,kind", [(b"binary", "application/octet-stream"), (b"", "text/plain"), (b"x"*(10*1024*1024+1), "text/plain")])
def test_unsupported_empty_oversize_source_is_rejected(content, kind):
    with patch("httpx.Client.get", return_value=response(200, content, {"content-type": kind})):
        with pytest.raises(SourceError):
            CMSMedicareConnector().fetch_latest_document()


def test_fallback_never_fabricates_unknown_document_fields():
    p = _deterministic_fallback_extractor({"raw_text": "Policy review for Humira. Awaiting a decision."})[0]
    assert p.insurer_id is p.target_code is p.proposed_effect is p.effective_from is None
    assert p.plan_ids == []
    assert not p.is_complete
    assert "plan_ids" in p.missing_fields


def test_evidence_and_effect_are_strict():
    p = _map_dict_to_proposal({"proposed_effect": "not_covered_maybe", "supporting_quote": "A long fabricated quotation not found here"}, "DOC", "notice.txt", [], "Original policy text")
    assert p.proposed_effect is None and not p.evidence_verified and not p.is_complete


def test_security_boundary_authorization_and_invalid_uploads(monkeypatch):
    monkeypatch.setenv("COVERAGEGUARD_REVIEW_TOKEN", "test-only-secret")
    assert client.post("/api/policies/proposals/P/approve").status_code == 403
    assert client.post("/api/settings/demo-mode", json={"demo_mode": False}, headers={"X-Reviewer-Token": "test-only-secret"}).status_code == 200
    assert client.post("/api/settings/demo-mode", json={"demo_mode": False}, headers={"X-Reviewer-Token": "test-only-secret", "Origin": "https://evil.com"}).status_code == 403
    monkeypatch.delenv("COVERAGEGUARD_REVIEW_TOKEN")
    assert TestClient(app).post("/api/policies/extract", json={"text": "hi"}).status_code == 400
    assert client.post("/api/policies/extract", json={"file_b64": "%%%"}).status_code == 400
    assert client.post("/api/sources/check", json={"override_content": "fabricated CMS source"}).status_code == 403
    assert client.post("/api/cases/upload", json={"patient_text": "unknown"}).status_code == 422
    assert client.post("/api/policies/extract", files={"file": ("bad.pdf", b"not pdf", "application/pdf")}).status_code == 400


def test_unknown_intake_never_inserts_demo_patient_or_drug():
    result = client.post("/api/intake/analyze", json={"clinical_text": "Routine examination. No prescribed treatment."})
    assert result.status_code == 200
    data = result.json()
    assert data["clinical"]["items"] == []
    assert data["card"]["insurer_id"] == ""
    assert data["card"]["plan_id"] == ""
    assert data["check_result"]["status"] == "Missing or wrong info"
    assert data["clinical"]["service_date"] is None


def test_checkpoint_restores_approvals_hashes_alerts_and_audit(monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    monkeypatch.setenv("COVERAGEGUARD_STATE_PATH", str(path))
    db = DataStore()
    db.rules = {"BASE-J1234_v1": rule()}
    db.cases = {"C-A": claim()}
    db.save_proposal(proposal())
    db.approve_proposal("P-A")
    db.official_sources["CMS-TEST"] = OfficialPolicySource(source_id="CMS-TEST", name="CMS", insurer_name="CMS", official_url="https://www.cms.gov/policy", status="processing")
    db.save_checkpoint()
    restored = DataStore()
    assert restored.proposals["P-A"].review_state == "approved"
    assert len(restored.rules) == 2 and restored.get_open_alerts()
    assert restored.audit_log == db.audit_log
    assert restored.official_sources["CMS-TEST"].status == "extraction_failed"
    assert path.stat().st_mode & 0o777 == 0o600
    old_count = len(restored.updates)
    restored.approve_proposal("P-A")
    assert len(restored.updates) == old_count


def test_worker_lock_rejects_second_process(monkeypatch, tmp_path):
    import app.connectors.scheduler as scheduler
    scheduler.release_worker_lock()
    monkeypatch.setenv("COVERAGEGUARD_WORKER_LOCK", str(tmp_path / "worker.lock"))
    scheduler.acquire_worker_lock()
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    child = subprocess.run([sys.executable, "-c", "from app.connectors.scheduler import acquire_worker_lock; acquire_worker_lock()"], env=env, capture_output=True, text=True)
    assert child.returncode != 0 and "requires one API worker" in child.stderr
    scheduler.release_worker_lock()
    scheduler.acquire_worker_lock()
    scheduler.release_worker_lock()


def test_worker_lock_follows_state_path(monkeypatch, tmp_path):
    import app.connectors.scheduler as scheduler
    monkeypatch.delenv("COVERAGEGUARD_WORKER_LOCK", raising=False)
    monkeypatch.setenv("COVERAGEGUARD_STATE_PATH", str(tmp_path / "a.sqlite3"))
    assert scheduler._default_worker_lock_path() == tmp_path / "a.sqlite3.lock"
    monkeypatch.setenv("COVERAGEGUARD_STATE_PATH", "")
    assert scheduler._default_worker_lock_path().name == "worker.lock"


def test_unfamiliar_pdf_upload_to_approval_to_alert_audit_end_to_end():
    seed()
    import fitz
    pdf = fitz.open()
    page = pdf.new_page()
    quote = "Aetna: PLAN-A excludes drug J1234 effective November 1, 2026."
    page.insert_text((50, 70), "SYNTHETIC POLICY AUDIT DOCUMENT\n"+quote)
    response = client.post("/api/policies/extract", files={"file": ("unfamiliar-audit.pdf", pdf.tobytes(), "application/pdf")})
    assert response.status_code == 200
    doc = response.json()
    p = doc["proposals"][0]
    assert p["insurer_id"] == "aetna" and p["plan_ids"] == ["PLAN-A"]
    assert p["target_code"] == "J1234" and p["effective_from"] == "2026-11-01"
    assert p["supporting_quote"] == quote and p["evidence_verified"]
    assert doc["extraction_method"] == "deterministic"
    assert doc["impact_preview"]["affected_cases"] == 1
    approved = client.post(f'/api/policies/proposals/{p["proposal_id"]}/approve', json={"reviewer_notes": "Synthetic end-to-end audit; verified all source fields."})
    assert approved.status_code == 200
    assert approved.json()["rule"]["version"] == 2
    assert client.get("/api/cases/C-A").json()["check_result"]["results"][0]["result"] == "Not covered"
    assert client.get("/api/alerts?status=open").json()
    assert any(e["action"] == "POLICY_PROPOSAL_APPROVED" for e in client.get("/api/audit").json())


def test_bulletin_lookup_never_matches_a_similar_reference():
    assert store.get_bulletin("R-1042") is not None
    assert store.get_bulletin("R-1") is None


def test_cms_content_panels_ignore_help_and_navigation_inside_main():
    html = b'<main><h1 id="h1PageTitle">CMS NCD 90.2</h1><div>Changing menu</div><div id="pnlTrackingInformation"><h2>Tracking</h2><p>Effective 2020-01-27</p></div><div id="pnlDescriptionInformation"><h2>Description</h2><p>Policy requires diagnostic testing criteria.</p></div><div>Changing FAQ</div></main>'
    doc = process_uploaded_document(html, "cms.html")
    assert "Changing menu" not in doc["raw_text"] and "Changing FAQ" not in doc["raw_text"]
    assert "CMS NCD 90.2" in doc["raw_text"] and "Effective 2020-01-27" in doc["raw_text"]


def test_fallback_chooses_dated_operative_evidence_not_subject_heading():
    p = _deterministic_fallback_extractor({"raw_text": "Demo Insurance Co.\nSUBJECT: Coverage Exclusion for Drug A (DRUG-A)\nBeginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A."})[0]
    assert p.supporting_quote == "Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A."
    assert p.evidence_verified


def test_unverified_visual_evidence_requires_recorded_reviewer_confirmation():
    seed()
    p = proposal(extraction_method="gemini", evidence_verified=False)
    store.save_proposal(p)
    assert preview_claim_impact([p]).affected_cases == 0
    with pytest.raises(ValueError, match="verified_evidence"):
        store.approve_proposal(p.proposal_id)
    with pytest.raises(ValueError, match="reviewer notes"):
        store.approve_proposal(p.proposal_id, edited_fields={"evidence_confirmed_by_reviewer": True})
    r, _ = store.approve_proposal(p.proposal_id, reviewer_notes="Visually checked the original scanned policy and all extracted fields.", edited_fields={"evidence_confirmed_by_reviewer": True})
    assert r.version == 2


def test_bad_images_rejected_and_unknown_plans_do_not_match_wildcard():
    with pytest.raises(DocumentProcessingError, match="Invalid image"):
        process_uploaded_document(b"not-an-image", "fake.png")
    assert not match_plan(["*"], "unknown")
    assert Rule.model_fields["plan_ids"].default_factory() == []


def test_live_mode_run_check_does_not_apply_synthetic_unapproved_updates():
    seed()
    original = deepcopy(store.rules)
    result = store.run_check_now()
    assert result["success"] and store.rules == original
    assert "No unapproved updates" in result["message"]


def test_clear_caseload_preserves_policy_history_and_closes_alerts():
    seed()
    store.save_proposal(proposal())
    store.approve_proposal("P-A")
    assert store.get_open_alerts()
    result = client.delete("/api/cases")
    assert result.status_code == 200 and not store.cases
    assert not store.get_open_alerts()
    assert store.proposals["P-A"].review_state == "approved"
    assert len(store.rules) == 2


def test_named_policy_cannot_version_another_reference_in_same_scope():
    seed()
    p = proposal(policy_reference="DIFFERENT-POLICY")
    assert not compute_policy_diff(p).has_existing_rule
    store.save_proposal(p)
    r, _ = store.approve_proposal("P-A")
    assert r.rule_id == "DIFFERENT-POLICY" and r.version == 1
    delay = proposal("DELAY", policy_reference="NONEXISTENT", change_type="delayed", effective_from=date(2026, 12, 1))
    store.save_proposal(delay)
    with pytest.raises(ValueError, match="policy_reference"):
        store.approve_proposal("DELAY")


def test_delay_notice_pdf_upload_reconciles_alerts_without_clearing_other_items():
    seed()
    pa = rule("PROC-1", rule_id="AUTH", category="procedure", target=Target(type="procedure", code="PROC-1"), effect="requires_prior_approval")
    store.rules["AUTH_v1"] = pa
    store.cases["C-A"].items.append(CaseItem(type="procedure", code="PROC-1"))
    import pymupdf
    def upload(text, filename):
        pdf = pymupdf.open()
        pdf.new_page().insert_text((45, 65), text, fontsize=9)
        response = client.post("/api/policies/extract", files={"file": (filename, pdf.tobytes(), "application/pdf")})
        assert response.status_code == 200
        return response.json()["proposals"][0]
    p = upload("SYNTHETIC AETNA POLICY\nAetna excludes drug J1234 for PLAN-A effective November 1, 2026.", "exclusion.pdf")
    response = client.post(f'/api/policies/proposals/{p["proposal_id"]}/approve')
    assert response.status_code == 200
    old_alert = next(a for a in store.get_open_alerts() if a.item_code == "J1234")
    delay = upload("SYNTHETIC AETNA DELAY NOTICE\nAetna postpones the exclusion for drug J1234 under PLAN-A until December 1, 2026.", "separate-delay.pdf")
    assert delay["change_type"] == "delayed" and delay["effective_from"] == "2026-12-01"
    response = client.post(f'/api/policies/proposals/{delay["proposal_id"]}/approve')
    assert response.status_code == 200
    assert store.alerts[old_alert.alert_id].status == "closed"
    assert store.cases["C-A"].status == "Needs attention"
    assert any(a.item_code == "PROC-1" for a in store.get_open_alerts())


def test_approval_failure_rolls_back_rules_proposal_alerts_and_audit():
    seed()
    store.save_proposal(proposal())
    before = deepcopy((store.rules, store.proposals, store.alerts, store.audit_log, store.cases))
    with patch("app.impact.analyzer.run_impact_analysis", side_effect=RuntimeError("controlled failure")):
        with pytest.raises(RuntimeError):
            store.approve_proposal("P-A")
    assert (store.rules, store.proposals, store.alerts, store.audit_log, store.cases) == before
    assert store.approve_proposal("P-A")[0].version == 2


def test_upload_bad_base64_intake_is_a_safe_400():
    result = client.post("/api/intake/analyze", json={"clinical_doc_b64": "%%%"})
    assert result.status_code == 400
    assert "Invalid" in result.json()["detail"]


def test_state_reset_during_source_extraction_does_not_resurrect_old_proposals():
    s = source()
    def resetting_extractor(document):
        store.reset_state(seed_demo=False)
        return [proposal()], True, None
    with patch("app.connectors.change_detector.extract_policies_with_gemini", side_effect=resetting_extractor):
        result = check_source_for_changes(s, HTML)
    assert result.status == "extraction_failed"
    assert not store.proposals and not store.get_source(s.source_id)


def test_gemini_http_failure_keeps_key_out_of_urls_logs_and_errors(capsys):
    from app.intelligence.policy_extractor import extract_policies_with_gemini
    secret = "synthetic-secret-for-regression"
    r = MagicMock(status_code=429, text=f"DO NOT LOG {secret}")
    with patch("app.intelligence.policy_extractor.get_gemini_api_key", return_value=secret), patch("httpx.Client.post", return_value=r) as post:
        proposals, used_live, error = extract_policies_with_gemini({"raw_text": "Aetna policy: PLAN-A excludes drug J1234 effective November 1, 2026."})
    assert not used_live and "429" in error
    assert secret not in post.call_args.args[0]
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == secret
    assert secret not in capsys.readouterr().out and secret not in error
    assert proposals and proposals[0].extraction_method == "deterministic"


def test_gemini_success_preserves_multiple_plan_scopes_and_verified_evidence():
    from app.intelligence.policy_extractor import extract_policies_with_gemini
    quote = "Aetna excludes drug J1234 for PLAN-A effective November 1, 2026."
    changes = [dict(insurer_id="aetna", plan_ids=[plan], target_type="drug", target_code="J1234", proposed_effect="excluded", effective_from="2026-11-01", supporting_quote=quote.replace("PLAN-A", plan)) for plan in ["PLAN-A", "PLAN-B"]]
    quote = quote + " " + quote.replace("PLAN-A", "PLAN-B")
    r = MagicMock(status_code=200)
    r.json.return_value = {"candidates": [{"content": {"parts": [{"text": json.dumps({"policy_changes": changes})}]}}]}
    with patch("app.intelligence.policy_extractor.get_gemini_api_key", return_value="test-key"), patch("httpx.Client.post", return_value=r):
        proposals, used_live, error = extract_policies_with_gemini({"raw_text": quote, "pages": [{"page": 1, "text": quote}]})
    assert used_live and error is None
    assert len(proposals) == 2 and proposals[0].evidence_verified
    assert all(p.extraction_method == "gemini" for p in proposals)


def test_verified_quote_does_not_validate_fabricated_structured_fields():
    quote = "Aetna policy review for PLAN-A drug J1234; a decision will follow."
    p = _map_dict_to_proposal(dict(insurer_id="uhc", plan_ids=["PLAN-B"], target_type="drug", target_code="J5678",
                                  effective_from="2026-11-01", proposed_effect="excluded", supporting_quote=quote),
                              "DOC", "unfamiliar.txt", [{"page": 1, "text": quote}], quote)
    assert p.evidence_verified
    assert p.insurer_id is p.target_code is p.effective_from is p.proposed_effect is None
    assert p.plan_ids == [] and not p.is_complete


def test_scanned_extraction_keeps_unverified_fields_for_human_correction():
    p = _map_dict_to_proposal(dict(insurer_id="aetna", plan_ids=["PLAN-A"], target_type="drug", target_code="J1234",
                                  effective_from="2026-11-01", proposed_effect="excluded", supporting_quote="Aetna excludes J1234 on November 1, 2026."),
                              "DOC", "scan.png", [{"page": 1, "text": "", "is_scanned": True}], "")
    assert p.insurer_id == "aetna" and p.target_code == "J1234" and p.effective_from
    assert not p.evidence_verified and not p.is_complete


def test_new_rule_identity_is_stable_between_preview_and_approval():
    from app.intelligence.rule_builder import build_proposed_rule
    p = proposal(plan_ids=["PLAN-NEW"])
    first = build_proposed_rule(p, store.get_all_rules())
    second = build_proposed_rule(p, store.get_all_rules())
    store.save_proposal(p)
    approved, _ = store.approve_proposal("P-A")
    assert first.rule_id == second.rule_id == approved.rule_id


def test_fixture_source_is_never_advertised_as_live_cms_connection():
    s = source()
    result = check_source_for_changes(s, HTML)
    assert result.is_simulated and s.last_check_simulated
    assert all(store.proposals[pid].is_synthetic for pid in result.proposals_created)
    assert not client.get('/api/sources/status').json()['is_real_external_connection']
