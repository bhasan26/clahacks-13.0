"""Multi-source, privacy, persistence and independent-service workflow regression tests."""

from datetime import date, timedelta
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import httpx, pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.store import store, DataStore
from app.domain.models import (
    Case,
    CaseItem,
    Rule,
    Target,
    ProposedPolicyChange,
    utc_now,
)
from app.domain.sync_models import PolicyCandidate
from app.connectors.policy_http import robots_allowed, PolicyHTTP
from app.connectors.sync_engine import sync_policies
from app.connectors.simulated import SimulatedInsurerConnector
from app.connectors.cms_connector import CMSCoverageConnector
from app.connectors.commercial import UHCConnector, AetnaConnector
from app.engine.checker import evaluate_case
from app.engine.findings import claim_findings
from simulators.hospital import app as hospital_app, synthetic_claims
from simulators.insurer import app as insurer_app, baseline, SimulatorState

DEMO_POLICIES = len(baseline()["policies"])

client = TestClient(app, headers={"X-Synthetic-Data": "true"})


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    store.reset_state(False)
    store.demo_mode = False
    monkeypatch.setattr(
        "simulators.insurer.state", SimulatorState("test_insurer", baseline)
    )
    import simulators.insurer as insurer

    insurer.state.path = tmp_path / "insurer.sqlite3"
    yield
    store.reset_state(False)
    store.demo_mode = False


@pytest.fixture
def services(monkeypatch):
    hospital = TestClient(hospital_app)
    insurer = TestClient(insurer_app)
    requests = []
    original = httpx.Client

    def handle(request):
        requests.append((request.method, str(request.url), request.content))
        target = (
            hospital
            if request.url.port == 8101
            else insurer
            if request.url.port == 8102
            else None
        )
        if not target:
            raise httpx.ConnectError("Unapproved test destination")
        response = target.request(
            request.method,
            request.url.raw_path.decode(),
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx.Response(
            response.status_code, content=response.content, headers=response.headers
        )

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)
    return requests, insurer


def activate_pending():
    approved = []
    for p in list(store.proposals.values()):
        if p.review_state == "pending_review":
            r = client.post(
                f"/api/policies/proposals/{p.proposal_id}/approve",
                json={
                    "reviewer_notes": "Verified exact synthetic source, plan, CA region, CPT/HCPCS code, date and evidence."
                },
            )
            assert r.status_code == 200, r.text
            approved.append(r.json())
    return approved


