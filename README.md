# Cortex

iEvo kernel source — provider-agnostic agent templates, skills, and pipeline conventions.

## What

Cortex stores the iEvo kernel as Jinja2-templated source and builds provider-specific
artifacts at release time. The iEvo CLI downloads the latest Cortex release asset
via HTTPS during `ievo init`.

## Structure

```
cortex/
├── src/
│   ├── agents/         # Agent YAML templates (provider-agnostic)
│   ├── skills/         # Skill YAML templates
│   └── kernel/
│       └── iEVO.md.j2  # iEVO pipeline conventions — Jinja2 template source
├── build.py            # Build script — renders provider artifacts + creates tarball
│                       #   └── validate_links() — runs lychee on dist/ (CI only)
├── tests/              # Build script tests
└── .github/
    └── workflows/
        └── release.yml # CI: tag push → build → lychee link validation → GitHub Release asset
```

## Template variables

The `src/kernel/iEVO.md.j2` template supports the following variables:

| Variable | Type | Source | Example |
|----------|------|--------|---------|
| `cortex_version` | string | `--tag` CLI argument | `"v1.2.0"` |

Variables are injected into the template using standard Jinja2 syntax:

```jinja2
<!-- cortex {{ cortex_version }} -->
```

## Release assets

Each GitHub Release includes `cortex-<tag>.tar.gz` containing:

```
cortex-<tag>.tar.gz
├── iEVO.md             # Rendered from src/kernel/iEVO.md.j2 (provider-agnostic)
├── claude/             # Claude Code provider artifacts
│   └── agents/
│       └── *.md        # Agent templates rendered for Claude Code
└── codex/              # OpenAI Codex provider artifacts
    └── BUILD_TARGET.md # Placeholder — full templates in future REQs
```

## Building locally

```bash
uv run cortex compile
# Output: dist/cortex-<version>.tar.gz
```

Version is auto-read from package metadata (CalVer) — no `--tag` argument needed.

Link validation runs by default. Add `--skip-validate` for faster local builds when
`lychee` is not installed:

```bash
uv run cortex compile --skip-validate
```

Link validation runs automatically in CI after the build.

## Running tests

```bash
uv run pytest tests/
# With coverage:
uv run pytest tests/ --cov
```

## Dependencies

All dependencies are managed by uv — see `pyproject.toml` for the full list.
Lychee (Markdown link validator) is a Rust binary used in CI only — not a Python dependency.

## Contributing

### Prerequisites

- **uv** (required) — Python package manager and virtualenv tool:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **lychee** (optional) — Markdown link validator. Only needed to run `cortex compile`
  without `--skip-validate`. Link validation runs automatically in CI.

### Quick start

```bash
git clone https://github.com/ievo-ai/cortex
cd cortex
uv sync --extra dev        # installs cortex + pytest + ruff + mypy + watchfiles
uv run cortex dev --watch  # hot-reload on src/ template changes
```

Run tests:
```bash
uv run pytest tests/
```

### Godfather dev mode

When developing cortex templates inside the godfather workspace, you can point
`.ievo/iEVO.md` at the cortex build output so `cortex dev --watch` rebuilds are
immediately picked up by godfather's context.

From the **godfather root**:

```bash
# Point iEVO.md at cortex dev output (live rebuilds)
ln -sf ../repos/cortex/dist/iEVO.md .ievo/iEVO.md

# Restore (points back to CLI-distributed template)
ln -sf ../repos/cli/src/ievo/marketplace/templates/iEVO.md .ievo/iEVO.md
```

Verify the symlink with:
```bash
ls -la .ievo/iEVO.md
```

## Integration

The iEvo CLI downloads and unpacks the latest release asset:

```bash
ievo init          # Downloads latest Cortex release automatically
ievo cortex build  # Rebuild locally from source (power-user path)
```

See: [ievo-ai/cli](https://github.com/ievo-ai/cli)
