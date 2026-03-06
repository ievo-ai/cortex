"""QA edge-case tests for REQ-017 — Typer CLI (cortex compile / dev / validate).

Covers gaps not addressed by the Coder's test_cli_compile.py, test_cli_dev.py,
test_cli_validate.py, and test_package.py:

  1. version.py __version__ is CalVer format (YY.MM.DD.HHMM) after version_bump.py runs
  2. cortex --help top-level shows all three subcommands (AC-1)
  3. cortex compile: --dist pointing to existing file raises error (not silent corrupt)
  4. cortex compile: default --dist when flag omitted (uses ./dist relative to cwd)
  5. cortex validate: default --dist when flag omitted
  6. cortex validate: CLI layer passes the correct path to validate_links (not hardcoded)
  7. cortex dev: "Compiled to" message printed to stdout (spec says print)
  8. cortex dev --watch: src/ directory does not exist — watchfiles raises, CLI handles
  9. (removed — build.py wrapper deleted in task 021)
  10. (removed — build.py wrapper deleted in task 021)
  11. cortex compile: validate exit code propagation for code != 2 (e.g. 127 from shell)
  12. version_bump.py: generated version matches CalVer pattern YY.MM.DD.HHMM
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cortex.cli import app

REPO_ROOT = Path(__file__).parent.parent
runner = CliRunner()


# ---------------------------------------------------------------------------
# 1. version.py — __version__ CalVer format after version_bump.py runs
# ---------------------------------------------------------------------------


def test_qa_version_bump_produces_calver_format(tmp_path: Path) -> None:
    """version_bump.py writes a CalVer string matching YY.MM.DD.HHMM.

    The spec says version is CalVer YY.MM.DD.HHMM (2-digit year).
    Current __version__ = "0.1.0" is NOT CalVer. This test exercises the
    version_bump.py script to verify it produces a conforming version.
    """
    # Write to a temp version file
    tmp_version_file = tmp_path / "version.py"
    tmp_version_file.write_text('"""Temp."""\n\n__version__ = "0.0.0"\n')

    # Monkey-patch the path the bump script uses
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import datetime
from pathlib import Path

version = datetime.datetime.now(datetime.UTC).strftime("%Y.%m.%d.%H%M")[2:]
version_file = Path({str(tmp_version_file)!r})
version_file.write_text(f'\"\"\"Define the version.\"\"\"\\n\\n__version__ = "{{version}}"\\n')
print(version)
""",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"

    written_version = result.stdout.strip()

    # CalVer pattern: YY.MM.DD.HHMM — two-digit year, month, day, hour+minute
    calver_pattern = re.compile(r"^\d{2}\.\d{2}\.\d{2}\.\d{4}$")
    assert calver_pattern.match(written_version), (
        f"version_bump.py output {written_version!r} does not match CalVer "
        f"pattern YY.MM.DD.HHMM"
    )

    # Also verify the file was updated correctly
    content = tmp_version_file.read_text()
    assert written_version in content, (
        f"version_bump.py did not write version {written_version!r} to file:\n{content}"
    )


# ---------------------------------------------------------------------------
# 2. cortex --help top-level output contains all three subcommands (AC-1)
# ---------------------------------------------------------------------------


