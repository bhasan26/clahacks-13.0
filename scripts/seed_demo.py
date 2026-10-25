"""Load the demo so the app opens ready: import test claims, fetch demo rules, approve them.

Safe to re-run: imports never overwrite existing claims and only pending demo rules are approved.
Only touches the local synthetic services; real insurer rules are never auto-approved.
"""

import os
import sys

import httpx

API = os.environ.get("COVERAGEGUARD_SEED_URL", "http://127.0.0.1:8000")
NOTE = "Reviewed synthetic simulator schema, exact plan, CA jurisdiction, code, effective date and source evidence."


def main():
    headers = {"X-Synthetic-Data": "true"}
    token = os.environ.get("COVERAGEGUARD_REVIEW_TOKEN")
    if token:
        headers["X-Reviewer-Token"] = token
    with httpx.Client(base_url=API, headers=headers, timeout=60, trust_env=False) as client:
        def post(path, body=None):
            response = client.post(path, json=body or {})
            response.raise_for_status()
            return response.json()

        imported = post("/api/demo/import-hospital")["imported"]
        post("/api/policy-sync/run", {"source_id": "demo-insurer-api"})
        approved = 0
        for proposal in client.get("/api/policies/proposals").raise_for_status().json():
            if proposal.get("extraction_method") == "structured_simulator" and proposal["review_state"] == "pending_review":
                post(f"/api/policies/proposals/{proposal['proposal_id']}/approve", {"reviewer_notes": NOTE})
                approved += 1
    print(f"Demo ready: {imported} test claims, {approved} demo rule(s) approved.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as error:
        print(f"Demo setup skipped: {error}. Use Insurer rules → 'Load demo claims' instead.", file=sys.stderr)
