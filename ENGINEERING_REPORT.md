# CoverageGuard final engineering audit

Audit date: October 24, 2026 (America/Los_Angeles). Baseline: `d25cead`. Review branch: `codex/coverageguard-reliability`; main is not modified. `origin/main` was fetched at the start and again before review preparation and remained at the baseline.

The implementation preserves the FastAPI/React architecture, existing pages, deterministic evaluation engine and explicit synthetic presets. The final workflow is verified with repeatable deterministic and mocked tests. Public CMS retrieval/staging is verified live with explicitly disabled AI. Live Gemini generation did not succeed and is not claimed as verified.

## Findings and fixes

| Finding | Fix and evidence |
| --- | --- |
| HTML support was a regex strip, including navigation; removing the CMS form would remove the policy itself | BeautifulSoup parsing retains form contents, removes controls/chrome/scripts, and selects the actual NCD title, tracking and description panels. Live NCD 90.2 extraction returns 5,265 policy-text characters. Relevant headings/source URLs survive. |
| Downloaded hash committed before extraction, losing failed revisions | A raw byte hash is recorded separately. Normalized policy-text hash advances only after proposals, diffs and preview are successfully computed and staged. Configured AI failure leaves the source retryable. Regression verifies download success → extraction failure → retry success → exactly one proposal. |
| Navigation changes could announce policy revisions | SHA-256 covers normalized selected policy text, with raw-byte SHA-256 retained independently. Navigation/footer changes do not stage duplicates; a controlled genuine policy revision does. |
| Arbitrary URLs and redirect destinations could be fetched | HTTPS CMS host/port allowlist is checked before every hop and followed PDF link. HTTP failures, redirects, timeouts, unsupported types, empty/oversize files are handled. Official landing-page PDF delegation uses the existing PDF pipeline. |
| Missing insurer/plan became wildcard; checker used fuzzy payer/code/name matching | One exact matcher across evaluation/diff/preview/approval. Unrecognized identities remain distinct; empty/unknown claim plans never satisfy wildcard. Plans must have an explicitly stated scope. Item type and standardized code are exact. Similar codes and shared codes across insurers/plans are tested. |
| Preview and approval could version a different payer/plan/type rule | Shared pure proposal-to-rule builder. Scope must match for versioning; ambiguous references require clarification. New scoped rules cannot overwrite a different scope. Generated rule IDs are stable between preview and approval. |
| Extraction, intake and UI substituted synthetic dates, drugs, plans, payers, authorization and effects | Unknowns remain null/empty. Unfamiliar text uses a conservative parser rather than sample lookup. Explicit sample presets are retained. The UI provides editable insurer/plan/type and an unknown effect option. |
| A real supporting quote could accompany fabricated structured fields | Selectable-text validation independently checks payer aliases, exact codes/plans, date representations, wildcard statements and quoted effects. Unsupported values are cleared and approval is blocked. Visual evidence remains unverified until a reviewer confirms it with notes. These checks are conservative and do not replace semantic human review. |
| Preview overcounted items, counted pre-existing risks, and could affect unrelated claims | Whole-claim before/after evaluation through the same deterministic engine; unique affected/new-risk case counts; only changed applicable item verdicts included. No preview writes or inserted claims with demo disabled. |
| Historical rules were mutated to superseded; delay/cancellation could erase other problems | Previous versions remain unchanged. Explicit delay/cancellation revision chains and service dates determine active rules. `as_of` restores prior knowledge snapshots. Entire claims and item alerts are reconciled. A separate missing authorization survives a delayed drug exclusion. |
| Alert analyzer filtered for impossible case status `open` and referenced nonexistent verdict fields | Rebuilt reconciliation against the existing `CaseCheckResult` / `ItemVerdict` schema. New, superseded and closed alerts retain actual evidence, date and actions. No fabricated guaranteed rejection or treatment-switch recommendations. |
| Duplicate approvals and partial failures could corrupt workflow | Serialized, idempotent approval; copied/validated edits; transaction rollback on processing failure. Rejected proposals cannot be activated; approved proposals cannot be retroactively rejected. |
| Scheduler thread guard did not prevent multiple API processes | Explicit one-worker application with POSIX process lock; opt-in scheduler in lifespan; per-source locks for scheduler/manual checks; bounded provider requests and stop handling. Another API worker is rejected. Interrupted processing remains retryable on restart. |
| All state vanished on restart | Atomic local 0600 JSON checkpoints retain synthetic claims, rules/versions, proposals/documents, alerts, audit and source history. Tests restore successful approval and interrupted-source state. Clear-claims retains policy history and closes orphan alerts. |
| Source fixtures and initial connection state could look like real monitoring | Unchecked sources start `active`, not `connected`. Scheduler status is visible; test overrides require explicit configuration and are marked simulated. They cannot establish the API's real-connection flag. CMS staged documents can be opened in the review UI. |
| Public mutation endpoints, wildcard CORS, oversized/invalid uploads and provider logging | Loopback/token mutation authorization, configured origins, synthetic-data acknowledgement for uploads, bounded request/file/image handling, header-based Gemini credentials and sanitized errors. Provider response bodies and request URLs with keys are not logged. |
| Policy bulletin substring lookup could show another policy's citation | Exact bulletin identity lookup; a regression rejects `R-1` as a match for `R-1042`. |
| Seeded commercial payer criteria looked authoritative | Seeded rules/bulletins explicitly identify synthetic examples; docs/UI distinguish public CMS retrieval from commercial insurer APIs. |

