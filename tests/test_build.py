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


# ---------------------------------------------------------------------------
# Step 1: render_template helper unit tests
# ---------------------------------------------------------------------------

import jinja2  # noqa: E402 — imported here for test isolation clarity

from build import render_template  # noqa: E402


def test_render_template_substitutes_variables(tmp_path: Path) -> None:
    """render_template() substitutes {{ cortex_version }} and {{ provider }} correctly."""
    template_file = tmp_path / "kernel" / "test.md.j2"
    template_file.parent.mkdir(parents=True)
    template_file.write_text(
        "Cortex {{ cortex_version }} — provider: {{ provider }}\n"
    )

    result = render_template(template_file, {"cortex_version": "v1.2.0", "provider": "claude"})

    assert "v1.2.0" in result
    assert "claude" in result
    assert "{{" not in result


def test_render_template_strict_undefined_raises(tmp_path: Path) -> None:
    """render_template() raises jinja2.UndefinedError for unknown variables."""
    template_file = tmp_path / "kernel" / "test.md.j2"
    template_file.parent.mkdir(parents=True)
    template_file.write_text("Version: {{ undefined_var }}\n")

    import pytest

    with pytest.raises(jinja2.UndefinedError):
        render_template(template_file, {"cortex_version": "v1.0.0", "provider": "claude"})


# ---------------------------------------------------------------------------
# Step 2: Template source file tests (AC-1)
# ---------------------------------------------------------------------------


def test_template_source_exists() -> None:
    """src/kernel/iEVO.md.j2 exists and is parseable by Jinja2."""
    template_path = CORTEX_ROOT / "src" / "kernel" / "iEVO.md.j2"
    assert template_path.exists(), f"Template not found: {template_path}"

    env = jinja2.Environment()
    source = template_path.read_text()
    env.parse(source)  # raises TemplateSyntaxError if invalid


def test_template_contains_required_variables() -> None:
    """iEVO.md.j2 contains {{ cortex_version }} and at least one provider conditional."""
    template_path = CORTEX_ROOT / "src" / "kernel" / "iEVO.md.j2"
    source = template_path.read_text()

    assert "{{ cortex_version }}" in source, "Missing {{ cortex_version }} placeholder"
    assert '{% if provider ==' in source, "Missing {% if provider == ... %} conditional block"


# ---------------------------------------------------------------------------
# Step 3: Integration tests — build wires render_template into targets (AC-2, AC-3, AC-4)
# ---------------------------------------------------------------------------


