"""
Shared Policy Matching Utility for CoverageGuard.
Ensures 100% consistent matching across:
- Policy comparison (policy_diff.py)
- What-If impact simulation (impact_previewer.py)
- Rule approval (store.py)
- Claim evaluation (checker.py)
- Alert generation (impact/analyzer.py)

STRICT ADJUDICATION RULES:
1. Insurer ID must match exactly or through an explicitly verified alias.
2. Plan ID must match exactly or through an approved wildcard ('*').
3. Item type must match ('drug', 'procedure', 'service').
4. Item code must match EXACTLY (no substring matches, no guessing by name similarity).
5. Effective date applicability check.
6. Superseded or historical rules must not override active versions.
"""

from datetime import date
from typing import Dict, List, Optional, Set, Any
from app.domain.models import Rule, RuleStatus, Case, CaseItem, ProposedPolicyChange

# Verified Insurer Identity Aliases
INSURER_ALIASES: Dict[str, Set[str]] = {
    "demo-insurer": {"demo-insurer", "demo_insurer", "demo", "demo-payer"},
    "uhc": {"uhc", "unitedhealthcare", "united_healthcare", "united-healthcare", "united health care"},
    "aetna": {"aetna", "aetna_health", "aetna-health", "aetna health"},
    "bcbs": {"bcbs", "blue_cross", "blue-cross", "blue cross blue shield", "blue cross"},
    "cigna": {"cigna", "cigna_healthcare", "cigna healthcare"},
    "cms": {"cms", "medicare", "centers for medicare & medicaid services"},
}


def normalize_insurer_id(insurer_id: Optional[str]) -> str:
    """Normalizes an insurer ID or string representation to a canonical key."""
    if not insurer_id:
        return ""
    clean = insurer_id.strip().lower()
    for canonical, aliases in INSURER_ALIASES.items():
        if clean == canonical or clean in aliases:
            return canonical
    return clean


def match_insurer(rule_or_proposal_insurer: Optional[str], target_insurer: Optional[str]) -> bool:
    """
    Checks if insurer IDs match.
    Wildcard '*' matches any insurer only when explicitly permitted.
    """
    norm_a = normalize_insurer_id(rule_or_proposal_insurer)
    norm_b = normalize_insurer_id(target_insurer)

    return bool(norm_a and norm_b and norm_a not in {"*", "unknown", "none"}
                and norm_b not in {"*", "unknown", "none"} and norm_a == norm_b)


def match_plan(rule_plan_ids: Optional[List[str]], claim_plan_id: Optional[str]) -> bool:
    """
    Checks if an insurance plan ID matches rule plan requirements.
    Plan IDs must match exactly, or match if the rule specifies wildcard '*'.
    """
    if not rule_plan_ids or not claim_plan_id or claim_plan_id.strip().upper() in {"", "*", "UNKNOWN", "NONE", "UNVERIFIED"}:
        return False
    if "*" in rule_plan_ids:
        return True

    clean_claim_plan = claim_plan_id.strip().upper()
    return clean_claim_plan in {p.strip().upper() for p in rule_plan_ids}


def normalize_code(code: Optional[str]) -> str:
    """Standardizes billing / procedure / drug codes (exact uppercase, stripped)."""
    if not code:
        return ""
    return str(code).strip().upper()


def match_item_code(code_a: Optional[str], code_b: Optional[str]) -> bool:
    """
    Strict exact matching for billing codes.
    NEVER uses substring matching (e.g. 'PROC-1' will not match 'PROC-10').
    """
    norm_a = normalize_code(code_a)
    norm_b = normalize_code(code_b)
    if not norm_a or not norm_b:
        return False
    return norm_a == norm_b


def is_rule_applicable_on_date(
    rule_or_from: Any,
    effective_to_or_check_date: Any,
    check_date: Optional[date] = None,
) -> bool:
    """Checks if a rule is in effect for a given service date."""
    if check_date is not None:
        rule_effective_from = rule_or_from
        rule_effective_to = effective_to_or_check_date
        target_date = check_date
    else:
        rule_effective_from = getattr(rule_or_from, "effective_from", None)
        rule_effective_to = getattr(rule_or_from, "effective_to", None)
        target_date = effective_to_or_check_date

    if not rule_effective_from or not target_date:
        return False
    if target_date < rule_effective_from:
        return False
    if rule_effective_to and target_date >= rule_effective_to:
        return False
    return True


def match_proposal_to_target(
    proposal: ProposedPolicyChange,
    insurer_id: Optional[str],
    plan_id: Optional[str],
    item_code: str,
    item_type: Optional[str] = None,
) -> bool:
    """Checks if proposal targets this item and insurer/plan without date evaluation."""
    if not proposal.target_code or not item_code:
        return False

    if not match_item_code(proposal.target_code, item_code):
        return False

    if not proposal.target_type or not item_type or proposal.target_type != item_type:
        return False

    if not match_insurer(proposal.insurer_id, insurer_id):
        return False

    if not match_plan(proposal.plan_ids, plan_id):
        return False

    return True


def match_proposal_to_claim_item(
    proposal: ProposedPolicyChange,
    case: Any,
    item: Any,
    governing_date: Optional[date] = None,
) -> bool:
    """
    Determines if a proposed policy change applies to a specific case item.
    Enforces all criteria:
    - Insurer match
    - Plan match
    - Item type match
    - Exact item code match
    - Service date applicability
    """
    if not proposal.target_code:
        return False

    # Extract fields whether case/item are objects or strings
    if hasattr(case, "insurer_id"):
        ins_id = case.insurer_id
        pln_id = getattr(case, "plan_id", "*")
        service_dt = governing_date or getattr(case, "service_date", None)
    else:
        ins_id = str(case) if case else None
        pln_id = None
        service_dt = governing_date

    if hasattr(item, "code"):
        it_code = item.code
        it_type = getattr(item, "type", None)
    else:
        it_code = str(item)
        it_type = None

    if not match_proposal_to_target(proposal, ins_id, pln_id, it_code, it_type):
        return False

    # Date check
    if not proposal.effective_from:
        return False
    if service_dt:
        if proposal.effective_from and service_dt < proposal.effective_from:
            return False
        if proposal.effective_to and service_dt > proposal.effective_to:
            return False

    return True


def match_proposal_to_rule(
    proposal: ProposedPolicyChange,
    rule: Rule,
) -> bool:
    """
    Determines if a proposal refers to an existing rule for versioning or diffing.
    Requires:
    - Insurer match
    - Exact target code match
    - Item type match
    """
    if not proposal.target_code:
        return False

    if not match_item_code(proposal.target_code, rule.target.code):
        return False

    if not proposal.target_type or proposal.target_type != rule.target.type:
        return False

    if not match_insurer(proposal.insurer_id, rule.insurer_id):
        return False

    # A scope change creates a separate rule; it cannot version another plan's rule.
    if not proposal.plan_ids or {p.strip().upper() for p in proposal.plan_ids} != {p.strip().upper() for p in rule.plan_ids}:
        return False

    return True
