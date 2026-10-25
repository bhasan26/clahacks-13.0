"""Upload-to-report contract, evidence safeguards, and persistent request history."""
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.policies import evidence_from_text

CARD = b'UnitedHealthcare\nMember Name: Avery Sample\nMember ID: M-123\nPlan ID: P-123\nGroup No: G-987'
RX = b'Patient: Avery Sample\nMember ID: M-123\nRx: Ozempic (semaglutide) 1 mg\nSig: Inject once weekly.'
URL = 'https://www.uhcprovider.com/policy'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'requests.sqlite3')
    async def no_source(*args):
        return [], 'No matching policy could be verified.'
    monkeypatch.setattr(main, 'lookup_policies', no_source)
    with TestClient(main.app) as client:
        yield client


def upload(client, card=CARD, rx=RX):
    files = {}
    if card is not None:
        files['insurance_card'] = ('card.txt', card)
    if rx is not None:
        files['prescription'] = ('rx.txt', rx)
    return client.post('/api/requests/check', files=files)


def test_complete_upload_stores_actual_fields_and_evidence(client):
    response = upload(client)
    assert response.status_code == 200
    result = response.json()
    assert result['insurer_name'] == 'UnitedHealthcare'
    assert result['treatment_name'] == 'Ozempic (semaglutide) 1 mg'
    assert result['status'] == 'Needs policy review'
    assert result['message'] == 'No applicable policy could be verified.'
    assert result['prescription_assumed_valid'] is True
    assert 'Prescription assumed valid' in result['coverage_note']
    assert not result['sources']
    assert result['physician_note'] == main.PHYSICIAN_NOTE
    assert result['documents'][0]['information']['member_id'] == 'M-123'
    assert client.get('/api/requests').json()[0]['request_id'] == result['request_id']
    assert client.get('/api/requests/' + result['request_id']).json() == result
    # A fresh connection still reads the stored report.
    assert main.all_reports()[0] == result
    assert client.get('/api/updates').json() == []


@pytest.mark.parametrize('card,rx,expected', [
    (None, RX, 'insurance card'), (CARD, None, 'prescription'),
    (b'Unreadable text', RX, 'insurer name'),
    (CARD, b'Patient: Avery Sample\nSig: once daily', 'medication or procedure name'),
])
def test_missing_documents_and_fields_never_invent_values(client, card, rx, expected):
    result = upload(client, card, rx).json()
    assert result['status'] == 'Missing information'
    assert expected in result['message']
    assert result['physician_note'] == main.PHYSICIAN_NOTE


@pytest.mark.parametrize('offset', [-30, 30])
def test_source_backed_alerts_distinguish_past_and_future(client, monkeypatch, offset):
    effective = (date.today() + timedelta(days=offset)).isoformat()
    excerpt = f'Plan P-123: Ozempic will no longer be covered starting {effective}.'
    source = evidence_from_text(URL, excerpt, 'UnitedHealthcare', 'Ozempic', 'P-123', 'Plan coverage update')
    assert source['exclusion_verified']
    async def verified_source(*args):
        return [source], 'Public source found.'
    monkeypatch.setattr(main, 'lookup_policies', verified_source)
    result = upload(client).json()
    assert result['status'] == ('Coverage alert' if offset > 0 else 'Policy mismatch')
    assert effective in result['message']
    assert 'Ozempic' in result['message']
    assert ('Until then, coverage may still apply.' in result['message']) == (offset > 0)
    assert result['sources'][0]['url'] == URL
    assert result['sources'][0]['excerpt'] == excerpt
    updates = client.get('/api/updates').json()
    assert updates[0]['effective_date'] == effective
    assert updates[0]['source_url'] == URL


@pytest.mark.parametrize('text,plan', [
    ('Plan OTHER: Ozempic will no longer be covered starting 2026-11-01.', 'P-123'),
    ('Plan P-123: Ozempic may no longer be covered starting 2026-11-01.', 'P-123'),
    ('Plan P-123: Ozempic is no longer covered for weight loss starting 2026-11-01.', 'P-123'),
    ('Do not assume Plan P-123: Ozempic is no longer covered starting 2026-11-01.', 'P-123'),
    ('Plan P-123: Ozempic is no longer covered starting 2026-11-01 unless approved.', 'P-123'),
    ('Ozempic will no longer be covered starting 2026-11-01.', None),
    ('Plan P-123: Ozempic is no longer covered.', 'P-123'),
    ('Plan P-123: Ozempic will no longer be covered starting 2026-02-31.', 'P-123'),
])
def test_ambiguous_or_inapplicable_evidence_cannot_deny_coverage(text, plan):
    source = evidence_from_text(URL, text, 'UnitedHealthcare', 'Ozempic', plan)
    assert source is None or not source['exclusion_verified']


