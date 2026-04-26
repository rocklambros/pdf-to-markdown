"""Unit tests for ``frontmatter.compose(overrides=...)``.

The ``overrides`` arg lets callers (CLI ``--meta`` / ``--meta-file`` /
``.any2md.toml``) deep-merge user-supplied values into the derived field
map *after* derivation but *before* YAML emission. Overrides win over
derived values; nested dicts merge recursively; lists/scalars replace.
"""

from __future__ import annotations

import yaml

from any2md.frontmatter import SourceMeta, compose
from any2md.pipeline import PipelineOptions


def _meta(**kw):
    base = dict(
        title_hint=None,
        authors=[],
        organization=None,
        date=None,
        keywords=[],
        pages=None,
        word_count=None,
        source_file="x.txt",
        source_url=None,
        doc_type="txt",
        extracted_via="heuristic",
        lane="text",
    )
    base.update(kw)
    return SourceMeta(**base)


def _fm(text: str) -> dict:
    """Parse the YAML frontmatter block from a composed document."""
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_simple_override():
    out = compose(
        "# T\n\nbody\n",
        _meta(),
        PipelineOptions(),
        overrides={"organization": "OWASP"},
    )
    assert _fm(out)["organization"] == "OWASP"


def test_array_override():
    out = compose(
        "# T\n\nbody\n",
        _meta(),
        PipelineOptions(),
        overrides={"authors": ["Alice", "Bob"]},
    )
    assert _fm(out)["authors"] == ["Alice", "Bob"]


def test_nested_override():
    out = compose(
        "# T\n\nbody\n",
        _meta(),
        PipelineOptions(),
        overrides={"generation_metadata": {"authored_by": "human"}},
    )
    fm = _fm(out)
    assert fm["generation_metadata"]["authored_by"] == "human"


def test_override_wins_over_derived():
    # title would normally come from H1
    out = compose(
        "# Auto\n\nbody\n",
        _meta(),
        PipelineOptions(),
        overrides={"title": "Manual"},
    )
    assert _fm(out)["title"] == "Manual"
