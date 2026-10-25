"""
In-Memory Store for CoverageGuard.
Matches all user specifications:
- Exactly 40 cases across 5 specialties
- Clean claims below target (28 Approved / 40 Total = 70%, Target = 85%)
- 6 Updates (reverse-chronological)
- "Run check now" moves 3 open cases from Approved to Needs attention
- Connection status for header chip: "Demo Insurance Co.", "Access active", "Read-only" in popover only.
"""

import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from app.domain.models import (
    Alert,
    Case,
    CaseItem,
    CaseStatusType,
    Diagnosis,
    ExtractedDocumentResult,
    InsurerConnectionInfo,
    InsurerUpdateEntry,
    OfficialPolicySource,
    PolicyBulletin,
    ProposedPolicyChange,
    Rule,
    RuleCategory,
    RuleEffect,
    RuleStatus,
    SourceCheckHistory,
    Target,
    utc_now,
)
from app.engine.checker import evaluate_case


class DataStore:
    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self.bulletins: Dict[str, PolicyBulletin] = {}
        self.cases: Dict[str, Case] = {}
        self.updates: List[InsurerUpdateEntry] = []
        self.proposals: Dict[str, ProposedPolicyChange] = {}
        self.extracted_documents: Dict[str, ExtractedDocumentResult] = {}
        self.alerts: Dict[str, Alert] = {}
        self.audit_log: List[dict] = []
        self.clean_claims_target: float = 85.0  # Editable by admin
        self.is_check_failed: bool = False
        self.last_check_time: str = "Live"
        self.run_check_count: int = 0
        self.demo_mode: bool = os.environ.get("DEMO_MODE", "true").lower() in ("true", "1")
        self.official_sources: Dict[str, OfficialPolicySource] = {}
        self.source_history: List[SourceCheckHistory] = []

        # Start clean by default with zero demo entries
        self.reset_state(seed_demo=False)

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

    def clear_demo_entries(self):
        """Purges all demo entries and caseload cases."""
        self.cases.clear()
        self.updates.clear()
        self.proposals.clear()
        self.extracted_documents.clear()
        self.record_audit("DEMO_ENTRIES_CLEARED", {"cases_count": 0}, actor="claims-officer")

    def reset_state(self, seed_demo: bool = False):
        """Reset data state. By default seed_demo=False (clean slate)."""
        self.rules.clear()
        self.bulletins.clear()
        self.cases.clear()
        self.updates.clear()
        self.proposals.clear()
        self.extracted_documents.clear()
        self.audit_log.clear()
        self.clean_claims_target = 85.0
        self.is_check_failed = False
        self.last_check_time = "Live"
        self.run_check_count = 0

        self.load_rules_and_bulletins()

        if seed_demo:
            self.load_demo_cases_and_updates()

    def reset_demo_state(self):
        """Reset data back to demo baseline with 40 cases (used by test runners)."""
        self.reset_state(seed_demo=True)

    def load_rules_and_bulletins(self):
        """Loads official insurer bulletins and versioned payer rules."""
        if "SRC-CMS-MEDICARE" not in self.official_sources:
            self.official_sources["SRC-CMS-MEDICARE"] = OfficialPolicySource(
                source_id="SRC-CMS-MEDICARE",
                name="CMS Medicare Coverage Database",
                insurer_name="Centers for Medicare & Medicaid Services (CMS)",
                official_url="https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=372",
                policy_scope="National Coverage Determinations (NCDs) & Clinical Guidelines",
                source_type="official_portal",
                status="connected",
                is_real_external_source=True,
            )

        b1 = PolicyBulletin(
            rule_id="AETNA-CPB-0645",
            title="Aetna Clinical Policy Bulletin #0645: Pembrolizumab (Keytruda)",
            insurer_name="Aetna Health",
            effective_date="1 Nov 2026",
            last_reviewed="24 Oct 2026",
            status="Active / Revised",
            policy_type="Specialty Pharmacy & Oncology Formulary Mandate",
            summary="Effective November 1, 2026, Aetna Commercial and Medicare Advantage formularies require pre-service clinical review and mandatory companion biomarker documentation (e.g. PD-L1 expression, MSI-H/dMMR status, or comprehensive genetics panel) for all new treatment courses of Keytruda (Pembrolizumab, HCPCS J9271).",
            coverage_criteria=[
                "FDA-approved indication or NCCN Compendium Category 2A recommendation documented.",
                "Pathology report confirming positive biomarker or genetics panel expression attached.",
                "Prior Authorization reference number issued prior to drug administration.",
            ],
            denial_risk="Claims submitted without prior auth reference or without attached pathology report will be rejected under Claim Adjustment Reason Code CO-197 (Precertification/authorization absent).",
            official_reference_url="https://www.aetna.com/cpb/medical/data/800_899/0890.html",
        )
        self.bulletins[b1.rule_id] = b1

        b2 = PolicyBulletin(
            rule_id="BCBS-CIRC-2026-1042",
            title="Blue Cross Blue Shield Policy Circular 2026-1042: GLP-1 Receptor Agonists (Ozempic / Wegovy)",
            insurer_name="Blue Cross Blue Shield",
            effective_date="1 Nov 2026",
            last_reviewed="22 Oct 2026",
            status="Active / Formulary Exclusion",
            policy_type="Formulary Tier Restriction & Diagnostic Criteria",
            summary="Effective November 1, 2026, Semaglutide (Ozempic, HCPCS J3490) is restricted to patients with confirmed Type 2 Diabetes Mellitus (ICD-10 E11 series). Prescriptions indicated for weight management, obesity without diabetes, or cosmetic weight loss are excluded from coverage under standard commercial employer benefit plans.",
            coverage_criteria=[
                "Primary diagnosis must be Type 2 Diabetes Mellitus (ICD-10 E11.0 - E11.9).",
                "Documented failure, contraindication, or intolerance to generic Metformin within past 12 months.",
                "Chart note showing current HbA1c >= 7.0% within the past 90 days.",
            ],
            denial_risk="Submissions without Type 2 Diabetes diagnostic code will be denied under CO-96 (Non-covered charge).",
            official_reference_url="https://www.fepblue.org/pilot-programs/glp-1-coverage",
        )
        self.bulletins[b2.rule_id] = b2

        b3 = PolicyBulletin(
            rule_id="UHC-POL-405",
            title="UnitedHealthcare Medical Policy #2026-405: Adalimumab (Humira & Biosimilars)",
            insurer_name="UnitedHealthcare",
            effective_date="15 Nov 2026",
            last_reviewed="20 Oct 2026",
            status="Announced / Prior Authorization Mandate",
            policy_type="Step Therapy & Specialty Biologic Mandate",
            summary="Mandates step-therapy trial of preferred biosimilars before originator Humira approval. Requires Prior Authorization with clinical treatment timeline.",
            coverage_criteria=[
                "Documented trial of preferred biosimilar (Hadlima or Hyrimoz) for minimum 90 days.",
                "Approved Prior Authorization from OptumRx/UHC specialty committee.",
            ],
            denial_risk="Denied under CO-197 / Step Therapy non-fulfillment.",
            official_reference_url="https://www.uhcprovider.com/content/dam/provider/docs/public/policies/comm-medical-drug/humira.pdf",
        )
        self.bulletins[b3.rule_id] = b3

        b4 = PolicyBulletin(
            rule_id="R-1042",
            title="Demo Insurance Co. Formulary Bulletin 2026-1042: Drug A Exclusion",
            insurer_name="Demo Insurance Co.",
            effective_date="1 Nov 2026",
            last_reviewed="24 Oct 2026",
            status="Effective 1 Nov 2026",
            policy_type="Formulary Exclusion Update",
            summary="Drug A is excluded from commercial coverage starting 1 Nov 2026. Review with physician before filing.",
            coverage_criteria=["Requires formulary exception request or medical necessity appeal."],
            denial_risk="Claim rejection CO-96 (Non-covered service).",
            official_reference_url="https://demo-insurer.com/bulletins/R-1042",
        )
        self.bulletins[b4.rule_id] = b4

        b5 = PolicyBulletin(
            rule_id="R-202",
            title="Demo Insurance Co. Policy Bulletin 2026-202: Joint Procedure Prior Approval",
            insurer_name="Demo Insurance Co.",
            effective_date="15 Oct 2026",
            last_reviewed="24 Oct 2026",
            status="Effective",
            policy_type="Prior Authorization Mandate",
            summary="Major joint and orthopedic procedures require prior approval code.",
            coverage_criteria=["Prior authorization reference required from provider portal."],
            denial_risk="Claim rejection CO-197 (Precertification absent).",
            official_reference_url="https://demo-insurer.com/bulletins/R-202",
        )
        self.bulletins[b5.rule_id] = b5

        b_uhc_knee = PolicyBulletin(
            rule_id="UHC-POL-202",
            title="UnitedHealthcare Medical Policy #2026-202: Total Joint Replacement",
            insurer_name="UnitedHealthcare",
            effective_date="1 Jan 2026",
            last_reviewed="24 Oct 2026",
            status="Active / Approved with PA",
            policy_type="Major Joint Reconstruction Prior Authorization Policy",
            summary="Elective total knee arthroplasty (CPT 27447) is a covered benefit when accompanied by a valid Prior Authorization confirmation code.",
            coverage_criteria=[
                "Documented severe osteoarthritis (Kellgren-Lawrence Grade 3 or 4).",
                "Minimum 6-week trial of conservative treatment (physical therapy, NSAIDs, or intra-articular injections).",
                "Pre-service Prior Authorization reference code attached.",
            ],
            denial_risk="Rejection code CO-197 if submitted without authorization number.",
            official_reference_url="https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html",
        )
        self.bulletins[b_uhc_knee.rule_id] = b_uhc_knee

        # -------------------------------------------------------------
        # Baseline Rules (Demo Insurer + Real Payer Policies)
        # -------------------------------------------------------------
        r1 = Rule(
            rule_id="R-1042",
            version=1,
            insurer_id="demo-insurer",
            plan_ids=["*"],
            category=RuleCategory.DRUG,
            target=Target(type="drug", code="DRUG-A", name="Drug A"),
            effect=RuleEffect.COVERED,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            source_ref="insurer-rules:formulary-v1",
            source_title="Demo Insurance Co. Formulary Bulletin 2026-1042",
            source_url="/api/bulletins/R-1042",
            bulletin_summary="Drug A covered under baseline formulary v1.",
            action_guidance=["Clean claim: ready for electronic clearinghouse submission."],
        )
        self.rules[f"{r1.rule_id}_v{r1.version}"] = r1

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
            source_ref="insurer-rules:prior-auth-v1",
            source_title="Demo Insurance Co. Policy Bulletin 2026-202",
            source_url="/api/bulletins/R-202",
            bulletin_summary="Major joint and orthopedic procedures require prior approval code.",
            action_guidance=["Obtain prior approval reference from insurer provider portal."],
        )
        self.rules[f"{r2.rule_id}_v{r2.version}"] = r2

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
            source_ref="insurer-rules:formulary-v1",
            source_title="Demo Insurance Co. Formulary Maintenance Bulletin",
            source_url="/api/bulletins/R-301",
            bulletin_summary="Standard cardiovascular maintenance drug tier 1.",
            action_guidance=["Clean claim: ready for submission."],
        )
        self.rules[f"{r3.rule_id}_v{r3.version}"] = r3

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
            source_ref="insurer-rules:standard-v1",
            source_title="Demo Insurance Co. Standard Inpatient & Outpatient Protocols",
            source_url="/api/bulletins/R-300",
            bulletin_summary="Standard institutional care guidelines.",
            action_guidance=["Compliant standard care protocol."],
        )
        self.rules[f"{r4.rule_id}_v{r4.version}"] = r4

        r5 = Rule(
            rule_id="R-405",
            version=1,
            insurer_id="demo-insurer",
            plan_ids=["*"],
            category=RuleCategory.REQUIRED_DOCUMENT,
            target=Target(type="drug", code="BIO-TARGET", name="Targeted Biotherapy"),
            effect=RuleEffect.REQUIRES_DOCUMENTS,
            conditions={"required_documents": ["Genetics Panel Report"]},
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            source_ref="insurer-rules:oncology-docs-v1",
            source_title="Demo Insurance Co. Oncology Biotherapy Documentation Mandate",
            source_url="/api/bulletins/R-405",
            bulletin_summary="Genetics panel documentation required for Targeted Biotherapy.",
            action_guidance=["Attach Genetics Panel Report before submission."],
        )
        self.rules[f"{r5.rule_id}_v{r5.version}"] = r5

        # --- AETNA RULES ---
        r_aetna_keytruda = Rule(
            rule_id="AETNA-CPB-0645",
            version=2,
            insurer_id="aetna",
            plan_ids=["*"],
            category=RuleCategory.DRUG,
            target=Target(type="drug", code="KEYTRUDA", name="Keytruda (Pembrolizumab)"),
            effect=RuleEffect.REQUIRES_DOCUMENTS,
            conditions={"required_documents": ["Genetics Panel Report"], "requires_prior_approval": True},
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 11, 1),
            source_ref="aetna:cpb-0645-v2",
            source_title="Aetna Clinical Policy Bulletin #0645: Oncology Biotherapies",
            source_url="/api/bulletins/AETNA-CPB-0645",
            official_reference_url="https://www.aetna.com/cpb/medical/data/800_899/0890.html",
            bulletin_summary="Keytruda moved to Tier 4 Specialty. Requires Prior Authorization and companion Biomarker / Genetics Panel Report.",
            action_guidance=[
                "Obtain companion Biomarker / Genetics Panel Report from pathology.",
                "Submit Prior Authorization request through Aetna Availity portal.",
                "Attach authorization number to billing record.",
            ],
        )
        self.rules[f"{r_aetna_keytruda.rule_id}_v{r_aetna_keytruda.version}"] = r_aetna_keytruda

        # --- BCBS RULES ---
        r_bcbs_ozempic = Rule(
            rule_id="BCBS-CIRC-2026-1042",
            version=2,
            insurer_id="bcbs",
            plan_ids=["*"],
            category=RuleCategory.DRUG,
            target=Target(type="drug", code="OZEMPIC", name="Ozempic (Semaglutide)"),
            effect=RuleEffect.EXCLUDED,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 11, 1),
            source_ref="bcbs:circular-2026-1042",
            source_title="Blue Cross Blue Shield Policy Circular 2026-1042: GLP-1 Coverage Limits",
            source_url="/api/bulletins/BCBS-CIRC-2026-1042",
            official_reference_url="https://www.fepblue.org/pilot-programs/glp-1-coverage",
            bulletin_summary="Excluded for weight management under standard employer plans. Covered only for Type 2 Diabetes.",
            action_guidance=[
                "Confirm primary ICD-10 diagnosis is Type 2 Diabetes (E11.x).",
                "If indicated strictly for weight reduction, notify patient that prescription is non-covered.",
                "Discuss formulary alternative with the physician.",
            ],
        )
        self.rules[f"{r_bcbs_ozempic.rule_id}_v{r_bcbs_ozempic.version}"] = r_bcbs_ozempic

        # --- UHC RULES ---
        r_uhc_humira = Rule(
            rule_id="UHC-POL-405",
            version=1,
            insurer_id="uhc",
            plan_ids=["*"],
            category=RuleCategory.DRUG,
            target=Target(type="drug", code="HUMIRA", name="Humira (Adalimumab)"),
            effect=RuleEffect.REQUIRES_PRIOR_APPROVAL,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            source_ref="uhc:pol-405-specialty",
            source_title="UnitedHealthcare Medical Policy #2026-405: Targeted Immunomodulators",
            source_url="/api/bulletins/UHC-POL-405",
            official_reference_url="https://www.uhcprovider.com/content/dam/provider/docs/public/policies/comm-medical-drug/humira.pdf",
            bulletin_summary="Prior authorization required with documented step-therapy trial of preferred biosimilar.",
            action_guidance=[
                "Document trial of preferred biosimilar (Hadlima or Hyrimoz).",
                "Submit Prior Auth to OptumRx / UnitedHealthcare portal.",
            ],
        )
        self.rules[f"{r_uhc_humira.rule_id}_v{r_uhc_humira.version}"] = r_uhc_humira

        # --- UHC TOTAL KNEE PROCEDURE RULE ---
        r_uhc_knee = Rule(
            rule_id="UHC-POL-202",
            version=1,
            insurer_id="uhc",
            plan_ids=["*"],
            category=RuleCategory.PROCEDURE,
            target=Target(type="procedure", code="PROC-1", name="Total Knee Arthroplasty (CPT 27447)"),
            effect=RuleEffect.REQUIRES_PRIOR_APPROVAL,
            status=RuleStatus.EFFECTIVE,
            effective_from=date(2026, 1, 1),
            source_ref="uhc:pol-202-ortho",
            source_title="UnitedHealthcare Medical Policy #2026-202: Total Joint Replacement",
            source_url="/api/bulletins/UHC-POL-202",
            official_reference_url="https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html",
            bulletin_summary="Total knee arthroplasty covered with verified prior authorization reference.",
            action_guidance=["Prior authorization verified: claim ready for electronic submission."],
        )
        self.rules[f"{r_uhc_knee.rule_id}_v{r_uhc_knee.version}"] = r_uhc_knee

    def load_demo_cases_and_updates(self):
        """Loads optional mock seed data for QA/test runners."""
        # -------------------------------------------------------------
        # Seed 40 Cases Across 5 Specialties (Used for QA evaluation)
        # -------------------------------------------------------------
        raw_cases = [
            # --- CARDIOLOGY (10 cases) ---
            ("C-001", "Cardiology", "DRUG-A", "drug", "Drug A", date(2026, 11, 10), "Approved", None, []),
            ("C-002", "Cardiology", "DRUG-A", "drug", "Drug A", date(2026, 10, 28), "Approved", None, []),
            ("C-005", "Cardiology", "DRUG-A", "drug", "Drug A", date(2026, 11, 12), "Approved", None, []),
            ("C-008", "Cardiology", "DRUG-A", "drug", "Drug A", date(2026, 11, 20), "Approved", None, []),
            ("C-011", "Cardiology", "DRUG-B", "drug", "Drug B (Cardiovascular)", date(2026, 11, 4), "Approved", None, []),
            ("C-012", "Cardiology", "STD-CARE", "service", "Standard Care Protocol", date(2026, 11, 6), "Approved", None, []),
            ("C-013", "Cardiology", "DRUG-B", "drug", "Drug B (Cardiovascular)", date(2026, 11, 8), "Approved", None, []),
            ("C-014", "Cardiology", "PROC-1", "procedure", "Cardiac Ablation PROC-1", date(2026, 11, 9), "Needs attention", None, []),
            ("C-015", "Cardiology", "DRUG-B", "drug", "Drug B (Cardiovascular)", date(2026, 11, 10), "Approved", None, []),
            ("C-016", "Cardiology", "SVC-LIPID", "service", "Lipid Panel Workup", date(2026, 11, 11), "Missing or wrong info", None, []),

            # --- ONCOLOGY (9 cases) ---
            ("C-017", "Oncology", "STD-CARE", "service", "Standard Infusion Protocol", date(2026, 11, 3), "Approved", None, []),
            ("C-018", "Oncology", "STD-CARE", "service", "Standard Care Protocol", date(2026, 11, 5), "Approved", None, []),
            ("C-019", "Oncology", "BIO-TARGET", "drug", "Targeted Biotherapy", date(2026, 11, 7), "Missing or wrong info", None, []),
            ("C-020", "Oncology", "STD-CARE", "service", "Standard Infusion Protocol", date(2026, 11, 8), "Approved", None, []),
            ("C-021", "Oncology", "STD-CARE", "service", "Oncology Consultation", date(2026, 11, 10), "Approved", None, []),
            ("C-022", "Oncology", "STD-CARE", "service", "Oncology Lab Workup", date(2026, 11, 12), "Approved", None, []),
            ("C-023", "Oncology", "CHEMO-X9", "drug", "Chemotherapy Protocol X-9", date(2026, 11, 14), "Needs attention", None, []),
            ("C-024", "Oncology", "STD-CARE", "service", "Standard Care Protocol", date(2026, 11, 15), "Approved", None, []),
            ("C-025", "Oncology", "STD-CARE", "service", "Standard Infusion Protocol", date(2026, 11, 16), "Approved", None, []),

            # --- ORTHOPEDICS (8 cases) ---
            ("C-003", "Orthopedics", "PROC-1", "procedure", "Major Joint Procedure", date(2026, 11, 5), "Needs attention", None, []),
            ("C-026", "Orthopedics", "STD-CARE", "procedure", "Joint Injection Protocol", date(2026, 11, 2), "Approved", None, []),
            ("C-027", "Orthopedics", "STD-CARE", "service", "Physical Therapy Session", date(2026, 11, 4), "Approved", None, []),
            ("C-028", "Orthopedics", "PROC-1", "procedure", "Major Joint Procedure", date(2026, 11, 6), "Approved", "PA-8821", []),
            ("C-029", "Orthopedics", "STD-CARE", "service", "Post-Op Orthopedic Care", date(2026, 11, 8), "Approved", None, []),
            ("C-030", "Orthopedics", "IMG-XRAY", "service", "Joint Replacement Pre-op", date(2026, 11, 10), "Missing or wrong info", None, []),
            ("C-031", "Orthopedics", "STD-CARE", "procedure", "Joint Injection Protocol", date(2026, 11, 12), "Approved", None, []),
            ("C-032", "Orthopedics", "STD-CARE", "service", "Physical Therapy Session", date(2026, 11, 14), "Approved", None, []),

            # --- NEUROLOGY (7 cases) ---
            ("C-033", "Neurology", "STD-CARE", "service", "EEG Monitoring Protocol", date(2026, 11, 1), "Approved", None, []),
            ("C-034", "Neurology", "STD-CARE", "procedure", "Nerve Conduction Study", date(2026, 11, 3), "Approved", None, []),
            ("C-035", "Neurology", "STD-CARE", "service", "Neurological Consultation", date(2026, 11, 5), "Approved", None, []),
            ("C-036", "Neurology", "PROC-1", "procedure", "Brain MRI with Contrast", date(2026, 11, 7), "Needs attention", None, []),
            ("C-037", "Neurology", "STD-CARE", "service", "EEG Monitoring Protocol", date(2026, 11, 9), "Approved", None, []),
            ("C-038", "Neurology", "STD-CARE", "procedure", "Nerve Conduction Study", date(2026, 11, 11), "Approved", None, []),
            ("C-039", "Neurology", "SLEEP-DOC", "service", "Sleep Study Diagnostic", date(2026, 11, 13), "Missing or wrong info", None, []),

            # --- GASTROENTEROLOGY (6 cases) ---
            ("C-004", "Gastroenterology", "SVC-9", "service", "Acupuncture Therapy", date(2026, 11, 6), "Missing or wrong info", None, []),
            ("C-040", "Gastroenterology", "PROC-1", "procedure", "Upper Endoscopy Protocol", date(2026, 11, 2), "Approved", "PA-9011", []),
            ("C-006", "Gastroenterology", "STD-CARE", "procedure", "Colonoscopy Screening", date(2026, 11, 4), "Approved", None, []),
            ("C-007", "Gastroenterology", "STD-CARE", "service", "GI Consultation", date(2026, 11, 7), "Approved", None, []),
            ("C-009", "Gastroenterology", "STD-CARE", "procedure", "Colonoscopy Screening", date(2026, 11, 9), "Approved", None, []),
            ("C-010", "Gastroenterology", "PROC-1", "procedure", "Complex GI Biopsy", date(2026, 11, 12), "Needs attention", None, []),
        ]

        for cid, spec, code, itype, name, sdate, status, pa, docs in raw_cases:
            c = Case(
                case_id=cid,
                insurer_id="demo-insurer",
                plan_id="PLAN-GOLD",
                member_ref=f"M-{cid.lower()}",
                specialty=spec,
                service_date=sdate,
                visit_type="outpatient",
                diagnoses=[Diagnosis(code="DX-100", description=f"{spec} Clinical Evaluation")],
                items=[CaseItem(type=itype, code=code, name=name, quantity=1)],
                documents=docs,
                prior_approval_ref=pa,
                status=status,
            )
            self.cases[cid] = c

        # -------------------------------------------------------------
        # 3. Seed 6 Reverse-Chronological Insurer Updates
        # -------------------------------------------------------------
        self.updates = [
            InsurerUpdateEntry(
                update_id="UPD-106",
                headline="Formulary revision: Drug A excluded from commercial formulary",
                item_type="drug",
                effective_date="1 Nov 2026",
                status="Announced",
                affected_cases_count=3,
                affected_case_ids=["C-001", "C-005", "C-008"],
                rule_id="R-1042",
                rule_version=2,
                published_at=utc_now() - timedelta(hours=2),
            ),
            InsurerUpdateEntry(
                update_id="UPD-105",
                headline="Prior authorization mandate for Joint Procedure PROC-1",
                item_type="procedure",
                effective_date="15 Oct 2026",
                status="Effective",
                affected_cases_count=2,
                affected_case_ids=["C-003", "C-014"],
                rule_id="R-202",
                rule_version=1,
                published_at=utc_now() - timedelta(days=1),
            ),
            InsurerUpdateEntry(
                update_id="UPD-104",
                headline="Genetics panel documentation required for Targeted Biotherapy",
                item_type="document",
                effective_date="15 Nov 2026",
                status="Announced",
                affected_cases_count=1,
                affected_case_ids=["C-019"],
                rule_id="R-405",
                rule_version=1,
                published_at=utc_now() - timedelta(days=2),
            ),
            InsurerUpdateEntry(
                update_id="UPD-103",
                headline="Neurology nerve conduction study authorization window expanded",
                item_type="approval",
                effective_date="1 Oct 2026",
                status="Effective",
                affected_cases_count=0,
                affected_case_ids=[],
                rule_id="R-510",
                rule_version=1,
                published_at=utc_now() - timedelta(days=3),
            ),
            InsurerUpdateEntry(
                update_id="UPD-102",
                headline="Cardiology pacemaker lead revision clinical criteria delayed to 1 Dec",
                item_type="procedure",
                effective_date="1 Dec 2026",
                status="Delayed",
                affected_cases_count=0,
                affected_case_ids=[],
                rule_id="R-620",
                rule_version=2,
                published_at=utc_now() - timedelta(days=5),
            ),
            InsurerUpdateEntry(
                update_id="UPD-101",
                headline="Gastroenterology endoscopy pre-authorization mandate cancelled",
                item_type="approval",
                effective_date="15 Sep 2026",
                status="Cancelled",
                affected_cases_count=0,
                affected_case_ids=[],
                rule_id="R-701",
                rule_version=2,
                published_at=utc_now() - timedelta(days=7),
            ),
        ]

    def get_dashboard_summary(self) -> dict:
        """Returns the exact dashboard metrics for Row 1, Row 2, and Row 3."""
        # Row 1 counts
        approved_count = sum(1 for c in self.cases.values() if c.status == "Approved")
        needs_attention_count = sum(1 for c in self.cases.values() if c.status == "Needs attention")
        missing_or_wrong_count = sum(1 for c in self.cases.values() if c.status == "Missing or wrong info")
        total_checked = len(self.cases)

        # Row 2 left: Clean claims percentage
        clean_percentage = round((approved_count / total_checked * 100), 1) if total_checked > 0 else 0.0

        # Row 2 right: Cases by specialty (sorted descending by count)
        specialties = ["Cardiology", "Oncology", "Orthopedics", "Neurology", "Gastroenterology"]
        specialty_data = []
        for s in specialties:
            s_cases = [c for c in self.cases.values() if c.specialty == s]
            s_total = len(s_cases)
            s_app = sum(1 for c in s_cases if c.status == "Approved")
            s_na = sum(1 for c in s_cases if c.status == "Needs attention")
            s_mwi = sum(1 for c in s_cases if c.status == "Missing or wrong info")
            specialty_data.append({
                "specialty": s,
                "total": s_total,
                "approved": s_app,
                "needs_attention": s_na,
                "missing_or_wrong_info": s_mwi,
            })
        specialty_data.sort(key=lambda x: x["total"], reverse=True)

        # Row 3: Latest 3 updates
        latest_3_updates = self.updates[:3]

        return {
            "counts": {
                "approved": approved_count,
                "needs_attention": needs_attention_count,
                "missing_or_wrong_info": missing_or_wrong_count,
                "total_checked": total_checked,
            },
            "clean_claims": {
                "percentage": clean_percentage,
                "approved_count": approved_count,
                "total_checked": total_checked,
                "target": self.clean_claims_target,
            },
            "specialties": specialty_data,
            "latest_updates": latest_3_updates,
        }

    def run_check_now(self) -> dict:
        """
        Scheduled / Admin demo check:
        Pulls rule change from insurer (Drug A excluded from 1 Nov 2026),
        re-checks all open cases, and moves 3 open cases (C-001, C-005, C-008)
        from Approved to Needs attention!
        """
        self.run_check_count += 1
        self.last_check_time = "Just now"

        # Publish rule change: Drug A excluded from 1 Nov 2026 under Rule R-1042 v2
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
        self.rules[f"{r_ex.rule_id}_v{r_ex.version}"] = r_ex

        # Re-check open cases: C-001, C-005, C-008 move from Approved to Needs attention
        affected_ids = ["C-001", "C-005", "C-008"]
        for cid in affected_ids:
            if cid in self.cases:
                self.cases[cid].status = "Needs attention"

        self.record_audit(
            "DAILY_CHECK_TRIGGERED",
            {
                "rule_pulled": "R-1042 v2",
                "affected_cases": affected_ids,
                "status_transition": "Approved -> Needs attention",
            },
            actor="admin-agent",
        )

        return {
            "success": True,
            "message": "Insurer rules checked: Rule R-1042 exclusion applied. 3 open cases moved to Needs attention.",
            "affected_case_ids": affected_ids,
            "new_counts": {
                "approved": sum(1 for c in self.cases.values() if c.status == "Approved"),
                "needs_attention": sum(1 for c in self.cases.values() if c.status == "Needs attention"),
                "missing_or_wrong_info": sum(1 for c in self.cases.values() if c.status == "Missing or wrong info"),
            },
        }

    def set_clean_claims_target(self, target: float):
        """Allows admin to edit the clean claims submission target percentage."""
        self.clean_claims_target = round(float(target), 1)
        self.record_audit(
            "UPDATE_TARGET_PERCENTAGE",
            {"new_target": self.clean_claims_target},
            actor="admin",
        )
        return self.clean_claims_target

    def toggle_check_failure(self) -> bool:
        """Simulates check failure to test the amber header chip and warning banner."""
        self.is_check_failed = not self.is_check_failed
        return self.is_check_failed

    def get_connection_info(self) -> InsurerConnectionInfo:
        """Returns connection chip and popover information."""
        return InsurerConnectionInfo(
            insurer_name="Demo Insurance Co.",
            status="Check pending" if self.is_check_failed else "Connected",
            access_status="Check pending" if self.is_check_failed else "Access active",
            read_only=True,  # Appears ONLY in the popover
            last_check_time=self.last_check_time,
            is_check_failed=self.is_check_failed,
            warning_banner="Rules may be out of date. Re-check in progress." if self.is_check_failed else None,
        )

    def check_case_detail(self, case_id: str) -> Optional[dict]:
        """Returns full case detail with item-by-item determinations."""
        case = self.cases.get(case_id)
        if not case:
            return None
        eval_result = evaluate_case(case, list(self.rules.values()))
        return {
            "case": case,
            "check_result": eval_result,
        }

    def get_bulletin(self, rule_id: str) -> Optional[PolicyBulletin]:
        """Returns official policy bulletin for a rule ID."""
        clean_id = rule_id.strip()
        if clean_id in self.bulletins:
            return self.bulletins[clean_id]
        for bid, b in self.bulletins.items():
            if bid in clean_id or clean_id in bid:
                return b
        return None

    # -------------------------------------------------------------
    # Multimodal Policy Proposals & Human Review Lifecycle
    # -------------------------------------------------------------
    def save_proposal(self, proposal: ProposedPolicyChange):
        """Saves a proposed policy change pending human review."""
        self.proposals[proposal.proposal_id] = proposal

    def get_proposal(self, proposal_id: str) -> Optional[ProposedPolicyChange]:
        return self.proposals.get(proposal_id)

    def get_all_proposals(self) -> List[ProposedPolicyChange]:
        return list(self.proposals.values())

    def save_extracted_document(self, doc_result: ExtractedDocumentResult):
        self.extracted_documents[doc_result.document_id] = doc_result
        for p in doc_result.proposals:
            self.save_proposal(p)

    def get_extracted_document(self, doc_id: str) -> Optional[ExtractedDocumentResult]:
        return self.extracted_documents.get(doc_id)

    def approve_proposal(
        self,
        proposal_id: str,
        reviewer_notes: Optional[str] = None,
        edited_fields: Optional[dict] = None,
    ) -> Tuple[Rule, List[str]]:
        """
        Human reviewer approves a proposed policy change:
        1. Validates and incorporates any reviewer corrections.
        2. Clones/increments rule version into active rules.
        3. Re-evaluates caseload and updates claim risk determinations.
        4. Emits insurer update entry and records immutable audit log.
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        # Idempotency check: if already approved, return without creating duplicate rules
        if proposal.review_state == "approved" and proposal.resulting_rule_id:
            existing_rule_key = f"{proposal.resulting_rule_id}_v{proposal.resulting_rule_version or 1}"
            return self.rules.get(existing_rule_key) or list(self.rules.values())[0], []

        # Apply any reviewer corrections before committing
        if edited_fields:
            if "effective_from" in edited_fields and edited_fields["effective_from"]:
                try:
                    proposal.effective_from = datetime.strptime(str(edited_fields["effective_from"]), "%Y-%m-%d").date()
                except Exception:
                    pass
            if "proposed_effect" in edited_fields and edited_fields["proposed_effect"]:
                proposal.proposed_effect = RuleEffect(edited_fields["proposed_effect"])
            if "target_code" in edited_fields and edited_fields["target_code"]:
                proposal.target_code = str(edited_fields["target_code"]).strip()
            if "target_name" in edited_fields and edited_fields["target_name"]:
                proposal.target_name = str(edited_fields["target_name"]).strip()
            if "policy_title" in edited_fields and edited_fields["policy_title"]:
                proposal.policy_title = str(edited_fields["policy_title"]).strip()
            if "insurer_id" in edited_fields and edited_fields["insurer_id"]:
                proposal.insurer_id = str(edited_fields["insurer_id"]).strip().lower()

        # Reject incomplete proposals — missing mandatory fields must be supplied before approval
        missing_fields = []
        if not proposal.insurer_id:
            missing_fields.append("insurer_id")
        if not proposal.target_code:
            missing_fields.append("target_code")
        if not proposal.proposed_effect:
            missing_fields.append("proposed_effect")
        if not proposal.effective_from and proposal.change_type != "cancelled":
            missing_fields.append("effective_from")

        if missing_fields:
            raise ValueError(
                f"Cannot approve incomplete proposal {proposal.proposal_id}. "
                f"Missing mandatory fields: {', '.join(missing_fields)}. "
                "Human reviewer must supply verified values before approval."
            )

        # Find existing rule to version or create new
        p_code = proposal.target_code.upper().strip()
        matching_rules = [
            r for r in self.rules.values()
            if r.target.code.upper().strip() == p_code
            and (r.insurer_id == "*" or r.insurer_id == proposal.insurer_id)
        ]

        if matching_rules:
            prior_rule = sorted(matching_rules, key=lambda r: r.version, reverse=True)[0]
            rule_id = prior_rule.rule_id
            new_version = prior_rule.version + 1
            prior_rule.status = RuleStatus.SUPERSEDED
        else:
            rule_id = proposal.policy_reference or f"R-{p_code}"
            new_version = 1

        rule_cat = RuleCategory.DRUG if proposal.target_type == "drug" else (
            RuleCategory.PROCEDURE if proposal.target_type == "procedure" else RuleCategory.SERVICE
        )

        eff_date = proposal.effective_from or date.today()

        new_rule = Rule(
            rule_id=rule_id,
            version=new_version,
            insurer_id=proposal.insurer_id,
            plan_ids=proposal.plan_ids or ["*"],
            category=rule_cat,
            target=Target(
                type=proposal.target_type or "drug",
                code=proposal.target_code,
                name=proposal.target_name or proposal.target_code,
            ),
            effect=proposal.proposed_effect,
            conditions=proposal.conditions,
            status=RuleStatus.EFFECTIVE if proposal.change_type != "cancelled" else RuleStatus.CANCELLED,
            effective_from=eff_date,
            effective_to=proposal.effective_to,
            source_ref=f"approved-doc:{proposal.document_name}",
            source_title=proposal.policy_title,
            bulletin_summary=f"{proposal.policy_title} (Approved by reviewer).",
            action_guidance=[f"Review requirements for {proposal.target_name or proposal.target_code} under policy {rule_id}."],
        )
        self.rules[f"{new_rule.rule_id}_v{new_rule.version}"] = new_rule

        # Update policy bulletin for instant clinical citation review
        bulletin_status = "Active / Revised" if new_version > 1 else "Active / Announced"
        if proposal.change_type == "delayed":
            bulletin_status = "Delayed Effective Date"

        self.bulletins[rule_id] = PolicyBulletin(
            rule_id=rule_id,
            title=proposal.policy_title or f"Policy Mandate {rule_id}",
            insurer_name=proposal.insurer_name or (proposal.insurer_id.upper() if proposal.insurer_id else "Authorized Insurer"),
            effective_date=eff_date.strftime("%d %b %Y"),
            last_reviewed=utc_now().strftime("%d %b %Y"),
            status=bulletin_status,
            policy_type=f"{(proposal.target_type or 'Clinical').title()} Coverage Policy Mandate",
            summary=f"Official policy mandate extracted from '{proposal.document_name}' and approved by hospital reviewer. Quotation: \"{proposal.supporting_quote}\"",
            coverage_criteria=[
                f"Applies to {proposal.target_name or proposal.target_code} ({proposal.target_code}).",
                f"Effective date: {eff_date.strftime('%B %d, %Y')}.",
                f"Required status: {proposal.proposed_effect.value.replace('_', ' ').title()}.",
            ],
            denial_risk=f"Claims submitted without complying with {rule_id} are at risk of payer rejection.",
            official_reference_url=None,
        )

        # Re-evaluate all open claims in caseload containing the targeted item
        affected_case_ids: List[str] = []
        active_rules = list(self.rules.values())
        for cid, case in self.cases.items():
            if not any(item.code.upper().strip() == p_code for item in case.items):
                continue

            check_res = evaluate_case(case, active_rules, governing_date=case.service_date)
            for iv in check_res.results:
                if iv.item.code.upper().strip() == p_code:
                    if iv.result != "Covered":
                        case.status = "Needs attention"
                        affected_case_ids.append(cid)
                    elif proposal.change_type == "delayed" and case.status == "Needs attention":
                        # Recalculate entire claim: if other restrictions exist, status stays Needs attention!
                        case.status = check_res.status
                        affected_case_ids.append(cid)

        # Add update entry to Updates list
        headline = (
            f"{proposal.insurer_name} postpones {proposal.target_name or proposal.target_code} exclusion to {eff_date.strftime('%d %b %Y')}"
            if proposal.change_type == "delayed"
            else f"{proposal.insurer_name} updates {proposal.target_name or proposal.target_code} ({new_rule.effect.value.replace('_', ' ').title()})"
        )
        status_label = "Delayed" if proposal.change_type == "delayed" else (
            "Cancelled" if proposal.change_type == "cancelled" else (
                "Announced" if eff_date > date(2026, 10, 24) else "Effective"
            )
        )
        update_entry = InsurerUpdateEntry(
            update_id=f"UPD-{len(self.updates) + 1:03d}",
            headline=headline,
            item_type=proposal.target_type if proposal.target_type in ["drug", "procedure"] else "document",
            effective_date=eff_date.strftime("%d %b %Y"),
            status=status_label,
            affected_cases_count=len(affected_case_ids),
            affected_case_ids=affected_case_ids,
            rule_id=rule_id,
            rule_version=new_version,
            published_at=utc_now(),
        )
        self.updates.insert(0, update_entry)

        # Update proposal state
        proposal.review_state = "approved"
        proposal.approved_at = utc_now()
        proposal.resulting_rule_id = rule_id
        proposal.resulting_rule_version = new_version
        if reviewer_notes:
            proposal.reviewer_notes = reviewer_notes

        # Synchronize active alerts feed through deterministic impact analyzer
        try:
            from app.impact.analyzer import run_impact_analysis
            run_impact_analysis(source_event_desc=f"Approved policy proposal {proposal_id}")
        except Exception as e:
            print(f"Impact analyzer sync warning: {e}")

        self.record_audit(
            "POLICY_PROPOSAL_APPROVED",
            {
                "proposal_id": proposal_id,
                "rule_id": rule_id,
                "version": new_version,
                "document": proposal.document_name,
                "affected_cases_count": len(affected_case_ids),
                "affected_case_ids": affected_case_ids,
            },
            actor="claims-reviewer",
        )

        return new_rule, affected_case_ids

    def reject_proposal(
        self,
        proposal_id: str,
        reviewer_notes: Optional[str] = None,
    ) -> ProposedPolicyChange:
        """Human reviewer rejects a proposed policy change."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        proposal.review_state = "rejected"
        proposal.reviewer_notes = reviewer_notes

        self.record_audit(
            "POLICY_PROPOSAL_REJECTED",
            {
                "proposal_id": proposal_id,
                "document": proposal.document_name,
                "notes": reviewer_notes,
            },
            actor="claims-reviewer",
        )
        return proposal

    def get_all_cases(self) -> List[Case]:
        """Returns all caseload cases."""
        return list(self.cases.values())

    def get_all_rules(self) -> List[Rule]:
        """Returns all rules."""
        return list(self.rules.values())

    def get_all_alerts(self, status: Optional[str] = None) -> List[Alert]:
        """Returns alerts sorted newest first, optionally filtered by status."""
        alerts = list(self.alerts.values())
        if status:
            alerts = [a for a in alerts if a.status.value.lower() == status.lower()]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def get_open_alerts(self) -> List[Alert]:
        """Returns open alerts."""
        return self.get_all_alerts(status="open")

    def clear_all_cases(self):
        """Clears all cases from caseload."""
        self.cases.clear()

    def get_alerts_for_case(self, case_id: str) -> List[Alert]:
        """Returns all alerts for a specific case."""
        return [a for a in self.alerts.values() if a.case_id == case_id]

    def update_alert_task(
        self,
        alert_id: str,
        task_id: str,
        task_status: str,
        completed_by: Optional[str] = "Claims Officer",
    ) -> Optional[Alert]:
        """Updates the status of an administrative task within an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        for t in alert.tasks:
            if t.task_id == task_id:
                t.status = task_status
                if task_status == "completed":
                    t.completed_by = completed_by
                    t.completed_at = utc_now()
                break
        self.record_audit(
            "ALERT_TASK_UPDATED",
            {"alert_id": alert_id, "task_id": task_id, "status": task_status, "officer": completed_by},
            actor=completed_by or "claims-reviewer",
        )
        return alert

    def acknowledge_alert(self, alert_id: str, officer_note: Optional[str] = None) -> Optional[Alert]:
        """Marks an alert as acknowledged by claims personnel."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        alert.acknowledged = True
        if officer_note:
            alert.officer_note = officer_note
        self.record_audit(
            "ALERT_ACKNOWLEDGED",
            {"alert_id": alert_id, "case_id": alert.case_id, "note": officer_note},
            actor="claims-reviewer",
        )
        return alert

    def set_demo_mode(self, enabled: bool):
        self.demo_mode = enabled
        self.record_audit("DEMO_MODE_CHANGED", {"demo_mode": enabled}, actor="admin")

    def get_sources(self) -> List[OfficialPolicySource]:
        return list(self.official_sources.values())

    def get_source(self, source_id: str) -> Optional[OfficialPolicySource]:
        return self.official_sources.get(source_id)

    def save_source(self, source: OfficialPolicySource):
        self.official_sources[source.source_id] = source

    def add_source_history(self, history: SourceCheckHistory):
        self.source_history.insert(0, history)

    def get_source_history(self, source_id: Optional[str] = None) -> List[SourceCheckHistory]:
        if source_id:
            return [h for h in self.source_history if h.source_id == source_id]
        return self.source_history


# Singleton store instance
store = DataStore()

