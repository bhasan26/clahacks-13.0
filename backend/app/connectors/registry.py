"""Explicit identities; generic BCBS cannot silently select a regional affiliate."""

import os
from datetime import timedelta
from app.domain.models import utc_now

from app.connectors.commercial import UHCConnector, AetnaConnector, AnthemCAConnector
from app.connectors.cms_connector import CMSCoverageConnector


def connector_registry(include_demo=True):
    connectors = [
        UHCConnector(),
        AetnaConnector(),
        AnthemCAConnector(),
        CMSCoverageConnector(),
    ]
    if include_demo:
        from app.connectors.simulated import SimulatedInsurerConnector

        connectors.append(SimulatedInsurerConnector())
    return {c.source.source_id: c for c in connectors}


def ensure_sources(db):
    for source_id, connector in connector_registry().items():
        if source_id not in db.sync_sources:
            db.sync_sources[source_id] = connector.source
        source = db.sync_sources[source_id]
        current = connector.source
        for field in (
            "name",
            "index_url",
            "source_type",
            "jurisdictions",
            "limitations",
        ):
            setattr(source, field, getattr(current, field))
        if current.status == "authorization_required":
            source.status = current.status
        elif source.status == "authorization_required":
            source.status = "unchecked"
            source.last_error = None
        if (
            source.next_sync_at is None
            and os.environ.get("COVERAGEGUARD_SCHEDULER_ENABLED") == "true"
        ):
            source.next_sync_at = (
                source.last_attempt_at
                + timedelta(
                    seconds=int(os.environ.get("COVERAGEGUARD_CHECK_INTERVAL", "86400"))
                )
                if source.last_attempt_at
                else utc_now()
            )
