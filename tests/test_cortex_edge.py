"""QA edge-case tests for cortex build script (REQ-002).

These tests cover gaps not addressed by the Coder's test_build.py:
  - render_template() unit-level error paths
  - Default loader_root inference
  - Empty and special-character tag values
  - One-sided provider conditionals (no else)
  - Template with no provider blocks at all
  - UTF-8 content in templates
  - dist/ directory does not exist on first build
  - codex/iEVO.md is present in the tarball
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

import jinja2
import pytest

from build import build, render_template


CORTEX_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# render_template() — unit-level error paths
# ---------------------------------------------------------------------------


def test_qa_render_template_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """render_template() raises FileNotFoundError when the template file does not exist."""
    nonexistent = tmp_path / "kernel" / "missing.md.j2"
    with pytest.raises(FileNotFoundError, match="missing.md.j2"):
        render_template(nonexistent, {"cortex_version": "v1.0.0", "provider": "claude"})


def test_qa_render_template_default_loader_root(tmp_path: Path) -> None:
    """render_template() uses template_path.parent.parent as loader_root when not provided."""
    # Structure matches the real layout: <root>/kernel/<name>.md.j2
    # loader_root should default to tmp_path (parent of 'kernel/')
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text("{{ cortex_version }}-{{ provider }}\n")

    result = render_template(tmpl, {"cortex_version": "v9.9.9", "provider": "claude"})

    assert "v9.9.9" in result
    assert "claude" in result
    assert "{{" not in result


# ---------------------------------------------------------------------------
# Provider conditional edge cases
# ---------------------------------------------------------------------------


def test_qa_one_sided_if_renders_empty_for_other_provider(tmp_path: Path) -> None:
    """A {% if provider == "claude" %} block with no else renders nothing for codex."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text(
        "Common line\n"
        "{% if provider == \"claude\" %}Claude-specific\n{% endif %}"
        "Trailing line\n"
    )

    codex_result = render_template(
        tmpl, {"cortex_version": "v1.0.0", "provider": "codex"}, tmp_path
    )

    assert "Common line" in codex_result
    assert "Trailing line" in codex_result
    assert "Claude-specific" not in codex_result
    assert "{%" not in codex_result


def test_qa_template_with_no_provider_blocks_renders_for_both(tmp_path: Path) -> None:
    """A template with only {{ cortex_version }} and no {% if provider %} renders cleanly."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text("# iEvo Pipeline — version {{ cortex_version }}\nNo provider blocks here.\n")

    for provider in ("claude", "codex"):
        result = render_template(
            tmpl, {"cortex_version": "v1.0.0", "provider": provider}, tmp_path
        )
        assert "v1.0.0" in result
        assert "{{" not in result
        assert "{%" not in result


# ---------------------------------------------------------------------------
# Tag value edge cases
# ---------------------------------------------------------------------------


def test_qa_empty_tag_renders_empty_version_in_output(tmp_path: Path) -> None:
    """An empty --tag value embeds an empty string for cortex_version without crashing."""
    result = subprocess.run(
        [sys.executable, str(CORTEX_ROOT / "build.py"), "--tag", "", "--dist", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )
    assert result.returncode == 0, f"build.py failed with empty tag:\n{result.stderr}"

    claude_md = tmp_path / "claude" / "iEVO.md"
    assert claude_md.exists(), "dist/claude/iEVO.md missing"

    content = claude_md.read_text()
    assert "{{" not in content, "Unrendered {{ with empty tag"
    assert "{%" not in content, "Unrendered {% with empty tag"


def test_qa_tag_with_spaces_renders_into_version(tmp_path: Path) -> None:
    """A tag containing spaces is passed through to cortex_version without escaping issues."""
    result = subprocess.run(
        [
            sys.executable,
            str(CORTEX_ROOT / "build.py"),
            "--tag",
            "v1.0 beta",
            "--dist",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )
    assert result.returncode == 0, f"build.py failed with spaced tag:\n{result.stderr}"

    claude_md = tmp_path / "claude" / "iEVO.md"
    content = claude_md.read_text()
    assert "v1.0 beta" in content, "Spaced tag not found in rendered output"
    assert "{{" not in content
    assert "{%" not in content


def test_qa_tag_with_special_chars_renders_cleanly(tmp_path: Path) -> None:
    """A tag with special characters (+ # @) renders into cortex_version without Jinja2 errors."""
    special_tag = "v1.0.0+build.42"
    result = subprocess.run(
        [
            sys.executable,
            str(CORTEX_ROOT / "build.py"),
            "--tag",
            special_tag,
            "--dist",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )
    assert result.returncode == 0, f"build.py failed with special-char tag:\n{result.stderr}"

    claude_md = tmp_path / "claude" / "iEVO.md"
    content = claude_md.read_text()
    assert special_tag in content
    assert "{{" not in content


# ---------------------------------------------------------------------------
# UTF-8 in template
# ---------------------------------------------------------------------------


def test_qa_utf8_content_in_template_renders_correctly(tmp_path: Path) -> None:
    """Template containing UTF-8 characters (non-ASCII) renders without encoding errors."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text(
        "# Версия {{ cortex_version }} — café ☕\nProvider: {{ provider }}\n",
        encoding="utf-8",
    )

    result = render_template(
        tmpl, {"cortex_version": "v1.0.0", "provider": "claude"}, tmp_path
    )

    assert "v1.0.0" in result
    assert "Версия" in result
    assert "café" in result
    assert "☕" in result
    assert "{{" not in result


# ---------------------------------------------------------------------------
# dist/ directory creation
# ---------------------------------------------------------------------------


def test_qa_build_creates_dist_dir_when_missing(tmp_path: Path) -> None:
    """build() creates the dist directory (and parents) if it does not already exist."""
    brand_new_dist = tmp_path / "deeply" / "nested" / "dist"
    assert not brand_new_dist.exists(), "Pre-condition: dir should not exist"

    tarball = build(tag="v1.0.0", dist_dir=brand_new_dist)

    assert brand_new_dist.exists(), "dist/ was not created"
    assert tarball.exists(), "Tarball was not created"


# ---------------------------------------------------------------------------
# Tarball content — codex/iEVO.md must be present
# ---------------------------------------------------------------------------


def test_qa_tarball_codex_contains_ievo_md(tmp_path: Path) -> None:
    """The codex/ directory in the tarball contains iEVO.md (rendered from template)."""
    result = subprocess.run(
        [
            sys.executable,
            str(CORTEX_ROOT / "build.py"),
            "--tag",
            "v1.0.0",
            "--dist",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "codex/iEVO.md" in names, f"codex/iEVO.md missing from tarball. Names: {names}"


def test_qa_codex_ievo_md_contains_version_and_no_jinja(tmp_path: Path) -> None:
    """dist/codex/iEVO.md is a rendered file: contains version tag, no raw Jinja2 syntax."""
    result = subprocess.run(
        [
            sys.executable,
            str(CORTEX_ROOT / "build.py"),
            "--tag",
            "v1.2.3",
            "--dist",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    codex_md = tmp_path / "codex" / "iEVO.md"
    assert codex_md.exists(), "dist/codex/iEVO.md not found on disk"

    content = codex_md.read_text()
    assert "v1.2.3" in content, "Version not found in dist/codex/iEVO.md"
    assert "{{" not in content, "Unrendered {{ in dist/codex/iEVO.md"
    assert "{%" not in content, "Unrendered {% in dist/codex/iEVO.md"
