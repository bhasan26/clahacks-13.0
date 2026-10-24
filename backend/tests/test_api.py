"""
API endpoint tests for CoverageGuard.
Tests:
1. Health and connection endpoints.
2. Dashboard summary (counts, clean claims, specialties, latest updates).
3. Cases listing and filters.
4. Case detail with itemized issue sentences.
5. "Run check now" daily check trigger (moving 3 cases from Approved to Needs attention).
6. Target editing.
7. Simulated check failure toggle.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health_and_connection():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["total_cases"] == 40

    conn = client.get("/api/connection").json()
    assert conn["insurer_name"] == "Demo Insurance Co."
    assert conn["access_status"] == "Access active"
    assert conn["read_only"] is True


def test_api_dashboard_metrics():
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.json()

    # Row 1 counts
    counts = data["counts"]
    assert counts["approved"] == 30
    assert counts["needs_attention"] == 5
    assert counts["missing_or_wrong_info"] == 5
    assert counts["total_checked"] == 40

    # Row 2 left: Clean claims % and target
    clean_claims = data["clean_claims"]
    assert clean_claims["percentage"] == 75.0
    assert clean_claims["target"] == 85.0
    assert clean_claims["percentage"] < clean_claims["target"]

    # Row 2 right: 5 specialties
    specs = data["specialties"]
    assert len(specs) == 5
    spec_names = [s["specialty"] for s in specs]
    assert "Cardiology" in spec_names
    assert "Oncology" in spec_names
    assert "Orthopedics" in spec_names
    assert "Neurology" in spec_names
    assert "Gastroenterology" in spec_names

    # Row 3: 3 latest updates
    updates = data["latest_updates"]
    assert len(updates) == 3


def test_api_cases_and_filters():
    # All cases
    res = client.get("/api/cases")
    assert res.status_code == 200
    all_cases = res.json()
    assert len(all_cases) == 40

    # Filter by status: Approved
    res = client.get("/api/cases?status=Approved")
    assert res.status_code == 200
    approved = res.json()
    assert all(c["status"] == "Approved" for c in approved)

    # Filter by specialty: Cardiology
    res = client.get("/api/cases?specialty=Cardiology")
    assert res.status_code == 200
    cardio = res.json()
    assert len(cardio) == 10
    assert all(c["specialty"] == "Cardiology" for c in cardio)


def test_api_case_detail_item_sentences():
    res = client.get("/api/cases/C-003")
    assert res.status_code == 200
    data = res.json()
    assert data["case"]["case_id"] == "C-003"
    assert data["check_result"]["status"] == "Needs attention"

    results = data["check_result"]["results"]
    assert len(results) >= 1
    verdict = results[0]
    assert verdict["result"] == "Prior approval needed"
    assert "Rule" in verdict["rule_reference"]
    assert len(verdict["plain_sentence"]) > 0
    assert len(verdict["what_to_do"]) > 0


def test_api_run_check_now_flow():
    # 1. Reset
    client.post("/api/simulator/reset")

    # Initial counts: Approved=30, Needs attention=5
    dash_before = client.get("/api/dashboard").json()
    assert dash_before["counts"]["approved"] == 30
    assert dash_before["counts"]["needs_attention"] == 5

    # 2. Run check now
    res = client.post("/api/check/run-now")
    assert res.status_code == 200
    result = res.json()
    assert result["success"] is True
    assert set(result["affected_case_ids"]) == {"C-001", "C-005", "C-008"}

    # Post-check counts: 3 open cases moved from Approved to Needs attention
    dash_after = client.get("/api/dashboard").json()
    assert dash_after["counts"]["approved"] == 27
    assert dash_after["counts"]["needs_attention"] == 8

    # Reset back to pristine
    client.post("/api/simulator/reset")


def test_api_target_editing_and_failure_toggle():
    # Target editing
    res = client.post("/api/settings/target", json={"target": 90.0})
    assert res.status_code == 200
    dash = client.get("/api/dashboard").json()
    assert dash["clean_claims"]["target"] == 90.0

    # Toggle failure
    res = client.post("/api/connection/toggle-fail")
    assert res.status_code == 200
    conn = client.get("/api/connection").json()
    assert conn["access_status"] == "Check pending"
    assert conn["is_check_failed"] is True
    assert conn["warning_banner"] is not None

    # Toggle back
    client.post("/api/connection/toggle-fail")
    conn = client.get("/api/connection").json()
    assert conn["access_status"] == "Access active"
    assert conn["is_check_failed"] is False

    # Reset
    client.post("/api/simulator/reset")
