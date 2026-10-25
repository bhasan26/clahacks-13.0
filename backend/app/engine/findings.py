"""Hospital-side findings. Never a claim approval, denial, submission or payment promise."""

from datetime import timedelta
from app.domain.models import is_uploaded_case, utc_now
from app.engine.checker import evaluate_case
from app.engine.matcher import (
    match_code_system,
    match_insurer,
    match_item_code,
    match_jurisdiction,
    match_plan,
    normalize_insurer_id,
)

PENDING_REVIEW_STATES = {"pending_review", "needs_correction"}


def pending_policy_changes(case, item, db):
    """Detected policy changes for this item that a reviewer has not approved yet.

    They never change the finding; they warn that the approved rule may be outdated.
    Scope is matched leniently where the proposal is still incomplete (no plan or
    code system yet) because missing a real change costs more than an extra warning.
    """
    changes = []
    for p in db.proposals.values():
        if p.review_state not in PENDING_REVIEW_STATES:
            continue
        if p.is_synthetic and case.policy_environment != "demo":
            continue
        if not match_insurer(p.insurer_id, case.insurer_id):
            continue
        if p.plan_ids and not match_plan(p.plan_ids, case.plan_id):
            continue
        if p.target_type != item.type or not match_item_code(p.target_code, item.code):
            continue
        if p.code_system and not match_code_system(p.code_system, item.code_system):
            continue
        if not match_jurisdiction(p.jurisdictions, case.jurisdiction):
            continue
        changes.append(
            {
                "proposal_id": p.proposal_id,
                "policy_reference": p.policy_reference or p.policy_title,
                "change_type": p.change_type,
                "proposed_effect": p.proposed_effect.value if p.proposed_effect else None,
                "effective_from": p.effective_from,
                "detected_at": p.created_at,
                "is_synthetic": p.is_synthetic,
                "supporting_quote": p.supporting_quote[:300],
                "source_url": p.source_url,
            }
        )
    return sorted(changes, key=lambda c: c["detected_at"], reverse=True)


def eligible_policy_rules(case, db):
    eligible = []
    gaps = []
    for rule in db.get_all_rules():
        if case.policy_environment == "official" and rule.is_synthetic:
            continue
        if rule.catalog_id:
            catalog = db.policy_catalog.get(rule.catalog_id)
            if (
                not catalog
                or catalog.status
                in {
                    "extraction_failed",
                    "fetch_failed",
                    "access_restricted",
                    "not_in_latest_index",
                }
                or (
                    catalog.effective_to
                    and case.service_date
                    and case.service_date >= catalog.effective_to
                )
                or not catalog.last_successful_sync
                or utc_now() - catalog.last_successful_sync > timedelta(hours=48)
            ):
                if normalize_insurer_id(rule.insurer_id) == normalize_insurer_id(
                    case.insurer_id
                ):
                    gaps.append(
                        f"Policy {rule.rule_id} source is stale or has no successful sync."
                    )
                continue
        eligible.append(rule)
    return eligible, gaps


def policy_gap_reason(case, item, db):
    rules = [
        r
        for r in db.get_all_rules()
        if normalize_insurer_id(r.insurer_id) == normalize_insurer_id(case.insurer_id)
    ]
    environment = (
        "official" if case.policy_environment == "official" else "simulated or verified"
    )
    rules = [
        r for r in rules if case.policy_environment == "demo" or not r.is_synthetic
    ]
    if not rules:
        return f"No approved {environment} policy is available locally for insurer {case.insurer_id or '(missing)'}."
    from app.engine.matcher import match_plan, match_jurisdiction, match_item_code

    for predicate, reason in [
        (
            lambda r: r.scope_verified and r.verification_status == "approved",
            "Policy scope has not been verified and approved.",
        ),
        (
            lambda r: match_plan(r.plan_ids, case.plan_id),
            f"No approved policy matches exact plan {case.plan_id or '(missing)'}.",
        ),
        (
            lambda r: match_jurisdiction(r.jurisdictions, case.jurisdiction),
            f"No approved policy matches state/jurisdiction {case.jurisdiction or '(missing)'}.",
        ),
        (
            lambda r: (
                r.target.type == item.type and match_item_code(r.target.code, item.code)
            ),
            f"No approved policy matches {item.type} code {item.code or '(missing)'}.",
        ),
        (
            lambda r: match_code_system(r.target.code_system, item.code_system),
            f"No approved policy matches code system {item.code_system or '(missing)'}.",
        ),
    ]:
        rules = [r for r in rules if predicate(r)]
        if not rules:
            return reason
    return f"No current, fresh, unambiguous approved policy applies on service date {case.service_date or '(missing)'}. Check effective dates, source freshness and policy review status."


