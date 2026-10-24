"""
Unit Tests for CoverageGuard Deterministic Check Engine.
Verifies:
1. Baseline statuses: Approved, Needs attention, Missing or wrong info.
2. Temporal validity (service date before vs after effective_from).
3. Plain issue sentence formatting: plain statement, rule reference, what to do.
4. "No rule found, verify with the insurer".
"""

from datetime import date
from app.db.store import store
from app.domain.models import Case, CaseItem, Rule, RuleCategory, RuleEffect, RuleStatus, Target
from app.engine.checker import evaluate_case


def test_baseline_case_evaluations():
    store.reset_demo_state()
    rules = list(store.rules.values())

    # Case C-001 (Drug A on Nov 10, 2026): Initially Approved & Covered
    c1 = store.cases["C-001"]
    r1 = evaluate_case(c1, rules)
    assert r1.status == "Approved"
    assert r1.results[0].result == "Covered"

    # Case C-003 (PROC-1 on Nov 5, 2026 without PA): Needs attention & Prior approval needed
    c3 = store.cases["C-003"]
    r3 = evaluate_case(c3, rules)
    assert r3.status == "Needs attention"
    assert r3.results[0].result == "Prior approval needed"
    assert "Rule R-202" in r3.results[0].rule_reference

    # Case C-019 (BIO-TARGET without required genetics report): Missing or wrong info
    c19 = store.cases["C-019"]
    r19 = evaluate_case(c19, rules)
    assert r19.status == "Missing or wrong info"
    assert r19.results[0].result == "Document missing"


def test_temporal_boundary_and_plain_issue_sentence():
    store.reset_demo_state()

    # Publish rule excluding Drug A starting Nov 1, 2026
    r_ex = Rule(
        rule_id="R-1042",
        version=2,
        insurer_id="demo-insurer",
        plan_ids=["*"],
        category=RuleCategory.DRUG,
        target=Target(type="drug", code="DRUG-A", name="Drug A"),
        effect=RuleEffect.EXCLUDED,
        status=RuleStatus.EFFECTIVE,
        effective_from=date(2026, 11, 1),
        source_ref="insurer-rules:formulary-v2",
    )
    rules_with_ex = list(store.rules.values()) + [r_ex]

    # C-001 (Service date Nov 10, 2026): After Nov 1 -> Not covered
    c1 = store.cases["C-001"]
    res1 = evaluate_case(c1, rules_with_ex)
    assert res1.status == "Needs attention"
    assert res1.results[0].result == "Not covered"

    # Verify plain sentence, rule reference, and action format:
    # "Drug X is not covered from 1 Nov 2026. Rule R-1042. Review with the physician before submitting."
    verdict = res1.results[0]
    assert "Drug A is not covered from 1 Nov 2026." in verdict.plain_sentence
    assert "Rule R-1042." in verdict.rule_reference
    assert "Review with the physician before submitting." in verdict.what_to_do
    assert verdict.full_issue_text == f"{verdict.plain_sentence} {verdict.rule_reference} {verdict.what_to_do}"

    # C-002 (Service date Oct 28, 2026): Prior to Nov 1 -> Remains Covered
    c2 = store.cases["C-002"]
    res2 = evaluate_case(c2, rules_with_ex)
    assert res2.status == "Approved"
    assert res2.results[0].result == "Covered"


def test_no_matching_rule_behavior():
    store.reset_demo_state()
    rules = list(store.rules.values())

    # Case C-004 has Acupuncture Therapy (SVC-9), which has no rule in the catalog
    c4 = store.cases["C-004"]
    res4 = evaluate_case(c4, rules)
    assert res4.status == "Missing or wrong info"
    assert res4.results[0].result == "No rule found, verify with the insurer"
    assert "verify with the insurer" in res4.results[0].what_to_do