def test_build_claude_ievo_contains_version(tmp_path: Path) -> None:
    """dist/claude/iEVO.md contains the version tag and no unrendered Jinja2 syntax."""
    result = run_build(tmp_path, tag="v1.2.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    ievo_md = tmp_path / "claude" / "iEVO.md"
    assert ievo_md.exists(), "dist/claude/iEVO.md not found"
    content = ievo_md.read_text()

    assert "v1.2.0" in content, "Version tag not found in dist/claude/iEVO.md"
    assert "{{" not in content, "Unrendered {{ in dist/claude/iEVO.md"
    assert "{%" not in content, "Unrendered {% in dist/claude/iEVO.md"


def test_build_codex_ievo_contains_version(tmp_path: Path) -> None:
    """dist/codex/iEVO.md contains the version tag and no unrendered Jinja2 syntax."""
    result = run_build(tmp_path, tag="v1.2.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    ievo_md = tmp_path / "codex" / "iEVO.md"
    assert ievo_md.exists(), "dist/codex/iEVO.md not found"
    content = ievo_md.read_text()

    assert "v1.2.0" in content, "Version tag not found in dist/codex/iEVO.md"
    assert "{{" not in content, "Unrendered {{ in dist/codex/iEVO.md"
    assert "{%" not in content, "Unrendered {% in dist/codex/iEVO.md"


def test_build_provider_specific_content_claude_only(tmp_path: Path) -> None:
    """CLAUDE_ONLY sentinel appears only in dist/claude/iEVO.md, not in dist/codex/iEVO.md."""
    result = run_build(tmp_path, tag="v1.0.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    claude_content = (tmp_path / "claude" / "iEVO.md").read_text()
    codex_content = (tmp_path / "codex" / "iEVO.md").read_text()

    assert "CLAUDE_ONLY" in claude_content, "CLAUDE_ONLY sentinel missing from dist/claude/iEVO.md"
    assert "CLAUDE_ONLY" not in codex_content, "CLAUDE_ONLY sentinel leaked into dist/codex/iEVO.md"


def test_build_provider_specific_content_codex_only(tmp_path: Path) -> None:
    """CODEX_ONLY sentinel appears only in dist/codex/iEVO.md, not in dist/claude/iEVO.md."""
    result = run_build(tmp_path, tag="v1.0.0")
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"

    claude_content = (tmp_path / "claude" / "iEVO.md").read_text()
    codex_content = (tmp_path / "codex" / "iEVO.md").read_text()

    assert "CODEX_ONLY" in codex_content, "CODEX_ONLY sentinel missing from dist/codex/iEVO.md"
    assert "CODEX_ONLY" not in claude_content, "CODEX_ONLY sentinel leaked into dist/claude/iEVO.md"


# ---------------------------------------------------------------------------
# Step 4: Error handling + idempotency tests (AC-5, AC-6, AC-7)
# ---------------------------------------------------------------------------


def test_build_fails_on_missing_template(tmp_path: Path) -> None:
    """build.py exits non-zero and mentions iEVO.md.j2 when template is missing."""
    import os
    import shutil

    # Copy cortex source to a temp dir so we can remove the template
    build_dir = tmp_path / "cortex_src"
    shutil.copytree(CORTEX_ROOT, build_dir, ignore=shutil.ignore_patterns(".venv", "dist", "__pycache__", ".git"))

    template = build_dir / "src" / "kernel" / "iEVO.md.j2"
    template.unlink()

    dist_dir = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, str(build_dir / "build.py"), "--tag", "v1.0.0", "--dist", str(dist_dir)],
        capture_output=True,
        text=True,
        cwd=str(build_dir),
        env={**os.environ, "PYTHONPATH": str(build_dir)},
    )

    assert result.returncode != 0, "Expected non-zero exit when template is missing"
    assert "iEVO.md.j2" in result.stderr, f"Expected iEVO.md.j2 in stderr, got:\n{result.stderr}"

    tarballs = list(dist_dir.glob("cortex-*.tar.gz")) if dist_dir.exists() else []
    assert not tarballs, f"No tarball should be created on error, found: {tarballs}"


def test_build_fails_on_undefined_variable(tmp_path: Path) -> None:
    """build.py exits non-zero and mentions the undefined var when template has unknown var."""
    import os
    import shutil

    # Copy cortex source to a temp dir so we can inject a bad template
    build_dir = tmp_path / "cortex_src"
    shutil.copytree(CORTEX_ROOT, build_dir, ignore=shutil.ignore_patterns(".venv", "dist", "__pycache__", ".git"))

    template = build_dir / "src" / "kernel" / "iEVO.md.j2"
    template.write_text("Version: {{ undefined_var }}\n")

    dist_dir = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, str(build_dir / "build.py"), "--tag", "v1.0.0", "--dist", str(dist_dir)],
        capture_output=True,
        text=True,
        cwd=str(build_dir),
        env={**os.environ, "PYTHONPATH": str(build_dir)},
    )

    assert result.returncode != 0, "Expected non-zero exit on undefined variable"
    assert "undefined_var" in result.stderr, f"Expected undefined_var in stderr, got:\n{result.stderr}"

    tarballs = list(dist_dir.glob("cortex-*.tar.gz")) if dist_dir.exists() else []
    assert not tarballs, f"No tarball should be created on error, found: {tarballs}"


def test_build_idempotent_rendered_content(tmp_path: Path) -> None:
    """Running build.py twice produces byte-identical iEVO.md files in both providers."""
    run_build(tmp_path, tag="v1.2.0")
    claude_first = (tmp_path / "claude" / "iEVO.md").read_bytes()
    codex_first = (tmp_path / "codex" / "iEVO.md").read_bytes()

    run_build(tmp_path, tag="v1.2.0")
    claude_second = (tmp_path / "claude" / "iEVO.md").read_bytes()
    codex_second = (tmp_path / "codex" / "iEVO.md").read_bytes()

    assert claude_first == claude_second, "dist/claude/iEVO.md differs between runs"
    assert codex_first == codex_second, "dist/codex/iEVO.md differs between runs"


def test_render_template_provider_conditional(tmp_path: Path) -> None:
    """render_template() includes/excludes content based on provider conditional."""
    template_file = tmp_path / "kernel" / "test.md.j2"
    template_file.parent.mkdir(parents=True)
    template_file.write_text(
        "{% if provider == \"claude\" %}CLAUDE_ONLY{% endif %}\n"
        "{% if provider == \"codex\" %}CODEX_ONLY{% endif %}\n"
    )

    claude_result = render_template(template_file, {"cortex_version": "v1.0.0", "provider": "claude"})
    codex_result = render_template(template_file, {"cortex_version": "v1.0.0", "provider": "codex"})

    assert "CLAUDE_ONLY" in claude_result
    assert "CODEX_ONLY" not in claude_result
    assert "CODEX_ONLY" in codex_result
    assert "CLAUDE_ONLY" not in codex_result
