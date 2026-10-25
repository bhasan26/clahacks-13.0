"""Hospital-side import, policy synchronization, catalog and findings routes."""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx
from app.db.store import store, _STATE_LOCK
from app.domain.models import Case
from app.connectors.registry import ensure_sources
from app.connectors.sync_engine import sync_policies
from app.connectors.simulated import simulator_url
from app.engine.findings import claim_findings
from app.engine.checker import evaluate_case

router = APIRouter(prefix="/api")


class SyncPayload(BaseModel):
    source_id: str | None = None
    claim_id: str | None = None
    catalog_ids: list[str] = Field(default_factory=list, max_length=20)


@router.get("/policy-sync/sources")
def sources():
    ensure_sources(store)
    return {
        "scheduler_enabled": os.environ.get("COVERAGEGUARD_SCHEDULER_ENABLED", "false")
        == "true",
        "interval_seconds": int(
            os.environ.get("COVERAGEGUARD_CHECK_INTERVAL", "86400")
        ),
        "scheduler_sources": [
            s
            for s in os.environ.get("COVERAGEGUARD_SCHEDULER_SOURCES", "").split(",")
            if s
        ],
        "sources": list(store.sync_sources.values()),
    }


@router.post("/policy-sync/run")
def run_sync(payload: SyncPayload = SyncPayload()):
    if payload.claim_id and payload.claim_id not in store.cases:
        raise HTTPException(404, "Claim not found.")
    try:
        return sync_policies(payload.source_id, payload.claim_id, payload.catalog_ids)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/policy-sync/history")
def history():
    return sorted(store.sync_runs.values(), key=lambda r: r.started_at, reverse=True)[
        :100
    ]


@router.get("/policies/catalog")
def catalog(insurer_id: str | None = None, q: str | None = None):
    rows = list(store.policy_catalog.values())
    if insurer_id:
        rows = [r for r in rows if r.insurer_id == insurer_id]
    if q:
        rows = [
            r
            for r in rows
            if q.lower()
            in " ".join(
                [
                    r.title,
                    r.policy_id,
                    r.insurer_id,
                    r.insurer_name,
                    *r.codes,
                    *r.plan_ids,
                    *r.jurisdictions,
                ]
            ).lower()
        ]
    # Internal retained retry documents may contain large images; do not emit them in an index.
    return [
        r.model_copy(
            update={
                "metadata": {
                    k: v for k, v in r.metadata.items() if not k.startswith("_")
                }
            }
        )
        for r in rows[:500]
    ]


@router.get("/policies/catalog/{catalog_id}/versions")
def policy_versions(catalog_id: str):
    return [v for v in store.policy_versions.values() if v.catalog_id == catalog_id]


@router.get("/claims/findings")
def all_findings():
    return [claim_findings(c, store) for c in store.cases.values()]


@router.get("/claims/{claim_id}/findings")
def findings(claim_id: str):
    case = store.cases.get(claim_id)
    if not case:
        raise HTTPException(404, "Claim not found.")
    return claim_findings(case, store)


class ClaimImport(BaseModel):
    claims: list[Case] = Field(max_length=200)


@router.post("/claims/import")
def import_claims(payload: ClaimImport):
    if any(not c.is_synthetic for c in payload.claims):
        raise HTTPException(422, "Synthetic patient data only.")
    ids = []
    with _STATE_LOCK:
        for case in payload.claims:
            if "policy_environment" not in case.model_fields_set:
                case.policy_environment = "official"
            if not case.case_id:
                raise HTTPException(422, "Claim identity required.")
            # Reimporting a hospital record must not silently overwrite local employee changes.
            if case.case_id not in store.cases:
                case.status = evaluate_case(case, store.get_all_rules()).status
                store.cases[case.case_id] = case
            ids.append(case.case_id)
        store.record_audit(
            "HOSPITAL_CLAIMS_IMPORTED",
            {"count": len(ids), "case_ids": ids},
            actor="claims-officer",
        )
    return {
        "imported": len(ids),
        "case_ids": ids,
        "findings": [claim_findings(store.cases[cid], store) for cid in ids],
    }


@router.post("/demo/import-hospital")
def import_hospital():
    try:
        with httpx.Client(
            timeout=10, follow_redirects=False, trust_env=False
        ) as client:
            response = client.get(simulator_url("hospital") + "/pending-claims")
            response.raise_for_status()
            if len(response.content) > 2 * 1024 * 1024:
                raise ValueError()
            body = response.json()
        if body.get("simulation") is not True:
            raise ValueError()
        payload = ClaimImport.model_validate({"claims": body["claims"]})
    except Exception:
        raise HTTPException(
            502, "Independent SIMULATED hospital service unavailable or invalid."
        ) from None
    return import_claims(payload)


class Scenario(BaseModel):
    scenario: str


@router.post("/demo/publish-insurer")
def publish_insurer(payload: Scenario):
    if payload.scenario not in {"restriction", "delay", "reset"}:
        raise HTTPException(422, "Choose restriction, delay or reset.")
    # This is an explicit simulator-admin action, separate from every read-only connector.
    path = "/admin/reset" if payload.scenario == "reset" else "/admin/publish"
    try:
        with httpx.Client(
            timeout=10, follow_redirects=False, trust_env=False
        ) as client:
            response = client.post(
                simulator_url("insurer") + path,
                json=payload.model_dump(),
                headers={
                    "X-Simulator-Token": os.environ.get("SIMULATOR_ADMIN_TOKEN", "")
                },
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        raise HTTPException(
            502,
            "SIMULATED insurer publication failed. Ensure its separate service is running and scenario order is correct.",
        ) from None


@router.get("/workflow/summary")
def summary():
    ensure_sources(store)
    reports = all_findings()
    return {
        "pending_claims": len(reports),
        "needs_attention": sum(r["issues_count"] > 0 for r in reports),
        "unable_to_verify": sum(r["status"].startswith("Unable") for r in reports),
        "newly_affected_claims": len({a.case_id for a in store.get_open_alerts()}),
        "sources_healthy": sum(
            s.status in {"healthy", "simulated"} for s in store.sync_sources.values()
        ),
        "sync_failures": sum(
            s.status == "unavailable" or bool(s.last_error)
            for s in store.sync_sources.values()
        ),
        "policies_indexed": len(store.policy_catalog),
        "pending_reviews": sum(
            p.review_state in {"pending_review", "needs_correction"}
            for p in store.proposals.values()
        ),
        "sources": list(store.sync_sources.values()),
    }
