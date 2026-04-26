"""Shared cleanup stages (always last). See spec §4.3."""

from __future__ import annotations

import unicodedata
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from any2md.pipeline import PipelineOptions

Stage = Callable[[str, "PipelineOptions"], str]


def nfc_normalize(text: str, _options: "PipelineOptions") -> str:
    """C1: NFC unicode normalization. Required by SSRM §5.1 for content_hash."""
    return unicodedata.normalize("NFC", text)


def strip_soft_hyphens(text: str, _options: "PipelineOptions") -> str:
    """C2: Remove U+00AD soft hyphen. Frequent PDF artifact."""
    return text.replace("­", "")


STAGES: list[Stage] = [
    nfc_normalize,
    strip_soft_hyphens,
]
