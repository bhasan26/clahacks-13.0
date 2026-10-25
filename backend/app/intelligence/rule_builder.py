"""One proposal-to-rule path for previews and approvals. No persistence here."""
from typing import List, Optional
from hashlib import sha256

from app.domain.models import ProposedPolicyChange, Rule, RuleStatus, Target
from app.engine.matcher import normalize_insurer_id, match_proposal_to_rule


def missing_required_fields(p: ProposedPolicyChange) -> List[str]:
    missing = []
    if normalize_insurer_id(p.insurer_id) in {"", "*", "unknown", "none", "unverified"}:
        missing.append("insurer_id")
    if not p.plan_ids or any(not x.strip() or x.lower() in {"unknown", "none"} for x in p.plan_ids):
        missing.append("plan_ids")
    for field in ("target_type", "target_code", "proposed_effect", "effective_from"):
        if not getattr(p, field):
            missing.append(field)
    if not p.supporting_quote.strip():
        missing.append("supporting_quote")
    if p.extraction_method and not (p.evidence_verified or p.evidence_confirmed_by_reviewer):
        missing.append("verified_evidence")
    if p.effective_from and p.effective_to and p.effective_to <= p.effective_from:
        missing.append("valid_effective_range")
    if p.proposed_effect and p.proposed_effect.value == "requires_documents" and not (p.conditions or {}).get("required_documents"):
        missing.append("required_documents")
    return missing


def find_prior(p: ProposedPolicyChange, rules: List[Rule]) -> Optional[Rule]:
    matches = [r for r in rules if match_proposal_to_rule(p, r)]
    if p.policy_reference:
        exact = [r for r in matches if r.rule_id == p.policy_reference]
        if exact:
            matches = exact
        elif p.change_type == "new_rule":
            return None
        elif matches:
            raise ValueError("The policy_reference does not identify an existing rule. Confirm the exact rule reference.")
    identities = {r.rule_id for r in matches}
    if len(identities) > 1:
        raise ValueError("Multiple rules match this scope. Specify the exact policy_reference before approval.")
    return max(matches, key=lambda r: r.version) if matches else None


def build_proposed_rule(p: ProposedPolicyChange, rules: List[Rule]) -> Rule:
    missing = missing_required_fields(p)
    if missing:
        raise ValueError(f"Cannot approve incomplete proposal. Missing mandatory fields: {', '.join(missing)}")
    prior = find_prior(p, rules)
    if p.change_type in {"delayed", "cancelled"} and not prior:
        raise ValueError("A delay or cancellation must identify an existing rule with the same insurer, plans, type and code.")
    rule_id = prior.rule_id if prior else p.policy_reference or f"R-{p.proposal_id}"
    if not prior and any(r.rule_id == rule_id for r in rules):
        # Official references can repeat across plans/targets. Never overwrite them.
        scope = f"{p.insurer_id}|{sorted(p.plan_ids)}|{p.target_type}|{p.target_code}"
        rule_id = f"{rule_id}-{sha256(scope.encode()).hexdigest()[:8].upper()}"
    return Rule(
        rule_id=rule_id, version=prior.version + 1 if prior else 1,
        insurer_id=normalize_insurer_id(p.insurer_id), plan_ids=p.plan_ids,
        category=p.target_type, target=Target(type=p.target_type, code=p.target_code.strip().upper(), name=p.target_name),
        effect=p.proposed_effect, conditions=p.conditions if p.conditions is not None else prior.conditions if prior and p.change_type in {"delayed", "cancelled"} else None,
        status=RuleStatus.CANCELLED if p.change_type == "cancelled" else RuleStatus.EFFECTIVE,
        effective_from=p.effective_from, effective_to=p.effective_to,
        source_ref=f"approved-doc:{p.document_id}", source_title=p.policy_title,
        source_url=p.source_url, official_reference_url=p.source_url,
        bulletin_summary=p.supporting_quote,
        change_type=p.change_type,
        replaces_version=prior.version if prior and p.change_type in {"delayed", "cancelled"} else None,
        is_synthetic=p.is_synthetic,
    )
