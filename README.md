# CoverageGuard

CoverageGuard helps hospital billing employees check **synthetic pending claims** and track insurance policy changes. It extends the existing FastAPI, React/TypeScript, Gemini policy extraction, deterministic engine, human review, version history and alerting implementation.

**Workflow A — Before submission:** import or upload a synthetic claim → identify exact insurer, plan, state, billing code and service date → evaluate approved, scoped, current local rules → show evidence, missing authorization/documents and employee follow-up. Missing or unverified policies produce **Unable to verify**, never claim approval. Findings cannot guarantee payment.

**Workflow B — Policy monitoring:** the backend discovers policy metadata → selects relevant documents within a bounded budget → detects changes → retains evidence and proposed versions → a person verifies the policy representation → deterministic re-evaluation identifies affected claims and reconciles alerts. A delay resolves the relevant issues while preserving unrelated requirements. The default enabled schedule is every 24 hours; the browser only displays results.

The independent hospital and insurer simulators demonstrate both workflows over real HTTP. They are prominently **DEMO / SIMULATED**, with no insurer affiliation. Real official source access is separately reported below. This is a single-worker local prototype for synthetic records, with no HIPAA or production-readiness claim.

## Run the complete demonstration

Requirements: Python 3.12+, Node.js 20.19+ or 22+, macOS/Linux (POSIX process lock).

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm ci)
cp backend/.env.example backend/.env
./scripts/run_demo.sh
```

Open `http://127.0.0.1:5173`. The script starts four separate processes: hospital API on 8101, insurer API on 8102, CoverageGuard on 8000, frontend on 5173. It enables only the demo source schedule, defaults to daily synchronization and disables external AI. Stop with Ctrl-C. Keep these ports free; do not run `dev.sh` concurrently.

For a short demonstration, start with:

```bash
COVERAGEGUARD_CHECK_INTERVAL=2 ./scripts/run_demo.sh
```

1. Open **Policy Monitoring**. Click **Import hospital claims**. Forty synthetic claims arrive from the independent hospital service. Before policy review, findings are unable to verify.
2. Click **Sync DEMO insurer** (or wait for the accelerated backend schedule). Inspect and approve the five **DEMO representations**. These approvals validate policy representations, not claims. Thirty-nine claims have no issue under simulated checked rules; H-003 has a separate missing authorization for HCPCS J1234.
3. In **Claims**, add a synthetic UHC claim: insurer `uhc`, exact plan `DEMO-UHC-PPO`, state `CA`, procedure `27447`, code system `CPT`, service date `2026-11-12`, synthetic member reference. Explicitly select **Use SIMULATED policy rules**. The findings cite the reviewed simulated UHC rule. An official-environment claim or unknown plan stays unable to verify.
4. In **Policy Monitoring**, publish the synthetic restriction. The insurer service publishes version 2, excluding the knee procedure from November 1. CoverageGuard detects it through its read-only connector. Inspect and approve the pending representation. Eight November UHC hospital claims are affected, plus the extra uploaded claim; earlier October claims and other insurers stay unchanged. Inspect **Alerts** and claim source evidence.
5. Publish the delay notice. Review the detected version 3, effective December 1. November knee exclusion alerts close. H-003's unrelated J1234 authorization issue remains. Repeat synchronization: five unchanged documents, no duplicate versions.

The demo persists across restarts. For a fresh isolated workspace, select new paths rather than deleting existing data:

```bash
COVERAGEGUARD_STATE_PATH=/tmp/coverageguard-new-demo.sqlite3 \
INSURER_SIMULATOR_STATE_PATH=/tmp/coverageguard-new-insurer.sqlite3 \
COVERAGEGUARD_CHECK_INTERVAL=2 ./scripts/run_demo.sh
```

## Patient PDF intake

In **Claims → Local clinical file / card intake**, select **DEMO / SIMULATED policies** or **Official / verified policies** explicitly. Upload a selectable PDF or text file, paste labeled text, or provide an image for manual correction. Clinical files stay local; scanned-image OCR is unavailable.

