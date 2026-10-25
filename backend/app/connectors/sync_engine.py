"""Caseload-filtered discovery and retry-safe document staging. No claim data is sent out."""

import hashlib, json, os, re, threading, uuid
from datetime import timedelta
from app.domain.models import ProposedPolicyChange, ExtractedDocumentResult, utc_now
from app.domain.sync_models import SyncRun, PolicyDocumentVersion
from app.db.store import store, _STATE_LOCK
from app.connectors.commercial import SourceAuthorizationRequired
from app.connectors.base import SourceAccessError
from app.connectors.registry import connector_registry, ensure_sources
from app.connectors.policy_base import PolicyQuery
from app.engine.matcher import normalize_insurer_id, match_item_code, match_plan
from app.intelligence.document_processor import process_uploaded_document
from app.intelligence.policy_extractor import extract_policies_with_gemini
from app.intelligence.policy_diff import compute_policy_diff
from app.intelligence.impact_previewer import preview_claim_impact

_SYNC_LOCK = threading.Lock()


def queries_for_cases(cases):
    """Only public policy search keys, used locally against retrieved catalog metadata."""
    return [
        PolicyQuery(
            insurer_id=normalize_insurer_id(c.insurer_id),
            plan_id=c.plan_id,
            environment=c.policy_environment,
            codes=tuple(i.code for i in c.items),
            topics=tuple(i.name or "" for i in c.items),
            jurisdictions=(c.jurisdiction.upper(),) if c.jurisdiction else (),
        )
        for c in cases
    ]


def relevant(candidate, queries):
    for q in queries:
        if normalize_insurer_id(candidate.insurer_id) != q.insurer_id:
            continue
        if candidate.is_synthetic and q.environment != "demo":
            continue
        if candidate.plan_ids and not match_plan(candidate.plan_ids, q.plan_id):
            continue
        if candidate.jurisdictions and not set(candidate.jurisdictions).intersection(
            q.jurisdictions
        ):
            continue
        if candidate.codes:
            if any(match_item_code(a, b) for a in q.codes for b in candidate.codes):
                return True
        else:
            # Topic filtering finds candidates, never proves code/plan applicability.
            tokens = {
                t.lower()
                for topic in q.topics
                for t in re.findall(r"[A-Za-z]{4,}", topic)
            } - {"total", "procedure", "service", "therapy", "synthetic", "treatment"}
            if any(
                re.search(r"\b" + re.escape(t) + r"\b", candidate.title, re.I)
                for t in tokens
            ):
                return True
    return False


def _document(download):
    if download.mime_type == "application/json":
        body = json.loads(download.content)
        rows = body.get("data", []) if isinstance(body, dict) else []
        if download.structured_rules:
            text = "\n".join(
                row["supporting_quote"] for row in download.structured_rules
            )
        else:
            # Preserve publisher field labels/values; never manufacture a coverage effect.
            from bs4 import BeautifulSoup

            text = "\n\n".join(
                f"{key}: {BeautifulSoup(str(value), 'html.parser').get_text(' ', strip=True) if '<' in str(value) else str(value)}"
                for row in rows
                for key, value in row.items()
                if value is not None
            )
        return process_uploaded_document(
            text.encode(), download.filename + ".txt", "text/plain"
        )
    return process_uploaded_document(
        download.content, download.filename, download.mime_type
    )


