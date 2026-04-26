"""Tests for C8 — decode_html_entities."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.cleanup import decode_html_entities


def test_decodes_amp_in_body_text():
    text = "AT&amp;T merger announced."
    out = decode_html_entities(text, PipelineOptions())
    assert out == "AT&T merger announced."


def test_decodes_lt_and_gt():
    text = "Use &lt;div&gt; tags here."
    out = decode_html_entities(text, PipelineOptions())
    assert out == "Use <div> tags here."


def test_decodes_numeric_entities():
    text = "em-dash &#x2014; and another &#8212; here."
    out = decode_html_entities(text, PipelineOptions())
    assert out == "em-dash — and another — here."


def test_preserves_entities_inside_fenced_code_blocks():
    text = (
        "Body text with &amp; entity.\n"
        "\n"
        "```html\n"
        "<p>Raw &amp; preserved &lt;b&gt;</p>\n"
        "```\n"
        "\n"
        "Trailing &amp; entity.\n"
    )
    out = decode_html_entities(text, PipelineOptions())
    assert "Body text with & entity." in out
    assert "Trailing & entity." in out
    # Code block content untouched
    assert "<p>Raw &amp; preserved &lt;b&gt;</p>" in out


def test_conservative_profile_still_applies():
    text = "AT&amp;T body."
    out = decode_html_entities(text, PipelineOptions(profile="conservative"))
    assert out == "AT&T body."


def test_no_entities_is_noop():
    text = "Plain text without any entities here.\nSecond line.\n"
    out = decode_html_entities(text, PipelineOptions())
    assert out == text
