"""
Deterministic Check Engine for CoverageGuard.
Pure function: check(case, rules, governing_date) -> CaseCheckResult
No LLM dependencies; 100% reproducible and testable.
"""

from datetime import date
from typing import List, Optional, Tuple

from app.domain.models import (
    Case,
    CaseCheckResult,
    CaseItem,
    CaseOverallStatus,
    ItemVerdict,
    Rule,
    RuleEffect,
    RuleStatus,
    SeverityType,
    VerdictType,
)


def is_rule_applicable(
    rule: Rule,
    insurer_id: str,
    plan_id: str,
    item: CaseItem,
    governing_date: date,
) -> bool:
    """
    Check if a rule version applies to an item on the governing date:
    1. Same insurer.
    2. plan_ids contains plan_id or '*'.
    3. Target type and code match item type and code.
    4. Status is 'effective' or 'announced' (cancelled and superseded are ignored).
    5. governing_date lies within [effective_from, effective_to).
    """
    if rule.insurer_id != insurer_id:
        return False

    if "*" not in rule.plan_ids and plan_id not in rule.plan_ids:
        return False

    if (
        rule.target.type.lower() != item.type.lower()
        or rule.target.code.upper() != item.code.upper()
    ):
        return False

    if rule.status in [RuleStatus.CANCELLED, RuleStatus.SUPERSEDED]:
        return False

    # Check temporal validity
    if governing_date < rule.effective_from:
        return False

    if rule.effective_to and governing_date >= rule.effective_to:
        return False

    return True


def select_best_rule(
    matching_rules: List[Rule], plan_id: str
) -> Tuple[Optional[Rule], bool]:
    """
    Select rule with highest precedence:
    1. Specific plan_id match over wildcard '*'
    2. Latest effective_from
    3. Highest version

    Returns (best_rule, has_conflict)
    """
    if not matching_rules:
        return None, False

    def sort_key(r: Rule):
        is_plan_specific = 1 if plan_id in r.plan_ids else 0
        return (is_plan_specific, r.effective_from, r.version)

    sorted_rules = sorted(matching_rules, key=sort_key, reverse=True)
    best = sorted_rules[0]

    # Check if second rule has identical precedence but different effect
    if len(sorted_rules) > 1:
        second = sorted_rules[1]
        if sort_key(best) == sort_key(second) and best.effect != second.effect:
            return None, True

    return best, False


