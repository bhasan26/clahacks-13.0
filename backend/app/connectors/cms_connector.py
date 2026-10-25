"""CMS Coverage API v1 endpoints inspected in its published OpenAPI schema.
Catalog endpoints provide metadata; LCD jurisdiction/articles remain required gaps
until separately retrieved and verified. No fabricated nationwide LCD scope.
"""

import json, os
from datetime import datetime
from urllib.parse import urlencode
from app.connectors.policy_base import InsurerPolicyConnector, PolicyDownload
from app.connectors.policy_http import PolicyHTTP, validate_url
from app.connectors.base import SourceError
from app.domain.sync_models import PolicyCandidate, SyncSource

BASE = "https://api.coverage.cms.gov"


def parse_date(value):
    if not value:
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:10], pattern).date()
        except ValueError:
            pass
    return None


class CMSCoverageConnector(InsurerPolicyConnector):
    def __init__(self):
        self.source = SyncSource(
            source_id="cms-api",
            insurer_id="cms",
            name="CMS Medicare Coverage API",
            index_url=BASE + "/docs/",
            source_type="Documented JSON API",
            limitations=[
                "Original Medicare only; NCD metadata does not identify every billing code. LCD applicability requires verified MAC jurisdiction and associated billing articles. Licensed endpoints require an operator-supplied token."
            ],
        )
        self.http = PolicyHTTP(
            {"api.coverage.cms.gov", "www.cms.gov"}, api_hosts={"api.coverage.cms.gov"}
        )

    def _json(self, url):
        token = os.environ.get("CMS_LICENSE_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        data, _, _ = self.http.get(url, headers=headers, use_cache=False)
        body = json.loads(data)
        if body.get("meta", {}).get("status", {}).get("id", 200) != 200:
            raise SourceError("CMS API reported an unsuccessful response.")
        return body

    def _pages(self, path):
        url = BASE + path
        # The inspected report schemas have no page-number argument. Follow only
        # an explicit HTTPS next URL; an opaque token is not guessed into a parameter.
        seen = set()
        for _ in range(5):
            if url in seen:
                raise SourceError("CMS pagination repeated a page.")
            seen.add(url)
            body = self._json(url)
            yield from body.get("data", [])
            next_token = body.get("meta", {}).get("next_token")
            if not next_token:
                return
            if not str(next_token).startswith(BASE + "/v1/"):
                raise SourceError(
                    "CMS returned an opaque pagination token without a documented continuation parameter. Catalog incomplete."
                )
            url = validate_url(next_token, self.http.hosts)
        raise SourceError("CMS catalog pagination bound reached; catalog incomplete.")

    def discover(self):
        results = []
        for kind, path in [
            ("NCD", "/v1/reports/national-coverage-ncd/"),
            ("LCD", "/v1/reports/local-coverage-final-lcds/"),
        ]:
            for row in self._pages(path):
                pid = str(row["document_id"])
                rev = str(row.get("document_version") or "")
                params = (
                    {"ncdid": pid, "ncdver": rev}
                    if kind == "NCD"
                    else {"lcdid": pid, "ver": rev}
                )
                detail = BASE + f"/v1/data/{kind.lower()}/?" + urlencode(params)
                results.append(
                    PolicyCandidate(
                        catalog_id=f"cms-api:{kind}:{pid}",
                        source_id="cms-api",
                        insurer_id="cms",
                        insurer_name="CMS Original Medicare",
                        policy_id=f"{kind}-{pid}",
                        title=row["title"],
                        source_url=detail,
                        document_type=kind,
                        revision=rev,
                        published_at=row.get("last_updated") or row.get("updated_on"),
                        effective_from=parse_date(row.get("effective_date")),
                        effective_to=parse_date(row.get("retirement_date")),
                        requires_billing_articles=kind == "LCD",
                        metadata={
                            "publisher_document_url": row.get("url"),
                            "contractor": row.get("contractor_name_type"),
                            "jurisdiction_verified": False if kind == "LCD" else None,
                        },
                    )
                )
        return results

    def fetch(self, candidate):
        body = self._json(candidate.source_url)
        if candidate.document_type == "LCD":
            lcdid = candidate.policy_id.removeprefix("LCD-")
            related = self._related(
                "/v1/data/lcd/related-documents", lcdid, candidate.revision
            )
            jurisdiction = self._related(
                "/v1/data/lcd/primary-jurisdiction", lcdid, candidate.revision
            )
            states = self._json(BASE + "/v1/metadata/states/").get("data", [])
            state_names = {row["state_id"]: row["description"] for row in states}
            names = "Alabama:AL,Alaska:AK,Arizona:AZ,Arkansas:AR,California:CA,Colorado:CO,Connecticut:CT,Delaware:DE,Florida:FL,Georgia:GA,Hawaii:HI,Idaho:ID,Illinois:IL,Indiana:IN,Iowa:IA,Kansas:KS,Kentucky:KY,Louisiana:LA,Maine:ME,Maryland:MD,Massachusetts:MA,Michigan:MI,Minnesota:MN,Mississippi:MS,Missouri:MO,Montana:MT,Nebraska:NE,Nevada:NV,New Hampshire:NH,New Jersey:NJ,New Mexico:NM,New York:NY,North Carolina:NC,North Dakota:ND,Ohio:OH,Oklahoma:OK,Oregon:OR,Pennsylvania:PA,Rhode Island:RI,South Carolina:SC,South Dakota:SD,Tennessee:TN,Texas:TX,Utah:UT,Vermont:VT,Virginia:VA,Washington:WA,West Virginia:WV,Wisconsin:WI,Wyoming:WY,District of Columbia:DC,Puerto Rico:PR"
            abbreviations = {
                name.casefold(): code
                for name, code in (part.split(":") for part in names.split(","))
            }
            candidate.jurisdictions = sorted(
                {
                    abbreviations[name.casefold()]
                    for row in jurisdiction
                    if (name := state_names.get(row["state_id"]))
                    and name.casefold() in abbreviations
                }
            )
            candidate.metadata["jurisdiction_records"] = jurisdiction
            candidate.metadata["jurisdiction_verified"] = bool(candidate.jurisdictions)
            candidate.metadata["associated_billing_articles"] = [
                row for row in related if row.get("r_article_id")
            ]
            candidate.metadata["article_review_required"] = True
            body["related_documents"] = related
            body["jurisdiction"] = jurisdiction
        return PolicyDownload(
            json.dumps(body, sort_keys=True).encode(),
            f"{candidate.policy_id}.json",
            "application/json",
            candidate.source_url,
        )

    def _related(self, path, lcdid, ver):
        params = {"lcdid": lcdid, "ver": ver, "page_size": "100"}
        seen = set()
        rows = []
        for _ in range(5):
            body = self._json(BASE + path + "?" + urlencode(params))
            rows.extend(body.get("data", []))
            token = body.get("meta", {}).get("next_token")
            if not token:
                return rows
            if token in seen:
                raise SourceError("CMS related metadata pagination repeated a token.")
            seen.add(token)
            params["next_token"] = token
        raise SourceError("CMS related metadata pagination bound reached.")
