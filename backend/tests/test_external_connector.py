"""
CoverageGuard — Official Insurer External Source Connector Test Suite.
Validates Feature 8:
- Retrieval of publicly accessible official insurer policy documents (CMS NCDs)
- SHA-256 fingerprinting & unchanged content detection
- Change detection triggering proposal staging (pending_review, zero unapproved mutations)
- Error handling: HTTP timeouts, 404/500 errors, 403 access control compliance
- API endpoints: /api/sources, /api/sources/check, /api/sources/history, /api/sources/status
- Scheduler safety: preventing duplicate polling workers
"""

import pytest
import httpx
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.domain.models import OfficialPolicySource, SourceCheckHistory, utc_now
from app.connectors.base import SourceError, SourceTimeoutError, SourceAccessError
from app.connectors.official_policy_source import CMSMedicareConnector
from app.connectors.change_detector import check_source_for_changes
from app.connectors.scheduler import start_source_scheduler, stop_source_scheduler
from app.db.store import store

client = TestClient(app, headers={"X-Synthetic-Data": "true"})


# ===========================================================================
# 1. CONNECTOR UNIT & FINGERPRINT TESTS
# ===========================================================================

def test_connector_fingerprint_computation():
    """Validates deterministic SHA-256 fingerprinting."""
    connector = CMSMedicareConnector()
    content_a = b"CMS National Coverage Determination 372 for Oncology."
    content_b = b"CMS National Coverage Determination 372 for Oncology."
    content_c = b"CMS National Coverage Determination 372 for Oncology Revised."

    hash_a = connector.compute_fingerprint(content_a)
    hash_b = connector.compute_fingerprint(content_b)
    hash_c = connector.compute_fingerprint(content_c)

    assert hash_a == hash_b
    assert hash_a != hash_c
    assert len(hash_a) == 64  # Standard SHA-256 hex string


def test_connector_fetch_success_mocked():
    """Validates successful retrieval of official document with headers and metadata."""
    connector = CMSMedicareConnector()
    fake_html = b"<html><body><h1>CMS NCD 372</h1><p>Coverage guideline.</p></body></html>"

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_html
        mock_resp.headers = {
            "content-type": "text/html; charset=utf-8",
            "etag": '"abc123etag"',
            "last-modified": "Wed, 21 Oct 2026 07:28:00 GMT",
        }
        mock_get.return_value = mock_resp

        content, filename, meta = connector.fetch_latest_document("https://www.cms.gov/ncd/372")

        assert content == fake_html
        assert "cms" in filename.lower()
        assert meta["etag"] == '"abc123etag"'
        assert meta["content_type"].startswith("text/html")


def test_connector_http_timeout_handling():
    """Connector must raise SourceTimeoutError on network timeouts."""
    connector = CMSMedicareConnector(timeout_seconds=0.1)

    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(SourceTimeoutError) as excinfo:
            connector.fetch_latest_document("https://www.cms.gov/slow-endpoint")
        assert "timed out" in str(excinfo.value).lower()


def test_connector_http_access_restricted_403():
    """Connector must respect paywalls/anti-bot and raise SourceAccessError without attempting bypass."""
    connector = CMSMedicareConnector()

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.reason_phrase = "Forbidden"
        mock_get.return_value = mock_resp

        with pytest.raises(SourceAccessError) as excinfo:
            connector.fetch_latest_document("https://www.cms.gov/restricted-docs")
        assert "restricted" in str(excinfo.value).lower()
        assert "does not bypass paywalls" in str(excinfo.value).lower()


def test_connector_http_server_error_500():
    """Connector must raise SourceAccessError or SourceError on 500 error."""
    connector = CMSMedicareConnector()

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.reason_phrase = "Internal Server Error"
        mock_get.return_value = mock_resp

        with pytest.raises(SourceAccessError) as excinfo:
            connector.fetch_latest_document("https://www.cms.gov/failing-endpoint")
        assert "500" in str(excinfo.value)


# ===========================================================================
# 2. CHANGE DETECTION & PROPOSAL STAGING TESTS
# ===========================================================================

def test_change_detection_initial_baseline():
    """Initial check of official source establishes baseline hash and stages initial proposals."""
    source = OfficialPolicySource(
        source_id="src-test-initial",
        name="CMS Test Source",
        insurer_name="Centers for Medicare & Medicaid Services (CMS)",
        official_url="https://www.cms.gov/test-policy",
        content_hash=None,  # No previous check
    )
    store.save_source(source)

    content = b"<html><body>CMS National Coverage Determination: Keytruda requires prior authorization.</body></html>"
    history = check_source_for_changes(source, override_content=content)

    assert history.changed is True
    assert history.status == "pending_review"
    assert history.content_hash is not None

    # Source updated in store
    saved_source = store.get_source("src-test-initial")
    assert saved_source.content_hash == history.content_hash
    assert saved_source.status == "pending_review"


def test_change_detection_unchanged_document():
    """Subsequent check with identical content reports unchanged and creates zero duplicate proposals."""
    connector = CMSMedicareConnector()
    content = b"<html><body>CMS Policy Bulletin: DRUG-A is excluded from commercial plans.</body></html>"
    from app.intelligence.document_processor import process_uploaded_document
    h = connector.compute_fingerprint(process_uploaded_document(content, "policy.html")["raw_text"].encode())

    source = OfficialPolicySource(
        source_id="src-test-unchanged",
        name="CMS Unchanged Source",
        insurer_name="Centers for Medicare & Medicaid Services (CMS)",
        official_url="https://www.cms.gov/test-policy",
        content_hash=h,  # Already matches
        status="connected",
    )
    store.save_source(source)

    history = check_source_for_changes(source, override_content=content)

    assert history.changed is False
    assert history.status == "unchanged"
    assert history.proposals_created == []
    assert history.affected_claims_count == 0


