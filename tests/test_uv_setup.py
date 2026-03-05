"""Tests for uv project setup (REQ-015)."""

import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


# --- Subtask 02: pyproject.toml build-system + dev extras ---


def test_pyproject_has_build_system() -> None:
    """AC-1: pyproject.toml has [build-system] table with hatchling."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)

    assert "build-system" in data, "Missing [build-system] table"
    build_system = data["build-system"]
    assert "requires" in build_system, "Missing build-system.requires"
    assert "hatchling" in build_system["requires"], (
        "hatchling not in build-system.requires"
    )
    assert build_system.get("build-backend") == "hatchling.build", (
        "build-backend should be 'hatchling.build'"
    )


def test_pyproject_dev_extras() -> None:
    """AC-2: pyproject.toml has dev extras with pytest, ruff, mypy."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)

    optional = data.get("project", {}).get("optional-dependencies", {})
    assert "dev" in optional, "Missing 'dev' in optional-dependencies"
    dev_deps = optional["dev"]
    assert any(d.startswith("pytest") for d in dev_deps), (
        "pytest not in dev extras"
    )
    assert any(d.startswith("ruff") for d in dev_deps), "ruff not in dev extras"
    assert any(d.startswith("mypy") for d in dev_deps), "mypy not in dev extras"


# --- Subtask 04: CI migration to uv ---


def test_ci_no_pip_install() -> None:
    """AC-5: CI release.yml does not use pip install."""
    ci_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    content = ci_path.read_text()
    assert "pip install" not in content, "CI still uses 'pip install'"


def test_ci_uses_setup_uv() -> None:
    """AC-6: CI uses astral-sh/setup-uv action."""
    ci_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    content = ci_path.read_text()
    assert "astral-sh/setup-uv" in content, "CI does not use astral-sh/setup-uv"


def test_ci_uses_uv_sync_frozen() -> None:
    """AC-5: CI uses uv sync --frozen to install deps."""
    ci_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    content = ci_path.read_text()
    assert "uv sync --frozen" in content, "CI does not use 'uv sync --frozen'"


def test_ci_uses_uv_run_for_build() -> None:
    """AC-5: CI uses uv run python build.py for the build step."""
    ci_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    content = ci_path.read_text()
    assert "uv run python build.py" in content, (
        "CI does not use 'uv run python build.py'"
    )


# --- Subtask 03: uv.lock regeneration + uv sync verification ---


def test_uv_lock_exists() -> None:
    """AC-3: uv.lock exists at repo root."""
    assert (REPO_ROOT / "uv.lock").exists(), "uv.lock not found at repo root"


def test_uv_lock_contains_cortex_entry() -> None:
    """AC-3: uv.lock contains a cortex package entry (reproducible install)."""
    content = (REPO_ROOT / "uv.lock").read_text()
    assert 'name = "cortex"' in content, (
        "uv.lock does not contain cortex package entry"
    )


def test_uv_lock_has_dev_deps() -> None:
    """AC-3: uv.lock resolves dev extras (ruff, mypy in lock)."""
    content = (REPO_ROOT / "uv.lock").read_text()
    assert 'name = "ruff"' in content, "ruff not resolved in uv.lock"
    assert 'name = "mypy"' in content, "mypy not resolved in uv.lock"


def test_uv_run_pytest_passes() -> None:
    """AC-4: uv run pytest tests/ passes — no regressions (excludes this file)."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "tests/",
            "--ignore=tests/test_uv_setup.py",
            "--tb=short",
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"uv run pytest failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# --- Subtask 05: End-to-end smoke test ---


def test_uv_run_build_produces_tarball(tmp_path: Path) -> None:
    """AC-7: uv run python build.py --tag v0.0.1 produces dist/cortex-v0.0.1.tar.gz."""
    result = subprocess.run(
        ["uv", "run", "python", "build.py", "--tag", "v0.0.1", "--dist", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"build.py failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    tarball = tmp_path / "cortex-v0.0.1.tar.gz"
    assert tarball.exists(), f"Expected tarball not found: {tarball}"
