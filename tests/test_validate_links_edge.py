"""QA edge-case tests for validate_links() in build.py.

Scenarios not covered by the Coder's test_validate_links.py:
  1. lychee exits with code 1 (runtime error) vs code 2 (broken links) — both non-zero
  2. lychee found but not executable (PermissionError from subprocess)
  3. validate_links() called with a non-existent dist_dir path
  4. dist_dir exists but is completely empty — lychee still invoked (no short-circuit)
  5. lychee exits non-zero and produces output only on stdout (not stderr)
  6. lychee exits non-zero and produces output only on stderr (not stdout)
  7. lychee exits non-zero with both stdout and stderr empty (silent failure)
  8. sys.exit is called with the exact return code from lychee (not hardcoded)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from build import validate_links  # noqa: E402


# ---------------------------------------------------------------------------
# Exit code disambiguation — exit 1 (runtime error) vs exit 2 (broken links)
# ---------------------------------------------------------------------------


def test_qa_lychee_exit_code_1_treated_as_failure(tmp_path: Path) -> None:
    """lychee exit code 1 (runtime/config error) must also cause sys.exit(1).

    The Coder only tested returncode=2. Exit code 1 is a distinct lychee exit
    code meaning a runtime error (bad flag, unreadable file, etc.). Both must
    be treated as build failures.
    """
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "lychee: error: unrecognised flag --bogus"

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(SystemExit) as exc_info,
    ):
        validate_links(tmp_path)

    assert exc_info.value.code == 1, (
        f"Expected sys.exit(1) for lychee runtime error, got sys.exit({exc_info.value.code!r})"
    )


def test_qa_exit_code_preserved_exactly(tmp_path: Path) -> None:
    """sys.exit() is called with lychee's actual return code, not a hardcoded value.

    Verifies that validate_links() propagates any non-zero code, not just 1 or 2.
    lychee can exit with 3 in some versions to signal different failure modes.
    """
    for code in (1, 2, 3):
        mock_result = MagicMock()
        mock_result.returncode = code
        mock_result.stdout = f"lychee output for code {code}"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/local/bin/lychee"),
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(SystemExit) as exc_info,
        ):
            validate_links(tmp_path)

        assert exc_info.value.code == code, (
            f"Expected sys.exit({code}), got sys.exit({exc_info.value.code!r})"
        )


# ---------------------------------------------------------------------------
# lychee binary found but not executable
# ---------------------------------------------------------------------------


def test_qa_lychee_not_executable_propagates_error(tmp_path: Path) -> None:
    """If lychee exists on PATH but is not executable, subprocess raises PermissionError.

    shutil.which() returns a path as long as the file exists, regardless of
    execute permission. The resulting PermissionError from subprocess.run must
    not be swallowed — it should propagate to the caller so the build fails loudly.
    """
    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch(
            "subprocess.run",
            side_effect=PermissionError("[Errno 13] Permission denied: '/usr/local/bin/lychee'"),
        ),
        pytest.raises(PermissionError),
    ):
        validate_links(tmp_path)


# ---------------------------------------------------------------------------
# Non-existent dist_dir
# ---------------------------------------------------------------------------


def test_qa_nonexistent_dist_dir_still_calls_lychee(tmp_path: Path) -> None:
    """validate_links() does not pre-check if dist_dir exists; lychee handles it.

    The function should pass the path to lychee and let lychee report the error
    (exit non-zero). validate_links() must NOT silently skip when the dir is absent.
    This test verifies subprocess.run is called (not short-circuited).
    """
    nonexistent_dir = tmp_path / "does_not_exist"
    assert not nonexistent_dir.exists()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        validate_links(nonexistent_dir)  # must not raise (lychee returns 0)

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert str(nonexistent_dir) in cmd, (
        f"Expected nonexistent_dir in subprocess command, got: {cmd}"
    )


# ---------------------------------------------------------------------------
# Empty dist_dir — lychee still invoked
# ---------------------------------------------------------------------------


def test_qa_empty_dist_dir_still_calls_lychee(tmp_path: Path) -> None:
    """validate_links() does not short-circuit on an empty dist_dir.

    An empty dist/ could mean the build step silently failed. lychee should
    still be invoked so that any CI configuration relying on its output is
    consistent. validate_links() must never skip lychee just because the dir
    is empty.
    """
    empty_dir = tmp_path / "dist"
    empty_dir.mkdir()
    assert list(empty_dir.iterdir()) == []

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        validate_links(empty_dir)

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert str(empty_dir) in cmd


# ---------------------------------------------------------------------------
# Output routing — lychee output appears on stderr regardless of which stream
# ---------------------------------------------------------------------------


def test_qa_lychee_stdout_only_output_printed_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When lychee writes only to stdout, that output is printed to our stderr.

    validate_links() routes lychee's output to sys.stderr so it's visible in CI
    logs. This must hold when lychee only uses stdout (e.g. older lychee versions).
    """
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = "BROKEN: file.md#bad-anchor"
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(SystemExit),
    ):
        validate_links(tmp_path)

    captured = capsys.readouterr()
    assert "BROKEN" in captured.err, (
        f"Expected lychee stdout routed to stderr, got err={captured.err!r}"
    )


def test_qa_lychee_stderr_only_output_printed_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When lychee writes only to stderr, that output is forwarded to our stderr."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "lychee runtime error: cannot read directory"

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(SystemExit),
    ):
        validate_links(tmp_path)

    captured = capsys.readouterr()
    assert "runtime error" in captured.err, (
        f"Expected lychee stderr forwarded to our stderr, got err={captured.err!r}"
    )


def test_qa_silent_failure_still_exits(tmp_path: Path) -> None:
    """lychee exits non-zero with no output at all — build must still fail.

    Empty stdout and stderr is unusual but possible (e.g. lychee killed by OOM).
    validate_links() must call sys.exit() even when there is nothing to print.
    """
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(SystemExit) as exc_info,
    ):
        validate_links(tmp_path)

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# dist_dir path is passed as string (not Path) to subprocess
# ---------------------------------------------------------------------------


def test_qa_dist_dir_passed_as_string_to_subprocess(tmp_path: Path) -> None:
    """The dist_dir is converted to a string before being added to the command list.

    subprocess.run requires list elements to be strings. If a Path object is
    passed directly some environments raise TypeError. Verify the command list
    contains a str, not a Path.
    """
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/local/bin/lychee"),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        validate_links(tmp_path)

    cmd = mock_run.call_args[0][0]
    for elem in cmd:
        assert isinstance(elem, str), (
            f"All command elements must be str; found {type(elem).__name__!r}: {elem!r}"
        )
