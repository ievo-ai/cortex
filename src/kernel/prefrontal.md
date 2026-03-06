## Prefrontal Cortex — Evolution & Meta-Learning

Project-specific lessons accumulate in `.ievo/evolution/` and are loaded as context at each session start. The evolution system has three components:

- **`LOG.md`** — append-only findings journal written by the Evolution agent. Write-only: agents do not load this as context.
- **`KERNEL.md`** — kernel overlay for pipeline-level lessons (naming conventions, document lifecycle, cross-agent coordination). Read by all agents at session start.
- **`agents/<agent>.md`** — per-agent overlay for agent-specific lessons. Read by that agent at session start.

```
Finding in agent behavior        → LOG.md + agents/<agent>.md
Finding in pipeline conventions  → LOG.md + KERNEL.md
All findings                     → curator GitHub issue
```

Read `EVOLUTION.md` for full convention — entry formats, routing rules, context loading template.
