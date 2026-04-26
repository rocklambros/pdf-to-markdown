"""Tests for SourceMeta and frontmatter module skeleton."""

import dataclasses

from any2md.frontmatter import SourceMeta


def test_source_meta_has_required_fields():
    fields = {f.name for f in dataclasses.fields(SourceMeta)}
    expected = {
        "title_hint", "authors", "organization", "date",
        "keywords", "pages", "word_count", "source_file",
        "source_url", "extracted_via", "lane",
    }
    assert expected <= fields, f"missing fields: {expected - fields}"


def test_source_meta_defaults_are_safe():
    meta = SourceMeta(
        title_hint=None, authors=[], organization=None, date=None,
        keywords=[], pages=None, word_count=None,
        source_file="x.txt", source_url=None,
        doc_type="txt", extracted_via="heuristic", lane="text",
    )
    assert meta.lane == "text"
    assert meta.extracted_via == "heuristic"
    assert meta.doc_type == "txt"


from any2md.frontmatter import estimate_tokens


def test_estimate_tokens_zero_on_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_ceil_chars_over_4():
    # 4 chars -> 1 token, 5 chars -> 2 tokens (ceil)
    assert estimate_tokens("a" * 4) == 1
    assert estimate_tokens("a" * 5) == 2
    assert estimate_tokens("a" * 8) == 2
