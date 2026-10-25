"""Policy metadata contains no hospital-side patient/claim records."""

from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.domain.models import utc_now


class PolicyCandidate(BaseModel):
    catalog_id: str
    source_id: str
    insurer_id: str
    insurer_name: str
    policy_id: str
    title: str
    source_url: str
    document_type: str = "policy"
    revision: Optional[str] = None
    published_at: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    plan_ids: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    codes: list[str] = Field(default_factory=list)
    code_system: Optional[str] = None
    category: Optional[str] = None
    scope_verified: bool = False
    requires_billing_articles: bool = False
    is_synthetic: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_seen_at: datetime = Field(default_factory=utc_now)
    last_successful_sync: Optional[datetime] = None
    processed_hash: Optional[str] = None
    downloaded_hash: Optional[str] = None
    status: str = "discovered"
    pending_proposal_ids: list[str] = Field(default_factory=list)
    last_error: Optional[str] = None
    document_id: Optional[str] = None


class PolicyDocumentVersion(BaseModel):
    version_id: str
    catalog_id: str
    content_hash: str
    source_url: str
    original_document_ref: str
    raw_text: str
    revision: Optional[str] = None
    fetched_at: datetime = Field(default_factory=utc_now)
    extraction_method: str
    proposal_ids: list[str] = Field(default_factory=list)
    verification_status: str = "pending_review"


class SyncSource(BaseModel):
    source_id: str
    insurer_id: str
    name: str
    index_url: str
    source_type: str
    jurisdictions: list[str] = Field(default_factory=list)
    is_synthetic: bool = False
    status: str = "unchecked"
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)
    consecutive_failures: int = 0
    counts: dict[str, int] = Field(default_factory=dict)


class SyncRun(BaseModel):
    run_id: str
    source_id: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    status: str = "running"
    discovered: int = 0
    fetched: int = 0
    changed: int = 0
    unchanged: int = 0
    pending_review: int = 0
    failed: int = 0
    gaps: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    is_synthetic: bool = False
