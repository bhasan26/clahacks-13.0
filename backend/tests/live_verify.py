"""Opt-in live verification. Sends only an explicitly synthetic audit policy to Gemini.

Run from repo root: PYTHONPATH=backend backend/.venv/bin/python backend/tests/live_verify.py
Network access and GEMINI_API_KEY are required for the relevant live checks.
"""
import json
import os
from datetime import date

# Isolate verification from the application's local checkpoint and caseload.
os.environ["COVERAGEGUARD_STATE_PATH"] = ""
from app.connectors.official_policy_source import CMSMedicareConnector
from app.intelligence.document_processor import process_uploaded_document
from app.connectors.change_detector import check_source_for_changes
from app.db.store import store
from app.domain.models import Case, CaseItem, Rule, Target, OfficialPolicySource
from app.main import app
from fastapi.testclient import TestClient


def verify():
    report = {}
    client = TestClient(app, headers={"X-Synthetic-Data": "true"})
    store.reset_state(seed_demo=False)
    store.demo_mode = False
    try:
        connector = CMSMedicareConnector(timeout_seconds=25)
        first, name, meta = connector.fetch_latest_document()
        doc = process_uploaded_document(first, name, meta["content_type"])
        second, second_name, second_meta = connector.fetch_latest_document()
        second_doc = process_uploaded_document(second, second_name, second_meta["content_type"])
        import hashlib, re
        digest = lambda text: hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()
        report["cms"] = {"http_status": 200, "source_url": meta["source_url"], "title": doc.get("policy_title"),
                         "download_bytes": len(first), "policy_text_characters": len(doc["raw_text"]),
                         "meaningful_hash": digest(doc["raw_text"]), "second_fetch_same_policy": digest(doc["raw_text"]) == digest(second_doc["raw_text"])}
        # Run the actual source pipeline twice (another pair of real HTTP requests).
        source = OfficialPolicySource(source_id="LIVE-CMS-AUDIT", name="Live public CMS NCD", insurer_name="CMS", official_url=meta["source_url"])
        store.save_source(source)
        staged = check_source_for_changes(source)
        repeated = check_source_for_changes(source)
        report["cms"].update(first_pipeline_status=staged.status, repeat_pipeline_status=repeated.status,
                             proposals_staged=len(staged.proposals_created), repeat_proposals=len(repeated.proposals_created),
                             approved_rules_applied=0, extraction_error=staged.error_message)
    except Exception as exc:
        report["cms"] = {"status": "failed", "error_type": type(exc).__name__}
    from app.intelligence.policy_extractor import get_gemini_api_key
    if not get_gemini_api_key():
        report["gemini"] = {"status": "not_tested", "reason": "GEMINI_API_KEY unavailable"}
    else:
        try:
            import fitz
            store.reset_state(seed_demo=False)
            store.demo_mode = False
            base = Rule(rule_id="AUDIT-BASE", version=1, insurer_id="aetna", plan_ids=["PLAN-AUDIT"],
                        category="drug", target=Target(type="drug", code="J1234"), effect="covered", status="effective",
                        effective_from=date(2026, 1, 1), source_ref="Explicit synthetic baseline for audit")
            store.rules = {"AUDIT-BASE_v1": base}
            store.cases["AUDIT-CLAIM"] = Case(case_id="AUDIT-CLAIM", insurer_id="aetna", plan_id="PLAN-AUDIT", member_ref="SYNTHETIC-ONLY",
                                                service_date=date(2026, 11, 12), items=[CaseItem(type="drug", code="J1234")])
            text = "SYNTHETIC POLICY NOTICE FOR SOFTWARE VERIFICATION ONLY\nInsurer: Aetna\nPlan: PLAN-AUDIT\nAetna excludes drug J1234 under PLAN-AUDIT effective November 1, 2026.\nNo patient data is included in this synthetic notice."
            pdf = fitz.open()
            pdf.new_page().insert_text((45, 60), text, fontsize=10)
            data = pdf.tobytes()
            r = client.post("/api/policies/extract", files={"file": ("unfamiliar-synthetic-audit.pdf", data, "application/pdf")})
            r.raise_for_status()
            doc = r.json()
            p = next(p for p in doc["proposals"] if p["target_code"] == "J1234")
            report["gemini_diagnostics"] = {"method": doc["extraction_method"], "extraction_error": doc["extraction_error"],
                                           "insurer": p["insurer_id"], "plans": p["plan_ids"], "code": p["target_code"],
                                           "effective_from": p["effective_from"], "evidence_verified": p["evidence_verified"]}
            assert doc["extraction_method"] == "gemini", doc["extraction_error"]
            assert p["insurer_id"] == "aetna" and p["plan_ids"] == ["PLAN-AUDIT"]
            assert p["effective_from"] == "2026-11-01" and p["proposed_effect"] == "excluded"
            assert p["evidence_verified"]
            assert doc["impact_preview"]["affected_cases"] == 1
            approval = client.post(f'/api/policies/proposals/{p["proposal_id"]}/approve', json={"reviewer_notes": "Synthetic live Gemini integration verification. Source fields checked."})
            approval.raise_for_status()
            rule = approval.json()["rule"]
            assert rule["version"] == 2
            assert store.cases["AUDIT-CLAIM"].status == "Needs attention"
            assert store.get_open_alerts()
            assert any(e["action"] == "POLICY_PROPOSAL_APPROVED" for e in store.audit_log)
            report["gemini"] = {"status": "passed_live", "extraction_method": doc["extraction_method"], "verified_quote": p["evidence_verified"],
                                "insurer": p["insurer_id"], "plans": p["plan_ids"], "code": p["target_code"], "effective_date": p["effective_from"],
                                "affected_claims": doc["impact_preview"]["affected_cases"], "stored_rule_version": rule["version"],
                                "open_alerts": len(store.get_open_alerts()), "audit_entries": len(store.audit_log)}
        except Exception as exc:
            report["gemini"] = {"status": "failed", "error_type": type(exc).__name__,
                                "reason": "Live extraction/validation/approval assertion failed; do not treat fallback as a live success."}
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    verify()
