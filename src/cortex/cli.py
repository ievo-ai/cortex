"""Cortex CLI — Typer application."""

from __future__ import annotations

import sys
from pathlib import Path

import jinja2
import typer

from cortex.compile import CORTEX_ROOT, build, validate_links
from cortex.version import __version__

app = typer.Typer(name="cortex", help="Cortex kernel compilation CLI.")

# NAMING HAZARD (S-4): `watch` is a CLI param on dev command — alias the fs_watch import
# to avoid shadowing the local bool parameter. This import is module-level for mockability.
try:
    from watchfiles import watch as fs_watch
except ImportError:
    fs_watch = None  # type: ignore[assignment]


@app.command()
def compile(
    dist: str = typer.Option("./dist", help="Output directory"),
    skip_validate: bool = typer.Option(False, "--skip-validate", help="Skip link validation"),
) -> None:
    """Render templates, prepare agents, validate links, create output in dist/.

    Reads version from package (__version__, CalVer). Validation is included by
    default. Use --skip-validate to render only (e.g. when lychee is not available).
    """
    tag = __version__
    dist_path = Path(dist)
    try:
        tarball = build(tag=tag, dist_dir=dist_path)
    except (FileNotFoundError, jinja2.UndefinedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)
    if not skip_validate:
        rc = validate_links(dist_path)
        if rc != 0:
            raise typer.Exit(code=rc)
    print(f"Compiled: {tarball}")


@app.command()
def validate(
    dist: str = typer.Option("./dist", help="Output directory"),
) -> None:
    """Standalone lychee validation on already-compiled output in dist/.

    Does not recompile. If lychee is not on PATH, prints a warning and exits 0.
    If lychee finds broken links, exits with lychee's return code.
    """
    rc = validate_links(Path(dist))
    if rc != 0:
        raise typer.Exit(code=rc)


@app.command()
def dev(
    watch: bool = typer.Option(False, "--watch", help="Watch templates/ for changes and recompile"),
    dist: str = typer.Option("./dist", help="Output directory"),
) -> None:
    """Single compile for development. Use --watch to recompile on file changes.

    Uses tag 'dev' (not __version__) for fast iteration. Validates links after
    each compile (warns if lychee not installed). Run `cortex compile` for a full build.
    """
    dist_path = Path(dist)
    # Initial compile
    build(tag="dev", dist_dir=dist_path)
    validate_links(dist_path)
    print(f"Compiled to {dist_path}")

    if not watch:
        return

    # NAMING HAZARD (S-4): `watch` is the bool param above — use `fs_watch` alias
    if fs_watch is None:
        print(
            "Error: watchfiles not installed. Run: uv sync --extra dev",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    try:
        for changes in fs_watch(CORTEX_ROOT / "templates"):
            print(f"Recompiling... {changes}")
            build(tag="dev", dist_dir=dist_path)
            validate_links(dist_path)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
