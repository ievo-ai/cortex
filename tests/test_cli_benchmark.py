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
    monkeypatch.setattr(bm, "RUNS_LOG", tmp_path / "runs.jsonl")

    return dist


def _mock_promptfoo_success(output_path: Path) -> MagicMock:
    """Create a fake promptfoo result that writes valid JSON output."""
    output_path.write_text(json.dumps({
        "results": {
            "results": [
                # baseline (naked) — mostly fails
                {"provider": {"label": "baseline"}, "vars": {"dimension": "structure_adherence"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "challenge_reflex"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "plan_first"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "decision_logging"}, "success": True},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "ac_verification"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "evolution_awareness"}, "success": False},
                # with-kernel — better scores
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "structure_adherence"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "challenge_reflex"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "plan_first"}, "success": False},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "decision_logging"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "ac_verification"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "evolution_awareness"}, "success": False},
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
    """First run seeds baseline and shows comparison table."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "Baseline seeded" in result.output
    assert "Naked" in result.output
    assert "Kernel" in result.output

    scores = bm.load_scores()
    assert scores is not None
    assert scores.baseline is not None
    assert scores.naked is not None
    # Kernel scores
    assert scores.baseline.scores.structure_adherence == 1.0
    assert scores.baseline.scores.plan_first == 0.0
    # Naked scores
    assert scores.naked.scores.structure_adherence == 0.0
    assert scores.naked.scores.decision_logging == 1.0


def test_benchmark_run_updates_existing(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second run updates scores."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    # Seed initial
    from cortex.benchmark import BenchmarkEntry, DimensionScores, ScoresFile
    sf = ScoresFile(baseline=BenchmarkEntry(
        timestamp="t", model="m", kernel_version=None,
        scores=DimensionScores(), overall=0.0,
    ))
    bm.save_scores(sf)

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "Scores updated" in result.output


def test_benchmark_run_appends_log(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each run appends to runs.jsonl."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])

    log_path = fake_env.parent / "runs.jsonl"
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert "naked" in entry
    assert "kernel" in entry
    assert "delta" in entry


def test_benchmark_run_missing_dist(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when dist/iEVO.md doesn't exist."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env / "nonexistent")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_benchmark_run_no_api_key(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when ANTHROPIC_API_KEY is not set."""
    import cortex.benchmark as bm

    def _raise(*a, **kw):
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    monkeypatch.setattr(bm, "check_api_key", _raise)

    result = runner.invoke(app, ["benchmark", "run", "--dist", str(fake_env)])
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY not set" in result.output


def test_benchmark_run_promptfoo_fail(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when promptfoo eval fails (no output file written)."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    def _fail_promptfoo(p: Path) -> MagicMock:
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

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    result = runner.invoke(app, ["benchmark", "compare", "--dist", str(fake_env)])
    assert result.exit_code == 0
    assert "No prior baseline" in result.output


def test_benchmark_compare_passes(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Compare passes when current >= baseline."""
    import cortex.benchmark as bm

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
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

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", lambda p: _mock_promptfoo_success(p))

    # Seed a high baseline — mock kernel scores will be lower (overall ~0.67)
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
