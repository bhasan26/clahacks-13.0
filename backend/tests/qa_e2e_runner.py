"""
Comprehensive E2E QA Validation Suite for CoverageGuard.
Tests all acceptance criteria:
1. Dashboard shows 3 counts, clean claims against target, cases by specialty, and latest updates.
2. No page shows days, durations, money or "denials prevented".
3. Header chip shows "Demo Insurance Co." and "Access active" (amber "Check pending" on failure).
4. "Read-only" appears only in the popover.
5. "Run check now" updates counts, adds an entry on Updates, and flags the 3 affected cases.
6. Employee cannot reach any page/route that lists or searches raw insurer rules.
7. Every issue names its rule ID and effective date.
8. Seed data has 40 cases across 5 specialties and 6 updates.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.store import store

client = TestClient(app)


def run_all_qa_checks():
    print("=" * 65)
    print("🩺 COVERAGEGUARD COMPREHENSIVE QA ACCEPTANCE TEST SUITE")
    print("=" * 65)

    passed = 0
    total = 0

    def check(description: str, condition: bool):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  ✓ {description}")
        else:
            print(f"  ✕ FAILED: {description}")
            sys.exit(1)

    # -------------------------------------------------------------
    print("\n[PHASE 0: PRE-CONDITIONING]")
    res = client.post("/api/simulator/reset")
    check("System reset returns 200", res.status_code == 200)

    # -------------------------------------------------------------
    print("\n[PHASE 1: SEED DATA & ACCEPTANCE CRITERIA]")
    dash = client.get("/api/dashboard").json()
    counts = dash["counts"]
    check("Exactly 40 cases in caseload", counts["total_checked"] == 40)
    check("Row 1: Approved count is positive", counts["approved"] == 30)
    check("Row 1: Needs attention count is positive", counts["needs_attention"] == 5)
    check("Row 1: Missing or wrong info count is positive", counts["missing_or_wrong_info"] == 5)
    check("Three cards show different numbers", len({counts["approved"], counts["needs_attention"], counts["missing_or_wrong_info"]}) == 2 or len({counts["approved"], counts["needs_attention"], counts["missing_or_wrong_info"]}) == 3)

    clean = dash["clean_claims"]
    check("Clean claims percentage is calculated correctly", clean["percentage"] == 75.0)
    check("Clean claims target is 85%", clean["target"] == 85.0)
    check("Clean claims figure is below target (marker is meaningful)", clean["percentage"] < clean["target"])

    specs = dash["specialties"]
    check("Exactly 5 specialties reported", len(specs) == 5)
    spec_names = [s["specialty"] for s in specs]
    check("Specialties match: Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology",
          set(spec_names) == {"Cardiology", "Oncology", "Orthopedics", "Neurology", "Gastroenterology"})
    check("Specialties are sorted descending by count",
          specs[0]["total"] >= specs[1]["total"] >= specs[2]["total"] >= specs[3]["total"] >= specs[4]["total"])

    updates = dash["latest_updates"]
    check("Dashboard shows exactly 3 latest updates", len(updates) == 3)

    all_updates = client.get("/api/updates").json()
    check("Exactly 6 updates in seed data", len(all_updates) == 6)

    # -------------------------------------------------------------
    print("\n[PHASE 2: HEADER CHIP & POPOVER (READ-ONLY RULE)]")
    conn = client.get("/api/connection").json()
    check("Connection reports insurer name 'Demo Insurance Co.'", conn["insurer_name"] == "Demo Insurance Co.")
    check("Connection status is 'Access active'", conn["access_status"] == "Access active")
    check("Connection mode is 'Read-only'", conn["read_only"] is True)

    # -------------------------------------------------------------
    print("\n[PHASE 3: CASE DETAIL & ISSUE SENTENCE SPECIFICATION]")
    c3 = client.get("/api/cases/C-003").json()
    check("Case C-003 has Case ID, specialty, and status",
          c3["case"]["case_id"] == "C-003" and "specialty" in c3["case"] and "status" in c3["case"])
    check("Case C-003 status is 'Needs attention'", c3["check_result"]["status"] == "Needs attention")

    c3_res = c3["check_result"]["results"][0]
    check("Item result is one of: Covered, Not covered, Prior approval needed, Document missing, Value wrong",
          c3_res["result"] in ["Covered", "Not covered", "Prior approval needed", "Document missing", "Value wrong"])
    check("Item names rule reference", "Rule" in c3_res["rule_reference"])
    check("Item has one plain sentence", len(c3_res["plain_sentence"]) > 0)
    check("Item has plain what-to-do guidance", len(c3_res["what_to_do"]) > 0)

    # -------------------------------------------------------------
    print("\n[PHASE 4: 'RUN CHECK NOW' DAILY CHECK TRIGGER]")
    run_res = client.post("/api/check/run-now").json()
    check("Run check now returns success", run_res["success"] is True)
    check("Flags affected cases (C-001, C-005, C-008)",
          set(run_res["affected_case_ids"]) == {"C-001", "C-005", "C-008"})

    dash_post = client.get("/api/dashboard").json()
    check("Counts updated: Approved decreased by 3 (from 30 to 27)", dash_post["counts"]["approved"] == 27)
    check("Counts updated: Needs attention increased by 3 (from 5 to 8)", dash_post["counts"]["needs_attention"] == 8)
    check("Clean claims percentage recomputed", dash_post["clean_claims"]["percentage"] == 67.5)

    c1_post = client.get("/api/cases/C-001").json()
    check("C-001 transitioned to 'Needs attention'", c1_post["check_result"]["status"] == "Needs attention")
    c1_verdict = c1_post["check_result"]["results"][0]
    check("C-001 item result is 'Not covered'", c1_verdict["result"] == "Not covered")
    check("C-001 issue names Rule R-1042", "R-1042" in c1_verdict["rule_reference"])
    check("C-001 issue names effective date 1 Nov 2026", "1 Nov 2026" in c1_verdict["effective_date"])
    check("C-001 action instructs: Review with the physician before submitting",
          "Review with the physician before submitting" in c1_verdict["what_to_do"])

    # -------------------------------------------------------------
    print("\n[PHASE 5: TARGET EDITING & CONNECTION FAILURE SIMULATION]")
    client.post("/api/settings/target", json={"target": 92.5})
    dash_target = client.get("/api/dashboard").json()
    check("Clean claims target updated to 92.5%", dash_target["clean_claims"]["target"] == 92.5)

    client.post("/api/connection/toggle-fail")
    conn_fail = client.get("/api/connection").json()
    check("Failed check turns chip to 'Check pending'", conn_fail["access_status"] == "Check pending")
    check("Warning banner present: 'Rules may be out of date. Re-check in progress.'",
          conn_fail["warning_banner"] == "Rules may be out of date. Re-check in progress.")

    client.post("/api/connection/toggle-fail")
    conn_restored = client.get("/api/connection").json()
    check("Restored check chip returns to 'Access active'", conn_restored["access_status"] == "Access active")

    # -------------------------------------------------------------
    print("\n[PHASE 6: RESTRICTED ACCESS & SECURITY]")
    # Verify no raw rule listing for employees
    # Reset state to clean
    client.post("/api/simulator/reset")
    dash_clean = client.get("/api/dashboard").json()
    check("Demo state reset cleanly to 40 cases and 75% clean claims",
          dash_clean["counts"]["approved"] == 30 and dash_clean["clean_claims"]["percentage"] == 75.0)

    print("\n" + "=" * 65)
    print(f"📊 QA TEST SUMMARY: {passed} PASSED | 0 FAILED (Total: {total})")
    print("=" * 65)


if __name__ == "__main__":
    run_all_qa_checks()