def test_other_drug_and_unofficial_site_cannot_supply_evidence():
    text = 'Plan P-123: Wegovy will no longer be covered starting 2026-11-01.'
    assert evidence_from_text(URL, text, 'UnitedHealthcare', 'Ozempic', 'P-123') is None
    assert evidence_from_text('https://uhcprovider.com.example.org/fake', text, 'UnitedHealthcare', 'Wegovy', 'P-123') is None


def test_invalid_files_and_missing_report(client):
    assert client.get('/api/requests/does-not-exist').status_code == 404
    assert client.post('/api/requests/check', files={'insurance_card': ('file.exe', b'fake')}).status_code == 415
    assert client.post('/api/requests/check', files={'insurance_card': ('large.txt', b'x' * (8 * 1024 * 1024 + 1))}).status_code == 413
    result = client.post('/api/requests/check', files={'insurance_card': ('broken.pdf', b'not a pdf')}).json()
    assert result['status'] == 'Missing information'
    assert 'readable insurance card' in result['message']


def test_connection_is_honest_and_old_demo_controls_are_removed(client):
    connection = client.get('/api/connection').json()
    assert connection['access_mode'] == 'READ-ONLY'
    assert connection['permission'] == 'READ ONLY — NO WRITE ACCESS'
    assert 'not configured' in connection['description']
    for path in ['/api/simulator/reset', '/api/check/run-now', '/api/connection/toggle-fail']:
        assert client.post(path).status_code == 404


@pytest.mark.parametrize('folder,extension', [('output/pdf', 'pdf'), ('backend/tests/fixtures', 'png')])
def test_actual_sample_documents_are_assumed_valid_and_checked(client, folder, extension):
    root = Path(__file__).resolve().parents[2]
    paths = list((root / folder).glob('*.' + extension))
    if len(paths) < 2:
        pytest.skip('Local sample fixtures not present')
    card = next(p for p in paths if 'card' in p.name)
    rx = next(p for p in paths if 'prescription' in p.name)
    result = client.post('/api/requests/check', files={'insurance_card': (card.name, card.read_bytes()), 'prescription': (rx.name, rx.read_bytes())}).json()
    assert result['insurer_name'] == 'UnitedHealthcare'
    assert 'Ozempic' in result['treatment_name']
    assert result['status'] == 'Needs policy review'
    assert result['prescription_assumed_valid'] is True
    assert 'valid prescription' not in result['message']


def test_procedure_and_second_insurer_are_extracted_without_default_drugs(client):
    result = upload(client, CARD.replace(b'UnitedHealthcare', b'Aetna'), b'Patient: Avery Sample\nProcedure: MRI of the right knee').json()
    assert result['insurer_name'] == 'Aetna'
    assert result['treatment_name'] == 'MRI of the right knee'
    assert result['status'] == 'Needs policy review'


