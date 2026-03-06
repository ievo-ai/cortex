"""Integration tests for Task 028 — benchmark expansion (agent/skill/generate).

These tests verify end-to-end flows across AC-1 through AC-7 using
the Typer test runner and mocked external calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from typer.testing import CliRunner

from cortex.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Set up an isolated benchmark environment with all paths patched."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "iEVO.md").write_text("# fake kernel content\n\nsome kernel instructions.")

    skills_dir = tmp_path / "benchmarks" / "skills"
    skills_dir.mkdir(parents=True)

    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "SCORES_FILE", tmp_path / "scores.json")
    monkeypatch.setattr(bm, "RUNS_LOG", tmp_path / "runs.jsonl")
    monkeypatch.setattr(bm, "BENCHMARKS_DIR", tmp_path / "benchmarks")
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "check_promptfoo", lambda: "promptfoo")

    return {
        "dist": dist,
        "tmp": tmp_path,
        "skills_dir": skills_dir,
    }


def _make_agent_promptfoo_output(output_path: Path, config_path: Path | None = None) -> MagicMock:
    """Write a valid promptfoo output for agent benchmark."""
    output_path.write_text(json.dumps({
        "results": {
            "results": [
                {"provider": {"label": "baseline"}, "vars": {"dimension": "structure_adherence"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "challenge_reflex"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "plan_first"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "decision_logging"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "ac_verification"}, "success": False},
                {"provider": {"label": "baseline"}, "vars": {"dimension": "evolution_awareness"}, "success": False},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "structure_adherence"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "challenge_reflex"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "plan_first"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "decision_logging"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "ac_verification"}, "success": True},
                {"provider": {"label": "with-kernel"}, "vars": {"dimension": "evolution_awareness"}, "success": True},
            ]
        }
    }))
    r = MagicMock()
    r.returncode = 0
    r.stderr = ""
    return r


def _make_skill_promptfoo_output(output_path: Path, config_path: Path | None = None) -> MagicMock:
    """Write a valid promptfoo output for skill benchmark."""
    output_path.write_text(json.dumps({
        "results": {
            "results": [
                {"description": "test_delegates_to_evolution_agent", "success": True},
                {"description": "test_passes_context", "success": True},
            ]
        }
    }))
    r = MagicMock()
    r.returncode = 0
    r.stderr = ""
    return r


# ---------------------------------------------------------------------------
# AC-1: cortex benchmark agent command exists and runs
# ---------------------------------------------------------------------------


def test_ac1_agent_command_help(isolated_env: dict) -> None:
    """AC-1: cortex benchmark agent --help exits 0."""
    result = runner.invoke(app, ["benchmark", "agent", "--help"])
    assert result.exit_code == 0


def test_ac1_agent_command_runs_e2e(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1: agent command runs end-to-end with valid inputs."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_agent_promptfoo_output)

    env = isolated_env
    overlay = env["tmp"] / "spec-writer.md"
    overlay.write_text("# Spec Writer overlay\nAlways challenge first.")

    result = runner.invoke(app, [
        "benchmark", "agent", str(overlay), "--dist", str(env["dist"])
    ])

    assert result.exit_code == 0, result.output
    assert "Agent overlay:" in result.output
    assert "Dimension" in result.output  # comparison table printed


def test_ac1_agent_exits_1_missing_kernel(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1: exits 1 with correct message when dist/iEVO.md not found."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_agent_promptfoo_output)

    env = isolated_env
    overlay = env["tmp"] / "spec-writer.md"
    overlay.write_text("# overlay")

    result = runner.invoke(app, [
        "benchmark", "agent", str(overlay), "--dist", "/nonexistent"
    ])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_ac1_agent_exits_1_missing_overlay(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1: exits 1 with correct message when overlay file not found."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_agent_promptfoo_output)

    env = isolated_env
    result = runner.invoke(app, [
        "benchmark", "agent", "/nonexistent/overlay.md", "--dist", str(env["dist"])
    ])
    assert result.exit_code == 1
    assert "overlay file not found" in result.output.lower()


# ---------------------------------------------------------------------------
# AC-2: scores stored under agents key with per-agent baseline + mutations
# ---------------------------------------------------------------------------


def test_ac2_agent_scores_stored(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2: scores.json updated with agent baseline under agents key."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_agent_promptfoo_output)

    env = isolated_env
    overlay = env["tmp"] / "spec-writer.md"
    overlay.write_text("# Spec Writer overlay")

    result = runner.invoke(app, [
        "benchmark", "agent", str(overlay), "--dist", str(env["dist"])
    ])
    assert result.exit_code == 0

    data = json.loads((env["tmp"] / "scores.json").read_text())
    assert "agents" in data
    assert "spec-writer" in data["agents"]
    agent_data = data["agents"]["spec-writer"]
    assert "baseline" in agent_data
    assert agent_data["baseline"]["model"] == "claude-haiku-4-5-20251001"
    assert "mutations" in agent_data
    assert agent_data["mutations"] == []

    # runs.jsonl entry
    log = (env["tmp"] / "runs.jsonl").read_text().strip()
    entry = json.loads(log.split("\n")[-1])
    assert entry["type"] == "agent"
    assert entry["agent"] == "spec-writer"


# ---------------------------------------------------------------------------
# AC-3: cortex benchmark skill command exists and runs
# ---------------------------------------------------------------------------


def test_ac3_skill_command_help(isolated_env: dict) -> None:
    """AC-3: cortex benchmark skill --help exits 0."""
    result = runner.invoke(app, ["benchmark", "skill", "--help"])
    assert result.exit_code == 0


def test_ac3_skill_missing_test_config_error(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: missing skill test config prints correct error message."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_skill_promptfoo_output)

    env = isolated_env
    skill_file = env["tmp"] / "mystery-skill.md"
    skill_file.write_text("# Mystery skill")

    result = runner.invoke(app, ["benchmark", "skill", str(skill_file)])
    assert result.exit_code == 1
    assert "no skill tests found" in result.output.lower()


def test_ac3_skill_runs_e2e(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: skill command runs end-to-end and exits 0."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_skill_promptfoo_output)

    env = isolated_env
    skill_file = env["tmp"] / "ievo.md"
    skill_file.write_text("# /ievo skill\nDelegate to evolution agent.")

    # Create skill test config
    skill_config = env["skills_dir"] / "ievo.yaml"
    skill_config.write_text(yaml.dump({
        "description": "ievo skill test",
        "tests": [
            {
                "description": "test_delegates_to_evolution_agent",
                "vars": {"prompt": "Use /ievo"},
                "assert": [{"type": "llm-rubric", "value": "delegates"}],
            }
        ],
    }))

    result = runner.invoke(app, ["benchmark", "skill", str(skill_file)])
    assert result.exit_code == 0, result.output
    assert "overall" in result.output.lower() or "pass" in result.output.lower()


# ---------------------------------------------------------------------------
# AC-4: skill scores stored with per-skill baseline
# ---------------------------------------------------------------------------


def test_ac4_skill_scores_stored(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-4: scores.json updated with skill baseline under skills key."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_skill_promptfoo_output)

    env = isolated_env
    skill_file = env["tmp"] / "ievo.md"
    skill_file.write_text("# /ievo skill")

    skill_config = env["skills_dir"] / "ievo.yaml"
    skill_config.write_text(yaml.dump({
        "description": "ievo test",
        "tests": [{"description": "t1", "vars": {"prompt": "x"}, "assert": []}],
    }))

    runner.invoke(app, ["benchmark", "skill", str(skill_file)])

    data = json.loads((env["tmp"] / "scores.json").read_text())
    assert "skills" in data
    assert "ievo" in data["skills"]
    skill_data = data["skills"]["ievo"]
    assert "baseline" in skill_data
    assert "mutations" in skill_data
    assert skill_data["mutations"] == []

    # runs.jsonl entry
    log = (env["tmp"] / "runs.jsonl").read_text().strip()
    entry = json.loads(log)
    assert entry["type"] == "skill"
    assert entry["skill"] == "ievo"


# ---------------------------------------------------------------------------
# AC-5 + AC-6: cortex benchmark generate command
# ---------------------------------------------------------------------------


def test_ac5_generate_command_help() -> None:
    """AC-5: cortex benchmark generate --help exits 0."""
    result = runner.invoke(app, ["benchmark", "generate", "--help"])
    assert result.exit_code == 0


def test_ac5_generate_stdout_output(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-5: generate prints test case YAML to stdout."""
    import cortex.benchmark as bm

    def _fake_generate(rule_text: str, dimension: str) -> str:
        return f"- description: \"{dimension}: test rule\"\n  vars:\n    prompt: scenario\n    dimension: {dimension}\n  assert:\n    - type: llm-rubric\n      value: follows rule\n    - type: icontains-any\n      value:\n        - keyword\n"

    monkeypatch.setattr(bm, "generate_test_case", _fake_generate)

    result = runner.invoke(app, ["benchmark", "generate", "always plan before coding"])
    assert result.exit_code == 0, result.output
    assert "plan_first" in result.output or "description" in result.output


