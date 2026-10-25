"""
What-If Claim Impact Simulator for CoverageGuard Policy Intelligence.
Simulates the impact of proposed policy changes against pending hospital claims
using the deterministic rule engine without persisting any database changes.
"""

from typing import List, Dict, Any, Optional
from datetime import date
from copy import deepcopy

from app.domain.models import (
    ProposedPolicyChange,
    ImpactPreviewResult,
    ImpactCaseItem,
    Case,
    Rule,
    RuleStatus,
    Target,
    RuleEffect,
)
from app.engine.checker import evaluate_case
from app.db.store import store


from typing import List, Dict, Any, Optional, Tuple
from datetime import date
from copy import deepcopy

from app.domain.models import (
    ProposedPolicyChange,
    ImpactPreviewResult,
    ImpactCaseItem,
    Case,
    Rule,
    RuleStatus,
    Target,
    RuleEffect,
)
from app.engine.checker import evaluate_case
from app.engine.matcher import match_proposal_to_claim_item, match_proposal_to_target
from app.db.store import store


def _get_active_cases() -> Tuple[List[Case], bool]:
    """
    Returns active caseload cases from store.
    If store has real cases, evaluates them.
    If store has 0 cases:
      - If demo_mode is True: loads temporary demo cases for simulation with synthetic label.
      - If demo_mode is False: returns empty list. Never silently generates synthetic patients.
    """
    is_demo = getattr(store, "demo_mode", False)

    if store.cases:
        return list(store.cases.values()), is_demo

    if is_demo:
        temp_store = deepcopy(store)
        temp_store.load_demo_cases_and_updates()
        return list(temp_store.cases.values()), True

    # Non-demo mode with empty caseload: return 0 cases
    return [], False


