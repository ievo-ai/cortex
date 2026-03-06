# Cortex Architecture

## 1. Overview

Cortex is the iEvo kernel source repository. It stores provider-agnostic agent
templates, skills, and pipeline conventions as Jinja2-templated YAML source and
compiles them into provider-specific release artifacts at build time. The primary
consumer is the iEvo CLI, which downloads the latest Cortex release asset via
HTTPS during `ievo init` and unpacks it into the project's `.ievo/` directory.

## 2. Module Structure

The `cortex/` Python package contains:

| Module | Responsibility |
|--------|---------------|
| `cortex/__init__.py` | Re-exports `__version__` from `version.py` |
| `cortex/version.py` | CalVer version string (`__version__`). Static `"0.1.0"` in source; `scripts/version_bump.py` overwrites it with a timestamp string on each CI release. |
| `cortex/cli.py` | Typer application with three commands: `compile`, `validate`, `dev`. Imports from `compile.py` and `version.py`. |
| `cortex/compile.py` | Core compilation logic: template rendering, provider artifact assembly, tarball creation, link validation. |

## 3. Source Templates (`src/`)

```
src/
├── kernel/
│   ├── iEVO.md.j2      # Jinja2 template — provider-agnostic pipeline conventions
│   └── iEVO.yaml       # Kernel source data (YAML, unused in v1 rendering pipeline)
├── agents/
│   └── spec-writer.yaml # Agent template source (YAML)
└── skills/
    └── backlog.yaml     # Skill template source (YAML)
```

The `iEVO.md.j2` template accepts one variable:

| Variable | Type | Source | Example |
|----------|------|--------|---------|
| `cortex_version` | string | CLI `__version__` or `"dev"` literal | `"26.03.06.1200"` |

The `.yaml` sources under `agents/` and `skills/` define the canonical agent/skill data.
In v1, `build_claude_target()` uses a hardcoded template string (`CLAUDE_AGENT_MD`);
future versions will load these YAML sources directly.

## 4. Compile Pipeline

Data flow through the compile pipeline:

```
src/kernel/iEVO.md.j2
  └──render_template()──► dist/iEVO.md          (provider-agnostic, tarball root)

CLAUDE_AGENT_MD (hardcoded v1)
  └──build_claude_target()──► dist/claude/agents/*.md   (Claude Code format)
(placeholder)
  └──build_codex_target()──►  dist/codex/BUILD_TARGET.md (placeholder, IDEA-005)

dist/iEVO.md
dist/claude/
dist/codex/
  └──create_tarball()──► dist/cortex-<tag>.tar.gz
```

`build()` is the orchestrator: it calls `build_claude_target()`,
`build_codex_target()`, `render_ievo_md()`, and `create_tarball()` in sequence.
It does NOT call `validate_links()` — that is the CLI layer's responsibility.

## 5. CLI Commands

| Command | Purpose | Tag value | Link validation |
|---------|---------|-----------|-----------------|
| `cortex compile` | Full release build | `__version__` (CalVer) | Yes, unless `--skip-validate` |
| `cortex validate` | Standalone lychee check on existing `dist/` | n/a | Yes |
| `cortex dev` | Development build, optional `--watch` | `"dev"` literal | No |

`compile` and `dev` both call `build()`. The `--watch` flag on `dev` uses
`watchfiles` to monitor `src/` for changes and triggers `build()` on each change.
`validate` calls `validate_links()` directly without recompiling.

## 6. Provider Targets

| Provider | Directory | Format | Status |
|----------|-----------|--------|--------|
| `claude` | `dist/claude/agents/*.md` | Markdown with YAML frontmatter (Claude Code agent format) | Implemented |
| `codex` | `dist/codex/BUILD_TARGET.md` | Placeholder — format TBD | Placeholder (IDEA-005) |

`iEVO.md` sits at the tarball root, shared across all providers. This placement
is a breaking change from the earlier layout where each provider directory had
its own copy (see `REQ-004` comment in `compile.py`).

