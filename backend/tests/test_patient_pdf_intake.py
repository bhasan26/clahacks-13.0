"""Actual PDF/base64 modal contract → editable details → saved claim → approved policy lifecycle."""

import base64
from pathlib import Path
from unittest.mock import patch

import fitz
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.store import store
from app.intake.analyzer import analyze_clinical_document
from simulators.insurer import app as insurer_app, SimulatorState, baseline

client = TestClient(app, headers={"X-Synthetic-Data": "true"})
FIXTURES = Path(__file__).parent / "fixtures"
TEXT = (FIXTURES / "synthetic_uhc_knee_claim.txt").read_text()


def encoded_pdf(text=TEXT):
    with fitz.open() as document:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(40, 40, 560, 780), text, fontsize=11)
        return (
            "data:application/pdf;base64,"
            + base64.b64encode(document.tobytes()).decode()
        )


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    store.reset_state(False)
    store.demo_mode = False
    state = SimulatorState("test_intake_insurer", baseline)
    state.path = tmp_path / "insurer.sqlite3"
    monkeypatch.setattr("simulators.insurer.state", state)
    monkeypatch.delenv("COVERAGEGUARD_INSURER_SIMULATOR_URL", raising=False)
    monkeypatch.delenv("SIMULATOR_ADMIN_TOKEN", raising=False)
    yield
    store.reset_state(False)


@pytest.fixture
def insurer_transport(monkeypatch):
    insurer = TestClient(insurer_app)
    original = httpx.Client

    def transport(request):
        assert request.url.host == "127.0.0.1" and request.url.port == 8102, (
            "Clinical intake must not call external services"
        )
        response = insurer.request(
            request.method,
            request.url.raw_path.decode(),
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx.Response(
            response.status_code, content=response.content, headers=response.headers
        )

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(transport)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)


