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
... (361 líneas restantes)
