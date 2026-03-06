"""Tests for `cortex compile` CLI command (REQ-017, Subtask 02).

TDD: tests written before implementation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cortex.cli import app
from cortex.version import __version__

REPO_ROOT = Path(__file__).parent.parent

runner = CliRunner()


def test_compile_produces_tarball(tmp_path: Path) -> None:
    """cortex compile --dist <tmp> exits 0 and tarball exists in tmp."""
    result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    tarballs = list(tmp_path.glob("cortex-*.tar.gz"))
    assert tarballs, f"No tarball found in {tmp_path}: {list(tmp_path.iterdir())}"


def test_compile_output_structure(tmp_path: Path) -> None:
    """After compile, dist/ contains iEVO.md, claude/, codex/ subdirectories."""
    result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    assert (tmp_path / "iEVO.md").exists(), "iEVO.md missing from dist"
    assert (tmp_path / "claude").is_dir(), "claude/ dir missing from dist"
    assert (tmp_path / "codex").is_dir(), "codex/ dir missing from dist"


def test_compile_uses_package_version(tmp_path: Path) -> None:
    """After compile, dist/iEVO.md contains the package __version__ value (AC-4)."""
    result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    ievo_md = tmp_path / "iEVO.md"
    assert ievo_md.exists(), "iEVO.md missing"
    content = ievo_md.read_text()
    assert __version__ in content, (
        f"__version__ {__version__!r} not found in dist/iEVO.md"
    )


def test_compile_validates_by_default(tmp_path: Path) -> None:
    """compile without --skip-validate calls validate_links() after build().

    Mock validate to return 2, verify exit code 2 (AC-2).
    """
    with patch("cortex.cli.validate_links", return_value=2) as mock_validate:
        result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])

    mock_validate.assert_called_once()
    assert result.exit_code == 2, (
        f"Expected exit code 2 from validate failure, got {result.exit_code}"
    )


def test_compile_skip_validate(tmp_path: Path) -> None:
    """cortex compile --skip-validate does NOT call validate_links but DOES call build() (AC-3)."""
    with patch("cortex.cli.validate_links") as mock_validate:
        result = runner.invoke(app, ["compile", "--skip-validate", "--dist", str(tmp_path)])

    mock_validate.assert_not_called()
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"
    # build was still called — tarball exists
    tarballs = list(tmp_path.glob("cortex-*.tar.gz"))
    assert tarballs, "Tarball missing — build() was not called"


def test_compile_missing_template_exits_1(tmp_path: Path) -> None:
    """When build() raises FileNotFoundError, compile exits 1."""

    with patch("cortex.cli.build", side_effect=FileNotFoundError("iEVO.md.j2 not found")):
        result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "iEVO.md.j2" in result.output or "Error" in result.output


def test_compile_undefined_var_exits_1(tmp_path: Path) -> None:
    """When build() raises jinja2.UndefinedError, compile exits 1."""
    import jinja2  # noqa: PLC0415

    with patch("cortex.cli.build", side_effect=jinja2.UndefinedError("undefined_var")):
        result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"


def test_compile_subprocess_integration(tmp_path: Path) -> None:
    """End-to-end: uv run cortex compile --dist <tmp> exits 0 and tarball exists."""
    result = subprocess.run(
        ["uv", "run", "cortex", "compile", "--dist", str(tmp_path), "--skip-validate"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"cortex compile failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    tarballs = list(tmp_path.glob("cortex-*.tar.gz"))
    assert tarballs, "No tarball found after subprocess cortex compile"