def test_live_retrieval_contract_only_fetches_official_sources_and_caches(monkeypatch):
    import asyncio
    import httpx
    from app import policies
    seen = []
    def respond(request):
        seen.append(str(request.url))
        if request.url.host == 'www.bing.com':
            return httpx.Response(200, text=f'<rss><channel><item><link>{URL}</link></item><item><link>https://untrusted.example/fake</link></item></channel></rss>')
        return httpx.Response(200, text='<html><title>Plan coverage update</title><p>Plan P-123: Ozempic will no longer be covered starting 2026-11-01.</p></html>')
    original = httpx.AsyncClient
    monkeypatch.setattr(policies.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    policies._cache.clear()
    async def check_twice():
        first = await policies.lookup_policies('UnitedHealthcare', 'Ozempic', 'P-123')
        count = len(seen)
        second = await policies.lookup_policies('UnitedHealthcare', 'Ozempic', 'P-123')
        assert first == second
        assert len(seen) == count
        assert first[0][0]['exclusion_verified']
        assert all('untrusted' not in url for url in seen)
    asyncio.run(check_twice())
    policies._cache.clear()


def test_source_redirect_cannot_reach_a_private_or_untrusted_host():
    import asyncio
    import httpx
    from app.policies import fetch_source
    seen = []
    def redirect(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={'Location': 'http://127.0.0.1/private'})
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as client:
            assert await fetch_source(client, URL, ('uhcprovider.com',)) is None
    asyncio.run(check())
    assert seen == [URL]


def test_treatment_digits_are_preserved_in_extraction_and_search():
    from app.documents import prescription_fields, search_treatment
    name = prescription_fields('Patient: Avery Sample\nMedication: Vitamin B12 1000 mcg')['treatment_name']
    assert name == 'Vitamin B12 1000 mcg'
    assert search_treatment(name) == 'Vitamin B12'


@pytest.mark.parametrize('card,rx', [
    (b'UnitedHealthcare', RX),
    (CARD, RX.replace(b'Avery Sample', b'Sam Other')),
    (CARD, RX.replace(b'M-123', b'M-456')),
    (CARD, b'Rx: Ozempic\nNOT VALID FOR DISPENSING'),
    (CARD + b'\nFICTIONAL MEMBER - NOT VALID FOR COVERAGE', RX),
])
def test_authenticity_and_identity_do_not_block_policy_testing(client, monkeypatch, card, rx):
    calls = []
    async def search(*args):
        calls.append(args)
        return [], 'No verified source.'
    monkeypatch.setattr(main, 'lookup_policies', search)
    result = upload(client, card, rx).json()
    assert calls and calls[0][0] == 'UnitedHealthcare'
    assert result['status'] == 'Needs policy review'
    assert result['prescription_assumed_valid'] is True


# Synthetic statements exercise the source comparison, without being real policies.
CRITERIA = """Medication Ozempic
Program Number 2026 P 1332-8
Effective Date 7/1/2026
2. Coverage Criteria:
Submission of medical records confirming diagnosis of type 2 diabetes mellitus
A1C greater than or equal to 6.5%
Fasting plasma glucose (FPG) greater than or equal to 126 mg/dL
For ongoing treatment, diagnosed greater than 2 years ago.
3. Additional Clinical Programs
"""


@pytest.mark.parametrize('clinical,outcome,reason', [
    ('Diagnosis: E11.9 Type 2 diabetes mellitus\nA1C: 7.2%', 'Accepted', 'A1C'),
    ('Diagnosis: Type 2 diabetes mellitus\nDiabetes duration: 3 years', 'Accepted', 'ongoing-treatment'),
    ('Diagnosis: Type 2 diabetes mellitus\nFPG: 140 mg/dL', 'Accepted', 'fasting glucose'),
    ('Diagnosis: Obesity, weight loss only', 'Policy mismatch', 'type 2 diabetes requirement'),
    ('Diagnosis: Type 1 diabetes mellitus', 'Policy mismatch', 'type 2 diabetes requirement'),
    ('Diagnosis: No type 2 diabetes, obesity only', 'Policy mismatch', 'type 2 diabetes requirement'),
    ('Diagnosis: Type 2 diabetes mellitus', 'Needs policy review', 'qualifying test results'),
    ('Diagnosis: Type 2 diabetes mellitus\nA1C: 5.9%', 'Needs policy review', 'qualifying test results'),
    ('Diagnosis: Type 2 diabetes mellitus\nA1C: 7.2', 'Needs policy review', 'qualifying test results'),
    ('', 'Needs policy review', 'type 2 diabetes diagnosis'),
])
def test_actual_prescription_facts_are_compared_with_cited_criteria(client, monkeypatch, clinical, outcome, reason):
    source = evidence_from_text(URL, CRITERIA, 'UnitedHealthcare', 'Ozempic', None, 'Diabetes medication policy')
    async def search(*args):
        return [source], 'Public policy found.'
    monkeypatch.setattr(main, 'lookup_policies', search)
    result = upload(client, b'UnitedHealthcare', ('NOT VALID FOR DISPENSING\nRx: Ozempic\n' + clinical).encode()).json()
    assert result['status'] == outcome
    assert reason in result['policy_findings'][0]['reason']
    assert result['policy_findings'][0]['source_url'] == URL
    assert result['policy_findings'][0]['policy_id'] == '2026 P 1332-8'
    assert result['prescription_assumed_valid'] is True
    assert 'Insurer approval is not confirmed' in result['coverage_note']


def test_explicit_coverage_statement_accepts_policy_test(client, monkeypatch):
    source = evidence_from_text(URL, 'Plan P-123: Ozempic is covered effective 2026-01-01.', 'UnitedHealthcare', 'Ozempic', 'P-123', 'Formulary')
    async def search(*args):
        return [source], 'Public policy found.'
    monkeypatch.setattr(main, 'lookup_policies', search)
    result = upload(client).json()
    assert result['status'] == 'Accepted'
    assert result['policy_findings'][0]['source_url'] == URL


def test_medication_mention_alone_does_not_mean_accepted(client, monkeypatch):
    source = evidence_from_text(URL, 'Medication: Ozempic', 'UnitedHealthcare', 'Ozempic', None, 'Drug list')
    async def search(*args):
        return [source], 'Public policy found.'
    monkeypatch.setattr(main, 'lookup_policies', search)
    result = upload(client).json()
    assert result['status'] == 'Needs policy review'
    assert result['policy_findings'][0]['outcome'] == 'unknown'
