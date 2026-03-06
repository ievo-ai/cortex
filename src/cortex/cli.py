"""Cortex CLI — Typer application."""

from __future__ import annotations

import sys
import tempfile
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


@benchmark_app.command()
def agent(
    overlay_path: str = typer.Argument(..., help="Path to agent overlay markdown file"),
    dist: str = typer.Option("./dist", help="Directory with compiled iEVO.md"),
) -> None:
    """Run cognitive benchmark with a combined kernel + agent overlay system prompt.

    Reads dist/iEVO.md + the overlay file, creates a temp combined prompt,
    runs promptfoo eval, and stores scores under benchmarks/scores.json agents key.
    """
    from cortex.benchmark import (
        AgentScores,
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
        PROMPTFOO_CONFIG,
    )
    import yaml

    try:
        check_api_key()
        check_promptfoo()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    dist_ievo = Path(dist) / "iEVO.md"
    if not dist_ievo.exists():
        print(
            "Error: dist/iEVO.md not found — run `cortex compile` first",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    overlay = Path(overlay_path)
    if not overlay.exists():
        print(f"Error: overlay file not found: {overlay_path}", file=sys.stderr)
        raise typer.Exit(code=1)

    agent_name = overlay.stem  # e.g. "spec-writer" from "spec-writer.md"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Build combined system prompt: kernel + separator + overlay
        kernel_content = dist_ievo.read_text()
        overlay_content = overlay.read_text()
        combined = kernel_content + "\n\n---\n\n" + overlay_content
        combined_prompt_file = tmp / "combined_prompt.md"
        combined_prompt_file.write_text(combined)

        # Load the base promptfoo config and inject the combined prompt
        base_config = yaml.safe_load(PROMPTFOO_CONFIG.read_text())
        for provider in base_config.get("providers", []):
            if provider.get("label") == "with-kernel":
                provider.setdefault("config", {})
                provider["config"]["systemPrompt"] = f"file://{combined_prompt_file}"

        tmp_config = tmp / "config.yaml"
        tmp_config.write_text(yaml.dump(base_config, default_flow_style=False))

        output_path = tmp / "output.json"
        result = run_promptfoo(output_path, config_path=tmp_config)

        if not output_path.exists() or output_path.stat().st_size == 0:
            print(f"Error: promptfoo eval failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            raise typer.Exit(code=1)

        naked = parse_results(output_path, provider_label="baseline")
        kernel_with_overlay = parse_results(output_path, provider_label="with-kernel")

    # Print comparison table
    for line in format_comparison_table(naked, kernel_with_overlay):
        print(line)
    print(f"\n  Agent overlay: {overlay_path}")

    # Append to run log with type + agent
    append_run_log(naked, kernel_with_overlay, run_type="agent", extra={"agent": agent_name})

    # Store scores
    ts = now_iso()
    agent_entry = BenchmarkEntry(
        timestamp=ts, model=MODEL, kernel_version=None,
        scores=kernel_with_overlay, overall=kernel_with_overlay.overall(),
    )

    existing = load_scores()
    if existing is None:
        existing = ScoresFile()
    existing.agents[agent_name] = AgentScores(baseline=agent_entry, mutations=[])
    save_scores(existing)


@benchmark_app.command()
def skill(
    skill_path: str = typer.Argument(..., help="Path to skill markdown file"),
) -> None:
    """Run benchmark for a skill using its companion test config.

    Reads <skill-path> and looks for benchmarks/skills/<skill-name>.yaml.
    Injects skill content as system prompt, runs promptfoo eval, and stores
    scores under benchmarks/scores.json skills key. Always exits 0 (report only).
    """
    from cortex.benchmark import (
        ScoresFile,
        SkillBenchmarkEntry,
        SkillScores,
        append_skill_run_log,
        check_api_key,
        check_promptfoo,
        load_scores,
        now_iso,
        parse_skill_results,
        run_promptfoo,
        save_scores,
        BENCHMARKS_DIR,
        MODEL,
    )
    import yaml

    try:
        check_api_key()
        check_promptfoo()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    skill_file = Path(skill_path)
    if not skill_file.exists():
        print(f"Error: skill file not found: {skill_path}", file=sys.stderr)
        raise typer.Exit(code=1)

    skill_name = skill_file.stem
    skill_test_config = BENCHMARKS_DIR / "skills" / f"{skill_name}.yaml"
    if not skill_test_config.exists():
        print(
            f"No skill tests found: {skill_test_config} — create test file first",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    skill_content = skill_file.read_text()

    # Load skill test config and inject skill content as system prompt
    config = yaml.safe_load(skill_test_config.read_text())
    config["providers"] = [
        {
            "id": f"anthropic:messages:{MODEL}",
            "label": "skill",
            "config": {
                "temperature": 0,
                "max_tokens": 4096,
                "systemPrompt": skill_content,
            },
        }
    ]
    config.setdefault("prompts", ["{{prompt}}"])
    config.setdefault("defaultTest", {
        "options": {"provider": f"anthropic:messages:{MODEL}"}
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tmp_config = tmp / "skill_config.yaml"
        tmp_config.write_text(yaml.dump(config, default_flow_style=False))
        output_path = tmp / "output.json"

        result = run_promptfoo(output_path, config_path=tmp_config)

        if not output_path.exists() or output_path.stat().st_size == 0:
            print(f"Error: promptfoo eval failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            raise typer.Exit(code=1)

        scores, overall = parse_skill_results(output_path)

    # Print per-test results
    print(f"\n  Skill: {skill_name}")
    print(f"  {'Test':<40} {'Score':>6}")
    print(f"  {'-' * 48}")
    for test_name, score in scores.items():
        status = "PASS" if score >= 1.0 else f"{score:.0%}"
        print(f"  {test_name:<40} {status:>6}")
    print(f"  {'-' * 48}")
    print(f"  {'overall':<40} {overall:>6.2f}")

    # Log run
    append_skill_run_log(skill_name, scores, overall)

    # Store scores
    ts = now_iso()
    skill_entry = SkillBenchmarkEntry(
        timestamp=ts, model=MODEL, scores=scores, overall=overall,
    )

    existing = load_scores()
    if existing is None:
        existing = ScoresFile()
    existing.skills[skill_name] = SkillScores(baseline=skill_entry, mutations=[])
    save_scores(existing)


@benchmark_app.command()
def generate(
    rule_text: str = typer.Argument(..., help="Text of the new rule being added to a brain region"),
    dimension: str = typer.Option(
        None, "--dimension", help="Cognitive dimension (inferred from rule text if omitted)"
    ),
    append: bool = typer.Option(False, "--append", help="Append generated test case to promptfooconfig.yaml"),
) -> None:
    """Generate a promptfoo test case for a new kernel rule.

    Uses Claude (Anthropic API) to generate a test case that verifies the rule.
    Prints YAML to stdout by default. Use --append to write to promptfooconfig.yaml.
    """
    from cortex.benchmark import (
        check_api_key,
        generate_test_case,
        infer_dimension,
        PROMPTFOO_CONFIG,
    )
    import yaml

    try:
        check_api_key()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    # Infer dimension if not provided
    effective_dimension = dimension if dimension else infer_dimension(rule_text)

    try:
        generated_yaml = generate_test_case(rule_text, effective_dimension)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    print(generated_yaml)

    if append:
        # YAML round-trip: load existing config, append test, write back
        existing_config = yaml.safe_load(PROMPTFOO_CONFIG.read_text())
        new_test = yaml.safe_load(generated_yaml)

        # new_test may be a list (YAML list item starting with -) or a dict
        if isinstance(new_test, list):
            new_test = new_test[0]

        existing_config.setdefault("tests", [])
        existing_config["tests"].append(new_test)
        PROMPTFOO_CONFIG.write_text(yaml.dump(existing_config, default_flow_style=False))
        print("Appended to promptfooconfig.yaml")


if __name__ == "__main__":
    app()
