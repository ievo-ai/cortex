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
