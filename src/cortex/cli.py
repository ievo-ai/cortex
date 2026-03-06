"""Cortex CLI — Typer application."""

from __future__ import annotations

import sys
from pathlib import Path

import jinja2
import typer

from cortex.compile import CORTEX_ROOT, build, validate_links
from cortex.version import __version__

app = typer.Typer(name="cortex", help="Cortex kernel compilation CLI.")

# NAMING HAZARD (S-4): `watch` is a CLI param on dev command — alias the fs_watch import
# to avoid shadowing the local bool parameter. This import is module-level for mockability.
try:
    from watchfiles import watch as fs_watch
except ImportError:
    fs_watch = None  # type: ignore[assignment]


@app.command()
def compile(
    dist: str = typer.Option("./dist", help="Output directory"),
    skip_validate: bool = typer.Option(False, "--skip-validate", help="Skip link validation"),
) -> None:
    """Render templates, prepare agents, validate links, create output in dist/.

    Reads version from package (__version__, CalVer). Validation is included by
    default. Use --skip-validate to render only (e.g. when lychee is not available).
    """
    tag = __version__
    dist_path = Path(dist)
    try:
        tarball = build(tag=tag, dist_dir=dist_path)
    except (FileNotFoundError, jinja2.UndefinedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)
    if not skip_validate:
        rc = validate_links(dist_path)
        if rc != 0:
            raise typer.Exit(code=rc)
    print(f"Compiled: {tarball}")


@app.command()
def validate(
    dist: str = typer.Option("./dist", help="Output directory"),
) -> None:
    """Standalone lychee validation on already-compiled output in dist/.

    Does not recompile. If lychee is not on PATH, prints a warning and exits 0.
    If lychee finds broken links, exits with lychee's return code.
    """
    rc = validate_links(Path(dist))
    if rc != 0:
        raise typer.Exit(code=rc)


@app.command()
def dev(
    watch: bool = typer.Option(False, "--watch", help="Watch templates/ for changes and recompile"),
    dist: str = typer.Option("./dist", help="Output directory"),
) -> None:
    """Single compile for development. Use --watch to recompile on file changes.

    Uses tag 'dev' (not __version__) for fast iteration. Validates links after
    each compile (warns if lychee not installed). Run `cortex compile` for a full build.
    """
    dist_path = Path(dist)
    # Initial compile
    build(tag="dev", dist_dir=dist_path)
    validate_links(dist_path)
    print(f"Compiled to {dist_path}")

    if not watch:
        return

    # NAMING HAZARD (S-4): `watch` is the bool param above — use `fs_watch` alias
    if fs_watch is None:
        print(
            "Error: watchfiles not installed. Run: uv sync --extra dev",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    try:
        for changes in fs_watch(CORTEX_ROOT / "templates"):
            print(f"Recompiling... {changes}")
            build(tag="dev", dist_dir=dist_path)
            validate_links(dist_path)
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Benchmark sub-app
# ---------------------------------------------------------------------------

benchmark_app = typer.Typer(name="benchmark", help="Cognitive benchmark for kernel validation.")
app.add_typer(benchmark_app)


@benchmark_app.command()
def run(
    dist: str = typer.Option("./dist", help="Directory with compiled iEVO.md"),
) -> None:
    """Run cognitive benchmark and save scores.

    Runs promptfoo eval against current dist/iEVO.md, writes scores to
    benchmarks/scores.json. First run seeds the baseline (no prior scores).
    """
    from cortex.benchmark import (
        BenchmarkEntry,
        ScoresFile,
        check_ollama,
        check_promptfoo,
        load_scores,
        now_iso,
        parse_results,
        run_promptfoo,
        save_scores,
        MODEL,
    )

    try:
        check_ollama()
        check_promptfoo()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    # Ensure dist/iEVO.md exists
    dist_ievo = Path(dist) / "iEVO.md"
    if not dist_ievo.exists():
        print(f"Error: {dist_ievo} not found — run `cortex compile` first", file=sys.stderr)
        raise typer.Exit(code=1)

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_path = Path(tmp.name)

    result = run_promptfoo(output_path)
    if result.returncode != 0:
        if "not found" in (result.stderr or "").lower():
            print(f"Error: Model {MODEL} not found — pull with: ollama pull {MODEL}", file=sys.stderr)
        else:
            print(f"Error: promptfoo eval failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise typer.Exit(code=1)

    scores = parse_results(output_path)
    output_path.unlink(missing_ok=True)

    existing = load_scores()
    if existing is None:
        # First run — seed baseline
        entry = BenchmarkEntry(
            timestamp=now_iso(), model=MODEL, kernel_version=None,
            scores=scores, overall=scores.overall(),
        )
        sf = ScoresFile(baseline=entry, mutations=[])
        save_scores(sf)
        print("Baseline seeded — no prior scores to compare")
    else:
        # Update baseline scores
        existing.baseline = BenchmarkEntry(
            timestamp=now_iso(), model=MODEL, kernel_version=None,
            scores=scores, overall=scores.overall(),
        )
        save_scores(existing)
        print("Scores updated")

    for dim in scores.to_dict():
        print(f"  {dim}: {getattr(scores, dim):.2f}")
    print(f"  overall: {scores.overall():.2f}")


@benchmark_app.command()
def compare(
    dist: str = typer.Option("./dist", help="Directory with compiled iEVO.md"),
) -> None:
    """Run benchmark and compare against baseline.

    Exits 0 if all scores >= baseline. Exits 1 on regression.
    First run seeds baseline and exits 0 (no regression possible).
    """
    from cortex.benchmark import (
        BenchmarkEntry,
        ScoresFile,
        check_ollama,
        check_promptfoo,
        compare_scores,
        load_scores,
        now_iso,
        parse_results,
        run_promptfoo,
        save_scores,
        MODEL,
    )

    try:
        check_ollama()
        check_promptfoo()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    dist_ievo = Path(dist) / "iEVO.md"
    if not dist_ievo.exists():
        print(f"Error: {dist_ievo} not found — run `cortex compile` first", file=sys.stderr)
        raise typer.Exit(code=1)

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_path = Path(tmp.name)

    result = run_promptfoo(output_path)
    if result.returncode != 0:
        if "not found" in (result.stderr or "").lower():
            print(f"Error: Model {MODEL} not found — pull with: ollama pull {MODEL}", file=sys.stderr)
        else:
            print(f"Error: promptfoo eval failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise typer.Exit(code=1)

    scores = parse_results(output_path)
    output_path.unlink(missing_ok=True)

    existing = load_scores()
    if existing is None:
        # First run — seed baseline, no comparison possible
        entry = BenchmarkEntry(
            timestamp=now_iso(), model=MODEL, kernel_version=None,
            scores=scores, overall=scores.overall(),
        )
        sf = ScoresFile(baseline=entry, mutations=[])
        save_scores(sf)
        print("No prior baseline — scores saved as new baseline")
        for dim in scores.to_dict():
            print(f"  {dim}: {getattr(scores, dim):.2f}")
        print(f"  overall: {scores.overall():.2f}")
        return

    baseline_overall = existing.last_accepted_overall()
    if baseline_overall is None:
        baseline_overall = 0.0

    passed, messages = compare_scores(scores, baseline_overall)
    for msg in messages:
        print(msg)

    if not passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
