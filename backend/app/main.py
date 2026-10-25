"""Four-page insurance check application. No simulated coverage decisions."""
import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager, closing
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# Load existing server configuration without exposing environment values.
env_file = Path(__file__).resolve().parent.parent / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('\"\''))

from app.documents import MAX_FILE_BYTES, card_fields, prescription_fields, read_document
from app.policies import lookup_policies
from app.assessment import assess_policies

PHYSICIAN_NOTE = 'If insurance does not cover the prescribed treatment, please consult the responsible physician.'
DB_PATH = Path(os.getenv('COVERAGEGUARD_REQUEST_DB', str(Path(__file__).resolve().parent.parent / 'data' / 'insurance_requests.sqlite3')))


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=3)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE IF NOT EXISTS insurance_requests (request_id TEXT PRIMARY KEY, submitted_at TEXT NOT NULL, report TEXT NOT NULL)')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def all_reports():
    with database() as conn:
        return [json.loads(row['report']) for row in conn.execute('SELECT report FROM insurance_requests ORDER BY submitted_at DESC')]


app = FastAPI(title='Coverage Guard', version='3.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


@app.get('/health')
@app.get('/api/health')
def health():
    return {'status': 'healthy', 'service': 'Coverage Guard'}


@app.get('/api/connection')
def connection():
    # Report the connection that actually exists; never impersonate an insurer API.
    with database():
        pass
    # The policy-record connection is opened with SQLite-enforced read-only access.
    with closing(sqlite3.connect(f'{DB_PATH.resolve().as_uri()}?mode=ro', uri=True)) as conn:
        conn.execute('SELECT 1 FROM insurance_requests LIMIT 1').fetchone()
    return {
        'status': 'Connected', 'database_name': 'Insurance policy records',
        'access_mode': 'READ-ONLY', 'permission': 'READ ONLY — NO WRITE ACCESS',
        'description': 'Application records connected. Direct insurer database access is not configured.',
    }


@app.get('/api/requests')
def requests():
    return [{key: report[key] for key in ('request_id', 'insurer_name', 'treatment_name', 'submitted_at', 'status')} for report in all_reports()]


@app.get('/api/requests/{request_id}')
def report(request_id: str):
    with database() as conn:
        row = conn.execute('SELECT report FROM insurance_requests WHERE request_id = ?', (request_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Request not found.')
    return json.loads(row['report'])


@app.get('/api/updates')
def updates():
    verified = {}
    for report in all_reports():
        for source in report['sources']:
            if not source.get('effective_date'):
                continue
            key = (source['url'], source['treatment_name'], source['effective_date'])
            verified.setdefault(key, {
                'title': source['title'], 'treatment_name': source['treatment_name'],
                'insurer_name': source['insurer_name'], 'effective_date': source['effective_date'],
                'description': source['excerpt'], 'source_url': source['url'],
                'checked_at': source['checked_at'],
            })
    return sorted(verified.values(), key=lambda item: (item['checked_at'], item['effective_date']), reverse=True)


async def uploaded_text(file: UploadFile | None) -> tuple[str, str | None]:
    if not file:
        return '', None
    filename = Path(file.filename or 'document').name
    if Path(filename).suffix.lower() not in {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.txt'}:
        raise HTTPException(415, 'Use a PDF, PNG, JPG, WebP, or text file.')
    data = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, 'Each file must be 8 MB or smaller.')
    try:
        async with asyncio.timeout(13):
            text = await asyncio.to_thread(read_document, data, filename)
    except TimeoutError:
        text = ''
    return text, filename


def build_result(rx: dict, missing: list, findings: list) -> tuple[str, str, str]:
    assumption = 'Prescription assumed valid for this policy test. Insurer approval is not confirmed.'
    if missing:
        return 'Missing information', 'Missing: ' + ', '.join(dict.fromkeys(missing)) + '.', assumption
    failed = [finding for finding in findings if finding['outcome'] == 'not_matched']
    if failed:
        return 'Policy mismatch', failed[0]['reason'], assumption
    upcoming = [finding for finding in findings if finding['outcome'] == 'upcoming']
    if upcoming:
        effective = upcoming[0]['effective_date']
        return 'Coverage alert', f"{rx['treatment_name']} will no longer be covered starting {effective}. Until then, coverage may still apply.", assumption
    if findings and all(finding['outcome'] == 'matched' for finding in findings):
        return 'Accepted', 'Accepted for this policy test. The checked policy criteria are met.', assumption
    reason = findings[0]['reason'] if findings else 'No applicable policy could be verified.'
    return 'Needs policy review', reason, assumption


@app.post('/api/requests/check')
async def check(insurance_card: UploadFile | None = File(None), prescription: UploadFile | None = File(None)):
    (card_text, card_file), (rx_text, rx_file) = await asyncio.gather(uploaded_text(insurance_card), uploaded_text(prescription))
    card, rx = card_fields(card_text), prescription_fields(rx_text)
    missing = []
    if not card_file:
        missing.append('insurance card')
    elif not card_text.strip():
        missing.append('readable insurance card')
    elif not card['insurer_name']:
        missing.append('insurer name')
    if not rx_file:
        missing.append('prescription')
    elif not rx_text.strip():
        missing.append('readable prescription')
    elif not rx['treatment_name']:
        missing.append('medication or procedure name')
    sources, search_status = [], 'Coverage is not verified.'
    if card['insurer_name'] and rx['treatment_name']:
        sources, search_status = await lookup_policies(card['insurer_name'], rx['treatment_name'], card['plan_id'])
    findings = assess_policies(card, rx['treatment_name'], rx_text, sources) if not missing else []
    status, message, coverage_note = build_result(rx, missing, findings)
    result = {
        'request_id': f'REQ-{uuid.uuid4().hex[:10].upper()}',
        'insurer_name': card['insurer_name'], 'treatment_name': rx['treatment_name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(), 'status': status,
        'message': message, 'coverage_note': coverage_note, 'physician_note': PHYSICIAN_NOTE,
        'card_information': card, 'sources': sources, 'policy_findings': findings,
        'prescription_assumed_valid': bool(rx_file), 'policy_search_status': search_status,
        'documents': [
            {'type': 'Insurance card', 'filename': card_file, 'information': {k: v for k, v in card.items() if v}},
            {'type': 'Prescription', 'filename': rx_file, 'information': {k: v for k, v in rx.items() if v}},
        ],
    }
    with database() as conn:
        conn.execute('INSERT INTO insurance_requests VALUES (?, ?, ?)', (result['request_id'], result['submitted_at'], json.dumps(result)))
    return result
