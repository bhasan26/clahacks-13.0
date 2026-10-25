"""
Domain models for CoverageGuard.
Matches the specification:
- Statuses: Approved, Needs attention, Missing or wrong info
- Items results: Covered, Not covered, Prior approval needed, Document missing, Value wrong, No rule found
- 5 Specialties: Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology
- 40 Cases, 6 Updates
"""

import re
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuleCategory(str, Enum):
    DRUG = "drug"
    PROCEDURE = "procedure"
    SERVICE = "service"
    REQUIRED_DOCUMENT = "document"
    PRIOR_APPROVAL = "approval"


class RuleEffect(str, Enum):
    COVERED = "covered"
    EXCLUDED = "excluded"
    REQUIRES_PRIOR_APPROVAL = "requires_prior_approval"
    REQUIRES_DOCUMENTS = "requires_documents"


class RuleStatus(str, Enum):
    ANNOUNCED = "announced"
    EFFECTIVE = "effective"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class Target(BaseModel):
    code_system: Optional[str] = None
    type: str  # "drug" | "procedure" | "service"
    code: str
    name: Optional[str] = None


class Rule(BaseModel):
    requires_billing_articles: bool = False
    billing_articles_verified: bool = False
    jurisdictions: List[str] = Field(default_factory=list)
    scope_verified: bool = True
    verification_status: str = "approved"
    catalog_id: Optional[str] = None
    source_revision: Optional[str] = None
    source_synced_at: Optional[datetime] = None
    rule_id: str
    version: int
    insurer_id: str
    plan_ids: List[str] = Field(default_factory=list)
    category: RuleCategory
    target: Target
    effect: RuleEffect
    conditions: Optional[Dict[str, Any]] = None
    status: RuleStatus
    effective_from: date
    effective_to: Optional[date] = None
    source_ref: str
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    official_reference_url: Optional[str] = None
    bulletin_summary: Optional[str] = None
    action_guidance: Optional[List[str]] = None
    received_at: datetime = Field(default_factory=utc_now)
    change_type: str = "new_rule"
    replaces_version: Optional[int] = None
    is_synthetic: bool = False


class Diagnosis(BaseModel):
    code: str
    description: Optional[str] = None


class CaseItem(BaseModel):
    code_system: Optional[str] = None
    type: str  # "drug" | "procedure" | "service"
    code: str
    name: Optional[str] = None
    quantity: Optional[int] = 1


# Standard plain status strings:
# "Approved" | "Needs attention" | "Missing or wrong info"
CaseStatusType = Literal["Approved", "Needs attention", "Missing or wrong info"]


class Case(BaseModel):
    jurisdiction: Optional[str] = None
    policy_environment: Literal["official", "demo"] = "demo"
    is_synthetic: bool = True
    case_id: str
    insurer_id: str = ""
    insurer_name: Optional[str] = None
    plan_id: str = ""
    member_ref: str
    group_number: Optional[str] = None
    specialty: str = "Cardiology"  # Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology
    service_date: Optional[date] = None
    visit_type: str = "outpatient"
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    items: List[CaseItem] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    prior_approval_ref: Optional[str] = None
    status: CaseStatusType = "Approved"
    intake_source: Optional[Literal["patient_intake"]] = None  # set for claims filed via the intake form
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


_LEGACY_UPLOAD_ID = re.compile(r"^(?:UPLOAD-.+|C-[0-9A-F]{12})$")


def is_uploaded_case(case: Case) -> bool:
    """Claims filed through intake (older uploads are recognized by their generated IDs)."""
    return case.intake_source == "patient_intake" or bool(_LEGACY_UPLOAD_ID.match(case.case_id))


# Standard item-level results:
# Covered, Not covered, Prior approval needed, Document missing, Value wrong
ItemResultType = Literal[
    "Covered",
    "Not covered",
    "Prior approval needed",
    "Document missing",
    "Value wrong",
    "No rule found, verify with the insurer",
]


