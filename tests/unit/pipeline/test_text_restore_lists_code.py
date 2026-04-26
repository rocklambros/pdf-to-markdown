"""Tests for T6 — restore_lists_and_code."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import restore_lists_and_code


def test_no_fenced_code_is_noop():
    text = "Plain prose.\nMore prose.\n"
    assert restore_lists_and_code(text, PipelineOptions()) == text


def test_existing_fenced_code_unchanged():
    text = "```\nfoo\nbar\nbaz\nqux\n```\n"
    out = restore_lists_and_code(text, PipelineOptions())
    assert out.count("```") == 2  # not double-wrapped


def test_wraps_indented_block_as_code():
    text = (
        "Some intro.\n\n"
        "    indented line one\n"
        "    indented line two\n"
        "    indented line three\n"
        "    indented line four\n\n"
        "Outro.\n"
    )
    out = restore_lists_and_code(text, PipelineOptions())
    assert "```" in out
    assert "indented line one" in out
