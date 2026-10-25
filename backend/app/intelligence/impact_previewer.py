"""Side-effect-free proposal simulation using the same rule builder and evaluator as approval."""
from copy import deepcopy
from datetime import date
from typing import List, Optional

from app.domain.models import ProposedPolicyChange, ImpactPreviewResult, ImpactCaseItem
from app.engine.checker import evaluate_case
from app.engine.matcher import match_proposal_to_target
from app.intelligence.rule_builder import build_proposed_rule
from app.db.store import store


def _get_active_cases():
    if store.cases:
        return list(store.cases.values()), store.demo_mode
    if store.demo_mode:
        from app.db.store import DataStore
        temporary = DataStore(persist=False)
        temporary.load_demo_cases_and_updates()
        return list(temporary.cases.values()), True
    return [], False


def preview_claim_impact(proposals: List[ProposedPolicyChange], governing_date: Optional[date] = None) -> ImpactPreviewResult:
    cases, is_demo = _get_active_cases()
    baseline = deepcopy(list(store.rules.values()))
    simulated = deepcopy(baseline)
    applicable_proposals = []
    warnings = []
    for p in proposals:
        if p.review_state == "rejected":
            continue
        if p.review_state == "approved" and p.resulting_rule_id:
            continue
        try:
            simulated.append(build_proposed_rule(p, simulated))
            applicable_proposals.append(p)
        except ValueError as exc:
            warnings.append(f"{p.proposal_id}: {exc}")
    items = []
    new_risks = set()
    adverse = {"Not covered", "Prior approval needed", "Document missing", "Value wrong", "No rule found, verify with the insurer"}
    for case in cases:
        old = evaluate_case(case, baseline, governing_date)
        new = evaluate_case(case, simulated, governing_date)
        for before, after in zip(old.results, new.results):
            p = next((p for p in reversed(applicable_proposals) if match_proposal_to_target(
                p, case.insurer_id, case.plan_id, after.item.code, after.item.type)), None)
            if not p or before.result == after.result:
                continue
            if after.result in adverse and before.result not in adverse:
                new_risks.add(case.case_id)
            items.append(ImpactCaseItem(
                case_id=case.case_id, member_ref=case.member_ref, specialty=case.specialty,
                service_date=str(case.service_date), item_code=after.item.code,
                item_name=after.item.name or after.item.code, previous_verdict=before.result,
                simulated_verdict=after.result, reason=after.full_issue_text,
                supporting_quote=p.supporting_quote, action_steps=after.action_guidance or [after.what_to_do],
            ))
    affected = len({item.case_id for item in items})
    notices = warnings + (["No pending claims available for analysis."] if not cases else [])
    if is_demo and not store.cases:
        notices.append("Showing synthetic demo claims.")
    return ImpactPreviewResult(total_cases_checked=len(cases), affected_cases=affected,
        new_risks=len(new_risks), unchanged_cases=len(cases)-affected, cases=items,
        is_demo_mode=is_demo, notice=" ".join(notices) or None)