def test_ac5_generate_infers_dimension(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-5: dimension inferred from rule text when --dimension not given."""
    import cortex.benchmark as bm

    captured: list[str] = []

    def _capture(rule_text: str, dimension: str) -> str:
        captured.append(dimension)
        return "- description: test\n  vars:\n    prompt: p\n    dimension: plan_first\n  assert: []\n"

    monkeypatch.setattr(bm, "generate_test_case", _capture)

    runner.invoke(app, ["benchmark", "generate", "write a plan before implementing"])
    assert captured == ["plan_first"]


def test_ac5_generate_append_modifies_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-5: --append appends test case to promptfooconfig.yaml."""
    import cortex.benchmark as bm

    config_path = tmp_path / "promptfooconfig.yaml"
    config_path.write_text(yaml.dump({
        "description": "base config",
        "tests": [{"description": "existing", "vars": {"prompt": "hi"}, "assert": []}],
    }))
    monkeypatch.setattr(bm, "PROMPTFOO_CONFIG", config_path)
    monkeypatch.setattr(bm, "check_api_key", lambda: None)
    monkeypatch.setattr(bm, "generate_test_case", lambda r, d: (
        "- description: \"plan_first: new test\"\n"
        "  vars:\n    prompt: test\n    dimension: plan_first\n"
        "  assert:\n    - type: llm-rubric\n      value: plans first\n"
        "    - type: icontains-any\n      value:\n        - plan\n"
    ))

    result = runner.invoke(app, [
        "benchmark", "generate", "plan before coding", "--append"
    ])
    assert result.exit_code == 0
    assert "Appended to promptfooconfig.yaml" in result.output

    updated = yaml.safe_load(config_path.read_text())
    assert len(updated["tests"]) == 2


def test_ac6_generate_api_key_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-6: exits 1 with ANTHROPIC_API_KEY error message when key missing."""
    import cortex.benchmark as bm

    def _raise() -> None:
        raise RuntimeError("ANTHROPIC_API_KEY not set — add it to .env or export it")

    monkeypatch.setattr(bm, "check_api_key", _raise)

    result = runner.invoke(app, ["benchmark", "generate", "some rule"])
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY" in result.output


# ---------------------------------------------------------------------------
# AC-7: existing run/compare tests still pass (verified by full suite)
# + backward compatibility of ScoresFile
# ---------------------------------------------------------------------------


def test_ac7_scores_file_backward_compat(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-7: existing scores.json without agents/skills loads correctly."""
    import cortex.benchmark as bm

    env = isolated_env
    # Write an old-format scores.json (no agents/skills)
    (env["tmp"] / "scores.json").write_text(json.dumps({
        "naked": {
            "timestamp": "2026-03-06T00:00:00+00:00",
            "model": "claude-haiku-4-5-20251001",
            "kernel_version": None,
            "scores": {
                "structure_adherence": 0.17, "challenge_reflex": 0.5,
                "plan_first": 0.0, "decision_logging": 0.0,
                "ac_verification": 0.0, "evolution_awareness": 0.0,
            },
            "overall": 0.17,
        },
        "baseline": {
            "timestamp": "2026-03-06T00:00:00+00:00",
            "model": "claude-haiku-4-5-20251001",
            "kernel_version": None,
            "scores": {
                "structure_adherence": 0.33, "challenge_reflex": 1.0,
                "plan_first": 0.0, "decision_logging": 0.0,
                "ac_verification": 0.0, "evolution_awareness": 1.0,
            },
            "overall": 0.33,
        },
        "mutations": [],
    }))

    sf = bm.load_scores()
    assert sf is not None
    assert sf.naked is not None
    assert sf.baseline is not None
    assert sf.agents == {}
    assert sf.skills == {}


def test_ac7_agent_then_skill_then_run_all_coexist(
    isolated_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-7: agent + skill + kernel scores coexist in scores.json."""
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "run_promptfoo", _make_agent_promptfoo_output)

    env = isolated_env

    # Run agent benchmark
    overlay = env["tmp"] / "team-lead.md"
    overlay.write_text("# Team Lead overlay")
    runner.invoke(app, [
        "benchmark", "agent", str(overlay), "--dist", str(env["dist"])
    ])

    # Run skill benchmark
    monkeypatch.setattr(bm, "run_promptfoo", _make_skill_promptfoo_output)
    skill_file = env["tmp"] / "ievo.md"
    skill_file.write_text("# /ievo skill")
    skill_config = env["skills_dir"] / "ievo.yaml"
    skill_config.write_text(yaml.dump({
        "description": "ievo",
        "tests": [{"description": "t1", "vars": {"prompt": "x"}, "assert": []}],
    }))
    runner.invoke(app, ["benchmark", "skill", str(skill_file)])

    # Verify coexistence
    sf = bm.load_scores()
    assert sf is not None
    assert "team-lead" in sf.agents
    assert "ievo" in sf.skills
    # agents and skills don't clobber each other
    assert "team-lead" not in sf.skills
    assert "ievo" not in sf.agents
