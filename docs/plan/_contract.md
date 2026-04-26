# plan/_contract.md — Execution Contract

Always load this file alongside whatever phase file is active.

## Per-step sequence

1. Tester writes failing test → branch `step/<id>/tests` → run → **observe red**.
2. Owner (per `AGENTS.md` path table) writes minimum passing impl → branch `step/<id>/impl` → run → **observe green**.
3. Reviewer runs Rule-6 scan → **zero findings**.
4. Coordinator prints the CHECKPOINT header + verification script verbatim.
5. User runs script, sees expected output, types `approved` or `rejected <reason>`.
6. On `approved`: squash-merge both branches → `main` → mark TodoWrite entry complete.
7. On `rejected`: roll back, diagnose, fix, re-run from step 1.
8. On silence >24h AND tests + Rule 6 green: auto-advance, tag commit `UNVERIFIED` — user may revert later.

No step is done until all 8 apply.

## Test rigor (Tester enforces)

- ≥1 `hypothesis` property-based test per module.
- `polyfactory` factories for every model.
- Parameterized edges: empty, null, unicode, max-length, malformed, duplicate.
- HTTP: `respx` (Python) / `msw` (TS). No live calls.
- Hardcoded-literal-only assertions → rejected by Reviewer.

## Rule-6 scan (Reviewer runs on every step)

```bash
uv run vulture app tests --min-confidence 80
uv run ruff check --select F401,F841,F811 app tests
cd web && pnpm dlx knip
grep -rnE "TODO|FIXME|XXX|NotImplementedError|^\s*pass\s*$" \
  app web --include="*.py" --include="*.ts" --include="*.tsx" --exclude-dir=node_modules
```

All four commands must exit zero. Any finding blocks the checkpoint.

## Production Definition-of-Done (Phase C exit gate)

Phase C cannot close until **every** item verifies. Reviewer holds the line.

- [ ] `pytest --cov=app --cov-fail-under=80` green
- [ ] `vitest` green
- [ ] Rule-6 scan (all four commands) → zero findings across whole repo
- [ ] HTTPS certificate valid on fly.dev URL
- [ ] All secrets via `fly secrets` — `git grep -E '(GROQ|GEMINI|SESSION|FERNET|GMAIL)_' -- ':!*.example' ':!docs/**'` returns nothing
- [ ] Structured logs via `structlog` with PII redaction in `app/logging.py`
- [ ] DB migrations run on every deploy (`release_command = "alembic upgrade head"` in `fly.toml`)
- [ ] Rate limiting on public auth endpoints (`slowapi`, 10 req/min/IP)
- [ ] CORS locked to own origin only
- [ ] Pydantic validation on every POST/PATCH route
- [ ] Error monitoring: unhandled exceptions captured with request context
- [ ] DB backups: `fly postgres backup list` shows automatic daily backups
- [ ] `robots.txt` honored at request time in every scraper
- [ ] `MAX_DRAFTS_PER_DAY` enforced in service layer with passing test
- [ ] No LinkedIn scraping; no form auto-submission anywhere in codebase

Any unchecked item → Phase C is not done.

## Phase-start protocol (Coordinator)

When user says *"begin Phase X"*:

1. Read `docs/plan/_contract.md` (this file) + `docs/plan/phase-{x}.md` in full.
2. Read `AGENTS.md` — identify phase agents.
3. In ONE message emit:
   - `mcp__ruv-swarm__swarm_init(...)` with `maxAgents` from the phase file.
   - One `Task(...)` per agent per the phase file. Each Task prompt includes: agent scope from `AGENTS.md`, phase goal from the phase file, hook instruction (`npx ruflo hooks pre-task` before, `npx ruflo hooks post-edit` after each edit).
   - `TodoWrite({ todos: [<one per step in the phase>] })`.
4. Begin step 1 of the phase.
