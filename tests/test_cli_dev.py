"""Tests for `cortex dev [--watch]` CLI command (REQ-017, Subtask 03).

TDD: tests written before implementation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cortex.cli import app

REPO_ROOT = Path(__file__).parent.parent

runner = CliRunner()


def test_dev_single_compile(tmp_path: Path) -> None:
    """cortex dev --dist <tmp> exits 0, tarball exists with tag 'dev' (AC-5)."""
    result = runner.invoke(app, ["dev", "--dist", str(tmp_path)])
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    tarballs = list(tmp_path.glob("cortex-dev.tar.gz"))
    assert tarballs, f"cortex-dev.tar.gz not found in {tmp_path}: {list(tmp_path.iterdir())}"


def test_dev_no_infinite_loop(tmp_path: Path) -> None:
    """cortex dev without --watch returns immediately (does not hang)."""
    import threading  # noqa: PLC0415

    result_holder = {}

    def run() -> None:
        result_holder["result"] = runner.invoke(app, ["dev", "--dist", str(tmp_path)])

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=10)  # 10s timeout — if hangs, something is wrong

    assert not t.is_alive(), "cortex dev without --watch hung (infinite loop?)"
    assert result_holder.get("result") is not None
    assert result_holder["result"].exit_code == 0


def test_dev_default_tag_is_dev(tmp_path: Path) -> None:
    """After cortex dev, tarball is named cortex-dev.tar.gz."""
    result = runner.invoke(app, ["dev", "--dist", str(tmp_path)])
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    assert (tmp_path / "cortex-dev.tar.gz").exists(), (
        f"Expected cortex-dev.tar.gz; found: {list(tmp_path.iterdir())}"
    )


def test_dev_skips_validation(tmp_path: Path) -> None:
    """cortex dev does NOT call validate_links() at all (dev speed > correctness)."""
    with patch("cortex.cli.validate_links") as mock_validate:
        result = runner.invoke(app, ["dev", "--dist", str(tmp_path)])

    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"
    mock_validate.assert_not_called()


def test_dev_watch_missing_watchfiles(tmp_path: Path) -> None:
    """When watchfiles is not available (fs_watch is None), cortex dev --watch exits 1."""
    # Patch fs_watch to None at module level — simulates watchfiles not installed
    with patch("cortex.cli.fs_watch", None):
        result = runner.invoke(app, ["dev", "--watch", "--dist", str(tmp_path)])

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "watchfiles" in result.output.lower() or "watchfiles" in (result.stdout or "").lower()


def test_dev_watch_triggers_recompile(tmp_path: Path) -> None:
    """cortex dev --watch recompiles when fs_watch yields a change (AC-6)."""
    changes = [frozenset({(1, str(tmp_path / "src/test.md"))})]  # one change set

    mock_fs_watch = MagicMock()
    mock_fs_watch.return_value = iter(changes)  # yields one then StopIteration

    build_calls = []

    def mock_build(tag: str, dist_dir: Path) -> Path:
        build_calls.append(tag)
        # Create a fake tarball so the code doesn't fail
        tarball = dist_dir / f"cortex-{tag}.tar.gz"
        dist_dir.mkdir(parents=True, exist_ok=True)
        tarball.touch()
        return tarball

    with (
        patch("cortex.cli.build", side_effect=mock_build),
        patch("cortex.cli.fs_watch", mock_fs_watch),
    ):
        result = runner.invoke(app, ["dev", "--watch", "--dist", str(tmp_path)])

    # build called: once initial + once for the change = 2
    assert len(build_calls) >= 2, (
        f"Expected at least 2 build calls (initial + recompile), got {len(build_calls)}"
    )
    assert "Recompiling" in result.output or "recompil" in result.output.lower(), (
        f"Expected recompile message in output:\n{result.output}"
    )


def test_dev_watch_ctrl_c(tmp_path: Path) -> None:
    """cortex dev --watch handles KeyboardInterrupt cleanly (no traceback)."""
    mock_fs_watch = MagicMock()
    mock_fs_watch.return_value = iter([KeyboardInterrupt()])

    def mock_fs_watch_raises(*args: object, **kwargs: object) -> object:
        raise KeyboardInterrupt

    with (
        patch("cortex.cli.build") as mock_build,
        patch("cortex.cli.fs_watch", side_effect=mock_fs_watch_raises),
    ):
        # mock_build needs to create actual tarball
        def real_mock_build(tag: str, dist_dir: Path) -> Path:
            dist_dir.mkdir(parents=True, exist_ok=True)
            tarball = dist_dir / f"cortex-{tag}.tar.gz"
            tarball.touch()
            return tarball

        mock_build.side_effect = real_mock_build
        result = runner.invoke(app, ["dev", "--watch", "--dist", str(tmp_path)])

    # Clean exit (no unhandled traceback) — CliRunner should catch gracefully
    assert "Traceback" not in result.output, f"Traceback in output:\n{result.output}"


def test_dev_subprocess_integration(tmp_path: Path) -> None:
    """End-to-end: uv run cortex dev --dist <tmp> exits 0 and cortex-dev.tar.gz exists."""
    result = subprocess.run(
        ["uv", "run", "cortex", "dev", "--dist", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"cortex dev failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert (tmp_path / "cortex-dev.tar.gz").exists(), (
        f"cortex-dev.tar.gz not found: {list(tmp_path.iterdir())}"
    )
