"""Tests for cortex compile module.

TDD: tests written before cortex/compile.py is implemented.
"""

from __future__ import annotations

import tarfile
from pathlib import Path
from unittest.mock import patch

import jinja2
import pytest

from cortex.compile import build, render_template


CORTEX_ROOT = Path(__file__).parent.parent


def test_build_creates_tarball(tmp_path: Path) -> None:
    """build() creates cortex-<tag>.tar.gz in the dist directory."""
    tarball = build(tag="v1.0.0", dist_dir=tmp_path)
    assert tarball.exists(), f"Expected {tarball} but found: {list(tmp_path.iterdir())}"
    assert tarball.name == "cortex-v1.0.0.tar.gz"


def test_tarball_contains_both_providers(tmp_path: Path) -> None:
    """The release asset, when unpacked, contains both claude/ and codex/ directories."""
    build(tag="v1.0.0", dist_dir=tmp_path)

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    # Must have at least one file under claude/ and at least the codex placeholder
    claude_files = [n for n in names if n.startswith("claude/")]
    codex_files = [n for n in names if n.startswith("codex/")]

    assert claude_files, f"No claude/ entries in tarball. Names: {names}"
    assert codex_files, f"No codex/ entries in tarball. Names: {names}"


def test_tarball_contains_ievo_md_at_root(tmp_path: Path) -> None:
    """The tarball contains iEVO.md at root level — not under a provider subdirectory (AC-4)."""
    build(tag="v1.0.0", dist_dir=tmp_path)

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "iEVO.md" in names, f"iEVO.md missing at root of tarball. Names: {names}"
    assert "claude/iEVO.md" not in names, (
        f"claude/iEVO.md should not be in tarball. Names: {names}"
    )
    assert "codex/iEVO.md" not in names, (
        f"codex/iEVO.md should not be in tarball. Names: {names}"
    )


def test_tarball_codex_contains_build_target_md(tmp_path: Path) -> None:
    """The codex/ directory contains BUILD_TARGET.md (placeholder for v1)."""
    build(tag="v1.0.0", dist_dir=tmp_path)

    tarball = tmp_path / "cortex-v1.0.0.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "codex/BUILD_TARGET.md" in names, (
        f"codex/BUILD_TARGET.md missing. Names: {names}"
    )


def test_build_idempotent(tmp_path: Path) -> None:
    """Running build() twice produces identical tarballs (same member names)."""
    build(tag="v1.0.0", dist_dir=tmp_path)
    tarball = tmp_path / "cortex-v1.0.0.tar.gz"

    with tarfile.open(tarball, "r:gz") as tf:
        names_first = sorted(tf.getnames())

    # Run again (overwrites)
    build(tag="v1.0.0", dist_dir=tmp_path)

    with tarfile.open(tarball, "r:gz") as tf:
        names_second = sorted(tf.getnames())

    assert names_first == names_second, (
        f"Build not idempotent.\nFirst:  {names_first}\nSecond: {names_second}"
    )


def test_build_uses_provided_tag(tmp_path: Path) -> None:
    """build() embeds the tag value in the output filename."""
    tarball = build(tag="v2.3.4", dist_dir=tmp_path)
    assert tarball.name == "cortex-v2.3.4.tar.gz"
    assert tarball.exists(), (
        f"Expected cortex-v2.3.4.tar.gz but found: {list(tmp_path.iterdir())}"
    )


# ---------------------------------------------------------------------------
# Step 1: render_template helper unit tests
# ---------------------------------------------------------------------------


def test_render_template_substitutes_variables(tmp_path: Path) -> None:
    """render_template() substitutes {{ cortex_version }} correctly."""
    template_file = tmp_path / "kernel" / "test.md.j2"
    template_file.parent.mkdir(parents=True)
    template_file.write_text("Cortex {{ cortex_version }}\n")

    result = render_template(template_file, {"cortex_version": "v1.2.0"})

    assert "v1.2.0" in result
    assert "{{" not in result


def test_render_template_strict_undefined_raises(tmp_path: Path) -> None:
    """render_template() raises jinja2.UndefinedError for unknown variables."""
    template_file = tmp_path / "kernel" / "test.md.j2"
    template_file.parent.mkdir(parents=True)
    template_file.write_text("Version: {{ undefined_var }}\n")

    with pytest.raises(jinja2.UndefinedError):
        render_template(template_file, {"cortex_version": "v1.0.0"})


# ---------------------------------------------------------------------------
# Step 2: Template source file tests (AC-1)
# ---------------------------------------------------------------------------


def test_template_source_exists() -> None:
    """templates/kernel/consciousness.md.j2 exists and is parseable by Jinja2."""
    template_path = CORTEX_ROOT / "templates" / "kernel" / "consciousness.md.j2"
    assert template_path.exists(), f"Template not found: {template_path}"

    env = jinja2.Environment()
    source = template_path.read_text()
    env.parse(source)  # raises TemplateSyntaxError if invalid


