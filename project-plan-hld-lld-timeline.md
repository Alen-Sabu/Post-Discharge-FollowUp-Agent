# Post-Discharge Follow-Up Agent — Full Plan

Revised scope for the CALL-E hackathon (deadline 14 Sept 2026). This
supersedes the original microservices/Redis/9-page-dashboard version — same
core idea, cut down to what actually wins on CALL-E's judging criteria
(real CALL-E usage, working demo, credible real-world impact) without
burning your 48 days on ops overhead. The backend below is already built
and tested (see the scaffold delivered earlier); this doc is the full plan
around it.

---

## 1. High-Level Design (HLD)

Single FastAPI app (modular monolith) instead of separate microservices.
One deployable unit, clean internal module boundaries — you get the same
separation of concerns without inter-service auth, networking, or
distributed debugging.

```
                        ┌─────────────────────────┐
                        │   Minimal Dashboard      │
                        │   (single page: React    │
                        │   or server-rendered)    │
                        └────────────┬─────────────┘
                                     │ REST
                                     ▼
                        ┌─────────────────────────┐
                        │      FastAPI App         │
                        │  ┌─────────────────────┐ │
                        │  │ api/patients.py     │ │
                        │  │ api/calls.py        │ │
                        │  │ api/webhooks.py     │ │
                        │  └─────────┬───────────┘ │
                        │            │             │
                        │  ┌─────────▼───────────┐ │
                        │  │ services/            │ │
                        │  │  call_e_client.py    │◄┼──── CALL-E (SDK/API)
                        │  │  ai_analysis.py       │◄┼──── LLM (Claude)
                        │  │  scheduler.py         │ │
                        │  │  notifications.py     │◄┼──── SMS/Email
                        │  └─────────┬───────────┘ │
                        └────────────┼─────────────┘
                                     ▼
                              ┌─────────────┐
                              │  PostgreSQL │
                              │  (SQLite    │
                              │  for local  │
                              │  dev/demo)  │
                              └─────────────┘
```

**Flow:**
1. Scheduler finds due follow-ups → triggers `call_e_client.place_call()`
2. CALL-E places the call, has the conversation, calls back your webhook
3. `webhooks.py` receives the transcript → `ai_analysis.py` extracts
   symptoms, scores risk, checks emergency keywords
4. If emergency → `notifications.py` alerts the doctor immediately
5. Dashboard reads calls/patients/risk levels from the DB

---

## 2. Low-Level Design (LLD)

### Data model (already implemented in `app/models/orm.py`)

```
Patient
  id, name, phone (E.164), age, gender, doctor_name,
  discharge_date, discharge_diagnosis,
  current_risk_level (low|medium|high|critical),
  consent_on_file (bool)  — hard gate before any real call

FollowUp
  id, patient_id → Patient, scheduled_time,
  status (pending|in_progress|completed|failed|cancelled),
  attempt_count, max_attempts

Call
  id, patient_id → Patient, followup_id → FollowUp,
  calle_call_id, call_start, call_end, status,
  transcript, summary, risk_score, risk_level,
  is_emergency, dry_run

Symptom
  id, call_id → Call, name, severity (mild|moderate|severe), note
```

### API surface (already implemented)

| Method | Path | Purpose |
|---|---|---|
| POST | `/patients` | Create patient (validates E.164 phone) |
| GET | `/patients` | List patients |
| GET | `/patients/{id}` | Get one patient |
| POST | `/calls/trigger` | Trigger a follow-up call (blocked without consent unless dry-run) |
| GET | `/calls` | List calls |
| GET | `/calls/{id}` | Get one call + symptoms |
| POST | `/webhooks/calle` | CALL-E's callback — receives transcript, runs analysis |
| GET | `/health` | Health check |

### Key module responsibilities

- **`call_e_client.py`** — the only file that talks to CALL-E. Builds a
  goal-driven prompt (not a rigid script), returns a `CallEResult`. Dry-run
  by default. **This is the one file you rewrite once you confirm CALL-E's
  real SDK contract.**
- **`ai_analysis.py`** — two-stage: (1) keyword backstop scans the *full*
  transcript for emergency terms, independent of the LLM; (2) LLM extracts
  structured symptoms/compliance/pain into JSON, fed into a rule-based
  `score_risk()` function — not a bare LLM classification, so it's
  explainable.
- **`webhooks.py`** — receives CALL-E's callback, runs analysis, updates
  `Call` and bumps `Patient.current_risk_level` if this call is worse than
  what's on file. Has the escalation hook (TODO marker) for notifications.

### Still to build

- **`services/scheduler.py`** — simple: an APScheduler job (in-process, no
  Celery/Redis needed at this scale) that runs every N minutes, queries
  `FollowUp` rows where `status = pending` and `scheduled_time <= now()`,
  calls the same logic as `POST /calls/trigger`, increments `attempt_count`
  on failure up to `max_attempts`.
- **`services/notifications.py`** — one function,
  `notify_emergency(patient, call)`, called from the TODO in `webhooks.py`.
  Simplest viable: Twilio SMS or SMTP email to `doctor_name`'s contact.
  Don't build a generic multi-channel system — one working channel beats
  three half-built ones for a demo.
