# CoverageGuard 🛡️
### Autonomous Health Insurance Coverage Sentinel & Denial Prevention Platform

[![Hackathon](https://img.shields.io/badge/Hackathon-CalHacks%2013.0-FF5722?style=flat-square&logo=hackerearth)](https://calhacks.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB?style=flat-square&logo=react)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square&logo=pydantic)](https://docs.pydantic.dev)
[![Tests](https://img.shields.io/badge/Tests-7%20Passed%20(100%25)-brightgreen?style=flat-square&logo=pytest)](file:///Users/bilalhasan/clahacks-13.0/clahacks-13.0/backend/tests)
[![Zero Hallucination](https://img.shields.io/badge/Engine-Zero--Hallucination%20Deterministic-blueviolet?style=flat-square)]()
[![Design](https://img.shields.io/badge/Design-Shakuro%20ACRU%20Bento-lime?style=flat-square)]()

---

## 📌 Executive Summary

Health insurance companies update clinical coverage policies, exclusions, prior-authorization mandates, and required documentation an average of **40 times per week**. Hospitals typically learn about these changes post-facto through fragmented PDF circulars, portal updates, or claims rejection notices. 

When a claim is prepared on yesterday's guidelines and filed after a policy revision, the claim is rejected. This triggers administrative rework, delays patient care, and results in millions of dollars in avoidable revenue-cycle losses.

**CoverageGuard** bridges this gap by acting as an autonomous sentinel between commercial health insurers and hospital billing departments. It continuously ingests versioned payer policy feeds, monitors the hospital's open claims caseload, and proactively warns billing officers **before** claims are submitted.

> ### 🏛️ Core Architectural Principle
> **"Code decides coverage; the AI model only extracts clinical notes and drafts wording."**  
> Every coverage verdict, temporal boundary check, and denial alert is calculated by a **100% deterministic Python rule engine**. LLMs are strictly isolated to document parsing and PII redaction to prevent clinical hallucinations.

---

## ✨ Key Features & Capabilities

* **Deterministic Coverage Verification:**  
  Pure function rule evaluation resolving policy scope (`plan_id` vs wildcard `*`), item categories (drugs, procedures, consultation services), and temporal validity intervals (`effective_from <= date < effective_to`).
* **Caseload Impact Rollup Alerting:**  
  When an insurer amends or excludes a code, the platform instantly re-evaluates all open claims and produces executive rollup notifications:
  > *"Insurer A no longer covers DRUG-A effective Nov 1, 2026. Of the 30 open claims, these 3 are affected: Case C-001, Case C-005, Case C-008."*
* **Physician Formulary Intervention:**  
  Differentiates between clean, ready-to-file claims and rejection risks:
  * **Sample 1 (Verified Clean):** Confirms all codes are covered and all prior authorizations are valid $\rightarrow$ *"File is Complete & Ready to Submit"*.
  * **Sample 2 (Rejection Risk Detected):** Flags gaps and directs staff $\rightarrow$ *"Take file to treating physician before submission to choose a covered alternative drug"*.
* **Dynamic Lifecycle & Auto-Closing Alerts:**  
  Tracks the full policy lifecycle (`announced`, `effective`, `delayed`, `cancelled`, `superseded`). If an insurer delays or cancels an announced exclusion, the alert is automatically closed with an audit reason, preventing alert fatigue.
* **Shakuro "ACRU" Bento Grid UI:**  
  Clean light design system (`#F4F5F7` canvas, `#FFFFFF` cards, `#84CC16` lime accents) featuring:
  * Stacked weekly caseload activity bar chart with peak tooltip.
  * Insurer Direct Feed telemetry card and 1-click sync.
  * Semi-circle radial compliance gauge (90% clean claims rate).
  * Caseload distribution by medical specialty.
* **Append-Only Regulatory Audit Log:**  
  Every check execution, policy sync, and officer acknowledgment is recorded immutably with timestamp, actor, and cited rule versions.
* **AI Clinical File Intake with PII Redaction:**  
  Powered by Google Gemini (`gemini-flash-lite-latest`) with a deterministic regex fallback. Extracts clinical codes while redacting patient names and identifiers.
* **Interactive 1-Click Simulator Dock:**  
  Allows judges and operators to simulate real-world payer actions (exclude drug, delay effective date, cancel exclusion, simulate feed outage, or reset demo state) with live UI feedback.

---

## 🏛️ System Architecture

```
 HOSPITAL WORKFLOW               COVERAGEGUARD PLATFORM                  PAYER ECOSYSTEM
 ┌─────────────────┐             ┌────────────────────────────────┐
 │ Claims Officer  │◄──(HTTPS)──►│ React + TypeScript SPA         │
 │ (Dr. Bilal)     │             │ ├ Bento Grid Dashboard         │
 └─────────────────┘             │ ├ Alerts Inbox & Caseload View │
                                 │ ├ Payer Rules Explorer         │
 ┌─────────────────┐             │ └ 1-Click Simulator Bar        │
 │ Clinical Notes  │             └───────────────┬────────────────┘
 │ & EHR Records   │                             │
 └────────┬────────┘                             │ REST API
          │                                      ▼
          │ Intake Form          ┌────────────────────────────────┐
          └─────────────────────►│ FastAPI Sentinel Backend       │
                                 │ ├ Pure Deterministic Engine    │
                                 │ │  (effective_from <= date)    │
                                 │ ├ Sentinel Impact Analyzer     │
                                 │ ├ Gemini AI Clinical Parser    │
                                 │ ├ In-Memory / SQLite Store     │
                                 │ └ Append-Only Audit Logger     │
                                 └───────────────┬────────────────┘
                                                 │
                                                 │ Payer Feed Protocol (v2)
                                                 ▼
                                 ┌────────────────────────────────┐
                                 │ Commercial Insurer Feed        │
                                 │ (Real-time Rulebooks & Delays) │
                                 └────────────────────────────────┘
```

---

## 📂 Project Structure

```bash
clahacks-13.0/
├── dev.sh                     # Unified startup script (Backend + Frontend)
├── project.md                 # Detailed problem specification & requirements
├── PROGRESS.md                # Engineering audit and development log
├── backend/
│   ├── app/
│   │   ├── domain/
│   │   │   └── models.py      # Pydantic v2 schemas (Rule, Case, Alert, Audit)
│   │   ├── engine/
│   │   │   └── checker.py     # Pure deterministic rule evaluation engine
│   │   ├── impact/
│   │   │   └── analyzer.py    # Caseload re-evaluation & auto-closing alert manager
│   │   ├── db/
│   │   │   └── store.py       # Data repository & 30 canonical hospital claims
│   │   └── main.py            # FastAPI endpoints, simulator, & Gemini AI intake
│   ├── tests/
│   │   ├── conftest.py        # Pytest configuration & path resolution
│   │   ├── test_engine.py     # Golden test suite for deterministic rules
│   │   └── test_api.py        # End-to-end API integration tests
│   └── requirements.txt       # Python dependencies
└── frontend/
    ├── src/
    │   ├── api.ts             # Typed REST API client
    │   ├── types.ts           # Frontend TypeScript contract interfaces
    │   ├── App.tsx            # Application entry & view router
    │   ├── components/
    │   │   ├── Sidebar.tsx           # Vertical navigation & live feed health
    │   │   ├── TopBar.tsx            # Header search, profile & intake trigger
    │   │   ├── DashboardOverview.tsx # Shakuro ACRU Bento Grid dashboard
    │   │   ├── AlertsInbox.tsx       # Rollup banner & alert diff views
    │   │   ├── CasesExplorer.tsx     # 30-case claims table & status chips
    │   │   ├── CaseDetailModal.tsx   # Verified clean vs rejection risk modals
    │   │   ├── ClinicalIntakeModal.tsx # Gemini AI file extractor (Sample 1 & 2)
    │   │   ├── RulesLibrary.tsx      # Versioned payer rulebook explorer
    │   │   ├── AuditLogView.tsx      # Immutable regulatory audit trail
    │   │   ├── SimulatorBar.tsx      # 1-Click floating dock controls
    │   │   └── StaleBanner.tsx       # Feed disconnection warning banner
    └── package.json           # Frontend dependencies & Vite configuration
```

---

## 🚀 Quickstart Guide

### Prerequisites
* **Python 3.11+** (Python 3.12 recommended)
* **Node.js 18+** & **npm**

### Option A: 1-Click Automated Startup (Recommended)

Run the root development script:
```bash
chmod +x dev.sh
./dev.sh
```
This automatically boots:
* **FastAPI Backend:** [http://127.0.0.1:8000](http://127.0.0.1:8000) (Swagger docs: [`/docs`](http://127.0.0.1:8000/docs))
* **Vite React UI:** [http://localhost:5173](http://localhost:5173)

---

### Option B: Manual Setup

#### 1. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the API server with auto-reload
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
cd frontend
npm install

# Start the Vite development server
npm run dev
```

---

## 🧪 Automated Testing

The deterministic check engine and API endpoints are validated by automated golden test suites:

```bash
# Run pytest from project root
backend/.venv/bin/pytest backend/tests -v
```

### Test Coverage Highlights:
* `test_baseline_verdicts`: Verifies that `DRUG-A` on `PLAN-GOLD` evaluates as **Covered** prior to policy cutoff dates.
* `test_rule_change_and_alerts`: Validates that amending `R-101` to `EXCLUDED` immediately triggers high-priority alerts with itemized citations.
* `test_temporal_boundary`: Asserts that claims scheduled prior to the exclusion date remain untouched and clean.
* `test_delay_closes_alert`: Confirms that delaying an exclusion automatically transitions open alerts to `closed` with audit reason.
* `test_api_health_and_cases`: Tests REST health telemetry and caseload retrieval across all 30 claims.
* `test_simulator_workflow`: Validates 1-click simulator state changes and rulebook updates.
* `test_stale_feed_detection`: Ensures outage simulation triggers the stale feed warning banner.

---

## 🎬 3-Minute Live Judging Click Script

Follow this script to demonstrate the platform to judges, clinicians, or revenue cycle directors:

| Step | Action in UI | Expected System Behavior | What to Tell the Judges |
| :--- | :--- | :--- | :--- |
| **1. Baseline State** | Open [http://localhost:5173](http://localhost:5173). Notice the Bento Grid Overview. | Shows **30 Active Claims**, **90% Compliant**, 0 open alerts, green **Insurer Direct Feed** card. | *"We are monitoring 30 active hospital claims against current payer contracts. Everything is clean and synchronized."* |
| **2. AI Clinical Intake (Sample 1)** | Click **`+ Intake File`** in the top bar. Click **`✓ Sample 1 (Complete)`**, then **`Confirm Fields & Run Coverage Check`**. | Case details modal opens showing the green banner: **Verified Clean — File is Complete & Ready to Submit**. | *"The AI extracts clinical codes and redacts PII, but deterministic Python code evaluates coverage. Sample 1 satisfies all criteria and is cleared for filing."* |
| **3. AI Clinical Intake (Sample 2)** | Click **`+ Intake File`**, click **`⚠ Sample 2 (Gaps)`**, then **`Confirm Fields & Run Coverage Check`**. | Case modal opens with high-contrast red banner: **Rejection Risk Detected — Take file to treating physician before submission**. | *"Sample 2 identifies that the prescribed drug is excluded under upcoming rules and prior authorization is missing. Staff are instructed to have the physician choose a covered alternative before submission."* |
| **4. Payer Policy Change** | In the bottom floating simulator dock, click **`Exclude Drug A (Nov 1)`**. | Toast confirms policy published. The **Policy Alerts** tab highlights with a red counter badge (`3`). | *"Insurer A just announced that DRUG-A is excluded starting Nov 1. The sentinel automatically re-evaluated all 30 open claims."* |
| **5. Executive Rollup Banner** | Click the **Policy Alerts** tab in the sidebar. | Top banner displays: *"Insurer A no longer covers DRUG-A effective Nov 1, 2026. Of the 30 open claims, these 3 claims are affected: Case C-001, Case C-005, Case C-008."* | *"The officer doesn't need to manually cross-reference 30 claims. The system identifies the exact cases affected and explains the financial risk."* |
| **6. Payer Delays Change** | Click **`Delay to Dec 1`** in the floating simulator bar. | The alerts are automatically updated to **Closed** with reason *"change delayed or cancelled by insurer"*. | *"Insurers often delay rule changes. CoverageGuard auto-closes the alert so billing staff aren't acting on outdated warnings."* |
| **7. Feed Outage Warning** | Click **`Simulate Outage`** in the dock. | A warning banner appears across the top: *"Payer Rules Feed Disconnected — Rules may be out of date"*. | *"If the payer feed goes down, staff are alerted that checks may be using stale rules."* |
| **8. Instant Reset** | Click **`Reset Demo`** in the bottom dock. | Caseload and rules are instantly restored to the clean baseline. | *"One click resets the entire platform for the next test."* |

---

## 📡 API Reference Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Payer feed freshness, active rule counts, and outage flags. |
| `GET` | `/api/cases` | Summaries and statuses of all 30 hospital claims. |
| `GET` | `/api/cases/{case_id}` | Detailed claim view, itemized verdicts, and cited rule versions. |
| `POST` | `/api/cases/extract` | Gemini AI clinical note entity extraction and PII redaction. |
| `POST` | `/api/cases` | Create and store a new clinical case. |
| `GET` | `/api/rules` | Complete versioned rulebook across all payers and plans. |
| `GET` | `/api/alerts` | Active and historical caseload impact alerts. |
| `POST` | `/api/alerts/{alert_id}/acknowledge` | Record claims officer review and audit notes. |
| `POST` | `/api/sync` | Manually trigger payer feed synchronization and caseload impact analysis. |
| `GET` | `/api/audit` | Append-only regulatory audit trail. |
| `POST` | `/api/simulator/exclude-drug-a` | Publish rule `R-101 v2` excluding `DRUG-A` on 2026-11-01. |
| `POST` | `/api/simulator/delay-drug-a` | Delay rule `R-101` to 2026-12-01 (auto-closes affected alerts). |
| `POST` | `/api/simulator/cancel-drug-a` | Cancel exclusion rule (reverts coverage to baseline). |
| `POST` | `/api/simulator/toggle-outage` | Toggle simulated payer feed downtime. |
| `POST` | `/api/simulator/reset` | Restore baseline seed data and reset all alerts. |

---

## 🔒 Security & Compliance Principles

1. **HIPAA & PII Isolation:**  
   Direct patient names and identifiers are scrubbed and replaced with synthetic member tokens (`M-XXXX`) prior to extraction.
2. **Zero Clinical Hallucination:**  
   Verdicts are strictly computed via Boolean logic over database records; the LLM never generates or modifies coverage rules.
3. **Read-Only Insurer Scoping:**  
   The platform consumes payer policy and formulary catalogs; no sensitive hospital pricing or claims transmission data is sent back to the insurer feed.
4. **Immutable Audit Trail:**  
   Every state modification is appended to an immutable audit record containing actor ID, UTC timestamp, and payload diffs for complete regulatory defensibility.

---

## 👥 Contributors & Team

Proudly built for **CalHacks 13.0** (UC Berkeley).

| Contributor | GitHub Profile | Role |
| :--- | :--- | :--- |
| **Bilal Hasan** | [@bhasan26](https://github.com/bhasan26) | Lead AI Engineer & Full-Stack Architect |
| **H. Lagunes** | [@hlagunes01](https://github.com/hlagunes01) / [@hlagunes01-bot](https://github.com/hlagunes01-bot) | Product Strategy & Domain Specifications |

### Special Acknowledgments
* **Design Inspiration:** Shakuro "ACRU" Web Dashboard UI/UX Design System.
* **Clinical Data Resources:** MTSamples & Synthetic Payer Formulary Specifications.

---
*CoverageGuard — Protecting Healthcare Providers from Avoidable Claims Denials.*
