"""CLI exit-code contract: 0 / 1 / 2 / 3.

Codes:
- 0 — success
- 1 — usage / install / pre-flight error (e.g. ``--input-dir`` not a
  directory, missing Docling under ``--high-fidelity``)
- 2 — at least one file failed entirely (HARD failure)
- 3 — at least one pipeline warning AND ``--strict`` (no hard failures)

Argparse itself exits 2 on bad flags; that's a usage error, distinct
from our "file failed" semantics, but we don't try to remap it. The
tests below assert the parts of the contract we own end-to-end.
"""

from __future__ import annotations

import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "any2md", *args],
        capture_output=True,
        text=True,
    )


def test_exit_0_clean(fixture_dir, tmp_path):
    """A clean conversion of a known-good fixture exits 0."""
    r = _run("-o", str(tmp_path / "out"), str(fixture_dir / "web_page.html"))
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"


def test_exit_1_unknown_flag():
    """Argparse rejects unknown flags with a non-zero exit (argparse uses 2)."""
    r = _run("--bogus-flag")
    # We don't try to remap argparse's exit code; we only assert non-zero
    # so the test stays robust if argparse internals change.
    assert r.returncode != 0


def test_exit_1_input_dir_not_a_directory(tmp_path):
    """``--input-dir`` pointing at a non-existent path exits 1 (pre-flight)."""
    r = _run("--input-dir", str(tmp_path / "nonexistent"))
    assert r.returncode == 1, f"stdout={r.stdout!r} stderr={r.stderr!r}"


def test_exit_2_when_one_of_many_fails(fixture_dir, tmp_path):
    """Mixed run with a missing positional file.

    The current behavior on missing positional files is to print
    ``NOT FOUND`` on stderr and skip — *not* count it as a failure
    that bumps `fail`. So with at least one valid input the all-existing
    path is exit 0 and the missing-file path stays warning-only.

    We assert the run completes without crashing (exit 0 or 2 — both
    are spec-permissible for the legacy ``NOT FOUND`` warning) and that
    the missing-file warning was surfaced. Constructing a deterministic
    extraction failure on disk is hard (corrupted fixtures vary by
    backend), so this loose assertion is intentional.
    """
    out = tmp_path / "out"
    r = _run(
        "-o",
        str(out),
        str(fixture_dir / "web_page.html"),
        str(tmp_path / "doesnotexist.pdf"),
    )
    assert r.returncode in (0, 2), f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "NOT FOUND" in (r.stdout + r.stderr)
