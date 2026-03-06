"""Tests for cortex cognitive benchmark module (Task 026 + 028)."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.benchmark import (
    AgentScores,
    BenchmarkEntry,
    DimensionScores,
    MutationEntry,
    ScoresFile,
    SkillBenchmarkEntry,
    SkillScores,
    compare_scores,
    infer_dimension,
    load_scores,
    now_iso,
    parse_skill_results,
    run_promptfoo,
    save_scores,
)


def test_dimension_scores_defaults() -> None:
    scores = DimensionScores()
    assert scores.overall() == 0.0
    assert scores.structure_adherence == 0.0


def test_dimension_scores_overall() -> None:
    scores = DimensionScores(
        structure_adherence=0.8,
        challenge_reflex=0.6,
        plan_first=0.7,
        decision_logging=0.5,
        ac_verification=0.9,
        evolution_awareness=0.3,
    )
    expected = (0.8 + 0.6 + 0.7 + 0.5 + 0.9 + 0.3) / 6
    assert abs(scores.overall() - expected) < 0.001


def test_dimension_scores_roundtrip() -> None:
    original = DimensionScores(structure_adherence=0.5, plan_first=0.7)
    d = original.to_dict()
    restored = DimensionScores.from_dict(d)
    assert restored.structure_adherence == 0.5
    assert restored.plan_first == 0.7


def test_benchmark_entry_roundtrip() -> None:
    entry = BenchmarkEntry(
        timestamp="2026-03-06T12:00:00+00:00",
        model="claude-haiku-4-5-20251001",
        kernel_version=None,
        scores=DimensionScores(structure_adherence=0.3),
        overall=0.05,
    )
    d = entry.to_dict()
    restored = BenchmarkEntry.from_dict(d)
    assert restored.kernel_version is None
    assert restored.scores.structure_adherence == 0.3
    assert restored.overall == 0.05


def test_mutation_entry_roundtrip() -> None:
    entry = MutationEntry(
        id=1,
        timestamp="2026-03-06T14:00:00+00:00",
        kernel_version="26.03.06.1400",
        region="instincts",
        lesson="no PR, no work",
        scores=DimensionScores(challenge_reflex=0.8),
        overall=0.53,
        delta=0.40,
        status="accepted",
    )
    d = entry.to_dict()
    restored = MutationEntry.from_dict(d)
    assert restored.id == 1
    assert restored.region == "instincts"
    assert restored.status == "accepted"
    assert restored.delta == 0.40


def test_scores_file_empty() -> None:
    sf = ScoresFile()
    assert sf.baseline is None
    assert sf.mutations == []
    assert sf.last_accepted_overall() is None


def test_scores_file_baseline_only() -> None:
    sf = ScoresFile(
        baseline=BenchmarkEntry(
            timestamp="t", model="m", kernel_version=None,
            scores=DimensionScores(), overall=0.13,
        )
    )
    assert sf.last_accepted_overall() == 0.13


def test_scores_file_with_mutations() -> None:
    sf = ScoresFile(
        baseline=BenchmarkEntry(
            timestamp="t", model="m", kernel_version=None,
            scores=DimensionScores(), overall=0.13,
        ),
        mutations=[
            MutationEntry(
                id=1, timestamp="t", kernel_version="v1", region="r",
                lesson="l", scores=DimensionScores(), overall=0.53,
                delta=0.40, status="accepted",
            ),
            MutationEntry(
                id=2, timestamp="t", kernel_version="v2", region="r",
                lesson="l2", scores=DimensionScores(), overall=0.45,
                delta=-0.08, status="rejected",
            ),
        ],
    )
    # Last accepted is mutation 1 (mutation 2 was rejected)
    assert sf.last_accepted_overall() == 0.53


def test_scores_file_roundtrip() -> None:
    sf = ScoresFile(
        baseline=BenchmarkEntry(
            timestamp="2026-03-06T12:00:00+00:00", model="claude-haiku-4-5-20251001",
            kernel_version=None, scores=DimensionScores(structure_adherence=0.3),
            overall=0.05,
        ),
        mutations=[],
    )
    d = sf.to_dict()
    restored = ScoresFile.from_dict(d)
    assert restored.baseline is not None
    assert restored.baseline.scores.structure_adherence == 0.3


def test_save_and_load_scores(tmp_path: Path, monkeypatch: object) -> None:
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "SCORES_FILE", tmp_path / "scores.json")

    sf = ScoresFile(
        baseline=BenchmarkEntry(
            timestamp="t", model="m", kernel_version=None,
            scores=DimensionScores(plan_first=0.42), overall=0.07,
        ),
    )
    save_scores(sf)

    loaded = load_scores()
    assert loaded is not None
    assert loaded.baseline is not None
    assert loaded.baseline.scores.plan_first == 0.42


def test_load_scores_missing(tmp_path: Path, monkeypatch: object) -> None:
    import cortex.benchmark as bm
    monkeypatch.setattr(bm, "SCORES_FILE", tmp_path / "nope.json")

    assert load_scores() is None


def test_now_iso_format() -> None:
    ts = now_iso()
    assert "T" in ts
    assert "+" in ts or "Z" in ts


def test_compare_scores_pass() -> None:
    current = DimensionScores(
        structure_adherence=0.8, challenge_reflex=0.7, plan_first=0.6,
        decision_logging=0.5, ac_verification=0.8, evolution_awareness=0.4,
    )
    passed, messages = compare_scores(current, baseline_overall=0.5)
    assert passed
    assert any("PASSED" in m for m in messages)


def test_compare_scores_regression() -> None:
    current = DimensionScores(
        structure_adherence=0.2, challenge_reflex=0.1, plan_first=0.1,
        decision_logging=0.1, ac_verification=0.2, evolution_awareness=0.0,
    )
    passed, messages = compare_scores(current, baseline_overall=0.5)
    assert not passed
    assert any("REGRESSED" in m for m in messages)


def test_scores_json_valid_format(tmp_path: Path, monkeypatch: object) -> None:
    """AC-3: scores.json is valid JSON with correct structure."""
    import cortex.benchmark as bm
    scores_path = tmp_path / "scores.json"
    monkeypatch.setattr(bm, "SCORES_FILE", scores_path)

    sf = ScoresFile(
        baseline=BenchmarkEntry(
            timestamp=now_iso(), model="claude-haiku-4-5-20251001", kernel_version=None,
            scores=DimensionScores(), overall=0.0,
        ),
    )
    save_scores(sf)

    data = json.loads(scores_path.read_text())
    assert "baseline" in data
    assert "mutations" in data
    assert data["baseline"]["kernel_version"] is None
    assert data["baseline"]["model"] == "claude-haiku-4-5-20251001"
    for dim in ["structure_adherence", "challenge_reflex", "plan_first",
                "decision_logging", "ac_verification", "evolution_awareness"]:
        assert dim in data["baseline"]["scores"]
        val = data["baseline"]["scores"][dim]
        assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# Subtask 01: New dataclasses (AgentScores, SkillBenchmarkEntry, SkillScores)
# ---------------------------------------------------------------------------


def test_skill_benchmark_entry_roundtrip() -> None:
    """SkillBenchmarkEntry: flat dict scores + overall."""
    entry = SkillBenchmarkEntry(
        timestamp="2026-03-06T12:00:00+00:00",
        model="claude-haiku-4-5-20251001",
        scores={"test_delegates": 1.0, "test_format": 0.0},
        overall=0.5,
    )
    d = entry.to_dict()
    restored = SkillBenchmarkEntry.from_dict(d)
    assert restored.model == "claude-haiku-4-5-20251001"
    assert restored.scores == {"test_delegates": 1.0, "test_format": 0.0}
    assert restored.overall == 0.5


def test_skill_scores_roundtrip() -> None:
    """SkillScores: baseline + mutations list."""
    ss = SkillScores(
        baseline=SkillBenchmarkEntry(
            timestamp="t", model="m",
            scores={"test_a": 1.0}, overall=1.0,
        ),
        mutations=[],
    )
    d = ss.to_dict()
    restored = SkillScores.from_dict(d)
    assert restored.baseline is not None
    assert restored.baseline.overall == 1.0
    assert restored.mutations == []


def test_skill_scores_empty() -> None:
    ss = SkillScores()
    assert ss.baseline is None
    assert ss.mutations == []


def test_agent_scores_roundtrip() -> None:
    """AgentScores: baseline (BenchmarkEntry) + mutations list."""
    entry = BenchmarkEntry(
        timestamp="t", model="m", kernel_version=None,
        scores=DimensionScores(plan_first=0.7), overall=0.12,
    )
    ag = AgentScores(baseline=entry, mutations=[])
    d = ag.to_dict()
    restored = AgentScores.from_dict(d)
    assert restored.baseline is not None
    assert restored.baseline.scores.plan_first == 0.7
    assert restored.mutations == []


def test_agent_scores_empty() -> None:
    ag = AgentScores()
    assert ag.baseline is None
    assert ag.mutations == []


def test_scores_file_with_agents_and_skills(tmp_path: Path, monkeypatch: object) -> None:
    """ScoresFile.to_dict() / from_dict() round-trips agents + skills."""
    import cortex.benchmark as bm
    scores_path = tmp_path / "scores.json"
    monkeypatch.setattr(bm, "SCORES_FILE", scores_path)

    sf = ScoresFile(
        agents={
            "spec-writer": AgentScores(
                baseline=BenchmarkEntry(
                    timestamp="t", model="m", kernel_version=None,
                    scores=DimensionScores(), overall=0.33,
                ),
                mutations=[],
            )
        },
        skills={
            "ievo": SkillScores(
                baseline=SkillBenchmarkEntry(
                    timestamp="t", model="m",
                    scores={"test_delegates": 1.0}, overall=1.0,
                ),
                mutations=[],
            )
        },
    )
    save_scores(sf)

    data = json.loads(scores_path.read_text())
    assert "agents" in data
    assert "spec-writer" in data["agents"]
    assert data["agents"]["spec-writer"]["baseline"]["overall"] == 0.33
    assert "skills" in data
    assert "ievo" in data["skills"]
    assert data["skills"]["ievo"]["baseline"]["overall"] == 1.0

    loaded = load_scores()
    assert loaded is not None
    assert loaded.agents["spec-writer"].baseline is not None
    assert loaded.skills["ievo"].baseline is not None


def test_scores_file_backward_compatible(tmp_path: Path, monkeypatch: object) -> None:
    """Loading old scores.json without agents/skills keys must not fail."""
    import cortex.benchmark as bm
    scores_path = tmp_path / "scores.json"
    monkeypatch.setattr(bm, "SCORES_FILE", scores_path)

    # Old-format scores.json (no agents/skills keys)
    scores_path.write_text(json.dumps({
        "naked": None,
        "baseline": None,
        "mutations": [],
    }))

    loaded = load_scores()
    assert loaded is not None
    assert loaded.agents == {}
    assert loaded.skills == {}


def test_run_promptfoo_uses_custom_config(tmp_path: Path, monkeypatch: object) -> None:
    """run_promptfoo() accepts optional config_path; uses it instead of PROMPTFOO_CONFIG."""
    import subprocess
    import cortex.benchmark as bm

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        result = object.__new__(subprocess.CompletedProcess)
        result.__dict__.update({"args": cmd, "returncode": 0, "stdout": "", "stderr": ""})
        return result

    monkeypatch.setattr(bm, "_load_env", lambda: None)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    custom_config = tmp_path / "custom.yaml"
    custom_config.write_text("description: test")
    output = tmp_path / "out.json"

    run_promptfoo(output, config_path=custom_config)

    # The custom config path must appear in the command
    assert any(str(custom_config) in arg for arg in calls[0])


def test_run_promptfoo_default_config(tmp_path: Path, monkeypatch: object) -> None:
    """run_promptfoo() without config_path uses PROMPTFOO_CONFIG."""
    import subprocess
    import cortex.benchmark as bm

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        result = object.__new__(subprocess.CompletedProcess)
        result.__dict__.update({"args": cmd, "returncode": 0, "stdout": "", "stderr": ""})
        return result

    default_config = tmp_path / "promptfooconfig.yaml"
    default_config.write_text("description: default")
    monkeypatch.setattr(bm, "PROMPTFOO_CONFIG", default_config)
    monkeypatch.setattr(bm, "_load_env", lambda: None)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    output = tmp_path / "out.json"
    run_promptfoo(output)

    assert any(str(default_config) in arg for arg in calls[0])


# ---------------------------------------------------------------------------
# Subtask 01: parse_skill_results + infer_dimension
# ---------------------------------------------------------------------------


def test_parse_skill_results() -> None:
    """parse_skill_results() computes per-test pass rate from promptfoo output."""
    output = {
        "results": {
            "results": [
                {"description": "test_delegates", "success": True},
                {"description": "test_format", "success": False},
                {"description": "test_format", "success": True},
            ]
        }
    }
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(output, f)
        p = Path(f.name)

    scores, overall = parse_skill_results(p)
    p.unlink(missing_ok=True)

    assert scores["test_delegates"] == 1.0
    assert abs(scores["test_format"] - 0.5) < 0.001
    assert abs(overall - 0.75) < 0.001  # (1.0 + 0.5) / 2 = 0.75


def test_infer_dimension_known_keywords() -> None:
    """infer_dimension() maps keywords to known dimension names."""
    assert infer_dimension("always challenge user input before executing") == "challenge_reflex"
    assert infer_dimension("plan before you code") == "plan_first"
    assert infer_dimension("log every decision with rationale") == "decision_logging"
    assert infer_dimension("always verify acceptance criteria") == "ac_verification"
    assert infer_dimension("maintain consistent structure and format") == "structure_adherence"
    assert infer_dimension("record lessons and evolve") == "evolution_awareness"


def test_infer_dimension_fallback() -> None:
    """infer_dimension() returns a default when no keyword matches."""
    result = infer_dimension("something completely unrelated")
    from cortex.benchmark import DIMENSIONS
    assert result in DIMENSIONS


def test_generate_test_case_strips_code_fences(monkeypatch: object) -> None:
    """generate_test_case() strips ```yaml code fences from LLM output."""
    import types
    import cortex.benchmark as bm

    # Mock the anthropic module at the point of lazy import
    fake_message = types.SimpleNamespace(
        content=[types.SimpleNamespace(text="""```yaml
- description: "plan_first: test"
  vars:
    prompt: "code now"
    dimension: plan_first
  assert:
    - type: llm-rubric
      value: "Plans first"
```""")]
    )
    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(
            create=lambda **kw: fake_message
        )
    )
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = lambda: fake_client  # type: ignore[attr-defined]

    import sys
    sys.modules["anthropic"] = fake_anthropic  # type: ignore[assignment]
    monkeypatch.setattr(bm, "_load_env", lambda: None)

    result = bm.generate_test_case("plan before coding", "plan_first")

    # Should not start/end with code fences
    assert not result.startswith("```")
    assert not result.endswith("```")
    assert "plan_first" in result


def test_generate_test_case_api_error(monkeypatch: object) -> None:
    """generate_test_case() raises RuntimeError on API failure."""
    import types
    import cortex.benchmark as bm

    def _raise(**kw: object) -> None:
        raise Exception("network error")

    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=_raise)
    )
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = lambda: fake_client  # type: ignore[attr-defined]

    import sys
    sys.modules["anthropic"] = fake_anthropic  # type: ignore[assignment]
    monkeypatch.setattr(bm, "_load_env", lambda: None)

    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="Anthropic API call failed"):
        bm.generate_test_case("some rule", "plan_first")
