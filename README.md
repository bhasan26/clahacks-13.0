# Coverage Guard 🛡️
### AI Agent for Hospital Insurance-Claims Officers

[![Hackathon](https://img.shields.io/badge/Hackathon-CalHacks%2013.0-FF5722?style=flat-square&logo=hackerearth)](https://calhacks.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB?style=flat-square&logo=react)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-6.4+-646CFF?style=flat-square&logo=vite)](https://vitejs.dev)
[![Tests](https://img.shields.io/badge/QA%20Tests-38%2F38%20Passed-brightgreen?style=flat-square&logo=pytest)](file:///Users/bilalhasan/clahacks-13.0/clahacks-13.0/backend/tests/qa_e2e_runner.py)

---

## 📌 What It Is

**Coverage Guard** is an AI agent for a hospital insurance-claims officer, with a simple, calm web interface on top.

The officer uploads a patient file and prescription. The agent checks every item (drug, procedure, service) against the insurer’s current rules and reports whether the case is:
* **Approved** (Green `#2A835F`)
* **Needs attention** (Amber `#D97706`)
* **Missing or wrong info** (Red `#DC2626`)

The agent is connected to the insurer’s system, checks it every day for updates, and re-checks all open cases after each check.

---

## 📏 Rules for the Whole Interface

1. **Clear, simple, uncluttered:** One purpose per page, no more than 6 elements above the fold.
2. **Numbers only:** No days, durations, turnaround times, or aging.
3. **No money metrics:** No total monitored value, no “denials prevented”.
4. **Plain wording:**
   * `“Approved”`
   * `“Needs attention”`
   * `“Missing or wrong info”`
5. **Calm, professional look:**
   * Pure white background (`#FFFFFF`), dark green text (`#092328`), brand accents: `#12544F`, `#2A835F`, `#8BBB92`.
   * Standard status conventions:
     * **Green (`#2A835F`)** for Approved
     * **Amber/Yellow (`#D97706`)** for Needs attention
     * **Red (`#DC2626`)** for Missing or wrong info
   * The **same three colors are used everywhere** a status appears: dashboard cards, specialty bars, case list badges, item results, and update status.

---

## 🧭 Site Structure & Pages

### Sidebar (Left Navigation on Every Page)
* **Top:** `“Coverage Guard”` brand mark and `“Claims Sentinel”` identifier.
* **Vertical Navigation:** Clean, calm vertical menu items:
  * `Dashboard`
  * `Cases`
  * `Updates`
* **Bottom:** Connection chip with the insurer’s name, a green dot, and `“Access active”`:
  $$\text{● Demo Insurance Co. · Access active}$$
* **Clicking the chip opens a small popover:**
  * Insurer name (`Demo Insurance Co.`)
  * `“Connected”`
  * `“Access active”`
  * `“Read-only”` (*“Read-only” appears only here. Nothing else on the site talks about limitations.*)
  * Last check time (`06:00 today`)
  * Quick demo triggers: `[ Run check now ]`, `[ Simulate check failure ]`
* **Outage / Check Failure Alert:** If the check failed, the chip turns amber (`“Check pending”`) with a one-line banner at the top of the content area:  
  *“Rules may be out of date. Re-check in progress.”*

---

### Page 1: Dashboard

```
┌────────────────────────────────────────────────────────────────────────┐
│ ROW 1: THREE NUMBER CARDS                                             │
│ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────┐ │
│ │ Approved          30 │ │ Needs attention    5 │ │ Missing/wrong  5 │ │
│ │ Complete & covered   │ │ Update/rule affects  │ │ Field/value err  │ │
│ └──────────────────────┘ └──────────────────────┘ └──────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ ROW 2: CLEAN CLAIMS (LEFT)             │ CASES BY SPECIALTY (RIGHT)    │
│ Clean claims submission                │ Cases by specialty            │
│ 75.0% (30 of 40 cases clean)           │ Cardiology     10 [====|==|==]│
│ [====================|               ] │ Oncology        9 [====|==|==]│
│                     Target 85%         │ Orthopedics     8 [====|==|==]│
│ (Target marker is editable by admin)   │ Neurology       7 [====|==|==]│
│                                        │ Gastroenterol.  6 [====|==|==]│
├────────────────────────────────────────────────────────────────────────┤
│ ROW 3: LATEST UPDATES (THE 3 MOST RECENT)                              │
│ • Formulary revision: Drug A excluded · Effective 1 Nov 2026 · Affects 3 │
│ • Prior authorization mandate for PROC-1 · Effective 15 Oct · Affects 2│
│ • Genetics panel report required · Effective 15 Nov 2026 · Affects 1   │
│                                                [ View all updates → ] │
└────────────────────────────────────────────────────────────────────────┘
```

* **Row 1:** Three number cards, nothing else in the row:
  * **Approved:** cases that are complete and covered.
  * **Needs attention:** an update or rule affects the case.
  * **Missing or wrong info:** a required document, number or field is missing, or a value is wrong.
* **Row 2, Left:** Clean claims submission.
  * Big percentage: cases that passed the check with no issues $\div$ all checked cases ($30 / 40 = 75.0\%$).
  * Horizontal bar with a marker for the target, labelled `“Target 85%”`. The target is editable by the admin.
* **Row 2, Right:** Cases by specialty.
  * Horizontal bars, one per specialty (Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology), sorted descending by count.
  * Count at the end of each bar.
  * Each bar split by the three statuses, using the same three colors (green, amber, red).
* **Row 3:** Latest updates (the 3 most recent).
  * One line each: what changed, effective date, number of open cases affected.
  * A `“View all updates”` link goes to the Updates page.
* **No other widgets.**

---

### Page 2: Cases

* `“Upload patient file”` button (patient file + prescription).
* **Table:**
  * Columns: `Case ID`, `Specialty`, `Status`, `Items (count)`.
  * Filters: `Status` (All, Approved, Needs attention, Missing or wrong info) and `Specialty` (All, Cardiology, Oncology, Orthopedics, Neurology, Gastroenterology).
* Clicking a row opens the case detail view.

---

### Page 3: Case Detail

* **Header:** Case ID, specialty, status badge.
* **Item List:** Each item shows one result:
  * `Covered`
  * `Not covered`
  * `Prior approval needed`
  * `Document missing`
  * `Value wrong`
* **Single Plain Sentence Format:** Each issue gets:
  1. One plain sentence.
  2. The rule reference.
  3. What to do.
  > *Example:* **“Drug X is not covered from 1 Nov 2026. Rule R-1042. Review with the physician before submitting.”**
* **Strict Principle:** The agent only notifies. It **never edits, rejects or submits, and never suggests a medical alternative.**

---

### Page 4: Updates

* Reverse-chronological list of recent updates from the insurer (6 entries).
* Each entry:
  * What changed (headline)
  * Item type badge (`Drug` / `Procedure` / `Document` / `Approval`)
  * Effective date (e.g., `1 Nov 2026`)
  * Status (`Announced` / `Effective` / `Delayed` / `Cancelled`)
  * `“Affects N open cases”` (linking/filtering to those cases).
* Filter by type (`All`, `Drug`, `Procedure`, `Document`, `Approval`).
* Employees see updates and their effect on their own cases. They cannot browse or search raw insurer rules.

---

## ⚙️ How the Agent Works (Backend)

* **Stack:** FastAPI, PostgreSQL / In-Memory Store, React + TypeScript, Vite.
* **Insurer Connection:** A mock insurer service exposes:
  * `GET /v1/rules/snapshot`
  * `GET /v1/rule-changes?since=`
  * With an API key scoped to `rules:read`. The key stays strictly on the server.
* **Daily Check Scheduled Job:** Pulls the insurer’s rules, stores each version, and records changes.
* **“Run check now” Button:** Admin demo trigger:
  * Applies an announced rule change (Drug A excluded from 1 Nov 2026 under Rule R-1042).
  * Automatically re-checks all 40 open cases.
  * Moves 3 open cases (`C-001`, `C-005`, `C-008`) from **Approved** $\rightarrow$ **Needs attention**.
  * Updates counts, updates the clean claims percentage, and prepends an entry on the Updates page.
* **Deterministic Code:** Coverage decisions come from pure deterministic Python logic over versioned rules. The LLM only extracts fields from uploaded files. It never decides coverage.
* **No Matching Rule:** Returns `“No rule found, verify with the insurer”`.
* **Audit Log:** Append-only; stores case, rule ID, rule version, and time.

---

## 📊 Seed Data for the Demo

1. **40 Cases across 5 Specialties:**
   * **Cardiology (10 cases):** `C-001`, `C-002`, `C-005`, `C-008`, `C-011`, `C-012`, `C-013`, `C-014`, `C-015`, `C-016`
   * **Oncology (9 cases):** `C-017`, `C-018`, `C-019`, `C-020`, `C-021`, `C-022`, `C-023`, `C-024`, `C-025`
   * **Orthopedics (8 cases):** `C-003`, `C-026`, `C-027`, `C-028`, `C-029`, `C-030`, `C-031`, `C-032`
   * **Neurology (7 cases):** `C-033`, `C-034`, `C-035`, `C-036`, `C-037`, `C-038`, `C-039`
   * **Gastroenterology (6 cases):** `C-004`, `C-040`, `C-006`, `C-007`, `C-009`, `C-010`
2. **Initial Status Mix:**
   * **Approved:** 30 cases
   * **Needs attention:** 5 cases
   * **Missing or wrong info:** 5 cases
   * Clean claims = $30 / 40 = 75.0\%$ (below the $85.0\%$ target marker, making it visually meaningful).
3. **6 Updates:**
   * `UPD-106`: Drug A excluded from commercial formulary (drug, 1 Nov 2026, Announced, affects 3 cases: C-001, C-005, C-008)
   * `UPD-105`: Prior authorization required for Joint Procedure PROC-1 (procedure, 15 Oct 2026, Effective, affects 2 cases: C-003, C-014)
   * `UPD-104`: Genetics panel report required for Targeted Biotherapy (document, 15 Nov 2026, Announced, affects 1 case: C-019)
   * `UPD-103`: Neurology nerve conduction test authorization window expanded (approval, 1 Oct 2026, Effective, affects 0 cases)
   * `UPD-102`: Cardiology pacemaker lead revision criteria delayed to 1 Dec (procedure, 1 Dec 2026, Delayed, affects 0 cases)
   * `UPD-101`: Gastroenterology endoscopy pre-cert mandate cancelled (approval, 15 Sep 2026, Cancelled, affects 0 cases)

---

## 🎬 Acceptance Criteria Verification

| Acceptance Criterion | Implementation & Verification | Status |
| :--- | :--- | :---: |
| **1. Uncluttered Dashboard** | Shows exactly 3 cards in Row 1, clean claims against target (Row 2L), specialty bars (Row 2R), and latest 3 updates (Row 3). No other widgets. | **PASS** |
| **2. Zero Durations / Money** | No page shows days, durations, turnaround times, aging, money, or “denials prevented”. Numbers only. | **PASS** |
| **3. Header Chip & Popover** | Chip shows `● Demo Insurance Co. · Access active`. Clicking chip reveals popover with `Read-only` (*only* appears here!). | **PASS** |
| **4. Run Check Now Dynamics** | Triggers check with new rule change, updates counts ($30 \rightarrow 27$ Approved, $5 \rightarrow 8$ Needs attention), flags C-001, C-005, C-008. | **PASS** |
| **5. Restricted Employee View** | Employees navigate Dashboard, Cases, Updates. No page or API route allows listing or searching raw insurer rules. | **PASS** |
| **6. Issue Naming** | Every issue names its Rule ID (e.g., `Rule R-1042.`), effective date (e.g., `1 Nov 2026`), and plain action. | **PASS** |

---

## 🚀 Quickstart Guide

### 1-Click Startup
Run the root startup script:
```bash
chmod +x dev.sh
./dev.sh
```
* **Frontend:** [http://localhost:5173](http://localhost:5173)
* **Backend:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Run Tests
```bash
# 1. Run full 38-check E2E QA Acceptance suite
python3 backend/tests/qa_e2e_runner.py

# 2. Run Pytest unit suite
backend/.venv/bin/pytest backend/tests/test_engine.py backend/tests/test_api.py -v

# 3. Verify Frontend build
cd frontend && npm run build
```

---

## 👥 Contributors

Built for **CalHacks 13.0** (UC Berkeley).
* **Bilal Hasan** ([@bhasan26](https://github.com/bhasan26))
* **H. Lagunes** ([@hlagunes01](https://github.com/hlagunes01))
