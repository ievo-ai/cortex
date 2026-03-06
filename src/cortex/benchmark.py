"""Cortex cognitive benchmark — measures kernel value via promptfoo + Ollama.

Runs the same test cases against two LLM configurations:
- Baseline: Qwen 2.5 7B without system prompt (naked model)
- Mutation: Qwen 2.5 7B with compiled iEVO.md as system prompt

Scores are tracked in benchmarks/scores.json for monotonic improvement.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cortex.compile import CORTEX_ROOT

BENCHMARKS_DIR = CORTEX_ROOT / "benchmarks"
SCORES_FILE = BENCHMARKS_DIR / "scores.json"
PROMPTFOO_CONFIG = BENCHMARKS_DIR / "promptfooconfig.yaml"
DIST_IEVO_MD = CORTEX_ROOT / "dist" / "iEVO.md"

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
MODEL = "qwen2.5:7b"

DIMENSIONS = [
    "structure_adherence",
    "challenge_reflex",
    "plan_first",
    "decision_logging",
    "ac_verification",
    "evolution_awareness",
]


@dataclass
class DimensionScores:
    structure_adherence: float = 0.0
    challenge_reflex: float = 0.0
    plan_first: float = 0.0
    decision_logging: float = 0.0
    ac_verification: float = 0.0
    evolution_awareness: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> DimensionScores:
        return cls(**{k: d.get(k, 0.0) for k in DIMENSIONS})

    def overall(self) -> float:
        values = [getattr(self, d) for d in DIMENSIONS]
        return sum(values) / len(values) if values else 0.0


@dataclass
class BenchmarkEntry:
    timestamp: str
    model: str
    kernel_version: str | None
    scores: DimensionScores
    overall: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "kernel_version": self.kernel_version,
            "scores": self.scores.to_dict(),
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BenchmarkEntry:
        scores = DimensionScores.from_dict(d.get("scores", {}))
        return cls(
            timestamp=d.get("timestamp", ""),
            model=d.get("model", MODEL),
            kernel_version=d.get("kernel_version"),
            scores=scores,
            overall=d.get("overall", scores.overall()),
        )


@dataclass
class MutationEntry:
    id: int
    timestamp: str
    kernel_version: str
    region: str
    lesson: str
    scores: DimensionScores
    overall: float
    delta: float
    status: str  # "accepted" or "rejected"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "kernel_version": self.kernel_version,
            "region": self.region,
            "lesson": self.lesson,
            "scores": self.scores.to_dict(),
            "overall": self.overall,
            "delta": self.delta,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MutationEntry:
        scores = DimensionScores.from_dict(d.get("scores", {}))
        return cls(
            id=d.get("id", 0),
            timestamp=d.get("timestamp", ""),
            kernel_version=d.get("kernel_version", ""),
            region=d.get("region", ""),
            lesson=d.get("lesson", ""),
            scores=scores,
            overall=d.get("overall", scores.overall()),
            delta=d.get("delta", 0.0),
            status=d.get("status", ""),
        )


@dataclass
class ScoresFile:
    baseline: BenchmarkEntry | None = None
    mutations: list[MutationEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "mutations": [m.to_dict() for m in self.mutations],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScoresFile:
        baseline = BenchmarkEntry.from_dict(d["baseline"]) if d.get("baseline") else None
        mutations = [MutationEntry.from_dict(m) for m in d.get("mutations", [])]
        return cls(baseline=baseline, mutations=mutations)

    def last_accepted_overall(self) -> float | None:
        accepted = [m for m in self.mutations if m.status == "accepted"]
        if accepted:
            return accepted[-1].overall
        if self.baseline:
            return self.baseline.overall
        return None


def load_scores() -> ScoresFile | None:
    if not SCORES_FILE.exists():
        return None
    data = json.loads(SCORES_FILE.read_text())
    return ScoresFile.from_dict(data)


def save_scores(scores: ScoresFile) -> None:
    SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCORES_FILE.write_text(json.dumps(scores.to_dict(), indent=2) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_ollama() -> None:
    """Check that Ollama is reachable. Raises RuntimeError if not."""
    import urllib.request
    import urllib.error

    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            model_names = [m.get("name", "") for m in data.get("models", [])]
            # Check if model is pulled (match with or without tag)
            found = any(MODEL in name for name in model_names)
            if not found:
                raise RuntimeError(
                    f"Model {MODEL} not found — pull with: ollama pull {MODEL}"
                )
    except urllib.error.URLError:
        raise RuntimeError(
            f"Ollama not reachable at {OLLAMA_HOST}:{OLLAMA_PORT} — start with: ollama serve"
        )


def check_promptfoo() -> str:
    """Find promptfoo binary. Returns the command name."""
    if shutil.which("promptfoo"):
        return "promptfoo"
    # Try via uv run
    result = subprocess.run(
        ["uv", "run", "promptfoo", "--version"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return "uv run promptfoo"
    raise RuntimeError(
        "promptfoo not found — install with: uv sync --extra dev"
    )


def run_promptfoo(output_path: Path) -> subprocess.CompletedProcess:
    """Run promptfoo eval and write JSON output."""
    if not PROMPTFOO_CONFIG.exists():
        raise FileNotFoundError(f"Config not found: {PROMPTFOO_CONFIG}")

    cmd = [
        "promptfoo", "eval",
        "--config", str(PROMPTFOO_CONFIG),
        "--output", str(output_path),
        "--no-progress-bar",
    ]

    # If promptfoo is not directly on PATH, use uv run
    if not shutil.which("promptfoo"):
        cmd = ["uv", "run"] + cmd

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=CORTEX_ROOT,
    )


def parse_results(output_path: Path) -> DimensionScores:
    """Parse promptfoo JSON output into dimension scores."""
    data = json.loads(output_path.read_text())

    results = data.get("results", data)
    test_results = results.get("results", [])

    # Group pass rates by dimension (from test metadata or description)
    dimension_passes: dict[str, list[bool]] = {d: [] for d in DIMENSIONS}

    for test in test_results:
        # Get dimension from test vars or description
        dim = None
        test_vars = test.get("vars", {})
        if "dimension" in test_vars:
            dim = test_vars["dimension"]
        else:
            # Try to infer from description
            desc = test.get("description", "").lower()
            for d in DIMENSIONS:
                if d.replace("_", " ") in desc or d.replace("_", "-") in desc:
                    dim = d
                    break

        if dim and dim in dimension_passes:
            dimension_passes[dim].append(test.get("success", False))

    # Calculate pass rate per dimension
    scores = {}
    for dim in DIMENSIONS:
        passes = dimension_passes[dim]
        scores[dim] = sum(passes) / len(passes) if passes else 0.0

    return DimensionScores.from_dict(scores)


def compare_scores(
    current: DimensionScores, baseline_overall: float
) -> tuple[bool, list[str]]:
    """Compare current scores against baseline. Returns (passed, messages)."""
    messages = []
    current_overall = current.overall()
    passed = current_overall >= baseline_overall

    for dim in DIMENSIONS:
        score = getattr(current, dim)
        messages.append(f"  {dim}: {score:.2f}")

    messages.append(f"  overall: {current_overall:.2f} (baseline: {baseline_overall:.2f})")

    if passed:
        delta = current_overall - baseline_overall
        messages.append(f"  PASSED (+{delta:.2f})")
    else:
        delta = current_overall - baseline_overall
        messages.append(f"  REGRESSED ({delta:.2f})")

    return passed, messages
