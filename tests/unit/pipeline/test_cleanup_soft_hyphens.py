"""Tests for C2 — strip_soft_hyphens."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.cleanup import strip_soft_hyphens


def test_strip_soft_hyphens_removes_u00ad():
    text = "ex­ists soft­hyphen"
    assert strip_soft_hyphens(text, PipelineOptions()) == "exists softhyphen"


def test_strip_soft_hyphens_no_match_is_noop():
    text = "no soft hyphens here"
    assert strip_soft_hyphens(text, PipelineOptions()) == text


def test_strip_soft_hyphens_preserves_regular_hyphens():
    text = "co-pilot integration"
    assert strip_soft_hyphens(text, PipelineOptions()) == text