def preview_claim_impact(
    proposals: List[ProposedPolicyChange],
    governing_date: Optional[date] = None,
) -> ImpactPreviewResult:
    """
    What-If Claim Impact Simulator:
    Evaluates every claim against current rules, applies proposals to a temporary
    simulated rule set, re-evaluates claims, and computes exact diff with reasons.
    ZERO side-effects on store or persistent database.
    """
    cases, is_demo = _get_active_cases()

    if not cases:
        return ImpactPreviewResult(
            total_cases_checked=0,
            affected_cases=0,
            new_risks=0,
            unchanged_cases=0,
            cases=[],
            is_demo_mode=is_demo,
            notice="No pending claims available for analysis.",
        )

    current_rules = [deepcopy(r) for r in store.rules.values()]

    # 1. Base evaluation with current active rules
    baseline_verdicts: Dict[str, Dict[str, str]] = {}
    for c in cases:
        eval_date = governing_date or c.service_date
        base_res = evaluate_case(c, current_rules, governing_date=eval_date)
        case_items: Dict[str, str] = {}
        for iv in base_res.results:
            case_items[iv.item.code] = iv.result
        baseline_verdicts[c.case_id] = case_items

    # 2. Build temporary simulated rules without side-effects
    simulated_rules: List[Rule] = [deepcopy(r) for r in current_rules]

    for p in proposals:
        # Ignore proposals that lack code or effect
        if not p.target_code or not p.proposed_effect:
            continue

        p_code = p.target_code.upper().strip()
        existing_idx = None
        for idx, r in enumerate(simulated_rules):
            if (
                (r.insurer_id == "*" or r.insurer_id == (p.insurer_id or "*"))
                and r.target.code.upper().strip() == p_code
            ):
                existing_idx = idx
                break

        rule_eff_date = p.effective_from or date(2099, 1, 1)

        if existing_idx is not None:
            old_r = simulated_rules[existing_idx]
            updated_rule = Rule(
                rule_id=old_r.rule_id,
                version=old_r.version + 1,
                insurer_id=p.insurer_id or old_r.insurer_id,
                plan_ids=p.plan_ids or old_r.plan_ids,
                category=old_r.category,
                target=old_r.target,
                effect=p.proposed_effect,
                conditions=p.conditions or old_r.conditions,
                status=RuleStatus.EFFECTIVE if p.change_type != "cancelled" else RuleStatus.CANCELLED,
                effective_from=rule_eff_date,
                effective_to=p.effective_to,
                source_ref=f"proposed:{p.proposal_id}",
                source_title=p.policy_title or old_r.source_title,
                bulletin_summary=f"Simulated policy update: {p.policy_title or old_r.source_title}",
                action_guidance=[f"Verify policy {p.policy_reference or p.proposal_id} before submission."],
            )
            simulated_rules[existing_idx] = updated_rule
        else:
            new_r = Rule(
                rule_id=p.policy_reference or f"SIM-{p_code}",
                version=1,
                insurer_id=p.insurer_id or "*",
                plan_ids=p.plan_ids or ["*"],
                category=p.target_type if p.target_type in ["drug", "procedure", "service"] else "drug",
                target=Target(type=p.target_type or "drug", code=p.target_code, name=p.target_name or p.target_code),
                effect=p.proposed_effect,
                conditions=p.conditions,
                status=RuleStatus.EFFECTIVE if p.change_type != "cancelled" else RuleStatus.CANCELLED,
                effective_from=rule_eff_date,
                effective_to=p.effective_to,
                source_ref=f"proposed:{p.proposal_id}",
                source_title=p.policy_title or f"Proposed Rule {p_code}",
                bulletin_summary=p.policy_title or f"Proposed Rule {p_code}",
                action_guidance=[f"Review requirements for {p.target_name or p.target_code}."],
            )
            simulated_rules.append(new_r)

    # 3. Simulated evaluation with proposed rules
    affected_items: List[ImpactCaseItem] = []
    new_risks_count = 0

    adverse_verdicts = {"Not covered", "Prior approval needed", "Document missing"}

    for c in cases:
        eval_date = governing_date or c.service_date
        sim_res = evaluate_case(c, simulated_rules, governing_date=eval_date)
        base_items = baseline_verdicts.get(c.case_id, {})

        for sim_iv in sim_res.results:
            item_code = sim_iv.item.code
            base_verdict = base_items.get(item_code, "Covered")
            sim_verdict = sim_iv.result

            # Match proposal to this specific case item using strict matcher
            matching_proposal = next(
                (p for p in proposals if match_proposal_to_target(p, c.insurer_id, c.plan_id, item_code)),
                None
            )

            is_different = base_verdict != sim_verdict
            is_matching_target = bool(matching_proposal)

            # Record if verdict changed OR if item matches proposal target and is adverse on claim date
            if is_different or (is_matching_target and sim_verdict != "Covered"):
                # New risk is strictly a change from non-adverse to adverse
                if sim_verdict in adverse_verdicts and base_verdict not in adverse_verdicts:
                    new_risks_count += 1

                reason = (
                    f"Policy {matching_proposal.policy_reference if matching_proposal and matching_proposal.policy_reference else 'change'} "
                    f"sets {item_code} as {sim_verdict.lower()} effective {sim_iv.effective_date or 'announced date'}. "
                    f"Claim service date is {c.service_date}."
                )

                affected_items.append(
                    ImpactCaseItem(
                        case_id=c.case_id,
                        member_ref=c.member_ref,
                        specialty=c.specialty,
                        service_date=str(c.service_date),
                        item_code=item_code,
                        item_name=sim_iv.item.name or item_code,
                        previous_verdict=base_verdict,
                        simulated_verdict=sim_verdict,
                        reason=reason,
                        supporting_quote=matching_proposal.supporting_quote if matching_proposal else None,
                        action_steps=sim_iv.action_guidance or [sim_iv.what_to_do],
                    )
                )

    total_cases = len(cases)
    affected_cases_count = len({item.case_id for item in affected_items})
    unchanged_count = max(0, total_cases - affected_cases_count)

    return ImpactPreviewResult(
        total_cases_checked=total_cases,
        affected_cases=affected_cases_count,
        new_risks=new_risks_count,
        unchanged_cases=unchanged_count,
        cases=affected_items,
        is_demo_mode=is_demo,
        notice="Showing synthetic demo claims." if (is_demo and not store.cases) else None,
    )
