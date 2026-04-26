"""Tests for the ``--no-arxiv-lookup`` CLI flag."""

import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "any2md", *args],
        capture_output=True,
        text=True,
    )


def test_no_arxiv_lookup_in_help():
    r = _run("--help")
    assert r.returncode == 0
    assert "--no-arxiv-lookup" in r.stdout


def test_no_arxiv_lookup_forwards_to_options(fixture_dir, tmp_path):
    """The flag parses cleanly and a normal conversion still succeeds."""
    out = tmp_path / "out"
    r = _run(
        "--no-arxiv-lookup",
        "-o",
        str(out),
        str(fixture_dir / "ligatures_and_softhyphens.txt"),
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_default_arxiv_lookup_enabled(fixture_dir, tmp_path):
    """Without the flag, conversion succeeds (default arxiv_lookup=True)."""
    out = tmp_path / "out"
    r = _run(
        "-o",
        str(out),
        str(fixture_dir / "ligatures_and_softhyphens.txt"),
    )
    assert r.returncode == 0, r.stdout + r.stderr
