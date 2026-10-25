"""Pluggable insurer policy catalog interface, deliberately separate from claims."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from app.domain.sync_models import PolicyCandidate, SyncSource


@dataclass(frozen=True)
class PolicyQuery:
    insurer_id: str
    plan_id: str | None = None
    environment: str = "official"
    codes: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()


@dataclass
class PolicyDownload:
    content: bytes
    filename: str
    mime_type: str
    source_url: str
    structured_rules: list[dict] = field(default_factory=list)


class InsurerPolicyConnector(ABC):
    source: SyncSource

    @abstractmethod
    def discover(self) -> list[PolicyCandidate]: ...
    @abstractmethod
    def fetch(self, candidate: PolicyCandidate) -> PolicyDownload: ...
