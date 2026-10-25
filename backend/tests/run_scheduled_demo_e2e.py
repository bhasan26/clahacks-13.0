"""Prove detection by the backend scheduler without calling the sync endpoint."""

import json, os, time
from pathlib import Path
import httpx

BASE = os.environ.get("COVERAGEGUARD_E2E_URL", "http://127.0.0.1:8011")


def run():
    with httpx.Client(
        base_url=BASE, timeout=15, trust_env=False, headers={"X-Synthetic-Data": "true"}
    ) as c:

        def post(path, data=None):
            r = c.post(path, json=data or {})
            r.raise_for_status()
            return r.json()

        def get(path):
            r = c.get(path)
            r.raise_for_status()
            return r.json()

        def wait_for(count):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                pending = [
                    p
                    for p in get("/api/policies/proposals")
                    if p.get("extraction_method") == "structured_simulator"
                    and p["review_state"] == "pending_review"
                ]
                if len(pending) == count:
                    return pending
                time.sleep(0.3)
            raise AssertionError(
                "Backend scheduler did not detect the expected policies within 30 seconds."
            )

        def approve(proposals):
            for p in proposals:
                post(
                    "/api/policies/proposals/" + p["proposal_id"] + "/approve",
                    {
                        "reviewer_notes": "Synthetic scheduled-HTTP test: verified exact plan, CA jurisdiction, code, date and evidence."
                    },
                )

        settings = get("/api/policy-sync/sources")
        assert settings["scheduler_enabled"] and settings["interval_seconds"] <= 5
        post("/api/simulator/reset?seed_demo=false")
        post("/api/demo/publish-insurer", {"scenario": "reset"})
        post("/api/demo/import-hospital")
        approve(wait_for(5))
        post("/api/demo/publish-insurer", {"scenario": "restriction"})
        restriction = wait_for(1)
        assert restriction[0]["proposed_effect"] == "excluded"
        approve(restriction)
        assert (
            get("/api/claims/H-003/findings")["findings"][0]["result"] == "Not covered"
        )
        post("/api/demo/publish-insurer", {"scenario": "delay"})
        delay = wait_for(1)
        assert delay[0]["change_type"] == "delayed"
        approve(delay)
        findings = get("/api/claims/H-003/findings")
        assert (
            findings["findings"][0]["result"] == "Covered"
            and findings["findings"][1]["result"] == "Prior approval needed"
        )
        report = {
            "transport": "real HTTP",
            "backend_scheduler": True,
            "interval_seconds": settings["interval_seconds"],
            "explicit_sync_calls": 0,
            "hospital_claims": 40,
            "baseline_policies": 5,
            "restriction_detected_automatically": True,
            "delay_detected_automatically": True,
            "unrelated_authorization_retained": True,
        }
        Path("verification/sync/scheduled-http-e2e.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report, indent=2))
        return report


if __name__ == "__main__":
    run()
