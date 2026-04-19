# plan/phase-a.md — SPINE (3–5 days)

**Goal:** local CLI + minimal UI. Discovers from RemoteOK, ranks with embeddings, generates drafts, UI shows them, user approves → DB state transitions. Ships a usable tool even if you stop here.

**Swarm:** 4 agents. `swarm_init({ maxAgents: 4, topology: "hierarchical", strategy: "specialized" })`. Spawn Coordinator / Builder / Tester / Reviewer per `AGENTS.md` §1–§4.

---

## A.1 — Data layer alive

**Tests:**
- Project layout: parameterized over required paths (`pyproject.toml`, `app/__init__.py`, `app/main.py`, `web/package.json`, `docker-compose.yml`, `.env.example`, `alembic.ini`, `tests/conftest.py`, `.github/workflows/ci.yml`, `.gitignore`) — each exists, non-empty.
- Health: `GET /health` → 200 `{status, db, version}`; 503 with DB monkeypatched down; shape-stable under random query params via `hypothesis`.
- Schema round-trip: `polyfactory` factories per model; `@given(st.integers(min_value=1, max_value=200))` rows inserted + selected per model, equality per field.
- Unique `(source, external_id)` on jobs raises `IntegrityError`.
- Cascade delete: removing a profile removes associated applications.
- Vector nearest-neighbor: 100 random 384-dim vectors inserted; HNSW query returns cosine-nearest.

**Build:**
- `pyproject.toml` (uv, deps per ARCHITECTURE.md external-services section + dev deps: pytest, pytest-asyncio, pytest-cov, hypothesis, polyfactory, respx, vulture, ruff).
- `docker-compose.yml` — services `postgres` (`pgvector/pgvector:pg16`, healthcheck, volume), `app`, `web`.
- `.env.example`, `.gitignore`, `alembic.ini`, `migrations/env.py`.
- `app/{__init__,config,db,main,logging}.py`.
- All 6 models per `ARCHITECTURE.md` data model.
- `app/api/health.py` wired into `app/main.py`.
- Single Alembic migration `0001_initial.py` — `CREATE EXTENSION vector`, HNSW index on `jobs.description_embedding`, GIN on `to_tsvector('english', jobs.description)`.

**CHECKPOINT A.1:**
```
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8000 &
sleep 3
curl -s localhost:8000/health | jq .
```
Expected: `{"status":"ok","db":"ok","version":"0.1.0"}`.

```
docker compose exec postgres psql -U intern -d internship -c "\dt"
docker compose exec postgres psql -U intern -d internship -c \
  "SELECT indexname FROM pg_indexes WHERE tablename='jobs';"
```
Expected: 7 tables. Indexes include `jobs_description_embedding_hnsw_idx`.

→ `approved` to proceed.

---

## A.2 — First ranked jobs in DB

**Tests:**
- `JobSource` ABC: direct instantiation raises `TypeError`; concrete subclass with `fetch` + `normalize` instantiates.
- RemoteOK scraper: fixture `tests/scrapers/fixtures/remoteok_200.json` (sanitized real sample); `respx` mocks endpoint; `@given` over 1k shape-valid entries → parser never crashes, outputs have non-empty title + company; 10 parameterized malformed payloads → graceful skip + structured log.
- Dedup: 10k generated jobs with controlled overlap on normalized `(company, title, location)` → exact collapse count; earliest `discovered_at` wins the merge.
- Embedding ranker: identical-text cosine > 0.99; orthogonal texts < 0.35; batch of 64 encodes in <2s on CPU.
- Keyword prefilter: monotonic in matched-skill count (property test).
- Profile import: 5 parameterized resume samples (short / long / PK / US / PDF-extracted) → extracted skills are a subset of resume text, non-empty, deduped.

**Build:**
- `app/scrapers/base.py` — `@dataclass RawJob`, `class JobSource(ABC)` with `fetch`/`normalize` abstract + concrete `run()` doing fetch→normalize→dedup→persist.
- `app/scrapers/_robots.py` (gate every request), `app/scrapers/_ratelimit.py`.
- `app/scrapers/remoteok.py` (1 req/5s, UA header).
- `app/services/dedup.py` — normalized hash, stored on `jobs.hash`.
- `app/ranker/keyword.py` — pure function.
- `app/ranker/embedding.py` — MiniLM with `batch_size=64`, writes `description_embedding`.
- `app/services/profile.py` + `app/generator/prompts/extract_profile.v1.txt`.
- `app/llm/client.py` + `app/llm/groq_client.py` — **cache-aware** (SELECT from `llm_calls` by `prompt_hash` before API call).
- `app/__main__.py` CLI: `discover`, `rank`, `profile import <path>`.

