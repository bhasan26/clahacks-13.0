 على الوثيقة الجزئية، فتجاهلها أو احذفها.

---

# Coverage Check Agent: Hackathon Build Draft

## 1. Executive summary

We build one web platform for a hospital's insurance-claims officer. The officer creates a patient case or uploads a patient file. The agent checks every item in it (drug, procedure, service) against the insurer's current coverage rules. Every day the platform pulls rule changes from the insurer, finds the open cases each change affects, and tells the officer what changed, since when, and from which source.

**The demo must prove three things:**
1. A case that was clear yesterday is flagged today because the insurer changed a rule, and the alert names the affected items.
2. When the insurer later delays or cancels that change, the alert updates, so the officer is never left with stale advice.
3. Every statement the agent makes traces to a rule ID, a rule version and a source in an audit log.

**Design principles:**
- **Notify only.** The agent never rejects, edits, submits, or suggests medical alternatives.
- **Code decides; the LLM reads and words.** Coverage results come from deterministic code over versioned rules. The LLM extracts fields from uploaded files, parses circulars into proposed rules, and optionally polishes alert wording. It never decides coverage.
- **Read-only, scoped insurer access.** The insurer shares coverage rules only: no patient data, prices or claims.
- **Unknown is not covered.** No matching rule means "No rule found, verify with the insurer".
- **Stale rules are visible.** If the daily sync fails, a banner says the rules may be out of date.

## 2. Problem and premise

Insurers change coverage rules (drug lists, excluded procedures, prior-approval requirements, required documents) on their own schedule. Hospitals learn of the changes through circulars, emails, portals and policy pages. A file prepared on yesterday's rule can be rejected today, which costs rework, delays the patient and strains the insurer relationship.

