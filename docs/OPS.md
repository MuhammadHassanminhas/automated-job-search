# OPS — Runbook

## Start everything locally

```
docker compose up -d postgres
uv run uvicorn app.main:app --reload          # :8000
cd web && pnpm run dev                        # :3000
```
Open http://localhost:3000.

## Resume Claude Code mid-phase

```
cd internship-intel
claude
> Resume from the last green checkpoint per swarm memory.
```
Ruflo `session-end` hook restored state.

## Common queries

```sql
-- top 10 by final score
SELECT title, company, llm_score FROM jobs ORDER BY llm_score DESC NULLS LAST LIMIT 10;

-- drafts awaiting review
SELECT d.id FROM drafts d JOIN applications a ON d.application_id=a.id
 WHERE a.status='DRAFTED';

-- sent today
SELECT count(*) FROM applications WHERE status='SENT'
 AND updated_at > now() - interval '1 day';

-- LLM cost last 30d
SELECT provider, count(*), sum(tokens_in+tokens_out) FROM llm_calls
 WHERE created_at > now() - interval '30 days' GROUP BY provider;

-- cache hit rate
SELECT
  100.0 * sum(CASE WHEN response IS NOT NULL AND latency_ms = 0 THEN 1 ELSE 0 END) / count(*)
  AS hit_rate_pct
FROM llm_calls WHERE created_at > now() - interval '7 days';
```

## Debugging

| Symptom | Fix |
|---|---|
| Test red, you think it's wrong | If stale vs new API → Tester updates, not Builder. If test is right → Builder fixes impl. |
| Reviewer flags dead code | Delete or wire it up. **Never** silence with `# noqa` or `vulture: ignore`. |
| LLM returns garbage JSON | Check `llm_calls` for raw response. Verify prompt template unchanged. If Groq 5xx, failover to Gemini should auto-trigger — if it didn't, write a test + fix in `app/llm/client.py`. |
| Scraper stops parsing | Site changed HTML. Re-run with `LOG_LEVEL=DEBUG`. Tester updates fixture, Builder updates selectors. |
| Free-tier LLM limits hit | Client backs off. If persistent: lower `MAX_DRAFTS_PER_DAY`, raise `DISCOVERY_INTERVAL_HOURS`, or add paid key (swap in `app/llm/client.py`). |
| Gmail send fails | `fly logs` → grep `sender`. Usually expired refresh_token → reconnect on `/profile`. |

## Deploy (Phase C)

One-time:
```bash
curl -L https://fly.io/install.sh | sh
fly auth signup
fly launch --name internship-intel --region sin
fly postgres create --name internship-intel-db --region sin
fly postgres attach internship-intel-db --app internship-intel
fly secrets set \
  GROQ_API_KEY=... GEMINI_API_KEY=... \
  SESSION_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))') \
  FERNET_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())') \
  GMAIL_OAUTH_CLIENT_ID=... GMAIL_OAUTH_CLIENT_SECRET=... \
  --app internship-intel
```

Every deploy:
```
fly deploy
fly logs --app internship-intel
```

## Nuke and restart

```
docker compose down -v
rm -rf .venv web/node_modules .pytest_cache web/.next
git clean -fdx
uv sync && cd web && pnpm install && cd ..
uv run alembic upgrade head
```

## Stop signals (when to pivot)

Honest abandonment criteria — no sunk-cost bias:

- **After Phase A**, if 20 applications yield zero responses over 3 weeks: the bottleneck is likely your profile/resume, not the pipeline. Fix that before building more system.
- **After Phase B**, if LLM-judge scores cluster (everything 40–60), your profile embedding is too vague. Add 2–3 specific, completed projects to `profiles.projects` and re-rank.
- **Before Phase C**, if local works fine and you have no plan to share it: skip C. Production deploy is only worth the cost if you need remote access or want to productize.