class ItemVerdict(BaseModel):
    item: CaseItem
    result: ItemResultType
    rule_id: Optional[str] = None
    rule_version: Optional[int] = None
    effective_date: Optional[str] = None
    plain_sentence: str  # "Drug X is not covered from 1 Nov 2026."
    rule_reference: str  # "Rule R-1042."
    what_to_do: str      # "Review with the physician before submitting."
    full_issue_text: str # Plain single sentence combining statement, rule reference, and action
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    official_reference_url: Optional[str] = None
    why_not_approved: Optional[str] = None
    bulletin_summary: Optional[str] = None
    action_guidance: Optional[List[str]] = None


class PolicyBulletin(BaseModel):
    rule_id: str
    title: str
    insurer_name: str
    effective_date: str
    last_reviewed: str
    status: str
    policy_type: str
    summary: str
    coverage_criteria: List[str]
    denial_risk: str
    official_reference_url: Optional[str] = None


class CaseCheckResult(BaseModel):
    case_id: str
    specialty: str
    status: CaseStatusType
    items_count: int
    results: List[ItemVerdict]
    checked_at: datetime = Field(default_factory=utc_now)


class InsurerUpdateEntry(BaseModel):
    update_id: str
    headline: str
    item_type: Literal["drug", "procedure", "document", "approval"]
    effective_date: str
    status: Literal["Announced", "Effective", "Delayed", "Cancelled"]
    affected_cases_count: int
    affected_case_ids: List[str] = Field(default_factory=list)
    rule_id: str
    rule_version: int
    published_at: datetime = Field(default_factory=utc_now)


class InsurerConnectionInfo(BaseModel):
    insurer_name: str = "Demo Insurance Co."
    status: str = "Connected"
    access_status: str = "Access active"
    read_only: bool = True  # "Read-only" appears only in the popover
    last_check_time: str = "06:00 today"
    is_check_failed: bool = False
    warning_banner: Optional[str] = None


# ---------------------------------------------------------------------------
# Alerts & Lifecycle
# ---------------------------------------------------------------------------
class VerdictType(str, Enum):
    COVERED = "covered"
    EXCLUDED = "excluded"
    PRIOR_APPROVAL_NEEDED = "prior_approval_needed"
    DOCUMENTS_MISSING = "documents_missing"
    NO_RULE_FOUND = "no_rule_found"
    CANNOT_ASSESS = "cannot_assess"


class SeverityType(str, Enum):
    CLEAR = "clear"
    ACTION_NEEDED = "action_needed"
    VERIFY = "verify"
    INFO = "info"


class AlertChange(BaseModel):
    from_version: Optional[int] = None
    to_version: int
    change_type: Optional[str] = None
    details: Optional[str] = None


class AlertStatus(str, Enum):
    OPEN = "open"
    SUPERSEDED = "superseded"
    CLOSED = "closed"


class AlertTask(BaseModel):
    task_id: str
    title: str
    status: Literal["open", "in_progress", "completed"] = "open"
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None


class Alert(BaseModel):
    alert_id: str
    case_id: str
    item_code: str
    rule_id: str
    change: AlertChange
    status: AlertStatus = AlertStatus.OPEN
    supersedes: Optional[str] = None
    closed_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    headline: Optional[str] = None
    explanation: Optional[str] = None
    suggested_action: Optional[str] = None
    acknowledged: bool = False
    officer_note: Optional[str] = None
    evidence_quote: Optional[str] = None
    effective_date: Optional[str] = None
    source_document: Optional[str] = None
    tasks: List[AlertTask] = Field(default_factory=list)
    draft_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Multimodal Policy Intelligence & Human Review
# ---------------------------------------------------------------------------
ReviewStateType = Literal["pending_review", "approved", "rejected", "needs_correction"]
PolicyChangeType = Literal["new_rule", "modification", "delayed", "cancelled"]


