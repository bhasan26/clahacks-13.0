"""Bounded, HTTPS-only access to explicitly allowed public CMS sources."""
from typing import Optional
from urllib.parse import urlparse, urljoin
import httpx

from app.connectors.base import PolicySourceConnector, SourceError, SourceTimeoutError, SourceAccessError
from app.intelligence.document_processor import MAX_FILE_SIZE_BYTES, extract_policy_html, DocumentProcessingError

DEFAULT_CMS_SOURCE_URL = "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=372"
USER_AGENT = "CoverageGuard/1.0 (synthetic-data policy review; https://github.com/bhasan26/clahacks-13.0)"
ALLOWED_HOSTS = {"www.cms.gov", "cms.gov"}


def validate_official_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        allowed = parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS and parsed.port in {None, 443}
    except ValueError:
        allowed = False
    if not allowed or parsed.username or parsed.password or parsed.fragment:
        raise SourceAccessError("Source restricted to approved HTTPS CMS hosts and port 443.")
    return url


class CMSMedicareConnector(PolicySourceConnector):
    def _download(self, client, url):
        for _ in range(6):
            validate_official_url(url)
            response = client.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,text/plain"})
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise SourceError("Official source redirect omitted Location.")
                url = urljoin(url, location)
                continue
            if response.status_code != 200:
                raise SourceAccessError(f"Official source returned HTTP {response.status_code}; access may be restricted and CoverageGuard does not bypass paywalls.")
            content = response.content
            if not content or len(content) > MAX_FILE_SIZE_BYTES:
                raise SourceError("Official document is empty or exceeds the 10 MB processing limit.")
            kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content.startswith(b"%PDF-"):
                kind = "application/pdf"
            if kind not in {"text/html", "application/xhtml+xml", "text/plain", "application/pdf"}:
                raise SourceError("Official source returned an unsupported content type.")
            return content, kind, url, response.headers
        raise SourceError("Official source exceeded the redirect limit.")

    def fetch_latest_document(self, url: Optional[str] = None):
        original = validate_official_url(url or DEFAULT_CMS_SOURCE_URL)
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                content, kind, final_url, headers = self._download(client, original)
                if kind in {"text/html", "application/xhtml+xml"}:
                    text, _, links = extract_policy_html(content)
                    # A short official landing page with one PDF can delegate to the PDF pipeline.
                    if len(text) < 300 and len(links) == 1:
                        pdf_url = validate_official_url(urljoin(final_url, links[0]))
                        pdf_content, pdf_kind, pdf_final, pdf_headers = self._download(client, pdf_url)
                        if pdf_kind == "application/pdf":
                            content, kind, final_url, headers = pdf_content, pdf_kind, pdf_final, pdf_headers
                extension = "pdf" if kind == "application/pdf" else "txt" if kind == "text/plain" else "html"
                return content, f"cms_policy.{extension}", {
                    "content_type": kind, "content_length": str(len(content)),
                    "etag": headers.get("etag", ""), "last_modified": headers.get("last-modified", ""),
                    "source_url": original, "document_url": final_url,
                }
        except httpx.TimeoutException:
            raise SourceTimeoutError(f"Official source timed out after {self.timeout_seconds}s.") from None
        except (httpx.RequestError, DocumentProcessingError):
            raise SourceError("Official source could not be downloaded or parsed.") from None
