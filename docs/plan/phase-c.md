# plan/phase-c.md — PRODUCTION (1–2 days)

**Goal:** live on internet at `internship-intel.fly.dev`. HTTPS. Secrets managed. DoD checklist in `_contract.md` fully green.

**Swarm:** Coordinator + Builder + Reviewer (3 agents). No new application code — only deploy config.

---

## C.1 — Deploy

**Tests:**
- `hadolint Dockerfile web/Dockerfile` → zero errors.
- Image sizes: `docker images` — app ≤500MB, web ≤300MB. Asserted via shell test in CI.
- `fly.toml` parse test: required keys present (`app`, `primary_region`, `release_command`, `[http_service]`, `[[services.ports]]`).
- Secrets checklist: shell script asserts `fly secrets list --app internship-intel` output contains every key from the `.env.example` non-default list.
- Prod smoke: `curl -s https://internship-intel.fly.dev/health | jq .status` → `"ok"`.

**Build:**
- `Dockerfile` — multi-stage: builder (`uv sync --no-dev`) → slim runtime. Non-root user. Healthcheck.
- `web/Dockerfile` — multi-stage: `pnpm build` → Next.js standalone output runtime.
- `fly.toml` for app — `release_command = "alembic upgrade head"`, internal port 8000, primary region `sin`, memory 512MB, `[http_service.concurrency]` hard=25 soft=20.
- `web/fly.toml` — similar, port 3000.
- `scripts/deploy.sh` — one-command deploy of both services.

**CHECKPOINT C.1 (FINAL):**
```
./scripts/deploy.sh
curl -s https://internship-intel.fly.dev/health | jq .
```
Expected: `{"status":"ok","db":"ok","version":"..."}`.

Open the URL in browser. Log in. Run the full A.4 flow on live HTTPS:
1. `/inbox` shows jobs (scheduler has fired at least once).
2. Generate a draft.
3. Approve.
4. Wait for send (or trigger manually via `/outbox`).
5. Receive email at alt address with `resume.pdf` attachment.
6. `/tracker` drag-drop persists.

Reviewer walks the **Production Definition-of-Done** in `_contract.md`. Every box must check.

→ `approved` — **project complete.**

---

## Phase C integration test

`tests/phase_c_integration.py` runs against the live fly.dev URL:
- `/health` returns 200.
- `/api/auth/me` without cookie → 401.
- DB migration version (queried via `fly postgres connect`) matches local `alembic current`.
- All Rule-6 scans green against the deployed image (run inside the app container via `fly ssh console`).

Must pass. Then tag release `v1.0.0`.
