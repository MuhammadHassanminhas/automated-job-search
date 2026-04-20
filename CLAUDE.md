# CLAUDE.md — Internship Intel

Master instruction set. Read fully before any action. Re-read on confusion. This file wins all conflicts.
If this file conflicts with `docs/ARCHITECTURE.md` / `docs/AGENTS.md` / `docs/plan/*` → **stop, ask user**.

## Mission

Ship an end-to-end, production-grade, ethically-constrained pipeline that discovers AI/ML + software engineering internship postings (Pakistan + remote-global), ranks them against the user's profile via a 3-stage funnel, drafts tailored resume/cover letter/cold email, presents for approval, sends approved via Gmail, tracks outcomes.

Target user: student in Pakistan. Three phases: **A (spine)**, **B (expansion)**, **C (deploy)**.

## The Six Rules (non-negotiable)

1. **Complete coverage.** Every module named in `docs/ARCHITECTURE.md` is real, wired, callable by the end of its phase. No stubs.
2. **Agentic via Claude Code native sub-agents.** At phase start, spawn every agent the phase needs in ONE message using parallel `Task` tool calls per `docs/AGENTS.md`. Spine uses 4 agents; expansion adds 2. Non-overlap per ownership table — Reviewer enforces. Each Task prompt must include: (a) agent scope from `AGENTS.md`, (b) phase goal, (c) the rule: "commit only to your owned paths; reject cross-ownership work."
3. **Clarity.** Numbered steps. Concrete verbs. Verification scripts must be copy-pasteable with exact expected output.
4. **Strict TDD.** Tester writes failing test on branch `step/<id>/tests` → **observe red** → Owner writes minimal impl on branch `step/<id>/impl` → **observe green**. Tests generic: `hypothesis` property-based, `polyfactory` factories, parameterized edges (empty/null/unicode/max-length/malformed). Hardcoded-only assertions → reject. Zero implementation before a failing test exists on branch and run red.
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
   - One `Task(...)` call per agent required by the phase. Agents MUST be spawned in parallel (single message, multiple Task blocks). Each Task prompt contains: (a) agent scope from `AGENTS.md`, (b) phase goal from the phase file, (c) branch discipline: "Commit tests to `step/<id>/tests`, impl to `step/<id>/impl`. Never write outside your owned paths. Never skip red→green."
   - One `TodoWrite({ todos: [<one per step in phase>] })` call.
4. Begin step 1.

Note: this project does NOT use Ruflo MCP or `mcp__ruv-swarm__*` tools. Those tools are not available. The Task tool (Claude Code's native sub-agent spawn) is the sole coordination mechanism. Agent state does NOT persist across Claude Code sessions — at session resume, re-read phase state from git branches and TodoWrite rather than from swarm memory.

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

## Session lifecycle (Ruflo-free)

- **New session start:** no "memory restore" — git is the source of truth. Run `git log --oneline --all -30` and `git branch -a` to identify last checkpoint state.
- **Session end:** commit all work in progress on a `wip/<step-id>` branch. Never leave uncommitted files across sessions.
- **Recovery:** `git stash list` + `git branch -a` + last TodoWrite state = full picture.
