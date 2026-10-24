"""
Contract-first Pydantic domain models for CoverageGuard.
Matches the project contract defined in project.md / Appendix A.
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
    REQUIRED_DOCUMENT = "required_document"
    PRIOR_APPROVAL = "prior_approval"


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
    received_at: datetime = Field(default_factory=utc_now)


class Diagnosis(BaseModel):
    code: str
    description: Optional[str] = None


class CaseItem(BaseModel):
    type: str  # "drug" | "procedure" | "service"
    code: str
    name: Optional[str] = None
    quantity: Optional[int] = 1


class Case(BaseModel):
    case_id: str
    insurer_id: str
    plan_id: str
    member_ref: str
    service_date: date
    visit_type: str = "outpatient"  # "outpatient" | "inpatient" | "emergency"
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    items: List[CaseItem] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    prior_approval_ref: Optional[str] = None
    status: Literal["open", "submitted", "closed"] = "open"
    officer_id: Optional[str] = "officer-1"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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


class ItemVerdict(BaseModel):
    item: CaseItem
    verdict: VerdictType
    severity: SeverityType
    rule_id: Optional[str] = None
    rule_version: Optional[int] = None
    effective_from: Optional[date] = None
    source_ref: Optional[str] = None
    explanation: str
    suggested_officer_action: Optional[str] = None


class CaseOverallStatus(str, Enum):
    CLEAR = "clear"
    NEEDS_ATTENTION = "needs_attention"
    CANNOT_ASSESS = "cannot_assess"


class CaseCheckResult(BaseModel):
    case_id: str
    governing_date: date
    overall_status: CaseOverallStatus
    results: List[ItemVerdict]
    checked_at: datetime = Field(default_factory=utc_now)


class AlertChange(BaseModel):
    from_version: Optional[int] = None
    to_version: int
    change_type: Optional[str] = None
    details: Optional[str] = None


class AlertStatus(str, Enum):
    OPEN = "open"
    SUPERSEDED = "superseded"
    CLOSED = "closed"


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


class InsurerChangeEvent(BaseModel):
    event_id: str
    published_at: datetime = Field(default_factory=utc_now)
    change_type: Literal["added", "modified", "status_changed", "delayed", "cancelled"]
    rule: Rule
    previous: Optional[Dict[str, Any]] = None
