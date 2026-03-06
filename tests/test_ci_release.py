"""Tests for updated CI release.yml workflow (REQ-017, Subtask 04).

TDD: tests written before implementation.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"


def test_ci_uses_cortex_compile() -> None:
    """release.yml contains 'cortex compile' (not 'python build.py')."""
    content = RELEASE_YML.read_text()
    assert "cortex compile" in content, (
        f"Expected 'cortex compile' in release.yml:\n{content}"
    )


def test_ci_no_python_build_py() -> None:
    """release.yml does NOT contain 'python build.py'."""
    content = RELEASE_YML.read_text()
    assert "python build.py" not in content, (
        "release.yml still references 'python build.py' — should use 'cortex compile'"
    )


def test_ci_has_uv_build_step() -> None:
    """release.yml contains 'uv build' step for Python package build."""
    content = RELEASE_YML.read_text()
    assert "uv build" in content, "Expected 'uv build' step in release.yml"


def test_ci_has_pypi_publish_action() -> None:
    """release.yml uses pypa/gh-action-pypi-publish for OIDC trusted publisher (REQ-022 AC-3, AC-5).
    Replaces 'uv publish' + PYPI_TOKEN secret with OIDC publishing.
    """
    content = RELEASE_YML.read_text()
    assert "pypa/gh-action-pypi-publish" in content, (
        "Expected 'pypa/gh-action-pypi-publish' in release.yml (OIDC trusted publisher)"
    )
    assert "uv publish" not in content, (
        "release.yml still uses 'uv publish' — should use pypa/gh-action-pypi-publish"
    )
    assert "PYPI_TOKEN" not in content, (
        "release.yml still references PYPI_TOKEN secret — should use OIDC (no secret needed)"
    )


def test_ci_has_oidc_permissions() -> None:
    """release.yml has id-token: write permission for OIDC (REQ-022 AC-4)."""
    content = RELEASE_YML.read_text()
    assert "id-token: write" in content, (
        "release.yml missing 'id-token: write' permission required for OIDC publishing"
    )
    assert "contents: write" in content, (
        "release.yml missing 'contents: write' permission required for gh release create"
    )


def test_ci_has_version_bump() -> None:
    """release.yml contains 'version_bump.py' step."""
    content = RELEASE_YML.read_text()
    assert "version_bump.py" in content, "Expected 'version_bump.py' in release.yml"


def test_ci_keeps_lychee_validation() -> None:
    """release.yml still has lychee install + validation steps."""
    content = RELEASE_YML.read_text()
    assert "lychee" in content, "release.yml missing lychee validation"
    assert "install lychee" in content.lower() or "Install lychee" in content, (
        "release.yml missing lychee install step"
    )


def test_ci_triggers_on_branch_push() -> None:
    """release.yml triggers on push to branches: main (NOT push: tags:)."""
    content = RELEASE_YML.read_text()
    assert "branches:" in content, "release.yml missing 'branches:' trigger"
    assert "main" in content, "release.yml missing 'main' branch in trigger"


def test_ci_no_tag_trigger() -> None:
    """release.yml does NOT contain 'tags:' trigger."""
    content = RELEASE_YML.read_text()
    # Should not have tags trigger in `on:` section
    assert "push:\n    tags:" not in content and "push:\n      tags:" not in content, (
        "release.yml still has tag-push trigger — should be branch-push"
    )
