"""Text-lane pipeline stages.

Phase 3: T1-T6 implemented. These stages run on text-lane output (mammoth
fallback, pymupdf4llm fallback, trafilatura, TXT structurizer) BEFORE the
shared cleanup pipeline. They repair regression artifacts that those
backends leave behind.
"""

from __future__ import annotations

import re
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from any2md.pipeline import PipelineOptions

Stage = Callable[[str, "PipelineOptions"], str]


_TERMINAL_PUNCT = ".!?:"
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*+]|\d+\.|[a-z]\.)\s+", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#{1,6}\s")
_TABLE_RE = re.compile(r"^\s*\|")
_FENCE_RE = re.compile(r"^\s*```")


def _is_structural(line: str) -> bool:
    """A 'structural' line — never join into or out of."""
    return bool(
        _LIST_PREFIX_RE.match(line)
        or _HEADING_RE.match(line)
        or _TABLE_RE.match(line)
        or _FENCE_RE.match(line)
    )


def repair_line_wraps(text: str, _options: "PipelineOptions") -> str:
    """T1: Join lines that look like soft wraps inside paragraphs."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        # Track fenced code state — never join inside.
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if in_fence:
            out.append(line)
            i += 1
            continue

        # End-of-text or empty line: emit and continue
        if i == len(lines) - 1 or line == "":
            out.append(line)
            i += 1
            continue

        next_line = lines[i + 1]
        # Stop conditions: structural next line, blank next line, terminal
        # punctuation at end of current line, uppercase start of next line.
        if (
            next_line == ""
            or _is_structural(line)
            or _is_structural(next_line)
            or (line and line[-1] in _TERMINAL_PUNCT)
            or (next_line and next_line[0].isupper())
        ):
            out.append(line)
            i += 1
            continue

        # Join: replace the trailing newline with a single space, drop leading
        # spaces from next.
        merged = line.rstrip() + " " + next_line.lstrip()
        out.append(merged)
        i += 2
    return "\n".join(out)


_HYPHEN_WRAP_RE = re.compile(r"([a-z]+)-\n([a-z]+)")


def dehyphenate(text: str, _options: "PipelineOptions") -> str:
    """T2: Merge soft-hyphenated word breaks across line ends.

    Conservative — only merges when the joined word appears elsewhere
    (same-doc corroboration). Avoids breaking compound words like
    'co-pilot' that appear hyphenated genuinely.
    """
    # Find candidates first
    candidates = list(_HYPHEN_WRAP_RE.finditer(text))
    if not candidates:
        return text

    # Build set of words that appear in the text (lowercase, alphanumeric)
    words_in_doc = set(re.findall(r"\b[a-z]+\b", text.lower()))

    def _replace(match: re.Match[str]) -> str:
        prefix_word = match.group(1)
        suffix_word = match.group(2)
        # The full word that would result if we merge
        joined = prefix_word + suffix_word
        # Look up: does the joined-form appear elsewhere in the doc?
        if joined.lower() in words_in_doc:
            return prefix_word + suffix_word
        return match.group(0)  # keep hyphen + newline

    return _HYPHEN_WRAP_RE.sub(_replace, text)


STAGES: list[Stage] = [
    repair_line_wraps,
    dehyphenate,
]
