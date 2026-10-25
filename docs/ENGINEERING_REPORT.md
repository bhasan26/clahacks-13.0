# CoverageGuard — hospital findings and insurer policy synchronization

**Patient-intake regression update:** See [PATIENT_INTAKE_REPORT.md](PATIENT_INTAKE_REPORT.md) for the subsequent selectable-PDF/editable-review repair, actual browser/HTTP evidence and current verification (**176 tests**, 38 acceptance checks, frontend build). The report below describes the preceding policy-sync delivery.

Implementation branch: `codex/insurer-policy-sync`. Base: merged reliability audit `d0948f0c4d2f0b32c38f3d926899b5c201a8a2d0`. Verification: October 24, 2026 Pacific / October 25 UTC. This report replaces the earlier audit's current-status description; that audit remains in Git history.

## Result and architecture

Both requested hospital workflows are implemented on the existing application. A hospital employee can import forty claims from an independent service or add a synthetic claim, see exact insurer/plan/state/code/date findings, inspect evidence and request a targeted refresh. The backend independently discovers and synchronizes policy metadata, stages changed representations, preserves evidence/version history, and re-evaluates claims after human approval. Nothing submits, denies, edits or guarantees payment for a patient claim.

```
Independent Hospital API ── read-only import ──> local claims
                                                │
Official sources / Independent Insurer API       │ exact local matching
         │                                      ▼
read-only connector → metadata catalog → bounded relevant fetch
         → content fingerprint → extraction / evidence → human review
         → approved versioned rules → deterministic full-claim evaluation
         → findings + affected claims + reconciled alerts + audit history
```

The existing document processing, policy extraction, validation, rule builder, diff/preview, approval, deterministic evaluator, alerts and frontend design were reused. The old demo API and CMS page-monitor API remain for compatibility; the main UI/scheduler use the new multi-source workflow. No old tests were deleted. Baseline before implementation: 117 tests and the frontend build passed.

## Connectors and safe discovery

`policy_base.py` defines policy-only queries, download records and discovery/fetch behavior. `registry.py` registers explicit source identities. Commercial adapters share `commercial.py`; CMS and the synthetic API have separate adapters.

- UHC: actual commercial medical/drug index and PDF links. Authorization gate runs before discovery **and** fetch.
- Aetna: follows the landing page's actual published XML index (`data-xmlfile`), deduplicates CPBs and fetches HTML. No invented search API. Authorization gate runs before any request.
- Anthem California: `bcbs-anthem-ca` only; source identity cannot be selected by generic `bcbs`. HTML directory is discoverable; blocked PDFs are reported as restricted.
- CMS: endpoints verified against the publisher's OpenAPI at `https://api.coverage.cms.gov/docs/v1/coverage-api.json`, linked by its Swagger client. NCD and final LCD reports provide discovery; detail URLs use documented identifiers/versions. Only explicit same-host next URLs are followed where report token parameters are undocumented. Documented related-document and primary-jurisdiction endpoints support bounded pagination. LCD metadata retains associated billing article references and MAC/state information when accessible. Activation requires explicit billing-article and jurisdiction review; neither is inferred from a national index.
- Demo: reads fixed loopback `/policies` and `/policies/{id}` from an independently persisted service. It does not read CoverageGuard's rule store. Structured synthetic scope is validated against catalog identity before staging, and still requires human approval.

Caseload queries remain local. They include only insurer/plan/environment, code, medical topic and jurisdiction. Outbound catalog requests do not receive patient names, member references, diagnoses, clinical documents or claim records. Discovery matches metadata before fetching documents. Missing code metadata may select topic candidates but cannot establish applicability. Default five documents per source/run, maximum twenty; unprocessed/retry candidates take precedence to avoid starvation. Catalog metadata is searchable across the complete store before the 500-result response limit, including insurer, plan and jurisdiction.

`policy_http.py` enforces approved HTTPS hosts, no URL credentials, each redirect hop, explicit-port restrictions, bounded streaming (10 MB), 20-second request/10-second connection timeouts, three temporary-failure attempts with backoff, long Retry-After deferral, throttling and five-minute metadata caching. Authorization headers are removed on cross-host redirects. Robots matching supports user-agent specificity, longest matching paths, wildcard and end anchors. The documented CMS programmatic API is treated as an API rather than a crawler; this grants no authentication bypass. Error reports exclude raw provider responses and credentials. Simulator URLs must be fixed `127.0.0.1` HTTP origins with explicit ports and no paths/queries/credentials.

