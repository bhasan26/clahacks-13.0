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

Pytest Unit Suite: 17 / 17 PASSED in 1.03s
- test_redact_sensitive_identifiers PASSED
- test_clinical_document_intake_no_fake_drug_when_empty PASSED
- test_alert_lifecycle_and_task_queue PASSED
- test_api_health_and_connection PASSED
- test_api_dashboard_metrics PASSED
- test_api_cases_and_filters PASSED
- test_api_case_detail_item_sentences PASSED
- test_api_run_check_now_flow PASSED
- test_api_target_editing_and_failure_toggle PASSED
- test_baseline_case_evaluations PASSED
- test_temporal_boundary_and_plain_issue_sentence PASSED
- test_no_matching_rule_behavior PASSED
- test_extract_policy_from_text PASSED
- test_what_if_impact_boundary_dates PASSED
- test_delayed_policy_clears_november_risks PASSED
- test_approve_policy_workflow_and_idempotency PASSED
- test_reject_proposal PASSED

Vite Production Build: Built in 329ms with 0 TypeScript errors
```
