# ARCHITECTURE

Canonical design. Architect agent owns this file. Changes require ADR in `docs/adr/NNNN-title.md`.

---

## Topology

```
┌──────────────┐  incremental fetch (If-Modified-Since, cursor)
│  Scheduler   │──▶ RemoteOK ┐
│  APScheduler │    Internshala ├─▶ Normalizer ─▶ Dedup ─▶ Postgres(+pgvector,HNSW)
│  6h/1h jobs  │    Rozee.pk    ┘                                    │
└──────────────┘                                                     │
                                                                     ▼
                        ┌────────────────────────────────────────────────┐
                        │  Ranker — 3-stage funnel                       │
                        │  [A] keyword prefilter (pure Python)           │
                        │  [B] embeddings (MiniLM, batch=64, HNSW)       │
                        │  [C] LLM judge (Groq, top-20 only, cached)     │
                        └──────────────────────┬─────────────────────────┘
                                               ▼
                        ┌─────────────────────────────────────────────┐
                        │  Generator — resume / cover / email         │
                        │  prompt cache: (prompt_hash, model) → out   │
                        └──────────────────────┬──────────────────────┘
                                               ▼
           ┌────────────────┐   HTTP   ┌────────────────────────┐
           │  Next.js 15    │◀────────▶│  FastAPI               │──▶ Gmail API
           │  /inbox        │  typed   │  /api/{auth,jobs,      │    (send after
           │  /draft/[id]   │  client  │   drafts,applications, │     user approve)
           │  /outbox       │          │   outreach,profile}    │
           │  /tracker      │          └──────────┬─────────────┘
           │  /profile      │                     │
           └────────────────┘                     ▼
                                       ┌──────────────────────┐
                                       │  llm_calls (audit,   │
                                       │  cost, cache lookup) │
                                       └──────────────────────┘
```

---

## Layer boundaries (reviewer enforces)

| Layer | May import | Imported by |
|---|---|---|
| `app/models/*` | `app/db`, stdlib | everyone (read); writes go through services |
| `app/schemas/*` | `app/models` | `app/api`, `app/services` |
| `app/llm/*` | stdlib, `groq`, `google-generativeai`, `tenacity`, `app/models` (cache only) | `app/ranker`, `app/generator` |
| `app/scrapers/*` | `app/services`, `app/models`, `httpx`, `selectolax` | `app/scheduler`, CLI |
| `app/ranker/*` | `app/llm`, `app/models`, `app/services` | `app/scheduler`, `app/api` |
| `app/generator/*` | `app/llm`, `app/models` | `app/services`, `app/api` |
| `app/services/*` | `app/models`, `app/ranker`, `app/generator`, `app/llm` | `app/api`, CLI, scheduler |
| `app/api/*` | `app/services`, `app/schemas`, `app/auth` | `app/main` |
| `web/*` | backend only via typed client (`web/lib/api.ts`) | — |

**Forbidden:** scrapers/ranker importing api. Web importing anything Python. Cross-module DB writes (only services write).

---

## Data model

All tables have `id uuid pk`, `created_at`, `updated_at`. Fields below are additional.

**jobs** — `source` (enum), `external_id`, `url`, `title`, `company`, `location`, `remote_allowed`, `description`, `description_embedding vector(384)`, `posted_at`, `hash` (dedup key), `keyword_score`, `embedding_score`, `llm_score`, `llm_reasoning`, `source_etag` (for If-Modified-Since). Unique `(source, external_id)`. Index: HNSW on embedding, GIN on `to_tsvector('english', description)`.

**profiles** — one per user. `user_id fk`, `full_name`, `email`, `phone`, `skills jsonb[]`, `projects jsonb`, `education jsonb`, `base_resume_md`, `style_examples jsonb` (cover letters user wrote → few-shot anchors).

**applications** — `user_id fk`, `job_id fk`, `status` (enum: DRAFTED / APPROVED / SENDING / SENT / RESPONDED / INTERVIEWING / OFFERED / REJECTED / WITHDRAWN / FAILED).

