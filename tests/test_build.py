"""Tests for cortex build script.

TDD: tests written before build.py is implemented.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path


CORTEX_ROOT = Path(__file__).parent.parent


def run_build(tmp_path: Path, tag: str = "v1.0.0") -> subprocess.CompletedProcess:
    """Run build.py from the cortex root into the given tmp_path."""
    return subprocess.run(
        [sys.executable, str(CORTEX_ROOT / "build.py"), "--tag", tag, "--dist", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )


def test_build_creates_tarball(tmp_path: Path) -> None:
    """build.py creates cortex-<tag>.tar.gz in the dist directory."""
    result = run_build(tmp_path, tag="v1.0.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    assert tarball.exists(), f"Expected {tarball} but found: {list(tmp_path.iterdir())}"


def test_tarball_contains_both_providers(tmp_path: Path) -> None:
    """The release asset, when unpacked, contains both claude/ and codex/ directories."""
    result = run_build(tmp_path, tag="v1.0.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    # Must have at least one file under claude/ and at least the codex placeholder
    claude_files = [n for n in names if n.startswith("claude/")]
    codex_files = [n for n in names if n.startswith("codex/")]

    assert claude_files, f"No claude/ entries in tarball. Names: {names}"
    assert codex_files, f"No codex/ entries in tarball. Names: {names}"


def test_tarball_claude_contains_ievo_md(tmp_path: Path) -> None:
    """The claude/ directory in the tarball contains iEVO.md."""
    result = run_build(tmp_path, tag="v1.0.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "claude/iEVO.md" in names, f"claude/iEVO.md missing. Names: {names}"


def test_tarball_codex_contains_build_target_md(tmp_path: Path) -> None:
    """The codex/ directory contains BUILD_TARGET.md (placeholder for v1)."""
    result = run_build(tmp_path, tag="v1.0.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "codex/BUILD_TARGET.md" in names, f"codex/BUILD_TARGET.md missing. Names: {names}"


def test_build_idempotent(tmp_path: Path) -> None:
    """Running build.py twice produces identical tarballs (same member names)."""
    run_build(tmp_path, tag="v1.0.0")
    tarball = tmp_path / "cortex-v1.0.0.tar.gz"

    with tarfile.open(tarball, "r:gz") as tf:
        names_first = sorted(tf.getnames())

    # Run again (overwrites)
    run_build(tmp_path, tag="v1.0.0")

    with tarfile.open(tarball, "r:gz") as tf:
        names_second = sorted(tf.getnames())

    assert names_first == names_second, (
        f"Build not idempotent.\nFirst:  {names_first}\nSecond: {names_second}"
    )


def test_build_uses_provided_tag(tmp_path: Path) -> None:
    """build.py embeds the --tag value in the output filename."""
    result = run_build(tmp_path, tag="v2.3.4")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    tarball = tmp_path / "cortex-v2.3.4.tar.gz"
    assert tarball.exists(), f"Expected cortex-v2.3.4.tar.gz but found: {list(tmp_path.iterdir())}"