def _stage(candidate, connector, run, generation=None):
    generation = store._generation if generation is None else generation
    # Failed extraction is retried from saved content rather than losing a download.
    cached = (
        candidate.metadata.get("_retry_document")
        if candidate.status == "extraction_failed"
        else None
    )
    if cached:
        doc = cached
        structured = candidate.metadata.get("_retry_rules", [])
    else:
        download = connector.fetch(candidate)
        run.fetched += 1
        candidate.downloaded_hash = hashlib.sha256(download.content).hexdigest()
        doc = _document(download)
        structured = download.structured_rules
        candidate.metadata["_retry_document"] = doc
        candidate.metadata["_retry_rules"] = structured
    normalized = re.sub(r"\s+", " ", doc["raw_text"]).strip()
    fingerprint = hashlib.sha256(
        (
            normalized + (candidate.downloaded_hash or "")
            if doc.get("total_pages", 0) > doc["page_count"]
            else normalized
        ).encode()
    ).hexdigest()
    if structured:
        keys = (
            "insurer_id",
            "plan_ids",
            "jurisdictions",
            "target_type",
            "target_code",
            "code_system",
            "proposed_effect",
            "effective_from",
            "effective_to",
            "conditions",
            "change_type",
        )
        semantic = [{key: row.get(key) for key in keys} for row in structured]
        fingerprint = hashlib.sha256(
            json.dumps(semantic, sort_keys=True).encode()
        ).hexdigest()
    if fingerprint == candidate.processed_hash:
        candidate.status = "unchanged"
        candidate.last_successful_sync = utc_now()
        candidate.last_error = None
        candidate.metadata.pop("_retry_document", None)
        candidate.metadata.pop("_retry_rules", None)
        run.unchanged += 1
        return
    candidate.status = "processing"
    if structured:
        proposals = []
        for row in structured:
            if normalize_insurer_id(row.get("insurer_id")) != normalize_insurer_id(
                candidate.insurer_id
            ):
                raise ValueError(
                    "Structured policy insurer does not match catalog identity."
                )
            if (
                row.get("plan_ids") != candidate.plan_ids
                or row.get("jurisdictions") != candidate.jurisdictions
                or row.get("target_code") not in candidate.codes
            ):
                raise ValueError(
                    "Structured policy scope differs from discovered metadata."
                )
            p = ProposedPolicyChange.model_validate(
                {
                    **row,
                    "proposal_id": f"PROP-{uuid.uuid4().hex[:12]}",
                    "document_id": doc["document_id"],
                    "document_name": doc["filename"],
                    "is_synthetic": True,
                    "evidence_verified": True,
                    "scope_verified": True,
                    "extraction_method": "structured_simulator",
                    "source_url": candidate.source_url,
                }
            )
            proposals.append(p)
        used_ai = False
        error = None
        method = "structured_simulator"
    else:
        proposals, used_ai, error = extract_policies_with_gemini(doc)
        if not proposals or (error and "not configured" not in error):
            raise ValueError(
                "Policy extraction unavailable; document retained for retry."
            )
        method = "gemini" if used_ai else "deterministic"
        for p in proposals:
            # Identity can be known from the source, but exact plan/region must be reviewed.
            p.scope_verified = False
            p.review_state = "needs_correction"
            p.validation_warnings.append(
                "Public policy is a candidate only. Verify exact plan, jurisdiction, clinical criteria and source scope before activation."
            )
    for p in proposals:
        p.requires_billing_articles = candidate.requires_billing_articles
        p.catalog_id = candidate.catalog_id
        p.source_revision = candidate.revision
        p.source_url = candidate.source_url
        p.validation_warnings.extend(doc.get("warnings", []))
        p.source_synced_at = utc_now()
        p.jurisdictions = p.jurisdictions or candidate.jurisdictions
        if not candidate.is_synthetic and normalize_insurer_id(p.insurer_id) not in {
            "",
            normalize_insurer_id(candidate.insurer_id),
        }:
            p.insurer_id = None
            p.scope_verified = False
            p.review_state = "needs_correction"
    preview = preview_claim_impact(proposals)
    result = ExtractedDocumentResult(
        document_id=doc["document_id"],
        filename=doc["filename"],
        file_type=doc["file_type"],
        page_count=doc["page_count"],
        pages_text=doc["pages"],
        raw_text=doc["raw_text"],
        proposals=proposals,
        diffs=[compute_policy_diff(p) for p in proposals],
        impact_preview=preview,
        extraction_method=method,
        extraction_error=error,
        warnings=doc.get("warnings", []),
        source_url=candidate.source_url,
    )
    # All computations precede this single in-memory commit; persistence is transactional.
    with _STATE_LOCK:
        if store._generation != generation:
            raise InterruptedError("Application state reset during extraction.")
        from copy import deepcopy

        snapshot = deepcopy(
            (
                store.proposals,
                store.extracted_documents,
                store.policy_versions,
                candidate,
                run.changed,
                run.pending_review,
            )
        )
        try:
            store.save_extracted_document(result)
            version_id = candidate.catalog_id + ":" + fingerprint
            store.policy_versions[version_id] = PolicyDocumentVersion(
                version_id=version_id,
                catalog_id=candidate.catalog_id,
                content_hash=fingerprint,
                source_url=candidate.source_url,
                original_document_ref=doc["document_id"],
                raw_text=doc["raw_text"],
                revision=candidate.revision,
                extraction_method=method,
                proposal_ids=[p.proposal_id for p in proposals],
            )
            candidate.processed_hash = fingerprint
            candidate.document_id = doc["document_id"]
            candidate.status = "pending_review"
            candidate.pending_proposal_ids = list(
                dict.fromkeys(
                    candidate.pending_proposal_ids + [p.proposal_id for p in proposals]
                )
            )
            candidate.last_successful_sync = utc_now()
            candidate.last_error = None
            candidate.metadata.pop("_retry_document", None)
            candidate.metadata.pop("_retry_rules", None)
            run.changed += 1
            run.pending_review += len(proposals)
            store.save_checkpoint()
        except Exception:
            (
                store.proposals,
                store.extracted_documents,
                store.policy_versions,
                previous,
                run.changed,
                run.pending_review,
            ) = snapshot
            candidate.__dict__.clear()
            candidate.__dict__.update(previous.__dict__)
            raise


