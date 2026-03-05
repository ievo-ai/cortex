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
├── iEVO.md             # Rendered from src/kernel/iEVO.md.j2
└── agents/
    └── *.md
```

## Building locally

```bash
python build.py --tag v1.0.0
# Output: dist/cortex-v1.0.0.tar.gz
```

Link validation (`validate_links()`) runs automatically in CI after the build.
Locally, it is skipped if `lychee` is not on `PATH` — no action required for local builds.

## Running tests

```bash
pytest tests/
```

## Dependencies

- `pyyaml` — YAML parsing for agent templates
- `jinja2>=3.1` — template rendering for `src/kernel/iEVO.md.j2`
- `lychee` — Markdown link validator (Rust binary, CI only — not a Python dependency)

## Integration

The iEvo CLI downloads and unpacks the latest release asset:

```bash
ievo init          # Downloads latest Cortex release automatically
ievo cortex build  # Rebuild locally from source (power-user path)
```

See: [ievo-ai/cli](https://github.com/ievo-ai/cli)
