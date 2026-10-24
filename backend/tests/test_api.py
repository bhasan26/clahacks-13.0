"""
API endpoint tests for CoverageGuard.
Verifies all core routes: health, cases, alerts, sync, and simulator.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["feed_connected"] is True


def test_api_cases_list():
    res = client.get("/api/cases")
    assert res.status_code == 200
    cases = res.json()
    assert len(cases) >= 4
    case_ids = [c["case"]["case_id"] for c in cases]
    assert "C-001" in case_ids
    assert "C-003" in case_ids


def test_api_simulator_flow():
    # 1. Reset
    res = client.post("/api/simulator/reset")
    assert res.status_code == 200

    # 2. Exclude DRUG-A
    res = client.post("/api/simulator/exclude-drug-a")
    assert res.status_code == 200

    # Verify alert created for C-001
    res = client.get("/api/alerts?status=open")
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) >= 1
    assert any(a["case_id"] == "C-001" for a in alerts)

    # 3. Delay DRUG-A to Dec 1
    res = client.post("/api/simulator/delay-drug-a")
    assert res.status_code == 200

    # Verify alert is closed
    res = client.get("/api/alerts")
    assert res.status_code == 200
    c1_alerts = [a for a in res.json() if a["case_id"] == "C-001"]
    assert c1_alerts[0]["status"] == "closed"


def test_api_feed_outage_stale_banner():
    # Toggle outage on
    res = client.post("/api/simulator/toggle-outage")
    assert res.status_code == 200
    assert res.json()["is_feed_outage_simulated"] is True

    # Health check should now report warning / stale
    health = client.get("/api/health").json()
    assert health["is_stale"] is True
    assert health["status"] == "warning"

    # Reset
    client.post("/api/simulator/reset")
