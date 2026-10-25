"""Real HTTP verification against three separate local services (no mocked responses)."""

import json, os
from pathlib import Path
import httpx

BASE = os.environ.get("COVERAGEGUARD_E2E_URL", "http://127.0.0.1:8011")


def run():
    log = []
    with httpx.Client(
        base_url=BASE, timeout=60, headers={"X-Synthetic-Data": "true"}, trust_env=False
    ) as client:

        def get(path):
            r = client.get(path)
            r.raise_for_status()
            return r.json()

        def post(path, data=None):
            r = client.post(path, json={} if data is None else data)
            r.raise_for_status()
            return r.json()

        def activate():
            ids = []
            for p in get("/api/policies/proposals"):
                if (
                    p.get("extraction_method") == "structured_simulator"
                    and p["review_state"] == "pending_review"
                ):
                    ids.append(
                        post(
                            "/api/policies/proposals/" + p["proposal_id"] + "/approve",
                            {
                                "reviewer_notes": "Real-HTTP synthetic integration audit: verified exact plan, CA scope, standardized code, effective date and source quotation."
                            },
                        )
                    )
            return ids

        post("/api/simulator/reset?seed_demo=false")
        post("/api/demo/publish-insurer", {"scenario": "reset"})
        data = post("/api/demo/import-hospital")
        assert data["imported"] == 40
        assert all(f["status"].startswith("Unable") for f in data["findings"])
        log.append(
            {
                "step": "import_independent_hospital",
                "claims": 40,
                "before_policies": "unable_to_verify",
            }
        )
        result = post("/api/policy-sync/run", {"source_id": "demo-insurer-api"})
        assert result["runs"][0]["changed"] == 5
        assert len(activate()) == 5
        log.append(
            {
                "step": "sync_and_review_baseline",
                "policies": 5,
                "H-003": get("/api/claims/H-003/findings")["status"],
            }
        )
        uploaded = post(
            "/api/cases/upload",
            {
                "insurer_id": "uhc",
                "insurer_name": "UnitedHealthcare (SIMULATED)",
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
        cid = uploaded["case"]["case_id"]
        assert get("/api/claims/" + cid + "/findings")["status"].startswith("No issue")
        log.append(
            {
                "step": "upload_additional_synthetic_claim",
                "claim_id": cid,
                "finding": "No issue detected under SIMULATED checked rules",
            }
        )
        post("/api/demo/publish-insurer", {"scenario": "restriction"})
        result = post("/api/policy-sync/run", {"source_id": "demo-insurer-api"})
        assert result["runs"][0]["changed"] == 1
        approvals = activate()
        assert len(approvals) == 1 and len(approvals[0]["affected_case_ids"]) == 9
        assert get("/api/claims/H-001/findings")["findings"][0]["result"] == "Covered"
        assert get("/api/claims/H-011/findings")["findings"][0]["result"] == "Covered"
        log.append(
            {
                "step": "restriction_detected_reviewed",
                "version": approvals[0]["rule"]["version"],
                "affected_claims": len(approvals[0]["affected_case_ids"]),
                "other_insurer_unchanged": True,
            }
        )
        post("/api/demo/publish-insurer", {"scenario": "delay"})
        post("/api/policy-sync/run", {"source_id": "demo-insurer-api"})
        approvals = activate()
        assert approvals[0]["rule"]["version"] == 3
        findings = get("/api/claims/H-003/findings")
        assert (
            findings["findings"][0]["result"] == "Covered"
            and findings["findings"][1]["result"] == "Prior approval needed"
        )
        alerts = get("/api/alerts")
        assert any(
            a["case_id"] == "H-003"
            and a["item_code"] == "27447"
            and a["status"] == "closed"
            for a in alerts
        )
        assert any(
            a["case_id"] == "H-003"
            and a["item_code"] == "J1234"
            and a["status"] == "open"
            for a in alerts
        )
        result = post("/api/policy-sync/run", {"source_id": "demo-insurer-api"})
        assert result["runs"][0]["unchanged"] == 5 and not result["runs"][0]["changed"]
        log.append(
            {
                "step": "delay_reviewed",
                "version": 3,
                "unrelated_authorization_retained": True,
                "resolved_alerts_closed": True,
                "repeat_sync_unchanged": 5,
            }
        )
        report = {
            "transport": "real HTTP",
            "simulation": True,
            "external_ai_used": False,
            "steps": log,
            "audit_events": len(get("/api/audit")),
        }
        print(json.dumps(report, indent=2))
        Path("verification/sync/demo-http-e2e.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        return report


if __name__ == "__main__":
    run()
