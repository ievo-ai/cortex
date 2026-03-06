"""Tests for cortex benchmark CLI commands (Task 026, subtask 03 + Task 028)."""

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


# ---------------------------------------------------------------------------
# Subtask 02: cortex benchmark agent
# ---------------------------------------------------------------------------


def _mock_agent_promptfoo_success(output_path: Path, config_path: Path | None = None) -> MagicMock:
    """Fake run_promptfoo for agent benchmark (uses with-kernel provider label)."""
    output_path.write_text(json.dumps({
        "results": {
            "results": [
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


@pytest.fixture()
def fake_env_with_overlay(fake_env: Path, tmp_path: Path) -> tuple[Path, Path]:
    """Extend fake_env with a compiled dist/iEVO.md and a fake overlay file."""
    # dist/iEVO.md is already created by fake_env
    overlay = tmp_path / "spec-writer.md"
    overlay.write_text("# Spec Writer overlay\nAlways challenge first.")
    return fake_env, overlay


def test_benchmark_agent_help() -> None:
    """cortex benchmark agent --help exits 0."""
    result = runner.invoke(app, ["benchmark", "agent", "--help"])
    assert result.exit_code == 0
    assert "overlay" in result.output.lower() or "path" in result.output.lower()


def test_benchmark_agent_missing_dist(fake_env_with_overlay: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when dist/iEVO.md doesn't exist."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    _, overlay = fake_env_with_overlay
    result = runner.invoke(app, ["benchmark", "agent", str(overlay), "--dist", "/nonexistent/dist"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_benchmark_agent_missing_overlay(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when overlay file doesn't exist."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    result = runner.invoke(app, ["benchmark", "agent", "/nonexistent/overlay.md", "--dist", str(fake_env)])
    assert result.exit_code == 1
    assert "overlay file not found" in result.output.lower()


def test_benchmark_agent_runs_and_prints_table(
    fake_env_with_overlay: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful run prints comparison table and agent overlay path."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_agent_promptfoo_success)

    dist, overlay = fake_env_with_overlay
    result = runner.invoke(app, ["benchmark", "agent", str(overlay), "--dist", str(dist)])

    assert result.exit_code == 0, result.output
    assert "Agent overlay:" in result.output
    assert str(overlay) in result.output
    # Comparison table columns
    assert "Dimension" in result.output


def test_benchmark_agent_stores_scores(
    fake_env_with_overlay: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent run seeds baseline in scores.json under agents key."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_agent_promptfoo_success)

    dist, overlay = fake_env_with_overlay
    result = runner.invoke(app, ["benchmark", "agent", str(overlay), "--dist", str(dist)])
    assert result.exit_code == 0

    scores = bm.load_scores()
    assert scores is not None
    agent_name = overlay.stem  # "spec-writer"
    assert agent_name in scores.agents
    assert scores.agents[agent_name].baseline is not None
    assert len(scores.agents[agent_name].mutations) == 0


def test_benchmark_agent_appends_run_log(
    fake_env_with_overlay: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent run appends to runs.jsonl with type=agent and agent=<name>."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_agent_promptfoo_success)

    dist, overlay = fake_env_with_overlay
    runner.invoke(app, ["benchmark", "agent", str(overlay), "--dist", str(dist)])

    log_path = dist.parent / "runs.jsonl"
    lines = log_path.read_text().strip().split("\n")
    entry = json.loads(lines[-1])
    assert entry.get("type") == "agent"
    assert entry.get("agent") == overlay.stem


def test_benchmark_agent_cleans_temp_files(
    fake_env_with_overlay: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Temporary files are cleaned up after a successful run."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_agent_promptfoo_success)

    import tempfile
    temp_dirs_created: list[str] = []
    original_tempdir = tempfile.TemporaryDirectory

    class _TrackingTempDir:
        def __init__(self) -> None:
            self._real = original_tempdir()
            temp_dirs_created.append(self._real.name)

        def __enter__(self) -> "tempfile.TemporaryDirectory[str]":
            return self._real.__enter__()

        def __exit__(self, *args: object) -> None:
            self._real.__exit__(*args)

    import cortex.cli as cli_mod
    monkeypatch.setattr(cli_mod.tempfile, "TemporaryDirectory", _TrackingTempDir)  # type: ignore[attr-defined]

    dist, overlay = fake_env_with_overlay
    runner.invoke(app, ["benchmark", "agent", str(overlay), "--dist", str(dist)])

    # All tracked temp dirs should no longer exist (cleaned up)
    import os
    for td in temp_dirs_created:
        assert not os.path.exists(td), f"Temp dir not cleaned up: {td}"


# ---------------------------------------------------------------------------
# Subtask 03: cortex benchmark skill
# ---------------------------------------------------------------------------


def _mock_skill_promptfoo_success(output_path: Path, config_path: Path | None = None) -> MagicMock:
    """Fake run_promptfoo for skill benchmark."""
    output_path.write_text(json.dumps({
        "results": {
            "results": [
                {"description": "test_delegates_to_evolution", "success": True},
                {"description": "test_format_matches_template", "success": True},
                {"description": "test_format_matches_template", "success": False},
            ]
        }
    }))
    result = MagicMock()
    result.returncode = 0
    result.stderr = ""
    return result


@pytest.fixture()
def fake_env_with_skill(fake_env: Path, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Extend fake_env with a skill file and a skill test config."""
    skill_file = tmp_path / "ievo.md"
    skill_file.write_text("# /ievo skill\nDelegate to the evolution agent.")

    # Create benchmarks/skills/ dir under the fake BENCHMARKS_DIR
    import cortex.benchmark as bm
    skills_dir = bm.BENCHMARKS_DIR / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    skill_config = skills_dir / "ievo.yaml"
    skill_config.write_text("""description: "ievo skill benchmark"
tests:
  - description: test_delegates_to_evolution
    vars:
      prompt: "Use /ievo to analyze this error."
    assert:
      - type: llm-rubric
        value: "Delegates to the evolution agent"
  - description: test_format_matches_template
    vars:
      prompt: "Trigger /ievo for the following finding."
    assert:
      - type: icontains
        value: "evolution"
""")

    return fake_env, skill_file, skill_config


def test_benchmark_skill_help() -> None:
    """cortex benchmark skill --help exits 0."""
    result = runner.invoke(app, ["benchmark", "skill", "--help"])
    assert result.exit_code == 0
    assert "skill" in result.output.lower()


def test_benchmark_skill_missing_skill_file(fake_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when skill file doesn't exist."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    result = runner.invoke(app, ["benchmark", "skill", "/nonexistent/skill.md"])
    assert result.exit_code == 1


def test_benchmark_skill_missing_test_config(
    fake_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exits 1 when benchmarks/skills/<name>.yaml doesn't exist."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    skill_file = tmp_path / "no-tests.md"
    skill_file.write_text("# No test skill")

    result = runner.invoke(app, ["benchmark", "skill", str(skill_file)])
    assert result.exit_code == 1
    assert "no skill tests found" in result.output.lower()


def test_benchmark_skill_runs_and_prints_results(
    fake_env_with_skill: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful skill run prints per-test pass/fail and overall pass rate."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_skill_promptfoo_success)

    dist, skill_file, _ = fake_env_with_skill
    result = runner.invoke(app, ["benchmark", "skill", str(skill_file)])

    assert result.exit_code == 0, result.output
    assert "pass" in result.output.lower() or "overall" in result.output.lower()


def test_benchmark_skill_stores_scores(
    fake_env_with_skill: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skill run seeds baseline in scores.json under skills key."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_skill_promptfoo_success)

    dist, skill_file, _ = fake_env_with_skill
    result = runner.invoke(app, ["benchmark", "skill", str(skill_file)])
    assert result.exit_code == 0

    scores = bm.load_scores()
    assert scores is not None
    skill_name = skill_file.stem  # "ievo"
    assert skill_name in scores.skills
    assert scores.skills[skill_name].baseline is not None
    assert len(scores.skills[skill_name].mutations) == 0


def test_benchmark_skill_appends_run_log(
    fake_env_with_skill: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skill run appends to runs.jsonl with type=skill and skill=<name>."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")
    monkeypatch.setattr(bm, "run_promptfoo", _mock_skill_promptfoo_success)

    dist, skill_file, _ = fake_env_with_skill
    runner.invoke(app, ["benchmark", "skill", str(skill_file)])

    log_path = dist.parent / "runs.jsonl"
    lines = log_path.read_text().strip().split("\n")
    entry = json.loads(lines[-1])
    assert entry.get("type") == "skill"
    assert entry.get("skill") == skill_file.stem


# ---------------------------------------------------------------------------
# Subtask 04: cortex benchmark generate
# ---------------------------------------------------------------------------

_FAKE_GENERATED_YAML = """- description: "plan_first: implement without planning"
  vars:
    prompt: "Build an OAuth flow now."
    dimension: plan_first
  assert:
    - type: llm-rubric
      value: "Creates a plan before implementing"
    - type: icontains-any
      value:
        - plan
        - outline
"""


def _mock_generate_test_case(rule_text: str, dimension: str) -> str:  # noqa: ARG001
    return _FAKE_GENERATED_YAML


def test_benchmark_generate_help() -> None:
    """cortex benchmark generate --help exits 0."""
    result = runner.invoke(app, ["benchmark", "generate", "--help"])
    assert result.exit_code == 0
    assert "rule" in result.output.lower() or "generate" in result.output.lower()


def test_benchmark_generate_prints_yaml(
    fake_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate prints YAML test case to stdout."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "generate_test_case", _mock_generate_test_case)

    result = runner.invoke(app, ["benchmark", "generate", "always plan before coding"])
    assert result.exit_code == 0, result.output
    assert "plan_first" in result.output or "dimension" in result.output.lower()


def test_benchmark_generate_infers_dimension(
    fake_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate uses infer_dimension when --dimension not provided."""
    import cortex.benchmark as bm

    inferred: list[str] = []

    def _capture(rule_text: str, dimension: str) -> str:
        inferred.append(dimension)
        return _FAKE_GENERATED_YAML

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "generate_test_case", _capture)

    runner.invoke(app, ["benchmark", "generate", "always challenge unclear requests"])
    assert inferred == ["challenge_reflex"]


def test_benchmark_generate_explicit_dimension(
    fake_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate uses --dimension when explicitly provided."""
    import cortex.benchmark as bm

    called_with: list[str] = []

    def _capture(rule_text: str, dimension: str) -> str:
        called_with.append(dimension)
        return _FAKE_GENERATED_YAML

    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "generate_test_case", _capture)

    runner.invoke(app, [
        "benchmark", "generate", "some rule text",
        "--dimension", "decision_logging",
    ])
    assert called_with == ["decision_logging"]


def test_benchmark_generate_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exits 1 when API key is not set."""
    import cortex.benchmark as bm

    def _raise() -> None:
        raise RuntimeError("ANTHROPIC_API_KEY not set — add it to .env or export it")

    monkeypatch.setattr(bm, "check_api_key", _raise)

    result = runner.invoke(app, ["benchmark", "generate", "some rule"])
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY" in result.output


def test_benchmark_generate_append_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--append flag appends generated test case to promptfooconfig.yaml."""
    import cortex.benchmark as bm
    import yaml

    # Set up a fake promptfooconfig.yaml
    fake_config = tmp_path / "promptfooconfig.yaml"
    fake_config.write_text("""description: test
tests:
  - description: existing_test
    vars:
      prompt: "hello"
""")
    monkeypatch.setattr(bm, "PROMPTFOO_CONFIG", fake_config)
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "generate_test_case", _mock_generate_test_case)

    result = runner.invoke(app, ["benchmark", "generate", "plan before coding", "--append"])
    assert result.exit_code == 0, result.output
    assert "Appended to promptfooconfig.yaml" in result.output

    # Verify the test was appended
    updated = yaml.safe_load(fake_config.read_text())
    assert len(updated["tests"]) == 2  # original + appended


def test_benchmark_generate_stdout_only_without_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --append, nothing is written to promptfooconfig.yaml."""
    import cortex.benchmark as bm
    import yaml

    fake_config = tmp_path / "promptfooconfig.yaml"
    fake_config.write_text("""description: test
tests:
  - description: existing_test
    vars:
      prompt: "hello"
""")
    monkeypatch.setattr(bm, "PROMPTFOO_CONFIG", fake_config)
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "generate_test_case", _mock_generate_test_case)

    result = runner.invoke(app, ["benchmark", "generate", "plan before coding"])
    assert result.exit_code == 0

    # Config should be unchanged
    unchanged = yaml.safe_load(fake_config.read_text())
    assert len(unchanged["tests"]) == 1
