"""Tests for C6 — strip_footnote_markers (aggressive profile only)."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.cleanup import strip_footnote_markers


_BODY_WITH_MARKERS = (
    "This is a sentence[^1]. Another sentence with a marker¹.\n"
    "\n"
    "## Footnotes\n"
    "\n"
    "[^1]: First footnote.\n"
    "1. Footnote one numbered style.\n"
)


def test_aggressive_strips_inline_markers_keeps_footnotes_section():
    opts = PipelineOptions(profile="aggressive")
    out = strip_footnote_markers(_BODY_WITH_MARKERS, opts)
    assert "[^1]" not in out.split("## Footnotes")[0]
    assert "[^1]: First footnote." in out
    assert "¹" not in out.split("## Footnotes")[0]


def test_conservative_is_noop():
    opts = PipelineOptions(profile="conservative")
    assert strip_footnote_markers(_BODY_WITH_MARKERS, opts) == _BODY_WITH_MARKERS


def test_no_footnotes_section_is_noop_even_at_aggressive():
    opts = PipelineOptions(profile="aggressive")
    text = "This is a sentence[^1]. Another¹."
    # No "## Footnotes" or similar — keep markers, we have nothing to point to.
    assert strip_footnote_markers(text, opts) == text


def test_maximum_profile_also_strips():
    opts = PipelineOptions(profile="maximum")
    out = strip_footnote_markers(_BODY_WITH_MARKERS, opts)
    assert "[^1]" not in out.split("## Footnotes")[0]
