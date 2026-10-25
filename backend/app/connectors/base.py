"""
Base connector interface for official external policy sources.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional


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
        """
        Computes SHA-256 content fingerprint for change detection.
        For HTML/web documents, normalizes away dynamic security nonces and scripts
        so only substantive policy text changes trigger alerts.
        """
        import re
        try:
            text = content.decode("utf-8", errors="ignore")
            if "<html" in text.lower() or "<!doctype" in text.lower() or "<body" in text.lower():
                clean_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r"<[^>]+>", " ", clean_text)
                clean_text = " ".join(clean_text.split())
                return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        except Exception:
            pass
        return hashlib.sha256(content).hexdigest()