def test_two_independent_service_import_restriction_delay_workflow(services):
    requests, insurer = services
    imported = client.post("/api/demo/import-hospital")
    assert imported.status_code == 200 and imported.json()["imported"] == 40
    assert all(r["status"].startswith("Unable") for r in imported.json()["findings"])
    response = client.post(
        "/api/policy-sync/run", json={"source_id": "demo-insurer-api"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["runs"][0]["changed"] == DEMO_POLICIES
    assert not any(
        r.catalog_id for r in store.rules.values()
    )  # unapproved proposals have no effect
    assert len(activate_pending()) == DEMO_POLICIES
    assert (
        client.get("/api/claims/H-001/findings").json()["status"].startswith("No issue")
    )
    assert (
        client.get("/api/claims/H-003/findings").json()["status"]
        == "Known coverage exclusion or unmet requirement"
    )
    prior = deepcopy(store.rules)
    # Additional synthetic UHC upload uses the same approved scoped rule.
    uploaded = client.post(
        "/api/cases/upload",
        json={
            "insurer_id": "uhc",
            "plan_id": "DEMO-UHC-PPO",
            "jurisdiction": "CA",
            "code_system": "CPT",
            "policy_environment": "demo",
            "member_ref": "SYNTHETIC-EXTRA",
            "item_type": "procedure",
            "item_code": "27447",
            "service_date": "2026-11-12",
        },
    )
    assert uploaded.status_code == 200
    extra = uploaded.json()["case"]["case_id"]
    assert (
        client.get(f"/api/claims/{extra}/findings")
        .json()["status"]
        .startswith("No issue")
    )
    assert (
        client.post(
            "/api/demo/publish-insurer", json={"scenario": "restriction"}
        ).status_code
        == 200
    )
    run = client.post(
        "/api/policy-sync/run", json={"source_id": "demo-insurer-api"}
    ).json()["runs"][0]
    assert run["changed"] == 1 and run["unchanged"] == DEMO_POLICIES - 1
    assert store.rules == prior
    activated = activate_pending()
    assert len(activated) == 1 and activated[0]["rule"]["version"] == 2
    assert (
        len(activated[0]["affected_case_ids"]) == 9
    )  # eight scheduled UHC claims plus uploaded one
    assert "H-001" not in activated[0]["affected_case_ids"]
    assert (
        client.get("/api/claims/H-011/findings").json()["status"].startswith("No issue")
    )  # Aetna unaffected
    assert (
        client.get("/api/claims/H-003/findings").json()["findings"][0]["result"]
        == "Not covered"
    )
    alert = next(
        a
        for a in store.get_open_alerts()
        if a.case_id == "H-003" and a.item_code == "27447"
    )
    assert alert.evidence_quote and "SIMULATED" in alert.evidence_quote
    assert (
        client.post("/api/demo/publish-insurer", json={"scenario": "delay"}).status_code
        == 200
    )
    client.post("/api/policy-sync/run", json={"source_id": "demo-insurer-api"})
    delayed = activate_pending()
    assert delayed[0]["rule"]["version"] == 3
    findings = client.get("/api/claims/H-003/findings").json()
    assert findings["findings"][0]["result"] == "Covered"
    assert findings["findings"][1]["result"] == "Prior approval needed"
    assert store.alerts[alert.alert_id].status == "closed"
    assert any(
        a.case_id == "H-003" and a.item_code == "J1234" for a in store.get_open_alerts()
    )
    count = len(store.proposals)
    client.post("/api/policy-sync/run", json={"source_id": "demo-insurer-api"})
    assert len(store.proposals) == count
    assert sum(r.version == 3 for r in store.rules.values()) == 1
    # The policy source saw fixed catalog/document GETs only, with no patient data.
    policy_requests = [
        r for r in requests if ":8102/" in r[1] and "/admin/" not in r[1]
    ]
    assert all(
        method == "GET" and not payload for method, url, payload in policy_requests
    )
    assert all(
        "SYNTHETIC-MEMBER" not in url and "member" not in url and "diagnos" not in url
        for _, url, _ in policy_requests
    )


def test_official_uhc_claim_never_uses_synthetic_uhc_rules(services):
    client.post("/api/demo/import-hospital")
    client.post("/api/policy-sync/run", json={"source_id": "demo-insurer-api"})
    activate_pending()
    c = Case(**{**synthetic_claims()[0], "policy_environment": "official"})
    report = claim_findings(c, store)
    assert report["status"].startswith("Unable")
    assert not any(v["policy_reference"] for v in report["findings"])


def make_rule(**overrides):
    row = dict(
        rule_id="REAL-TEST",
        version=1,
        insurer_id="bcbs-anthem-ca",
        plan_ids=["EXACT"],
        jurisdictions=["CA"],
        category="procedure",
        target=Target(type="procedure", code="27447", code_system="CPT"),
        effect="requires_prior_approval",
        status="effective",
        effective_from=date(2026, 1, 1),
        source_ref="controlled policy evidence",
    )
    row.update(overrides)
    return Rule(**row)


@pytest.mark.parametrize(
    "payer,plan,region,code,system,expected",
    [
        ("bcbs-anthem-ca", "EXACT", "CA", "27447", "CPT", "Prior approval needed"),
        (
            "bcbs",
            "EXACT",
            "CA",
            "27447",
            "CPT",
            "No rule found, verify with the insurer",
        ),
        (
            "aetna",
            "EXACT",
            "CA",
            "27447",
            "CPT",
            "No rule found, verify with the insurer",
        ),
        (
            "bcbs-anthem-ca",
            "OTHER",
            "CA",
            "27447",
            "CPT",
            "No rule found, verify with the insurer",
        ),
        (
            "bcbs-anthem-ca",
            "EXACT",
            "NY",
            "27447",
            "CPT",
            "No rule found, verify with the insurer",
        ),
        (
            "bcbs-anthem-ca",
            "EXACT",
            None,
            "27447",
            "CPT",
            "No rule found, verify with the insurer",
        ),
        (
            "bcbs-anthem-ca",
            "EXACT",
            "CA",
            "274470",
            "CPT",
            "No rule found, verify with the insurer",
        ),
        (
            "bcbs-anthem-ca",
            "EXACT",
            "CA",
            "27447",
            "HCPCS",
            "No rule found, verify with the insurer",
        ),
    ],
)
def test_exact_affiliate_plan_region_code_system_matching(
    payer, plan, region, code, system, expected
):
    c = Case(
        case_id="TEST",
        member_ref="SYNTHETIC",
        insurer_id=payer,
        plan_id=plan,
        jurisdiction=region,
        service_date=date(2026, 11, 1),
        policy_environment="official",
        items=[CaseItem(type="procedure", code=code, code_system=system)],
    )
    assert evaluate_case(c, [make_rule()]).results[0].result == expected


def test_unapproved_unverified_expired_rules_do_not_apply():
    c = Case(
        case_id="T",
        member_ref="M",
        insurer_id="bcbs-anthem-ca",
        plan_id="EXACT",
        jurisdiction="CA",
        service_date=date(2026, 11, 1),
        items=[CaseItem(type="procedure", code="27447", code_system="CPT")],
    )
    for r in [
        make_rule(verification_status="pending_review"),
        make_rule(scope_verified=False),
        make_rule(effective_to=date(2026, 11, 1)),
    ]:
        assert evaluate_case(c, [r]).results[0].rule_id is None


def test_failed_extraction_keeps_download_for_retry_and_one_proposal(services):
    client.post("/api/demo/import-hospital")
    connector = SimulatedInsurerConnector()
    original_fetch = connector.fetch
    with (
        patch.object(connector, "fetch", side_effect=original_fetch) as fetch,
        patch(
            "app.connectors.sync_engine.compute_policy_diff",
            side_effect=RuntimeError("controlled failed extraction"),
        ),
    ):
        first = sync_policies(
            "demo-insurer-api", connectors={"demo-insurer-api": connector}
        )
        assert first["runs"][0].failed == DEMO_POLICIES and fetch.call_count == DEMO_POLICIES
    assert not store.proposals
    assert all(
        c.processed_hash is None and c.metadata.get("_retry_document")
        for c in store.policy_catalog.values()
    )
    with patch.object(
        connector,
        "fetch",
        side_effect=AssertionError("Retry must use saved downloaded content"),
    ):
        second = sync_policies(
            "demo-insurer-api", connectors={"demo-insurer-api": connector}
        )
    assert second["runs"][0].changed == DEMO_POLICIES and len(store.proposals) == DEMO_POLICIES
    third = sync_policies(
        "demo-insurer-api", connectors={"demo-insurer-api": connector}
    )
    assert third["runs"][0].unchanged == DEMO_POLICIES and len(store.proposals) == DEMO_POLICIES


def test_concurrent_sync_and_duplicate_publication_do_not_duplicate(services):
    client.post("/api/demo/import-hospital")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: sync_policies("demo-insurer-api"), range(4)))
    assert len(store.proposals) == DEMO_POLICIES
    assert any(r["status"] == "completed" for r in results)
    activate_pending()
    for _ in range(2):
        client.post("/api/demo/publish-insurer", json={"scenario": "restriction"})
    sync_policies("demo-insurer-api")
    activate_pending()
    assert (
        max(r.version for r in store.rules.values() if r.rule_id == "DEMO-UHC-KNEE")
        == 2
    )