Publisher permission is distinct from technical reachability. After researching the terms, UHC and Aetna automated connectors were disabled by default. An operator may supply an authorization reference **after** obtaining the publisher's permission. References do not override robots/authentication or establish plan scope. Existing persisted source cards refresh these restrictions on startup/API reads; a new authorization reference changes status to unchecked, never connected.

## Actual official-source verification

Final gate-respecting execution is recorded in [live-sources.json](verification/sync/live-sources.json). Earlier technical observations are preserved separately in [technical-source-observations.json](verification/sync/technical-source-observations.json), explicitly marked as preceding the terms restriction. They do not establish authorized ongoing access.

| Insurer/source and URL | Type | Discovery | Document retrieval | Usable verified rules | Exact plan/jurisdiction | Complete claim check |
| --- | --- | --- | --- | --- | --- | --- |
| [UHC](https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html) | HTML / PDF | Final run: authorization required. Earlier technical observation: 250 entries. | Final run: disabled. Earlier relevant knee PDF returned text, bounded to ten pages. | No | No | No |
| [Aetna](https://www.aetna.com/health-care-professionals/clinical-policy-bulletins/medical-clinical-policy-bulletins.html) | Published XML / HTML | Final run: authorization required. Earlier technical observation: 920 deduplicated entries. | Final run: disabled. Earlier CPB 0673 HTML returned text. | No | No | No |
| [Anthem CA](https://www.anthem.com/ca/provider/policies/clinical-guidelines/?cnslocale=en_US_ca) | Regional HTML / PDF | Live: 98 directory entries. | Sample PDF blocked by robots. No bypass. | No | Affiliate CA known; exact plan unverified. | No |
| [CMS](https://api.coverage.cms.gov/docs/) | Documented JSON API | Live: 1,301 NCD/LCD metadata entries. | NCD 285 v1: 5,018 text characters. Sample LCD detail/metadata: HTTP 401 without token. | No approved clinical rule; text retrieval only. | No complete code/plan/MAC/article evidence verified. | No |

UHC's [terms PDF](https://www.uhc.com/content/dam/uhcdotcom/en/npp/TOU-UHCPROVIDER-COM-EN.pdf) restrict harvesting. Aetna's [digital terms](https://www.aetna.com/legal-notices/digital-terms-of-use.html), Unauthorized Conduct, require express prior written consent for automated indexing and systematic downloading. The Anthem [robots policy](https://www.anthem.com/robots.txt) blocks the attempted PDF retrieval. CMS licensed endpoints require an operator-supplied token/appropriate rights; no license acceptance was performed.

This independently demonstrates real official CMS discovery/detail connectivity and partial regional directory connectivity. It does **not** demonstrate synchronized commercial member benefits, complete Medicare adjudication or an insurer partnership. Catalog counts are observations at the recorded time, not coverage completeness metrics.

## Sync lifecycle, versions and persistence

A global non-overlap lock prevents concurrent syncs. The scheduler is opt-in (`COVERAGEGUARD_SCHEDULER_ENABLED=true`), defaults to 86,400 seconds, and runs server-side. `COVERAGEGUARD_SCHEDULER_SOURCES` can restrict it to the demo source. Frontend five-second polling merely refreshes displayed data. The POSIX process lock enforces a single API worker.

Each source records attempted/successful/next timestamps, health and limitations, consecutive failures and discovered/fetched/changed/unchanged/pending/failed counts. Each persisted run has gaps, errors and completion state. Restart loading marks interrupted runs; persisted due times resume. Temporary failures retry with bounded exponential scheduling; authorization-required sources defer to the normal interval. Manual and targeted refresh use the same engine.

Metadata revision, document reference, downloaded fingerprint and successfully processed fingerprint are separate. Formatting-normalized text avoids irrelevant HTML layout duplicates; structured demo fingerprints compare rule semantics rather than quotes/version labels. Truncated PDFs additionally retain a download hash so changes outside processed pages cannot silently appear unchanged. This normalization is conservative text comparison, not a general semantic equivalence solver: materially rewritten prose can require another review.

Failed extraction keeps the parsed document and structured source for safe retry. The successful fingerprint advances only with successful staging. Staging proposals, extracted documents, immutable versions and counters is committed transactionally; controlled checkpoint failure rolls back in-memory changes and keeps the retry document. A generation check prevents a reset during fetch/extraction from resurrecting old state. Missing index entries become `not_in_latest_index`, never automatic cancellation. A stale/superseded extracted document cannot be approved against a newer catalog revision/document reference.

`persistence.py` introduces SQLite `records(kind,id,insurer_id,policy_id,version,payload)` with a composite identity/version index. Existing domain objects remain the unit of work; the entire snapshot is one transaction. Claims, rules/history, catalog, documents/versions, proposals, source state/runs, alerts and audit records survive restart. The default is `backend/data/coverageguard.sqlite3`, mode 0600. A legacy sibling JSON snapshot is imported only when the default SQLite file is absent, leaving the JSON untouched. Explicit `.json` paths retain prior behavior for compatibility; empty path disables persistence. Corrupt state fails startup rather than silently resetting.

This remains an in-memory single-worker application with SQLite checkpoints, not a normalized multi-tenant query service, encrypted clinical database, distributed scheduler or tamper-proof audit log.

## Findings, approval and privacy

Rules now carry jurisdiction, code system, verified scope, verification status, catalog/revision/sync provenance and LCD/article review flags. Matching requires exact insurer/affiliate, plan (or explicitly verified wildcard), region, item type, code/system and service date. Publication/revision dates are separate from effective dates. Empty plans, unknown scope, unsupported conditions and absent rules remain unknown. Official-environment claims cannot use synthetic rules. Public connector extraction always stages unverified scope for correction, even when the model returns plausible data.

The hospital findings endpoint evaluates approved current evidence; source documents older than 48 hours or known failed/absent from an index are omitted with a gap. Findings include reference/version, effective date, source URL/quotation, required documents, authorization needs and follow-up. Missing member reference or items produces unable-to-verify. These results are advisory and distinguish simulated evidence. The old engine's internal `Approved` compatibility status is displayed as “No checked issue”; it is not a patient/insurer approval.

Approval reuses source validation, scope confirmation, immutable version history, deterministic preview, complete-claim re-evaluation and alert reconciliation. Version 2 restriction affects exact matching November claims; version 3 delay closes only resolved item alerts. Unrelated authorization issues remain. Alert quotations are now looked up only when an actual governing rule exists; a missing-rule alert cannot borrow an unrelated pending proposal's evidence.

Clinical intake is **local only**. The clinical Gemini call is disabled regardless of configured key. Selectable PDF/text can use local extraction; image/scanned OCR is not implemented and requires manual structured entry. Public/synthetic policy documents can use optional server-side Gemini, with conservative deterministic fallback if no key exists. Live Gemini generation is still unverified: the earlier audit observed 404/429/timeouts. No new success is claimed.

Synthetic-data attestation remains required on patient import/upload routes. Local mutation/origin checks and optional reviewer token remain; credentials stay server-side. This is not production authentication. No PHI detection, certified de-identification, HIPAA compliance or real hospital integration is claimed.

## API and UI

New routes under `/api`:

- `GET /policy-sync/sources`, `GET /policy-sync/history`, `POST /policy-sync/run` (optional source/claim/catalog targeting).
- `GET /policies/catalog` (insurer/query filtering), `GET /policies/catalog/{id}/versions`.
- `POST /claims/import`, `GET /claims/findings`, `GET /claims/{id}/findings`.
- `GET /workflow/summary`, `POST /demo/import-hospital`, `POST /demo/publish-insurer`.

Existing clinical/file upload, cases, policy proposal correction/preview/approval, audit, alerts and version routes remain. The demo publication proxy is an explicit local synthetic admin action; real source connectors only read.

Navigation now emphasizes Dashboard, Claims, Policy Monitoring, Alerts and supporting Policy Review. Existing colors/layout are preserved. Claims supports structured entry/JSON upload, existing clinical/card intake, exact insurer/plan/region and explicit demo-environment choice, insurer/status/specialty filters, source evidence and targeted refresh. Monitoring shows actual source access state, timestamps, schedule/counters/limitations, catalog search, runs and pending review. Dashboard, alerts and case metadata refresh to show backend changes without owning synchronization. Alerts show insurer, claim, policy/version, effective date, evidence and follow-up. Policy Review retains source inspection/correction and adds scope/jurisdiction/code-system/article confirmation. Static fake insurer connectivity was replaced with a link to real source status.

## Verification and evidence

| Check | Actual result |
| --- | --- |
| Baseline full pytest | 117 passed before changes |
| Final full pytest | **157 passed**, six third-party deprecation warnings |
| Existing acceptance runner | **38 passed, zero failed** |
| Frontend | TypeScript and Vite production build passed |
| Independent services over real HTTP | 40 imports, five approved baseline representations, extra UHC upload, nine affected restriction claims, delay resolution, preserved J1234 authorization, five unchanged on repeat, 94 audit events |
| Actual backend schedule over real HTTP | Two-second demo interval, **zero manual sync calls**, baseline/restriction/delay discovered automatically; human approval remains explicit |
| Official sources | Gate-respecting live matrix above; no verified commercial or CMS member-specific check |
| Native Chrome smoke | Dashboard, Claims, Policy Monitoring, Alerts and supporting Policy Review inspected on isolated production preview; an unfamiliar official UHC plan returned unable-to-verify with no demo fallback |

New tests cover exact UHC/Aetna/affiliate/Medicare isolation, wrong plan/region/code/system, unknown insurer, stale/missing scope, required authorization/documents, synthetic/official separation, read-only/privacy boundaries, safe hosts/redirects/size/robots, publisher gates before requests, source retries, extraction retry retention, checkpoint rollback, restart persistence, duplicates/races, metadata search beyond 500 rows, approval gating, exact restriction/delay impact and evidence attribution. Old tests remain; one scheduler test was adapted to the new sync entry point.

Scripts and recorded artifacts:

- `backend/tests/run_sync_demo_e2e.py` → [demo-http-e2e.json](verification/sync/demo-http-e2e.json).
- `backend/tests/run_scheduled_demo_e2e.py` → [scheduled-http-e2e.json](verification/sync/scheduled-http-e2e.json).
- `backend/tests/verify_sources_live.py` → [live-sources.json](verification/sync/live-sources.json).
- `scripts/run_demo.sh` starts the four local processes. [README.md](README.md) gives commands, exact scenario and expected counts. HTTP demo scripts reset only the selected synthetic workspace; use an isolated instance.

## Changed implementation files

New backend modules: `connectors/{policy_base,policy_http,commercial,cms_connector,simulated,registry,sync_engine}.py`, `db/persistence.py`, `domain/sync_models.py`, `engine/findings.py`, `sync_api.py`, independent `simulators/{common,hospital,insurer}.py`. Modified existing `connectors/scheduler.py`, `db/store.py`, `domain/models.py`, `engine/{checker,matcher}.py`, `impact/analyzer.py`, `intake/analyzer.py`, `intelligence/{policy_extractor,rule_builder}.py`, `main.py` and `.env.example`.

Frontend: new `ClaimsWorkspace.tsx`, `PolicyMonitoring.tsx`, `WorkflowOverview.tsx`; updated App routing/polling, API/types, Sidebar, PolicyIntelligence, DashboardPage, CasesPage, CaseDetailModal and UploadPatientFileModal. Test additions: policy-sync regressions plus three opt-in HTTP/live scripts; existing external connector scheduler test updated. Documentation, demo launcher and four small verification JSON artifacts are included. Runtime databases, credentials, generated frontend output, nested unrelated checkout and local `plan.md` are excluded.

## Remaining gaps

- Actual commercial automation requires publisher permission; exact member benefits/plan applicability are unavailable. No commercial end-to-end claim verification is claimed.
- Anthem PDF robots restrictions prevent that sample document ingestion. CMS LCD detail/related access requires appropriate license token; actual MAC/article applicability remains unverified.
- Public medical policy language can contain complex clinical criteria beyond the deterministic schema. Reviewers must not approve an incomplete representation as fully authoritative. Public source text and metadata are candidates only.
- Daily document budgets and partial metadata can leave gaps; they are visible. The database is not an exhaustive insurer coverage mirror. Text normalization does not prove semantic equivalence of arbitrary prose.
- No clinical OCR/external clinical AI. Manual structured entry is required when local text extraction fails. No new live Gemini generation success.
- Single API worker, local synthetic records, coarse snapshot persistence, no distributed scheduling/roles/encrypted PHI storage or production-readiness claim.
