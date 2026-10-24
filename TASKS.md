# CoverageGuard: 24-Hour Build Plan & Task Roadmap

**Goal:** Build a production-grade, demo-ready web platform for hospital insurance claims officers that:
1. **Pre-checks patient files** against active insurer coverage rules with strict citation (Rule ID, version, date, source).
2. **Autonomously syncs rule changes** (additions, exclusions, delays, cancellations) and alerts officers to impacted open cases.
3. **Features a 1-click Insurer Simulator** that allows live demonstrations of rule changes, delays, cancellations, and stale-feed detection in front of judges.

---

## ⏱️ 24-Hour Execution Timeline

```
[00:00 - 03:00] Phase 1: Foundation, Schemas & Seed Dataset
[03:00 - 08:00] Phase 2: Core Deterministic Engine & Insurer Feed Sync
[08:00 - 14:00] Phase 3: Modern Claims Officer Web Application (React + Vite)
[14:00 - 18:00] Phase 4: Insurer Simulator & AI Document Extraction
[18:00 - 21:00] Phase 5: End-to-End Verification & Golden Test Suite
[21:00 - 24:00] Phase 6: Demo Rehearsal, Polish & Pitch Readiness
```

---

## 📋 Detailed Task Breakdown

### Phase 1: Foundation, Schemas & Seed Data (Hours 0 – 3)
- [ ] **1.1 Workspace & Dependencies Setup**
  - [ ] Initialize Python backend environment (`FastAPI`, `uvicorn`, `pydantic`, `sqlalchemy`, `httpx`).
  - [ ] Initialize frontend application with Vite, React, TypeScript, Tailwind CSS, Lucide icons.
  - [ ] Configure unified development runner (single command or concurrently to launch both).
- [ ] **1.2 Contract-First Domain Models (`domain/`)**
  - [ ] Define `Rule` model (rule_id, version, insurer_id, plan_ids, category, target, effect, effective_from, effective_to, status, source_ref).
  - [ ] Define `Case` model (case_id, insurer_id, plan_id, member_ref, service_date, diagnoses, items, documents, prior_approval_ref, status).
  - [ ] Define `CheckResult` & `ItemVerdict` (verdict: covered, excluded, prior_approval_needed, documents_missing, no_rule_found).
  - [ ] Define `Alert` model (alert_id, case_id, item_code, rule_id, from_version, to_version, status: open/superseded/closed, closed_reason).
- [ ] **1.3 Synthetic Seed Dataset & Database Initializer**
  - [ ] Seed standard rules (`DRUG-A` covered under `R-101 v1`, `PROC-1` requires prior approval under `R-202 v1`, `SVC-9` unknown).
  - [ ] Seed 4 canonical demo cases:
    - `C-001`: Contains `DRUG-A` with service date `Nov 10, 2026` (Expected: Clear $\rightarrow$ Flagged after Nov 1 rule change).
    - `C-002`: Contains `DRUG-A` with service date `Oct 28, 2026` (Expected: Clear $\rightarrow$ Remains Clear, before effective date).
    - `C-003`: Contains `PROC-1` without prior approval (Expected: Needs Attention - prior approval missing).
    - `C-004`: Contains `SVC-9` (Expected: Cannot Assess - no matching rule).

---

### Phase 2: Core Deterministic Engine & Insurer Sync (Hours 3 – 8)
- [ ] **2.1 Deterministic Check Engine (`engine/checker.py`)**
  - [ ] Implement pure evaluation function: `check(case, rules, governing_date) -> CaseCheckResult`.
  - [ ] Match rules on `insurer_id`, `plan_id` (or wildcard `*`), item type & code.
  - [ ] Evaluate temporal validity: `effective_from <= governing_date < (effective_to or infinity)`.
  - [ ] Resolve precedence: Plan-specific over wildcard, latest `effective_from`, highest version.
  - [ ] Emit structured result citing rule ID, version, effective date, and non-clinical officer action advice.
- [ ] **2.2 Insurer Feed & Change Detection (`sync/`)**
  - [ ] Implement mock insurer API client to fetch snapshots and incremental change events.
  - [ ] Implement change detector (handles `added`, `modified`, `status_changed`, `delayed`, `cancelled`).
  - [ ] Save versioned rules without mutating historical versions.
- [ ] **2.3 Impact Analyzer & Alert Manager (`impact/`)**
  - [ ] On rule sync, re-run all open cases against the new rule set.
  - [ ] Compare previous verdict vs new verdict per item.
  - [ ] Create new alerts if item status deteriorates (e.g. Covered $\rightarrow$ Excluded).
  - [ ] If a rule is delayed past the service date or cancelled, automatically close the alert (`closed_reason: "change delayed"` / `"change cancelled"`).
  - [ ] Deduplicate and supersede existing alerts with compound key `(case_id, item_code, rule_id)`.
- [ ] **2.4 Append-Only Audit Trail (`audit/`)**
  - [ ] Log every sync event, rule version bump, check run, and officer acknowledgment.

---