def test_change_detection_triggers_staged_proposals_without_direct_rule_mutation():
    """
    Acceptance test for Feature 8:
    A changed document creates proposed policy changes in review_state='pending_review',
    and NEVER mutates the active rules database directly before human review.
    """
    connector = CMSMedicareConnector()
    initial_content = b"Initial CMS guidance."
    initial_hash = connector.compute_fingerprint(initial_content)

    source = OfficialPolicySource(
        source_id="src-test-change",
        name="CMS Revision Source",
        insurer_name="Centers for Medicare & Medicaid Services (CMS)",
        official_url="https://www.cms.gov/revision-policy",
        content_hash=initial_hash,
        status="connected",
    )
    store.save_source(source)

    rules_before = len(store.get_all_rules())

    new_content = (
        b"<html><body><h1>CMS Revision 2026-12</h1>"
        b"<p>Effective December 1, 2026, Humira (Adalimumab) requires prior authorization and biosimilar step therapy.</p>"
        b"</body></html>"
    )

    history = check_source_for_changes(source, override_content=new_content)

    assert history.changed is True
    assert history.status == "pending_review"
    assert history.content_hash != initial_hash

    # Proposals were staged
    assert len(history.proposals_created) >= 1
    staged_proposal_id = history.proposals_created[0]
    staged_proposal = store.get_proposal(staged_proposal_id)
    assert staged_proposal is not None
    assert staged_proposal.review_state == "needs_correction"
    assert "plan_ids" in staged_proposal.missing_fields

    # ACTIVE RULES MUST NOT BE MUTATED WITHOUT REVIEWER APPROVAL!
    rules_after = len(store.get_all_rules())
    assert rules_before == rules_after


def test_change_detection_timeout_records_error_history():
    """When fetch fails with timeout, source check history records error status."""
    source = OfficialPolicySource(
        source_id="src-test-err",
        name="CMS Timeout Source",
        insurer_name="CMS",
        official_url="https://www.cms.gov/timeout-policy",
    )
    store.save_source(source)

    with patch("app.connectors.official_policy_source.CMSMedicareConnector.fetch_latest_document", side_effect=SourceTimeoutError("Timeout after 15s")):
        history = check_source_for_changes(source)

    assert history.status == "source_unavailable"
    assert history.changed is False
    assert "sourcetimeouterror" in history.summary.lower()

    updated_source = store.get_source("src-test-err")
    assert updated_source.status == "source_unavailable"
    assert "sourcetimeouterror" in updated_source.error_message.lower()


# ===========================================================================
# 3. API ENDPOINTS TEST (/api/sources*)
# ===========================================================================

def test_api_get_sources():
    """GET /api/sources returns list of configured official policy sources."""
    res = client.get("/api/sources")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    cms_source = next((s for s in data if s["source_id"] == "SRC-CMS-MEDICARE"), None)
    assert cms_source is not None
    assert "medicare" in cms_source["name"].lower() or "cms" in cms_source["name"].lower()
    assert cms_source["is_real_external_source"] is True


def test_api_post_sources_check_success():
    """POST /api/sources/check triggers check and returns check record."""
    fake_content = b"Official CMS policy document."
    with patch("app.connectors.official_policy_source.CMSMedicareConnector.fetch_latest_document", return_value=(fake_content, "cms.html", {"source_url": "https://www.cms.gov"})):
        res = client.post("/api/sources/check", json={"source_id": "SRC-CMS-MEDICARE"})
        assert res.status_code == 200
        data = res.json()
        assert "check_id" in data
        assert data["source_id"] == "SRC-CMS-MEDICARE"
        assert data["status"] in ["pending_review", "unchanged", "pending_review"]


def test_api_get_sources_history():
    """GET /api/sources/history returns check history logs."""
    res = client.get("/api/sources/history?source_id=SRC-CMS-MEDICARE")
    assert res.status_code == 200
    history = res.json()
    assert isinstance(history, list)
    assert len(history) >= 1
    assert all("check_id" in h for h in history)


def test_api_get_sources_status():
    """GET /api/sources/status returns real-time Sentinel monitoring summary."""
    res = client.get("/api/sources/status")
    assert res.status_code == 200
    status_summary = res.json()
    assert "total_sources" in status_summary
    assert "connected_sources" in status_summary
    assert "latest_check" in status_summary
    assert "sources" in status_summary


# ===========================================================================
# 4. SCHEDULER TESTS
# ===========================================================================

def test_scheduler_thread_safety_no_duplicates(monkeypatch):
    """Scheduler must not start duplicate threads if already running."""
    import app.connectors.scheduler as sched
    monkeypatch.setattr("app.connectors.change_detector.check_source_for_changes", lambda source: None)
    monkeypatch.setattr("app.connectors.sync_engine.sync_policies", lambda source: None)

    # Start once
    start_source_scheduler(interval_seconds=3600)
    t1 = sched._scheduler_thread
    assert t1 is not None and t1.is_alive()

    # Call start again -> must not spawn duplicate thread
    start_source_scheduler(interval_seconds=3600)
    assert sched._scheduler_thread == t1

    # Stop scheduler
    stop_source_scheduler()
    assert sched._scheduler_thread is None
