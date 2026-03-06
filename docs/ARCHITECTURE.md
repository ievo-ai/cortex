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
| `release.yml` | Push to `main` | Lint → Test → Version bump → `cortex compile --skip-validate` → Install lychee → `lychee` link validation → `uv build` → PyPI publish → GitHub Release with `dist/*` |

Release pipeline separation: `cortex compile` runs with `--skip-validate` so the
Python-managed compile step is independent of the Rust `lychee` binary. Lychee
runs as a separate CI step immediately after.

## 9. Dependencies

| Category | Packages |
|----------|---------|
| Runtime | `pyyaml`, `jinja2>=3.1`, `typer>=0.15.0` |
| Dev (extra) | `pytest`, `ruff`, `mypy`, `pytest-cov`, `watchfiles>=1.0.0` |
| CI-only | `lychee` (Rust binary, installed via GitHub Actions curl step — not a Python dep) |
| Build system | `hatchling` |

All Python dependencies are declared in `pyproject.toml` and managed by `uv`.
