"""Cortex backward-compat build wrapper — DEPRECATED.

Usage:
    python build.py --tag v1.0.0 [--dist ./dist]

# TODO(task 017): remove build.py backward-compat wrapper once all callers
#   have migrated to `cortex compile`.

This thin wrapper delegates to cortex.compile and preserves the old behavior:
compile first, then validate links (sys.exit on failure).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cortex.compile import (  # noqa: F401 (re-export for backward compat)
    CLAUDE_AGENT_MD,
    CODEX_BUILD_TARGET_MD,
    CORTEX_ROOT,
    IEVO_MD_TEMPLATE,
    build,
    build_claude_target,
    build_codex_target,
    create_tarball,
    render_ievo_md,
    render_template,
    validate_links,
)

import jinja2


def main() -> None:
    """Run compile + validate (preserving original build.py behavior)."""
    parser = argparse.ArgumentParser(description="Build Cortex release artifacts.")
    parser.add_argument("--tag", required=True, help="Release tag (e.g. v1.0.0)")
    parser.add_argument(
        "--dist",
        default=str(CORTEX_ROOT / "dist"),
        help="Output directory (default: ./dist)",
    )
    args = parser.parse_args()

    dist_dir = Path(args.dist)
    try:
        tarball = build(tag=args.tag, dist_dir=dist_dir)
    except FileNotFoundError as exc:
        print(f"Error: template file not found — {exc}", file=sys.stderr)
        sys.exit(1)
    except jinja2.UndefinedError as exc:
        print(f"Error: undefined template variable — {exc}", file=sys.stderr)
        sys.exit(1)

    # Validate after compile (preserving old behavior — CLI orchestrates separately)
    rc = validate_links(dist_dir)
    if rc != 0:
        sys.exit(rc)

    print(f"Built: {tarball}")


if __name__ == "__main__":
    main()