def test_stale_proposal_cannot_activate_after_a_new_catalog_revision(services):
    client.post("/api/demo/import-hospital")
    sync_policies("demo-insurer-api")
    original = next(
        p for p in store.proposals.values() if p.policy_reference == "DEMO-UHC-KNEE"
    )
    client.post("/api/demo/publish-insurer", json={"scenario": "restriction"})
    sync_policies("demo-insurer-api")
    with pytest.raises(ValueError, match="latest discovered"):
        store.approve_proposal(original.proposal_id, reviewer_notes="Reviewed")


def test_sqlite_persistence_catalog_versions_sync_runs_and_legacy_json_migration(
    monkeypatch, tmp_path, services
):
    client.post("/api/demo/import-hospital")
    sync_policies("demo-insurer-api")
    activate_pending()
    path = tmp_path / "coverageguard.sqlite3"
    monkeypatch.setenv("COVERAGEGUARD_STATE_PATH", str(path))
    store.save_checkpoint()
    restored = DataStore()
    assert (
        len(restored.cases) == 40
        and len(restored.policy_catalog) == DEMO_POLICIES
        and len(restored.policy_versions) == DEMO_POLICIES
    )
    assert restored.sync_runs and all(
        p.review_state == "approved" for p in restored.proposals.values()
    )
    assert path.stat().st_mode & 0o777 == 0o600
    import sqlite3

    with sqlite3.connect(path) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM records WHERE kind='policy_catalog' AND insurer_id='uhc'"
            ).fetchone()[0]
            == 2
        )
    legacy = tmp_path / "legacy" / "state.json"
    monkeypatch.setenv("COVERAGEGUARD_STATE_PATH", str(legacy))
    store.save_checkpoint()
    new_path = legacy.parent / "coverageguard.sqlite3"
    monkeypatch.setenv("COVERAGEGUARD_STATE_PATH", str(new_path))
    migrated = DataStore()
    migrated.save_checkpoint()
    assert new_path.exists() and len(migrated.policy_catalog) == DEMO_POLICIES and legacy.exists()


