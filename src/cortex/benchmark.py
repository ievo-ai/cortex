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
RUNS_LOG = BENCHMARKS_DIR / "runs.jsonl"
PROMPTFOO_CONFIG = BENCHMARKS_DIR / "promptfooconfig.yaml"
DIST_IEVO_MD = CORTEX_ROOT / "dist" / "iEVO.md"

MODEL = "claude-haiku-4-5-20251001"

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
class SkillBenchmarkEntry:
    timestamp: str
    model: str
    scores: dict[str, float]
    overall: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "scores": self.scores,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SkillBenchmarkEntry:
        return cls(
            timestamp=d.get("timestamp", ""),
            model=d.get("model", MODEL),
            scores=d.get("scores", {}),
            overall=d.get("overall", 0.0),
        )


@dataclass
class SkillScores:
    baseline: SkillBenchmarkEntry | None = None
    mutations: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "mutations": self.mutations,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SkillScores:
        baseline = SkillBenchmarkEntry.from_dict(d["baseline"]) if d.get("baseline") else None
        return cls(baseline=baseline, mutations=d.get("mutations", []))


@dataclass
class AgentScores:
    baseline: BenchmarkEntry | None = None
    mutations: list[MutationEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "mutations": [m.to_dict() for m in self.mutations],
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentScores:
        baseline = BenchmarkEntry.from_dict(d["baseline"]) if d.get("baseline") else None
        mutations = [MutationEntry.from_dict(m) for m in d.get("mutations", [])]
        return cls(baseline=baseline, mutations=mutations)


@dataclass
class ScoresFile:
    naked: BenchmarkEntry | None = None
    baseline: BenchmarkEntry | None = None
    mutations: list[MutationEntry] = field(default_factory=list)
    agents: dict[str, AgentScores] = field(default_factory=dict)
    skills: dict[str, SkillScores] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "naked": self.naked.to_dict() if self.naked else None,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "mutations": [m.to_dict() for m in self.mutations],
            "agents": {name: ag.to_dict() for name, ag in self.agents.items()},
            "skills": {name: sk.to_dict() for name, sk in self.skills.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScoresFile:
        naked = BenchmarkEntry.from_dict(d["naked"]) if d.get("naked") else None
        baseline = BenchmarkEntry.from_dict(d["baseline"]) if d.get("baseline") else None
        mutations = [MutationEntry.from_dict(m) for m in d.get("mutations", [])]
        agents = {name: AgentScores.from_dict(v) for name, v in d.get("agents", {}).items()}
        skills = {name: SkillScores.from_dict(v) for name, v in d.get("skills", {}).items()}
        return cls(naked=naked, baseline=baseline, mutations=mutations, agents=agents, skills=skills)

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


def _load_env() -> None:
    """Load .env file into os.environ if it exists."""
    import os

    env_file = CORTEX_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def check_api_key() -> None:
    """Check that ANTHROPIC_API_KEY is set. Raises RuntimeError if not."""
    import os

    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set — add it to .env or export it"
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


def run_promptfoo(
    output_path: Path,
    config_path: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run promptfoo eval and write JSON output.

    config_path: optional override for the promptfoo config file.
    When None, uses PROMPTFOO_CONFIG (default kernel benchmark config).
    """
    effective_config = config_path if config_path is not None else PROMPTFOO_CONFIG
    if not effective_config.exists():
        raise FileNotFoundError(f"Config not found: {effective_config}")

    # Ensure .env is loaded (check_api_key does this, but be safe)
    _load_env()

    cmd = [
        "promptfoo", "eval",
        "--config", str(effective_config),
        "--output", str(output_path),
        "--no-progress-bar",
        "--no-cache",
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


def parse_results(output_path: Path, provider_label: str = "with-kernel") -> DimensionScores:
    """Parse promptfoo JSON output into dimension scores.

    Filters results to the given provider label (default: "with-kernel").
    promptfoo runs both providers on every test — we only want scores for one.
    """
    data = json.loads(output_path.read_text())

    results = data.get("results", data)
    test_results = results.get("results", [])

    # Group pass rates by dimension, filtered by provider
    dimension_passes: dict[str, list[bool]] = {d: [] for d in DIMENSIONS}

    for test in test_results:
        # Filter by provider label
        label = test.get("provider", {}).get("label", "")
        if label != provider_label:
            continue

        # Get dimension from test vars or description
        dim = None
        test_vars = test.get("vars", {})
        if "dimension" in test_vars:
            dim = test_vars["dimension"]
        else:
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


def append_run_log(
    naked: DimensionScores,
    kernel: DimensionScores,
    run_type: str = "kernel",
    extra: dict | None = None,
) -> None:
    """Append a run entry to the JSONL log file.

    run_type: "kernel" (default), "agent", or "skill"
    extra: additional fields to include (e.g. {"agent": "spec-writer"})
    """
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry: dict = {
        "timestamp": now_iso(),
        "type": run_type,
        "model": MODEL,
        "naked": naked.to_dict(),
        "naked_overall": naked.overall(),
        "kernel": kernel.to_dict(),
        "kernel_overall": kernel.overall(),
        "delta": kernel.overall() - naked.overall(),
    }
    if extra:
        entry.update(extra)
    with RUNS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def format_comparison_table(naked: DimensionScores, kernel: DimensionScores) -> list[str]:
    """Format a side-by-side comparison table. Returns lines."""
    lines = []
    lines.append(f"  {'Dimension':<25} {'Naked':>8} {'Kernel':>8} {'Delta':>8}")
    lines.append(f"  {'-' * 53}")
    for dim in DIMENSIONS:
        n = getattr(naked, dim)
        k = getattr(kernel, dim)
        d = k - n
        sign = "+" if d >= 0 else ""
        lines.append(f"  {dim:<25} {n:>8.2f} {k:>8.2f} {sign}{d:>7.2f}")
    lines.append(f"  {'-' * 53}")
    no = naked.overall()
    ko = kernel.overall()
    d = ko - no
    sign = "+" if d >= 0 else ""
    lines.append(f"  {'overall':<25} {no:>8.2f} {ko:>8.2f} {sign}{d:>7.2f}")
    return lines


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


def append_skill_run_log(
    skill_name: str,
    scores: dict[str, float],
    overall: float,
) -> None:
    """Append a skill run entry to the JSONL log file."""
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry: dict = {
        "timestamp": now_iso(),
        "type": "skill",
        "model": MODEL,
        "skill": skill_name,
        "scores": scores,
        "overall": overall,
    }
    with RUNS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Skill benchmark helpers
# ---------------------------------------------------------------------------

def parse_skill_results(output_path: Path) -> tuple[dict[str, float], float]:
    """Parse promptfoo JSON output for skill benchmarks.

    Returns (scores_by_test, overall) where scores_by_test maps test
    description to pass rate and overall is the mean across all tests.
    """
    data = json.loads(output_path.read_text())
    results = data.get("results", data)
    test_results = results.get("results", [])

    # Group by description
    passes_by_test: dict[str, list[bool]] = {}
    for test in test_results:
        desc = test.get("description", "unknown")
        if desc not in passes_by_test:
            passes_by_test[desc] = []
        passes_by_test[desc].append(test.get("success", False))

    scores: dict[str, float] = {}
    for desc, passes in passes_by_test.items():
        scores[desc] = sum(passes) / len(passes) if passes else 0.0

    overall = sum(scores.values()) / len(scores) if scores else 0.0
    return scores, overall


# Keyword map for dimension inference
_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "challenge_reflex": ["challenge", "question", "push back", "clarif", "ambig", "verify request"],
    "plan_first": ["plan", "plan first", "outline", "decompose", "blueprint"],
    "decision_logging": ["decision", "log", "rationale", "why", "record why", "document"],
    "ac_verification": ["acceptance", "ac-", "criteria", "verify ac", "check ac"],
    "structure_adherence": ["structure", "format", "template", "naming", "convention", "yaml"],
    "evolution_awareness": ["evolution", "evolve", "lesson", "learn", "improve", "tech debt"],
}


def infer_dimension(rule_text: str) -> str:
    """Infer the most relevant cognitive dimension from rule text.

    Uses keyword matching. Falls back to 'structure_adherence' if no match.
    """
    lower = rule_text.lower()
    for dim, keywords in _DIMENSION_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return dim
    return "structure_adherence"
