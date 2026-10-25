# Coverage Guard 🛡️
### Multimodal AI Insurance Intelligence & Claim-Denial Prevention Platform

[![Hackathon](https://img.shields.io/badge/Hackathon-CalHacks%2013.0-FF5722?style=flat-square&logo=hackerearth)](https://calhacks.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB?style=flat-square&logo=react)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-6.4+-646CFF?style=flat-square&logo=vite)](https://vitejs.dev)
[![Gemini](https://img.shields.io/badge/Gemini-3%20Flash%20Multimodal-blue?style=flat-square&logo=google)](https://ai.google.dev/)
[![QA Tests](https://img.shields.io/badge/QA%20Tests-38%2F38%20Passed-brightgreen?style=flat-square&logo=pytest)](file:///Users/bilalhasan/clahacks-13.0/clahacks-13.0/backend/tests/qa_e2e_runner.py)
[![Pytest](https://img.shields.io/badge/Pytest-17%2F17%20Passed-brightgreen?style=flat-square&logo=pytest)](file:///Users/bilalhasan/clahacks-13.0/clahacks-13.0/backend/tests/)

---

## 📌 What It Is & Our Core Differentiator

**Coverage Guard** transforms hospital insurance administration from a reactive appeals cycle into an autonomous, proactive claims-denial prevention platform.

### The Problem:
Health insurance policies change dozens of times per week. Insurers publish circulars in scanned PDFs, photographs, or portal memos. Hospital revenue cycle teams only discover these changes months later when claims are rejected, resulting in millions of dollars in preventable denials and delayed patient treatments.

### Our Solution:
> **"An insurance company publishes a new policy in a scanned PDF, photograph, or email. CoverageGuard extracts the change with Gemini, highlights the verified evidence, simulates the impact on pending hospital claims before human approval, and automatically re-evaluates caseload risks upon activation."**

---

## 🛡️ Core Safety Principles

Throughout our architecture, we strictly adhere to:
```
┌─────────────────┐      ┌─────────────────────────┐      ┌──────────────────────┐
│  AI EXTRACTS    │ ───> │  DETERMINISTIC CODE     │ ───> │  HUMANS APPROVE      │
│  Multimodal     │      │  Pure Python Check      │      │  Reviewer preview    │
│  document parser│      │  Engine decides coverage│      │  commits to live rule│
└─────────────────┘      └─────────────────────────┘      └──────────────────────┘
```
1. **AI extracts. Code decides. Humans approve:** Gemini never makes final coverage decisions. All determinations remain 100% deterministic through our Python rules engine.
2. **Never invent codes or dates:** If a policy date or plan is ambiguous, it is marked unknown for human review.
3. **Zero unredacted PII to external models:** All clinical text passes through automated privacy redaction before model calls.
4. **Append-only audit history:** Every proposal, difference, simulation, and approval is immutably logged.

---

## 🧭 System Capabilities & Workflows

### 1. Multimodal Document Ingestion (PDF, Scanned PDF, Images, Text)
- Supports selectable-text PDFs (`pypdf`/`fitz`), scanned document rasterization, PNG, JPEG, WebP, and pasted notices.
- Dedicated modular backend: `backend/app/intelligence/` (`document_processor.py`, `evidence_validator.py`, `policy_extractor.py`, `policy_diff.py`, `impact_previewer.py`).
- Automatic file validation and 10MB size limiting.

### 2. Structured Policy Extraction & Evidence Highlighting
- Gemini multimodal extraction maps raw circulars into `ProposedPolicyChange` models.
- Interactive two-column review workspace:
  - **Left column:** Original document view with page navigation and verified evidence quotation box.
  - **Right column:** Editable fields (Insurer, Plan, Target Item, Effect, Effective Date) with policy difference comparison against existing active rules.

### 3. What-If Claim Impact Simulator
- Stateless simulation: checks pending open claims against a proposed policy before commiting any changes.
- Evaluates temporal boundaries: claims scheduled before an effective date remain **Approved**, while services scheduled after the effective date are flagged as **Potential Denial Risk**.
- Zero database side effects until explicit human approval.

### 4. Human Review & Autonomous Caseload Re-Evaluation
- Approving a proposal increments the rule version in the versioned rule store.
- Re-evaluates open claims, dynamically updates the clean claims rate, publishes circular entries, and manages alert lifecycles.
- **Idempotency protection:** Resubmitting an approved proposal returns the active rule without duplicate alerts.

### 5. Explainable Action Center & Alert Lifecycles
- For every affected claim, displays:
  - **Claim ID:** e.g. `C-001`
  - **Status:** `Potential Denial Risk`
  - **Reason:** Item excluded or restricted under approved rule
  - **Effective Date:** e.g. `1 Nov 2026`
  - **Supporting Policy:** Rule citation (e.g. `Rule R-1042 v2`)
  - **Verified Document Evidence:** Exact quotation from the insurance circular
  - **Suggested Follow-Up:** Actionable clinical/billing guidance
- **Action Queue Tasks:** Interactive checklist (`open`, `in_progress`, `completed`) tracking officer attribution and completion timestamps.
- **AI Administrative Follow-Up Draft:** One-click generation of draft communications for clinical staff with safety disclaimers (human review required, automated external dispatch restricted).
- **Automatic Alert Resolution:** When an insurer postpones or cancels a restriction, affected claims automatically return to **Approved** and alerts close cleanly.

### 6. Multimodal Clinical Intake
- Upload patient clinical notes, orders, or insurance cards (PDF or image).
- Built-in PII redaction masks SSNs, phone numbers, and email addresses.
- Strict schema validation: never fabricates medications or plans when documents lack specific clinical items.

---

## 🎬 3-Minute CalHacks Demonstration Script

We provide 3 synthetic demo documents in `backend/tests/fixtures/`:
* **Document A (`demo_document_A_new_exclusion.pdf`):** New exclusion of `DRUG-A` effective **November 1, 2026**.
* **Document B (`demo_document_B_delayed_exclusion.pdf`):** Postponement of `DRUG-A` exclusion to **December 1, 2026**.
* **Document C (`demo_document_C_prior_auth.pdf`):** Mandatory Prior Authorization for `PROC-1`.

### Step-by-Step Demo Flow:
1. **Open Dashboard:** Navigate to [http://localhost:5173](http://localhost:5173). Observe initial caseload (40 claims, 75.0% clean claims).
2. **Open Policy Intelligence:** Click **Policy Intelligence** in the left sidebar.
3. **Load Document A:** Click preset **"Document A (New Exclusion)"** or upload `demo_document_A_new_exclusion.pdf`.
   - Watch Gemini extract the exclusion for `DRUG-A` effective `2026-11-01`.
   - Inspect the highlighted verified quotation and policy difference (`Covered` $\rightarrow$ `Excluded`).
4. **Simulate What-If Impact:** Click **"Preview Claim Impact"**.
   - See instant simulation: 3 claims flagged (`C-001`, `C-005`, `C-008`).
   - Notice that claims scheduled before November 1 remain unchanged.
5. **Approve Policy:** Click **"Approve & Apply Policy"**.
   - System commits Rule R-1042 v2.
   - Clean claims rate updates; alerts appear in the Updates and Cases feeds.
6. **Inspect Explainable Action Center:** Open **Cases**, click `C-001`.
   - View the **Explainable Action Center**: Potential Denial Risk badge, quotation, action queue checklist, and draft follow-up notice.
   - Click a task to mark it `Completed`.
7. **Load Document B (The Reversal):** Return to **Policy Intelligence**, select preset **"Document B (Delayed Exclusion)"**.
   - Notice Gemini identifies `change_type: delayed` to December 1, 2026.
   - Preview impact: shows `C-001` (service date Nov 5) returning to `Covered`.
   - Click **"Approve & Apply Policy"**.
8. **Verify Alert Closure:** Open `C-001`. The case is now **Approved**, and the alert is closed automatically because the service date precedes the postponed effective date!

---

## 🔌 API Endpoints Reference

### Policy Intelligence & Proposals
- `POST /api/policies/extract`: Multimodal upload (multipart/form-data or JSON text). Extracts structured policy changes, source quotes, diffs, and validation warnings.
- `POST /api/policies/preview-impact`: Stateless What-If claim simulation against caseload.
- `GET /api/policies/proposals`: Lists all extracted policy change proposals.
- `GET /api/policies/proposals/{id}`: Returns proposal detail.
- `POST /api/policies/proposals/{id}/approve`: Commits proposal into active versioned rules, re-evaluates claims, and records audit trail.
- `POST /api/policies/proposals/{id}/reject`: Rejects proposal with reviewer notes.

### Explainable Action Center & Alerts
- `GET /api/alerts`: Lists active and historical alerts.
- `GET /api/alerts/case/{case_id}`: Returns alerts for a specific claim.
- `POST /api/alerts/{alert_id}/tasks/{task_id}`: Updates administrative checklist task status (`open`, `in_progress`, `completed`).
- `POST /api/alerts/{alert_id}/acknowledge`: Acknowledges alert with officer note.
- `POST /api/alerts/{alert_id}/draft`: Generates administrative draft follow-up notice.

### Clinical Intake & Core System
- `POST /api/intake/analyze`: Multimodal clinical document & insurance card analysis with PII redaction.
- `POST /api/cases/upload`: Creates and checks new patient case in caseload.
- `GET /api/dashboard`: Summary statistics and clean claims percentage.
- `GET /api/cases`: Paginated and filterable caseload table.
- `GET /api/cases/{case_id}`: Case detail with deterministic verdicts.
- `GET /api/updates`: Reverse-chronological policy update notifications.
- `POST /api/check/run-now`: Triggers scheduled rules check.

---

## 🚀 Setup & Execution

### Prerequisites
- Python 3.11+
- Node.js 18+
- Gemini API Key (optional for live multimodal calls; deterministic fallback included)

### Quickstart
```bash
# 1. Clone repository
git clone https://github.com/bhasan26/clahacks-13.0.git
cd clahacks-13.0

# 2. Configure environment (optional for live Gemini)
echo "GEMINI_API_KEY=your_key_here" > backend/.env

# 3. Launch application
chmod +x dev.sh
./dev.sh
```
* **Frontend Application:** [http://localhost:5173](http://localhost:5173)
* **Backend API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Verification Commands
```bash
# Run complete QA Acceptance suite (38 checks)
./backend/.venv/bin/python backend/tests/qa_e2e_runner.py

# Run unit tests (17 unit tests)
./backend/.venv/bin/pytest backend/tests/ -v

# Run Frontend TypeScript validation and build
npm --prefix frontend run build
```

---

## 👥 Contributors

Built for **CalHacks 13.0** (UC Berkeley).
* **Bilal Hasan** ([@bhasan26](https://github.com/bhasan26))
* **H. Lagunes** ([@hlagunes01](https://github.com/hlagunes01))
