"""
In-Memory / SQLite Repository Store with Initial Seed Data.
Includes reset_demo_state() for instant 1-click test and judge reset.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.domain.models import (
    Alert,
    AlertChange,
    AlertStatus,
    Case,
    CaseItem,
    Diagnosis,
    Rule,
    RuleCategory,
    RuleEffect,
    RuleStatus,
    Target,
    utc_now,
)


class DataStore:
    def __init__(self):
        self.rules: Dict[str, Rule] = {}  # key: f"{rule_id}_v{version}"
        self.cases: Dict[str, Case] = {}  # key: case_id
        self.alerts: Dict[str, Alert] = {}  # key: alert_id
        self.audit_log: List[dict] = []
        self.last_sync_time: datetime = utc_now()
        self.is_feed_outage_simulated: bool = False
        self.stale_threshold_seconds: int = 120  # For demo: 2 minutes is considered stale

        # Initialize with canonical hackathon seed data
        self.reset_demo_state()

    def record_audit(self, action: str, details: dict, actor: str = "system"):
        entry = {
            "entry_id": f"AUDIT-{len(self.audit_log) + 1:04d}",
            "timestamp": utc_now().isoformat(),
            "actor": actor,
            "action": action,
            "details": details,
        }
        self.audit_log.append(entry)
        return entry

    def reset_demo_state(self):
        """Resets the store back to canonical pre-demo initial state."""
        self.rules.clear()
        self.cases.clear()
        self.alerts.clear()
        self.audit_log.clear()
        self.is_feed_outage_simulated = False
        self.last_sync_time = utc_now()

        # Seed Rule 1: DRUG-A covered under PLAN-GOLD
        r1 = Rule(
            rule_id="R-101",
            version=1,
            insurer_id="demo-insurer",
            plan_ids=["PLAN-GOLD"],
            category=RuleCategory.DRUG,
            target=Target(type="drug", code="DRUG-A", name="Drug A"),
            effect=RuleEffect.COVERED,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            source_ref="feed:initial-seed",
            received_at=utc_now() - timedelta(days=10),
        )
        self.rules[f"{r1.rule_id}_v{r1.version}"] = r1

        # Seed Rule 2: PROC-1 requires prior approval
        r2 = Rule(
            rule_id="R-202",
            version=1,
            insurer_id="demo-insurer",
            plan_ids=["*"],
            category=RuleCategory.PROCEDURE,
            target=Target(type="procedure", code="PROC-1", name="Major Joint Procedure"),
            effect=RuleEffect.REQUIRES_PRIOR_APPROVAL,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            source_ref="feed:initial-seed",
            received_at=utc_now() - timedelta(days=10),
        )
        self.rules[f"{r2.rule_id}_v{r2.version}"] = r2

        # Seed Rule 3: DRUG-B covered (Cardiovascular care)
        r3 = Rule(
            rule_id="R-301",
            version=1,
            insurer_id="demo-insurer",
            plan_ids=["*"],
            category=RuleCategory.DRUG,
            target=Target(type="drug", code="DRUG-B", name="Drug B (Cardiovascular)"),
            effect=RuleEffect.COVERED,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            source_ref="feed:initial-seed",
            received_at=utc_now() - timedelta(days=10),
        )
        self.rules[f"{r3.rule_id}_v{r3.version}"] = r3

        # Seed Rule 4: STD-CARE covered (Standard Consultation & Labs)
        r4 = Rule(
            rule_id="R-300",
            version=1,
            insurer_id="demo-insurer",
            plan_ids=["*"],
            category=RuleCategory.SERVICE,
            target=Target(type="service", code="STD-CARE", name="Standard Care Protocol"),
            effect=RuleEffect.COVERED,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            source_ref="feed:initial-seed",
            received_at=utc_now() - timedelta(days=10),
        )
        self.rules[f"{r4.rule_id}_v{r4.version}"] = r4

        # Seed 4 Canonical Cases from project.md
        # C-001: DRUG-A, Service Date Nov 10, 2026 (Clear initially)
        c1 = Case(
            case_id="C-001",
            insurer_id="demo-insurer",
            plan_id="PLAN-GOLD",
            member_ref="M-5f3a",
            service_date=date(2026, 11, 10),
            visit_type="outpatient",
            diagnoses=[Diagnosis(code="DX-100", description="Rheumatoid arthritis")],
            items=[CaseItem(type="drug", code="DRUG-A", name="Drug A", quantity=30)],
            documents=[],
            prior_approval_ref=None,
            status="open",
            officer_id="officer-1",
        )
        self.cases[c1.case_id] = c1

        # C-002: DRUG-A, Service Date Oct 28, 2026 (Clear initially & after Nov 1 rule change)
        c2 = Case(
            case_id="C-002",
            insurer_id="demo-insurer",
            plan_id="PLAN-GOLD",
            member_ref="M-8b1c",
            service_date=date(2026, 10, 28),
            visit_type="outpatient",
            diagnoses=[Diagnosis(code="DX-100", description="Rheumatoid arthritis")],
            items=[CaseItem(type="drug", code="DRUG-A", name="Drug A", quantity=15)],
            documents=[],
            prior_approval_ref=None,
            status="open",
            officer_id="officer-1",
        )
        self.cases[c2.case_id] = c2

        # C-003: PROC-1, Service Date Nov 5, 2026 (Needs attention: Prior approval missing)
        c3 = Case(
            case_id="C-003",
            insurer_id="demo-insurer",
            plan_id="PLAN-GOLD",
            member_ref="M-99c2",
            service_date=date(2026, 11, 5),
            visit_type="outpatient",
            diagnoses=[Diagnosis(code="DX-201", description="Severe osteoarthritis")],
            items=[CaseItem(type="procedure", code="PROC-1", name="Major Joint Procedure", quantity=1)],
            documents=[],
            prior_approval_ref=None,
            status="open",
            officer_id="officer-1",
        )
        self.cases[c3.case_id] = c3

        # C-004: SVC-9, Service Date Nov 6, 2026 (Cannot assess: No rule found)
        c4 = Case(
            case_id="C-004",
            insurer_id="demo-insurer",
            plan_id="PLAN-GOLD",
            member_ref="M-120d",
            service_date=date(2026, 11, 6),
            visit_type="outpatient",
            diagnoses=[Diagnosis(code="DX-305", description="Chronic back pain")],
            items=[CaseItem(type="service", code="SVC-9", name="Acupuncture Therapy", quantity=5)],
            documents=[],
            prior_approval_ref=None,
            status="open",
            officer_id="officer-1",
        )
        self.cases[c4.case_id] = c4

        # Seed additional realistic hospital caseload (Total 30 claims)
        # C-005 & C-008: Also on DRUG-A with service dates in November (affected by Nov 1 rule change)
        c5 = Case(
            case_id="C-005",
            insurer_id="demo-insurer",
            plan_id="PLAN-GOLD",
            member_ref="M-55a1",
            service_date=date(2026, 11, 14),
            visit_type="outpatient",
            diagnoses=[Diagnosis(code="DX-100", description="Rheumatoid arthritis")],
            items=[CaseItem(type="drug", code="DRUG-A", name="Drug A", quantity=30)],
            documents=[],
            prior_approval_ref=None,
            status="open",
            officer_id="officer-1",
        )
        self.cases[c5.case_id] = c5

        c8 = Case(
            case_id="C-008",
            insurer_id="demo-insurer",
            plan_id="PLAN-GOLD",
            member_ref="M-88c4",
            service_date=date(2026, 11, 20),
            visit_type="outpatient",
            diagnoses=[Diagnosis(code="DX-100", description="Rheumatoid arthritis flare")],
            items=[CaseItem(type="drug", code="DRUG-A", name="Drug A", quantity=30)],
            documents=[],
            prior_approval_ref=None,
            status="open",
            officer_id="officer-1",
        )
        self.cases[c8.case_id] = c8

        # Cases C-006, C-007, C-009 through C-030: Routine Cardiovascular (DRUG-B) and Standard Care (STD-CARE)
        other_cases = [
            ("C-006", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Essential hypertension", date(2026, 11, 2)),
            ("C-007", "STD-CARE", "Standard Care Protocol", "service", "DX-500", "Annual medical examination", date(2026, 11, 3)),
            ("C-009", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Hypertension stage 2", date(2026, 11, 4)),
            ("C-010", "STD-CARE", "Standard Care Protocol", "service", "DX-502", "Routine post-op checkup", date(2026, 11, 5)),
            ("C-011", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-402", "Hyperlipidemia management", date(2026, 11, 6)),
            ("C-012", "STD-CARE", "Standard Care Protocol", "service", "DX-505", "General wellness exam", date(2026, 11, 7)),
            ("C-013", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Essential hypertension", date(2026, 11, 8)),
            ("C-014", "STD-CARE", "Standard Care Protocol", "service", "DX-510", "Endocrine consultation", date(2026, 11, 9)),
            ("C-015", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-403", "Cardiovascular prevention", date(2026, 11, 10)),
            ("C-016", "STD-CARE", "Standard Care Protocol", "service", "DX-512", "Dermatology screening", date(2026, 11, 11)),
            ("C-017", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Hypertension follow-up", date(2026, 11, 12)),
            ("C-018", "STD-CARE", "Standard Care Protocol", "service", "DX-515", "Comprehensive metabolic panel", date(2026, 11, 13)),
            ("C-019", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-402", "Lipid control protocol", date(2026, 11, 14)),
            ("C-020", "STD-CARE", "Standard Care Protocol", "service", "DX-520", "Pulmonary function review", date(2026, 11, 15)),
            ("C-021", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Cardiology outpatient visit", date(2026, 11, 16)),
            ("C-022", "STD-CARE", "Standard Care Protocol", "service", "DX-525", "Ophthalmology clearance", date(2026, 11, 17)),
            ("C-023", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-403", "Coronary risk reduction", date(2026, 11, 18)),
            ("C-024", "STD-CARE", "Standard Care Protocol", "service", "DX-530", "Gastroenterology consult", date(2026, 11, 19)),
            ("C-025", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Blood pressure monitoring", date(2026, 11, 20)),
            ("C-026", "STD-CARE", "Standard Care Protocol", "service", "DX-535", "Preventive health screening", date(2026, 11, 21)),
            ("C-027", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-402", "Dyslipidemia review", date(2026, 11, 22)),
            ("C-028", "STD-CARE", "Standard Care Protocol", "service", "DX-540", "ENT routine evaluation", date(2026, 11, 23)),
            ("C-029", "DRUG-B", "Drug B (Cardiovascular)", "drug", "DX-401", "Hypertension routine visit", date(2026, 11, 24)),
            ("C-030", "STD-CARE", "Standard Care Protocol", "service", "DX-545", "Adult immunization consult", date(2026, 11, 25)),
        ]

        for cid, item_code, item_name, item_type, dx_code, dx_desc, svc_date in other_cases:
            c_other = Case(
                case_id=cid,
                insurer_id="demo-insurer",
                plan_id="PLAN-GOLD",
                member_ref=f"M-{cid.lower()}",
                service_date=svc_date,
                visit_type="outpatient",
                diagnoses=[Diagnosis(code=dx_code, description=dx_desc)],
                items=[CaseItem(type=item_type, code=item_code, name=item_name, quantity=1)],
                documents=[],
                prior_approval_ref=None,
                status="open",
                officer_id="officer-1",
            )
            self.cases[cid] = c_other

        self.record_audit(
            action="RESET_DEMO_STATE",
            details={"rules_count": len(self.rules), "cases_count": len(self.cases)},
            actor="admin",
        )

    def get_all_rules(self) -> List[Rule]:
        return list(self.rules.values())

    def get_latest_rules(self) -> List[Rule]:
        """Returns the latest version of each rule_id."""
        latest: Dict[str, Rule] = {}
        for r in self.rules.values():
            if r.rule_id not in latest or r.version > latest[r.rule_id].version:
                latest[r.rule_id] = r
        return list(latest.values())

    def get_all_cases(self) -> List[Case]:
        return list(self.cases.values())

    def get_case(self, case_id: str) -> Optional[Case]:
        return self.cases.get(case_id)

    def save_case(self, case: Case):
        self.cases[case.case_id] = case
        self.record_audit("SAVE_CASE", {"case_id": case.case_id})

    def save_rule(self, rule: Rule):
        """
        Saves a rule version and manages lifecycle transitions:
        When a new version for rule_id is published:
        - If delayed or cancelled, the specific version being delayed or cancelled (version - 1) is superseded.
        """
        if rule.status in [RuleStatus.DELAYED, RuleStatus.CANCELLED]:
            target_v = rule.version - 1
            for existing in self.rules.values():
                if existing.rule_id == rule.rule_id and existing.version == target_v:
                    existing.status = (
                        RuleStatus.CANCELLED
                        if rule.status == RuleStatus.CANCELLED
                        else RuleStatus.SUPERSEDED
                    )

        key = f"{rule.rule_id}_v{rule.version}"
        self.rules[key] = rule
        self.record_audit(
            "SAVE_RULE",
            {
                "rule_id": rule.rule_id,
                "version": rule.version,
                "effect": rule.effect,
                "status": rule.status,
                "effective_from": str(rule.effective_from),
            },
        )

    def get_all_alerts(self) -> List[Alert]:
        return sorted(
            self.alerts.values(),
            key=lambda a: a.created_at,
            reverse=True,
        )


# Singleton instance
store = DataStore()
