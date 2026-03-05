"""QA edge-case tests for REQ-004 — iEVO.md single provider-agnostic file.

Covers gaps not addressed by test_build.py or test_cortex_edge.py:
  1. Leftover dist/claude/iEVO.md from a prior build is cleaned up by build()
  2. Tarball after a run from dirty state: iEVO.md at root, claude/iEVO.md absent
  3. --tag "" (empty string) still creates dist/iEVO.md (empty cortex_version is valid)
  4. build_claude_target() and build_codex_target() have unused tag param — different
     tag values do not affect dist/iEVO.md content (content comes from render_ievo_md)
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from build import build, build_claude_target, build_codex_target


CORTEX_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# 1. Stale dist/claude/iEVO.md is cleaned up by build()
# ---------------------------------------------------------------------------


def test_qa_stale_claude_ievo_md_removed_by_build(tmp_path: Path) -> None:
    """A leftover dist/claude/iEVO.md from a prior build is removed on rebuild.

    Scenario: a previous REQ-002-era run wrote dist/claude/iEVO.md.
    After REQ-004, build() must clean that file so it is absent from dist/.
    """
    # Plant a stale iEVO.md inside dist/claude/ simulating a prior-era build
    stale_claude_dir = tmp_path / "claude"
    stale_claude_dir.mkdir(parents=True)
    stale_ievo = stale_claude_dir / "iEVO.md"
    stale_ievo.write_text("old per-provider content — should be gone after rebuild\n")

    assert stale_ievo.exists(), "Pre-condition: stale file must exist before build"

    build(tag="v1.0.0", dist_dir=tmp_path)

    assert not stale_ievo.exists(), (
        "dist/claude/iEVO.md must not exist after build() — "
        "build() cleans provider dirs before rebuilding them"
    )


def test_qa_stale_codex_ievo_md_removed_by_build(tmp_path: Path) -> None:
    """A leftover dist/codex/iEVO.md from a prior build is removed on rebuild."""
    stale_codex_dir = tmp_path / "codex"
    stale_codex_dir.mkdir(parents=True)
    stale_ievo = stale_codex_dir / "iEVO.md"
    stale_ievo.write_text("old codex per-provider content\n")

    assert stale_ievo.exists(), "Pre-condition: stale file must exist before build"

    build(tag="v1.0.0", dist_dir=tmp_path)

    assert not stale_ievo.exists(), (
        "dist/codex/iEVO.md must not exist after build() — "
        "build() cleans provider dirs before rebuilding them"
    )


def test_qa_stale_provider_ievo_md_absent_from_tarball(tmp_path: Path) -> None:
    """After a build from dirty state, the tarball must not contain claude/iEVO.md.

    Plants stale provider iEVO.md files, runs build(), then inspects the tarball.
    This closes the end-to-end gap: the tarball itself must be clean even if dist/
    was dirty before the build.
    """
    # Plant stale files in both provider dirs
    for provider in ("claude", "codex"):
        d = tmp_path / provider
        d.mkdir(parents=True)
        (d / "iEVO.md").write_text(f"stale {provider} iEVO.md\n")

    build(tag="v2.0.0", dist_dir=tmp_path)

    tarball = tmp_path / "cortex-v2.0.0.tar.gz"
    assert tarball.exists(), "Tarball must be created"

    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "iEVO.md" in names, (
        f"iEVO.md must be at tarball root. Members: {names}"
    )
    assert "claude/iEVO.md" not in names, (
        f"claude/iEVO.md must NOT appear in tarball. Members: {names}"
    )
    assert "codex/iEVO.md" not in names, (
        f"codex/iEVO.md must NOT appear in tarball. Members: {names}"
    )


# ---------------------------------------------------------------------------
# 2. --tag "" produces dist/iEVO.md (empty cortex_version is valid)
# ---------------------------------------------------------------------------


def test_qa_empty_tag_produces_ievo_md_at_root(tmp_path: Path) -> None:
    """build() with tag='' writes dist/iEVO.md even when cortex_version is empty.

    The tarball is named cortex-.tar.gz (empty tag suffix). Both the file
    and the tarball entry must exist at dist root level.
    """
    build(tag="", dist_dir=tmp_path)

    ievo_md = tmp_path / "iEVO.md"
    assert ievo_md.exists(), "dist/iEVO.md must exist even with empty tag"

    content = ievo_md.read_text()
    assert "{{" not in content, "Unrendered {{ found with empty tag"
    assert "{%" not in content, "Unrendered {% found with empty tag"

    # Tarball named cortex-.tar.gz
    tarball = tmp_path / "cortex-.tar.gz"
    assert tarball.exists(), (
        f"Expected cortex-.tar.gz with empty tag; found: {list(tmp_path.iterdir())}"
    )

    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "iEVO.md" in names, (
        f"iEVO.md must be in tarball even with empty tag. Members: {names}"
    )


def test_qa_empty_tag_no_provider_ievo_md_in_subdirs(tmp_path: Path) -> None:
    """build() with tag='' must NOT write dist/claude/iEVO.md or dist/codex/iEVO.md."""
    build(tag="", dist_dir=tmp_path)

    assert not (tmp_path / "claude" / "iEVO.md").exists(), (
        "dist/claude/iEVO.md must not be created even with empty tag"
    )
    assert not (tmp_path / "codex" / "iEVO.md").exists(), (
        "dist/codex/iEVO.md must not be created even with empty tag"
    )


# ---------------------------------------------------------------------------
# 3. Unused tag param in build_claude_target / build_codex_target
#    — different tag values do not affect dist/iEVO.md content
# ---------------------------------------------------------------------------


def test_qa_build_claude_target_tag_does_not_affect_artifacts(tmp_path: Path) -> None:
    """build_claude_target() ignores the tag param — artifact content is tag-independent.

    The tag param is currently unused; calling with different tag values must
    produce identical file content inside dist/claude/.
    """
    claude_dir_a = tmp_path / "run_a" / "claude"
    claude_dir_b = tmp_path / "run_b" / "claude"

    build_claude_target(claude_dir_a, tag="v1.0.0")
    build_claude_target(claude_dir_b, tag="v99.0.0")

    # Both should produce the same set of files with identical content
    files_a = sorted(p.relative_to(claude_dir_a) for p in claude_dir_a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(claude_dir_b) for p in claude_dir_b.rglob("*") if p.is_file())

    assert files_a == files_b, (
        f"build_claude_target produced different file sets for different tags.\n"
        f"v1.0.0: {files_a}\nv99.0.0: {files_b}"
    )

    for rel in files_a:
        content_a = (claude_dir_a / rel).read_bytes()
        content_b = (claude_dir_b / rel).read_bytes()
        assert content_a == content_b, (
            f"build_claude_target: {rel} differs between tag v1.0.0 and v99.0.0"
        )


def test_qa_build_codex_target_tag_does_not_affect_artifacts(tmp_path: Path) -> None:
    """build_codex_target() ignores the tag param — artifact content is tag-independent."""
    codex_dir_a = tmp_path / "run_a" / "codex"
    codex_dir_b = tmp_path / "run_b" / "codex"

    build_codex_target(codex_dir_a, tag="v1.0.0")
    build_codex_target(codex_dir_b, tag="v99.0.0")

    files_a = sorted(p.relative_to(codex_dir_a) for p in codex_dir_a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(codex_dir_b) for p in codex_dir_b.rglob("*") if p.is_file())

    assert files_a == files_b, (
        f"build_codex_target produced different file sets for different tags.\n"
        f"v1.0.0: {files_a}\nv99.0.0: {files_b}"
    )

    for rel in files_a:
        content_a = (codex_dir_a / rel).read_bytes()
        content_b = (codex_dir_b / rel).read_bytes()
        assert content_b == content_a, (
            f"build_codex_target: {rel} differs between tag v1.0.0 and v99.0.0"
        )


def test_qa_ievo_md_content_independent_of_provider_function_tag(tmp_path: Path) -> None:
    """dist/iEVO.md content comes from render_ievo_md, not build_claude/codex_target.

    Even if provider functions were hypothetically changed to pass tag into iEVO.md,
    the actual dist/iEVO.md content is determined solely by render_ievo_md(tag).
    Two builds with the same tag must produce the same dist/iEVO.md regardless of
    what happens inside the provider target functions.
    """
    dist_a = tmp_path / "dist_a"
    dist_b = tmp_path / "dist_b"

    build(tag="v3.0.0", dist_dir=dist_a)
    build(tag="v3.0.0", dist_dir=dist_b)

    content_a = (dist_a / "iEVO.md").read_bytes()
    content_b = (dist_b / "iEVO.md").read_bytes()

    assert content_a == content_b, (
        "dist/iEVO.md must be identical across two builds with the same tag"
    )
    assert b"v3.0.0" in content_a, "Version tag must appear in dist/iEVO.md"
