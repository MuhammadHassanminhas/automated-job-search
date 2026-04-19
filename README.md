# Internship Intel

AI pipeline: **find internships → rank against your profile → draft tailored resume + cover letter + email → you approve → send via Gmail**. You approve every send. Nothing auto-submits.

Built by Claude Code + Ruflo (ruv-swarm). Three phases, 8 checkpoints, you verify each one.

---

## Prerequisites

1. **Node.js 20+** — check `node --version`. Install from nodejs.org if missing.
2. **Python 3.11+** — check `python3 --version`.
3. **Docker Desktop** — install from docker.com, open it, confirm whale icon in menu bar.
4. **Claude Code** — `npm install -g @anthropic-ai/claude-code` → `claude --version`.
5. **Groq API key** — free at https://console.groq.com → API Keys.
6. **Gemini API key** — free at https://aistudio.google.com/app/apikey.
7. **Gmail account** for sending (App Password setup happens in Phase B).

---

## Launch (5 commands, one at a time)

```bash
cd internship-intel
npx ruflo@latest init
claude mcp add ruflo -- npx -y ruflo@latest mcp start
claude mcp list        # confirm "ruflo" appears. If not → re-run the previous line.
claude
```

Inside Claude Code, type exactly:

```
Read CLAUDE.md. Begin Phase A of docs/BUILD_PLAN.md. Honor the six rules. Spawn the swarm per docs/AGENTS.md. Do not skip verification checkpoints.
```

Claude Code takes over. At every **CHECKPOINT**, it stops and shows a script. You run it. You see the expected output. You type `approved`.

If anything looks wrong → type `rejected <one-line reason>`. Claude Code rolls back and fixes.

---

## What you have

```
internship-intel/
├── README.md        ← you are here
├── CLAUDE.md        ← constitution (Claude Code reads on startup)
└── docs/
    ├── ARCHITECTURE.md    ← system design, data model, optimizations
    ├── AGENTS.md          ← 4-agent spine swarm → 6-agent expansion
    ├── BUILD_PLAN.md      ← 3 phases, 8 checkpoints, TDD at each step
    └── OPS.md             ← runbook + debugging + deploy
```

Everything else (code, tests, migrations, UI) gets created as you progress.

---

## Phase guarantees

- **After Phase A (~3–5 days):** working local CLI + minimal UI. Discovers, ranks, drafts, approves. You can use it as-is.
- **After Phase B (~5–7 days):** polished local web app. 3 sources, LLM judge, Gmail send, tracker, scheduler.
- **After Phase C (~1–2 days):** live on the internet at `internship-intel.fly.dev`. HTTPS, secrets managed, auto-migrations.

Stop after any phase — each is self-contained. No wasted work.

---

## Stop at any time

`Ctrl+C` in Claude Code. State persists via Ruflo `session-end` hook. Next `claude` resumes where you left off.
