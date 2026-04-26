"""Tests for C4 — normalize_quotes_dashes."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.cleanup import normalize_quotes_dashes


def test_smart_quotes_to_straight():
    text = "“hello” he said"
    assert normalize_quotes_dashes(text, PipelineOptions()) == '"hello" he said'


def test_smart_apostrophes_to_straight():
    text = "it’s a test"
    assert normalize_quotes_dashes(text, PipelineOptions()) == "it's a test"


def test_ellipsis_to_three_dots():
    text = "wait… what"
    assert normalize_quotes_dashes(text, PipelineOptions()) == "wait... what"


def test_em_dash_preserved():
    text = "foo — bar"
    assert normalize_quotes_dashes(text, PipelineOptions()) == "foo — bar"


def test_en_dash_preserved():
    text = "1990–2000"
    assert normalize_quotes_dashes(text, PipelineOptions()) == "1990–2000"
