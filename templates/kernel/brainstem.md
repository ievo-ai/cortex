## Brainstem — Structure & Conventions

### Directory Structure

```
.ievo/
├── version           # CLI version that last updated this project
├── iEVO.md           # This file — pipeline context overlay
├── config.yaml       # Project settings
├── tasks/            # All work items — unified lifecycle
│   ├── _index.csv    # Generated cache for fast grep (id,title,type,status,priority,deps,pr,updated)
│   └── NNN/          # Task directory (sequential ID: 001, 002, ...)
│       ├── spec.md   # Single file: frontmatter + context + ACs + plan + questions + history
│       ├── reports/   # qa.md, review.md, acceptance.md (written by review agents)
│       └── subtasks/  # Architect-created work units, assigned by team-lead
│           └── NN/
│               └── spec.md  # Subtask: frontmatter (parent, status, assigned, deps) + what/tests/files + history
├── sessions/         # Work sessions (cross-task)
│   ├── _index.csv    # Session index (id,date,agent,tasks,status,summary)
│   └── NNN/
│       ├── plan.md   # Intent — written BEFORE work starts
│       └── log.md    # Reality — written during and after work
├── evolution/        # Evolution log + overlays (see EVOLUTION.md)
│   ├── LOG.md        # Append-only findings journal (write-only)
│   ├── KERNEL.md     # Kernel overlay — pipeline-level rules (read by all agents)
│   └── agents/       # Per-agent overlays
│       └── <agent>.md
└── memory/           # Shared project memory
    ├── CONTEXT.md    # Project state, entities, architecture
    ├── DECISIONS.md  # Append-only decision log
    ├── VOCABULARY.md # Domain terms and definitions
    └── HISTORY.md    # Legacy session index (migrating to sessions/_index.csv)
```

### Task Statuses

```
idea → ready → planned → plan-approved → in_progress → review → done | blocked
                                              ↑            |
                                              └── reject ──┘
```

- `idea` — raw thought, no acceptance criteria yet
- `ready` — spec written, user approved, waiting for architect
- `planned` — ## Plan section written in spec.md, waiting for architect-reviewer
- `plan-approved` — plan reviewed and approved, team-lead can implement
- `in_progress` — draft PR open, internal pipeline running (direction → code → QA → acceptance). CI does NOT trigger
- `review` — acceptance PASS, PR marked ready for review, CI triggers, waiting for user
- `done` — user approved and merged
- `blocked` — waiting on question answer or dependency

**Reject flow:** user rejects PR → PR back to draft → status `in_progress` → team-lead fixes → acceptance re-verifies → PR ready for review again → status `review`

### Naming Conventions

| Type | Pattern | Location |
|------|---------|----------|
| Task (all-in-one) | `spec.md` | `.ievo/tasks/NNN/` |
| Subtask (all-in-one) | `spec.md` | `.ievo/tasks/NNN/subtasks/NN/` |
| QA report | `qa.md` | `.ievo/tasks/NNN/reports/` |
| Code review | `review.md` | `.ievo/tasks/NNN/reports/` |
| Acceptance report | `acceptance.md` | `.ievo/tasks/NNN/reports/` |
| Acceptance revision | `acceptance-rN.md` | `.ievo/tasks/NNN/reports/` |
| Task index | `_index.csv` | `.ievo/tasks/` |
| Session plan | `plan.md` | `.ievo/sessions/NNN/` |
| Session log | `log.md` | `.ievo/sessions/NNN/` |
| Session index | `_index.csv` | `.ievo/sessions/` |
| Decision | `D-NNN` (entry in file) | `.ievo/memory/DECISIONS.md` |
| Experience log | `EXP.md` | `.ievo/` |
| Evolution log | `LOG.md` | `.ievo/evolution/` |
| Kernel overlay | `KERNEL.md` | `.ievo/evolution/` |
| Agent overlay | `<agent>.md` | `.ievo/evolution/agents/` |