Industry sources point the same way:
- Experian's 2024 State of Claims survey (210 healthcare staff): 77% said payer policy changes happen more often than before, up from 67% in 2022 ([Becker's](https://www.beckersasc.com/asc-coding-billing-and-collections/claims-denials-surge-5-things-to-know/)).
- A Vermont hospital network told legislators that payer notices come as newsletters, paper notices and policy pages, often without standard fields such as the effective date ([testimony, Jan 2024](https://legislature.vermont.gov/Documents/2024/WorkGroups/House%20Health%20Care/Insurance%20Claims%20Processing/W~Kelly%20Lange~UVM%20Health%20Network%20Testimony%20-%20Claims%20Edits%20and%20Payer%20Administrative%20Burden~1-10-2024.pdf)).
- Changes also move after announcement. Cigna delayed a modifier 25 documentation policy days before go-live via a banner on the policy page ([AAFP](https://aafp.org/pubs/fpm/blogs/gettingpaid/entry/cigna-modifier25-delay.html)). Anthem reversed an anesthesia time-limit policy it had announced to providers ([MPR/NPR](https://www.mprnews.org/story/2024/12/05/npr-blue-cross-blue-shield-anesthesia-anthem)).

**Consequences for the design:** a rule change has a lifecycle (announced, effective, delayed, cancelled, superseded); the platform must show when its rules may be stale; effectiveness must be measured on the hospital's own data.

**Positioning.** Existing tools monitor payer policy pages and send digests (Experian Payer Alerts, Avia Policy Reporter) or automate US prior-authorization workflows (Optum, Innovaccer). Our differentiators: a direct read-only insurer feed instead of page monitoring, alerts matched to each open case, and one platform for check plus alerts.

## 3. Product scope

| Priority | Capability |
| --- | --- |
| Must | Rules store with versions, statuses, effective dates |
| Must | Daily sync from the insurer feed, plus a "Run sync now" button |
| Must | Case intake: structured form, with file upload to pre-fill it |
| Must | Check engine: covered, excluded, prior approval needed, documents missing, no rule found |
| Must | Impact analysis and alerts when a change touches an open case |
| Must | Append-only audit log |
| Must | Stale-rules banner |
| Should | Circular ingestion (Plan B): upload an insurer circular, get proposed rule changes, a reviewer approves |
| Should | LLM extraction of case fields from an uploaded PDF |
| Could | Limit and frequency checks, email notification, Arabic UI, a second insurer |

**Non-goals:** submitting anything to the insurer; blocking or editing a file; changing codes or diagnoses; clinical alternatives; pricing or payment; real-time patient eligibility; fraud detection; replacing the hospital information system (HIS).

**Hospital-side link in the hackathon:** cases arrive by form, file upload or a JSON import endpoint that stands in for the HIS. **Insurer-side link:** a mock insurer service exposes the read-only API defined in Section 6, so a real insurer can replace it without platform changes.

## 4. Users and workflow

| Role | Does | Gets alerts |
| --- | --- | --- |
| Claims officer (primary) | Creates cases, runs checks, reads and acknowledges alerts | Yes |
| Rules reviewer | Approves rules proposed from circulars; watches sync health | No |
| Auditor (read-only) | Reads and exports the audit log | No |

**A day in the platform:**
1. **Morning sync.** The scheduled job pulls changes and stores them as new rule versions. On failure, the stale banner shows.
2. **Impact analysis.** After each sync, all open cases are re-checked; an alert is created only where the result changed.
3. **Inbox.** The officer sees alerts: what changed, since when, source, affected cases.
4. **New case.** The officer fills the form or uploads a PDF. The agent pre-fills fields and shows the source text for each; the officer confirms every field.
5. **Check.** Each item gets a verdict with rule ID, version, effective date and source.
6. **Action outside the platform.** Obtain a document, request prior approval, ask the physician, inform the patient.
7. **Acknowledge.** The officer marks the result reviewed, with an optional note.
8. **Re-check on change.** A later change to the same case re-raises the alert and marks the old one superseded.

**Screens:** Inbox, Case list, Case detail, Rules browser (read-only, with version history), Sync status, Audit log, Insurer console (demo only: publish, delay, cancel a change), Review queue (should-have).

**Case status:** *Clear* (every item has a matching current rule with no conflict), *Needs attention* (a conflict or a missing document), *Cannot assess* (a required field is missing or an item has no rule).

## 5. Architecture

```
 HOSPITAL SIDE                 PLATFORM                                   INSURER SIDE
 ┌───────────────┐   UI    ┌────────────────────────────────────┐
 │ Claims officer│───────▶ │ Web app (React + TypeScript)       │
 └───────────────┘         └──────────────┬─────────────────────┘
 ┌───────────────┐  JSON   ┌──────────────▼─────────────────────┐   read-only    ┌──────────────────┐
 │ HIS (stub)    │───────▶ │ API (FastAPI)                      │◀───────────────│ Insurer rules API│
 └───────────────┘         │  ├ Case service                    │  daily / manual│ (mock in demo)   │
                           │  ├ Check engine (deterministic)    │                └──────────────────┘
                           │  ├ Rules store + change detector   │
                           │  ├ Impact analyser + alert service │
                           │  ├ Audit log (append-only)         │
                           │  └ LLM gateway (extract / parse)   │
                           │ Scheduler ─▶ Sync worker           │
                           │ PostgreSQL                         │
                           └────────────────────────────────────┘
```

| Component | Responsibility |
| --- | --- |
| Web app | All screens in Section 4 |
| Case service | Create, update, import cases; track status |
| Sync worker | Pull events from the insurer, validate, store, trigger impact analysis |
| Rules store | Versioned rules; never overwritten, only superseded |
| Change detector | Turns incoming events into stored change records |
| Check engine | Pure function: (case, rules, governing date) returns verdicts |
| Impact analyser | Re-runs checks after sync, diffs against previous results, creates alerts |
| Alert service | Alert lifecycle and dedupe |
| LLM gateway | The only module that calls an LLM; enforces schemas and redaction |
| Audit log | Append-only record of every sync, check, alert and acknowledgement |

**The key boundary:** the LLM gateway is called from case extraction and circular parsing only. The check engine, impact analyser and alert service have no LLM dependency, so they are testable and reproducible.

## 6. Insurer feed and data contracts

**Endpoints (read-only, rules only; no patient or claims endpoints exist):**
- `GET /v1/rules/snapshot?plan_id=…`: current rules; used for first load and weekly reconciliation.
- `GET /v1/rule-changes?since={cursor}&plan_id=…`: events since the cursor; returns `{events, next_cursor}`.

**Auth:** API key or OAuth2 client-credentials with a single scope, `rules:read`.

**Change status lifecycle:**
`announced` → `effective` · `announced` → `delayed` (new `effective_from`) · `announced` → `cancelled` · `effective` → `superseded`

**Sync behaviour:** idempotent (events carry unique IDs; a replayed event changes nothing); the cursor advances only after the batch is stored; any failure keeps the old cursor and records a failed sync; a weekly snapshot comparison catches missed events.

**Plan B for insurers without an API:** the officer or reviewer uploads a circular (PDF or email). The LLM proposes structured rule changes with the source text for each. A reviewer approves, edits or rejects. Only approved changes enter the rules store, marked `source: circular`.

## 7. Rules store, change detection, effective dates

**Rule fields:** `rule_id`, `version`, `insurer_id`, `plan_ids` (list or `*`), `category` (`drug` | `procedure` | `service` | `required_document` | `prior_approval`), `target` (`type`, `code`, `name`), `effect` (`covered` | `excluded` | `requires_prior_approval` | `requires_documents`), `conditions` (optional, structured), `status`, `effective_from`, `effective_to`, `source_ref`, `received_at`.

**Change detection:** each event is compared with the latest stored version of that `rule_id`. Outcomes: `added`, `modified` (a field differs), `removed`, `status_changed`. Each outcome writes a change record with `before`, `after` and `detected_at`.

**Applicability of a rule version to a case item:**
1. Same insurer; `plan_ids` contains the case plan or `*`; `target.type` and `target.code` equal the item's.
2. The governing date lies within `[effective_from, effective_to)`.
3. Status is `announced` or `effective`. `cancelled` and `superseded` are ignored. `delayed` uses its new `effective_from`.

**Governing date** is configurable per insurer: `service_date` (default), `submission_date`, `approval_date`. The correct value must be confirmed with the insurer's claims team.

**Precedence when several rules match:** plan-specific over wildcard; then latest `effective_from`; then highest `version`. Two rules that disagree at the same precedence produce *Cannot assess: conflicting rules* and go to the reviewer.

## 8. Case intake and extraction

**Case schema (core fields):** `case_id`, `insurer_id`, `plan_id`, `member_ref` (pseudonymous ID, no name), `service_date`, `visit_type`, `diagnoses[]` (code), `items[]` (`type`, `code`, `name`, `quantity`), `documents[]` (type labels), `prior_approval_ref`, `status`, `officer_id`, timestamps.

**Extraction pipeline (PDF upload):**
1. Extract text (PyMuPDF or pdfplumber). Scanned files go to a vision-capable model as a stretch goal.
2. Redact direct identifiers (name, national ID, phone) before any LLM call.
3. The LLM returns JSON that matches the case schema. Each field has `value`, `confidence` and `source_text`. Missing information stays `null`; the model may not infer.
4. Validate with Pydantic. Invalid output is rejected and the form opens empty.
5. The UI shows each value beside its source text. The officer confirms or corrects every field before the check can run.

## 9. Check engine

A pure, deterministic function: `check(case, rules, governing_date) → results`.

| Check | Condition | Verdict |
| --- | --- | --- |
| Coverage | Matching rule with `effect: covered` | Covered |
| Exclusion | Matching rule with `effect: excluded` | Excluded under rule R |
| Prior approval | Rule requires it and `prior_approval_ref` is empty | Prior approval needed |
| Documents | Rule lists document types the case lacks | Documents missing: list |
| No rule | No applicable rule for the item | No rule found, verify with insurer |
| Completeness | Required case field is empty | Cannot assess: field missing |
| Upcoming | Rule is `announced` and takes effect after the governing date | Info: change announced for date D |

**Result object per item:** `item`, `verdict`, `severity` (`action_needed` | `verify` | `info`), `rule_id`, `rule_version`, `effective_from`, `source_ref`, `explanation` (a template-generated sentence from those fields), `suggested_officer_action` (a fixed generic phrase per verdict; never clinical).

Every run is stored with the rule versions it used. That makes any past result reproducible.

## 10. Impact analysis and alerts

**Algorithm after each sync:**
1. For every open case, run the engine with current rules.
2. Compare each item's new result to its last stored result.
3. If the verdict, rule version or effective date changed, create or update an alert.
4. Dedupe key: `(case_id, item_code, rule_id)`. An existing alert with the same key is marked `superseded` and linked to the new one.
5. If a later change makes the item clear again (for example a delay moves the effective date past the service date), the alert closes with the reason "change delayed" or "change cancelled".


Re-running all open cases after each sync is simple and robust, and it also catches cases that cross an effective-date boundary with no new event. Scale it later with an index on item codes.

**Alert content:** headline; insurer and plan; change type; effective date; rule ID with version before and after; source and received date; affected case IDs and items; the fixed generic officer action; links to the case and the rule.

**Sample alert:**
> **Coverage change affecting 1 open case**
> Insurer: Demo Insurer · Plan: PLAN-GOLD
> Change: DRUG-A is now excluded (rule R-101, v1 → v2), effective 1 Nov 2026
> Source: insurer feed, received 24 Oct 2026 06:00
> Affected: Case C-001 (service date 10 Nov 2026)
> Action: Verify with the insurer and inform the treating physician before submission.

**Stale-rules banner:** shown to all users when the last successful sync is older than a configured threshold (default 26 hours; set to 1 minute in the demo environment).

## 11. Where the AI fits

| Task | Input | Output | Human check |
| --- | --- | --- | --- |
| T1 Case extraction | Redacted text of an uploaded file | Case JSON with confidence and source text | Officer confirms every field |
| T2 Circular parsing (should-have) | Circular text | Proposed rule changes, each with source text | Reviewer approves each change |
| T3 Alert wording (optional) | Structured alert facts | One or two clear sentences | Output validated against the facts |

**Guardrails:**
- Structured output only, validated against JSON Schema; failures fall back to manual entry or templated text.
- Temperature 0; fixed prompt versions stored in the repo and logged with each call.
- Confidence is a sorting hint for the UI, never a gate.
- T3 validation: rule ID, version, dates and codes must appear verbatim in the generated text. If not, use the template.
- The model never sees patient names or national IDs, and never outputs a coverage verdict.
- Every LLM call is logged: prompt version, input hash, output, validation result.

**Provider choice:** any model with structured output works. Choose the provider by the hospital's data-residency and retention terms (Section 13).

## 12. Tech stack and repository layout

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Database | PostgreSQL (SQLite acceptable for a demo build), SQLAlchemy, Alembic |
| Scheduler | APScheduler inside the worker, plus the manual trigger endpoint |
| HTTP client | httpx |
| Frontend | React, TypeScript, Vite, Tailwind |
| PDF text | PyMuPDF or pdfplumber |
| LLM | Provider SDK behind the LLM gateway module |
| Packaging | Docker Compose; one command starts everything |
| Tests | pytest (backend), Playwright (demo path) |

```
coverage-check-agent/
├─ docker-compose.yml
├─ backend/
│  ├─ app/
│  │  ├─ api/            # routes: cases, alerts, rules, sync, audit
│  │  ├─ domain/         # pydantic models (rule, case, result, alert)
│  │  ├─ engine/         # check engine, effective-date logic
│  │  ├─ sync/           # insurer client, change detector, worker
│  │  ├─ impact/         # impact analyser, alert service
│  │  ├─ llm/            # gateway, redaction, prompts, validators
│  │  ├─ audit/          # append-only writer
│  │  └─ db/             # models, migrations
│  └─ tests/             # golden tests, boundary tests
├─ mock-insurer/         # FastAPI app + console UI to publish/delay/cancel
├─ frontend/             # screens from Section 4
├─ data/
│  ├─ synthetic-cases/
│  └─ circulars/
└─ docs/                 # this draft, schemas, demo script
```

**Contract-first rule:** the team agrees the Pydantic schemas in Appendix A in the first hours. Backend, mock insurer and frontend all build from them.

## 13. Security, privacy, compliance

- **Hackathon data:** synthetic only. No real patient or insurer data enters the repo or any LLM call.
- **Data minimisation:** pseudonymous `member_ref`; identifiers redacted before LLM calls; the insurer feed carries no patient data by design.
- **Access control:** role-based (officer, reviewer, auditor); a per-hospital tenant key in every table.
- **Audit log:** append-only; each entry has timestamp, actor, action, object ID, and rule version where relevant; optional hash chaining for tamper evidence.
- **Transport and storage:** TLS in transit, encrypted storage, secrets in environment or a secrets manager, no PHI in application logs.
- **Decisions to settle before any pilot:** the personal-data and health-data law that applies in the hospital's country; the data-sharing agreement with the insurer (read-only rules feed); the LLM provider's retention, training-use and region terms; whether patient text may leave hospital infrastructure at all (if not, extraction runs on a hospital-hosted model or stays manual).

## 14. Hackathon build plan

**Assumptions:** 48 hours; a team of five; Docker on every laptop. Adjust the hours proportionally for a different length.

| Phase | Hours | Deliverable | Done when |
| --- | --- | --- | --- |
| 0 Setup | 0 to 4 | Repo, Compose stack, Appendix A schemas agreed, synthetic data outline | `docker compose up` runs an empty app, mock insurer and DB |
| 1 Core | 4 to 16 | Rules store, mock insurer with feed, sync worker, check engine with golden tests | A rule published in the mock appears in the store; engine tests pass |
| 2 Product | 16 to 28 | Case form, results view, impact analysis, alerts, inbox, audit log | Seeded change produces the expected alert in the UI |
| 3 AI and resilience | 28 to 36 | PDF extraction with confirmation UI, stale banner, delay and cancel handling | Delay closes the alert; killing the mock triggers the banner |
| 4 Polish | 36 to 44 | Rules browser, sync status, demo data reset script, optional circular parsing, UI polish | Full demo runs twice without manual fixes |
| 5 Buffer | 44 to 48 | Rehearsal, slides, bug fixes only | Code freeze at hour 44 |

**Roles:** (1) backend lead for engine, rules and sync; (2) backend or data engineer for impact analysis, alerts, audit and the mock insurer; (3) AI engineer for extraction, circular parsing, redaction and prompts; (4) frontend engineer for all screens; (5) product and demo lead for the script, synthetic data, slides and QA.

**Cut order if behind:** circular parsing, then PDF extraction (keep the form), then the rules browser, then the auditor export. Never cut: the engine, sync, impact analysis, alerts, the audit log, or the stale banner.

## 15. Demo script and synthetic data

**Fictional setup:** Demo Insurer; plan `PLAN-GOLD`; drug `DRUG-A` (covered); procedure `PROC-1` (covered, prior approval required); service `SVC-9` (no rule).

**Seeded cases:**

| Case | Content | Service date | Expected first result |
| --- | --- | --- | --- |
| C-001 | DRUG-A | 10 Nov 2026 | Clear |
| C-002 | DRUG-A | 28 Oct 2026 | Clear |
| C-003 | PROC-1, no prior-approval reference | 5 Nov 2026 | Needs attention: prior approval needed |
| C-004 | SVC-9 | 6 Nov 2026 | Cannot assess: no rule found |

**Script (about 6 minutes):**
1. Show the inbox (empty) and the freshness indicator (synced today).
2. Open C-001, run the check: clear. Show C-003 and C-004 results to demonstrate the check types.
3. In the Insurer console, publish: DRUG-A excluded under PLAN-GOLD, effective 1 Nov 2026.
4. Click Run sync now. An alert appears for C-001. C-002 has no alert because its service date is before the effective date; point this out.
5. Open the alert: rule ID, v1 to v2, effective date, source, generic action.
6. In the console, delay the change to 1 Dec 2026. Sync. The alert on C-001 closes with the reason "change delayed".
7. Cancel the change and show the audit log trail for the whole sequence.
8. Stop the mock insurer, run sync: the stale-rules banner appears.
9. Optional: upload a sample circular, show proposed changes in the review queue, approve one, and show it in the rules browser.

**Reset script:** one command restores the database and the mock insurer to the seeded state.


## 16. Testing and evaluation

| Test | Method | Pass criterion |
| --- | --- | --- |
| Engine correctness | Table-driven golden tests for every verdict and precedence rule | 100% pass |
| Effective-date boundaries | Cases with service date one day before, on and after `effective_from` and `effective_to` | Correct verdict each time |
| Sync idempotency | Replay the same events twice | No duplicate rules or alerts |
| Change detection | Seeded add, modify, remove, delay, cancel events | Each detected once, with the right before and after |
| Alert dedupe and lifecycle | Change, delay, cancel sequence on one case | One live alert at a time; correct closing reasons |
| Stale banner | Make the feed fail | Banner appears after the threshold and clears after a good sync |
| Extraction accuracy | 10 synthetic PDFs with known values | Per-field accuracy reported; no field filled where the source is empty |
| Wording validation | Inject a model output with a wrong date | Falls back to the template |
| End to end | Demo script on a clean stack | Completes without manual repair; sync to alert in under 60 seconds on the demo dataset |

**Acceptance for the hackathon:** all Must items in Section 3 demonstrated live; golden tests green; demo script runs twice in a row.

**Pilot metrics (later, on real data):** time from rule change to officer awareness; share of alerts the officers judge useful; rejections caused by rule changes before and after; share of items returning "no rule found"; officer time per case.

## 17. Risks, assumptions, open decisions, roadmap

| Risk | Mitigation |
| --- | --- |
| Insurer offers no feed | Circular ingestion with human review; start with the insurer that agrees |
| A change is missed | Weekly snapshot reconciliation; stale banner; sync health on the home screen |
| Misread circular | Reviewer approves every proposed rule; source text shown |
| Alert fatigue | Alert only on changed results; dedupe; track usefulness |
| Wrong governing date | Configurable per insurer; confirm during discovery |
| Extraction error | Officer confirms every field; nulls over guesses |
| Plan variants cause false results | Plan scoping in every rule; "no rule found" instead of assuming |
| Data protection | Synthetic data now; legal and provider review before any pilot |

**Assumptions in this draft:** 48-hour hackathon with five people; English UI; one insurer; the insurer can expose a read-only rules feed, or circulars are available as files; cases carry codes in the code sets the insurer's rules use.

**Decisions to confirm:** the hospital's country and target insurer; which date governs a rule; whether the insurer has any structured feed; the LLM data policy; the exact hackathon length and team size.

**Roadmap after the hackathon:**
1. **Baseline study (weeks 0 to 4):** take the hospital's last 12 months of rejections, mark which were caused by a rule change, and record the days between circular issue, effective date and officer awareness. This gives the real size of the problem.
2. **Pilot (months 1 to 3):** one insurer, one department, shadow mode first (alerts shown, officers keep their usual process), then live. Target the metrics in Section 16.
3. **Integration (months 3 to 6):** HIS adapter for case import; an official insurer feed; Arabic UI; email or push alerts.
4. **Scale:** more insurers, limit and frequency checks, standards-based feeds where insurers support them.

## Appendix A: Schemas, payloads, prompts

**Rule**
```json
{
  "rule_id": "R-101",
  "version": 2,
  "insurer_id": "demo-insurer",
  "plan_ids": ["PLAN-GOLD"],
  "category": "drug",
  "target": { "type": "drug", "code": "DRUG-A", "name": "Drug A" },
  "effect": "excluded",
  "conditions": null,
  "status": "announced",
  "effective_from": "2026-11-01",
  "effective_to": null,
  "source_ref": "feed:evt-000123",
  "received_at": "2026-10-24T06:00:00+03:00"
}
```

**Change event (from the feed)**
```json
{
  "event_id": "evt-000123",
  "published_at": "2026-10-24T05:40:00+03:00",
  "change_type": "modified",
  "rule": { "rule_id": "R-101", "version": 2, "effect": "excluded", "status": "announced", "effective_from": "2026-11-01" },
  "previous": { "version": 1, "effect": "covered", "status": "effective" }
}
```

**Case**
```json
{
  "case_id": "C-001",
  "insurer_id": "demo-insurer",
  "plan_id": "PLAN-GOLD",
  "member_ref": "M-5f3a",
  "service_date": "2026-11-10",
  "visit_type": "outpatient",
  "diagnoses": [{ "code": "DX-1" }],
  "items": [{ "type": "drug", "code": "DRUG-A", "name": "Drug A", "quantity": 30 }],
  "documents": [],
  "prior_approval_ref": null,
  "status": "open"
}
```

**Check result item**
```json
{
  "item": { "type": "drug", "code": "DRUG-A" },
  "verdict": "excluded",
  "severity": "action_needed",
  "rule_id": "R-101",
  "rule_version": 2,
  "effective_from": "2026-11-01",
  "source_ref": "feed:evt-000123",
  "explanation": "DRUG-A is excluded under rule R-101 v2 from 2026-11-01 for PLAN-GOLD.",
  "suggested_officer_action": "Verify with the insurer and inform the treating physician before submission."
}
```

**Alert**
```json
{
  "alert_id": "A-0007",
  "case_id": "C-001",
  "item_code": "DRUG-A",
  "rule_id": "R-101",
  "change": { "from_version": 1, "to_version": 2 },
  "status": "open",
  "supersedes": null,
  "closed_reason": null,
  "created_at": "2026-10-24T06:00:30+03:00"

  }
```

**Prompt T1: case extraction (system)**
```
You extract fields from a hospital patient file into JSON that matches the provided schema.
Rules:
- Use only information that is explicitly present in the text.
- If a field is not present, set it to null. Never guess or infer.
- For every field return: value, confidence (0 to 1), source_text (the exact words used).
- Do not include names, national IDs or phone numbers; they have been removed.
- Output JSON only.
```

**Prompt T2: circular parsing (system)**
```
You read an insurer circular and list the coverage-rule changes it states.
For each change return: category, target type, target code, target name, new effect,
plan scope, effective_from, effective_to, and source_text (the exact sentence).
If a date, code or plan is not stated, set it to null. Do not infer.
If the circular states no rule change, return an empty list. Output JSON only.
```

**Prompt T3: alert wording (system, optional)**
```
Write one or two plain sentences for a hospital claims officer from the structured facts.
Mention the rule ID, version, effective date and item code exactly as given.
Do not say a claim will be rejected. Do not give medical advice. Do not add facts.
```

**Sources**
- [Becker's: Experian 2024 State of Claims](https://www.beckersasc.com/asc-coding-billing-and-collections/claims-denials-surge-5-things-to-know/)
- [UVM Health Network testimony, Jan 2024](https://legislature.vermont.gov/Documents/2024/WorkGroups/House%20Health%20Care/Insurance%20Claims%20Processing/W~Kelly%20Lange~UVM%20Health%20Network%20Testimony%20-%20Claims%20Edits%20and%20Payer%20Administrative%20Burden~1-10-2024.pdf)
- [AAFP: Cigna delays modifier 25 documentation](https://aafp.org/pubs/fpm/blogs/gettingpaid/entry/cigna-modifier25-delay.html)
- [MPR/NPR: Anthem reverses anesthesia limits](https://www.mprnews.org/story/2024/12/05/npr-blue-cross-blue-shield-anesthesia-anthem)
- [Experian Payer Alerts](https://www.experian.com/blogs/healthcare/how-to-keep-up-with-changing-payer-requirements/)
- [Avia Policy Reporter](https://marketplace.aviahealth.com/company/72289)
- [Optum Digital Auth Complete](https://business.optum.com/en/operations-technology/revenue-cycle-management/patient-access/digital-auth-complete.html)
- [Innovaccer Flow Auth](https://thehealthcaretechnologyreport.com/innovaccer-launches-flow-auth-to-streamline-prior-authorizations-and-boost-roi/)

---

الخطوة الجاية اللي تنفع الفريق: جاوب على النقاط في "Decisions to confirm" (الدولة وشركة التأمين، التاريخ الحاكم للقاعدة، وجود feed عند الشركة، سياسة بيانات الـ LLM)، وأعدّل الدرافت عليها.
message.txt
32 KB
