# AGENTS — Swarm Roster

Two swarm configurations. Spine uses 4 agents. Expansion spawns 2 more specialists when scope genuinely requires them.

**Invocation rule:** ALL `Task(...)` spawns for a phase must go in ONE message so Claude Code runs them in parallel. Never spawn serially, never one-per-message.

---

## Spine swarm (Phase A)

Spawn when Phase A starts:

```
Task("Coordinator", "<§1 prompt + Phase A goal + branch discipline>", "general-purpose")
Task("Builder",     "<§2 prompt + Phase A goal + branch discipline>", "general-purpose")
Task("Tester",      "<§3 prompt + Phase A goal + branch discipline>", "general-purpose")
Task("Reviewer",    "<§4 prompt + Phase A goal + branch discipline>", "general-purpose")

TodoWrite({ todos: [<one per Phase A step: A.1, A.2, A.3, A.4>] })
```

## Expansion swarm (Phase B onward)

When Phase B starts, spawn two more in ONE message — do NOT re-spawn the existing four, they're already active:

```
Task("ML Specialist",       "<§5 prompt + Phase B goal>", "general-purpose")
Task("Frontend Specialist", "<§6 prompt + Phase B goal>", "general-purpose")
```

Now 6 agents active. Builder's scope narrows to backend + scrapers per the ownership table below.

---

## Roles

### §1 Coordinator

Tracks phase state. Routes work between agents. Enforces checkpoints — blocks progress on failed tests or Rule-6 findings. **Writes no implementation code.** Kills and reassigns any worker caught doing another's job.

### §2 Builder

**Phase A:** writes every implementation file — scrapers, ranker, generator, backend, the minimal UI pages. **Phase B+:** scope narrows to `app/scrapers/**`, `app/api/**`, `app/models/**`, `app/schemas/**`, `app/services/**`, `app/auth/**`, `migrations/**`, `app/main.py`.

### §3 Tester

Writes failing tests FIRST, always. Never writes application code — ever.

Test rules (Reviewer enforces):

- ≥1 `hypothesis` property-based test per module.
- `polyfactory` factories for every model.
- Parameterized edge cases: empty, null, unicode, max-length, malformed, duplicate.
- HTTP mocked with `respx` (Python) / `msw` (TS). No live calls in tests.
- Tests whose only assertion is `== <hardcoded literal>` → rejected.

Owns `tests/**`, `web/tests/**`.

### §4 Reviewer

Veto power on every PR. Runs on every step:

```
uv run vulture app tests --min-confidence 80         # → 0 findings
uv run ruff check --select F401,F841,F811 app tests  # → 0 findings
cd web && pnpm dlx knip                              # → 0 findings
grep -rnE "TODO|FIXME|XXX|NotImplementedError|^\s*pass\s*$" \
  app web --include="*.py" --include="*.ts" --include="*.tsx"  # → 0 matches
```

Also verifies: layer boundaries from `ARCHITECTURE.md`, path ownership from the table below, generic-test rule from §3.

Writes no features, tests, or docs.

### §5 ML Specialist — Phase B+

Owns `app/llm/**`, `app/ranker/**`, `app/generator/**`, `app/generator/prompts/**`. Builds the LLM judge stage, Gemini failover, prompt caching, and the full generator suite.

### §6 Frontend Specialist — Phase B+

Owns `web/**`. In Phase A, Builder produces the minimal UI; Specialist takes over in Phase B for polish (shadcn, loading states, optimistic updates, drag-drop tracker).

---

## Path ownership (enforced)

| Path | Spine owner (Phase A) | Expansion owner (Phase B+) |
|---|---|---|
| `docs/ARCHITECTURE.md`, `docs/adr/*` | Coordinator writes ADRs | same |
| `app/scrapers/**`, `app/api/**`, `app/models/**`, `app/schemas/**`, `app/services/**`, `app/auth/**`, `migrations/**`, `app/main.py` | Builder | Builder |
| `app/llm/**`, `app/ranker/**`, `app/generator/**` | Builder | ML Specialist |
| `web/**` | Builder | Frontend Specialist |
| `tests/**`, `web/tests/**` | Tester | Tester |
| Rule-6 scans, PR reviews | Reviewer | Reviewer |

Commit touches a path → only that path's owner may have produced it. Reviewer rejects violations.

---

## Coordination (no Ruflo, no shared swarm memory)

- Coordination is via **git branches** (`step/<id>/tests`, `step/<id>/impl`), **TodoWrite** (visible to all agents), and **direct Task prompts** (each agent receives its scope + goal at spawn time).
- State does NOT persist across Claude Code sessions. At session resume, state is reconstructed from git log + branch list + last TodoWrite output.
- If an agent needs information from another agent, Coordinator relays via the next Task spawn — agents do not communicate directly.