def test_robots_wildcard_disallow_prevents_anthem_pdf_download():
    text = "User-agent: *\nDisallow: /*.pdf$\nDisallow: /medicalpolicies\nAllow: /docs/public/allowed.pdf"
    assert not robots_allowed(text, "https://www.anthem.com/docs/private.pdf")
    assert not robots_allowed(text, "https://www.anthem.com/medicalpolicies/x")
    assert robots_allowed(text, "https://www.anthem.com/docs/public/allowed.pdf")
    assert robots_allowed(
        text, "https://www.anthem.com/ca/provider/policies/clinical-guidelines/"
    )


def test_cms_schema_mapping_does_not_fabricate_lcd_jurisdiction():
    c = CMSCoverageConnector()
    with patch.object(
        c,
        "_pages",
        side_effect=[
            [
                {
                    "document_id": 372,
                    "document_version": 2,
                    "title": "NGS",
                    "last_updated": "10/01/2026",
                    "url": "/data/ncd?ncdid=372",
                }
            ],
            [
                {
                    "document_id": 123,
                    "document_version": 3,
                    "title": "Local policy",
                    "effective_date": "11/01/2026",
                    "contractor_name_type": "MAC",
                    "url": "https://www.cms.gov/policy",
                }
            ],
        ],
    ):
        rows = c.discover()
    assert rows[0].revision == "2" and rows[0].effective_from is None
    assert (
        rows[1].requires_billing_articles
        and rows[1].jurisdictions == []
        and not rows[1].scope_verified
    )


def test_cms_pagination_uses_explicit_next_url_and_refuses_opaque_tokens():
    c = CMSCoverageConnector()
    with patch.object(
        c,
        "_json",
        side_effect=[
            {
                "data": [{"id": 1}],
                "meta": {
                    "next_token": "https://api.coverage.cms.gov/v1/reports/page-2"
                },
            },
            {"data": [{"id": 2}], "meta": {"next_token": ""}},
        ],
    ):
        assert list(c._pages("/v1/reports/test")) == [{"id": 1}, {"id": 2}]
    with patch.object(
        c, "_json", return_value={"data": [], "meta": {"next_token": "opaque"}}
    ):
        with pytest.raises(Exception, match="opaque pagination"):
            list(c._pages("/v1/reports/test"))


def test_public_scope_cannot_activate_without_human_verification():
    p = ProposedPolicyChange(
        proposal_id="P",
        document_id="D",
        document_name="public",
        insurer_id="uhc",
        plan_ids=["EXACT"],
        target_type="procedure",
        target_code="27447",
        proposed_effect="excluded",
        effective_from=date(2026, 11, 1),
        supporting_quote="Real evidence quotation",
        scope_verified=False,
    )
    store.save_proposal(p)
    with pytest.raises(ValueError, match="verified_plan"):
        store.approve_proposal("P")


