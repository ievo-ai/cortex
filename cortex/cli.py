"""Cortex CLI — Typer application."""

from __future__ import annotations

import sys
from pathlib import Path

import jinja2
import typer

from cortex.compile import build, validate_links
from cortex.version import __version__

app = typer.Typer(name="cortex", help="Cortex kernel compilation CLI.")


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


if __name__ == "__main__":
    app()
