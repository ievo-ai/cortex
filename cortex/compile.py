"""Cortex compile module — produces provider-specific artifacts and a release tarball.

Content compilation: template rendering + provider artifact assembly.
NOT package build (use `uv build` for that).

iEVO.md is rendered ONCE (provider-agnostic) → dist/iEVO.md.
For each provider target (claude, codex):
    - Renders provider-specific artifacts from src/
    - Writes to dist/<provider>/
    - Creates dist/cortex-<tag>.tar.gz with iEVO.md at root + provider directories

BREAKING CHANGE (REQ-004): iEVO.md moved from dist/<provider>/iEVO.md to dist/iEVO.md.

v1 placeholder behavior:
    - dist/iEVO.md: kernel (provider-agnostic)
    - claude/: one placeholder agent .md
    - codex/: BUILD_TARGET.md (format TBD per IDEA-005)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

# CORTEX_ROOT is the repo root (one level above this package directory)
CORTEX_ROOT = Path(__file__).parent.parent
IEVO_MD_TEMPLATE = CORTEX_ROOT / "src" / "kernel" / "consciousness.md.j2"


def render_template(
    template_path: Path, context: dict[str, str], loader_root: Path | None = None
) -> str:
    """Render a Jinja2 template file with the given context variables.

    Args:
        template_path: Absolute path to the .j2 template file.
        context: Variables to pass to the template.
        loader_root: Root directory for the Jinja2 FileSystemLoader. Defaults to
            ``template_path.parent.parent`` when not provided.

    Returns:
        Rendered string content.

    Raises:
        FileNotFoundError: If the template file does not exist.
        jinja2.UndefinedError: If the template references a variable not in context.
    """
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    if loader_root is None:
        loader_root = template_path.parent.parent
    relative = template_path.relative_to(loader_root)

    env = Environment(
        loader=FileSystemLoader(str(loader_root)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    template = env.get_template(str(relative))
    return template.render(**context)


CLAUDE_AGENTS_SRC = CORTEX_ROOT / "src" / "agents"
CODEX_SRC = CORTEX_ROOT / "src" / "codex"


def validate_links(dist_dir: Path) -> int:
    """Validate Markdown links in dist_dir using lychee.

    Runs lychee with --offline (skip external URLs), --include-fragments (anchor
    checking — mandatory for AC-2 and AC-4), and --no-progress (CI-friendly output).

    Three explicit return paths:
    1. Lychee not on PATH: print warning to stderr + return 0
    2. Lychee runs and passes (returncode == 0): return 0
    3. Lychee runs and fails (returncode != 0): print output to stderr + return result.returncode

    # TODO(IDEA-011): orphaned anchor detection — headings never referenced

    Args:
        dist_dir: Path to the rendered output directory (e.g. dist/).

    Returns:
        int: 0 on success or lychee not found, lychee's exit code on failure.
    """
    lychee_bin = shutil.which("lychee")
    if lychee_bin is None:
        print(
            "Warning: lychee not found on PATH — skipping link validation.\n"
            "  macOS:   brew install lychee\n"
            "  Windows: scoop install lychee  (or choco install lychee)\n"
            "  Linux:   cargo install lychee  (or download from https://github.com/lycheeverse/lychee/releases)",
            file=sys.stderr,
        )
        return 0

    result = subprocess.run(
        ["lychee", "--offline", "--include-fragments", "--no-progress", str(dist_dir)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode

    return 0


def render_ievo_md(dist_dir: Path, tag: str) -> None:
    """Render iEVO.md once (provider-agnostic) → dist_dir/iEVO.md."""
    rendered = render_template(
        IEVO_MD_TEMPLATE,
        {"cortex_version": tag},
        CORTEX_ROOT / "src",
    )
    (dist_dir / "iEVO.md").write_text(rendered)


def build_claude_target(claude_dir: Path, tag: str) -> None:
    """Render claude/ provider artifacts."""
    claude_dir.mkdir(parents=True, exist_ok=True)

    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    for src_file in sorted(CLAUDE_AGENTS_SRC.glob("*.md")):
        (agents_dir / src_file.name).write_text(src_file.read_text())


def build_codex_target(codex_dir: Path, tag: str) -> None:
    """Render codex/ provider artifacts."""
    codex_dir.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(CODEX_SRC.glob("*.md")):
        (codex_dir / src_file.name).write_text(src_file.read_text())


def create_tarball(dist_dir: Path, tag: str) -> Path:
    """Create cortex-<tag>.tar.gz with iEVO.md at root + provider directories."""
    tarball_path = dist_dir / f"cortex-{tag}.tar.gz"

    with tarfile.open(tarball_path, "w:gz") as tf:
        # Add iEVO.md at tarball root (provider-agnostic)
        ievo_md = dist_dir / "iEVO.md"
        if ievo_md.exists():
            tf.add(ievo_md, arcname="iEVO.md")

        # Add provider-specific directories
        for provider in ("claude", "codex"):
            provider_dir = dist_dir / provider
            if provider_dir.exists():
                for file_path in sorted(provider_dir.rglob("*")):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(dist_dir))
                        tf.add(file_path, arcname=arcname)

    return tarball_path


def build(tag: str, dist_dir: Path) -> Path:
    """Compile all provider targets and create release tarball.

    This is a pure compilation step — it does NOT call validate_links().
    The CLI layer orchestrates validation separately.

    Returns the path to the created tarball.
    """
    # Clean and recreate provider dirs for idempotency
    for provider in ("claude", "codex"):
        provider_dir = dist_dir / provider
        if provider_dir.exists():
            shutil.rmtree(provider_dir)

    dist_dir.mkdir(parents=True, exist_ok=True)

    build_claude_target(dist_dir / "claude", tag)
    build_codex_target(dist_dir / "codex", tag)

    # Render iEVO.md once — provider-agnostic (REQ-004)
    render_ievo_md(dist_dir, tag)

    return create_tarball(dist_dir, tag)
