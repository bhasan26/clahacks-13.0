# CoverageGuard

CoverageGuard is a CalHacks prototype for reviewing insurance policy documents against **synthetic claims**. FastAPI, React/TypeScript, Gemini extraction, and a deterministic rule engine implement:

**Public policy source or uploaded document → proposed rules → source validation → claim-impact preview → human review → versioned rules → claim re-evaluation → alerts and audit history.**

Seeded commercial-payer rules and patient presets are synthetic examples. Public CMS retrieval is not a commercial insurer partnership, authenticated insurer API integration, eligibility verification, or a complete claims-adjudication service. No HIPAA compliance or production readiness is claimed.

## Verified audit status

Audit baseline: `d25cead`; working branch: `codex/coverageguard-reliability`.

- Backend: **117 pytest tests passed**, including PDF upload, separate delay notice, full re-evaluation, alerts, audit, retries, matching boundaries, concurrency, and persistence.
- Existing acceptance runner: **38 checks passed**.
- Frontend: TypeScript validation and Vite production build passed; Dashboard, Cases, Updates, and Policy Intelligence were inspected in Chrome.
- Live CMS NCD 90.2: HTTP 200, 5,265 characters of extracted policy text, one explicitly labelled deterministic review proposal, then `unchanged` with zero duplicate proposals and no rules applied. This incomplete proposal requires reviewer clarification.
- **Live Gemini extraction is not verified.** The existing key could list models, but generation returned HTTP 404 for `gemini-2.5-flash`, HTTP 429 for `gemini-3-flash-preview`, and a read timeout for `gemini-3.8-flash`. Mocked Gemini success/failure and deterministic workflows passed. Fallback is visibly identified and is never reported as live Gemini success.

See [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md) for findings, files, evidence, limitations, and the verification matrix. [PROGRESS.md](PROGRESS.md) records the current implementation status.

## Run locally

Requirements: Python 3.12+, Node.js 20.19+ or 22+, and macOS/Linux. The lightweight worker lock uses POSIX `flock`.

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
cp backend/.env.example backend/.env
```

Add `GEMINI_API_KEY` to `backend/.env` if available. Keep the key server-side. `GEMINI_MODEL` defaults to `gemini-3.8-flash` and is configurable; verify model access for your own account using the [official Gemini model documentation](https://ai.google.dev/gemini-api/docs/models). Text-only deterministic assistance remains available without a key; scanned images require a functioning vision model plus human evidence verification.

```bash
./dev.sh
```

Backend: `http://127.0.0.1:8000`; frontend: `http://localhost:5173`. Start only **one API worker**. A process lock rejects a second worker; source checks and approvals also have in-process serialization. Automatic monitoring is off by default. Enable `COVERAGEGUARD_SCHEDULER_ENABLED=true` in the backend environment to poll configured sources every `COVERAGEGUARD_CHECK_INTERVAL` seconds (default 3600).

To start separately:

```bash
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
cd frontend
npm run dev
```

The frontend proxy can use `COVERAGEGUARD_API_URL` for an alternate local backend. If you change the frontend origin, configure `COVERAGEGUARD_CORS_ORIGINS` accordingly. Do not expose the server publicly for patient workflows.

## Review and data boundaries

- Only synthetic patient information and synthetic upload fixtures are permitted in this prototype. The client supplies `X-Synthetic-Data: true`; direct API upload requests must explicitly supply it too. A header cannot detect real PHI—operators must keep real records out.
- Regex text redaction is partial. Images and scanned pages are **not de-identified** and can be sent to Gemini as uploaded.
- Local review mutations require a loopback client. If `COVERAGEGUARD_REVIEW_TOKEN` is configured, every mutation requires `X-Reviewer-Token`. Enter it in Policy Intelligence; it stays in the browser session. This is a local prototype boundary, not a user/role management system.
- The allowed external hosts are `https://www.cms.gov` and `https://cms.gov`, including each redirect and followed PDF link. Arbitrary external URLs and private-address redirects are rejected.
- Source fixture overrides are disabled unless explicitly enabled with `COVERAGEGUARD_ALLOW_SOURCE_FIXTURES=true`; fixture history is marked simulated.
- Uploads have a 10 MB document limit, a 14 MB request limit, image validation and a 20-megapixel limit. PDF extraction is limited to ten pages, with warnings. Vision submission is limited to five scanned page images; review any omitted content separately.