**drafts** — `application_id fk unique`, `resume_md`, `cover_letter_md`, `email_subject`, `email_body`, `model_used`, `prompt_version`, `prompt_hash` (sha256 of full rendered prompt — cache key).

**outreach_events** — `application_id fk`, `channel` (EMAIL/LINKEDIN/FORM), `direction` (OUT/IN), `subject`, `body`, `sent_at`, `received_at`, `sent_hash unique` (idempotency).

**llm_calls** — `provider`, `model`, `prompt_hash`, `prompt`, `response`, `latency_ms`, `tokens_in`, `tokens_out`, `error`. Doubles as **response cache**: generator checks `SELECT response FROM llm_calls WHERE prompt_hash=? AND error IS NULL LIMIT 1` before calling the API.

**users** — `email unique`, `password_hash` (argon2).

---

## Optimizations (locked in v2)

1. **LLM response cache.** Every generator/judge call hashes its rendered prompt; identical prompts never re-call the API. Cache hit rate on scheduled re-ranks: ~90%.
2. **Batch embeddings.** MiniLM encodes 64 descriptions per call via `SentenceTransformer.encode(list, batch_size=64)`. 40× faster than one-by-one.
3. **HNSW vector index** (not ivfflat). `CREATE INDEX ON jobs USING hnsw (description_embedding vector_cosine_ops)`. Better recall at query time, no rebuild on insert.
4. **Incremental scraping.** Each source stores `source_etag` / `last_modified`. Next run sends `If-Modified-Since` and skips unchanged pages. Rozee/Internshala use cursor-based pagination capped at `max(posted_at) - 1 day`.
5. **Prompt versioning.** `app/generator/prompts/resume.v3.txt`. Version string embedded in `drafts.prompt_version`. Old drafts remain reproducible.
6. **Config cap** `MAX_DRAFTS_PER_DAY` (default 10). Enforced in service layer, prevents inbox flood even if discovery surfaces 500 matches.

---

## External services

| Service | Role | Tier | Swap in |
|---|---|---|---|
| Groq (`llama-3.3-70b-versatile`) | primary LLM | free 30 rpm / 14.4k rpd | `app/llm/groq_client.py` |
| Gemini 2.0 Flash | failover LLM | free 1500 rpd | `app/llm/gemini_client.py` |
| `sentence-transformers/all-MiniLM-L6-v2` | embeddings | free, local CPU | `app/ranker/embedding.py` |
| Gmail API | sending | free | `app/services/sender.py` |
| Fly.io (sin region) | hosting | $5/mo free credit | `fly.toml` |

---

## Security & ethics (non-negotiable)

- `robots.txt` honored per source (`app/scrapers/_robots.py` gates every request).
- Per-source rate limits (hardcoded constants). UA header `internship-intel/<ver> (+contact)`.
- **No form auto-submission.** Email-based applications only, always after explicit user approve.
- OAuth tokens encrypted at rest (`cryptography.Fernet`, key in `FERNET_KEY` env).
- Passwords: argon2. Sessions: HttpOnly + Secure (prod) + SameSite=Lax.
- PII redaction in `app/logging.py` — structured logs never contain email bodies or full resumes.
- `MAX_DRAFTS_PER_DAY` enforced in service layer.

---

## Config keys (`.env.example`)

```
DATABASE_URL=postgresql+asyncpg://intern:intern@localhost:5432/internship
GROQ_API_KEY=
GEMINI_API_KEY=
SESSION_SECRET=
FERNET_KEY=
GMAIL_OAUTH_CLIENT_ID=
GMAIL_OAUTH_CLIENT_SECRET=
GMAIL_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/gmail/callback
ENV=development
MAX_DRAFTS_PER_DAY=10
DISCOVERY_INTERVAL_HOURS=6
RANKING_INTERVAL_HOURS=1
LOG_LEVEL=INFO
```
