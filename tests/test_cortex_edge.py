"""QA edge-case tests for cortex build script (REQ-002, updated for REQ-004).

These tests cover gaps not addressed by the Coder's test_build.py:
  - render_template() unit-level error paths
  - Default loader_root inference
  - Empty and special-character tag values
  - One-sided provider conditionals (no else) — generic Jinja2 behavior
  - Template with only cortex_version renders cleanly (mirrors real iEVO.md use case)
  - UTF-8 content in templates
  - dist/ directory does not exist on first build
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
        render_template(nonexistent, {"cortex_version": "v1.0.0"})


def test_qa_render_template_default_loader_root(tmp_path: Path) -> None:
    """render_template() uses template_path.parent.parent as loader_root when not provided."""
    # Structure matches the real layout: <root>/kernel/<name>.md.j2
    # loader_root should default to tmp_path (parent of 'kernel/')
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text("{{ cortex_version }}\n")

    result = render_template(tmpl, {"cortex_version": "v9.9.9"})

    assert "v9.9.9" in result
    assert "{{" not in result


# ---------------------------------------------------------------------------
# Provider conditional edge cases — generic Jinja2 behavior tests
# ---------------------------------------------------------------------------


def test_qa_render_template_one_sided_conditional(tmp_path: Path) -> None:
    """A {% if %} block with no else renders nothing when condition is false.

    Tests generic Jinja2 conditional behavior, not iEVO.md-specific provider logic.
    """
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text(
        "Common line\n"
        '{% if provider == "claude" %}Claude-specific\n{% endif %}'
        "Trailing line\n"
    )

    codex_result = render_template(
        tmpl, {"cortex_version": "v1.0.0", "provider": "codex"}, tmp_path
    )

    assert "Common line" in codex_result
    assert "Trailing line" in codex_result
    assert "Claude-specific" not in codex_result
    assert "{%" not in codex_result


def test_qa_template_with_only_cortex_version_renders_cleanly(tmp_path: Path) -> None:
    """A template with only {{ cortex_version }} and no provider blocks renders cleanly.

    This mirrors the real iEVO.md use case after REQ-004.
    """
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    tmpl = kernel_dir / "test.md.j2"
    tmpl.write_text(
        "# iEvo Pipeline — version {{ cortex_version }}\nNo provider blocks here.\n"
    )

    result = render_template(tmpl, {"cortex_version": "v1.0.0"}, tmp_path)
    assert "v1.0.0" in result
    assert "{{" not in result
    assert "{%" not in result


# ---------------------------------------------------------------------------
# Tag value edge cases
# ---------------------------------------------------------------------------


def test_qa_empty_tag_renders_empty_version_in_output(tmp_path: Path) -> None:
    """An empty --tag value embeds an empty string for cortex_version without crashing."""
    result = subprocess.run(
        [
            sys.executable,
            str(CORTEX_ROOT / "build.py"),
            "--tag",
            "",
            "--dist",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(CORTEX_ROOT),
    )
    assert result.returncode == 0, f"build.py failed with empty tag:\n{result.stderr}"

    ievo_md = tmp_path / "iEVO.md"
    assert ievo_md.exists(), "dist/iEVO.md missing"

    content = ievo_md.read_text()
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

    ievo_md = tmp_path / "iEVO.md"
    content = ievo_md.read_text()
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
    assert result.returncode == 0, (
        f"build.py failed with special-char tag:\n{result.stderr}"
    )

    ievo_md = tmp_path / "iEVO.md"
    content = ievo_md.read_text()
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
        "# Версия {{ cortex_version }} — café ☕\n",
        encoding="utf-8",
    )

    result = render_template(tmpl, {"cortex_version": "v1.0.0"}, tmp_path)

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