def test_clinical_documents_cannot_trigger_any_external_ai_request():
    from app.intake.analyzer import analyze_clinical_document, call_gemini_extraction

    with patch(
        "httpx.Client.post",
        side_effect=AssertionError("Clinical AI transmission is forbidden"),
    ):
        assert (
            call_gemini_extraction([{"text": "SYNTHETIC clinical note"}], "extract")
            is None
        )
        data = analyze_clinical_document(
            text_content="Member: SYNTHETIC-MEMBER\nService Date: 2026-11-10\nUHC\nProcedure 27447"
        )
    assert data["items"] and data["insurer_id"] == "uhc"


def test_known_verified_official_uhc_rule_can_produce_a_scoped_finding():
    c = Case(
        case_id="UHC-OFFICIAL-FIXTURE",
        insurer_id="uhc",
        plan_id="VERIFIED-PLAN",
        jurisdiction="CA",
        policy_environment="official",
        member_ref="SYNTHETIC",
        service_date=date(2026, 11, 10),
        items=[CaseItem(type="procedure", code="27447", code_system="CPT")],
    )
    candidate = PolicyCandidate(
        catalog_id="controlled-uhc:KNEE",
        source_id="controlled-uhc",
        insurer_id="uhc",
        insurer_name="UHC controlled test",
        policy_id="KNEE",
        title="Controlled evidence",
        source_url="https://www.uhcprovider.com/controlled-test",
        revision="1",
        document_id="DOC",
        last_successful_sync=utc_now(),
    )
    store.policy_catalog[candidate.catalog_id] = candidate
    store.cases[c.case_id] = c
    p = ProposedPolicyChange(
        proposal_id="CONTROLLED",
        document_id="DOC",
        document_name="controlled-policy.txt",
        catalog_id=candidate.catalog_id,
        source_revision="1",
        insurer_id="uhc",
        plan_ids=["VERIFIED-PLAN"],
        jurisdictions=["CA"],
        code_system="CPT",
        target_type="procedure",
        target_code="27447",
        proposed_effect="covered",
        effective_from=date(2026, 1, 1),
        supporting_quote="Controlled fixture explicitly covers CPT 27447 for VERIFIED-PLAN in CA.",
        source_url=candidate.source_url,
        scope_verified=False,
    )
    store.save_proposal(p)
    assert claim_findings(c, store)["status"].startswith("Unable")
    store.approve_proposal(
        p.proposal_id,
        reviewer_notes="Controlled synthetic test of human verification, not a live insurer benefit determination.",
        edited_fields={"scope_verified": True},
    )
    report = claim_findings(c, store)
    assert report["status"] == "No issue detected under verified checked rules"
    assert report["findings"][0]["source_evidence"] == p.supporting_quote
    # Staleness or an observed unprocessed update removes the definitive checked-rule result.
    candidate.last_successful_sync = utc_now() - timedelta(days=3)
    assert claim_findings(c, store)["status"].startswith("Unable")


def test_discovery_plan_and_environment_filters_prevent_unrelated_downloads(services):
    from app.connectors.sync_engine import relevant, queries_for_cases

    connector = SimulatedInsurerConnector()
    candidates = connector.discover()
    claim = Case(**{**synthetic_claims()[0], "plan_id": "WRONG-PLAN"})
    assert not any(relevant(c, queries_for_cases([claim])) for c in candidates)
    claim = Case(**{**synthetic_claims()[0], "policy_environment": "official"})
    assert not any(relevant(c, queries_for_cases([claim])) for c in candidates)


def test_document_budget_progresses_instead_of_repeating_first_documents(
    monkeypatch, services
):
    client.post("/api/demo/import-hospital")
    monkeypatch.setenv("COVERAGEGUARD_SYNC_DOCUMENT_LIMIT", "1")
    for _ in range(DEMO_POLICIES):
        sync_policies("demo-insurer-api")
    assert len(store.proposals) == DEMO_POLICIES and all(
        c.processed_hash for c in store.policy_catalog.values()
    )


