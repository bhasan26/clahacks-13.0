# Coverage Guard: Engineering Progress & Rationale
## Multimodal AI Insurance Intelligence Platform (CalHacks 13.0)

**Document Purpose:** Complete audit of what has been implemented, how each component works, and the design rationale behind every engineering decision.

---

## 🎯 Executive Summary & Core Philosophy

In healthcare insurance processing, hallucinations and unpredictable LLM verdicts lead to costly claim rejections, patient delays, and legal liabilities. 

**Our Core Architectural Principle:**
> **"AI extracts. Code decides. Humans approve."**

1. **Gemini AI extracts:** Reads scanned circulars, letters, PDFs, or photos into structured proposal models with exact document citations.
2. **Deterministic Code decides:** All coverage calculations, temporal governing-date boundaries, and impact analyses are run by 100% deterministic, test-proven Python logic.
3. **Humans approve:** Extracted policies are held in `pending_review` until an authorized claims officer previews the impact, makes any corrections, and approves them into production.

---

## 🏗️ Architecture & Modules Implemented

### 1. Dedicated Intelligence Engine (`backend/app/intelligence/`)
- **`document_processor.py`**:
  - Validates file formats and enforces 10MB file size limits.
  - Ingests selectable text PDFs via `pypdf`/`fitz`.
  - Supports scanned PDFs by rendering page rasters for multimodal vision analysis.
  - Decodes images (PNG, JPEG, WebP) and handles direct text pastes.
- **`evidence_validator.py`**:
  - Normalizes and verifies whether extracted quotes actually exist in source document text.
  - Flags unverified or fabricated assertions with actionable reviewer warnings.
- **`policy_extractor.py`**:
  - Queries Gemini multimodal models with strict JSON schemas.
  - Extracts insurer identity, target codes, effective dates, prior-auth criteria, and supporting quotes.
  - Marks missing fields as explicit nulls/unknowns without fabricating codes or plans.
- **`policy_diff.py`**:
  - Compares proposed changes against current active rules in `DataStore`.
  - Classifies change types: `new_rule`, `modification`, `delayed`, `cancelled`.
  - Identifies prior rule version, restriction severity, and conflicts.
- **`impact_previewer.py`**:
  - What-If simulation engine.
  - Evaluates open claims against a temporary in-memory rule snapshot without persisting changes or polluting production alerts.
  - Evaluates date boundaries: Oct 28 claims remain unaffected by Nov 1 policies, while Nov 5 claims are flagged.

### 2. Explainable Action Center & Alerts (`backend/app/impact/analyzer.py`, `backend/app/domain/models.py`)
- **`Alert` & `AlertTask` Models**:
  - Tracks Claim ID, status ("Potential Denial Risk"), reason, effective date, rule version, evidence quotation, suggested follow-up, and administrative tasks.
  - Interactive Action Queue tasks:
    1. Review coverage rule and governing date criteria.
    2. Verify member eligibility and plan formulary tier.
    3. Check prior authorization status or submit PA packet.
    4. Obtain required clinical documentation or lab results.
    5. Contact responsible clinical department before submission.
  - Interactive task statuses (`open`, `in_progress`, `completed`) with officer attribution and completion timestamps.
  - Optional AI feature: Automated generation of administrative follow-up messages for clinical staff with safety disclaimers (human review required, external auto-dispatch disabled).

### 3. Multimodal Clinical Intake Improvements (`backend/app/intake/analyzer.py`, `UploadPatientFileModal.tsx`)
- Ingests selectable PDFs, scanned clinical charts, and insurance card images.
- Implements privacy redaction (`redact_sensitive_identifiers`) masking SSNs, phone numbers, and email addresses prior to LLM calls.
- Eliminates hardcoded fallbacks and fabricated drugs: empty notes return empty items with explicit guidance.
- Eliminates fabricated confidence percentages.
- Preserves verbatim source text spans for extracted items.

### 4. Interactive Policy Intelligence UI (`frontend/src/components/PolicyIntelligence.tsx`)
- Modern two-column review workspace consistent with CoverageGuard's hospital design system.
- Drag-and-drop file upload, file browsing, and text paste modes.
- 1-click synthetic demo presets for Document A, Document B, and Document C.
- Left column: Original document viewer with page navigation and verified evidence quote highlight box.
- Right column: Extracted policy fields with live editing, validation warnings, and Policy Diff comparison.
- What-If Claim Impact Simulator:
  - Instant preview of affected claims before approval.
  - Shows Total Claims Analyzed, Affected Claims, New Denial Risks, and Unchanged Claims.
  - Granular table detailing Case ID, Item Code, Previous Verdict, Simulated Verdict, and Reason.
- Approval workflow:
  - "Approve & Apply Policy" commits new rule version, re-evaluates hospital caseload, updates alerts, and writes to immutable audit log.
  - Idempotency protection prevents duplicate approvals.

---

## 🧪 Automated Test Suite & QA Verification