Click **Extract locally & check policies**, review the editable insurer/plan/member/state/service-date and procedure/code/system fields, correct missing details, then **Recheck corrected details** before filing. Findings show exact policy/version/date/evidence, missing documents, authorization reference presence and employee follow-up. Missing payer/plan/procedure information stays blank with a specific warning. Official mode never falls back to simulated rules.

Use the [synthetic UHC knee PDF](backend/tests/fixtures/synthetic_uhc_knee_claim.pdf) or [typed-text fixture](backend/tests/fixtures/synthetic_uhc_knee_claim.txt). Exact matching demo rules must first be synchronized and reviewed. The regression fix was verified through an actual browser PDF upload, filing, restriction and delay workflow; details and limits are in [PATIENT_INTAKE_REPORT.md](PATIENT_INTAKE_REPORT.md).

## Official source support and honest limits

| Source | Actual verification | Current limitation |
| --- | --- | --- |
| [UnitedHealthcare commercial policies](https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html) | HTML/PDF adapter implemented; technical research found index/document access | Automatic indexing **disabled pending publisher authorization**. Public medical policies do not prove a member's benefits or exact plan scope. |
| [Aetna medical CPBs](https://www.aetna.com/health-care-professionals/clinical-policy-bulletins/medical-clinical-policy-bulletins.html) | Published XML/HTML adapter implemented | Automatic indexing **disabled pending publisher authorization**. Exact member benefits and deviations remain unverified. |
| [Anthem California](https://www.anthem.com/ca/provider/policies/clinical-guidelines/?cnslocale=en_US_ca) | Live directory discovery: **98 metadata entries** | Sample PDF denied by publisher robots policy; no bypass. Only `bcbs-anthem-ca`, never generic/nationwide BCBS. |
| [CMS Medicare Coverage API](https://api.coverage.cms.gov/docs/) | Live documented API: **1,301 NCD/LCD metadata entries**, relevant NCD detail retrieved, **5,018 text characters** | Sample LCD metadata/detail returned **401** without a license token. Associated billing articles and MAC jurisdiction require review. No complete member-specific check demonstrated. |

Source checks ran October 24, 2026 Pacific / October 25 UTC. **No real commercial source or CMS source achieved a complete verified claim check.** Metadata discovery and text retrieval are reported separately from usable approved rule extraction. See [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md) and [recorded live results](verification/sync/live-sources.json).

UHC's [published terms](https://www.uhc.com/content/dam/uhcdotcom/en/npp/TOU-UHCPROVIDER-COM-EN.pdf) restrict harvesting; Aetna's [digital terms](https://www.aetna.com/legal-notices/digital-terms-of-use.html) require prior written consent for automated indexing. The server requires `COVERAGEGUARD_UHC_AUTHORIZATION_REFERENCE` / `COVERAGEGUARD_AETNA_AUTHORIZATION_REFERENCE` only after appropriate publisher permission. These operator attestations do not bypass robots, authentication or plan verification. CMS licensed access optionally uses server-side `CMS_LICENSE_TOKEN`; CoverageGuard does not accept license agreements for you.

## Configuration and persistence

For the main app without independent simulators, `./dev.sh` starts backend/frontend. Monitoring is off by default. Configure server environment before startup:

- `COVERAGEGUARD_SCHEDULER_ENABLED=true`: explicitly enable the backend worker.
- `COVERAGEGUARD_CHECK_INTERVAL=86400`: daily schedule; positive seconds for a demo.
- `COVERAGEGUARD_SCHEDULER_SOURCES=demo-insurer-api`: optional comma-separated source restriction. Omit to schedule all registered sources, subject to access gates.
- `COVERAGEGUARD_SYNC_DOCUMENT_LIMIT=5`: relevant document processing budget per source/run (maximum 20).
- `COVERAGEGUARD_STATE_PATH`: default `backend/data/coverageguard.sqlite3`; empty disables persistence. An explicitly selected `.json` path preserves legacy behavior. On first default SQLite startup, an existing sibling `state.json` is imported and retained.
- `COVERAGEGUARD_REVIEW_TOKEN`: optional local mutation token; client sends `X-Reviewer-Token`. Enter it in Policy Review.
- `COVERAGEGUARD_CORS_ORIGINS`: allowed frontend origins. `COVERAGEGUARD_API_URL` controls the frontend proxy target.
- `COVERAGEGUARD_HOSPITAL_SIMULATOR_URL` / `COVERAGEGUARD_INSURER_SIMULATOR_URL`: fixed loopback HTTP origins with explicit ports; defaults 8101/8102. No arbitrary remote simulator URLs.
- `SIMULATOR_ADMIN_TOKEN`: optional shared token for explicit simulator publication; never used to write to real insurers.

SQLite stores transactional snapshots of claims, catalog records, retained source text, proposals, immutable rule/document versions, sync history, alerts and audit records; mode 0600. It has queryable identity/version columns and preserves the existing domain store. It is not encrypted storage or a multi-process database application. Run **one API worker**: a POSIX lock rejects competing workers. Do not use distinct lock paths for processes sharing a database.

Only public/synthetic **policy documents** may use optional Gemini extraction (`GEMINI_API_KEY`, server-side `GEMINI_MODEL`). **Clinical files and identifiers never go to external AI**: clinical intake parses selectable text locally; scans/cards requiring OCR need manual structured entry. No-key policy extraction offers a conservative deterministic review fallback. Live Gemini generation remains unverified; the previous audit observed 404/429/timeouts and no new live success is claimed.

All patient imports/uploads require `X-Synthetic-Data: true`; the UI supplies it. This attestation does not detect real PHI. Uploads enforce size/type limits. Policy retrieval enforces approved HTTPS hosts, per-hop redirect checks, robots restrictions, bounded downloads, retries, caching and throttling. Policy queries contain no names, member identifiers, diagnoses or clinical documents. Only explicit synthetic simulator controls publish demo rules; real insurer ingestion remains read-only.

## Verification

```bash
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python backend/tests/qa_e2e_runner.py
(cd frontend && npm run build)
```

Latest: **176 pytest tests passed**, **38 acceptance checks passed**, TypeScript/Vite build passed. Dependency deprecation warnings remain. Existing tests were retained. New tests cover insurer/plan/region/code isolation, approval gates, privacy, retry/rollback, duplicate/race behavior, persistent versions and full restriction/delay impact.

With the three services running, the following scripts reset **only the selected synthetic workspace** and record real HTTP results. Point them at the intended disposable demo server:

```bash
COVERAGEGUARD_E2E_URL=http://127.0.0.1:8000 PYTHONPATH=backend \
  backend/.venv/bin/python backend/tests/run_sync_demo_e2e.py
# Requires the demo scheduler enabled with interval <= 5 seconds:
COVERAGEGUARD_E2E_URL=http://127.0.0.1:8000 PYTHONPATH=backend \
  backend/.venv/bin/python backend/tests/run_scheduled_demo_e2e.py
```

[Manual HTTP evidence](verification/sync/demo-http-e2e.json) verifies the extra upload, nine affected claims, source/version evidence, delay resolution and retained authorization. [Scheduled HTTP evidence](verification/sync/scheduled-http-e2e.json) verifies automatic detection with **zero explicit sync calls**. UI smoke checks cover Dashboard, Claims, Policy Monitoring, Alerts and preserved Policy Review.

Opt-in official source verification (no patient data, respects configured authorization gates):

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/tests/verify_sources_live.py
```

Public policy text remains a candidate until exact applicability, complex conditions, evidence and effective dates are sufficiently verified by a reviewer. Unknown scope never becomes an all-plan wildcard. CoverageGuard does not approve, deny, submit or alter patient claims.
