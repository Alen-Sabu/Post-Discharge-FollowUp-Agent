# AfterCare

**Post-discharge voice follow-up powered by CALL-E.**

Follow-up care that reaches patients before risk escalates.

AfterCare is a clinical workspace: it places structured calls after hospital discharge, scores recovery risk from the conversation, and puts the next action in front of the care team. The clinic UI is served from this same FastAPI process — judges only need to run the backend.

## What it does

- Places **consent-aware CALL-E** follow-up calls from disease-specific protocols (questions, warning signs, result schema)
- **Schedules** outreach and retries missed calls within attempt limits
- **Scores clinical risk** (low / medium / high / critical) from CALL-E structured results plus Gemini or Claude
- **Escalates emergencies**: SMS the doctor (Twilio), then a CALL-E warning call
- Serves a **clinic UI** (overview, activity, patients, protocols, AI assistant) from `static/frontend/`
- Lets staff **ask the clinic in plain language**; the assistant answers only from live tools
- **Semantic search** over patients and call transcripts (sentence-transformers + pgvector)

The agent summarizes recorded clinic data. It does not diagnose or prescribe.

## Architecture

AfterCare is one FastAPI process that both serves the clinic UI and runs the follow-up pipeline. PostgreSQL is the system of record. CALL-E is the voice plane. Twilio and LLMs are sidecar services used only after a call completes.

### 1. Context

```mermaid
flowchart LR
  staff[CareTeam]
  patient[DischargedPatient]
  doctor[AttendingDoctor]
  ui[ClinicUI]
  api[AfterCare_FastAPI]
  db[(Postgres_pgvector)]
  calle[CALLE_voice]
  twilio[Twilio_SMS]
  llm[Gemini_or_Claude]
  embed[MiniLM_local]

  staff --> ui
  ui --> api
  api --> db
  api -->|"place follow-up / warning call"| calle
  calle -->|"phone"| patient
  calle -->|"phone"| doctor
  calle -->|"webhook transcript + result"| api
  api --> llm
  api --> embed
  api -->|"emergency SMS"| twilio
  twilio --> doctor
```

### 2. Components inside FastAPI

Layered so HTTP handlers stay thin: routes → services → repositories → Postgres.

```mermaid
flowchart TB
  subgraph edge [Edge]
    staticFiles[static_frontend]
    routers[API_routers]
    mw[JWT_CORS_CSP]
  end

  subgraph domain [Domain]
    patients[PatientService]
    protocols[ProtocolService]
    followups[FollowUpService]
    calls[CallService]
    webhooks[WebhookService]
    risk[AIService]
    notify[NotificationService]
    agent[AgentService]
  end

  subgraph workers [In_process_workers]
    sched[APScheduler_due_followups]
    backfill[Embedding_backfill]
  end

  subgraph outbound [Integrations]
    calleSdk[calle.py]
    twilioSdk[twilio.py]
    llmSdk[google_anthropic]
  end

  staticFiles --> mw
  routers --> mw
  mw --> patients
  mw --> protocols
  mw --> followups
  mw --> calls
  mw --> webhooks
  mw --> agent
  sched --> calls
  calls --> calleSdk
  webhooks --> risk
  webhooks --> notify
  notify --> twilioSdk
  notify --> calleSdk
  risk --> llmSdk
  agent --> db[(Postgres)]
  patients --> db
  backfill --> db
```

| Piece | Responsibility |
|---|---|
| `static/frontend/` | Built Next.js export. Served last, after API routes. |
| `app/api/routes/` | Auth, patients, protocols, follow-ups, calls, dashboard, agent, webhooks. |
| `ProtocolService` | Turns questions / keywords / fields into a CALL-E **task** and **result schema**. |
| `CallService` | Consent check, create `Call` row, place CALL-E call, mark follow-up attempts. |
| `WebhookService` | Verify payload, idempotency, flatten transcript, score risk, escalate. |
| `NotificationService` | SMS first, then CALL-E doctor warning. Skips if no doctor number. |
| `AgentService` | Tool-using clinic assistant (Gemini / Claude). Answers only from tool results. |
| APScheduler | Every `SCHEDULER_INTERVAL_MINUTES`, pick due follow-ups (limit 20). |
| Embedder | Local `all-MiniLM-L6-v2` (384-d) into `patient_embeddings` / `call_embeddings`. |