def analyze(**extra):
    response = client.post(
        "/api/intake/analyze",
        json={"clinical_doc_b64": encoded_pdf(), "policy_environment": "demo", **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


def sync_and_review():
    response = client.post(
        "/api/policy-sync/run", json={"source_id": "demo-insurer-api"}
    )
    assert response.status_code == 200, response.text
    for proposal in list(store.proposals.values()):
        if proposal.review_state == "pending_review":
            response = client.post(
                f"/api/policies/proposals/{proposal.proposal_id}/approve",
                json={
                    "reviewer_notes": "Verified exact synthetic insurer, plan, state, CPT/HCPCS, date and evidence."
                },
            )
            assert response.status_code == 200, response.text


def test_actual_pdf_intake_filing_restriction_delay_and_official_isolation(
    insurer_transport,
):
    # Import establishes relevant caseload for the same connector path as the UI.
    initial = analyze()
    assert initial["claim"]["insurer_id"] == "uhc"
    assert initial["claim"]["plan_id"] == "DEMO-UHC-PPO"
    assert initial["claim"]["member_ref"] == "SYNTHETIC-001"
    assert initial["claim"]["jurisdiction"] == "CA"
    assert initial["claim"]["service_date"] == "2026-11-12"
    assert initial["claim"]["prior_approval_ref"] == "PA-DEMO-001"
    assert initial["claim"]["items"][0] == {
        "type": "procedure",
        "code": "27447",
        "code_system": "CPT",
        "name": "Total Knee Replacement",
        "quantity": 1,
    }
    assert not initial["missing_fields"]
    assert initial["findings"]["status"].startswith("Unable")
    saved = client.post("/api/cases/upload", json=initial["claim"])
    assert saved.status_code == 200, saved.text
    claim_id = saved.json()["case"]["case_id"]
    detail = client.get(f"/api/cases/{claim_id}").json()
    assert detail["case"]["member_ref"] == "SYNTHETIC-001"
    assert detail["case"]["policy_environment"] == "demo"
    assert detail["findings"]["status"].startswith("Unable")
    sync_and_review()
    baseline_result = analyze()
    assert (
        baseline_result["findings"]["status"]
        == "No issue detected under SIMULATED checked rules"
    )
    finding = baseline_result["findings"]["findings"][0]
    assert (
        finding["policy_reference"] == "DEMO-UHC-KNEE"
        and finding["policy_version"] == 1
    )
    assert finding["source_evidence"] and finding["prior_authorization_present"]
    assert finding["prior_authorization_reference"] == "PA-DEMO-001"
    assert (
        client.post(
            "/api/demo/publish-insurer", json={"scenario": "restriction"}
        ).status_code
        == 200
    )
    sync_and_review()
    excluded = analyze()["findings"]
    assert excluded["findings"][0]["result"] == "Not covered"
    assert excluded["findings"][0]["policy_version"] == 2
    assert (
        client.get(f"/api/claims/{claim_id}/findings").json()["findings"][0]["result"]
        == "Not covered"
    )
    assert (
        client.post("/api/demo/publish-insurer", json={"scenario": "delay"}).status_code
        == 200
    )
    sync_and_review()
    delayed = analyze()["findings"]
    assert delayed["status"] == "No issue detected under SIMULATED checked rules"
    assert delayed["findings"][0]["result"] == "Covered"
    assert (
        client.get(f"/api/claims/{claim_id}/findings").json()["findings"][0]["result"]
        == "Covered"
    )
    official = analyze(policy_environment="official")
    assert official["findings"]["status"].startswith("Unable")
    assert (
        "No approved official policy"
        in official["findings"]["findings"][0]["policy_missing_reason"]
    )
    assert official["check_result"]["status"] != "Approved"


@pytest.mark.parametrize(
    "text",
    [
        TEXT,
        TEXT.replace(": ", "= ").replace("\n", " | "),
        TEXT.replace(": ", "\n"),
        TEXT.replace(
            "Service Date: 2026-11-12", "Date of Service: November 12, 2026"
        ).replace("Member ID:", "Subscriber Number:"),
    ],
)
def test_pdf_and_typed_text_allow_multiple_label_layouts_without_network(text):
    with patch(
        "httpx.HTTPTransport.handle_request",
        side_effect=AssertionError("No clinical AI requests"),
    ):
        for payload in (
            {"clinical_doc_b64": encoded_pdf(text)},
            {"clinical_text": text, "clinical_doc_b64": None},
        ):
            data = analyze(**payload)
            assert data["claim"]["insurer_id"] == "uhc"
            assert data["claim"]["member_ref"] == "SYNTHETIC-001"
            assert data["claim"]["plan_id"] == "DEMO-UHC-PPO"
            assert data["claim"]["items"][0]["code"] == "27447"
            assert data["claim"]["items"][0]["code_system"] == "CPT"
            assert data["claim"]["service_date"] == "2026-11-12"


@pytest.mark.parametrize(
    "label,field",
    [
        ("Insurance Company", "insurer_id"),
        ("Plan ID", "plan_id"),
        ("Procedure", "items"),
    ],
)
def test_missing_pdf_fields_are_specific_and_never_fabricated(label, field):
    lines = TEXT.splitlines()
    removed = (
        {"Insurance Company", "Insurer ID"}
        if label == "Insurance Company"
        else {"Procedure", "CPT Code"}
        if label == "Procedure"
        else {label}
    )
    text = "\n".join(
        line
        for line in lines
        if not any(line.startswith(prefix + ":") for prefix in removed)
    )
    data = analyze(clinical_doc_b64=encoded_pdf(text))
    assert field in {row["field"] for row in data["missing_fields"]}
    assert not data["claim"][field]
    assert data["findings"]["status"].startswith("Unable")
    assert data["card"]["insurer_name"] != "Demo Insurance Co."
    assert not any(
        v["item"]["name"] == "Patient Record" for v in data["check_result"]["results"]
    )


def test_card_pdf_fields_merge_and_reviewed_corrections_control_saved_claim():
    data = analyze(
        clinical_doc_b64=encoded_pdf(
            "Procedure: Total Knee Replacement\nCPT Code: 27447\nService Date: 2026-11-12"
        ),
        card_image_b64=encoded_pdf(
            "Insurance Company: UnitedHealthcare\nPlan ID: DEMO-UHC-PPO\nMember ID: SYNTHETIC-001\nState: CA"
        ),
    )
    assert not data["missing_fields"] and data["card"]["member_ref"] == "SYNTHETIC-001"
    corrected = {
        **data["claim"],
        "plan_id": "REVIEWED-PLAN",
        "jurisdiction": "NY",
        "service_date": "2026-11-13",
    }
    response = client.post(
        "/api/intake/analyze",
        json={"policy_environment": "official", "reviewed_claim": corrected},
    )
    assert response.status_code == 200
    assert response.json()["claim"]["plan_id"] == "REVIEWED-PLAN"
    saved = client.post("/api/cases/upload", json=response.json()["claim"])
    assert saved.status_code == 200
    assert saved.json()["case"]["jurisdiction"] == "NY"
    assert saved.json()["case"]["items"][0]["code_system"] == "CPT"
    assert saved.json()["findings"]["status"].startswith("Unable")


def test_local_image_and_scanned_pdf_require_manual_entry_without_fake_ocr():
    with fitz.open() as image_doc:
        image_doc.new_page()
        image = image_doc[0].get_pixmap().tobytes("png")
    with patch(
        "httpx.HTTPTransport.handle_request",
        side_effect=AssertionError("No clinical AI requests"),
    ):
        for data_uri in (
            "data:image/png;base64," + base64.b64encode(image).decode(),
            encoded_pdf(""),
        ):
            result = analyze(clinical_doc_b64=data_uri)
            assert not result["claim"]["items"] and not result["claim"]["member_ref"]
            assert any(
                "OCR is unavailable" in message
                for message in result["validation_warnings"]
            )
            assert {"insurer_id", "plan_id", "service_date", "items"} <= {
                row["field"] for row in result["missing_fields"]
            }


def test_numeric_identifiers_are_not_treated_as_billing_codes_and_pending_is_not_authorization():
    result = analyze_clinical_document(
        text_content="Insurer ID: uhc\nMember ID: 12345\nProvider NPI: 1234567890\nPrior Authorization: PENDING / NOT ATTACHED"
    )
    assert result["items"] == [] and result["prior_approval_ref"] is None


def test_multiple_items_survive_intake_and_filing_and_missing_code_stays_editable():
    data = analyze(
        clinical_text=TEXT + "\nProcedure: Other service\nCPT Code: 12345",
        clinical_doc_b64=None,
    )
    assert len(data["claim"]["items"]) == 2
    result = client.post("/api/cases/upload", json=data["claim"])
    assert result.status_code == 200 and len(result.json()["case"]["items"]) == 2
    missing = analyze(clinical_doc_b64=encoded_pdf(TEXT.replace("CPT Code: 27447", "")))
    assert missing["claim"]["items"][0]["name"] == "Total Knee Replacement"
    assert missing["claim"]["items"][0]["code"] == ""
    assert "items.0.code" in {row["field"] for row in missing["missing_fields"]}


def test_findings_explain_required_documents_and_authorization_presence():
    from datetime import date
    from app.domain.models import Rule, Target

    rule = Rule(
        rule_id="DEMO-INTAKE-REQUIREMENTS",
        version=1,
        insurer_id="uhc",
        plan_ids=["DEMO-UHC-PPO"],
        jurisdictions=["CA"],
        target=Target(type="procedure", code="27447", code_system="CPT"),
        category="procedure",
        effect="covered",
        status="effective",
        effective_from=date(2026, 1, 1),
        conditions={
            "requires_prior_approval": True,
            "required_documents": ["Operative Note"],
        },
        source_ref="SIMULATED",
        bulletin_summary="SIMULATED knee rule requires prior authorization and Operative Note.",
        is_synthetic=True,
    )
    store.rules["DEMO-INTAKE-REQUIREMENTS_v1"] = rule
    finding = analyze()["findings"]["findings"][0]
    assert (
        finding["requires_prior_authorization"]
        and finding["prior_authorization_present"]
    )
    assert (
        finding["missing_documents"] == ["Operative Note"]
        and finding["result"] == "Document missing"
    )
    no_auth = analyze(
        clinical_doc_b64=encoded_pdf(
            TEXT.replace("Prior Authorization: PA-DEMO-001", "")
        )
    )["findings"]["findings"][0]
    assert (
        no_auth["requires_prior_authorization"]
        and not no_auth["prior_authorization_present"]
    )
    assert no_auth["result"] == "Prior approval needed"


def test_invalid_service_date_and_missing_member_are_not_generated():
    text = TEXT.replace("Service Date: 2026-11-12", "Service Date: 2026-02-31").replace(
        "Member ID: SYNTHETIC-001", ""
    )
    data = analyze(clinical_doc_b64=encoded_pdf(text))
    assert data["claim"]["service_date"] is None and data["claim"]["member_ref"] == ""
    assert {"service_date", "member_ref"} <= {
        row["field"] for row in data["missing_fields"]
    }
    assert any("Invalid" in message for message in data["validation_warnings"])
    assert client.post("/api/cases/upload", json=data["claim"]).status_code == 422


def test_review_only_recheck_does_not_report_resolved_extraction_gaps():
    data = analyze()
    reviewed = client.post(
        "/api/intake/analyze",
        json={"policy_environment": "demo", "reviewed_claim": data["claim"]},
    ).json()
    assert not reviewed["missing_fields"] and not reviewed["validation_warnings"]
    assert reviewed["claim"]["items"][0]["code"] == "27447"
    pending = {**data["claim"], "prior_approval_ref": "PENDING"}
    response = client.post(
        "/api/intake/analyze",
        json={"policy_environment": "demo", "reviewed_claim": pending},
    ).json()
    assert response["claim"]["prior_approval_ref"] is None


@pytest.mark.parametrize(
    "replacement",
    [
        ("State: CA", "State: NY"),
        ("Plan ID: DEMO-UHC-PPO", "Plan ID: DIFFERENT-PLAN"),
        ("CPT Code: 27447", "HCPCS Code: 27447"),
        ("CPT Code: 27447", "CPT Code: 274470"),
    ],
)
def test_pdf_matching_rejects_wrong_plan_region_system_or_similar_code(
    insurer_transport, replacement
):
    initial = analyze()
    assert client.post("/api/cases/upload", json=initial["claim"]).status_code == 200
    sync_and_review()
    wrong = analyze(clinical_doc_b64=encoded_pdf(TEXT.replace(*replacement)))
    assert wrong["findings"]["status"].startswith("Unable")
    assert not wrong["findings"]["findings"][0]["policy_reference"]
    assert wrong["findings"]["findings"][0]["policy_missing_reason"]
