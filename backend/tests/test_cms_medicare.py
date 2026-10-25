"""Real-source path: CMS NCD → reviewer-verified rule → diagnosis-scoped Medicare claim check (offline)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.store import store
from app.connectors.cms_connector import CMSCoverageConnector

client = TestClient(app, headers={"X-Synthetic-Data": "true"})

# Shaped like the live API: HTML inside the JSON is itself entity-escaped.
NONCOVERED = (
    "CMS determines that the following procedures are not considered reasonable or necessary in "
    "treatment of the osteoarthritic knee and are not covered by the Medicare program"
)
NCD_ROW = {
    "document_id": 285, "document_version": 1, "document_display_id": "150.9",
    "title": "Arthroscopic Lavage and Arthroscopic Debridement for the Osteoarthritic Knee",
    "last_updated": "09/24/2026", "document_type": "NCD", "url": "/data/ncd?ncdid=285&ncdver=1",
}
NCD_DETAIL = {
    **NCD_ROW,
    "effective_date": "06/11/2004",
    "indications_limitations": "&lt;p&gt;&lt;strong&gt;B. Nationally Noncovered Indications&lt;&sol;strong&gt;&lt;&sol;p&gt;"
    f"&lt;p&gt;{NONCOVERED}:&lt;&sol;p&gt;&lt;ul&gt;&lt;li&gt;Arthroscopic lavage used alone for the osteoarthritic knee;&lt;&sol;li&gt;&lt;&sol;ul&gt;",
}


def fake_cms(self, url):
    if "/reports/national-coverage-ncd/" in url:
        return {"data": [NCD_ROW], "meta": {}}
    if "/reports/local-coverage-final-lcds/" in url:
        return {"data": [], "meta": {}}
    if "/data/ncd/" in url and "ncdid=285" in url:
        return {"data": [NCD_DETAIL], "meta": {}}
    raise AssertionError(f"Unexpected CMS request {url}")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    store.reset_state(False)
    store.demo_mode = False
    monkeypatch.setattr(CMSCoverageConnector, "_json", fake_cms)
    yield
    store.reset_state(False)


CLAIM = """Insurer ID: cms
Plan ID: MEDICARE-PART-B
Member ID: SYNTHETIC-MBI-001
State: CA
Service Date: 2026-11-12
Procedure: Arthroscopic debridement of knee
CPT Code: 29877
"""
OA = CLAIM + "Diagnosis Code: M17.11\n"
EDITS = dict(
    insurer_id="cms", plan_ids=["*"], jurisdictions=["US"], target_type="procedure", target_code="29877",
    code_system="CPT", proposed_effect="excluded", effective_from="2004-06-11", policy_reference="CMS-NCD-150.9",
    conditions={"applies_to_diagnosis_prefixes": ["M17"]}, scope_verified=True,
)
NOTES = "National NCD; CPT 29877 mapped by reviewer; diagnosis scope M17 (knee osteoarthritis)."


def analyze(text, **extra):
    response = client.post("/api/intake/analyze", json={"clinical_text": text, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def staged_proposal():
    analyze(OA, refresh_sources=True)
    return next(p for p in store.proposals.values() if p.catalog_id == "cms-api:NCD:285")


def approve(proposal, quote):
    return client.post(
        f"/api/policies/proposals/{proposal.proposal_id}/approve",
        json={"reviewer_notes": NOTES, "edited_fields": {**EDITS, "supporting_quote": quote}},
    )


def test_medicare_claim_refresh_stages_readable_ncd_for_review():
    result = analyze(OA, refresh_sources=True)
    assert result["policy_environment"] == "official"
    assert [r["source_id"] for r in result["rules_refresh"]] == ["cms-api"]
    proposal = next(p for p in store.proposals.values() if p.catalog_id == "cms-api:NCD:285")
    assert proposal.review_state == "needs_correction"
    assert proposal.source_url == "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=285&ncdver=1"
    text = store.extracted_documents[proposal.document_id].raw_text
    assert NONCOVERED in text and "&lt;" not in text and "<strong>" not in text
    # Nothing is decided before review.
    assert result["findings"]["findings"][0]["result"] == "No rule found, verify with the insurer"


def test_reviewer_quote_must_be_verbatim_official_text():
    proposal = staged_proposal()
    rejected = approve(proposal, "Medicare never covers any knee arthroscopy.")
    assert rejected.status_code == 422 and "word for word" in rejected.json()["detail"]
    assert store.proposals[proposal.proposal_id].review_state == "needs_correction"
    accepted = approve(proposal, NONCOVERED)
    assert accepted.status_code == 200, accepted.text
    rule = accepted.json()["rule"]
    assert rule["rule_id"] == "CMS-NCD-150.9" and rule["bulletin_summary"] == NONCOVERED


@pytest.mark.parametrize("diagnosis,expected", [
    ("Diagnosis Code: M17.11\n", "Not covered"),
    ("Diagnosis Code: M1712\n", "Not covered"),
    ("", "Value wrong"),
    ("Diagnosis Code: S83.211A\n", "No rule found, verify with the insurer"),
])
def test_diagnosis_scoped_ncd_rule(diagnosis, expected):
    assert approve(staged_proposal(), NONCOVERED).status_code == 200
    finding = analyze(CLAIM + diagnosis)["findings"]["findings"][0]
    assert finding["result"] == expected
    if expected == "Not covered":
        assert finding["policy_reference"] == "CMS-NCD-150.9"
        assert finding["source_evidence"] == NONCOVERED
        assert finding["source_url"].startswith("https://www.cms.gov/medicare-coverage-database/")


def test_medicare_rule_never_applies_to_other_insurers():
    assert approve(staged_proposal(), NONCOVERED).status_code == 200
    other = analyze(OA.replace("Insurer ID: cms", "Insurer ID: uhc").replace("MEDICARE-PART-B", "UHC-CHOICE"))
    assert other["findings"]["findings"][0]["result"] == "No rule found, verify with the insurer"
