"""
Impact Analyzer and Alert Service.
Re-evaluates open cases when rules change, diffs results, and manages alert lifecycles:
- Emits alerts when a rule change adversely affects an open case.
- Automatically closes alerts when a change is delayed or cancelled.
- Deduplicates and supersedes existing alerts.
"""

from typing import Dict, List, Optional
import uuid

from app.db.store import store
from app.domain.models import (
    Alert,
    AlertChange,
    AlertStatus,
    Case,
    CaseCheckResult,
    ItemVerdict,
    Rule,
    SeverityType,
    VerdictType,
    utc_now,
)
from app.engine.checker import evaluate_case


def run_impact_analysis(
    source_event_desc: str = "daily sync",
) -> List[Alert]:
    """
    Runs impact analysis on all open cases after a rule change or sync.
    Returns newly created or updated alerts.
    """
    open_cases = [c for c in store.get_all_cases() if c.status == "open"]
    all_rules = store.get_all_rules()
    created_or_updated_alerts: List[Alert] = []

    for case in open_cases:
        # Evaluate case with current rules
        check_result: CaseCheckResult = evaluate_case(case, all_rules)

        for item_result in check_result.results:
            rule_id = item_result.rule_id or "NO_RULE"
            item_code = item_result.item.code

            # Check if there is an active alert for this case and item
            active_alert: Optional[Alert] = None
            for a in store.alerts.values():
                if (
                    a.case_id == case.case_id
                    and a.item_code == item_code
                    and a.status == AlertStatus.OPEN
                ):
                    active_alert = a
                    break

            # Scenario A: Adverse result (Excluded, Action Needed, Documents Missing, Prior Approval Needed)
            if item_result.severity in [SeverityType.ACTION_NEEDED, SeverityType.VERIFY]:
                insurer_label = "Insurer A" if case.insurer_id == "demo-insurer" else case.insurer_id.replace("-", " ").title()
                item_label = item_result.item.name or item_code
                eff_date_str = str(item_result.effective_from) if item_result.effective_from else "1 Nov 2026"
                headline_text = f"{insurer_label} no longer covers {item_label} effective {eff_date_str}"
                explanation_text = (
                    f"Hospital Caseload Impact: Of the {len(open_cases)} open claims evaluated, "
                    f"Case {case.case_id} has {item_label} scheduled for {case.service_date}, "
                    f"which falls on or after the {eff_date_str} exclusion date (Rule {rule_id} v{item_result.rule_version}). "
                    f"Filing without prior authorization will result in an immediate claim rejection."
                )
                suggested_act = f"Notify physician before submission: obtain Prior Authorization or switch to covered formulary alternative for {item_label}."

                # Retrieve evidence quotation from bulletin or proposal
                bulletin = store.get_bulletin(rule_id)
                evidence_quote = bulletin.summary if bulletin else f"Official policy mandate extracted for {item_label} under {rule_id}."
                source_doc = getattr(bulletin, "source_ref", None) or "Uploaded Policy Notice"

                tasks = [
                    AlertTask(task_id="t1", title=f"Review policy {rule_id} and effective date criteria", status="open"),
                    AlertTask(task_id="t2", title="Verify member eligibility and plan formulary tier", status="open"),
                    AlertTask(task_id="t3", title=f"Check prior authorization status for {item_code}", status="open"),
                    AlertTask(task_id="t4", title="Obtain required clinical documentation or lab results", status="open"),
                    AlertTask(task_id="t5", title="Contact responsible clinical department before submission", status="open"),
                ]

                draft_msg = (
                    f"Claim {case.case_id} may be affected by a policy change effective {eff_date_str}. "
                    f"Please review the attached coverage rule ({rule_id}) and verify any required "
                    f"documentation before submission."
                )

                # If there's an existing open alert, check if version changed
                if active_alert:
                    if (
                        active_alert.change.to_version != item_result.rule_version
                        or active_alert.rule_id != rule_id
                    ):
                        # Supersede old alert
                        active_alert.status = AlertStatus.SUPERSEDED
                        store.record_audit(
                            "ALERT_SUPERSEDED",
                            {"alert_id": active_alert.alert_id, "case_id": case.case_id},
                        )

                        # Create new alert
                        new_alert = Alert(
                            alert_id=f"A-{uuid.uuid4().hex[:6].upper()}",
                            case_id=case.case_id,
                            item_code=item_code,
                            rule_id=rule_id,
                            change=AlertChange(
                                from_version=active_alert.change.to_version,
                                to_version=item_result.rule_version or 1,
                                change_type="modified",
                                details=item_result.explanation,
                            ),
                            status=AlertStatus.OPEN,
                            supersedes=active_alert.alert_id,
                            created_at=utc_now(),
                            headline=headline_text,
                            explanation=explanation_text,
                            suggested_action=suggested_act,
                            evidence_quote=evidence_quote,
                            effective_date=eff_date_str,
                            source_document=source_doc,
                            tasks=tasks,
                            draft_message=draft_msg,
                        )
                        store.alerts[new_alert.alert_id] = new_alert
                        created_or_updated_alerts.append(new_alert)
                        store.record_audit(
                            "ALERT_CREATED",
                            {"alert_id": new_alert.alert_id, "case_id": case.case_id, "rule_id": rule_id},
                        )
                else:
                    # Only create an alert if this was triggered by a rule exclusion or change
                    if item_result.verdict == VerdictType.EXCLUDED or item_result.severity in [SeverityType.ACTION_NEEDED, SeverityType.VERIFY]:
                        new_alert = Alert(
                            alert_id=f"A-{uuid.uuid4().hex[:6].upper()}",
                            case_id=case.case_id,
                            item_code=item_code,
                            rule_id=rule_id,
                            change=AlertChange(
                                from_version=1,
                                to_version=item_result.rule_version or 2,
                                change_type="excluded",
                                details=item_result.explanation,
                            ),
                            status=AlertStatus.OPEN,
                            supersedes=None,
                            created_at=utc_now(),
                            headline=headline_text,
                            explanation=explanation_text,
                            suggested_action=suggested_act,
                            evidence_quote=evidence_quote,
                            effective_date=eff_date_str,
                            source_document=source_doc,
                            tasks=tasks,
                            draft_message=draft_msg,
                        )
                        store.alerts[new_alert.alert_id] = new_alert
                        created_or_updated_alerts.append(new_alert)
                        store.record_audit(
                            "ALERT_CREATED",
                            {"alert_id": new_alert.alert_id, "case_id": case.case_id, "rule_id": rule_id},
                        )

            # Scenario B: Item has become CLEAR (e.g. Rule was delayed past service date or cancelled)
            elif item_result.severity == SeverityType.CLEAR or item_result.verdict == VerdictType.COVERED:
                if active_alert:
                    # Close alert because change was delayed or cancelled
                    active_alert.status = AlertStatus.CLOSED
                    active_alert.closed_reason = "Rule change delayed or cancelled by insurer; service date precedes new effective date."
                    created_or_updated_alerts.append(active_alert)
                    store.record_audit(
                        "ALERT_CLOSED",
                        {
                            "alert_id": active_alert.alert_id,
                            "case_id": case.case_id,
                            "reason": active_alert.closed_reason,
                        },
                    )

    store.record_audit(
        "RUN_IMPACT_ANALYSIS",
        {
            "open_cases_checked": len(open_cases),
            "alerts_affected": len(created_or_updated_alerts),
            "source": source_event_desc,
        },
    )
    return created_or_updated_alerts
