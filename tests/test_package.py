"""Tests for cortex Python package structure (REQ-017, Subtask 01).

TDD: tests written before implementation.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# 1. Package importability + __version__
# ---------------------------------------------------------------------------


def test_package_importable() -> None:
    """import cortex succeeds, cortex.__version__ is a string."""
    import cortex  # noqa: PLC0415

    assert isinstance(cortex.__version__, str), (
        f"cortex.__version__ must be a string, got {type(cortex.__version__)}"
    )
    assert len(cortex.__version__) > 0, "cortex.__version__ must not be empty"


# ---------------------------------------------------------------------------
# 2-5. validate_links() returns int — NOT sys.exit()
# ---------------------------------------------------------------------------


def test_validate_links_returns_int_on_failure() -> None:
    """cortex.compile.validate_links() returns int, does NOT raise SystemExit."""
    from cortex.compile import validate_links  # noqa: PLC0415

    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = "broken: ./missing.md"
    mock_result.stderr = "1 broken link found"

    with (
        patch("cortex.compile.shutil.which", return_value="/usr/local/bin/lychee"),
        patch("cortex.compile.subprocess.run", return_value=mock_result),
    ):
        rc = validate_links(Path("/tmp/dist"))

    assert isinstance(rc, int), f"Expected int, got {type(rc)}"
    assert rc == 2, f"Expected rc=2, got {rc}"


def test_validate_links_returns_zero_when_lychee_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When lychee is absent, validate_links() warns to stderr + returns 0."""
    from cortex.compile import validate_links  # noqa: PLC0415

    with patch("cortex.compile.shutil.which", return_value=None):
        rc = validate_links(tmp_path)

    assert rc == 0, f"Expected rc=0 when lychee missing, got {rc}"
    captured = capsys.readouterr()
    assert "lychee" in captured.err.lower(), (
        f"Expected lychee warning in stderr, got: {captured.err!r}"
    )


def test_validate_links_returns_zero_when_lychee_passes(tmp_path: Path) -> None:
    """When lychee exits 0, validate_links() returns 0."""
    from cortex.compile import validate_links  # noqa: PLC0415

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("cortex.compile.shutil.which", return_value="/usr/local/bin/lychee"),
        patch("cortex.compile.subprocess.run", return_value=mock_result),
    ):
        rc = validate_links(tmp_path)

    assert rc == 0, f"Expected rc=0 when lychee passes, got {rc}"


def test_validate_links_returns_lychee_exit_code_on_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When lychee exits with non-zero, validate_links() returns that code + writes to stderr."""
    from cortex.compile import validate_links  # noqa: PLC0415

    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = "BROKEN: ./missing.md"
    mock_result.stderr = "1 broken link"

    with (
        patch("cortex.compile.shutil.which", return_value="/usr/local/bin/lychee"),
        patch("cortex.compile.subprocess.run", return_value=mock_result),
    ):
        rc = validate_links(tmp_path)

    assert rc == 2, f"Expected rc=2, got {rc}"
    captured = capsys.readouterr()
    assert len(captured.err) > 0, "Expected stderr output when lychee fails"


# ---------------------------------------------------------------------------
# 6-7. build() — returns Path, does NOT call validate_links
# ---------------------------------------------------------------------------


def test_build_returns_path_no_sysexit(tmp_path: Path) -> None:
    """build() returns a Path (tarball), no SystemExit raised."""
    from cortex.compile import build  # noqa: PLC0415

    result = build(tag="v1.0.0", dist_dir=tmp_path)

    assert isinstance(result, Path), f"Expected Path, got {type(result)}"
    assert result.exists(), f"Tarball {result} does not exist"


def test_build_does_not_call_validate(tmp_path: Path) -> None:
    """build() does NOT call validate_links() — pure compilation step."""
    from cortex import compile as compile_module  # noqa: PLC0415

    with patch.object(compile_module, "validate_links") as mock_validate:
        compile_module.build(tag="v1.0.0", dist_dir=tmp_path)

    mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# 8. scripts/version_bump.py exists and is valid Python
# ---------------------------------------------------------------------------


def test_version_bump_script_exists() -> None:
    """scripts/version_bump.py exists and is syntactically valid Python."""
    script = REPO_ROOT / "scripts" / "version_bump.py"
    assert script.exists(), f"scripts/version_bump.py not found at {script}"

    # Parse to verify syntax
    source = script.read_text()
    ast.parse(source)  # raises SyntaxError if invalid


# ---------------------------------------------------------------------------
# 9-11. pyproject.toml structure
# ---------------------------------------------------------------------------


def test_pyproject_has_scripts_entry() -> None:
    """pyproject.toml has [project.scripts] cortex = 'cortex.cli:app'."""
    import tomllib  # noqa: PLC0415

    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert "cortex" in scripts, f"Missing 'cortex' in [project.scripts]: {scripts}"
    assert scripts["cortex"] == "cortex.cli:app", (
        f"Expected 'cortex.cli:app', got {scripts['cortex']!r}"
    )


def test_pyproject_has_hatch_version() -> None:
    """[tool.hatch.version] path points to cortex/version.py."""
    import tomllib  # noqa: PLC0415

    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)

    hatch_version = data.get("tool", {}).get("hatch", {}).get("version", {})
    assert "path" in hatch_version, f"Missing path in [tool.hatch.version]: {hatch_version}"
    assert "cortex/version.py" in hatch_version["path"], (
        f"Expected cortex/version.py in hatch version path, got {hatch_version['path']!r}"
    )


def test_pyproject_dynamic_version() -> None:
    """pyproject.toml has dynamic = ['version'], no static version field in [project]."""
    import tomllib  # noqa: PLC0415

    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    dynamic = project.get("dynamic", [])
    assert "version" in dynamic, f"'version' not in dynamic: {dynamic}"
    assert "version" not in project or project.get("version") is None, (
        "Static version field should not exist when using dynamic version"
    )


# ---------------------------------------------------------------------------
# 12. backward-compat build.py removed (task 021)
# ---------------------------------------------------------------------------


def test_build_py_wrapper_removed() -> None:
    """build.py backward-compat wrapper has been deleted (task 021).

    All callers have migrated to `uv run cortex compile`. The wrapper is dead code.
    """
    build_py = REPO_ROOT / "build.py"
    assert not build_py.exists(), (
        "build.py backward-compat wrapper must be deleted. "
        "All callers now use `uv run cortex compile`."
    )