**CHECKPOINT A.2:**
```
uv run python -m app profile import ./my_resume.md
uv run python -m app discover --source remoteok --limit 50
uv run python -m app rank

docker compose exec postgres psql -U intern -d internship -c \
  "SELECT title, company, keyword_score, round(embedding_score::numeric, 3) AS emb
   FROM jobs ORDER BY embedding_score DESC NULLS LAST LIMIT 10;"
```
Expected: 10 rows, plausibly AI/ML-related given your profile, `emb` descending in `[0,1]`.

→ `approved` to proceed.

---

## A.3 — First draft generated

**Tests:**
- LLM client: `respx` mocks Groq; tenacity retry on 429 asserted via request count; cache-hit path bypasses API when `llm_calls` row pre-seeded.
- Resume tailorer: property test — every section heading from `base_resume_md` appears verbatim in output (no hallucinated experience).
- Cover letter: output contains company name + ≥2 matched skills from the job's `matched_skills`.
- Cold email: subject ≤70 chars, body ≤200 words (parameterized over 20 generated jobs).
- `MAX_DRAFTS_PER_DAY` cap: 11th call in 24h raises `DraftLimitExceeded`.

**Build:**
- `app/generator/resume.py` + `prompts/resume.v1.txt`.
- `app/generator/cover_letter.py` + `prompts/cover_letter.v1.txt`.
- `app/generator/cold_email.py` + `prompts/cold_email.v1.txt`.
- `app/services/generation.py` — orchestrates all three, stores `Draft`, enforces daily cap.
- CLI: `generate --job-id <uuid> --out ./drafts/` writes three `.md` files.

**CHECKPOINT A.3:**
```
JOB_ID=$(docker compose exec -T postgres psql -U intern -d internship -t -c \
  "SELECT id FROM jobs ORDER BY embedding_score DESC LIMIT 1;" | xargs)
uv run python -m app generate --job-id "$JOB_ID" --out ./drafts/
ls ./drafts/
cat ./drafts/cover_letter.md
```
Expected: three files (`resume.md`, `cover_letter.md`, `email.md`). Cover letter names the real company from the job, references your actual skills.

→ `approved` to proceed.

---

## A.4 — End-to-end spine (UI + approve)

**Tests:**
- API (`async_client`): `POST /api/drafts/generate/{job_id}` creates Application + Draft; `GET /api/drafts/{id}` returns it; `PATCH` updates; `POST /approve` → DRAFTED→APPROVED; `POST /reject` → WITHDRAWN. Invalid transitions → 409.
- Auth: unauthenticated access to `/api/drafts/*` → 401; post-login round-trip succeeds.
- Frontend (Vitest + RTL): `/inbox` renders list from mocked API; click navigates to `/draft/[id]`; draft view shows JD left + 3 editable tabs right; Approve fires API call.

**Build:**
- `app/auth/session.py` (`itsdangerous`), `app/api/auth.py` (login/logout/me), `app/api/drafts.py`, `app/api/jobs.py`, `app/api/applications.py`.
- `app/schemas/*.py` — Pydantic per model.
- Next.js: `web/app/{login,inbox,draft/[id]}/page.tsx`, `web/lib/api.ts` (typed client from OpenAPI via `openapi-typescript`), `web/lib/auth.ts`.
- `web/components/{JobCard,DraftEditor,ApproveBar}.tsx` — shadcn.
- `scripts/seed_user.py` — creates user from env vars.

**CHECKPOINT A.4 (end of spine):**
```
docker compose down -v && docker compose up -d postgres
uv run alembic upgrade head
uv run python scripts/seed_user.py
uv run python -m app profile import ./my_resume.md
uv run python -m app discover --source remoteok --limit 50
uv run python -m app rank
uv run uvicorn app.main:app --port 8000 &
cd web && pnpm run dev &
```
Browser flow:
1. http://localhost:3000 → redirects to `/login`.
2. Log in with `.env` credentials.
3. `/inbox` shows ranked jobs.
4. Click top job → `/draft/<id>` shows JD left, tabs right.
5. Edit cover letter → Save → refresh → edit persists.
6. Click Approve.
```
docker compose exec postgres psql -U intern -d internship -c \
  "SELECT a.status, d.prompt_version FROM applications a
   JOIN drafts d ON d.application_id=a.id ORDER BY a.updated_at DESC LIMIT 1;"
```
Expected: `APPROVED | v1`.

→ `approved` to advance to Phase B.

---

## Phase A integration test

`tests/phase_a_integration.py` — runs A.1–A.4 sequence in-process (API round-trips replace browser steps). Must pass green. Rule-6 clean repo-wide.
