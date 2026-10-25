"""
Unit tests for Explainable Action Center, Alerts, and Clinical Intake enhancements.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.db.store import store
from app.domain.models import Alert, AlertChange, AlertStatus, AlertTask, utc_now
from app.intake.analyzer import redact_sensitive_identifiers, analyze_clinical_document

client = TestClient(app)


def test_redact_sensitive_identifiers():
    """Verify SSNs, phone numbers, and emails are properly masked before model calls."""
    raw_text = (
        "Patient John Doe, SSN: 123-45-6789, Phone: (555) 234-5678, "
        "Email: patient.john@example.com is prescribed Keytruda for Stage IV NSCLC."
    )
    redacted, was_masked = redact_sensitive_identifiers(raw_text)
    assert was_masked is True
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "(555) 234-5678" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "patient.john@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_clinical_document_intake_no_fake_drug_when_empty():
    """Ensure clinical intake does not fabricate drugs when input is ambiguous or empty."""
    res = analyze_clinical_document(text_content="Routine wellness checkup with no prescribed therapy.")
    # Should not fabricate Humira or Keytruda
    assert res["items"] == []
    assert len(res["validation_warnings"]) > 0
    assert res["confidence"] is None


def test_alert_lifecycle_and_task_queue():
    """Verify Explainable Action Center alerts, interactive tasks, and AI draft generation."""
    # Seed an alert into store
    alert_id = "A-TEST01"
    store.alerts[alert_id] = Alert(
        alert_id=alert_id,
        case_id="C-001",
        item_code="DRUG-A",
        rule_id="R-1042",
        change=AlertChange(from_version=1, to_version=2, change_type="excluded"),
        status=AlertStatus.OPEN,
        headline="Demo Insurer excludes DRUG-A effective 1 Nov 2026",
        explanation="Case C-001 has DRUG-A scheduled for 2026-11-05.",
        suggested_action="Obtain prior authorization or switch to covered formulary alternative.",
        evidence_quote="Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A.",
        effective_date="1 Nov 2026",
        source_document="Uploaded Insurance Notice",
        tasks=[
            AlertTask(task_id="t1", title="Review policy mandate and governing date criteria", status="open"),
            AlertTask(task_id="t2", title="Verify member eligibility and plan formulary tier", status="open"),
        ],
        draft_message="Notice regarding Claim C-001: Payer policy update for DRUG-A effective 1 Nov 2026.",
    )

    # 1. Fetch alerts
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    assert any(a["alert_id"] == alert_id for a in alerts)

    # 2. Fetch case-specific alerts
    resp_case = client.get("/api/alerts/case/C-001")
    assert resp_case.status_code == 200
    case_alerts = resp_case.json()
    assert len(case_alerts) >= 1
    assert case_alerts[0]["item_code"] == "DRUG-A"

    # 3. Update task status (open -> completed)
    resp_task = client.post(
        f"/api/alerts/{alert_id}/tasks/t1",
        json={"status": "completed", "completed_by": "Dr. Sarah Connor"},
    )
    assert resp_task.status_code == 200
    updated_alert = resp_task.json()["alert"]
    task1 = next(t for t in updated_alert["tasks"] if t["task_id"] == "t1")
    assert task1["status"] == "completed"
    assert task1["completed_by"] == "Dr. Sarah Connor"
    assert task1["completed_at"] is not None

    # 4. Generate/Retrieve administrative draft message
    resp_draft = client.post(f"/api/alerts/{alert_id}/draft")
    assert resp_draft.status_code == 200
    draft_data = resp_draft.json()
    assert "Notice regarding Claim C-001" in draft_data["draft_message"]
    assert "disclaimer" in draft_data
    assert "human review" in draft_data["disclaimer"].lower()

    # 5. Acknowledge alert
    resp_ack = client.post(
        f"/api/alerts/{alert_id}/acknowledge",
        json={"officer_note": "Verified with pharmacy team; submitting PA request."},
    )
    assert resp_ack.status_code == 200
    assert resp_ack.json()["alert"]["acknowledged"] is True
