"""Tests for test CI workflow (REQ-017, Subtask 06).

Validates that .github/workflows/test.yml exists and covers the
required triggers and steps for PR-gated test CI.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEST_YML = REPO_ROOT / ".github" / "workflows" / "test.yml"


def test_test_workflow_exists() -> None:
    """AC-1: .github/workflows/test.yml exists."""
    assert TEST_YML.exists(), f"Expected {TEST_YML} to exist"


def test_test_workflow_triggers_on_push() -> None:
    """AC-2: workflow triggers on push to main."""
    content = TEST_YML.read_text()
    assert "push:" in content, "Missing 'push:' trigger"
    assert "main" in content, "Missing 'main' branch in trigger"


def test_test_workflow_triggers_on_pr() -> None:
    """AC-3: workflow triggers on pull_request."""
    content = TEST_YML.read_text()
    assert "pull_request:" in content, "Missing 'pull_request:' trigger"


def test_test_workflow_runs_pytest() -> None:
    """AC-4: workflow runs pytest."""
    content = TEST_YML.read_text()
    assert "pytest" in content, "Missing 'pytest' step in test.yml"


def test_test_workflow_runs_ruff() -> None:
    """AC-5: workflow runs ruff check."""
    content = TEST_YML.read_text()
    assert "ruff check" in content, "Missing 'ruff check' step in test.yml"
