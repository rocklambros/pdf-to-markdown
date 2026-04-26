"""End-to-end test for the CLI ``--meta KEY=VAL`` flag.

Confirms that values supplied on the command line replace derived
frontmatter fields in the emitted Markdown.
"""

from __future__ import annotations

import subprocess
import sys

import yaml


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "any2md", *args],
        capture_output=True,
        text=True,
    )


def test_meta_simple_override(fixture_dir, tmp_path):
    out = tmp_path / "out"
    r = _run(
        "-o",
        str(out),
        "--meta",
        "organization=OWASP",
        str(fixture_dir / "ligatures_and_softhyphens.txt"),
    )
    assert r.returncode == 0, r.stderr
    md = (out / "ligatures_and_softhyphens.md").read_text()
    end = md.index("\n---\n", 4)
    fm = yaml.safe_load(md[4:end])
    assert fm["organization"] == "OWASP"
