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
        append_run_log,
        check_api_key,
        check_promptfoo,
        format_comparison_table,
        load_scores,
        now_iso,
        parse_results,
        run_promptfoo,
        save_scores,
        MODEL,
    )

    try:
        check_api_key()
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
    # promptfoo exits non-zero when assertions fail (expected).
    # Only treat as error if output file wasn't written.
    if not output_path.exists() or output_path.stat().st_size == 0:
        if "not found" in (result.stderr or "").lower():
            print(f"Error: Model {MODEL} not found — pull with: ollama pull {MODEL}", file=sys.stderr)
        else:
            print(f"Error: promptfoo eval failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise typer.Exit(code=1)

    naked = parse_results(output_path, provider_label="baseline")
    kernel = parse_results(output_path, provider_label="with-kernel")
    output_path.unlink(missing_ok=True)

    # Log every run
    append_run_log(naked, kernel)

    # Print comparison table
    for line in format_comparison_table(naked, kernel):
        print(line)

    # Save scores
    ts = now_iso()
    naked_entry = BenchmarkEntry(
        timestamp=ts, model=MODEL, kernel_version=None,
        scores=naked, overall=naked.overall(),
    )
    kernel_entry = BenchmarkEntry(
        timestamp=ts, model=MODEL, kernel_version=None,
        scores=kernel, overall=kernel.overall(),
    )

    existing = load_scores()
    if existing is None:
        sf = ScoresFile(naked=naked_entry, baseline=kernel_entry, mutations=[])
        save_scores(sf)
        print("\n  Baseline seeded — no prior scores to compare")
    else:
        existing.naked = naked_entry
        existing.baseline = kernel_entry
        save_scores(existing)
        print("\n  Scores updated")


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
        append_run_log,
        check_api_key,
        check_promptfoo,
        compare_scores,
        format_comparison_table,
        load_scores,
        now_iso,
        parse_results,
        run_promptfoo,
        save_scores,
        MODEL,
    )

    try:
        check_api_key()
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
    # promptfoo exits non-zero when assertions fail (expected).
    # Only treat as error if output file wasn't written.
    if not output_path.exists() or output_path.stat().st_size == 0:
        if "not found" in (result.stderr or "").lower():
            print(f"Error: Model {MODEL} not found — pull with: ollama pull {MODEL}", file=sys.stderr)
        else:
            print(f"Error: promptfoo eval failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise typer.Exit(code=1)

    naked = parse_results(output_path, provider_label="baseline")
    kernel = parse_results(output_path, provider_label="with-kernel")
    output_path.unlink(missing_ok=True)

    # Log every run
    append_run_log(naked, kernel)

    # Print comparison table
    for line in format_comparison_table(naked, kernel):
        print(line)

    existing = load_scores()
    if existing is None:
        # First run — seed baseline, no comparison possible
        ts = now_iso()
        sf = ScoresFile(
            naked=BenchmarkEntry(timestamp=ts, model=MODEL, kernel_version=None, scores=naked, overall=naked.overall()),
            baseline=BenchmarkEntry(timestamp=ts, model=MODEL, kernel_version=None, scores=kernel, overall=kernel.overall()),
            mutations=[],
        )
        save_scores(sf)
        print("\n  No prior baseline — scores saved as new baseline")
        return

    baseline_overall = existing.last_accepted_overall()
    if baseline_overall is None:
        baseline_overall = 0.0

    passed, messages = compare_scores(kernel, baseline_overall)
    print()
    for msg in messages:
        print(msg)

    if not passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
