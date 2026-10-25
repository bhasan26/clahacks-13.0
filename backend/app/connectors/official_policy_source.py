"""
Official Insurer Policy Connector for CMS Medicare Coverage Database.
Retrieves authorized, publicly accessible National Coverage Determinations (NCDs)
and transmittal announcements from Centers for Medicare & Medicaid Services (CMS).
"""

import httpx
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse

from app.connectors.base import (
    PolicySourceConnector,
    SourceError,
    SourceTimeoutError,
    SourceAccessError,
)

# Standard official public CMS Medicare policy source
DEFAULT_CMS_SOURCE_URL = "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=372"
USER_AGENT = "CoverageGuard-PolicyIntelligence/1.0 (Public Health Policy Adjudication; +https://github.com/bhasan26/clahacks-13.0)"


class CMSMedicareConnector(PolicySourceConnector):
    """
    Connects to official CMS (Centers for Medicare & Medicaid Services)
    public National Coverage Determinations (NCDs).
    """

    def fetch_latest_document(
        self,
        url: Optional[str] = None,
    ) -> Tuple[bytes, str, Dict[str, str]]:
        target_url = url or DEFAULT_CMS_SOURCE_URL

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                resp = client.get(target_url, headers=headers)
                if resp.status_code == 200:
                    content_bytes = resp.content
                    meta = {
                        "content_type": resp.headers.get("content-type", "text/html"),
                        "content_length": str(len(content_bytes)),
                        "etag": resp.headers.get("etag", ""),
                        "last_modified": resp.headers.get("last-modified", ""),
                        "source_url": target_url,
                    }
                    filename = f"cms_ncd_{urlparse(target_url).query or 'policy'}.html"
                    return content_bytes, filename, meta
                elif resp.status_code in [401, 403]:
                    raise SourceAccessError(
                        f"Access to official source was restricted (HTTP {resp.status_code}). "
                        "CoverageGuard respects all access controls and does not bypass paywalls or anti-bot protections."
                    )
                else:
                    raise SourceAccessError(f"Official source returned HTTP {resp.status_code}: {resp.reason_phrase}")
        except httpx.TimeoutException as e:
            raise SourceTimeoutError(f"Connection to official insurer source timed out after {self.timeout_seconds}s: {e}")
        except httpx.RequestError as e:
            raise SourceError(f"Network error connecting to official insurer source: {e}")
