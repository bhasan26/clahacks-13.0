"""
Deterministic Check Engine for CoverageGuard.
Pure function: evaluate_case(case, rules, governing_date) -> CaseCheckResult
Produces plain wording per specification:
- Statuses: Approved, Needs attention, Missing or wrong info
- Item Results: Covered, Not covered, Prior approval needed, Document missing, Value wrong, No rule found, verify with the insurer
- Each issue gets: one plain sentence, rule reference, what to do.
- Agent only notifies; never edits, rejects, or submits, and never suggests a medical alternative.
"""

from datetime import date, datetime
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
        return "Unknown effective date"
    return d.strftime("%-d %b %Y")


from app.engine.matcher import match_insurer, match_plan, match_item_code, normalize_insurer_id, match_jurisdiction


def normalize_insurer(ins: Optional[str]) -> str:
    return normalize_insurer_id(ins)


def codes_match(target_code: str, item_code: str, item_name: Optional[str] = None) -> bool:
    return match_item_code(target_code, item_code)


def rules_for_date(rules: List[Rule], service_date: date) -> List[Rule]:
    """Resolve revision chains without modifying stored historical versions.

    Delays withdraw the superseded schedule. Cancellations withdraw it from their
    stated effective date. Older independent coverage remains available.
    """
    suppressed = set()
    by_key = {(r.rule_id, r.version): r for r in rules}
    for r in rules:
        if r.change_type == "delayed" or (r.change_type == "cancelled" and service_date >= r.effective_from):
            version = r.replaces_version
            while version is not None:
                key = (r.rule_id, version)
                suppressed.add(key)
                previous = by_key.get(key)
                version = previous.replaces_version if previous else None
    candidates = [r for r in rules if (r.rule_id, r.version) not in suppressed
                  and r.status not in {RuleStatus.CANCELLED, RuleStatus.SUPERSEDED}
                  and r.effective_from <= service_date
                  and (r.effective_to is None or service_date < r.effective_to)]
    latest = {}
    for r in candidates:
        # Version precedence is per rule identity, never across unrelated policies.
        key = (r.rule_id, normalize_insurer_id(r.insurer_id), tuple(sorted(r.plan_ids)), r.target.type, r.target.code)
        if key not in latest or r.version > latest[key].version:
            latest[key] = r
    return list(latest.values())


def is_rule_applicable(
    rule: Rule,
    insurer_id: str,
    plan_id: str,
    item: CaseItem,
    governing_date: date,
) -> bool:
    """Check if a rule version applies to an item on governing_date."""
    if not match_insurer(rule.insurer_id, insurer_id) or not match_plan(rule.plan_ids, plan_id):
        return False
    if rule.target.type != item.type or not codes_match(rule.target.code, item.code):
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
        and not (case.policy_environment == "official" and normalize_insurer_id(case.insurer_id) == "bcbs")
        and r.scope_verified and r.verification_status == "approved"
        and match_jurisdiction(r.jurisdictions, case.jurisdiction)
        and (not r.target.code_system or r.target.code_system == item.code_system)
        and (case.policy_environment == "demo" or not r.is_synthetic)
    ]

    best_rule, has_conflict = select_best_rule(applicable_rules, case.plan_id)

    # 1. No rule found
    if not best_rule or has_conflict:
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
    official_ref = best_rule.official_reference_url
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
            official_reference_url=official_ref,
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
                official_reference_url=official_ref,
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
                official_reference_url=official_ref,
                why_not_approved=why,
                bulletin_summary=b_summary,
                action_guidance=guidance or [f"Obtain {docs_str} from medical records department and attach to claim file."],
            )

    unsupported=set((best_rule.conditions or {})) - {"requires_prior_approval", "required_documents"}
    if unsupported or (best_rule.effect == RuleEffect.REQUIRES_DOCUMENTS and not (best_rule.conditions or {}).get("required_documents")):
        sentence=f"{item_display} has policy conditions that require employee verification."
        action="Verify the remaining clinical/benefit criteria against the source; do not assume coverage."
        return ItemVerdict(item=item,result="Value wrong",rule_id=best_rule.rule_id,rule_version=best_rule.version,
            effective_date=eff_str,plain_sentence=sentence,rule_reference=rule_ref,what_to_do=action,
            full_issue_text=f"{sentence} {rule_ref} {action}",source_title=src_title,source_url=src_url,
            official_reference_url=official_ref,bulletin_summary=b_summary,action_guidance=[action])

    # 5. Covered
    sentence = f"{item_display} is covered under current policy."
    action = "No issue detected under this checked rule. Staff must review the complete claim before submission."
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
        official_reference_url=official_ref,
        bulletin_summary=b_summary,
        action_guidance=guidance or ["Review all checked rules and member benefits; this is not a payment guarantee."],
    )


def evaluate_case(
    case: Case,
    rules: List[Rule],
    governing_date: Optional[date] = None,
    as_of: Optional["datetime"] = None,
) -> CaseCheckResult:
    """Evaluate entire case and return CaseCheckResult with plain status."""
    target_date = governing_date or case.service_date
    item_verdicts: List[ItemVerdict] = []
    known_rules = [r for r in rules if as_of is None or r.received_at <= as_of]
    rules = rules_for_date(known_rules, target_date) if target_date else []

    # Check if core fields are missing or wrong
    if not case.service_date or not case.insurer_id or not case.plan_id or not case.items:
        return CaseCheckResult(
            case_id=case.case_id,
            specialty=case.specialty,
            status="Missing or wrong info",
            items_count=len(case.items),
            results=[
                ItemVerdict(
                    item=CaseItem(type="case", code="INFO", name="Patient Record"),
                    result="Value wrong",
                    rule_id=None,
                    rule_version=None,
                    effective_date=None,
                    plain_sentence="Patient service date or insurer plan reference is missing or wrong.",
                    rule_reference="Patient record validation.",
                    what_to_do="Review and correct patient record values before submitting.",
                    full_issue_text="Patient service date or insurer plan reference is missing or wrong. Review and correct patient record values before submitting.",
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
