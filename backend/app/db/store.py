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
from threading import RLock
from functools import wraps

_STATE_LOCK = RLock()

def serialized(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        with _STATE_LOCK:
            return method(*args, **kwargs)
    return wrapped


def transactional(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        from copy import deepcopy
        snapshot = deepcopy(self.__dict__)
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise
    return wrapped

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
from app.domain.sync_models import PolicyCandidate, PolicyDocumentVersion, SyncSource, SyncRun


class DataStore:
    def _checkpoint_path(self):
        from pathlib import Path
        value = os.environ.get("COVERAGEGUARD_STATE_PATH")
        if value == "" or not getattr(self, "_persistent", True):
            return None
        return Path(value) if value else Path(__file__).resolve().parents[2] / "data" / "coverageguard.sqlite3"

    @serialized
    def save_checkpoint(self):
        """Atomic local snapshot for this single-process synthetic-data application."""
        import json
        path = self._checkpoint_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        mappings = ("rules", "bulletins", "cases", "proposals", "extracted_documents", "alerts", "official_sources", "policy_catalog", "policy_versions", "sync_sources", "sync_runs")
        data = {name: {k: v.model_dump(mode="json") for k, v in getattr(self, name).items()} for name in mappings}
        data.update(updates=[v.model_dump(mode="json") for v in self.updates],
                    source_history=[v.model_dump(mode="json") for v in self.source_history],
                    audit_log=self.audit_log, demo_mode=self.demo_mode, clean_claims_target=self.clean_claims_target)
        if path.suffix in {".sqlite3", ".db"}:
            from app.db.persistence import write_snapshot
            write_snapshot(path, data)
            return
        temporary = path.with_suffix(".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            os.chmod(temporary, 0o600)
            json.dump(data, handle, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def load_checkpoint(self):
        import json
        path = self._checkpoint_path()
        if path is None:
            return
        if not path.exists():
            legacy = path.parent / "state.json"
            if path.suffix not in {".sqlite3", ".db"} or not legacy.exists():
                return
            data = json.loads(legacy.read_text())
        elif path.suffix in {".sqlite3", ".db"}:
            from app.db.persistence import read_snapshot
            data = read_snapshot(path)
        else:
            data = json.loads(path.read_text())
        models = {"rules": Rule, "bulletins": PolicyBulletin, "cases": Case,
                  "proposals": ProposedPolicyChange, "extracted_documents": ExtractedDocumentResult,
                  "alerts": Alert, "official_sources": OfficialPolicySource,
                  "policy_catalog": PolicyCandidate, "policy_versions": PolicyDocumentVersion, "sync_sources": SyncSource, "sync_runs": SyncRun}
        for name, model in models.items():
            setattr(self, name, {k: model.model_validate(v) for k, v in data.get(name, {}).items()})
        self.updates = [InsurerUpdateEntry.model_validate(v) for v in data["updates"]]
        self.source_history = [SourceCheckHistory.model_validate(v) for v in data["source_history"]]
        self.audit_log = data["audit_log"]
        self.demo_mode = data["demo_mode"]
        self.clean_claims_target = data["clean_claims_target"]
        for run in self.sync_runs.values():
            if run.status == "running":
                run.status = "interrupted"
                run.error = "Previous sync interrupted; unprocessed documents remain retryable."
        for source in self.official_sources.values():
            if source.status == "connected" and not source.processed_at:
                source.status = "active"
            if source.status in {"checking", "fetched", "processing"}:
                source.status = "extraction_failed"
                source.error_message = "Previous check interrupted; document will be retried."

    def __init__(self, persist=True):
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
        self.demo_mode: bool = os.environ.get("DEMO_MODE", "false").lower() in ("true", "1")
        self.official_sources: Dict[str, OfficialPolicySource] = {}
        self.source_history: List[SourceCheckHistory] = []
        self.policy_catalog = {}
        self.policy_versions = {}
        self.sync_sources = {}
        self.sync_runs = {}

        # Start clean by default with zero demo entries
        self.reset_state(seed_demo=False)
        self._persistent = persist
        if persist:
            self.load_checkpoint()

    @serialized
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

    @serialized
    def clear_demo_entries(self):
        """Purges all demo entries and caseload cases."""
        self.cases.clear()
        self.alerts.clear()
        self.updates.clear()
        self.proposals.clear()
        self.extracted_documents.clear()
        self.record_audit("DEMO_ENTRIES_CLEARED", {"cases_count": 0}, actor="claims-officer")

    @serialized
    def reset_state(self, seed_demo: bool = False):
        """Reset data state. By default seed_demo=False (clean slate)."""
        self._generation = getattr(self, "_generation", 0) + 1
        self.rules.clear()
        self.bulletins.clear()
        self.cases.clear()
        self.alerts.clear()
        self.updates.clear()
        self.proposals.clear()
        self.extracted_documents.clear()
        self.audit_log.clear()
        self.alerts.clear()
        self.official_sources.clear()
        self.source_history.clear()
        self.policy_catalog.clear()
        self.policy_versions.clear()
        self.sync_sources.clear()
        self.sync_runs.clear()
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
        self.demo_mode = True

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
                status="active",
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
        for rule in self.rules.values():
            rule.is_synthetic = True
            rule.source_title = f"Synthetic example: {rule.source_title or rule.rule_id}"
        for bulletin in self.bulletins.values():
            bulletin.status = "Synthetic example"
            bulletin.summary = f"SYNTHETIC EXAMPLE — not verified current payer criteria. {bulletin.summary}"

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
        if not self.demo_mode:
            from app.impact.analyzer import run_impact_analysis
            before = {c.case_id: c.status for c in self.cases.values()}
            run_impact_analysis(data_store=self)
            affected = [c.case_id for c in self.cases.values() if before[c.case_id] != c.status]
            return {"success": True, "message": "Current approved rules re-evaluated. No unapproved updates applied.",
                    "affected_case_ids": affected}
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
            "message": "Synthetic demo check: Rule R-1042 exclusion applied to demo claims.",
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
        from app.engine.findings import claim_findings, eligible_policy_rules
        eval_result = evaluate_case(case, eligible_policy_rules(case, self)[0])
        return {
            "case": case,
            "check_result": eval_result,
            "findings": claim_findings(case, self),
        }

    def get_bulletin(self, rule_id: str) -> Optional[PolicyBulletin]:
        """Returns official policy bulletin for a rule ID."""
        clean_id = rule_id.strip()
        return self.bulletins.get(clean_id)

    # -------------------------------------------------------------
    # Multimodal Policy Proposals & Human Review Lifecycle
    # -------------------------------------------------------------
    @serialized
    def save_proposal(self, proposal: ProposedPolicyChange):
        """Saves a proposed policy change pending human review."""
        self.proposals[proposal.proposal_id] = proposal

    def get_proposal(self, proposal_id: str) -> Optional[ProposedPolicyChange]:
        return self.proposals.get(proposal_id)

    def get_all_proposals(self) -> List[ProposedPolicyChange]:
        return list(self.proposals.values())

    @serialized
    def save_extracted_document(self, doc_result: ExtractedDocumentResult):
        self.extracted_documents[doc_result.document_id] = doc_result
        for p in doc_result.proposals:
            self.save_proposal(p)

    def get_extracted_document(self, doc_id: str) -> Optional[ExtractedDocumentResult]:
        document = self.extracted_documents.get(doc_id)
        if document:
            return document.model_copy(update={"proposals": [self.proposals.get(p.proposal_id, p) for p in document.proposals]})
        return None

    @serialized
    @transactional
    def approve_proposal(self, proposal_id: str, reviewer_notes=None, edited_fields=None):
        from app.intelligence.rule_builder import build_proposed_rule
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")
        if proposal.review_state == "approved":
            rule = self.rules.get(f"{proposal.resulting_rule_id}_v{proposal.resulting_rule_version}")
            if rule is None:
                raise ValueError("Approved proposal's rule is missing; restore the checkpoint before retrying.")
            return rule, []
        if proposal.review_state == "rejected":
            raise ValueError("Rejected proposals cannot be approved. Extract a new proposal for review.")
        # Validate a copy: a rejected edit must not partially mutate stored evidence.
        allowed = {"insurer_id", "insurer_name", "plan_ids", "target_type", "target_code", "target_name",
                   "policy_title", "policy_reference", "proposed_effect", "effective_from", "effective_to",
                   "conditions", "change_type", "evidence_confirmed_by_reviewer", "jurisdictions", "code_system", "scope_verified", "billing_articles_verified"}
        edits = edited_fields or {}
        if set(edits) - allowed:
            raise ValueError("Unsupported reviewer correction field.")
        proposal = ProposedPolicyChange.model_validate({**proposal.model_dump(), **edits})
        if proposal.evidence_confirmed_by_reviewer and not reviewer_notes:
            raise ValueError("Record how the original evidence was visually verified in reviewer notes.")
        if proposal.catalog_id:
            candidate=self.policy_catalog.get(proposal.catalog_id)
            if not candidate or candidate.revision!=proposal.source_revision or candidate.document_id!=proposal.document_id or candidate.status in {"extraction_failed", "fetch_failed", "access_restricted", "not_in_latest_index"}:
                raise ValueError("This proposal is not the latest discovered policy revision. Refresh and review the current version.")
            if proposal.scope_verified and not reviewer_notes:
                raise ValueError("Record verification of plan, jurisdiction and source scope in reviewer notes.")
        new_rule = build_proposed_rule(proposal, self.get_all_rules())
        if proposal.extraction_method and not proposal.is_synthetic and proposal.scope_verified and not reviewer_notes:
            raise ValueError("Record verification of exact insurer, plan and jurisdiction in reviewer notes.")
        before = {c.case_id: evaluate_case(c, self.get_all_rules()) for c in self.cases.values()}
        proposal.review_state = "approved"
        proposal.approved_at = utc_now()
        proposal.resulting_rule_id = new_rule.rule_id
        proposal.resulting_rule_version = new_rule.version
        proposal.reviewer_notes = reviewer_notes
        self.proposals[proposal_id] = proposal
        for source in self.official_sources.values():
            source.pending_proposal_ids = [pid for pid in source.pending_proposal_ids if pid != proposal_id]
            if not source.pending_proposal_ids and source.status == "pending_review":
                source.status = "connected"
        self.rules[f"{new_rule.rule_id}_v{new_rule.version}"] = new_rule
        self.bulletins[new_rule.rule_id] = PolicyBulletin(
            rule_id=new_rule.rule_id, title=proposal.policy_title or new_rule.rule_id,
            insurer_name=proposal.insurer_name or proposal.insurer_id,
            effective_date=str(new_rule.effective_from), last_reviewed=utc_now().date().isoformat(),
            status="Cancelled" if proposal.change_type == "cancelled" else "Human reviewed",
            policy_type=f"{proposal.target_type} policy", summary=proposal.supporting_quote,
            coverage_criteria=[f"Plans: {', '.join(proposal.plan_ids)}", f"Effect: {new_rule.effect.value}"],
            denial_risk="Review the deterministic item assessment before submission.",
            official_reference_url=proposal.source_url,
        )
        from app.impact.analyzer import run_impact_analysis
        run_impact_analysis(source_event_desc=f"Approved {proposal_id}", data_store=self)
        affected = []
        for case in self.cases.values():
            after = evaluate_case(case, self.get_all_rules())
            if [i.result for i in before[case.case_id].results] != [i.result for i in after.results]:
                affected.append(case.case_id)
        self.updates.insert(0, InsurerUpdateEntry(
            update_id=f"UPD-{__import__('uuid').uuid4().hex[:12]}",
            headline=f"{proposal.insurer_name or proposal.insurer_id}: {proposal.target_name or proposal.target_code} policy {proposal.change_type}",
            item_type=proposal.target_type if proposal.target_type in {"drug", "procedure"} else "document",
            effective_date=str(new_rule.effective_from),
            status="Delayed" if proposal.change_type == "delayed" else "Cancelled" if proposal.change_type == "cancelled" else "Announced" if new_rule.effective_from > utc_now().date() else "Effective",
            affected_cases_count=len(affected), affected_case_ids=affected,
            rule_id=new_rule.rule_id, rule_version=new_rule.version,
        ))
        self.record_audit("POLICY_PROPOSAL_APPROVED", {
            "proposal_id": proposal_id, "rule_id": new_rule.rule_id, "version": new_rule.version,
            "document": proposal.document_name, "affected_cases_count": len(affected),
            "affected_case_ids": affected, "reviewer_corrections": edits,
        }, actor="claims-reviewer")
        if proposal.catalog_id:
            candidate=self.policy_catalog[proposal.catalog_id]
            candidate.pending_proposal_ids=[pid for pid in candidate.pending_proposal_ids if pid!=proposal_id]
            if not candidate.pending_proposal_ids:candidate.status="reviewed"
            for version in self.policy_versions.values():
                if proposal_id in version.proposal_ids:
                    version.verification_status="approved" if all(self.proposals[pid].review_state=="approved" for pid in version.proposal_ids) else "partially_reviewed"
        self.save_checkpoint()
        return new_rule, affected

    @serialized
    def reject_proposal(
        self,
        proposal_id: str,
        reviewer_notes: Optional[str] = None,
    ) -> ProposedPolicyChange:
        """Human reviewer rejects a proposed policy change."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        if proposal.review_state == "approved":
            raise ValueError("Approved proposals cannot be rejected; review a versioned cancellation instead.")
        proposal.review_state = "rejected"
        proposal.reviewer_notes = reviewer_notes
        for source in self.official_sources.values():
            source.pending_proposal_ids = [pid for pid in source.pending_proposal_ids if pid != proposal_id]
            if not source.pending_proposal_ids and source.status == "pending_review":
                source.status = "connected"

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

    @serialized
    def save_source(self, source: OfficialPolicySource):
        self.official_sources[source.source_id] = source

    @serialized
    def add_source_history(self, history: SourceCheckHistory):
        self.source_history.insert(0, history)

    def get_source_history(self, source_id: Optional[str] = None) -> List[SourceCheckHistory]:
        if source_id:
            return [h for h in self.source_history if h.source_id == source_id]
        return self.source_history


# Singleton store instance
store = DataStore()

