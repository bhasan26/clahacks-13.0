# CoverageGuard verification progress

Updated October 24, 2026 (America/Los_Angeles). Baseline `d25cead`; branch `codex/coverageguard-reliability`.

## Completed

- Established the baseline: 49 existing backend tests passed; frontend TypeScript/build passed. No newer `origin/main` commit was available when the audit began.
- Added backend dependency requirements and environment example.
- Replaced regex HTML stripping with parsed CMS policy-section extraction, preserving titles/headings/source URLs. Correctly handles CMS's page-wide ASP.NET form. Safe official PDF links use the PDF pipeline.
- Separated downloaded-byte SHA-256 from normalized policy-text SHA-256. Failed extraction never advances the processed fingerprint. Identical successful checks create no duplicate proposals; concurrent checks serialize.
- Added distinct source states and timestamps, observable extraction failures, safe restart checkpoints and opt-in monitoring in one process.
- Unified exact matching and proposal rule construction across preview, diff and approval. Missing insurer/plan/type/code/effect/date blocks activation. Explicit all-plan rules are supported; unknown claims never become wildcards.
- Removed guessed payer, plan, billing item, authorization, diagnosis and date values from unfamiliar intake/extraction. Explicit synthetic presets remain available.
- Independently grounded structured fields in selectable source text; scanned evidence requires reviewer confirmation and recorded notes.
- Fixed alert generation against the actual domain schema. Entire claims are re-evaluated; delays/cancellations close resolved item alerts while retaining unrelated problems.
- Preserved historical rule versions and knowledge snapshots. Approval is serialized, idempotent and rolls back memory changes if processing fails.
- Added safe URL/redirect validation, bounded uploads/image validation, explicit CORS origins, local/token review authorization, synthetic-only notices, and credential-safe model headers/error handling.
- Fixed review controls for missing insurer/plan/type/effect, visible extraction status, CMS staged-proposal review, and misleading empty-preview/source-connection wording.
- Persisted synthetic state atomically; claim clearing retains policy and audit history.

## Verification results

| Check | Actual result |
| --- | --- |
| Backend pytest | 117 passed; six third-party deprecation warnings |
| Existing QA acceptance runner | 38 passed |
| Frontend TypeScript + production build | Passed |
| Browser smoke checks | Dashboard, Cases, Updates, Policy Intelligence render; synthetic extraction and review tested |
| Unfamiliar synthetic PDF → extraction → preview → approval → rule version → claim risk → alert → audit | Passed using deterministic extraction; Gemini success contract covered by mocks |
| Separate exclusion PDF and delay PDF; unrelated authorization retained | Passed |
| Fetch succeeds → extraction fails → retry succeeds → one proposal | Passed, automated controlled integration |
| Concurrent source checks / repeated approval | No duplicate proposal/version/approval event |
| Empty caseload with demo disabled | Zero analyzed claims; no synthetic insertion |
| Live CMS HTTP/HTML | HTTP 200; NCD 90.2 title and 5,265 characters of policy text |
| Live CMS with explicit deterministic extraction | One incomplete proposal staged; second check unchanged; zero duplicate proposals; zero approved rules applied |
| Live Gemini | Not verified: 2.5 Flash returned 404; 3 Flash Preview returned 429; 3.8 Flash timed out |

The public CMS result establishes retrieval, text extraction, staging and unchanged detection. It does **not** establish live Gemini extraction or clinically complete Medicare rules. The incomplete CMS proposal requires clarification and cannot affect a claim.

See [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md) for exact changed files, regression rationale, remaining limitations and detailed test evidence. See [README.md](README.md) for setup and the demonstration sequence. Historical claims of full live insurer connectivity or successful live AI extraction should not be used as verified status.
