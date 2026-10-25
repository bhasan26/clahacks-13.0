"""
Official Insurer Policy Change Detection Engine.
Calculates SHA-256 content fingerprints, identifies policy bulletin revisions,
and routes detected changes to human approval staging.
"""

import uuid
from typing import Optional, Tuple, List, Dict, Any
from app.domain.models import (
    OfficialPolicySource,
    SourceCheckHistory,
    ProposedPolicyChange,
    utc_now,
)
from app.connectors.base import PolicySourceConnector, SourceError
from app.connectors.official_policy_source import CMSMedicareConnector
from app.intelligence.document_processor import process_uploaded_document
from app.intelligence.policy_extractor import extract_policies_with_gemini
from app.intelligence.impact_previewer import preview_claim_impact
from app.db.store import store


def check_source_for_changes(
    source: OfficialPolicySource,
    override_content: Optional[bytes] = None,
    override_filename: Optional[str] = None,
) -> SourceCheckHistory:
    """
    Executes a fingerprint check against an official policy source.
    If the document has changed:
      - Computes new SHA-256 hash
      - Triggers policy extraction pipeline
      - Creates proposals in pending_review state
      - Previews claim impact
      - Stages changes for human approval (ZERO unapproved rule mutations)
    """
    connector = CMSMedicareConnector()
    now = utc_now()
    check_id = f"CHK-{uuid.uuid4().hex[:8].upper()}"

    content_bytes: bytes
    filename: str
    metadata: Dict[str, str] = {}

    try:
        if override_content is not None:
            content_bytes = override_content
            filename = override_filename or "official_policy_fixture.html"
            metadata = {"source_url": source.official_url, "simulated": "test_fixture"}
        else:
            content_bytes, filename, metadata = connector.fetch_latest_document(source.official_url)
    except SourceError as e:
        source.status = "error"
        source.last_checked_at = now
        source.error_message = str(e)
        store.save_source(source)

        history = SourceCheckHistory(
            check_id=check_id,
            source_id=source.source_id,
            source_name=source.name,
            checked_at=now,
            status="error",
            content_hash=source.content_hash,
            changed=False,
            summary=f"Failed to check official source: {e}",
            error_message=str(e),
        )
        store.add_source_history(history)
        return history
    except Exception as e:
        source.status = "error"
        source.last_checked_at = now
        source.error_message = str(e)
        store.save_source(source)

        history = SourceCheckHistory(
            check_id=check_id,
            source_id=source.source_id,
            source_name=source.name,
            checked_at=now,
            status="error",
            content_hash=source.content_hash,
            changed=False,
            summary=f"Unexpected error checking official source: {e}",
            error_message=str(e),
        )
        store.add_source_history(history)
        return history

    new_hash = connector.compute_fingerprint(content_bytes)
    is_initial = not source.content_hash
    is_changed = (new_hash != source.content_hash)

    source.last_checked_at = now
    source.status = "connected"
    source.error_message = None

    if not is_changed:
        # Document is unchanged: record check and do nothing further
        store.save_source(source)
        history = SourceCheckHistory(
            check_id=check_id,
            source_id=source.source_id,
            source_name=source.name,
            checked_at=now,
            status="unchanged",
            content_hash=new_hash,
            changed=False,
            proposals_created=[],
            affected_claims_count=0,
            summary="Document content fingerprint matches previous check. No policy changes announced.",
        )
        store.add_source_history(history)
        return history

    # Document has changed (or initial baseline)
    source.content_hash = new_hash
    source.last_changed_at = now
    store.save_source(source)

    # Process document through extraction pipeline
    created_proposal_ids: List[str] = []
    affected_count = 0
    summary = ""

    try:
        doc_data = process_uploaded_document(
            file_bytes=content_bytes,
            filename=filename,
            mime_type=metadata.get("content_type", "text/html"),
        )
        proposals, used_ai, ai_err = extract_policies_with_gemini(doc_data)

        # Stage each proposal for human review
        for p in proposals:
            p.policy_title = p.policy_title or f"Official Update from {source.name}"
            if not p.insurer_id:
                p.insurer_id = "cms"
                p.insurer_name = source.insurer_name
            p.review_state = "pending_review"
            store.save_proposal(p)
            created_proposal_ids.append(p.proposal_id)

        source.pending_proposal_ids = list(set(source.pending_proposal_ids + created_proposal_ids))
        store.save_source(source)

        # Calculate impact on open claims
        if proposals:
            impact = preview_claim_impact(proposals)
            affected_count = impact.affected_cases

        summary = (
            f"Initial baseline document captured. Hash: {new_hash[:12]}... Extracted {len(proposals)} proposed rule(s)."
            if is_initial
            else f"Official policy revision detected! Hash changed to {new_hash[:12]}... Generated {len(proposals)} proposal(s) affecting {affected_count} claims."
        )
    except Exception as e:
        summary = f"Document updated but extraction pipeline encountered error: {e}"

    history = SourceCheckHistory(
        check_id=check_id,
        source_id=source.source_id,
        source_name=source.name,
        checked_at=now,
        status="change_detected" if not is_initial else "baseline_established",
        content_hash=new_hash,
        changed=True,
        proposals_created=created_proposal_ids,
        affected_claims_count=affected_count,
        summary=summary,
    )
    store.add_source_history(history)
    return history
