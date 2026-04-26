"""Tests for C1 — nfc_normalize."""

import unicodedata

from any2md.pipeline import PipelineOptions
from any2md.pipeline.cleanup import nfc_normalize


def test_nfc_normalize_decomposed_to_composed():
    decomposed = "café"  # "café" in NFD form
    result = nfc_normalize(decomposed, PipelineOptions())
    assert result == "café"
    assert unicodedata.is_normalized("NFC", result)


def test_nfc_normalize_already_composed_is_noop():
    text = "already café"
    assert nfc_normalize(text, PipelineOptions()) == text


def test_nfc_normalize_empty_is_noop():
    assert nfc_normalize("", PipelineOptions()) == ""
