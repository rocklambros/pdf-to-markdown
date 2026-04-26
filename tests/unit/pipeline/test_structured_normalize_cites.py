"""Tests for S3 — normalize_citations."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.structured import normalize_citations


def test_coalesces_adjacent_citations():
    text = "Statement [1] [2] [3]."
    out = normalize_citations(text, PipelineOptions())
    assert out == "Statement [1][2][3]."


def test_preserves_already_compact():
    text = "Statement [1][2]."
    assert normalize_citations(text, PipelineOptions()) == text


def test_no_citations_is_noop():
    text = "Plain prose with no brackets.\n"
    assert normalize_citations(text, PipelineOptions()) == text


def test_does_not_collapse_non_numeric_brackets():
    text = "See [appendix A] and [section B]."
    assert normalize_citations(text, PipelineOptions()) == text