## Verification actually executed

Environment: Python 3.12.10, Node v25.9.0, npm 11.12.1. Backend dependencies installed into the root repo's isolated `backend/.venv`; frontend installed using `npm ci` and the existing lockfile.

| Command / workflow | Result |
| --- | --- |
| Baseline pytest before edits | 49 passed |
| Baseline frontend `npm run build` | Passed TypeScript and production build |
| Final `backend/.venv/bin/python -m pytest backend/tests -q` | **117 passed**, six third-party FastAPI TestClient / PyMuPDF deprecation warnings |
| `backend/.venv/bin/python backend/tests/qa_e2e_runner.py` | **38 passed**, zero failed |
| `npm run build --prefix frontend` | Passed TypeScript and Vite production build; 37 modules transformed |
| API response inspection | Health, dashboard, cases, connection, sources and audit returned HTTP 200 with expected contracts |
| Unfamiliar synthetic PDF | Upload → text extraction → grounded fields/quote → preview → human approval → stored v2 → claim risk → explainable alert → audit passed with deterministic extraction |
| Separate exclusion and delay PDFs | Exclusion creates risk, separate uploaded delay moves the date, resolved alert closes, unrelated prior authorization stays open |
| Concurrent approvals and source checks | One rule version/approval event and one source proposal; no duplicates |
| Failure injection | Failed extraction is retried; failed approval rolls back; a reset during extraction does not resurrect old proposals |
| Empty caseload | Demo disabled, claims cleared, zero analyzed claims, no silent demo generation |
| Native Chrome against isolated production preview | Dashboard, Cases, Updates and Policy Intelligence rendered. Verified 40-claim demo → extracted quotation/fields → preview of 3 affected/new-risk claims → approval of 3 claims → Updated policy and Action Center queue for C-001/C-005/C-008. Final ID-stability regression was added after the browser exposed changing generated IDs. |
| Live CMS with deterministic extraction explicitly selected | HTTP 200; NCD 90.2 / Next Generation Sequencing; 5,265 extracted characters; stable meaningful hash; one incomplete proposal staged; next actual network check `unchanged`; zero duplicate proposals; zero unapproved rules applied |
| Controlled CMS revision fixture | Navigation change unchanged; genuine text/date change stages another review; rules remain untouched |
| Mocked Gemini | Successful multi-proposal JSON/evidence mapping and HTTP failure/fallback/key handling passed |
| Live Gemini | **Not verified**. Model catalog HTTP 200; `gemini-2.5-flash` generation HTTP 404; `gemini-3-flash-preview` HTTP 429; `gemini-3.8-flash` read timeout, including a 60-second extraction attempt. Never counted fallback as live success. |

Live artifacts: [CMS deterministic verification](verification/live-cms-deterministic.json) and [Gemini attempt](verification/live-gemini-attempt.json). They contain public-source metadata and synthetic test values, no API keys or patient information. The separately verified CMS staging flow deliberately used deterministic extraction; the configured-but-failing AI run correctly stayed `extraction_failed` and did not commit a processed hash.

No actual CMS policy revision was induced on the government site. Revision detection was exercised using a controlled fixture. The live NCD has no complete standardized target/plan mapping from the conservative parser, so its staged proposal needs clarification and cannot be applied. Linked-PDF handling was tested with controlled HTTP responses, not an observed live linked CMS PDF.

Existing tests were retained. Fixture corrections supplied explicit plan/insurer/evidence where the prior assertions relied on unsafe defaults; the old assertion that a future rule alone proved current coverage was replaced by an explicit affirmative baseline. Plan-specific approval expectations now require a separate scoped rule rather than silently versioning an all-plan baseline. Source-status assertions reflect the new retry/review states. New negative tests protect each corrected assumption.

