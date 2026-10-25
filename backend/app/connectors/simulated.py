"""The same discovery/download contract, against a separate loopback-only simulator."""

import os, json
from urllib.parse import urlparse
import httpx
from app.connectors.policy_base import InsurerPolicyConnector, PolicyDownload
from app.connectors.base import SourceAccessError, SourceError
from app.domain.sync_models import PolicyCandidate, SyncSource


def simulator_url(service):
    default = (
        "http://127.0.0.1:8102" if service == "insurer" else "http://127.0.0.1:8101"
    )
    value = os.environ.get(
        f"COVERAGEGUARD_{service.upper()}_SIMULATOR_URL", default
    ).rstrip("/")
    p = urlparse(value)
    if (
        p.scheme != "http"
        or p.hostname != "127.0.0.1"
        or p.username
        or p.password
        or p.path
        or p.query
        or p.fragment
        or not p.port
    ):
        raise SourceAccessError(
            "Simulators must use an explicit 127.0.0.1 HTTP port, without a path or credentials."
        )
    return value


class SimulatedInsurerConnector(InsurerPolicyConnector):
    def __init__(self):
        self.base = simulator_url("insurer")
        self.source = SyncSource(
            source_id="demo-insurer-api",
            insurer_id="demo-multi",
            name="SIMULATED insurer rules service",
            index_url=self.base + "/policies",
            source_type="Independent local JSON API",
            is_synthetic=True,
            limitations=[
                "Synthetic UHC/Aetna/Anthem-CA/Medicare examples; no insurer partnership."
            ],
        )

    def get(self, path):
        try:
            with httpx.Client(
                timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                r = client.get(self.base + path)
                r.raise_for_status()
                if len(r.content) > 2 * 1024 * 1024:
                    raise SourceError("Simulator response exceeds bound.")
                body = r.json()
        except httpx.HTTPError:
            raise SourceError("SIMULATED insurer service unavailable.") from None
        if body.get("simulation") is not True:
            raise SourceError("Simulator response lacks explicit synthetic marker.")
        return body

    def discover(self):
        results = []
        for row in self.get("/policies")["policies"]:
            pid = row["policy_id"]
            # Never trust a service-supplied URL for subsequent requests.
            if not __import__("re").fullmatch(r"[A-Z0-9-]+", pid):
                raise SourceError("Invalid synthetic policy identity.")
            results.append(
                PolicyCandidate(
                    catalog_id=f"demo-insurer-api:{pid}",
                    source_id=self.source.source_id,
                    insurer_id=row["insurer_id"],
                    insurer_name=row["insurer_name"],
                    policy_id=pid,
                    title=row["policy_title"],
                    source_url=self.base + "/policies/" + pid,
                    revision=str(row["version"]),
                    plan_ids=row["plan_ids"],
                    jurisdictions=row["jurisdictions"],
                    codes=[row["target_code"]],
                    code_system=row["code_system"],
                    scope_verified=True,
                    is_synthetic=True,
                )
            )
        return results

    def fetch(self, candidate):
        data = self.get("/policies/" + candidate.policy_id)
        return PolicyDownload(
            json.dumps(data, sort_keys=True).encode(),
            candidate.policy_id + ".json",
            "application/json",
            candidate.source_url,
            structured_rules=data["rules"],
        )
