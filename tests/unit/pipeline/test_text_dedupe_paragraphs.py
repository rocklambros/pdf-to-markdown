"""Tests for T3 — dedupe_paragraphs."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import dedupe_paragraphs


def test_drops_consecutive_duplicate():
    text = "Para A.\n\nDuplicate para.\n\nDuplicate para.\n\nPara B.\n"
    out = dedupe_paragraphs(text, PipelineOptions())
    assert out.count("Duplicate para") == 1


def test_keeps_non_consecutive_duplicates():
    text = "Para A.\n\nPara B.\n\nPara A.\n"
    out = dedupe_paragraphs(text, PipelineOptions())
    assert out.count("Para A") == 2


def test_no_duplicates_is_noop():
    text = "First.\n\nSecond.\n\nThird.\n"
    assert dedupe_paragraphs(text, PipelineOptions()) == text


def test_handles_whitespace_only_difference():
    text = "Same content.\n\nSame content.  \n"
    out = dedupe_paragraphs(text, PipelineOptions())
    assert out.count("Same content") == 1