## Remaining limitations

1. Live Gemini generation remains blocked by the observed service/model/quota/timeouts. Obtain working model access and rerun `backend/tests/live_verify.py` before claiming successful live AI integration. `GEMINI_MODEL` is configurable; the current stable model identifier was checked against [Google's official model documentation](https://ai.google.dev/gemini-api/docs/models).
2. The CMS connector monitors one configured public NCD page. It does not discover the entire database, implement Medicare jurisdiction/benefit logic, or connect to commercial insurer accounts. HTML layout changes may require selector maintenance.
3. Conservative text extraction cannot interpret every policy, billing code standard, condition or date format. Visual/complex evidence requires human correction. Code presence in a document does not prove that all clinical criteria were understood correctly.
4. The engine implements this prototype's existing coverage/prior-approval/document model. It is not a validated clinical, coding, benefits or payment determination system. Conflicting/unknown rules require verification rather than presumed coverage.
5. Synthetic-only acknowledgement, partial regex redaction and loopback/shared-token review are practical prototype boundaries, not full privacy controls or role-based access. Images are not de-identified. Do not submit real patient data or expose the prototype publicly for that use.
6. The checkpoint is local, unencrypted, single-process and not tamper-proof. It is appropriate for synthetic demonstration state, not multi-server production storage. POSIX `flock` requires macOS/Linux. Do not run multiple workers or independent servers against the same checkpoint with different lock paths.
7. Uploaded files are limited to 10 MB and images to 20 megapixels. PDF extraction covers at most ten pages; vision sends at most five scanned page images. Review truncation warnings and omitted pages manually.
8. This is a manual browser smoke test, not a committed automated browser suite or exhaustive browser/accessibility certification. Tests use synthetic fixtures; no real patient or insurer transaction was performed.

## Compatibility changes to review

Existing routes and response structure remain where practical, with additive source/evidence/extraction metadata. Intentional safety changes: upload requests require `X-Synthetic-Data: true`; configured reviewer tokens apply to mutations; invalid/incomplete approvals return 422 instead of incorrectly returning 404; missing intake fields no longer produce fabricated samples; unknown service dates can be null; claim clearing retains policy history; source states now distinguish retry failures and pending review. The frontend is updated for these changes. API consumers should adopt the same requirements.

## Local run and CalHacks sequence

[README.md](README.md#run-locally) provides dependency installation, environment setup, one-worker startup, optional scheduler/token configuration and test commands. [The CalHacks demonstration sequence](README.md#calhacks-demonstration) explicitly seeds 40 synthetic claims, ingests exclusion and delay notices, previews and approves changes, inspects alerts/audit, checks CMS twice, and demonstrates the empty caseload. Explain the extraction mode aloud; do not advertise a fallback demonstration as a live Gemini call.

## Exact files modified or added

- `.gitignore`
- `ENGINEERING_REPORT.md`
- `PROGRESS.md`
- `README.md`
- `backend/.env.example`
- `backend/app/connectors/base.py`
- `backend/app/connectors/change_detector.py`
- `backend/app/connectors/official_policy_source.py`
- `backend/app/connectors/scheduler.py`
- `backend/app/db/store.py`
- `backend/app/domain/models.py`
- `backend/app/engine/checker.py`
- `backend/app/engine/matcher.py`
- `backend/app/impact/analyzer.py`
- `backend/app/intake/analyzer.py`
- `backend/app/intelligence/document_processor.py`
- `backend/app/intelligence/evidence_validator.py`
- `backend/app/intelligence/impact_previewer.py`
- `backend/app/intelligence/policy_diff.py`
- `backend/app/intelligence/policy_extractor.py`
- `backend/app/intelligence/rule_builder.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/tests/conftest.py`
- `backend/tests/live_verify.py`
- `backend/tests/qa_e2e_runner.py`
- `backend/tests/test_action_center.py`
- `backend/tests/test_api.py`
- `backend/tests/test_external_connector.py`
- `backend/tests/test_fixes.py`
- `backend/tests/test_policy_intelligence.py`
- `backend/tests/test_reliability.py`
- `frontend/src/api.ts`
- `frontend/src/components/PolicyIntelligence.tsx`
- `frontend/src/components/UpdatesPage.tsx`
- `frontend/src/components/UploadPatientFileModal.tsx`
- `frontend/src/types.ts`
- `frontend/vite.config.ts`
- `verification/live-cms-deterministic.json`
- `verification/live-gemini-attempt.json`

The untracked nested `clahacks-13.0/` repo and `plan.md` were preserved and are not part of this change. No credentials, runtime checkpoints or generated frontend bundles are committed.