**Same-process routing:** `/health`, `/auth`, `/patients`, `/protocols`, `/calls`, `/followups`, `/dashboard`, `/agent`, `/webhooks`, `/docs` are JSON/API. Everything else (`/`, `/login`, `/admin/...`, `/_next`) is the UI.

### 3. Data model

```mermaid
erDiagram
  User ||--o{ RefreshToken : has
  DiseaseProtocol ||--o{ ProtocolQuestion : has
  DiseaseProtocol ||--o{ ProtocolEmergencyKeyword : has
  DiseaseProtocol ||--o{ ProtocolResultField : has
  DiseaseProtocol ||--o{ Patient : assigned
  Patient ||--o{ FollowUp : scheduled
  Patient ||--o{ Call : receives
  Patient ||--o| PatientEmbedding : indexed
  FollowUp ||--o{ Call : produces
  Call ||--o{ Symptom : extracted
  Call ||--o{ EmergencyNotification : alerts
  Call ||--o{ WebhookEvent : idempotency
  Call ||--o| CallEmbedding : indexed
```

- **Protocol** is the clinical contract for a call: what to ask, what to watch for, what structured fields CALL-E must return.
- **FollowUp** is the work queue (`pending` → `in_progress` → `completed` / `failed`), with `attempt_count` / `max_attempts` (default 3). An ambiguous provider create leaves the follow-up `in_progress` for reconciliation.
- **Call** stores provider id, transcript, summary, `risk_score`, `risk_level`, `is_emergency`.
- **WebhookEvent** unique on `event_id` so CALL-E retries do not double-score or double-alert.
- Patient `current_risk_level` only **ratchets up** (low → critical), never down from a later quieter call.

### 4. Follow-up call sequence

```mermaid
sequenceDiagram
  participant UI as ClinicUI
  participant API as FastAPI
  participant DB as Postgres
  participant S as Scheduler
  participant CE as CALLE

  UI->>API: create patient plus protocol consent
  API->>DB: Patient FollowUp pending
  Note over S: tick every N minutes
  S->>DB: due follow-ups scheduled_time now
  S->>API: CallService.trigger
  API->>API: refuse live call if no consent
  API->>API: build task and result schema
  API->>DB: Call queued
  API->>CE: place_call dry_run or live
  CE-->>API: provider_call_id
  API->>DB: Call status plus calle_call_id
```

Immediate trigger from the UI uses the same `CallService.trigger` path as the scheduler. Dry-run writes the call row and skips the CALL-E HTTP request.

### 5. Webhook, risk, and escalation

Only terminal events are processed: `call.completed`, `call.failed`, `call.result_validation_failed`. Doctor warning calls are a separate `purpose=doctor_warning` path and do not re-score the patient.

```mermaid
sequenceDiagram
  participant CE as CALLE
  participant WH as POST_webhooks_calle
  participant DB as Postgres
  participant AI as AIService
  participant N as NotificationService
  participant SMS as Twilio
  participant Warn as CALLE_warning

  CE->>WH: signed JSON
  WH->>WH: unwrap if CALLE_WEBHOOK_SECRET set
  WH->>DB: try_claim event_id
  alt duplicate
    WH-->>CE: 200 duplicate
  else call.failed
    WH->>DB: reopen FollowUp pending unless max attempts
  else call.completed
    WH->>WH: flatten transcript_turns
    WH->>AI: structured_result plus keywords plus transcript
    AI-->>WH: summary risk_score risk_level is_emergency symptoms
    WH->>DB: Call plus Symptoms plus Patient.risk if worse
    WH->>DB: upsert call embedding
    opt is_emergency
      N->>SMS: doctor SMS
      N->>Warn: doctor warning call
    end
  end
  WH-->>CE: 200
```

