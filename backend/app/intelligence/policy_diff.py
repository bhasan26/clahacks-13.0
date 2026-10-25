"""
Policy Difference Engine for CoverageGuard Policy Intelligence.
Compares proposed policy changes against currently approved rules in the database,
identifying coverage restrictions, delayed dates, cancellations, and documentation updates.
"""

from typing import List, Optional, Tuple
from datetime import date
from app.domain.models import ProposedPolicyChange, PolicyDiff, Rule, RuleEffect
from app.db.store import store
from app.engine.matcher import match_proposal_to_rule
from app.intelligence.rule_builder import find_prior


def find_matching_existing_rule(
    proposal: ProposedPolicyChange,
    all_rules: List[Rule],
) -> Optional[Rule]:
    """
    Finds the active baseline or prior version of the rule matching insurer,
    plan, item target type and code using strict matching.
    """
    return find_prior(proposal, all_rules)


def compute_policy_diff(
    proposal: ProposedPolicyChange,
    all_rules: Optional[List[Rule]] = None,
) -> PolicyDiff:
    """
    Compares the proposed policy change with the active rule store.
    """
    if all_rules is None:
        all_rules = list(store.rules.values())

    try:
        prior_rule = find_matching_existing_rule(proposal, all_rules)
    except ValueError as exc:
        return PolicyDiff(proposal_id=proposal.proposal_id, has_existing_rule=False,
                          proposed_effect=proposal.proposed_effect.value if proposal.proposed_effect else None,
                          diff_summary=str(exc), change_category="needs_clarification")

    if not prior_rule:
        return PolicyDiff(
            proposal_id=proposal.proposal_id,
            has_existing_rule=False,
            existing_rule_id=None,
            existing_rule_version=None,
            previous_effect=None,
            proposed_effect=proposal.proposed_effect.value if proposal.proposed_effect else "pending_review",
            previous_effective_from=None,
            proposed_effective_from=str(proposal.effective_from) if proposal.effective_from else None,
            is_delay=False,
            is_cancellation=False,
            diff_summary=f"Proposed policy: {proposal.target_name or proposal.target_code or 'Unspecified'} ({proposal.proposed_effect.value if proposal.proposed_effect else 'unknown effect'}) effective {proposal.effective_from or 'unknown date'}. Scope and evidence require human review.",
            change_category="new_rule",
        )

    # Prior rule found - analyze difference
    prev_eff = prior_rule.effect.value
    new_eff = proposal.proposed_effect.value if proposal.proposed_effect else "pending_review"
    prev_date = prior_rule.effective_from
    new_date = proposal.effective_from

    is_delay = False
    is_cancellation = proposal.change_type == "cancelled"

    # Check if effective date was postponed
    if new_date and prev_date and new_date > prev_date:
        is_delay = True
    elif proposal.change_type == "delayed":
        is_delay = True

    # Build plain summary
    if is_delay:
        diff_summary = (
            f"Coverage Delay Detected: {proposal.target_name or proposal.target_code} "
            f"exclusion postponed from {prev_date} to {new_date}. "
            f"Claims must be re-evaluated against all remaining rules."
        )
        category = "delayed"
    elif is_cancellation:
        diff_summary = (
            f"Policy Cancellation: Rule {prior_rule.rule_id} cancelled. "
            f"Re-evaluate {proposal.target_name or proposal.target_code} against all remaining rules."
        )
        category = "cancelled"
    elif prev_eff != new_eff:
        diff_summary = (
            f"Coverage Change Detected: "
            f"Previous: {prev_eff.replace('_', ' ').title()} -> Proposed: {new_eff.replace('_', ' ').title()} "
            f"effective {new_date} (Rule {prior_rule.rule_id} v{prior_rule.version} -> v{prior_rule.version + 1})."
        )
        category = "coverage_restriction" if new_eff == "excluded" else "modification"
    else:
        diff_summary = (
            f"Policy Clarification: {proposal.target_name or proposal.target_code} "
            f"updated terms effective {new_date} under Rule {prior_rule.rule_id}."
        )
        category = "criteria_update"

    return PolicyDiff(
        proposal_id=proposal.proposal_id,
        has_existing_rule=True,
        existing_rule_id=prior_rule.rule_id,
        existing_rule_version=prior_rule.version,
        previous_effect=prev_eff,
        proposed_effect=new_eff,
        previous_effective_from=str(prev_date) if prev_date else None,
        proposed_effective_from=str(new_date) if new_date else None,
        is_delay=is_delay,
        is_cancellation=is_cancellation,
        diff_summary=diff_summary,
        change_category=category,
    )
