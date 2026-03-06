"""Tests for `cortex validate` CLI command (REQ-017, Subtask 02).

TDD: tests written before implementation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cortex.cli import app

runner = CliRunner()


def test_validate_no_lychee_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When lychee is absent (validate_links returns 0), exit 0 (AC-7)."""
    with patch("cortex.cli.validate_links", return_value=0):
        result = runner.invoke(app, ["validate", "--dist", str(tmp_path)])

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"


def test_validate_broken_links_exits_nonzero(tmp_path: Path) -> None:
    """When validate_links returns 2, cortex validate exits with code 2."""
    with patch("cortex.cli.validate_links", return_value=2):
        result = runner.invoke(app, ["validate", "--dist", str(tmp_path)])

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"


def test_validate_clean_exits_0(tmp_path: Path) -> None:
    """When validate_links returns 0, cortex validate exits 0."""
    with patch("cortex.cli.validate_links", return_value=0):
        result = runner.invoke(app, ["validate", "--dist", str(tmp_path)])

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"
