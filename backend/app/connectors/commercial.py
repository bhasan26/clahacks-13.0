"""Public commercial indexes are discovery evidence, never member benefit verification."""

import os
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.connectors.policy_base import InsurerPolicyConnector, PolicyDownload
from app.connectors.policy_http import PolicyHTTP, validate_url
from app.connectors.base import SourceError, SourceAccessError
from app.domain.sync_models import SyncSource, PolicyCandidate

UHC_INDEX = "https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html"
AETNA_INDEX = "https://www.aetna.com/health-care-professionals/clinical-policy-bulletins/medical-clinical-policy-bulletins.html"
BCBS_INDEX = "https://www.anthem.com/ca/provider/policies/clinical-guidelines/?cnslocale=en_US_ca"


class SourceAuthorizationRequired(SourceAccessError):
    pass


class PublicIndexConnector(InsurerPolicyConnector):
    def __init__(self, source, hosts):
        self.source = source
        self.http = PolicyHTTP(hosts)
        if source.insurer_id in {"uhc", "aetna"}:
            self.authorization_key = (
                f"COVERAGEGUARD_{source.insurer_id.upper()}_AUTHORIZATION_REFERENCE"
            )
            self.source.limitations.append(
                "Automated indexing requires publisher permission under the published terms; this connector is disabled until an operator supplies an authorization reference. Technical public accessibility is not permission."
            )
            if not os.environ.get(self.authorization_key):
                self.source.status = "authorization_required"
        else:
            self.authorization_key = None

    def _assert_access(self):
        if self.authorization_key and not os.environ.get(self.authorization_key):
            raise SourceAuthorizationRequired(
                f"Publisher authorization is required for automated indexing. Configure {self.authorization_key} only after obtaining permission."
            )

    def links(self):
        self._assert_access()
        data, _, url = self.http.get(self.source.index_url)
        soup = BeautifulSoup(data, "html.parser")
        return soup, [
            (a.get_text(" ", strip=True), urljoin(url, a["href"]))
            for a in soup.select("a[href]")
        ]

    def candidate(self, title, url):
        validate_url(url, self.http.hosts)
        policy_id = urlparse(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return PolicyCandidate(
            catalog_id=f"{self.source.source_id}:{policy_id}",
            source_id=self.source.source_id,
            insurer_id=self.source.insurer_id,
            insurer_name=self.source.name,
            policy_id=policy_id,
            title=title,
            source_url=url,
            document_type="public_medical_policy",
            jurisdictions=self.source.jurisdictions,
            metadata={
                "scope_limitations": "Member benefit plan, clinical criteria and effective date must be separately verified."
            },
        )

    def fetch(self, candidate):
        self._assert_access()
        data, headers, url = self.http.get(candidate.source_url, use_cache=False)
        mime = headers.get("content-type", "").split(";")[0]
        if data.startswith(b"%PDF-"):
            mime = "application/pdf"
        if mime not in {"application/pdf", "text/html", "application/xhtml+xml"}:
            raise SourceError("Unsupported official policy content type.")
        ext = "pdf" if mime == "application/pdf" else "html"
        return PolicyDownload(data, f"{candidate.policy_id}.{ext}", mime, url)


class UHCConnector(PublicIndexConnector):
    def __init__(self):
        super().__init__(
            SyncSource(
                source_id="uhc-public",
                insurer_id="uhc",
                name="UnitedHealthcare public commercial policies",
                index_url=UHC_INDEX,
                source_type="HTML index / PDF",
                limitations=[
                    "Commercial index only; specific member plan and exclusions are not verified by a public PDF."
                ],
            ),
            {"www.uhcprovider.com"},
        )

    def discover(self):
        _, links = self.links()
        return list(
            {
                url: self.candidate(title, url)
                for title, url in links
                if "/public/policies/comm-medical-drug/" in url
                and urlparse(url).path.endswith(".pdf")
                and "archive" not in url
            }.values()
        )[:500]


class AetnaConnector(PublicIndexConnector):
    def __init__(self):
        super().__init__(
            SyncSource(
                source_id="aetna-public",
                insurer_id="aetna",
                name="Aetna public Clinical Policy Bulletins",
                index_url=AETNA_INDEX,
                source_type="Published XML index / HTML",
                limitations=[
                    "CPBs describe medical necessity; member plan benefits, state deviations and prior authorization require separate verification."
                ],
            ),
            {"www.aetna.com"},
        )

    def discover(self):
        soup, _ = self.links()
        feed = next(
            (
                node["data-xmlfile"]
                for node in soup.select("[data-xmlfile]")
                if "mcpb-alpha.xml" in node["data-xmlfile"]
            ),
            None,
        )
        if not feed:
            return []
        data, _, url = self.http.get(urljoin(self.source.index_url, feed))
        # Parse the publisher's structured XML using a parser that cannot resolve external entities.
        import xml.etree.ElementTree as ET

        root = ET.fromstring(data)
        candidates = {}
        for node in root.iter():
            fields = {
                child.tag.lower(): "".join(child.itertext()).strip() for child in node
            }
            link = fields.get("url")
            title = fields.get("name") or fields.get("text") or fields.get("title")
            if link and title:
                target = urljoin("https://www.aetna.com", link)
                if "/cpb/medical/data/" in target and target.endswith(".html"):
                    candidates[target] = self.candidate(title, target)
        return list(candidates.values())[:3000]


class AnthemCAConnector(PublicIndexConnector):
    def __init__(self):
        super().__init__(
            SyncSource(
                source_id="anthem-ca-public",
                insurer_id="bcbs-anthem-ca",
                name="Anthem Blue Cross — California",
                index_url=BCBS_INDEX,
                source_type="Regional HTML policy directory",
                jurisdictions=["CA"],
                limitations=[
                    "California affiliate only. Generic BCBS identity cannot select this source. Publisher robots restrictions may prevent automated policy/PDF retrieval; no bypass is attempted."
                ],
            ),
            {"www.anthem.com"},
        )

    def discover(self):
        _, links = self.links()
        candidates = {}
        for title, url in links:
            if urlparse(url).hostname != "www.anthem.com":
                continue
            if (
                "medicalpolic" in url.lower() or urlparse(url).path.endswith(".pdf")
            ) and title:
                candidates[url] = self.candidate(title, url)
        return list(candidates.values())[:300]
