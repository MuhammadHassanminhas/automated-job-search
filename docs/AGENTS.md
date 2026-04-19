# AGENTS — Swarm Roster

Two swarm configurations. Spine uses 4 agents. Expansion spawns 2 more specialists when scope genuinely requires them.

**Invocation rule:** `swarm_init` and all `Task(...)` spawns in ONE message → parallel execution. Never spawn serially.

---

## Spine swarm (Phase A)

Spawn when Phase A starts:

```
mcp__ruv-swarm__swarm_init({ topology: "hierarchical", maxAgents: 4, strategy: "specialized" })

Task("Coordinator", "<§1 + Phase A goal + hook instr>", "hierarchical-coordinator")
Task("Builder",     "<§2 + Phase A goal>",              "coder")
Task("Tester",      "<§3 + Phase A goal>",              "tester")
Task("Reviewer",    "<§4 + Phase A goal>",              "reviewer")

TodoWrite({ todos: [<one per Phase A step>] })
```

## Expansion swarm (Phase B onward)

When Phase B starts, spawn two more — do NOT re-spawn the existing four, they persist:

```
Task("ML Specialist",       "<§5 + Phase B goal>", "coder")
Task("Frontend Specialist", "<§6 + Phase B goal>", "coder")
```

Now 6 agents. Builder's scope narrows to backend + scrapers per the ownership table.

---

## Roles

### §1 Coordinator (`hierarchical-coordinator`)
Tracks phase state. Routes work. Owns memory namespace `swarm/intel/*`. Enforces checkpoints — blocks progress on failed tests or dead-code hits. **Writes no code.** Kills and reassigns any worker caught doing another's job.

### §2 Builder (`coder`)
**Phase A:** writes every implementation file — scrapers, ranker, generator, backend, the minimal UI pages. **Phase B+:** scope narrows to `app/scrapers/**`, `app/api/**`, `app/models/**`, `app/schemas/**`, `app/services/**`, `app/auth/**`, `migrations/**`, `app/main.py`.

### §3 Tester (`tester`)
Writes failing tests FIRST, always. Never writes application code — ever.

Test rules (reviewer enforces):
- ≥1 `hypothesis` property-based test per module.
- `polyfactory` factories for every model.
- Parameterized edge cases: empty, null, unicode, max-length, malformed, duplicate.
- HTTP mocked with `respx` (Python) / `msw` (TS). No live calls in tests.
- Tests whose only assertion is `== <hardcoded literal>` → rejected.

Owns `tests/**`, `web/tests/**`.

### §4 Reviewer (`reviewer`)
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

### §5 ML Specialist — Phase B+ (`coder`)
Owns `app/llm/**`, `app/ranker/**`, `app/generator/**`, `app/generator/prompts/**`. Builds the LLM judge stage, Gemini failover, prompt caching, and the full generator suite.

### §6 Frontend Specialist — Phase B+ (`coder`)
Owns `web/**`. In Phase A, Builder produces the minimal UI; Specialist takes over in Phase B for polish (shadcn, loading states, optimistic updates, drag-drop tracker).

---

## Path ownership (enforced)

| Path | Spine owner | Expansion owner |
|---|---|---|
| `docs/ARCHITECTURE.md`, `docs/adr/*` | Coordinator writes ADRs | same |
| `app/scrapers/**`, `app/api/**`, `app/models/**`, `app/schemas/**`, `app/services/**`, `app/auth/**`, `migrations/**`, `app/main.py` | Builder | Builder |
| `app/llm/**`, `app/ranker/**`, `app/generator/**` | Builder | ML Specialist |
| `web/**` | Builder | Frontend Specialist |
| `tests/**`, `web/tests/**` | Tester | Tester |
| Rule-6 scans, PR reviews | Reviewer | Reviewer |

Commit touches a path → only that path's owner produced it. Reviewer rejects violations.

---

## Hooks (Ruflo pre-configures in `.claude/settings.json`)

| Hook | Purpose |
|---|---|
| `pre-task` | load prior memory |
| `post-edit` | run formatter (`ruff format`, `prettier`), log change to memory |
| `post-task` | run step's tests + Rule 6 scan |
| `session-end` | persist state for resume |

Agents never invoke hooks manually. Ruflo runs them.
