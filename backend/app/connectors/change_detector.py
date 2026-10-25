"""Retry-safe source monitoring; only successful extraction commits a policy fingerprint."""
import hashlib
import re
import uuid
from threading import Lock
from typing import Optional

from app.domain.models import OfficialPolicySource, SourceCheckHistory, ExtractedDocumentResult, utc_now
from app.connectors.official_policy_source import CMSMedicareConnector
from app.intelligence.document_processor import process_uploaded_document
from app.intelligence.policy_extractor import extract_policies_with_gemini
from app.intelligence.impact_previewer import preview_claim_impact
from app.intelligence.policy_diff import compute_policy_diff
from app.db.store import store, _STATE_LOCK

_source_locks = {}
_registry_lock = Lock()


def _source_lock(source_id):
    with _registry_lock:
        return _source_locks.setdefault(source_id, Lock())


def check_source_for_changes(source: OfficialPolicySource, override_content: Optional[bytes] = None,
                             override_filename: Optional[str] = None) -> SourceCheckHistory:
    # Serialize manual checks and scheduler work per source. The app runs one process.
    with _source_lock(source.source_id):
        source = store.get_source(source.source_id) or source
        return _check(source, override_content, override_filename)


def _check(source, override_content, override_filename):
    now = utc_now()
    connector = CMSMedicareConnector()
    generation = store._generation
    source.last_checked_at = now
    source.last_check_simulated = override_content is not None
    source.status = "checking"
    source.error_message = None
    store.save_source(source)
    meaningful_hash = None
    created = []
    affected = 0
    changed = False
    state = "source_unavailable"
    error = None
    try:
        if override_content is not None:
            content, filename, meta = override_content, override_filename or "fixture.html", {"source_url": source.official_url}
        else:
            content, filename, meta = connector.fetch_latest_document(source.official_url)
        source.fetched_at = utc_now()
        source.downloaded_content_hash = connector.compute_fingerprint(content)
        source.status = "fetched"
        state = "extraction_failed"
        document = process_uploaded_document(content, filename, meta.get("content_type"))
        document["source_url"] = meta.get("source_url", source.official_url)
        normalized = re.sub(r"\s+", " ", document["raw_text"]).strip()
        meaningful_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else source.downloaded_content_hash
        changed = meaningful_hash != source.content_hash
        if not changed:
            source.status = "unchanged"
            summary = "Meaningful policy content is unchanged. No duplicate proposal created."
            state = "unchanged"
        else:
            source.status = "processing"
            proposals, used_ai, ai_error = extract_policies_with_gemini(document)
            # Fallback is review assistance, not a successful live Gemini extraction.
            # Retry whenever a configured service failed; missing credentials can stage explicitly labelled text extraction.
            if not proposals or (ai_error and "not configured" not in ai_error):
                raise ValueError("Policy extraction unavailable or returned no proposals; source remains retryable.")
            for p in proposals:
                p.source_url = document["source_url"]
                if override_content is not None:
                    p.is_synthetic = True
                    p.validation_warnings.append("Simulated source fixture; this document was not downloaded from CMS.")
                # Never infer a missing insurer or plan from the connector name.
                p.policy_title = p.policy_title or document.get("policy_title")
            impact = preview_claim_impact(proposals)
            affected = impact.affected_cases
            result = ExtractedDocumentResult(
                document_id=document["document_id"], filename=filename, file_type=document["file_type"],
                page_count=document["page_count"], pages_text=document["pages"], raw_text=document["raw_text"],
                proposals=proposals, diffs=[compute_policy_diff(p) for p in proposals], impact_preview=impact,
                extraction_method="gemini" if used_ai else "deterministic", extraction_error=ai_error,
                warnings=document.get("warnings", []), source_url=document["source_url"],
            )
            # All computations must succeed before staging or advancing the committed fingerprint.
            with _STATE_LOCK:
                if store._generation != generation:
                    return SourceCheckHistory(check_id=f"CHK-{uuid.uuid4().hex[:12].upper()}", source_id=source.source_id,
                                              status="extraction_failed", summary="Application state reset during check. No proposals staged.")
                store.save_extracted_document(result)
                created = [p.proposal_id for p in proposals]
                source.pending_proposal_ids = list(dict.fromkeys(source.pending_proposal_ids + created))
                source.content_hash = meaningful_hash
                source.last_changed_at = utc_now()
                source.processed_at = utc_now()
                source.latest_document_title = document.get("policy_title") or proposals[0].policy_title
                source.status = "pending_review"
                state = "pending_review"
                summary = f"Staged {len(created)} proposal(s) for human review; {affected} claims change in preview. No rules applied."
    except Exception as exc:
        source.status = state
        # Do not echo network URLs, credentials, provider bodies, or document text into logs/API errors.
        error = f"{state}: {type(exc).__name__}. Check source availability and extraction configuration; retry is allowed."
        source.error_message = error
        summary = error
    history = SourceCheckHistory(
        check_id=f"CHK-{uuid.uuid4().hex[:12].upper()}", source_id=source.source_id,
        source_name=source.name, checked_at=now, status=state,
        content_hash=meaningful_hash or source.content_hash, changed=changed,
        proposals_created=created, affected_claims_count=affected, summary=summary, error_message=error,
        is_simulated=override_content is not None,
    )
    if store._generation != generation:
        return SourceCheckHistory(check_id=history.check_id, source_id=source.source_id, status="extraction_failed",
                                  summary="Application state reset during check. No proposals staged.")
    store.save_source(source)
    store.add_source_history(history)
    store.save_checkpoint()
    return history
