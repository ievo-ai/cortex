"""Tests for validate_links() in build.py.

Unit tests (Steps 1): mock subprocess to verify argument construction and error handling.
Integration tests (Step 2): exercise real lychee binary — skipped when lychee not installed.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# validate_links and build are imported from the build module in cortex root
sys.path.insert(0, str(Path(__file__).parent.parent))
from build import build, validate_links  # noqa: E402


CORTEX_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Step 1: Unit tests — mocked subprocess (lychee not required)
# ---------------------------------------------------------------------------


def test_validate_links_skipped_when_lychee_not_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """When lychee binary is absent, validate_links() warns to stderr and returns (no error)."""
    with patch("shutil.which", return_value=None):
        validate_links(tmp_path)  # must not raise

    captured = capsys.readouterr()
    assert "lychee" in captured.err.lower(), (
        f"Expected lychee warning in stderr, got: {captured.err!r}"
    )


def test_validate_links_calls_lychee_with_correct_flags(tmp_path: Path) -> None:
    """validate_links() invokes lychee with --offline, --include-fragments, --no-progress."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        validate_links(tmp_path)

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "--offline" in cmd, f"--offline missing from command: {cmd}"
    assert "--include-fragments" in cmd, (
        f"--include-fragments missing from command: {cmd}"
    )
    assert "--no-progress" in cmd, f"--no-progress missing from command: {cmd}"
    assert str(tmp_path) in cmd, f"dist_dir missing from command: {cmd}"


def test_validate_links_raises_on_broken_links(tmp_path: Path) -> None:
    """When lychee exits with non-zero code, validate_links() calls sys.exit with that code."""
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = "broken: ./missing.md"
    mock_result.stderr = "1 broken link found"

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(SystemExit) as exc_info,
    ):
        validate_links(tmp_path)

    assert exc_info.value.code == 2


def test_validate_links_passes_on_exit_zero(tmp_path: Path) -> None:
    """When lychee exits 0, validate_links() returns without raising."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result),
    ):
        validate_links(tmp_path)  # must not raise


# ---------------------------------------------------------------------------
# Step 2: Integration tests — real lychee binary required
# ---------------------------------------------------------------------------

_lychee_available = shutil.which("lychee") is not None
_skip_if_no_lychee = pytest.mark.skipif(
    not _lychee_available, reason="lychee not installed"
)


def _build_dist(tmp_path: Path, tag: str = "v1.0.0") -> Path:
    """Run build() into tmp_path and return the dist_dir."""
    dist_dir = tmp_path / "dist"
    build(tag=tag, dist_dir=dist_dir)
    return dist_dir


@_skip_if_no_lychee
def test_valid_build_passes_lychee(tmp_path: Path) -> None:
    """AC-1: A clean build output passes lychee without error."""
    dist_dir = _build_dist(tmp_path)
    validate_links(dist_dir)  # must not raise


@_skip_if_no_lychee
def test_broken_same_file_anchor_fails(tmp_path: Path) -> None:
    """AC-2: A broken same-file anchor in dist/claude/iEVO.md causes lychee to exit non-zero."""
    dist_dir = _build_dist(tmp_path)

    ievo_md = dist_dir / "claude" / "iEVO.md"
    existing = ievo_md.read_text()
    ievo_md.write_text(existing + "\n[broken](#nonexistent-heading-xyz-abc)\n")

    with pytest.raises(SystemExit) as exc_info:
        validate_links(dist_dir)

    assert exc_info.value.code != 0


@_skip_if_no_lychee
def test_missing_cross_file_target_fails(tmp_path: Path) -> None:
    """AC-3: A link to a non-existent file in dist/ causes lychee to exit non-zero."""
    dist_dir = _build_dist(tmp_path)

    ievo_md = dist_dir / "claude" / "iEVO.md"
    existing = ievo_md.read_text()
    ievo_md.write_text(existing + "\n[missing](./totally-missing-file.md)\n")

    with pytest.raises(SystemExit) as exc_info:
        validate_links(dist_dir)

    assert exc_info.value.code != 0


@_skip_if_no_lychee
def test_broken_cross_file_anchor_fails(tmp_path: Path) -> None:
    """AC-4: A broken cross-file anchor causes lychee to exit non-zero."""
    dist_dir = _build_dist(tmp_path)

    agent_md = dist_dir / "claude" / "agents" / "spec-writer.md"
    existing = agent_md.read_text()
    agent_md.write_text(existing + "\n[broken](../iEVO.md#no-such-section-xyz)\n")

    with pytest.raises(SystemExit) as exc_info:
        validate_links(dist_dir)

    assert exc_info.value.code != 0


@_skip_if_no_lychee
def test_external_urls_skipped_with_offline(tmp_path: Path) -> None:
    """AC-5: External https:// URLs are ignored when lychee runs with --offline."""
    dist_dir = _build_dist(tmp_path)

    ievo_md = dist_dir / "claude" / "iEVO.md"
    existing = ievo_md.read_text()
    ievo_md.write_text(
        existing + "\n[Docs](https://example.com/nonexistent-page-xyz)\n"
    )

    validate_links(dist_dir)  # must not raise — external URL skipped