def test_template_contains_required_variables() -> None:
    """consciousness.md.j2 contains {{ cortex_version }} and no provider Jinja2 references (AC-1)."""
    template_path = CORTEX_ROOT / "templates" / "kernel" / "consciousness.md.j2"
    source = template_path.read_text()

    assert "{{ cortex_version }}" in source, "Missing {{ cortex_version }} placeholder"
    assert "{{ provider }}" not in source, (
        "Template must not use {{ provider }} variable"
    )
    assert "{% if provider" not in source, (
        "Template must not use {% if provider %} blocks"
    )


# ---------------------------------------------------------------------------
# Step 3: Integration tests — build wires render_template into targets (AC-2, AC-3, AC-4)
# ---------------------------------------------------------------------------


def test_build_ievo_md_contains_version(tmp_path: Path) -> None:
    """dist/iEVO.md contains the version tag and no unrendered Jinja2 syntax (AC-2)."""
    build(tag="v1.2.0", dist_dir=tmp_path)

    ievo_md = tmp_path / "iEVO.md"
    assert ievo_md.exists(), "dist/iEVO.md not found"
    content = ievo_md.read_text()

    assert "v1.2.0" in content, "Version tag not found in dist/iEVO.md"
    assert "{{" not in content, "Unrendered {{ in dist/iEVO.md"
    assert "{%" not in content, "Unrendered {% in dist/iEVO.md"


def test_build_no_provider_ievo_md_in_subdirs(tmp_path: Path) -> None:
    """dist/claude/iEVO.md and dist/codex/iEVO.md must NOT exist after build (AC-3)."""
    build(tag="v2.0.0", dist_dir=tmp_path)

    assert not (tmp_path / "claude" / "iEVO.md").exists(), (
        "dist/claude/iEVO.md must not be created"
    )
    assert not (tmp_path / "codex" / "iEVO.md").exists(), (
        "dist/codex/iEVO.md must not be created"
    )


# ---------------------------------------------------------------------------
# Step 4: Error handling + idempotency tests (AC-5, AC-6, AC-7)
# ---------------------------------------------------------------------------


def test_build_fails_on_missing_template(tmp_path: Path) -> None:
    """build() raises FileNotFoundError when the template file is missing."""

    # Temporarily point IEVO_MD_TEMPLATE to a non-existent path
    fake_template = tmp_path / "nonexistent" / "consciousness.md.j2"
    with patch("cortex.compile.IEVO_MD_TEMPLATE", fake_template):
        with pytest.raises(FileNotFoundError, match="consciousness.md.j2"):
            build(tag="v1.0.0", dist_dir=tmp_path / "dist")

    tarballs = list((tmp_path / "dist").glob("cortex-*.tar.gz")) if (tmp_path / "dist").exists() else []
    assert not tarballs, f"No tarball should be created on error, found: {tarballs}"


def test_build_fails_on_undefined_variable(tmp_path: Path) -> None:
    """build() raises jinja2.UndefinedError when template has unknown variable."""
    # Create a bad template under a structure that matches the loader_root expectation
    templates_dir = tmp_path / "templates"
    bad_template = templates_dir / "kernel" / "consciousness.md.j2"
    bad_template.parent.mkdir(parents=True)
    bad_template.write_text("Version: {{ undefined_var }}\n")

    with (
        patch("cortex.compile.IEVO_MD_TEMPLATE", bad_template),
        patch("cortex.compile.CORTEX_ROOT", tmp_path),
    ):
        with pytest.raises(jinja2.UndefinedError, match="undefined_var"):
            build(tag="v1.0.0", dist_dir=tmp_path / "dist")

    tarballs = list((tmp_path / "dist").glob("cortex-*.tar.gz")) if (tmp_path / "dist").exists() else []
    assert not tarballs, f"No tarball should be created on error, found: {tarballs}"


def test_build_idempotent_rendered_content(tmp_path: Path) -> None:
    """Running build() twice produces byte-identical dist/iEVO.md (AC-6)."""
    build(tag="v1.2.0", dist_dir=tmp_path)
    first = (tmp_path / "iEVO.md").read_bytes()

    build(tag="v1.2.0", dist_dir=tmp_path)
    second = (tmp_path / "iEVO.md").read_bytes()

    assert first == second, "dist/iEVO.md differs between runs"


def test_build_ievo_render_context_has_no_provider(tmp_path: Path) -> None:
    """The render call for consciousness.md.j2 in compile.py passes only cortex_version (AC-5)."""
    import cortex.compile as build_module

    captured_contexts: list[dict[str, str]] = []
    original_render = build_module.render_template

    def capturing_render(
        template_path: Path, context: dict[str, str], loader_root: Path | None = None
    ) -> str:
        if template_path.name == "consciousness.md.j2":
            captured_contexts.append(dict(context))
        return original_render(template_path, context, loader_root)

    with patch.object(build_module, "render_template", side_effect=capturing_render):
        build_module.build(tag="v2.0.0", dist_dir=tmp_path)

    assert captured_contexts, "render_template was never called for consciousness.md.j2"
    assert len(captured_contexts) == 1, (
        f"render_template called {len(captured_contexts)} times for consciousness.md.j2, expected 1"
    )
    ctx = captured_contexts[0]
    assert "provider" not in ctx, (
        f"'provider' key found in iEVO.md render context: {ctx}"
    )
    assert "cortex_version" in ctx, f"'cortex_version' missing from context: {ctx}"