def check_item(
    item: CaseItem,
    case: Case,
    rules: List[Rule],
    governing_date: date,
) -> ItemVerdict:
    """Evaluate a single case item against the rules catalog."""
    applicable_rules = [
        r
        for r in rules
        if is_rule_applicable(r, case.insurer_id, case.plan_id, item, governing_date)
    ]

    best_rule, has_conflict = select_best_rule(applicable_rules, case.plan_id)

    if has_conflict:
        return ItemVerdict(
            item=item,
            verdict=VerdictType.CANNOT_ASSESS,
            severity=SeverityType.ACTION_NEEDED,
            explanation=f"Conflicting rules found for {item.code} at the same precedence level.",
            suggested_officer_action="Escalate to rules reviewer for clarification with insurer.",
        )

    if not best_rule:
        # Check if an upcoming rule was announced after governing date
        upcoming = [
            r
            for r in rules
            if r.insurer_id == case.insurer_id
            and ("*" in r.plan_ids or case.plan_id in r.plan_ids)
            and r.target.code.upper() == item.code.upper()
            and r.status in [RuleStatus.ANNOUNCED, RuleStatus.EFFECTIVE]
            and r.effective_from > governing_date
        ]

        if upcoming:
            latest_upcoming = sorted(upcoming, key=lambda r: r.effective_from)[0]
            return ItemVerdict(
                item=item,
                verdict=VerdictType.NO_RULE_FOUND,
                severity=SeverityType.VERIFY,
                rule_id=latest_upcoming.rule_id,
                rule_version=latest_upcoming.version,
                effective_from=latest_upcoming.effective_from,
                source_ref=latest_upcoming.source_ref,
                explanation=f"No active rule on {governing_date}. Note: change announced to take effect on {latest_upcoming.effective_from}.",
                suggested_officer_action="Verify coverage directly with insurer before submitting.",
            )

        return ItemVerdict(
            item=item,
            verdict=VerdictType.NO_RULE_FOUND,
            severity=SeverityType.VERIFY,
            explanation=f"No applicable coverage rule found for {item.code} under plan {case.plan_id}.",
            suggested_officer_action="No rule found in insurer feed; verify coverage directly with insurer.",
        )

    # 1. Exclusion
    if best_rule.effect == RuleEffect.EXCLUDED:
        return ItemVerdict(
            item=item,
            verdict=VerdictType.EXCLUDED,
            severity=SeverityType.ACTION_NEEDED,
            rule_id=best_rule.rule_id,
            rule_version=best_rule.version,
            effective_from=best_rule.effective_from,
            source_ref=best_rule.source_ref,
            explanation=f"{item.code} is excluded under rule {best_rule.rule_id} v{best_rule.version} from {best_rule.effective_from} for plan {case.plan_id}.",
            suggested_officer_action="Take file to treating physician before submission to choose a covered alternative drug to avoid claim rejection.",
        )

    # 2. Prior Approval Needed
    if (
        best_rule.effect == RuleEffect.REQUIRES_PRIOR_APPROVAL
        or (best_rule.conditions and best_rule.conditions.get("requires_prior_approval"))
    ):
        if not case.prior_approval_ref:
            return ItemVerdict(
                item=item,
                verdict=VerdictType.PRIOR_APPROVAL_NEEDED,
                severity=SeverityType.ACTION_NEEDED,
                rule_id=best_rule.rule_id,
                rule_version=best_rule.version,
                effective_from=best_rule.effective_from,
                source_ref=best_rule.source_ref,
                explanation=f"{item.code} requires prior approval under rule {best_rule.rule_id} v{best_rule.version}, but no approval reference was provided.",
                suggested_officer_action="Obtain prior approval reference from insurer before submission.",
            )

    # 3. Required Documents Missing
    if (
        best_rule.effect == RuleEffect.REQUIRES_DOCUMENTS
        or (best_rule.conditions and "required_documents" in best_rule.conditions)
    ):
        required_docs = []
        if best_rule.conditions and "required_documents" in best_rule.conditions:
            required_docs = best_rule.conditions["required_documents"]
        missing_docs = [doc for doc in required_docs if doc not in case.documents]
        if missing_docs:
            return ItemVerdict(
                item=item,
                verdict=VerdictType.DOCUMENTS_MISSING,
                severity=SeverityType.ACTION_NEEDED,
                rule_id=best_rule.rule_id,
                rule_version=best_rule.version,
                effective_from=best_rule.effective_from,
                source_ref=best_rule.source_ref,
                explanation=f"{item.code} requires documentation ({', '.join(missing_docs)}) under rule {best_rule.rule_id} v{best_rule.version}.",
                suggested_officer_action=f"Attach required supporting documentation ({', '.join(missing_docs)}) before submission.",
            )

    # 4. Covered
    return ItemVerdict(
        item=item,
        verdict=VerdictType.COVERED,
        severity=SeverityType.CLEAR,
        rule_id=best_rule.rule_id,
        rule_version=best_rule.version,
        effective_from=best_rule.effective_from,
        source_ref=best_rule.source_ref,
        explanation=f"{item.code} is covered under rule {best_rule.rule_id} v{best_rule.version} from {best_rule.effective_from}.",
        suggested_officer_action="Proceed with standard submission.",
    )


def evaluate_case(
    case: Case,
    rules: List[Rule],
    governing_date: Optional[date] = None,
) -> CaseCheckResult:
    """
    Pure check engine function to evaluate entire case.
    Governing date defaults to case.service_date.
    """
    target_date = governing_date or case.service_date
    item_verdicts: List[ItemVerdict] = []

    # Completeness check on core fields
    if not case.service_date or not case.insurer_id or not case.plan_id:
        return CaseCheckResult(
            case_id=case.case_id,
            governing_date=target_date,
            overall_status=CaseOverallStatus.CANNOT_ASSESS,
            results=[
                ItemVerdict(
                    item=CaseItem(type="case", code="METADATA", name="Case Info"),
                    verdict=VerdictType.CANNOT_ASSESS,
                    severity=SeverityType.ACTION_NEEDED,
                    explanation="Required case fields (service_date, insurer_id, plan_id) are missing.",
                    suggested_officer_action="Complete required fields before running check.",
                )
            ],
        )

    for item in case.items:
        verdict = check_item(item, case, rules, target_date)
        item_verdicts.append(verdict)

    # Determine overall case status
    has_action_needed = any(
        v.severity == SeverityType.ACTION_NEEDED for v in item_verdicts
    )
    has_verify = any(v.severity == SeverityType.VERIFY for v in item_verdicts)

    if has_action_needed:
        overall_status = CaseOverallStatus.NEEDS_ATTENTION
    elif has_verify:
        overall_status = CaseOverallStatus.CANNOT_ASSESS
    else:
        overall_status = CaseOverallStatus.CLEAR

    return CaseCheckResult(
        case_id=case.case_id,
        governing_date=target_date,
        overall_status=overall_status,
        results=item_verdicts,
    )