def test_failed_download_records_backoff_and_retry(services):
    client.post("/api/demo/import-hospital")
    connector = SimulatedInsurerConnector()
    with patch.object(
        connector, "fetch", side_effect=Exception("controlled download failure")
    ):
        first = sync_policies(
            "demo-insurer-api", connectors={"demo-insurer-api": connector}
        )
    assert first["runs"][0].failed == DEMO_POLICIES
    s = store.sync_sources["demo-insurer-api"]
    assert s.consecutive_failures == 1
    assert timedelta(seconds=290) < s.next_sync_at - utc_now() < timedelta(seconds=310)
    second = sync_policies(
        "demo-insurer-api", connectors={"demo-insurer-api": connector}
    )
    assert second["runs"][0].changed == DEMO_POLICIES and not s.consecutive_failures


def test_structured_formatting_changes_do_not_duplicate_policy_proposals(services):
    client.post("/api/demo/import-hospital")
    sync_policies("demo-insurer-api")
    count = len(store.proposals)
    connector = SimulatedInsurerConnector()
    original = connector.fetch

    def changed_format(candidate):
        download = original(candidate)
        for row in download.structured_rules:
            row["supporting_quote"] = "FORMATTING ONLY " + row["supporting_quote"]
        return download

    with patch.object(connector, "fetch", side_effect=changed_format):
        result = sync_policies(
            "demo-insurer-api", connectors={"demo-insurer-api": connector}
        )
    assert result["runs"][0].unchanged == DEMO_POLICIES and len(store.proposals) == count


def test_lcd_related_metadata_pagination_preserves_opaque_token_as_documented_parameter():
    c = CMSCoverageConnector()
    with patch.object(
        c,
        "_json",
        side_effect=[
            {
                "data": [{"r_article_id": 1}],
                "meta": {"next_token": "token/with +chars"},
            },
            {"data": [{"r_article_id": 2}], "meta": {}},
        ],
    ) as fetch:
        rows = c._related("/v1/data/lcd/related-documents", "100", "2")
    assert (
        len(rows) == 2 and "next_token=token%2Fwith+%2Bchars" in fetch.call_args.args[0]
    )


def test_lcd_billing_articles_need_explicit_review_before_rule_activation():
    p = ProposedPolicyChange(
        proposal_id="LCD",
        document_id="D",
        document_name="LCD",
        insurer_id="cms",
        plan_ids=["ORIGINAL"],
        jurisdictions=["CA"],
        code_system="CPT",
        target_type="procedure",
        target_code="27447",
        proposed_effect="covered",
        effective_from=date(2026, 1, 1),
        supporting_quote="Controlled source evidence text.",
        requires_billing_articles=True,
    )
    store.save_proposal(p)
    with pytest.raises(ValueError, match="associated_billing_articles"):
        store.approve_proposal("LCD")


def test_unsupported_clinical_condition_never_silently_becomes_covered():
    r = make_rule(
        effect="covered", conditions={"requires_special_diagnosis": "not implemented"}
    )
    c = Case(
        case_id="CONDITION",
        member_ref="SYNTHETIC",
        insurer_id="bcbs-anthem-ca",
        plan_id="EXACT",
        jurisdiction="CA",
        service_date=date(2026, 11, 1),
        items=[CaseItem(type="procedure", code="27447", code_system="CPT")],
    )
    result = evaluate_case(c, [r])
    assert result.results[0].result == "Value wrong"


def test_missing_service_date_survives_cases_listing_without_runtime_error():
    c = Case(
        case_id="INCOMPLETE",
        insurer_id="uhc",
        plan_id="",
        member_ref="SYNTHETIC",
        service_date=None,
    )
    store.cases[c.case_id] = c
    assert client.get("/api/cases").status_code == 200
    assert (
        client.get("/api/claims/INCOMPLETE/findings")
        .json()["status"]
        .startswith("Unable")
    )


def test_claim_import_without_environment_defaults_to_official_not_legacy_demo():
    row = synthetic_claims()[0]
    row.pop("policy_environment")
    result = client.post("/api/claims/import", json={"claims": [row]})
    assert (
        result.status_code == 200
        and result.json()["findings"][0]["policy_environment"] == "official"
    )


