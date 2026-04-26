"""CLI smoke: existing v0.7 flags still work and route through v1.0 pipeline."""

import subprocess
import sys

import yaml


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "any2md", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_help_works():
    r = _run("--help")
    assert r.returncode == 0
    assert "any2md" in r.stdout.lower()
    assert "--strip-links" in r.stdout


def test_force_flag_overwrites(fixture_dir, tmp_output_dir):
    fixture = str(fixture_dir / "ligatures_and_softhyphens.txt")
    r1 = _run("-o", str(tmp_output_dir), fixture)
    assert r1.returncode == 0, r1.stderr
    r2 = _run("-o", str(tmp_output_dir), fixture)  # skip-existing
    assert "SKIP" in (r2.stdout + r2.stderr)
    r3 = _run("-o", str(tmp_output_dir), "--force", fixture)
    assert r3.returncode == 0, r3.stderr
    assert "OK" in (r3.stdout + r3.stderr) or "Done" in (r3.stdout + r3.stderr)


def test_strip_links_propagates_to_pipeline_options(fixture_dir, tmp_output_dir):
    # We can't directly inspect PipelineOptions from CLI, but the converted
    # file should have v1.0 frontmatter regardless. Smoke that the flag is
    # accepted and conversion succeeds.
    r = _run(
        "-o",
        str(tmp_output_dir),
        "--strip-links",
        str(fixture_dir / "ligatures_and_softhyphens.txt"),
    )
    assert r.returncode == 0, r.stderr
    out = list(tmp_output_dir.glob("*.md"))
    assert len(out) == 1
    text = out[0].read_text()
    end = text.index("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    assert fm["status"] == "draft"
