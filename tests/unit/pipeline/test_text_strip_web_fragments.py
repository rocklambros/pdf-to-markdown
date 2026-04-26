"""Tests for T10 — strip_web_fragments."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import strip_web_fragments


def test_drops_orphan_punctuation_lines():
    text = (
        "Real paragraph one.\n"
        "\n"
        "|\n"
        "\n"
        ">\n"
        "\n"
        "Real paragraph two.\n"
    )
    out = strip_web_fragments(text, PipelineOptions(profile="aggressive"))
    assert "Real paragraph one." in out
    assert "Real paragraph two." in out
    # Orphan single-character lines gone
    lines = [ln.strip() for ln in out.split("\n")]
    assert "|" not in lines
    assert ">" not in lines


def test_drops_short_incomplete_sentence_between_blanks():
    text = (
        "Real paragraph here.\n"
        "\n"
        "fragment text\n"
        "\n"
        "Another real paragraph follows.\n"
    )
    out = strip_web_fragments(text, PipelineOptions(profile="aggressive"))
    assert "Real paragraph here." in out
    assert "Another real paragraph follows." in out
    assert "fragment text" not in out


def test_keeps_short_legitimate_heading_text():
    text = (
        "Real paragraph here.\n"
        "\n"
        "Contents\n"
        "\n"
        "Another real paragraph.\n"
    )
    out = strip_web_fragments(text, PipelineOptions(profile="aggressive"))
    assert "Contents" in out


def test_conservative_profile_is_noop():
    text = (
        "Real paragraph.\n"
        "\n"
        "|\n"
        "\n"
        "fragment text\n"
        "\n"
        "Another paragraph.\n"
    )
    out = strip_web_fragments(text, PipelineOptions(profile="conservative"))
    assert out == text