```
=================================================================
🩺 COVERAGEGUARD COMPREHENSIVE QA ACCEPTANCE TEST SUITE
=================================================================
[PHASE 0: PRE-CONDITIONING]
  ✓ System reset returns 200
[PHASE 1: SEED DATA & ACCEPTANCE CRITERIA]
  ✓ Exactly 40 cases in caseload
  ✓ Row 1: Approved count is positive
  ✓ Row 1: Needs attention count is positive
  ✓ Row 1: Missing or wrong info count is positive
  ✓ Three cards show different numbers
  ✓ Clean claims percentage is calculated correctly
  ✓ Clean claims target is 85%
  ✓ Clean claims figure is below target (marker is meaningful)
  ✓ Exactly 5 specialties reported (Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology)
  ✓ Specialties are sorted descending by count
  ✓ Dashboard shows exactly 3 latest updates
  ✓ Exactly 6 updates in seed data
[PHASE 2: HEADER CHIP & POPOVER (READ-ONLY RULE)]
  ✓ Connection reports insurer name 'Demo Insurance Co.'
  ✓ Connection status is 'Access active'
  ✓ Connection mode is 'Read-only'
[PHASE 3: CASE DETAIL & ISSUE SENTENCE SPECIFICATION]
  ✓ Case C-003 has Case ID, specialty, and status
  ✓ Case C-003 status is 'Needs attention'
  ✓ Item result is one of: Covered, Not covered, Prior approval needed, Document missing, Value wrong
  ✓ Item names rule reference
  ✓ Item has one plain sentence
  ✓ Item has plain what-to-do guidance
[PHASE 4: 'RUN CHECK NOW' DAILY CHECK TRIGGER]
  ✓ Run check now returns success
  ✓ Flags affected cases (C-001, C-005, C-008)
  ✓ Counts updated: Approved decreased by 3 (from 30 to 27)
  ✓ Counts updated: Needs attention increased by 3 (from 5 to 8)
  ✓ Clean claims percentage recomputed
  ✓ C-001 transitioned to 'Needs attention'
  ✓ C-001 item result is 'Not covered'
  ✓ C-001 issue names Rule R-1042
  ✓ C-001 issue names effective date 1 Nov 2026
  ✓ C-001 action instructs: Review with the physician before submitting
[PHASE 5: TARGET EDITING & CONNECTION FAILURE SIMULATION]
  ✓ Clean claims target updated to 92.5%
  ✓ Failed check turns chip to 'Check pending'
  ✓ Warning banner present: 'Rules may be out of date. Re-check in progress.'
  ✓ Restored check chip returns to 'Access active'
[PHASE 6: RESTRICTED ACCESS & SECURITY]
  ✓ Demo state reset cleanly to 40 cases and 75% clean claims

=================================================================
📊 QA TEST SUMMARY: 38 PASSED | 0 FAILED (Total: 38)
=================================================================

Pytest Unit & Integration Suite: 49 / 49 PASSED in 4.25s
- Action Center & Privacy Redaction: 3 passed
- API Endpoints & Dashboard: 6 passed
- Deterministic Rule Engine: 3 passed
- Policy Intelligence & Approvals: 5 passed
- Fixes 1-7, 9-10 Safety & Regression Suite (test_fixes.py): 18 passed
  * test_unfamiliar_insurance_doc_no_invented_fields PASSED
  * test_missing_mandatory_fields_blocks_store_approval PASSED
  * test_unrelated_document_produces_no_fabricated_rules PASSED
  * test_multiple_policy_rules_no_loop_variable_leakage PASSED
  * test_multipage_pdf_page_identification PASSED
  * test_evidence_verification_strict_matching PASSED
  * test_evidence_verification_scanned_page PASSED
  * test_document_processor_corrupted_pdf PASSED
  * test_document_processor_unsupported_file_format PASSED
  * test_document_processor_oversized_file PASSED
  * test_matcher_exact_code_no_substring PASSED
  * test_matcher_insurer_isolation PASSED
  * test_matcher_plan_wildcard PASSED
  * test_matcher_effective_date_boundaries PASSED
  * test_multi_issue_claim_adjudication_on_exclusion_delay PASSED
  * test_duplicate_proposal_approval_rejected PASSED
  * test_empty_caseload_in_non_demo_mode_returns_zero_cases PASSED
  * test_what_if_preview_side_effect_free PASSED
- Real Official Insurer Connector Suite (test_external_connector.py): 14 passed
  * test_connector_fingerprint_computation PASSED
  * test_connector_fetch_success_mocked PASSED
  * test_connector_http_timeout_handling PASSED
  * test_connector_http_access_restricted_403 PASSED
  * test_connector_http_server_error_500 PASSED
  * test_change_detection_initial_baseline PASSED
  * test_change_detection_unchanged_document PASSED
  * test_change_detection_triggers_staged_proposals_without_direct_rule_mutation PASSED
  * test_change_detection_timeout_records_error_history PASSED
  * test_api_get_sources PASSED
  * test_api_post_sources_check_success PASSED
  * test_api_get_sources_history PASSED
  * test_api_get_sources_status PASSED
  * test_scheduler_thread_safety_no_duplicates PASSED

Vite Production Build: Built in 335ms with 0 TypeScript errors
```

---

## 🌐 Feature 8: Real External Insurer Policy Source Integration
- **Selected Source:** Centers for Medicare & Medicaid Services (CMS) Medicare Coverage Database (National Coverage Determinations & Clinical Guidelines).
- **Official URL:** `https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=372`
- **Why CMS NCDs:** Authorized, publicly accessible government source; provides transparent healthcare determinations without paywalls or anti-bot blocks; compliant with ethical web crawling standards.
- **Fingerprinting & Change Detection:**
  - Computes SHA-256 content hashes.
  - Normalizes dynamic HTML script nonces and query-string cache-busters so only substantive policy text changes trigger alerts.
  - Unchanged checks log an audit entry and create 0 duplicate proposals.
  - Changed checks route new policy updates through multimodal extraction and stage proposals in `pending_review`.
  - Zero unapproved rule mutations occur without reviewer approval.
- **Scheduler & Endpoints:**
  - Thread-safe background monitor (`PolicyMonitoringScheduler`) preventing duplicate threads during reload.
  - Endpoints: `GET /api/sources`, `POST /api/sources/check`, `GET /api/sources/history`, `GET /api/sources/status`, `GET/POST /api/settings/demo-mode`.
