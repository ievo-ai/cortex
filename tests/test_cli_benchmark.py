"""Tests for cortex benchmark CLI commands (Task 026, subtask 03)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from cortex.cli import app

runner = CliRunner()


@pytest.fixture()
def fake_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up fake dist dir with iEVO.md and patch benchmark module paths."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "iEVO.md").write_text("# fake kernel")

    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "SCORES_FILE", tmp_path / "scores.json")

    return dist


def _mock_promptfoo_success(output_path: Path) -> MagicMock:
    """Create a fake promptfoo result that writes valid JSON output."""
    # Write a fake promptfoo output file
    output_path.write_text(json.dumps({
        "results": {
            "results": [
                {"vars": {"dimension": "structure_adherence"}, "success": True},
                {"vars": {"dimension": "challenge_reflex"}, "success": True},
                {"vars": {"dimension": "plan_first"}, "success": False},
                {"vars": {"dimension": "decision_logging"}, "success": True},
                {"vars": {"dimension": "ac_verification"}, "success": True},
                {"vars": {"dimension": "evolution_awareness"}, "success": False},
            ]
        }
    }))
    result = MagicMock()
    result.returncode = 0
    result.stderr = ""
    return result


# ---------------------------------------------------------------------------
# cortex benchmark run
# ---------------------------------------------------------------------------


def test_benchmark_run_seeds_baseline(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """First run seeds baseline scores."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "Baseline seeded" in result.output

    scores = bm.load_scores()
    assert scores is not None
    assert scores.baseline is not None
    assert scores.baseline.scores.structure_adherence == 1.0
    assert scores.baseline.scores.plan_first == 0.0


def test_benchmark_run_updates_existing(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second run updates baseline scores."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    # Seed initial baseline
    from cortex.benchmark import BenchmarkEntry, DimensionScores, ScoresFile
    sf = ScoresFile(baseline=BenchmarkEntry(
        timestamp="t", model="m", kernel_version=None,
        scores=DimensionScores(), overall=0.0,
    ))
    bm.save_scores(sf)

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "Scores updated" in result.output


def test_benchmark_run_missing_dist(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when dist/iEVO.md doesn't exist."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env / "nonexistent")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_benchmark_run_ollama_down(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when Ollama is not reachable."""
    import cortex.benchmark as bm

    def _raise(*a, **kw):
        raise RuntimeError("Ollama not reachable")

    monkeypatch.setattr(bm, "check_ollama", _raise)

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 1
    assert "Ollama not reachable" in result.output


def test_benchmark_run_promptfoo_fail(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when promptfoo eval fails (no output file written)."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    def _fail_promptfoo(p: Path) -> MagicMock:
        # Don't write output file — simulates real failure
        p.unlink(missing_ok=True)
        r = MagicMock()
        r.returncode = 1
        r.stderr = "some error"
        return r

    monkeypatch.setattr(bm, "run_promptfoo", _fail_promptfoo)

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 1
    assert "promptfoo eval failed" in result.output


# ---------------------------------------------------------------------------
# cortex benchmark compare
# ---------------------------------------------------------------------------


def test_benchmark_compare_seeds_on_first_run(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """First compare run seeds baseline, exits 0."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    result = runner.invoke(app, ["benchmark", "compare", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "No prior baseline" in result.output


def test_benchmark_compare_passes(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Compare passes when current >= baseline."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    # Seed a low baseline
    from cortex.benchmark import BenchmarkEntry, DimensionScores, ScoresFile
    sf = ScoresFile(baseline=BenchmarkEntry(
        timestamp="t", model="m", kernel_version=None,
        scores=DimensionScores(), overall=0.1,
    ))
    bm.save_scores(sf)

    result = runner.invoke(app, ["benchmark", "compare", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "PASSED" in result.output


def test_benchmark_compare_regression(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Compare exits 1 on regression."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_ollama", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    # Seed a high baseline — mock scores will be lower
    from cortex.benchmark import BenchmarkEntry, DimensionScores, ScoresFile
    sf = ScoresFile(baseline=BenchmarkEntry(
        timestamp="t", model="m", kernel_version=None,
        scores=DimensionScores(
            structure_adherence=1.0, challenge_reflex=1.0, plan_first=1.0,
            decision_logging=1.0, ac_verification=1.0, evolution_awareness=1.0,
        ), overall=1.0,
    ))
    bm.save_scores(sf)

    result = runner.invoke(app, ["benchmark", "compare", "--dist", str(fake_env)])
    assert result.exit_code == 1
    assert "REGRESSED" in result.output
