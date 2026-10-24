"""
Deterministic Check Engine for CoverageGuard.
Pure function: evaluate_case(case, rules, governing_date) -> CaseCheckResult
Produces plain wording per specification:
- Statuses: Approved, Needs attention, Missing or wrong info
- Item Results: Covered, Not covered, Prior approval needed, Document missing, Value wrong, No rule found, verify with the insurer
- Each issue gets: one plain sentence, rule reference, what to do.
- Agent only notifies; never edits, rejects, or submits, and never suggests a medical alternative.
"""

from datetime import date
from typing import List, Optional, Tuple

from app.domain.models import (
    Case,
    CaseCheckResult,
    CaseItem,
    CaseStatusType,
    ItemResultType,
    ItemVerdict,
    Rule,
    RuleEffect,
    RuleStatus,
)


def format_date_plain(d: Optional[date]) -> str:
    if not d:
        return "1 Nov 2026"
    return d.strftime("%-d %b %Y")


def normalize_insurer(ins: Optional[str]) -> str:
    s = (ins or "").lower()
    if "aetna" in s:
        return "aetna"
    if "blue" in s or "bcbs" in s:
        return "bcbs"
    if "united" in s or "uhc" in s:
        return "uhc"
    if "cigna" in s:
        return "cigna"
    if "medicare" in s or "cms" in s:
        return "cms"
    return "demo-insurer"


ALIAS_MAP = {
    "KEYTRUDA": ["KEYTRUDA", "PEMBROLIZUMAB", "J9271"],
    "PEMBROLIZUMAB": ["KEYTRUDA", "PEMBROLIZUMAB", "J9271"],
    "J9271": ["KEYTRUDA", "PEMBROLIZUMAB", "J9271"],
    "OZEMPIC": ["OZEMPIC", "SEMAGLUTIDE", "J3490", "WEGOVY"],
    "SEMAGLUTIDE": ["OZEMPIC", "SEMAGLUTIDE", "J3490", "WEGOVY"],
    "HUMIRA": ["HUMIRA", "ADALIMUMAB", "J0135"],
    "ADALIMUMAB": ["HUMIRA", "ADALIMUMAB", "J0135"],
    "PROC-1": ["PROC-1", "KNEE ARTHROPLASTY", "TOTAL KNEE", "27447", "MAJOR JOINT PROCEDURE"],
    "DRUG-A": ["DRUG-A", "DRUG A"],
    "DRUG-B": ["DRUG-B", "DRUG B", "LISINOPRIL", "ATORVASTATIN"],
}


def codes_match(target_code: str, item_code: str, item_name: Optional[str] = None) -> bool:
    t_up = target_code.upper()
    i_up = item_code.upper()
    if t_up == i_up:
        return True
    
    aliases = ALIAS_MAP.get(t_up, [t_up])
    if i_up in aliases:
        return True
    
    if item_name:
        name_up = item_name.upper()
        if any(alias in name_up for alias in aliases):
            return True
            
    return False