def test_backend_scheduler_checks_only_due_sources(monkeypatch):
    from app.connectors import scheduler
    from app.connectors.registry import ensure_sources

    ensure_sources(store)
    for source in store.sync_sources.values():
        source.next_sync_at = utc_now() + timedelta(days=1)
    store.sync_sources["demo-insurer-api"].next_sync_at = utc_now() - timedelta(
        seconds=1
    )

    class StopAfterOneCycle:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, seconds):
            self.stopped = True

    monkeypatch.setattr(scheduler, "_stop_event", StopAfterOneCycle())
    with patch("app.connectors.sync_engine.sync_policies") as sync:
        scheduler._run_scheduler_loop(86400)
    sync.assert_called_once_with("demo-insurer-api")


def test_reset_during_download_does_not_resurrect_catalog_or_proposals(services):
    client.post("/api/demo/import-hospital")
    connector = SimulatedInsurerConnector()
    original = connector.fetch

    def resets(candidate):
        download = original(candidate)
        store.reset_state(False)
        return download

    with patch.object(connector, "fetch", side_effect=resets):
        result = sync_policies(
            "demo-insurer-api", connectors={"demo-insurer-api": connector}
        )
    assert (
        result["status"] == "interrupted"
        and not store.proposals
        and not store.policy_catalog
    )


def test_document_staging_storage_failure_rolls_back_processed_hash_and_proposals(
    services,
):
    from app.connectors.sync_engine import _stage
    from app.domain.sync_models import SyncRun

    connector = SimulatedInsurerConnector()
    candidate = connector.discover()[0]
    store.policy_catalog[candidate.catalog_id] = candidate
    run = SyncRun(run_id="TEST-RUN", source_id="demo-insurer-api")
    with patch.object(
        store, "save_checkpoint", side_effect=OSError("controlled disk failure")
    ):
        with pytest.raises(OSError):
            _stage(candidate, connector, run)
    assert candidate.processed_hash is None and candidate.metadata.get(
        "_retry_document"
    )
    assert not store.proposals and not store.policy_versions and run.changed == 0


def test_official_http_retries_temporary_failure_and_keeps_credentials_on_original_host(
    monkeypatch,
):
    from app.connectors import policy_http

    requests = []
    original = httpx.Client

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        if request.url.host == "api.coverage.cms.gov":
            return httpx.Response(
                302, headers={"location": "https://www.cms.gov/document"}
            )
        return httpx.Response(200, text="Official policy text")

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)
    monkeypatch.setattr(policy_http.time, "sleep", lambda _: None)
    client = PolicyHTTP(
        {"api.coverage.cms.gov", "www.cms.gov"},
        api_hosts={"api.coverage.cms.gov", "www.cms.gov"},
    )
    data, _, url = client.get(
        "https://api.coverage.cms.gov/v1/test",
        headers={"Authorization": "Bearer test-secret"},
        use_cache=False,
    )
    assert data == b"Official policy text" and len(requests) == 3
    assert requests[0].headers.get("authorization") == "Bearer test-secret"
    assert requests[-1].headers.get("authorization") is None


def test_official_http_blocks_private_redirect_and_oversize_download(monkeypatch):
    from app.connectors import policy_http

    original = httpx.Client
    response = httpx.Response(302, headers={"location": "https://127.0.0.1/private"})

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(lambda _: response)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)
    reader = PolicyHTTP({"api.coverage.cms.gov"}, api_hosts={"api.coverage.cms.gov"})
    with pytest.raises(Exception, match="approved HTTPS"):
        reader.get("https://api.coverage.cms.gov/v1/test", use_cache=False)
    response = httpx.Response(200, content=b"x" * 101)
    monkeypatch.setattr(policy_http, "MAX_BYTES", 100)
    with pytest.raises(Exception, match="10 MB"):
        reader.get("https://api.coverage.cms.gov/v1/test", use_cache=False)


