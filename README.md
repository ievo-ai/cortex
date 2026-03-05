# Cortex

iEvo kernel source — provider-agnostic agent templates, skills, and pipeline conventions.

## What

Cortex stores the iEvo kernel as YAML-templated source and builds provider-specific
artifacts at release time. The iEvo CLI downloads the latest Cortex release asset
via HTTPS during `ievo init`.

## Structure

```
cortex/
├── src/
│   ├── agents/         # Agent YAML templates (provider-agnostic)
│   ├── skills/         # Skill YAML templates
│   └── kernel/         # iEVO kernel source (iEVO.yaml)
├── build.py            # Build script — renders provider artifacts + creates tarball
├── tests/              # Build script tests
└── .github/
    └── workflows/
        └── release.yml # CI: tag push → build → GitHub Release asset
```

## Release assets

Each GitHub Release includes `cortex-<tag>.tar.gz` containing:

```
cortex-<tag>.tar.gz
├── claude/             # Claude Code artifacts (.md agent files, iEVO.md)
│   ├── iEVO.md
│   └── agents/
│       └── *.md
└── codex/              # OpenAI Codex artifacts (placeholder for v1)
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

## Integration

The iEvo CLI downloads and unpacks the latest release asset:

```bash
ievo init          # Downloads latest Cortex release automatically
ievo cortex build  # Rebuild locally from source (power-user path)
```

See: [ievo-ai/cli](https://github.com/ievo-ai/cli)
