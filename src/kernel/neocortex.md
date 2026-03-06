## Neocortex — Best Practices

Proven practices derived from real sessions — apply these by default.

> New practices discovered during sessions go to `.ievo/evolution/KERNEL.md`, not here. See `EVOLUTION.md` for the full evolution convention.

### Requirements & Backlog

- **Discussion starts as idea**: every new requirement begins as a task with `status: idea` via `/idea`, never directly as a ready spec. The spec.md is a living document — it grows through research, interview, and architect assessment until spec-writer promotes it to `ready` with user approval.
- **Always record WHY**: every decision made during discussion must be logged with context — what options were considered, why this one was chosen, who decided. Log to IDEA file or `.ievo/memory/DECISIONS.md`. Without a decision log, context is lost within days and no one remembers why things were done a certain way.
- **Backlog revival requires full context reload**: when an idea returns from backlog after weeks, always load its discussion log and run a context refresh — what has changed since then, is the original approach still valid?
- **New requirements during discussion → new task**: if a new requirement emerges during spec elicitation, capture it as a separate task (`/idea`) immediately. Do not graft it onto the current task's scope without explicit user approval.

### Research

- **Verify before trusting research findings**: always check that GitHub repos, star counts, and project names found in research are real. Researchers can hallucinate project names. Apply the "can I open this URL?" test. Flag unverified items with `⚠️ TODO: verify`.
- **Study adjacent ecosystems**: before building something, check if OpenClaw, IronClaw, Lobster, or similar projects already solved it. Reference implementations save months.
- **Persist research findings in `.ievo/research/`**: raw research output belongs in `.ievo/research/YYYY-MM-DD-<topic>.md`, not in task specs or session logs. Task specs reference research files — they don't contain raw findings. Update `INDEX.md` in `.ievo/research/` after every new research file. Format: `findings / comparing A vs B and why / conclusion / final decision and why`.

### Pipeline Design

- **Deterministic engine over LLM routing**: pipeline stage transitions must be driven by a deterministic workflow engine (YAML state machine), not by LLMs deciding what to do next. LLMs are unreliable routers — they misinterpret iteration counts and forget to signal transitions.
- **Hard gates between stages**: every pipeline stage has explicit entry conditions and exit artifacts. The next stage agent checks entry conditions before starting. No stage can claim completion without producing its required artifact.
- **Judge/gate agent is non-bypassable**: the judge that promotes a REQ from draft to ready cannot be skipped. If a stage's artifact is missing or invalid, the pipeline stops — it does not proceed with assumptions.

### Security

- **LLM sees credential names, never values**: inject only the list of available credential names into agent context. Actual values are resolved by the security layer at tool execution time and never appear in LLM reasoning.
- **LiteLLM proxy for API keys**: run a LiteLLM proxy on the host. Docker containers receive a fake API key + proxy base URL. The proxy adds real auth headers. Even `echo $ANTHROPIC_API_KEY` in the container returns a useless placeholder.
- **Shell wrapper over PTY bridge for credential injection**: replace `/bin/bash` inside Docker with `ievo-bash`. Intercept credential references at shell execution level — not at PTY stream level. PTY bridge fails during model thinking phases; shell wrapper fires on every actual tool execution regardless of model state.
- **Scan tool output for leaks**: PostToolUse hook (or shell wrapper post-exec) scans every tool output for credential patterns before returning it to the LLM.

### PR Review Methodology

All agents that review PR changes follow this protocol:

1. **Get changed files locally** — never use `gh pr diff` (GitHub has a 20 000-line limit):
   ```bash
   git fetch origin <branch>
   git diff main...<branch> --name-only
   ```

2. **Read each changed file by size**:
   - File < 300 lines → read the full file (`Read` tool)
   - File ≥ 300 lines → `git diff -U40 main...<branch> -- <file>` (40 lines context each side)

3. **Group files by module** before reviewing — understand the structure before diving into individual files

4. **Never review a raw diff alone** — a diff without surrounding context hides intent. When a single line changed, read at least the enclosing function.

### Agent & App Design

- **One agent, one responsibility**: each agent has exactly one job. Do not combine review, verification, and acceptance into one agent — split them. When an agent's description requires "and", it is two agents. Single-responsibility agents are independently replaceable, testable, and evolvable.
- **Apps > agents for end-to-end workflows**: when a use case requires multiple agents working together, package them as an iEvo App (agents + pipeline + MCP) rather than shipping loose agents. Users get a working system, not parts to wire manually.
- **One pipeline engine, many providers**: pipeline YAML is provider-agnostic. The same workflow runs whether agents execute on Claude, Codex, Ollama, or a mix. Provider selection lives in UAF agent config, not in pipeline logic.
- **Native CLI passthrough**: never replace the native provider CLI (Claude Code, Codex). Wrap it transparently via PTY bridge. Users keep full native access; iEvo adds orchestration on top.