- **Dashboard** — one page: a table of patients (name, risk level badge,
  last call summary, last call date) plus a detail view per patient
  showing call history and transcripts. Skip the 9-page version
  (Login/Dashboard/Patients/Calls/Appointments/Alerts/Analytics/Settings)
  from the original plan — it doesn't move the needle on judging criteria
  and eats days you don't have to spend.

---

## 3. Features

### MVP (must-have for submission)
- Patient creation with consent gate
- Real CALL-E call triggered against at least one real patient record
  (even if it's just you as the "patient" for the demo)
- Transcript received via webhook, analyzed, risk-scored
- Emergency keyword detection with a visible escalation action
  (notification sent)
- One dashboard page showing patients + risk + summaries
- A PR to CALL-E's `awesome-phone-call-agents` repo (required for
  submission — check the README for which contribution area, e.g.
  "Agent Skills" or an example app)
- 3-minute demo video showing a real call happening end-to-end

### Stretch (only after MVP is solid and demoed)
- Scheduler running unattended (vs. manually triggered) — shows
  automation, judges may value this
- Multi-attempt retry logic for missed calls
- Medication compliance trend over multiple calls
- Basic analytics chart (calls completed, risk distribution)

### Explicitly cut from original plan
- Microservices split, Redis/Celery, multi-role auth (doctor/nurse/admin),
  9-page dashboard, WhatsApp notifications. None of these help you score
  higher against CALL-E's actual judging rubric; all of them cost days.

---

## 4. Timeline (48 days to 14 Sept 2026, ~2-3 hrs/day solo)

| Days | Phase | Deliverable |
|---|---|---|
| 1-4 | Real CALL-E integration | `place_call()` implemented against actual SDK; one real call placed successfully |
| 5-6 | End-to-end verification | Real call → real transcript → real webhook → real risk score, confirmed working |
| 7-8 | Scheduler | Unattended follow-up triggering works |
| 9 | Notifications | Emergency → real SMS or email fires |
| 10-13 | Dashboard | Single-page patient list + detail view, wired to the API |
| 14-15 | Polish & safety | Seed realistic demo patients, re-read CALL-E's consent/safety reference, tighten the consent gate |
| 16 | Contribution PR | Write and submit the PR to `awesome-phone-call-agents` |
| 17 | Demo video | Record, 3 minutes, script it in advance |
| 18-20 | Buffer | Bug fixes, re-record video if needed |

Total: ~20 days of work inside a 48-day window — comfortable margin for
CALL-E's SDK changing under you mid-beta, which is the real schedule risk
here, not your own code.

---

## 5. Step-by-step — what to actually do, in order

1. **Run CALL-E's install guide** (~30 min per their own estimate):
   `https://raw.githubusercontent.com/CALLE-AI/call-e-integrations/main/docs/install/CALL-E-installation-guide.md`
   Get your API key / SDK access working with a trivial "hello world" call
   before touching this project's code.
2. **Read CALL-E's safety reference** in `awesome-phone-call-agents` —
   specifically consent handling and medical reminder boundaries, since
   they apply directly to this use case.
3. **Confirm the current SDK/API contract** — exact method names, whether
   it's the Python `calle-ai` package or raw HTTP, what the callback
   payload actually looks like when you test it against your own webhook
   URL (use `ngrok http 8000` to get a reachable URL in dev).
4. **Rewrite `call_e_client.place_call()`** using the confirmed contract.
   Keep the dry-run branch — it's useful for demo safety even after real
   integration works.
5. **Update `CalleWebhookPayload`** in `models/schemas.py` to match the
   real payload shape you observe.
6. **Place one real test call to yourself.** Confirm the full loop: call
   happens → you talk to CALL-E → webhook fires → transcript lands in your
   DB → risk score computes → (if you say "chest pain" as a test) emergency
   fires.
7. **Build `services/scheduler.py`** — APScheduler, in-process, polling
   `FollowUp` rows. Test with a followup scheduled 1 minute in the future.
8. **Build `services/notifications.py`** — pick one channel (Twilio SMS is
   fastest to set up), wire it into the TODO in `webhooks.py`.
9. **Build the single-page dashboard.** Plain React (or even server-rendered
   Jinja2 templates in FastAPI if you want to skip a frontend build step
   entirely) — patient table with risk badges, click-through to call
   history.
10. **Seed 3-5 realistic demo patients** with varied diagnoses and risk
    profiles so the dashboard doesn't look empty in the demo video.
11. **Write and open the PR** to `awesome-phone-call-agents` per their
    README's contribution instructions — do this before the video, since
    you'll want the PR link for submission.
12. **Script and record the 3-minute demo video**: show a real call being
    placed, the transcript coming back, risk scoring, and — the moment that
    sells it — an emergency call triggering a real notification.
13. **Submit** via Devpost with the PR URL, video link, and your CALL-E
    account email.

---

## 6. What to bring to me next time

The scaffold and this plan get you to step 3 above on your own (reading
CALL-E's docs is something only you can do against your actual beta
access). Come back once you've confirmed the SDK contract and I'll help
you implement `place_call()` for real, build the scheduler, or put the
dashboard together — whichever you want to tackle first.