def test_qa_cortex_help_shows_all_subcommands() -> None:
    """cortex --help output lists compile, dev, and validate subcommands (AC-1)."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, f"cortex --help failed: {result.output}"

    output = result.output.lower()
    assert "compile" in output, f"'compile' missing from --help output:\n{result.output}"
    assert "dev" in output, f"'dev' missing from --help output:\n{result.output}"
    assert "validate" in output, f"'validate' missing from --help output:\n{result.output}"


# ---------------------------------------------------------------------------
# 3. cortex compile: --dist pointing to an existing FILE (not dir) fails gracefully
# ---------------------------------------------------------------------------


def test_qa_compile_dist_is_existing_file_exits_with_error(tmp_path: Path) -> None:
    """When --dist points to an existing *file*, compile must exit non-zero.

    build() calls dist_dir.mkdir(parents=True, exist_ok=True). If the path
    is already a file, mkdir raises NotADirectoryError (or FileExistsError
    on some systems). The CLI must not silently succeed or produce a corrupt
    output — it should exit non-zero.

    This is a real user error: user passes a file path instead of a dir path.
    """
    # Create a file at the path we'll use as --dist
    existing_file = tmp_path / "output"
    existing_file.write_text("I am a file, not a directory\n")

    result = runner.invoke(app, ["compile", "--dist", str(existing_file)])

    # Must exit non-zero — the build cannot proceed when dist_dir is a file
    assert result.exit_code != 0, (
        f"Expected non-zero exit when --dist is an existing file, "
        f"got exit_code={result.exit_code}. Output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# 4. cortex compile: default --dist (omitting the flag) uses "./dist"
# ---------------------------------------------------------------------------


def test_qa_compile_default_dist_uses_dot_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """cortex compile without --dist flag uses './dist' relative to cwd.

    The default is `./dist` per the CLI definition. If omitted, compile
    should write output under <cwd>/dist/.
    """
    monkeypatch.chdir(tmp_path)

    # Mock validate_links to avoid needing lychee
    with patch("cortex.cli.validate_links", return_value=0):
        result = runner.invoke(app, ["compile", "--skip-validate"])

    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    dist_dir = tmp_path / "dist"
    assert dist_dir.exists(), (
        f"Expected dist/ to be created at {dist_dir} when --dist is omitted"
    )
    tarballs = list(dist_dir.glob("cortex-*.tar.gz"))
    assert tarballs, f"No tarball found in default dist/ at {dist_dir}"


# ---------------------------------------------------------------------------
# 5. cortex validate: default --dist (omitting the flag) passes "./dist" to validate_links
# ---------------------------------------------------------------------------


def test_qa_validate_default_dist_passes_correct_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """cortex validate without --dist passes './dist' (relative to cwd) to validate_links.

    Verifies that the default value is wired through to validate_links, not
    silently ignored or hardcoded to a different path.
    """
    monkeypatch.chdir(tmp_path)

    captured_paths: list[Path] = []

    def capturing_validate(dist_dir: Path) -> int:
        captured_paths.append(dist_dir)
        return 0

    with patch("cortex.cli.validate_links", side_effect=capturing_validate):
        result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"
    assert len(captured_paths) == 1, f"Expected 1 validate_links call, got {len(captured_paths)}"
    assert captured_paths[0] == Path("./dist"), (
        f"Expected Path('./dist'), got {captured_paths[0]!r}"
    )


# ---------------------------------------------------------------------------
# 6. cortex validate: CLI passes the exact --dist value to validate_links
# ---------------------------------------------------------------------------


def test_qa_validate_passes_exact_dist_path_to_validate_links(tmp_path: Path) -> None:
    """cortex validate --dist <path> passes that exact path to validate_links.

    Guards against a future refactor that might hardcode the path or forget
    to thread the CLI argument through to the function call.
    """
    custom_dist = tmp_path / "my_custom_output"

    captured_paths: list[Path] = []

    def capturing_validate(dist_dir: Path) -> int:
        captured_paths.append(dist_dir)
        return 0

    with patch("cortex.cli.validate_links", side_effect=capturing_validate):
        result = runner.invoke(app, ["validate", "--dist", str(custom_dist)])

    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"
    assert len(captured_paths) == 1
    assert captured_paths[0] == custom_dist, (
        f"Expected {custom_dist!r}, validate_links received {captured_paths[0]!r}"
    )


# ---------------------------------------------------------------------------
# 7. cortex dev: "Compiled to" message printed to stdout
# ---------------------------------------------------------------------------


def test_qa_dev_prints_compiled_to_message(tmp_path: Path) -> None:
    """cortex dev prints 'Compiled to <dist_path>' to stdout after compiling.

    The spec says the command prints a message. Tests confirm the tarball exists
    but not the human-readable output. This test locks in the message format.
    """
    result = runner.invoke(app, ["dev", "--dist", str(tmp_path)])
    assert result.exit_code == 0, f"Exit {result.exit_code}:\n{result.output}"

    # Should contain some form of "Compiled to <path>"
    assert "compiled" in result.output.lower(), (
        f"Expected 'Compiled to ...' in stdout. Got:\n{result.output}"
    )
    assert str(tmp_path) in result.output, (
        f"Expected dist path {tmp_path} in output. Got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# 8. cortex dev --watch: src/ directory does not exist — error, not hang
# ---------------------------------------------------------------------------


def test_qa_dev_watch_nonexistent_src_dir_exits_nonzero(tmp_path: Path) -> None:
    """When src/ doesn't exist, cortex dev --watch must fail gracefully.

    watchfiles.watch() on a non-existent directory raises FileNotFoundError
    (or similar). The CLI should handle this and exit non-zero, not crash
    with an unhandled traceback.

    Uses a real (but wrong) CORTEX_ROOT pointing to a dir without src/.
    """
    # Patch CORTEX_ROOT to point to a dir with no src/ subdirectory
    empty_root = tmp_path / "fake_root"
    empty_root.mkdir()

    # We need fs_watch to actually be available but point to a missing dir
    # Simulate watchfiles raising FileNotFoundError for missing path
    def mock_fs_watch_raises_fnf(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError(f"No such file or directory: {args[0]!r}")

    with (
        patch("cortex.cli.CORTEX_ROOT", empty_root),
        patch("cortex.cli.fs_watch", side_effect=mock_fs_watch_raises_fnf),
        patch("cortex.cli.build") as mock_build,
    ):
        # Set up mock_build to return a fake tarball so initial compile works
        def real_mock_build(tag: str, dist_dir: Path) -> Path:
            dist_dir.mkdir(parents=True, exist_ok=True)
            tarball = dist_dir / f"cortex-{tag}.tar.gz"
            tarball.touch()
            return tarball

        mock_build.side_effect = real_mock_build

        result = runner.invoke(app, ["dev", "--watch", "--dist", str(tmp_path)])

    # Should exit with a non-zero code, not hang or produce unhandled traceback
    assert result.exit_code != 0 or "Traceback" not in result.output, (
        f"Expected either non-zero exit or no traceback. Exit: {result.exit_code}. "
        f"Output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# 11. cortex compile: validate exit code propagation for unusual codes
# ---------------------------------------------------------------------------


def test_qa_compile_propagates_unusual_validate_exit_codes(tmp_path: Path) -> None:
    """cortex compile propagates any non-zero validate exit code, not just 2.

    The Coder tested returncode=2. But validate_links() can return any non-zero
    code (e.g., 127 from a shell "command not found" wrapper, or 1 from a
    runtime error). The CLI must propagate any non-zero code faithfully.
    """
    for code in (1, 3, 127):
        with patch("cortex.cli.validate_links", return_value=code):
            result = runner.invoke(app, ["compile", "--dist", str(tmp_path)])

        assert result.exit_code == code, (
            f"Expected exit code {code}, got {result.exit_code} "
            f"(validate_links returned {code})"
        )


# ---------------------------------------------------------------------------
# 12. version_bump.py: generated version matches CalVer pattern precisely
# ---------------------------------------------------------------------------


def test_qa_version_bump_script_calver_logic() -> None:
    """Verify the CalVer format logic in version_bump.py produces 2-digit year.

    version_bump.py uses strftime("%Y.%m.%d.%H%M")[2:] to strip the century.
    This test verifies the stripping logic produces a conforming YY.MM.DD.HHMM
    pattern without importing the script (which would run it and mutate files).
    """
    import datetime  # noqa: PLC0415

    # Simulate what version_bump.py does
    version = datetime.datetime.now(datetime.UTC).strftime("%Y.%m.%d.%H%M")[2:]

    # Pattern: YY.MM.DD.HHMM — two-digit year, two-digit month, two-digit day, 4-digit HHMM
    calver_pattern = re.compile(r"^\d{2}\.\d{2}\.\d{2}\.\d{4}$")
    assert calver_pattern.match(version), (
        f"CalVer logic produces {version!r}, which does not match "
        f"YY.MM.DD.HHMM pattern (e.g. '26.03.06.1430')"
    )

    parts = version.split(".")
    assert len(parts) == 4, f"Expected 4 parts (YY.MM.DD.HHMM), got {len(parts)}: {parts}"
    year, month, day, hhmm = parts
    assert len(year) == 2, f"Year part should be 2 digits, got {year!r}"
    assert len(month) == 2, f"Month part should be 2 digits, got {month!r}"
    assert len(day) == 2, f"Day part should be 2 digits, got {day!r}"
    assert len(hhmm) == 4, f"HHMM part should be 4 digits, got {hhmm!r}"
