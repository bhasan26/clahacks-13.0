# CoverageGuard implementation status

Patient intake repaired on `codex/patient-pdf-intake-fix`: local selectable-PDF/text extraction, explicit DEMO/OFFICIAL selection, editable details/recheck, exact state/code-system propagation, all-item filing, shared evidence-backed findings and specific missing-field warnings. Actual browser upload and real HTTP restriction/delay verification passed; **176 backend tests**, **38 QA checks**, and frontend build passed. See [PATIENT_INTAKE_REPORT.md](PATIENT_INTAKE_REPORT.md). The earlier delivery status follows.

Updated October 24, 2026 Pacific / October 25 UTC.

The earlier reliability audit was merged as PR #1 (`d0948f0`). The current implementation extends that baseline on `codex/insurer-policy-sync`, preserving existing tests and document/rule review tools.

Completed:

- Insurer-aware synthetic claim import/upload and evidence-backed findings, exact insurer/plan/region/code matching, honest unknowns and explicit simulated/official separation.
- Pluggable UHC, Aetna, Anthem California, CMS documented API and independent synthetic insurer adapters, metadata discovery and bounded relevant document fetches.
- Daily opt-in backend scheduling, manual/targeted refresh, persisted status/history, retries, failed-document retention, successful fingerprint discipline, atomic staging and duplicate/race protections.
- SQLite snapshot persistence with legacy JSON migration/compatibility, retained policy evidence and immutable versions.
- Independent hospital API with forty claims and insurer API with separately persisted rule publication, restriction and delayed effective date scenarios.
- Dashboard, Claims, Policy Monitoring, Alerts and supporting Policy Review UI; local-only clinical parsing and no clinical-data transmission to external AI.
- Publisher restriction research: UHC/Aetna automation disabled pending permission, Anthem PDF robots denial reported, CMS LCD 401 reported without bypass.

Verification:

- **157 pytest tests passed**; **38 existing acceptance checks passed**; frontend TypeScript/Vite build passed.
- Real HTTP full workflow: extra upload, nine affected UHC claims, unrelated insurer/date isolation, delay resolution, retained authorization requirement, repeat unchanged and 94 audit events.
- Real backend automatic schedule: two seconds, zero explicit sync calls, restriction and delay automatically discovered; review remains explicit.
- Official sources: CMS 1,301 metadata entries plus real NCD detail; Anthem 98 directory entries but sample PDF restricted. No complete official insurer/member-specific claim check demonstrated.
- Native Chrome smoke checks covered all five navigation destinations, an unfamiliar official UHC plan's unable-to-verify result, policy evidence and closed/open alerts.

Run instructions, source matrix and boundaries: [README.md](README.md). Architecture, changed files, full evidence and remaining gaps: [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md). Live and synthetic HTTP observations: [verification/sync](verification/sync).

Known gaps remain explicit: commercial publisher authorization/member benefits; CMS licensed LCD/article/MAC verification; clinical OCR/manual correction; unverified live Gemini generation; single-worker local prototype limits. No production or HIPAA claim.
