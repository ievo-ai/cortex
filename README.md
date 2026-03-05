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
├── tests/              # Build script tests
└── .github/
    └── workflows/
        └── release.yml # CI: tag push → build → GitHub Release asset
```

## Template variables

The `src/kernel/iEVO.md.j2` template supports the following variables:

| Variable | Type | Source | Example |
|----------|------|--------|---------|
| `cortex_version` | string | `--tag` CLI argument | `"v1.2.0"` |
| `provider` | string | set per render pass | `"claude"`, `"codex"` |

Provider-specific blocks use Jinja2 conditionals:

```jinja2
{% if provider == "claude" %}
Claude Code-specific content here.
{% endif %}
```

## Release assets

Each GitHub Release includes `cortex-<tag>.tar.gz` containing:

```
cortex-<tag>.tar.gz
├── claude/             # Claude Code artifacts (.md agent files, iEVO.md)
│   ├── iEVO.md         # Rendered from src/kernel/iEVO.md.j2 (provider="claude")
│   └── agents/
│       └── *.md
└── codex/              # OpenAI Codex artifacts
    ├── iEVO.md         # Rendered from src/kernel/iEVO.md.j2 (provider="codex")
    └── BUILD_TARGET.md
```

## Building locally

```bash
python build.py --tag v1.0.0
# Output: dist/cortex-v1.0.0.tar.gz
```

## Running tests

```bash
pytest tests/
```

## Dependencies

- `pyyaml` — YAML parsing for agent templates
- `jinja2>=3.1` — template rendering for `src/kernel/iEVO.md.j2`

## Integration

The iEvo CLI downloads and unpacks the latest release asset:

```bash
ievo init          # Downloads latest Cortex release automatically
ievo cortex build  # Rebuild locally from source (power-user path)
```

See: [ievo-ai/cli](https://github.com/ievo-ai/cli)