### Phase 3: Claims Officer Dashboard UI (Hours 8 – 14)
- [ ] **3.1 Global Shell & Navigation**
  - [ ] Header with hospital/officer profile, system clock indicator, and Feed Health Badge (Active vs Stale).
  - [ ] Main views: **Alerts Inbox**, **Cases Explorer**, **Rules Library**, and **Audit Log**.
- [ ] **3.2 Alerts Inbox**
  - [ ] Live notification cards showing: Rule ID, Version Diff ($v1 \rightarrow v2$), Impacted Cases count, and Effective Date.
  - [ ] Collapsible case impact cards with clear guidance: *"DRUG-A is now excluded effective Nov 1, 2026. Action: Notify physician before submission."*
  - [ ] One-click "Acknowledge" with optional officer notes.
  - [ ] Filter by status (Open / Closed / Superseded).
- [ ] **3.3 Cases Explorer & Detail Drawer**
  - [ ] Table of patient cases with badges: `Clear` (green), `Needs Attention` (amber), `Cannot Assess` (gray).
  - [ ] Case Detail Drawer:
    - Breakdown of all drugs, procedures, and services.
    - Status chip next to every item.
    - Rule citation hover card (Rule ID, Version, Source, Verified timestamp).
    - "Re-check Case" button.
- [ ] **3.4 Rules Browser**
  - [ ] Searchable, filterable catalogue of all loaded insurer coverage rules.
  - [ ] Version history timeline modal for any selected rule showing changes, delays, and notes.

---

### Phase 4: Insurer Simulator & AI Document Intake (Hours 14 – 18)
- [ ] **4.1 Interactive "Insurer Simulator" Demo Bar**
  - [ ] Floating dock / control drawer accessible anywhere in the app for testing:
    - **Button 1:** *Publish Rule Exclusion* (`DRUG-A` excluded effective Nov 1).
    - **Button 2:** *Delay Rule* (Push effective date from Nov 1 to Dec 1).
    - **Button 3:** *Cancel Rule* (Revert exclusion).
    - **Button 4:** *Simulate Feed Outage* (Triggers stale warning banner).
    - **Button 5:** *Reset Demo State* (Restores seeded database in 1 click).
  - [ ] Instant toast notifications on the UI when changes sync.
- [ ] **4.2 AI Patient File Intake Drawer**
  - [ ] Simple drop-zone for patient clinical summaries (PDF or raw text).
  - [ ] LLM extraction endpoint (Gemini API with strict JSON schema):
    - Extracts `service_date`, `diagnoses`, `items` (drugs, procedures), and `documents`.
    - Returns exact `source_text` citations for each extracted field.
  - [ ] Split-screen confirmation UI: Left side shows extracted source text, right side shows editable form fields before submission.

---

### Phase 5: Verification & Golden Tests (Hours 18 – 21)
- [ ] **5.1 Backend Test Suite (`pytest`)**
  - [ ] Table-driven golden tests for all verdict combinations.
  - [ ] Boundary tests on effective dates (day before, exact date, day after).
  - [ ] Idempotency tests: Replaying the same sync events does not create duplicate alerts.
  - [ ] Alert lifecycle test: Added $\rightarrow$ Delayed $\rightarrow$ Cancelled transitions.
- [ ] **5.2 End-to-End Demo Script Dry Run**
  - [ ] Step 1: Start fresh (Inbox empty, 4 cases seeded, feed green).
  - [ ] Step 2: Show `C-001` (Clear) and `C-003` (Needs approval).
  - [ ] Step 3: Trigger Simulator "Exclude DRUG-A" $\rightarrow$ Verify alert appears for `C-001` but NOT `C-002`.
  - [ ] Step 4: Trigger Simulator "Delay to Dec 1" $\rightarrow$ Verify alert for `C-001` automatically closes.
  - [ ] Step 5: Cut feed $\rightarrow$ Verify Stale Rules banner appears.
  - [ ] Step 6: Hit "Reset Demo" $\rightarrow$ Verify complete state reset without restart.

---

### Phase 6: Polish, Hackathon Pitch & Submission (Hours 21 – 24)
- [ ] **6.1 UI Micro-interactions & Visual Polish**
  - [ ] Dark/Light mode toggle, smooth transitions, status badge animations.
  - [ ] Clear zero-states with helpful guidance.
- [ ] **6.2 Sponsor Track Alignment**
  - [ ] Configure autonomous sync worker to integrate with **Factory Droid SDK** or **Fetch.ai uAgents** schema.
  - [ ] Document agent trigger and execution logs in `README.md`.
- [ ] **6.3 Pitch & Demo Artifacts**
  - [ ] 2-minute clean screen recording.
  - [ ] Slide deck outline with problem data (Experian claims rejection stats) and live demo architecture.

---

## ⚡ Principles for High-Velocity Execution
1. **Zero-Configuration Storage:** Use SQLite locally so there are zero database setup or migration blockers for anyone running the project.
2. **Deterministic Rules Over Hallucinations:** All coverage decisions are calculated in pure Python logic; the LLM is restricted to document extraction and text formatting.
3. **Fail-Safe Demo:** The "Reset Demo" button guarantees that you can restart your 5-minute presentation in 1 second during live judging.