The app persists synthetic state to `backend/data/state.json` using an atomic local snapshot with file mode 0600. The snapshot includes claims, original extracted text/previews, proposals, rules, source hashes/history, alerts and audit records. It is ignored by Git. Set `COVERAGEGUARD_STATE_PATH` to choose another file, or to an empty string to disable persistence. Preserve this file when restarting a demo. Corrupt checkpoints fail startup rather than silently erasing history. This is not an encrypted medical-record database or tamper-proof audit system.

## Matching and approval

Insurer identity uses exact IDs or an explicit alias table. Plans require exact scope or an explicit `*` meaning all verified plans; empty plans never mean all plans. Type and code must match exactly. Unknown code/date/insurer/plan/effect remains unknown and blocks activation.

Selectable-text extraction independently checks identifiers, plans, dates and quoted effects against source text. This is a guard against obvious unsupported values, not proof that complex policy semantics were interpreted correctly. Image-based evidence requires explicit visual confirmation and reviewer notes. All changes still require human approval.

Preview and approval use the same rule builder and deterministic evaluator. Preview does not save claims, rules or alerts. Counts refer to unique affected claims; existing risk is not counted as new risk. Approval records immutable prior rule versions and corrections, rechecks whole claims, and reconciles alerts. Delays and cancellations preserve unrelated problems. Dates use an inclusive start and exclusive end. Historical evaluation supports an `as_of` knowledge timestamp.

## Tests

```bash
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python backend/tests/qa_e2e_runner.py
cd frontend
npm run build
```

Pytest deliberately disables live AI and local checkpoint writes. External failures and successful model responses are mocked for repeatability. There are currently third-party FastAPI TestClient/PyMuPDF deprecation warnings.

Opt-in live integration verification (synthetic data only):

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/tests/live_verify.py
```

The live script uses isolated in-memory state. It fetches CMS over real HTTP and, when a key is available, attempts an unfamiliar synthetic PDF → Gemini → preview → approval → alerts → audit workflow. Its JSON distinguishes live failure, deterministic fallback, and actual live success. Do not use a fallback result as evidence that Gemini worked. An explicit offline-extraction CMS check can use `COVERAGEGUARD_DISABLE_AI=true`.

## CalHacks demonstration

1. Start both servers. Use synthetic data only. Seed the existing 40-claim demonstration explicitly:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/simulator/reset
   ```
   Include `X-Reviewer-Token` if you configured a token.
2. Inspect Dashboard and Cases. Open Policy Intelligence and ingest **Demo Notice A — Drug A Exclusion**. Inspect the exact evidence and verify insurer, plan, type, code, effect and effective date. The UI shows whether Gemini or deterministic extraction was used.
3. Preview impact: the three applicable November Drug A claims change, while the earlier service remains covered by its baseline rule. Approve the proposal and inspect Cases, Updates and alerts (`GET /api/alerts`), plus `GET /api/audit`.
4. Ingest **Demo Notice B — Delayed Exclusion** and approve the December effective date. November exclusion alerts close. A claim with a separate missing prior authorization remains flagged; the automated PDF delay regression demonstrates this explicitly.
5. Click **Check Source Now** for CMS. Show the actual source status, meaningful fingerprint, timestamps and pending review. With a working model, extracted source proposals still need human review. With no key, conservative text extraction can stage an incomplete proposal for clarification. With a configured but failing model, the source reports `extraction_failed` and remains retryable. Repeat a successful check to show `unchanged` and no duplicate.
6. Turn demo mode off and clear claims via `DELETE /api/cases`. Preview reports zero analyzed claims. Policy versions and audit evidence remain available.

The connector currently monitors one configured CMS NCD page. Database-wide policy discovery, jurisdiction-aware Medicare adjudication, insurer credentials, and commercial payer feeds are outside the verified implementation.
