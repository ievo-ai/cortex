"""Tests for cortex cognitive benchmark module (Task 026)."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.benchmark import (
    BenchmarkEntry,
    DimensionScores,
    MutationEntry,
    ScoresFile,
    compare_scores,
    load_scores,
    now_iso,
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
        model="qwen2.5:7b",
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
            timestamp="2026-03-06T12:00:00+00:00", model="qwen2.5:7b",
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
            timestamp=now_iso(), model="qwen2.5:7b", kernel_version=None,
            scores=DimensionScores(), overall=0.0,
        ),
    )
    save_scores(sf)

    data = json.loads(scores_path.read_text())
    assert "baseline" in data
    assert "mutations" in data
    assert data["baseline"]["kernel_version"] is None
    assert data["baseline"]["model"] == "qwen2.5:7b"
    for dim in ["structure_adherence", "challenge_reflex", "plan_first",
                "decision_logging", "ac_verification", "evolution_awareness"]:
        assert dim in data["baseline"]["scores"]
        val = data["baseline"]["scores"][dim]
        assert 0.0 <= val <= 1.0