def sync_policies(source_id=None, claim_id=None, catalog_ids=None, connectors=None):
    ensure_sources(store)
    if not _SYNC_LOCK.acquire(blocking=False):
        return {"status": "already_running", "runs": []}
    try:
        registry = connectors or connector_registry()
        if source_id and source_id not in registry:
            raise ValueError("Unknown policy source.")
        cases = (
            [store.cases[claim_id]]
            if claim_id and claim_id in store.cases
            else list(store.cases.values())
        )
        queries = queries_for_cases(cases)
        runs = []
        generation = store._generation
        for sid, connector in registry.items():
            if source_id and source_id != sid:
                continue
            source = store.sync_sources.setdefault(sid, connector.source)
            run = SyncRun(
                run_id="SYNC-" + uuid.uuid4().hex[:12],
                source_id=sid,
                is_synthetic=source.is_synthetic,
            )
            store.sync_runs[run.run_id] = run
            source.last_attempt_at = run.started_at
            source.status = "syncing"
            store.save_checkpoint()
            try:
                discovered = connector.discover()
                run.discovered = len(discovered)
                if store._generation != generation:
                    return {"status": "interrupted", "runs": []}
                for candidate in discovered:
                    old = store.policy_catalog.get(candidate.catalog_id)
                    if old:
                        # Refresh discovery metadata while preserving evidence, hashes and failed downloads.
                        preserved = {
                            key: getattr(old, key)
                            for key in (
                                "processed_hash",
                                "downloaded_hash",
                                "status",
                                "pending_proposal_ids",
                                "last_error",
                                "document_id",
                                "last_successful_sync",
                            )
                        }
                        retry = {
                            key: value
                            for key, value in old.metadata.items()
                            if key.startswith("_retry")
                        }
                        if old.revision == candidate.revision:
                            enriched = {
                                key: value
                                for key, value in old.metadata.items()
                                if not key.startswith("_retry")
                            }
                            enriched.update(candidate.metadata)
                            for key in (
                                "associated_billing_articles",
                                "jurisdiction_records",
                                "article_review_required",
                                "jurisdiction_verified",
                            ):
                                if key in old.metadata:
                                    enriched[key] = old.metadata[key]
                            candidate.metadata = enriched
                            candidate.jurisdictions = (
                                candidate.jurisdictions or old.jurisdictions
                            )
                            candidate.metadata.update(retry)
                        else:
                            preserved["status"] = "discovered"
                        candidate = candidate.model_copy(update=preserved)
                    store.policy_catalog[candidate.catalog_id] = candidate
                seen = {c.catalog_id for c in discovered}
                for existing in store.policy_catalog.values():
                    if existing.source_id == sid and existing.catalog_id not in seen:
                        existing.status = "not_in_latest_index"
                        existing.last_error = "Not present in the latest index; not automatically cancelled."
                selected = [
                    c
                    for c in discovered
                    if (catalog_ids and c.catalog_id in catalog_ids)
                    or relevant(c, queries)
                ]
                selected.sort(
                    key=lambda c: (
                        0
                        if store.policy_catalog[c.catalog_id].status
                        == "extraction_failed"
                        else 1
                        if store.policy_catalog[c.catalog_id].status == "discovered"
                        or not store.policy_catalog[c.catalog_id].processed_hash
                        else 2,
                        store.policy_catalog[c.catalog_id].last_successful_sync
                        or utc_now() - timedelta(days=36500),
                    )
                )
                limit = max(
                    1,
                    min(
                        20,
                        int(os.environ.get("COVERAGEGUARD_SYNC_DOCUMENT_LIMIT", "5")),
                    ),
                )
                if len(selected) > limit:
                    run.gaps.append(
                        f"Document budget {limit} reached; remaining relevant candidates require a later/targeted sync."
                    )
                for metadata in selected[:limit]:
                    if store._generation != generation:
                        raise ValueError("Application state reset during sync.")
                    candidate = store.policy_catalog[metadata.catalog_id]
                    try:
                        _stage(candidate, connector, run, generation)
                    except InterruptedError:
                        return {"status": "interrupted", "runs": []}
                    except Exception as exc:
                        candidate.status = (
                            "access_restricted"
                            if isinstance(exc, SourceAccessError)
                            else "extraction_failed"
                            if "_retry_document" in candidate.metadata
                            else "fetch_failed"
                        )
                        candidate.last_error = f"{type(exc).__name__}: policy processing failed; retry is available."
                        run.failed += 1
                    store.save_checkpoint()
                if not selected:
                    run.gaps.append(
                        "No relevant policy metadata matched the selected claims; no coverage rule was invented."
                    )
                if not source.is_synthetic:
                    run.gaps.append(
                        "Public policy candidates require exact member plan/scope verification and human approval."
                    )
                run.status = "partial" if run.failed or run.gaps else "succeeded"
                source.status = (
                    "partial"
                    if run.status == "partial"
                    else "simulated"
                    if source.is_synthetic
                    else "healthy"
                )
                if not run.failed:
                    source.last_success_at = utc_now()
                source.last_error = (
                    None
                    if not run.failed
                    else "Some documents failed; their content remains retryable."
                )
            except Exception as exc:
                run.status = "failed"
                run.error = f"{type(exc).__name__}: source sync failed. See source access limitations; no bypass attempted."
                source.status = (
                    "authorization_required"
                    if isinstance(exc, SourceAuthorizationRequired)
                    else "unavailable"
                )
                if isinstance(exc, SourceAuthorizationRequired):
                    run.error = str(exc)
                source.last_error = run.error
                run.failed += 1
            run.completed_at = utc_now()
            source.counts = {
                key: getattr(run, key)
                for key in (
                    "discovered",
                    "fetched",
                    "changed",
                    "unchanged",
                    "pending_review",
                    "failed",
                )
            }
            interval = int(os.environ.get("COVERAGEGUARD_CHECK_INTERVAL", "86400"))
            source.consecutive_failures = (
                source.consecutive_failures + 1 if run.failed else 0
            )
            retry_seconds = (
                min(interval, 300 * (2 ** min(source.consecutive_failures - 1, 8)))
                if run.failed
                else interval
            )
            source.next_sync_at = utc_now() + timedelta(seconds=max(1, retry_seconds))
            if source.status == "authorization_required":
                source.next_sync_at = utc_now() + timedelta(seconds=interval)
            runs.append(run)
            store.record_audit(
                "POLICY_SYNC_COMPLETED",
                {
                    "run_id": run.run_id,
                    "source_id": sid,
                    "status": run.status,
                    "counts": source.counts,
                },
            )
            if store._generation == generation:
                store.save_checkpoint()
        return {"status": "completed", "runs": runs}
    finally:
        _SYNC_LOCK.release()
