"""
Base connector interface for official external policy sources.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Tuple, Dict


class SourceError(Exception):
    """Base error for official source connectors."""
    pass


class SourceTimeoutError(SourceError):
    """Raised when an official source times out."""
    pass


class SourceAccessError(SourceError):
    """Raised when an official source returns 4xx/5xx or blocked."""
    pass


class PolicySourceConnector(ABC):
    """Abstract connector for official insurer policy portals and feeds."""

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def fetch_latest_document(self, url: str) -> Tuple[bytes, str, Dict[str, str]]:
        """
        Retrieves official policy document content.
        Returns: (document_bytes, content_title_or_filename, metadata)
        """
        pass

    @staticmethod
    def compute_fingerprint(content: bytes) -> str:
        """Raw downloaded-byte hash. Meaningful policy normalization is separate."""
        return hashlib.sha256(content).hexdigest()
