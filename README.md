# Coverage Guard

A simple insurance document check with four pages, using the existing React, Tailwind, and FastAPI stack and styling.

1. **New Insurance Check** — insurance card and prescription uploads, Check, and a result with extracted information and policy sources.
2. **All Requests** — persisted uploads with insurer, treatment, date, status, and a report dialog.
3. **Insurance Database Connection** — the actual local records connection, read-only policy access, and the direct insurer connection status.
4. **Latest Insurance Updates** — retrieved policy statements with an explicit effective date and a link to the original source. Empty until a matching dated source has been retrieved for an uploaded request.

## Run

```sh
./dev.sh
```

Frontend: http://localhost:5173. Backend: http://127.0.0.1:8000.
Use the existing `backend/.venv` and `frontend/node_modules`. If setting up elsewhere:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd frontend
npm ci
```

## Document and policy behavior

Uploads accept PDF (up to five pages), PNG, JPG, WebP, and text files up to 8 MB each. Text PDFs are read locally; images and up to two scanned PDF pages use the already installed RapidOCR engine. Document processing stays local and needs no API key.

The app extracts insurer, patient, member, plan and available card information plus the actual prescribed medication or procedure. It never substitutes demo names or identifiers. Every uploaded prescription is assumed valid for the policy test, including sample or fictional prescriptions. Patient names, member IDs, signatures, authenticity markings, and identity mismatches do not block execution. Only missing files, unreadable files, an unknown insurer, or an unextractable treatment prevent comparison.

**Accepted means the checked policy criteria match in this test; it is not live insurer approval.** A policy mismatch identifies the unmet requirement and links to the policy. Missing clinical criteria or inaccessible sources produce **Needs policy review**, rather than invented acceptance or rejection. For the retrieved UnitedHealthcare diabetes policy, the test compares the stated diagnosis and qualifying clinical facts with its actual coverage criteria. It does not require proof that the uploaded prescription is authentic.

Public searches send insurer and treatment names, not patient or member identifiers. Retrieved documents must come from recognized official insurer domains. Reports show original source URLs, policy IDs when available, exact excerpts, retrieval dates, and explicit effective dates when stated. Simple formulary statements require an exact plan, medication, and effective-date match. No realistic-looking policies, dates, or approvals are generated.

Public search is bounded to seven seconds, three source documents, and no automatic retries. Results are cached for 15 minutes. Unsupported insurers and inaccessible sources produce an unverified result. The direct insurer database integration is not configured; the connection page states this plainly. No endpoint writes to an insurer database.

Requests and reports are stored in `backend/data/insurance_requests.sqlite3`; set `COVERAGEGUARD_REQUEST_DB` to override that path. Existing legacy databases are untouched.

## Verify

```sh
npm run build --prefix frontend
backend/.venv/bin/python -m pytest backend/tests -q
```

Tests cover complete and incomplete uploads, PDF and image extraction using local sample files when available, assumed-valid fictional prescriptions, optional patient identifiers, policy acceptance, specific policy mismatches, incomplete clinical criteria, persistent report history, unsupported files, past and upcoming effective dates, and rejection of ambiguous or untrusted policy evidence. Browser workflow verification lives in `verification/browser-check.cjs` and uses an existing Playwright installation; it does not add a runtime dependency.