def is_rule_applicable(
    rule: Rule,
    insurer_id: str,
    plan_id: str,
    item: CaseItem,
    governing_date: date,
) -> bool:
    """Check if a rule version applies to an item on governing_date."""
    # Match insurer
    if rule.insurer_id != "*" and rule.insurer_id != insurer_id:
        if normalize_insurer(rule.insurer_id) != normalize_insurer(insurer_id):
            return False

    if "*" not in rule.plan_ids and plan_id not in rule.plan_ids:
        return False

    if not codes_match(rule.target.code, item.code, item.name):
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
    """Select rule with highest precedence: plan-specific > effective_from > version."""
    if not matching_rules:
        return None, False

    def sort_key(r: Rule):
        is_plan_specific = 1 if plan_id in r.plan_ids else 0
        return (is_plan_specific, r.effective_from, r.version)

    sorted_rules = sorted(matching_rules, key=sort_key, reverse=True)
    best = sorted_rules[0]

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
    item_display = item.name or item.code

    applicable_rules = [
        r
        for r in rules
        if is_rule_applicable(r, case.insurer_id, case.plan_id, item, governing_date)
    ]

    best_rule, has_conflict = select_best_rule(applicable_rules, case.plan_id)

    # 1. No rule found
    if not best_rule or has_conflict:
        # Check if an upcoming rule was announced after governing date
        upcoming = [
            r
            for r in rules
            if (r.insurer_id == "*" or normalize_insurer(r.insurer_id) == normalize_insurer(case.insurer_id))
            and ("*" in r.plan_ids or case.plan_id in r.plan_ids)
            and codes_match(r.target.code, item.code, item.name)
            and r.status in [RuleStatus.ANNOUNCED, RuleStatus.EFFECTIVE]
            and r.effective_from > governing_date
        ]

        if upcoming:
            latest_upcoming = sorted(upcoming, key=lambda r: r.effective_from)[0]
            eff_str = format_date_plain(latest_upcoming.effective_from)
            sentence = f"{item_display} has an announced policy change effective {eff_str}."
            rule_ref = f"Rule {latest_upcoming.rule_id}."
            action = "Verify with the insurer before submitting."
            return ItemVerdict(
                item=item,
                result="Covered",
                rule_id=latest_upcoming.rule_id,
                rule_version=latest_upcoming.version,
                effective_date=eff_str,
                plain_sentence=sentence,
                rule_reference=rule_ref,
                what_to_do=action,
                full_issue_text=f"{sentence} {rule_ref} {action}",
                source_title=latest_upcoming.source_title or f"Policy Bulletin {latest_upcoming.rule_id}",
                source_url=latest_upcoming.source_url or f"/api/bulletins/{latest_upcoming.rule_id}",
                bulletin_summary=latest_upcoming.bulletin_summary,
                action_guidance=latest_upcoming.action_guidance,
            )

        sentence = f"No matching rule found for {item_display}."
        rule_ref = "Rule unlisted."
        action = "No rule found, verify with the insurer."
        return ItemVerdict(
            item=item,
            result="No rule found, verify with the insurer",
            rule_id=None,
            rule_version=None,
            effective_date=None,
            plain_sentence=sentence,
            rule_reference=rule_ref,
            what_to_do=action,
            full_issue_text=f"{sentence} {rule_ref} {action}",
            why_not_approved="No established insurer policy found for this billing code in the current database.",
            action_guidance=["Verify patient eligibility and code in payer portal before filing."],
        )

    eff_str = format_date_plain(best_rule.effective_from)
    rule_ref = f"Rule {best_rule.rule_id}."
    src_title = best_rule.source_title or f"Insurer Policy Bulletin {best_rule.rule_id}"
    src_url = best_rule.source_url or f"/api/bulletins/{best_rule.rule_id}"
    b_summary = best_rule.bulletin_summary
    guidance = best_rule.action_guidance or [best_rule.source_ref]

    # 2. Excluded
    if best_rule.effect == RuleEffect.EXCLUDED:
        sentence = f"{item_display} is not covered from {eff_str}."
        action = "Review with the physician before submitting."
        why = f"{item_display} is non-covered or excluded under policy {best_rule.rule_id} effective {eff_str}."
        return ItemVerdict(
            item=item,
            result="Not covered",
            rule_id=best_rule.rule_id,
            rule_version=best_rule.version,
            effective_date=eff_str,
            plain_sentence=sentence,
            rule_reference=rule_ref,
            what_to_do=action,
            full_issue_text=f"{sentence} {rule_ref} {action}",
            source_title=src_title,
            source_url=src_url,
            why_not_approved=why,
            bulletin_summary=b_summary,
            action_guidance=guidance or ["Discuss formulary alternatives with the ordering physician before submission."],
        )

    # 3. Prior Approval Needed
    if (
        best_rule.effect == RuleEffect.REQUIRES_PRIOR_APPROVAL
        or (best_rule.conditions and best_rule.conditions.get("requires_prior_approval"))
    ):
        if not case.prior_approval_ref:
            sentence = f"{item_display} requires prior approval under current rules."
            action = "Obtain prior approval reference from insurer before submitting."
            why = f"{item_display} requires pre-service clinical authorization from {case.insurer_name or 'the insurer'} under policy {best_rule.rule_id}."
            return ItemVerdict(
                item=item,
                result="Prior approval needed",
                rule_id=best_rule.rule_id,
                rule_version=best_rule.version,
                effective_date=eff_str,
                plain_sentence=sentence,
                rule_reference=rule_ref,
                what_to_do=action,
                full_issue_text=f"{sentence} {rule_ref} {action}",
                source_title=src_title,
                source_url=src_url,
                why_not_approved=why,
                bulletin_summary=b_summary,
                action_guidance=guidance or ["Submit prior authorization request via payer provider portal before service is rendered."],
            )

    # 4. Required Documents Missing
    if (
        best_rule.effect == RuleEffect.REQUIRES_DOCUMENTS
        or (best_rule.conditions and "required_documents" in best_rule.conditions)
    ):
        required_docs = []
        if best_rule.conditions and "required_documents" in best_rule.conditions:
            required_docs = best_rule.conditions["required_documents"]
        missing_docs = [doc for doc in required_docs if doc not in case.documents]
        if missing_docs:
            docs_str = ", ".join(missing_docs)
            sentence = f"Required document ({docs_str}) is missing for {item_display}."
            action = f"Attach {docs_str} before submitting."
            why = f"Policy {best_rule.rule_id} mandates attachment of clinical documentation ({docs_str}) to justify medical necessity."
            return ItemVerdict(
                item=item,
                result="Document missing",
                rule_id=best_rule.rule_id,
                rule_version=best_rule.version,
                effective_date=eff_str,
                plain_sentence=sentence,
                rule_reference=rule_ref,
                what_to_do=action,
                full_issue_text=f"{sentence} {rule_ref} {action}",
                source_title=src_title,
                source_url=src_url,
                why_not_approved=why,
                bulletin_summary=b_summary,
                action_guidance=guidance or [f"Obtain {docs_str} from medical records department and attach to claim file."],
            )

    # 5. Covered
    sentence = f"{item_display} is covered under current policy."
    action = "File is ready to submit."
    return ItemVerdict(
        item=item,
        result="Covered",
        rule_id=best_rule.rule_id,
        rule_version=best_rule.version,
        effective_date=eff_str,
        plain_sentence=sentence,
        rule_reference=rule_ref,
        what_to_do=action,
        full_issue_text=f"{sentence} {rule_ref} {action}",
        source_title=src_title,
        source_url=src_url,
        bulletin_summary=b_summary,
        action_guidance=guidance or ["Clean claim: ready for electronic clearinghouse submission."],
    )


