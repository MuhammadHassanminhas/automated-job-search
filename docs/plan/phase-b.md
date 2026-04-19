# plan/phase-b.md — EXPANSION (5–7 days)

**Goal:** polished production-quality local web app. 3 sources, 3-stage funnel with LLM judge, Gemini failover, Gmail send, outbox + tracker UI, scheduler, hardened auth.

**Swarm:** existing 4 agents persist. Spawn 2 specialists from `AGENTS.md` §5–§6 (ML Specialist, Frontend Specialist). Do NOT re-spawn the original 4. Total: 6 agents.

Builder's scope narrows in Phase B to backend + scrapers. ML paths transfer to ML Specialist. `web/**` transfers to Frontend Specialist.

---

## B.1 — Full pipeline (3 sources, 3-stage funnel, scheduler)

**Tests:**
- Internshala scraper: canned HTML fixture `tests/scrapers/fixtures/internshala_sample.html`; selector tests; `@given` over 500 synthetic listings → parser robust; 10 malformed → graceful skip.
- Rozee.pk scraper: same rigor as above; 1 req/10s rate limit asserted.
- Incremental scraping: second run with unchanged `source_etag` makes zero parse calls — asserted via spy on the normalizer.
- LLM judge: `respx` mocks Groq; asserts output schema `{score: int in [0,100], reasoning: str non-empty, matched_skills: list[str]}`; malformed JSON raises `LLMJudgeParseError` — never silently accepts.
- Gemini failover: Groq returns 429 → client calls Gemini → asserts both calls happened, final result from Gemini.
- Scheduler: `freezegun` advances time; discovery tick fires at 6h intervals, rank tick at 1h.

**Build:**
- `app/scrapers/internshala.py`, `app/scrapers/rozee.py`.
- `app/ranker/llm_judge.py` — cache-aware via `llm_calls.prompt_hash`.
- `app/llm/gemini_client.py`.
- `app/llm/client.py` updated — failover chain (Groq → Gemini on 429/5xx), retry policy via `tenacity`.
- `app/scheduler.py` — APScheduler wired into FastAPI lifespan; jobs: `scheduler.discovery.tick` (6h), `scheduler.rank.tick` (1h), `scheduler.sender.tick` (30s) (sender pulled forward for B.2).

**CHECKPOINT B.1:**
```
uv run python -m app discover --all
uv run python -m app rank --full

docker compose exec postgres psql -U intern -d internship -c \
  "SELECT source, count(*) FROM jobs GROUP BY source;"
docker compose exec postgres psql -U intern -d internship -c \
  "SELECT title, company, llm_score, substring(llm_reasoning, 1, 80)
   FROM jobs WHERE llm_score IS NOT NULL ORDER BY llm_score DESC LIMIT 10;"
```
Expected: 3 sources represented. Top-10 reasoning references YOUR specific skills (not generic).

Restart app. Verify scheduler:
```
grep "scheduler.discovery.tick" logs/app.log | tail -1
```
Expected: a log line with recent timestamp.

→ `approved` to proceed.

---

## B.2 — Outreach + tracking

**Tests:**
- Gmail OAuth: end-to-end mocked flow; tokens stored encrypted — `cryptography.Fernet` round-trip asserted; token refresh on expiry.
- Sender MIME: asserts `From`, `To`, `Subject`, body, attachment named `resume.pdf` with `application/pdf` content-type. PDF generated from `resume_md` via `weasyprint`.
- Send queue idempotency: same APPROVED draft processed twice → exactly one `OutreachEvent` (UNIQUE on `sent_hash`).
- Status machine: APPROVED→SENDING→SENT on success; →FAILED with error logged on exception.
- Tracker drag-drop (RTL): dragging card from SENT→RESPONDED fires `PATCH /api/applications/{id}` with new status; optimistic update rolls back on 409 response.

**Build:**
- `app/auth/gmail_oauth.py` + `app/api/auth/gmail.py` (authorize/callback routes).
- `app/services/sender.py`, `app/services/pdf.py` (weasyprint).
- Poller loop in `app/scheduler.py` — every 30s picks APPROVED → sends.
- `web/app/outbox/page.tsx`, `web/app/tracker/page.tsx` (shadcn + `@dnd-kit/core`).
- `app/api/outreach.py`, `app/api/applications.py` (status transitions).

**CHECKPOINT B.2:**
Configure Gmail OAuth on `/profile` (connects your Gmail). Generate a draft → approve → wait 30s for poller. Send goes to your alt email.

```
docker compose exec postgres psql -U intern -d internship -c \
  "SELECT direction, sent_at, substring(subject, 1, 60)
   FROM outreach_events ORDER BY sent_at DESC LIMIT 1;"
```
Expected: `OUT | <timestamp> | <real subject line>`. Check alt inbox — email arrived with `resume.pdf` attachment that opens.

On `/tracker`: drag the card SENT → RESPONDED. DB reflects the change.

→ `approved` to proceed.

---

## B.3 — Hardening

**Tests:**
- Brute-force protection: 5 failed logins in 60s → 429. Implemented via `slowapi`.
- Session cookie: in prod-mode test, asserts `Set-Cookie` contains `HttpOnly; Secure; SameSite=Lax`.
- Argon2 params: `argon2id`, t=3, m=64MB, p=4 — asserted via hash decoding.
- Public endpoint rate limits: 10 req/min/IP on login + `/api/auth/*`.
- Analytics: `SELECT * FROM v_response_rate_by_source` and `v_response_rate_by_prompt_version` return non-null rows with correct shape.
- Rule-6 scan over WHOLE repo: zero findings on all four commands.

**Build:**
- `app/auth/ratelimit.py` (slowapi middleware).
- Migration `0002_analytics_views.py` — SQL views `v_response_rate_by_source`, `v_response_rate_by_prompt_version`.
- `web/app/profile/page.tsx` — analytics cards (source table, template table).
- `app/logging.py` — PII redaction verified (emails, resume bodies scrubbed from log output).

**CHECKPOINT B.3 (end of phase B):**
```
uv run pytest --cov=app --cov-fail-under=80 -x
cd web && pnpm test && pnpm build
uv run vulture app tests --min-confidence 80
uv run ruff check --select F401,F841,F811 app tests
cd web && pnpm dlx knip
grep -rnE "TODO|FIXME|XXX|NotImplementedError" app web \
  --include="*.py" --include="*.ts" --include="*.tsx"
```
All must exit zero.

Open `/profile` in browser → analytics panel renders with real numbers (e.g., "RemoteOK: 5 sent / 0 replied").

→ `approved` to advance to Phase C.

---

## Phase B integration test

`tests/phase_b_integration.py` — seed → discover → rank → generate → approve → send (to `aiosmtpd` fake SMTP server) → tracker transition → analytics query. End-to-end, no live Gmail.
