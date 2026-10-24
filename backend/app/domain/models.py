"""
Domain models for CoverageGuard.
Matches the specification:
- Statuses: Approved, Needs attention, Missing or wrong info
- Items results: Covered, Not covered, Prior approval needed, Document missing, Value wrong, No rule found
- 5 Specialties: Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology
- 40 Cases, 6 Updates
"""

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
    type: str  # "drug" | "procedure" | "service"
    code: str
    name: Optional[str] = None


class Rule(BaseModel):
    rule_id: str
    version: int
    insurer_id: str
    plan_ids: List[str] = Field(default_factory=lambda: ["*"])
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


class Diagnosis(BaseModel):
    code: str
    description: Optional[str] = None


class CaseItem(BaseModel):
    type: str  # "drug" | "procedure" | "service"
    code: str
    name: Optional[str] = None
    quantity: Optional[int] = 1


# Standard plain status strings:
# "Approved" | "Needs attention" | "Missing or wrong info"
CaseStatusType = Literal["Approved", "Needs attention", "Missing or wrong info"]


class Case(BaseModel):
    case_id: str
    insurer_id: str = "demo-insurer"
    insurer_name: Optional[str] = "Demo Insurance Co."
    plan_id: str = "PLAN-GOLD"
    member_ref: str
    group_number: Optional[str] = None
    specialty: str = "Cardiology"  # Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology
    service_date: date
    visit_type: str = "outpatient"
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    items: List[CaseItem] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    prior_approval_ref: Optional[str] = None
    status: CaseStatusType = "Approved"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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
