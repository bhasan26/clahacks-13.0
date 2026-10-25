"""Hospital-side findings. Never a claim approval, denial, submission or payment promise."""

from datetime import timedelta
from app.domain.models import utc_now
from app.engine.checker import evaluate_case
from app.engine.matcher import normalize_insurer_id


def claim_findings(case, db):
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
    for verdict in evaluation.results:
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
                "follow_up": verdict.what_to_do,
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
        "status": status,
        "policy_environment": case.policy_environment,
        "is_synthetic_patient": case.is_synthetic,
        "issues_count": len(issues),
        "findings": records,
        "coverage_gaps": list(dict.fromkeys(gaps)),
        "checked_at": utc_now(),
        "notice": "Findings for employee review only. CoverageGuard does not approve, deny, alter or submit claims and cannot guarantee payment.",
    }