def _policy_checked_at(rule, db):
    """When the governing rule's source was last confirmed current."""
    if not rule:
        return None
    catalog = db.policy_catalog.get(rule.catalog_id) if rule.catalog_id else None
    return (catalog.last_successful_sync if catalog else None) or rule.source_synced_at


def claim_findings(case, db):
    eligible, gaps = eligible_policy_rules(case, db)
    evaluation = evaluate_case(case, eligible)
    unknown = any(
        v.result in {"Value wrong", "No rule found, verify with the insurer"}
        for v in evaluation.results
    )
    if not case.items or not case.member_ref:
        unknown = True
    issues = [v for v in evaluation.results if v.result != "Covered"]
    status = (
        "Unable to verify / insufficient policy information"
        if unknown
        else "Known coverage exclusion or unmet requirement"
        if issues
        else "No issue detected under verified checked rules"
    )
    if case.policy_environment == "demo":
        status = status.replace("verified checked rules", "SIMULATED checked rules")
    records = []
    pending_total = 0
    for verdict in evaluation.results:
        pending = pending_policy_changes(case, verdict.item, db)
        pending_total += len(pending)
        for change in pending:
            effect = (change["proposed_effect"] or change["change_type"]).replace("_", " ")
            gaps.append(
                f"Policy change detected {change['detected_at']:%d %b %Y} for {verdict.item.code}, awaiting review: "
                f"{effect}{' effective ' + format(change['effective_from'], '%d %b %Y') if change['effective_from'] else ''}. "
                "This claim may be affected; findings use the currently approved rule until the change is reviewed."
            )
        rule = next(
            (
                r
                for r in eligible
                if r.rule_id == verdict.rule_id and r.version == verdict.rule_version
            ),
            None,
        )
        records.append(
            {
                **verdict.model_dump(mode="json"),
                "policy_is_synthetic": rule.is_synthetic if rule else None,
                "policy_reference": verdict.rule_id,
                "policy_version": verdict.rule_version,
                "source_evidence": rule.bulletin_summary if rule else None,
                "source_url": rule.official_reference_url or rule.source_url
                if rule
                else None,
                "verification_status": rule.verification_status if rule else "unknown",
                "required_documents": (rule.conditions or {}).get(
                    "required_documents", []
                )
                if rule
                else [],
                "requires_prior_authorization": bool(
                    rule
                    and (
                        rule.effect.value == "requires_prior_approval"
                        or (rule.conditions or {}).get("requires_prior_approval")
                    )
                ),
                "missing_documents": [
                    doc
                    for doc in (rule.conditions or {}).get("required_documents", [])
                    if doc not in case.documents
                ]
                if rule
                else [],
                "prior_authorization_present": bool(case.prior_approval_ref),
                "prior_authorization_reference": case.prior_approval_ref,
                "policy_missing_reason": policy_gap_reason(case, verdict.item, db)
                if not rule
                else None,
                "follow_up": verdict.what_to_do,
                "pending_changes": pending,
                "policy_checked_at": _policy_checked_at(rule, db),
            }
        )
    if unknown:
        gaps.append(
            "Exact approved insurer, plan, jurisdiction, code and service-date policy evidence is missing. Request a targeted refresh or supply verified policy evidence."
        )
    if case.insurer_id == "bcbs":
        gaps.append(
            "BCBS affiliate is unknown. Specify the regional insurer and state; nationwide matching is not supported."
        )
    return {
        "case_id": case.case_id,
        "specialty": case.specialty,
        "engine_status": evaluation.status,
        "insurer_id": case.insurer_id,
        "insurer_name": case.insurer_name,
        "plan_id": case.plan_id,
        "jurisdiction": case.jurisdiction,
        "service_date": case.service_date,
        "member_ref": case.member_ref,
        "status": status,
        "policy_environment": case.policy_environment,
        "is_synthetic_patient": case.is_synthetic,
        "is_uploaded": is_uploaded_case(case),
        "issues_count": len(issues),
        "pending_changes_count": pending_total,
        "findings": records,
        "coverage_gaps": list(dict.fromkeys(gaps)),
        "checked_at": utc_now(),
        "notice": "Findings for employee review only. CoverageGuard does not approve, deny, alter or submit claims and cannot guarantee payment.",
    }
