"""Reconcile alerts from the deterministic engine's actual ItemVerdict contract."""
from typing import List
from uuid import uuid4

from app.db.store import store
from app.domain.models import Alert, AlertChange, AlertStatus, AlertTask, utc_now
from app.engine.checker import evaluate_case


def run_impact_analysis(source_event_desc: str = "policy sync", data_store=None) -> List[Alert]:
    db = data_store or store
    changed = []
    for case in db.get_all_cases():
        result = evaluate_case(case, db.get_all_rules(), governing_date=case.service_date)
        case.status = result.status
        case.updated_at = utc_now()
        for iv in result.results:
            active = [a for a in db.alerts.values() if a.case_id == case.case_id
                      and a.item_code == iv.item.code and a.status == AlertStatus.OPEN]
            if iv.result == "Covered":
                for alert in active:
                    alert.status = AlertStatus.CLOSED
                    alert.closed_reason = "Full claim re-evaluation: item is covered under current rules."
                    db.record_audit("ALERT_CLOSED", {"alert_id": alert.alert_id, "case_id": case.case_id})
                    changed.append(alert)
                continue
            if any(a.rule_id == (iv.rule_id or "NO_RULE") and a.change.to_version == (iv.rule_version or 0)
                   and a.change.details == iv.full_issue_text for a in active):
                continue
            for alert in active:
                alert.status = AlertStatus.SUPERSEDED
                db.record_audit("ALERT_SUPERSEDED", {"alert_id": alert.alert_id, "case_id": case.case_id})
            proposal = next((p for p in db.proposals.values() if iv.rule_id is not None and p.resulting_rule_id == iv.rule_id
                             and p.resulting_rule_version == iv.rule_version), None)
            alert = Alert(
                alert_id=f"A-{uuid4().hex[:12].upper()}", case_id=case.case_id, item_code=iv.item.code,
                rule_id=iv.rule_id or "NO_RULE", change=AlertChange(
                    from_version=active[0].change.to_version if active else None,
                    to_version=iv.rule_version or 0, change_type=iv.result, details=iv.full_issue_text),
                supersedes=active[0].alert_id if active else None,
                headline=f"{iv.item.name or iv.item.code}: {iv.result}",
                explanation=iv.full_issue_text, suggested_action=iv.what_to_do,
                evidence_quote=proposal.supporting_quote if proposal else None,
                effective_date=iv.effective_date,
                source_document=proposal.document_name if proposal else iv.source_title,
                tasks=[AlertTask(task_id="t1", title=iv.what_to_do),
                       AlertTask(task_id="t2", title="Verify policy scope and service date before submission")],
                draft_message=f"Please review claim {case.case_id}: {iv.full_issue_text}",
            )
            db.alerts[alert.alert_id] = alert
            db.record_audit("ALERT_CREATED", {"alert_id": alert.alert_id, "case_id": case.case_id, "rule_id": iv.rule_id})
            changed.append(alert)
    return changed