def evaluate_case(
    case: Case,
    rules: List[Rule],
    governing_date: Optional[date] = None,
) -> CaseCheckResult:
    """Evaluate entire case and return CaseCheckResult with plain status."""
    target_date = governing_date or case.service_date
    item_verdicts: List[ItemVerdict] = []

    # Check if core fields are missing or wrong
    if not case.service_date or not case.insurer_id or not case.plan_id:
        return CaseCheckResult(
            case_id=case.case_id,
            specialty=case.specialty,
            status="Missing or wrong info",
            items_count=len(case.items),
            results=[
                ItemVerdict(
                    item=CaseItem(type="case", code="INFO", name="Patient Record"),
                    result="Value wrong",
                    rule_id="R-100",
                    rule_version=1,
                    effective_date="1 Jan 2026",
                    plain_sentence="Patient service date or insurer plan reference is missing or wrong.",
                    rule_reference="Rule R-100.",
                    what_to_do="Review and correct patient record values before submitting.",
                    full_issue_text="Patient service date or insurer plan reference is missing or wrong. Rule R-100. Review and correct patient record values before submitting.",
                )
            ],
        )

    for item in case.items:
        verdict = check_item(item, case, rules, target_date)
        item_verdicts.append(verdict)

    # Determine overall case status:
    # "Approved" | "Needs attention" | "Missing or wrong info"
    has_missing_or_wrong = any(
        v.result in ["Document missing", "Value wrong", "No rule found, verify with the insurer"]
        for v in item_verdicts
    )
    has_needs_attention = any(
        v.result in ["Not covered", "Prior approval needed"]
        for v in item_verdicts
    )

    if has_missing_or_wrong:
        overall_status: CaseStatusType = "Missing or wrong info"
    elif has_needs_attention:
        overall_status: CaseStatusType = "Needs attention"
    else:
        overall_status: CaseStatusType = "Approved"

    return CaseCheckResult(
        case_id=case.case_id,
        specialty=case.specialty,
        status=overall_status,
        items_count=len(case.items),
        results=item_verdicts,
    )
