# Patient PDF intake regression repair

Branch: `codex/patient-pdf-intake-fix`, based on merged `main` (`08d3fe8`). Verified October 24, 2026 Pacific / October 25 UTC.

The existing patient intake modal now extracts selectable synthetic PDFs locally, shows editable claim fields, offers an explicit policy environment, and uses the same scoped approved-policy findings as the Claims workspace. Clinical files and identifiers are never sent to an external LLM or insurer source.

## What was wrong

- Clinical PDF insurance details were not consistently merged into the card/payer result, losing the member reference and other fields.
- The narrow parser ignored procedure names, jurisdiction and code systems, and could mistake unrelated numbers for billing codes.
- Intake forced ordinary files into official mode; there was no explicit simulated-policy choice.
- Provisional evaluation generated a member reference when absent and omitted jurisdiction/code system, preventing exact matches.
- Extracted values were read-only, only the first item was filed, and generic validation concealed the specific missing fields.
- The saved-case dialog fabricated insurer/plan fallback labels. Its action center could show closed alerts and a hardcoded unrelated policy quotation.

## Repair

`intake/local_parser.py` reads explicit insurer/plan/member/state/service/authorization/procedure/code labels with colon, equals, inline-separated and label-on-next-line layouts. It recognizes explicit CPT/HCPCS/NDC contexts, supports common explicit date formats, and preserves names without guessing a missing billing code. Plan names never become invented plan IDs. Numeric member IDs and provider identifiers are not treated as procedure codes. Pending authorization is not an authorization reference. Conflicting or invalid fields require review.

`analyzer.py` reuses the bounded local document processor for selectable PDFs and text, including optional card PDFs. Images and scanned pages produce an honest no-local-OCR warning and editable manual-entry workflow. The clinical Gemini shim remains disabled. No synthetic patient name, member number, date, payer or plan is fabricated.

`/api/intake/analyze` accepts an explicit `policy_environment` (defaults to official) and reviewed claim fields. It returns the canonical provisional claim, specific missing fields, warnings, detailed findings, and the compatible legacy check result. Source fields merge locally; corrections can clear or replace values. A review-only recheck does not retain warnings about fields that were subsequently supplied. Jurisdiction, each item's code system and all requested items survive preview and filing.

The modal retains the existing colors, rounded panels and layout. It adds a prominent DEMO/OFFICIAL selector, editable payer/plan/member/state/date/authorization fields and item rows. Editing invalidates displayed findings until rechecked; incomplete claims cannot be filed. Official mode never borrows a synthetic rule. A complete claim with missing authoritative policy evidence can be filed with an unable-to-verify result.

`ClaimFindingsPanel.tsx` is shared by intake, Claims and the saved-case dialog. It shows insurer, plan, state, member reference, service date, procedure/code/system, matched or missing policy, governing version/date, source quotation/link, required/missing documents, authorization requirement/reference presence and employee follow-up. References are explicitly described as provided, not validated with the insurer. Missing-policy reasons distinguish unavailable official evidence, wrong plan/state/type/code/system, dates and stale/unverified sources. Saved-case detail uses the same source-freshness filter. The old generic record verdict now names the actual missing fields and retains recognized items.

The action center displays only open actual alerts. Closed exclusions no longer appear as current problems after a delay, and absent source evidence never produces a hardcoded PLAN-GOLD/DRUG-A quotation. Existing alert tasks and policy-review tools remain available.

## Actual verification

- Baseline: **157 backend tests passed** before changes.
- Final: **176 backend tests passed**, including **19 new patient-intake regressions**. Existing tests were retained. Six third-party deprecation warnings remain.
- Existing QA acceptance runner: **38 passed, zero failed**.
- Frontend: TypeScript and Vite production build passed.
- Regression tests send actual generated PDF bytes through the modal's base64 analyze endpoint, file the returned details, synchronize the independent simulator contract, approve versions and evaluate the saved claim. Coverage includes A–E below, four field layouts, PDF/text/card merging, editable corrections, multiple items, scans/images, invalid/missing fields, numeric identifier isolation, wrong plan/state/code/system, required documents, pending/missing authorization and no external clinical requests.
- Native Chrome: selected the actual PDF in the operating-system file picker; verified extracted editable UHC fields, baseline evidence, missing-plan warning and disabled filing, correction/recheck, official-mode isolation, and successful filing to the caseload.
- Real HTTP independent services: the browser-filed claim then followed the restriction/delay lifecycle. No main-workspace claims or policy history were reset. The open Claims findings panel refreshed after approval.

| Scenario | Observed result |
| --- | --- |
| A. Approved synthetic baseline | No issue detected under SIMULATED checked rules; exact UHC plan/CA/CPT 27447, version 1 and quotation shown. |
| B. November 1 restriction | Retrieval stages the representation without changing the claim. After human approval, that same November claim is Not covered under version 2, with source/date evidence and an alert. |
| C. Delayed to December 1 | After review, the November claim returns to no checked issue under its governing baseline; the exclusion alert closes. H-003's unrelated J1234 authorization issue remains. |
| D. Missing plan/insurer/procedure | Specific missing-field warnings; absent values remain blank; no default Demo Insurance Co., generated member ID or generic Patient Record verdict. |
| E. Official mode, no verified UHC policy | Unable to verify; explicit missing official-policy reason; no simulated fallback. |

Recorded browser/HTTP evidence: [verification/intake/pdf-http-e2e.json](../verification/intake/pdf-http-e2e.json). Test code: [backend/tests/test_patient_pdf_intake.py](../backend/tests/test_patient_pdf_intake.py).

## Test it in the UI

1. Open Claims → **Local clinical file / card intake**.
2. Select **DEMO / SIMULATED policies** explicitly.
3. Upload [synthetic_uhc_knee_claim.pdf](../backend/tests/fixtures/synthetic_uhc_knee_claim.pdf), or paste the [text fixture](../backend/tests/fixtures/synthetic_uhc_knee_claim.txt).
4. Click **Extract locally & check policies**. Review insurer `uhc`, plan `DEMO-UHC-PPO`, state `CA`, member `SYNTHETIC-001`, procedure `27447` / `CPT`, service date `2026-11-12`, and authorization `PA-DEMO-001`.
5. Inspect findings and evidence. If you edit a field, click **Recheck corrected details**, then **File reviewed case to caseload**.
6. Clear the plan and recheck to see its specific warning; restore it and recheck. Switch to official mode and recheck to confirm the honest missing-policy result.

A matching approved demo baseline must exist first. In a fresh demonstration, import the forty hospital claims, sync DEMO and review the baseline representations in Policy Monitoring. The existing simulator cannot republish an older restriction after the delay is already published; use a separate fresh demo workspace for the full A→B→C sequence, as described in README. Existing working demo records are preserved by this fix.

## Limits

This is structured local extraction, not general medical natural-language understanding. Unlabeled/ambiguous details, unsupported layouts, complex clinical interpretation and scanned-image OCR can require manual correction. A procedure name never establishes an unprovided billing code. Official commercial access/benefit verification restrictions remain unchanged. There is no external clinical AI transmission, live insurer authorization confirmation, payment guarantee, HIPAA compliance or production-readiness claim.
