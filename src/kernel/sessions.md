## Working Memory — Sessions

A **session** is one episodic work unit — one sitting, one goal. Sessions can span multiple tasks.

### Structure

```
.ievo/sessions/
├── _index.csv    # id,date,agent,tasks,status,summary
└── NNN/
    ├── plan.md   # Intent — written BEFORE work starts
    └── log.md    # Reality — written during and after work
```

- **`plan.md`** — goals, phases, decisions to make, files to create/modify. Recovery document.
- **`log.md`** — what was actually built, artifacts created/modified, commits, errors.

### Session statuses

```
planned → in_progress → completed
```

### Rules

- **Plan first**: write `plan.md` BEFORE starting implementation. No plan = no recovery if context is lost.
- **Incremental updates**: update `plan.md` and `log.md` after each phase completes — don't wait until session end.
- **Sequential numbering**: 001, 002, 003... Never skip numbers.
- **One session = one goal**: if the goal shifts significantly, start a new session.
- **Record experience in real time**: when something is learned — a mistake, a discovery, a pattern — append it immediately to `.ievo/EXP.md`. Don't wait for session end (session may never end cleanly). Write as it happens. This is raw experience — unprocessed, unfiltered. Format:
  ```
  ## YYYY-MM-DD: <short title>
  - **What worked:** <pattern/approach that proved effective — and WHY>
  - **What didn't:** <approach that failed or caused rework — and WHY>
  - **Discovered:** <new insight, tool, convention worth remembering>
  - **For next time:** <concrete action to take in similar situations>
  ```
  Not every entry needs all four fields — write what's relevant.

### Cross-Linking

#### Sessions → Tasks (strong, required)

`log.md` MUST list tasks worked on:

```markdown
## What was done
- Tasks: 001 (spec → ready), 002 (arch written), 003 (idea captured)
- Decisions: D-007, D-008
- Commits: abc1234, def5678
```

Experience is logged in real time to `.ievo/EXP.md`, not in session logs.

#### Tasks → Sessions (weak, via frontmatter)

`spec.md` frontmatter has `created_session: "NNN"` — optional link to originating session.

#### DECISIONS.md — the cross-session decision log

Decisions are referenced by ID (`D-NNN`) from any document:

```markdown
## D-007: Use PostgreSQL for persistence
**Date:** 2026-02-28
**Session:** 001
**Context:** Evaluated SQLite vs PostgreSQL vs MongoDB
**Decision:** PostgreSQL — team expertise, ACID guarantees
**Affects:** tasks 003, 004
```

#### Summary

| Direction | Strength | Example |
|-----------|----------|---------|
| Session → Tasks | **Strong** | `log.md` lists tasks worked on |
| Tasks → Sessions | Weak | `created_session` in frontmatter |
| Any doc → Decisions | **Strong** | "Per D-007, we use PostgreSQL" |
| `_index.csv` → Tasks | **Strong** | Generated from `spec.md` frontmatter |