## 7. Version Scheme

- **Format:** CalVer `YY.MM.DD.HHMM` (2-digit year, e.g. `"26.03.06.1200"`)
- **Local source:** `cortex/version.py` contains a static string (currently `"0.1.0"`)
- **CI release:** `scripts/version_bump.py` overwrites `cortex/version.py` with the
  current timestamp before `hatchling` builds the package. The published package
  carries the CalVer string; the source file always reads `"0.1.0"` between releases.
- **Dev builds:** the `dev` CLI command passes the literal string `"dev"` as the tag
  so dev artifacts are never confused with release artifacts.

## 8. CI Pipelines

| Workflow | Trigger | Steps |
|----------|---------|-------|
| `test.yml` | Push + PR on `main` | Lint (ruff) → Test (pytest) |
| `release.yml` | Push to `main` | Lint → Test → Version bump → `cortex compile --skip-validate` → Install lychee → `lychee` link validation → `uv build` → PyPI publish (OIDC) → GitHub Release with `dist/*` |

Release pipeline separation: `cortex compile` runs with `--skip-validate` so the
Python-managed compile step is independent of the Rust `lychee` binary. Lychee
runs as a separate CI step immediately after.

### PyPI Publishing — OIDC Trusted Publisher

The release workflow publishes to PyPI as `ievo-cortex` using the
[PyPI trusted publisher](https://docs.pypi.org/trusted-publishers/) mechanism (OIDC).
This replaces long-lived API token (`PYPI_TOKEN`) with GitHub's short-lived OIDC
identity token — no secrets to manage.

**Workflow configuration:**
- Action: `pypa/gh-action-pypi-publish@release/v1`
- Permission: `id-token: write` (OIDC) + `contents: write` (GitHub Release)
- No `PYPI_TOKEN` secret required

**PyPI trusted publisher setup (manual, one-time):**
1. Go to https://pypi.org/manage/account/publishing/
2. Create a pending publisher with:
   - PyPI project name: `ievo-cortex`
   - Owner: `ievo-ai`
   - Repository: `cortex`
   - Workflow name: `release.yml`
   - Environment: _(leave blank)_
3. The first successful workflow run auto-creates the `ievo-cortex` project on PyPI.

**Package naming:** The PyPI distribution name (`ievo-cortex`) differs from the Python
import name (`cortex`). The `cortex/` source directory is unchanged — `import cortex`
continues to work. Only the `[project] name` in `pyproject.toml` was renamed.

## 10. Brain Regions — Kernel Architecture

The kernel (iEVO.md) is decomposed into functional regions inspired by the human brain.
Each region is a separate `.md` file in `src/kernel/`. The master template
`consciousness.md.j2` assembles them into a single consciousness file via
Jinja2 `{% include %}`.

### Region Map

| Region | File | Responsibility | Brain Analogy |
|--------|------|---------------|---------------|
| **Brainstem** | `brainstem.md` | Directory structure, task statuses, file naming conventions — the survival layer | Autonomic functions — without this, the system is dead. Like the biological brainstem regulates heartbeat and breathing, this region defines the minimal structure every agent needs to operate |
| **Instincts** | `instincts.md` | Hardwired reflexes — challenge requirements first, flag tech debt on sight, verify before recording | Amygdala-driven fight-or-flight — unconditional responses that fire before deliberation. In cognitive architectures (ACT-R, SOAR), these map to **production rules** with highest utility |
| **Limbic System** | `limbic.md` | Pipeline rules, merge strategy, commit format, branch naming, PR workflow — habitual procedures | Basal ganglia + cerebellum — procedural memory. Automatic sequences executed the same way every time. In SOAR terms: **operator proposals** that always win because they've been reinforced |
| **Neocortex** | `neocortex.md` | Best practices, proven patterns, architectural knowledge — accumulated experience | Declarative long-term memory. In ACT-R: **chunks in declarative memory** with high activation from repeated retrieval. Knowledge that was learned, not hardwired |
| **Prefrontal Cortex** | `prefrontal.md` | Evolution conventions, self-improvement rules, meta-learning — controls how other regions change | Executive function — the region that monitors and modifies other regions. In Global Workspace Theory (LIDA): the **attention codelet** that selects what enters consciousness. This is the only region aware of the evolution pipeline |
| **Working Memory** | `sessions.md` | Session conventions, plan.md/log.md format, context loading rules — short-term state | Prefrontal working memory buffer — limited capacity, refreshed each session. In ACT-R: the **goal buffer** and **imaginal buffer** that hold current task state |

### Design Principles

- **Each region file is plain markdown** — no Jinja syntax. Only `consciousness.md.j2`
  contains Jinja directives (`{% include %}` and `{{ cortex_version }}`).
- **Regions are self-contained** — each starts with its own H2 heading
  (`## Brainstem — Structure & Conventions`).
- **Order matters** — brainstem loads first (survival), instincts second (reflexes),
  then habits, knowledge, meta-learning, and finally working memory. This mirrors
  biological priority: brainstem > limbic > cortex.
- **Evolution targets regions** — when a lesson is learned, it is classified into
  the appropriate region file. Classification criteria:
  - Does it define structure? → Brainstem
  - Is it an unconditional reflex? → Instincts
  - Is it a repeatable procedure? → Limbic
  - Is it learned knowledge? → Neocortex
  - Is it about how to learn/evolve? → Prefrontal
  - Is it about session workflow? → Working Memory

### Cognitive Architecture References

The brain metaphor is grounded in established cognitive architectures:

- **ACT-R** (Adaptive Control of Thought—Rational): hybrid system with declarative
  memory (chunks), procedural memory (productions), and buffers. Our
  brainstem/instincts ≈ productions, neocortex ≈ declarative chunks,
  working memory ≈ buffers.
- **SOAR** (State, Operator And Result): continuous decision cycle with a goal stack.
  Our limbic ≈ default operator preferences, prefrontal ≈ impasse resolution and
  chunking (learning).
- **LIDA/Global Workspace Theory**: perception → understanding → attention
  (consciousness) → action. Our compile pipeline mirrors this: read regions →
  assemble → produce single consciousness file → agent consumes it.

## 11. Mutation Validation Pipeline (planned)

Mutations can degrade the kernel. Every mutation must pass a cognitive benchmark before
being accepted. The pipeline:

```
cortex mutate "lesson"
  → applies change to brain region file in src/kernel/
  → cortex compile (new consciousness)
  → run cognitive benchmark suite (SWE-bench-like for kernel quality)
  → compare scores against baseline
  → IF scores >= baseline → git commit (mutation accepted)
  → IF scores < baseline  → git checkout (mutation rejected, rolled back)
```

**Benchmark dimensions (planned):**
- Task completion rate — can agents following the mutated kernel complete standard tasks?
- Instruction adherence — does the kernel produce correct agent behavior?
- Regression detection — do previously passing scenarios still pass?

**Baseline tracking:**
Each accepted mutation records its benchmark scores in the repo. The baseline is the
score of the last accepted mutation. This creates a monotonically improving kernel —
mutations can only be additive to cognitive capability, never degrading.

**Relation to Curator (task 019):**
The Curator aggregates mutation candidates from across projects. The validation pipeline
is the gate that decides whether a candidate becomes permanent. Curator proposes,
validation pipeline disposes.

## 9. Dependencies

| Category | Packages |
|----------|---------|
| Runtime | `pyyaml`, `jinja2>=3.1`, `typer>=0.15.0` |
| Dev (extra) | `pytest`, `ruff`, `mypy`, `pytest-cov`, `watchfiles>=1.0.0` |
| CI-only | `lychee` (Rust binary, installed via GitHub Actions curl step — not a Python dep) |
| Build system | `hatchling` |

All Python dependencies are declared in `pyproject.toml` and managed by `uv`.
