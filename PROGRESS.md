# Coverage Guard: Engineering Progress & Rationale

**Document Purpose:** Complete audit of what has been implemented, how each component works, and the design rationale behind every engineering decision.

---

## 🎯 Executive Summary & Core Philosophy

In healthcare insurance processing, hallucinations and unpredictable LLM verdicts lead to costly claim rejections, patient delays, and legal liabilities. 

**Our Core Architecture Rule:**
> **"Code decides coverage; the LLM only reads documents and words text."**

Every coverage verdict, temporal check, and impact alert in CoverageGuard is produced by **100% deterministic, test-proven Python logic** backed by immutable versioned rules.

---

## 🏗️ What Was Built & Why

### 1. Vertical Sidebar & Popover Architecture (`frontend/src/components/Sidebar.tsx`)
- **What was built:**
  - Left navigation sidebar across every page:
    - Top: `“Coverage Guard”` brand mark and `“Claims Sentinel”` identifier.
    - Vertical navigation: `Dashboard`, `Cases`, `Updates` with crisp active states.
    - Bottom: Connection chip: `● Demo Insurance Co. · Access active` with green dot.
  - Small popover dropdown on chip click:
    - Insurer name: `Demo Insurance Co.`
    - Status: `Connected`
    - Access: `Access active`
    - Mode: `Read-only` (*“Read-only” appears only here. Nothing else on the site talks about limitations.*)
    - Last check: `06:00 today`
    - Demo triggers: `[ Run check now ]`, `[ Simulate check failure ]`
  - Check failure alert: Chip turns amber (`“Check pending”`) with a one-line banner at the top of the content area:  
    *“Rules may be out of date. Re-check in progress.”*
- **Why we did it:**
  - Provides a clean, calm, professional layout where the dashboard and cases occupy the full content area, keeping navigation accessible while placing connection telemetry neatly at the bottom.

---

### 2. Page 1: Dashboard (`frontend/src/components/DashboardPage.tsx`)
- **What was built:**
  - **Row 1:** Exactly three number cards, nothing else in the row:
    1. **Approved** (Green `#2A835F`): cases that are complete and covered (30 cases).
    2. **Needs attention** (Amber `#D97706`): an update or rule affects the case (5 cases).
    3. **Missing or wrong info** (Red `#DC2626`): a required document, number or field is missing, or a value is wrong (5 cases).
  - **Row 2 Left:** Clean claims submission:
    - Big percentage: $30 / 40 = 75.0\%$.
    - Horizontal bar with editable target marker labelled `“Target 85%”`.
  - **Row 2 Right:** Cases by specialty:
    - Horizontal bars, one per specialty (Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology), sorted descending by count. Count at the end of each bar.
    - Each bar split by the three statuses, using identical green, amber, red status colors.
  - **Row 3:** Latest updates (the 3 most recent):
    - One line each: what changed, effective date, number of open cases affected.
    - `“View all updates”` link navigating to the Updates page.
  - **No other widgets:** Zero money metrics, zero durations, zero aging.
- **Why we did it:**
  - Keeps the dashboard uncluttered and immediately understandable. No more than 6 elements above the fold.

---

### 3. Page 2: Cases (`frontend/src/components/CasesPage.tsx`)
- **What was built:**
  - `“Upload patient file”` button.
  - Clean table: `Case ID`, `Specialty`, `Status`, `Items (count)`.
  - Filters:
    - Status: `All`, `Approved`, `Needs attention`, `Missing or wrong info`.
    - Specialty: `All`, `Cardiology`, `Oncology`, `Orthopedics`, `Neurology`, `Gastroenterology`.
  - Clicking any row opens the Case Detail view.
- **Why we did it:**
  - Gives officers immediate access to their claims without exposing raw insurer rule search engines.

---

### 4. Page 3: Case Detail (`frontend/src/components/CaseDetailModal.tsx`)
- **What was built:**
  - Header: Case ID, specialty, status badge.
  - Item list showing one result per item: `Covered`, `Not covered`, `Prior approval needed`, `Document missing`, `Value wrong`.
  - Single plain sentence format for every issue:
    > *“Drug X is not covered from 1 Nov 2026. Rule R-1042. Review with the physician before submitting.”*
  - Strict notification principle: agent only notifies; never edits, rejects, or submits, and never suggests a medical alternative.
- **Why we did it:**
  - Eliminates administrative rework and prevents legal liability by never prescribing medical alternatives.

---

### 5. Page 4: Updates (`frontend/src/components/UpdatesPage.tsx`)
- **What was built:**
  - Reverse-chronological list of 6 updates from the insurer.
  - Filter by type: `All`, `Drug`, `Procedure`, `Document`, `Approval`.
  - Each entry: what changed, item type badge, effective date, status (`Announced`, `Effective`, `Delayed`, `Cancelled`), and `“Affects N open cases”` (clicking it filters Cases to those case IDs).
  - Employees see updates and effect on their cases, but cannot browse or search raw insurer rules.
- **Why we did it:**
  - Gives officers transparency into upcoming policy revisions while maintaining payer intellectual property boundaries.

---

### 6. Backend Check Engine & Seed Data (`backend/app/db/store.py`, `backend/app/engine/checker.py`)
- **What was built:**
  - Pure deterministic rule evaluation over versioned rules.
  - 40 cases seeded across 5 specialties (Cardiology: 10, Oncology: 9, Orthopedics: 8, Neurology: 7, Gastroenterology: 6).
  - Clean claims initially 75.0% against an 85.0% target marker.
  - 6 insurer updates seeded.
  - `“Run check now”` button / API endpoint (`POST /api/check/run-now`):
    - Applies Rule R-1042 v2 (Drug A excluded Nov 1).
    - Re-checks all 40 open cases.
    - Moves 3 open cases (`C-001`, `C-005`, `C-008`) from **Approved** $\rightarrow$ **Needs attention**.
    - Counts update dynamically: Approved drops from 30 to 27, Needs attention rises from 5 to 8, clean claims becomes 67.5%.
  - Mock insurer endpoints: `GET /v1/rules/snapshot` and `GET /v1/rule-changes?since=` with server-scoped API key.

---

## 📊 Verification & Test Summary

```
=================================================================
📊 QA TEST SUMMARY: 38 PASSED | 0 FAILED (Total: 38)
=================================================================
[x] Phase 0: System reset returns 200
[x] Phase 1: 40 cases across 5 specialties, clean claims < target, 3 dashboard cards
[x] Phase 2: Header chip shows "Demo Insurance Co.", "Access active", "Read-only" in popover only
[x] Phase 3: Case detail item results, rule reference, single plain sentence format
[x] Phase 4: "Run check now" moves 3 open cases to Needs attention, updates counts
[x] Phase 5: Target editing & check failure simulation (amber chip, warning banner)
[x] Phase 6: Restricted employee view (no raw rules listing reachable)

Pytest Unit Suite: 9 / 9 PASSED in 0.19s
Vite Production Build: Built in 305ms with 0 errors
```
