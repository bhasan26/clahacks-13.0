"""
Golden Tests for CoverageGuard Engine, Rules Precedence, and Alert Lifecycles.
"""

from datetime import date, datetime
import pytest

from app.db.store import store
from app.domain.models import (
    CaseOverallStatus,
    Rule,
    RuleCategory,
    RuleEffect,
    RuleStatus,
    SeverityType,
    Target,
    VerdictType,
    utc_now,
)
from app.engine.checker import evaluate_case
from app.impact.analyzer import run_impact_analysis


def test_seed_cases_baseline_verdicts():
    store.reset_demo_state()
    rules = store.get_all_rules()

    # Case C-001 (DRUG-A on Nov 10, 2026): Should be CLEAR
    c1 = store.get_case("C-001")
    assert c1 is not None
    r1 = evaluate_case(c1, rules)
    assert r1.overall_status == CaseOverallStatus.CLEAR
    assert r1.results[0].verdict == VerdictType.COVERED

    # Case C-002 (DRUG-A on Oct 28, 2026): Should be CLEAR
    c2 = store.get_case("C-002")
    assert c2 is not None
    r2 = evaluate_case(c2, rules)
    assert r2.overall_status == CaseOverallStatus.CLEAR

    # Case C-003 (PROC-1 on Nov 5, 2026 without prior approval): Should be NEEDS_ATTENTION
    c3 = store.get_case("C-003")
    assert c3 is not None
    r3 = evaluate_case(c3, rules)
    assert r3.overall_status == CaseOverallStatus.NEEDS_ATTENTION
    assert r3.results[0].verdict == VerdictType.PRIOR_APPROVAL_NEEDED

    # Case C-004 (SVC-9 on Nov 6, 2026): Should be CANNOT_ASSESS
    c4 = store.get_case("C-004")
    assert c4 is not None
    r4 = evaluate_case(c4, rules)
    assert r4.overall_status == CaseOverallStatus.CANNOT_ASSESS
    assert r4.results[0].verdict == VerdictType.NO_RULE_FOUND


def test_rule_exclusion_and_impact_alerts():
    store.reset_demo_state()

    # 1. Initially no alerts
    assert len(store.alerts) == 0

    # 2. Insurer publishes R-101 v2: DRUG-A is EXCLUDED starting 2026-11-01
    r_excluded = Rule(
        rule_id="R-101",
        version=2,
        insurer_id="demo-insurer",
        plan_ids=["PLAN-GOLD"],
        category=RuleCategory.DRUG,
        target=Target(type="drug", code="DRUG-A", name="Drug A"),
        effect=RuleEffect.EXCLUDED,
        status=RuleStatus.EFFECTIVE,
        effective_from=date(2026, 11, 1),
        effective_to=None,
        source_ref="feed:evt-exclude-drug-a",
        received_at=utc_now(),
    )
    store.save_rule(r_excluded)

    # 3. Run impact analysis
    alerts = run_impact_analysis("Test exclusion")

    # Case C-001 (service_date Nov 10 >= Nov 1) MUST receive an alert
    c1_alerts = [a for a in store.alerts.values() if a.case_id == "C-001"]
    assert len(c1_alerts) == 1
    assert c1_alerts[0].status == "open"
    assert c1_alerts[0].item_code == "DRUG-A"

    # Case C-002 (service_date Oct 28 < Nov 1) must NOT receive an alert
    c2_alerts = [a for a in store.alerts.values() if a.case_id == "C-002"]
    assert len(c2_alerts) == 0


def test_rule_delay_auto_closes_alert():
    store.reset_demo_state()

    # First exclude DRUG-A
    r_excluded = Rule(
        rule_id="R-101",
        version=2,
        insurer_id="demo-insurer",
        plan_ids=["PLAN-GOLD"],
        category=RuleCategory.DRUG,
        target=Target(type="drug", code="DRUG-A", name="Drug A"),
        effect=RuleEffect.EXCLUDED,
        status=RuleStatus.EFFECTIVE,
        effective_from=date(2026, 11, 1),
        effective_to=None,
        source_ref="feed:evt-exclude-drug-a",
    )
    store.save_rule(r_excluded)
    run_impact_analysis("Test exclusion")

    alert = [a for a in store.alerts.values() if a.case_id == "C-001"][0]
    assert alert.status == "open"

    # Now insurer DELAYS rule R-101 to 2026-12-01 (past C-001's service date 2026-11-10)
    r_delayed = Rule(
        rule_id="R-101",
        version=3,
        insurer_id="demo-insurer",
        plan_ids=["PLAN-GOLD"],
        category=RuleCategory.DRUG,
        target=Target(type="drug", code="DRUG-A", name="Drug A"),
        effect=RuleEffect.EXCLUDED,
        status=RuleStatus.DELAYED,
        effective_from=date(2026, 12, 1),
        effective_to=None,
        source_ref="feed:evt-delay-drug-a",
    )
    store.save_rule(r_delayed)

    # Re-run impact analysis
    run_impact_analysis("Test delay")

    # Alert must now be CLOSED
    assert alert.status == "closed"
    assert "change delayed or cancelled" in (alert.closed_reason or "")