@pytest.mark.parametrize("factory", [UHCConnector, AetnaConnector])
def test_commercial_automation_requires_publisher_authorization_before_any_fetch(
    factory, monkeypatch
):
    monkeypatch.delenv("COVERAGEGUARD_UHC_AUTHORIZATION_REFERENCE", raising=False)
    monkeypatch.delenv("COVERAGEGUARD_AETNA_AUTHORIZATION_REFERENCE", raising=False)
    connector = factory()
    assert connector.source.status == "authorization_required"
    with patch.object(
        connector.http,
        "get",
        side_effect=AssertionError("No automatic request without permission"),
    ):
        with pytest.raises(Exception, match="Publisher authorization"):
            connector.discover()


def test_catalog_search_queries_all_rows_and_exact_scope_fields():
    for index in range(510):
        candidate = PolicyCandidate(
            catalog_id=f"catalog-{index}",
            source_id="test",
            insurer_id="uhc",
            insurer_name="UnitedHealthcare",
            policy_id=str(index),
            title="Knee policy",
            source_url="https://www.uhcprovider.com/policy",
            jurisdictions=["CA"],
            plan_ids=[f"PLAN-{index}"],
        )
        store.policy_catalog[candidate.catalog_id] = candidate
    assert len(client.get("/api/policies/catalog").json()) == 500
    rows = client.get("/api/policies/catalog", params={"q": "PLAN-509"}).json()
    assert [row["catalog_id"] for row in rows] == ["catalog-509"]
    assert (
        len(
            client.get("/api/policies/catalog", params={"q": "UnitedHealthcare"}).json()
        )
        == 500
    )


def test_persisted_source_status_tracks_current_publisher_authorization(monkeypatch):
    from app.connectors.registry import ensure_sources

    monkeypatch.delenv("COVERAGEGUARD_UHC_AUTHORIZATION_REFERENCE", raising=False)
    ensure_sources(store)
    source = store.sync_sources["uhc-public"]
    source.status = "healthy"
    source.last_success_at = utc_now()
    ensure_sources(store)
    assert source.status == "authorization_required" and source.last_success_at
    monkeypatch.setenv(
        "COVERAGEGUARD_UHC_AUTHORIZATION_REFERENCE", "TEST-OPERATOR-ATTESTATION"
    )
    ensure_sources(store)
    assert source.status == "unchecked"  # permission does not prove connectivity


def test_missing_rule_alert_never_quotes_an_unrelated_pending_policy(services):
    from app.impact.analyzer import run_impact_analysis

    client.post("/api/demo/import-hospital")
    client.post("/api/policy-sync/run", json={"source_id": "demo-insurer-api"})
    assert store.proposals and all(
        p.resulting_rule_id is None for p in store.proposals.values()
    )
    alerts = run_impact_analysis(data_store=store)
    assert alerts and all(
        a.rule_id == "NO_RULE" and a.evidence_quote is None for a in alerts
    )


@pytest.mark.parametrize("claim_id,expected", [
    ("H-002", "Covered"),
    ("H-013", "Covered"),  # MRI with prior authorization reference
    ("H-014", "Prior approval needed"),
    ("H-015", "Covered"),  # physical therapy with referral attached
    ("H-016", "Document missing"),
    ("H-017", "Prior approval needed"),
    ("H-018", "Not covered"),
    ("H-019", "No rule found, verify with the insurer"),
    ("H-020", "Covered"),
    ("H-023", "Covered"),
    ("H-024", "Prior approval needed"),
    ("H-025", "Document missing"),  # only one of two required documents
    ("H-026", "Covered"),
    ("H-027", "Covered"),
    ("H-028", "Not covered"),
    ("H-033", "Document missing"),
    ("H-034", "Covered"),
    ("H-035", "Covered"),
    ("H-036", "Covered"),
    ("H-037", "Not covered"),  # knee osteoarthritis diagnosis
    ("H-038", "No rule found, verify with the insurer"),  # meniscus tear is outside the rule
])
def test_varied_demo_claims_show_each_kind_of_result(services, claim_id, expected):
    client.post("/api/demo/import-hospital")
    sync_policies("demo-insurer-api")
    activate_pending()
    findings = client.get(f"/api/claims/{claim_id}/findings").json()["findings"]
    assert findings[0]["result"] == expected
