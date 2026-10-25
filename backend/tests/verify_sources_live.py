"""Opt-in read-only source verification. No hospital or patient data is used."""

import json
from datetime import datetime, timezone
from pathlib import Path
from app.connectors.registry import connector_registry
from app.connectors.sync_engine import _document


def verify_sources():
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "sources": []}
    for connector in connector_registry(include_demo=False).values():
        row = {
            "source_id": connector.source.source_id,
            "official_source_url": connector.source.index_url,
            "source_type": connector.source.source_type,
            "discovery_succeeded": False,
            "document_retrieved": False,
            "usable_rule_extracted": False,
            "plan_jurisdiction_verified": False,
            "complete_claim_check": False,
            "limitations": connector.source.limitations,
        }
        try:
            policies = connector.discover()
            row["discovery_succeeded"] = True
            row["policies_discovered"] = len(policies)
            if policies:
                candidate = next(
                    (p for p in policies if "knee" in p.title.lower()), policies[0]
                )
                row["sample_document_url"] = candidate.source_url
                try:
                    doc = _document(connector.fetch(candidate))
                    row["document_retrieved"] = True
                    row["extracted_text_characters"] = len(doc["raw_text"])
                    row["processed_pages"] = doc["page_count"]
                    row["document_warnings"] = doc.get("warnings", [])
                    row["document_title"] = candidate.title
                    row["rule_gap"] = (
                        "Text retrieval is not a verified coverage rule; exact code/plan/region/effect/evidence require human review."
                    )
                except Exception as exc:
                    row["document_error"] = (
                        str(exc)
                        if type(exc).__name__ in {"SourceAccessError", "SourceError"}
                        else type(exc).__name__
                    )
        except Exception as exc:
            row["discovery_error"] = (
                str(exc)
                if type(exc).__name__ in {"SourceAccessError", "SourceError"}
                else type(exc).__name__
            )
        if connector.source.source_id == "cms-api" and row["discovery_succeeded"]:
            lcd = next(
                (
                    p
                    for p in policies
                    if p.document_type == "LCD" and "knee" in p.title.lower()
                ),
                next((p for p in policies if p.document_type == "LCD"), None),
            )
            if lcd:
                try:
                    connector.fetch(lcd)
                    row["lcd_sample"] = {
                        "url": lcd.source_url,
                        "jurisdictions": lcd.jurisdictions,
                        "related_billing_articles": len(
                            lcd.metadata.get("associated_billing_articles", [])
                        ),
                        "human_article_and_plan_review_required": True,
                    }
                except Exception as exc:
                    row["lcd_metadata_error"] = (
                        str(exc)
                        if type(exc).__name__ in {"SourceAccessError", "SourceError"}
                        else type(exc).__name__
                    )
        report["sources"].append(row)
        print(json.dumps(row), flush=True)
    return report


if __name__ == "__main__":
    report = verify_sources()
    Path("verification/sync/live-sources.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
