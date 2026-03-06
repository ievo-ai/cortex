"""Cortex CLI — Typer application."""

from __future__ import annotations

import typer

app = typer.Typer(name="cortex", help="Cortex kernel compilation CLI.")

if __name__ == "__main__":
    app()