Risk combines CALL-E structured fields, protocol emergency keywords, and LLM extraction (Claude primary, Gemini fallback) when the payload is sparse.

### 6. Clinic assistant

`POST /agent/chat` is a tool loop (max 8 rounds). Tools query Postgres only: overview, list/detail patients, risk lists, overdue follow-ups, emergencies, discharge stats, semantic patient search, transcript search. Identical tool results are deduped before UI cards are built. The model is not allowed to invent patients or give treatment advice.

### 7. Auth and safety boundaries

- JWT access + refresh (`/auth/login`, `/auth/register` with `X-Register-Secret`).
- Live CALL-E requires `consent_on_file`. Dry-run does not.
- `CALLE_API_KEY` is sent only to `https://api.heycall-e.com`. Any other `CALLE_BASE_URL` is refused.
- Webhooks: optional signature verify; durable idempotency; failed claims can be retried.
- Default `DRY_RUN_DEFAULT=true` so a clone does not place real calls.
- The product summarizes recorded data. It does not diagnose or prescribe.


## Stack

Python, FastAPI, PostgreSQL + pgvector, SQLAlchemy, Alembic, CALL-E, Gemini / Claude, Twilio, sentence-transformers, Next.js static export.

## Run 

**Need:** Python 3.12+, PostgreSQL with the `vector` extension.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env: DATABASE_URL, JWT_SECRET, REGISTER_SECRET, CALLE_API_KEY
```

Enable pgvector in Postgres, then:

```bash
alembic upgrade head
python -m scripts.seed_protocols
```

Keep **`DRY_RUN_DEFAULT=true`** unless you intend to place real calls.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

| URL | What |
|---|---|
| http://localhost:8000 | Clinic UI |
| http://localhost:8000/docs | API |
| http://localhost:8000/health | Liveness |

Create a user with `POST /auth/register` and header `X-Register-Secret` matching `REGISTER_SECRET`, then sign in on `/login`. JWT protects the admin API.

**Live CALL-E** (optional): set `DRY_RUN_DEFAULT=false`, a real `CALLE_API_KEY`, and a public HTTPS `CALLE_WEBHOOK_URL` (for example ngrok) pointing at `/webhooks/calle`. The Bearer key is sent only to `https://api.heycall-e.com`; any other `CALLE_BASE_URL` is refused. Live calls never go out without consent on file.

## Repo map

| Path | Role |
|---|---|
| `app/api/routes/` | HTTP endpoints |
| `app/services/` | Follow-ups, risk, assistant, notifications |
| `app/integrations/calle.py` | Place calls + verify webhooks |
| `app/workers/` | Due-follow-up scheduler, embedding backfill |
| `static/frontend/` | Built clinic UI (committed; no Node required) |
| `scripts/seed_protocols.py` | Sample disease protocols |
| `scripts/sync_frontend.py` | Rebuild UI only if you have the sibling `frontend/` folder |

## Safety

- Default is dry-run: no CALL-E request is sent
- Live calls require `consent_on_file` and `authorized_destination` matching the exact ASCII E.164 patient phone
- The scheduler places dry-run follow-ups only; live outreach is `POST /calls/trigger`
- Sample numbers are reserved fictional E.164 values such as `+15555550100`
- Logs and the assistant mask phones, transcripts, and clinical text
- Webhook deliveries are idempotent
- An ambiguous CALL-E create (timeout, missing id, 5xx) stores the call as `outcome_unknown` and leaves the follow-up `in_progress`. Do not auto-retry; a person must reconcile it.
- Assistant tools read clinic data only; they do not invent patients
