# Cortex Cognitive Benchmark

Measures kernel value by comparing agent behavior WITH and WITHOUT `iEVO.md` as a system prompt. Uses [promptfoo](https://www.promptfoo.dev/) for A/B evaluation against a local Ollama model.

## Prerequisites

```bash
# Install Ollama
brew install ollama

# Start Ollama server
ollama serve

# Pull the benchmark model
ollama pull qwen2.5:7b

# Install dev dependencies (includes promptfoo)
uv sync --extra dev
```

## Usage

```bash
# Compile the kernel first
cortex compile

# Run benchmark and save scores
cortex benchmark run

# Run benchmark and compare against saved baseline
cortex benchmark compare
```

### `cortex benchmark run`

Runs promptfoo eval against current `dist/iEVO.md`, writes scores to `benchmarks/scores.json`. First run seeds the baseline (no prior scores to compare).

### `cortex benchmark compare`

Runs eval and compares against the saved baseline. Exits 0 if overall score >= baseline, exits 1 on regression. Used by `cortex mutate` (planned) to gate mutation acceptance.

## Cognitive Dimensions

Six behaviors the kernel should instil in agents:

| Dimension | What it measures |
|-----------|-----------------|
| `structure_adherence` | Writes YAML frontmatter, uses correct file formats |
| `challenge_reflex` | Asks clarifying questions before implementing |
| `plan_first` | Creates a plan before starting implementation |
| `decision_logging` | Records WHY, not just WHAT |
| `ac_verification` | Checks acceptance criteria before marking done |
| `evolution_awareness` | Flags lessons learned for kernel improvement |

Each dimension produces a pass rate (0.0–1.0). The overall score is the mean of all dimensions.

## Scores

Scores are tracked in `benchmarks/scores.json`:

```json
{
  "baseline": {
    "timestamp": "2026-03-06T12:00:00+00:00",
    "model": "qwen2.5:7b",
    "kernel_version": null,
    "scores": { "structure_adherence": 0.0, ... },
    "overall": 0.0
  },
  "mutations": []
}
```

The baseline is seeded on first run. Future mutations (via `cortex mutate`) append to the `mutations` array with delta and accept/reject status.

## Model Choice

**Qwen 2.5 7B Instruct** is the sweet spot: smart enough to understand agent tasks, weak enough that the kernel makes a visible difference. 70B+ models pass without any kernel (delta invisible). 3B models fail regardless.

## CI Integration

The benchmark is not a CI gate by default — it requires Ollama running locally. To add it to CI, you would need an Ollama service in the CI runner. The infrastructure supports it; integration is a separate task.
