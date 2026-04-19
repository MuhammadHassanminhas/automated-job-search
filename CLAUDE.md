# CLAUDE.md — Internship Intel

Master instruction set. Read fully before any action. Re-read on confusion. This file wins all conflicts.
If this file conflicts with `docs/ARCHITECTURE.md` / `docs/AGENTS.md` / `docs/plan/*` → **stop, ask user**.

## Mission

Ship an end-to-end, production-grade, ethically-constrained pipeline that discovers AI/ML + software engineering internship postings (Pakistan + remote-global), ranks them against the user's profile via a 3-stage funnel, drafts tailored resume/cover letter/cold email, presents for approval, sends approved via Gmail, tracks outcomes.

Target user: student in Pakistan. Three phases: **A (spine)**, **B (expansion)**, **C (deploy)**.

## The Six Rules (non-negotiable)

1. **Complete coverage.** Every module named in `docs/ARCHITECTURE.md` is real, wired, callable by the end of its phase. No stubs.
2. **Agentic via Ruflo.** At phase start, emit `mcp__ruv-swarm__swarm_init` + every `Task(...)` spawn + `TodoWrite` in **one message** per `docs/AGENTS.md`. Spine uses 4 agents; expansion adds 2. Non-overlap per ownership table — reviewer enforces.
3. **Clarity.** Numbered steps. Concrete verbs. Instructions in user-facing verification scripts must be copy-pasteable with exact expected output.
4. **Strict TDD.** Tester writes failing test on `step/<id>/tests` → **observe red** → Builder writes minimal impl on `step/<id>/impl` → **observe green**. Tests generic: `hypothesis` property-based, `polyfactory` factories, parameterized edges (empty/null/unicode/max-length/malformed). Hardcoded-only assertions → reject. Zero implementation before a failing test exists.
5. **Live checkpoints.** At each CHECKPOINT: stop, print ID, give verification script with exact expected output, wait for `approved`. Never infer approval. On `rejected <reason>` → roll back, fix, re-present. Auto-advance only after 24h silence AND tests+Rule-6 green (commit tagged `UNVERIFIED`).
6. **Zero dead code.** Reviewer scan blocks every checkpoint:
   - `uv run vulture app tests --min-confidence 80` → 0
   - `uv run ruff check --select F401,F841,F811 app tests` → 0
   - `cd web && pnpm dlx knip` → 0
   - `grep -rnE "TODO|FIXME|XXX|NotImplementedError|^\s*pass\s*$" app web --include="*.py" --include="*.ts" --include="*.tsx"` → 0
   Every import used, every function called, every component rendered, every route reachable. Not wired = delete.

## Phase start protocol

When user says *"begin Phase X"*:

1. Read `docs/plan/_contract.md` + `docs/plan/phase-{x}.md` in full. Do NOT load other phase files.
2. Read `docs/AGENTS.md` — identify phase agents.
3. In ONE message, emit:
   - `mcp__ruv-swarm__swarm_init(...)` with `maxAgents` from the phase file.
   - One `Task(...)` per agent. Each Task prompt contains: (a) agent scope from `AGENTS.md`, (b) phase goal from the phase file, (c) hook instruction: *"Run `npx ruflo hooks pre-task` before you start and `npx ruflo hooks post-edit` after each file change."*
   - `TodoWrite({ todos: [<one per step in phase>] })`.
4. Begin step 1.

## Per-step protocol

Defined in `docs/plan/_contract.md`. Read it once per session. Follow verbatim.

## Reading order on session start

1. This file.
2. `docs/ARCHITECTURE.md` — what you are building.
3. `docs/AGENTS.md` — roster + ownership.
4. `docs/plan/_contract.md` — execution contract + Definition-of-Done.
5. `docs/plan/phase-{active}.md` — ONLY the currently active phase.
6. `docs/OPS.md` — when things break.

Two docs disagree → stop, ask user.

## Hooks (Ruflo pre-wires via `npx ruflo@latest init`)

| Hook | Purpose |
|---|---|
| `pre-task` | load memory |
| `post-edit` | format + log change |
| `post-task` | run step tests + Rule-6 |
| `session-end` | persist state |

Never invoke hooks manually. Ruflo runs them.