class ProposedPolicyChange(BaseModel):
    requires_billing_articles: bool = False
    billing_articles_verified: bool = False
    jurisdictions: List[str] = Field(default_factory=list)
    code_system: Optional[str] = None
    scope_verified: bool = True
    catalog_id: Optional[str] = None
    source_revision: Optional[str] = None
    source_synced_at: Optional[datetime] = None
    proposal_id: str
    document_id: str
    document_name: str
    source_url: Optional[str] = None
    evidence_verified: bool = False
    evidence_confirmed_by_reviewer: bool = False
    extraction_method: Optional[str] = None
    is_synthetic: bool = False
    insurer_id: Optional[str] = None
    insurer_name: Optional[str] = None
    plan_ids: List[str] = Field(default_factory=list)
    policy_title: Optional[str] = None
    policy_reference: Optional[str] = None
    target_type: Optional[Literal["drug", "procedure", "service"]] = None
    target_code: Optional[str] = None
    target_name: Optional[str] = None
    previous_effect: Optional[str] = None
    proposed_effect: Optional[RuleEffect] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    change_type: PolicyChangeType = "new_rule"
    conditions: Optional[Dict[str, Any]] = None
    supporting_quote: str = ""
    source_page: int = 1
    confidence: Optional[float] = None
    validation_warnings: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    is_complete: bool = False
    requires_code_mapping: bool = False
    review_state: ReviewStateType = "pending_review"
    reviewer_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: Optional[datetime] = None
    resulting_rule_id: Optional[str] = None
    resulting_rule_version: Optional[int] = None


class PolicyDiff(BaseModel):
    proposal_id: str
    has_existing_rule: bool
    existing_rule_id: Optional[str] = None
    existing_rule_version: Optional[int] = None
    previous_effect: Optional[str] = None
    proposed_effect: Optional[str] = None
    previous_effective_from: Optional[str] = None
    proposed_effective_from: Optional[str] = None
    is_delay: bool = False
    is_cancellation: bool = False
    diff_summary: str
    change_category: str


class ImpactCaseItem(BaseModel):
    case_id: str
    member_ref: str
    specialty: str
    service_date: str
    item_code: str
    item_name: str
    previous_verdict: str
    simulated_verdict: str
    reason: str
    supporting_quote: Optional[str] = None
    action_steps: List[str] = Field(default_factory=list)


class ImpactPreviewResult(BaseModel):
    total_cases_checked: int
    affected_cases: int
    new_risks: int
    unchanged_cases: int
    cases: List[ImpactCaseItem]
    simulation_timestamp: datetime = Field(default_factory=utc_now)
    is_demo_mode: bool = False
    notice: Optional[str] = None


class ExtractedDocumentResult(BaseModel):
    document_id: str
    filename: str
    file_type: str
    page_count: int
    pages_text: List[Dict[str, Any]]
    raw_text: str
    proposals: List[ProposedPolicyChange]
    diffs: List[PolicyDiff]
    impact_preview: Optional[ImpactPreviewResult] = None
    extracted_at: datetime = Field(default_factory=utc_now)
    extraction_method: Optional[str] = None
    extraction_error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Official External Policy Source Monitoring (Feature 8)
# ---------------------------------------------------------------------------
class OfficialPolicySource(BaseModel):
    source_id: str
    name: str
    insurer_name: str
    official_url: str
    policy_scope: str = "National Coverage Determinations & Clinical Bulletins"
    last_checked_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    downloaded_content_hash: Optional[str] = None
    fetched_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    last_check_simulated: bool = False
    status: Literal["active", "connected", "checking", "unchanged", "change_detected", "error", "fetched", "processing", "pending_review", "extraction_failed", "source_unavailable", "disabled"] = "active"
    latest_document_title: Optional[str] = None
    pending_proposal_ids: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    is_real_external_source: bool = True
    source_type: str = "official_portal"


class SourceCheckHistory(BaseModel):
    check_id: str
    source_id: str
    source_name: Optional[str] = None
    checked_at: datetime = Field(default_factory=utc_now)
    status: str
    content_hash: Optional[str] = None
    changed: bool = False
    summary: str
    proposals_created: List[str] = Field(default_factory=list)
    affected_claims_count: int = 0
    error_message: Optional[str] = None
    is_simulated: bool = False


