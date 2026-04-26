"""SSRM-compatible YAML frontmatter emitter.

See spec §3 (frontmatter contract) and §5.0 (SourceMeta dataclass).
This module is the single producer of the YAML block — converters
never touch YAML directly.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from any2md.pipeline import Lane


def compute_content_hash(body: str) -> str:
    """SHA-256 of NFC-normalized, LF-line-ended body. SSRM §5.1.

    The body MUST be the post-pipeline output (after C1-C5). This function
    re-applies NFC and LF normalization defensively so callers can pass any
    string and get a stable hash.
    """
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class SourceMeta:
    title_hint: str | None
    authors: list[str]
    organization: str | None
    date: str | None              # ISO-8601 YYYY-MM-DD
    keywords: list[str]
    pages: int | None             # PDFs only
    word_count: int | None        # DOCX/HTML/TXT (post-cleanup)
    source_file: str | None
    source_url: str | None
    doc_type: Literal["pdf", "docx", "html", "txt"]   # v0.7-compat extension
    extracted_via: Literal[
        "docling", "pymupdf4llm", "mammoth+markdownify",
        "trafilatura", "trafilatura+bs4_fallback", "heuristic",
    ]
    lane: Lane


def estimate_tokens(body: str) -> int:
    """Rough token estimate: ceil(chars / 4). Spec §3.2."""
    return math.ceil(len(body) / 4)


_H2_RE = re.compile(r"^##\s+\S.*$", re.MULTILINE)


def recommend_chunk_level(body: str) -> str:
    """Spec §3.2: h3 if any H2 section body > 1500 estimated tokens; else h2."""
    matches = list(_H2_RE.finditer(body))
    if not matches:
        return "h2"
    boundaries = [m.start() for m in matches] + [len(body)]
    for start, end in zip(boundaries, boundaries[1:]):
        section = body[start:end]
        if estimate_tokens(section) > 1500:
            return "h3"
    return "h2"


_H1_LINE_RE = re.compile(r"^#\s+\S.*$", re.MULTILINE)
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+\S")


def extract_abstract(body: str) -> str | None:
    """First non-heading paragraph >= 80 chars after H1, capped at 400.

    Returns None if no qualifying paragraph exists. Spec §3.2.
    """
    h1 = _H1_LINE_RE.search(body)
    if not h1:
        return None

    # Walk paragraphs after the H1 (split on blank lines).
    after = body[h1.end():]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", after)]
    for para in paragraphs:
        if not para:
            continue
        if _HEADING_LINE_RE.match(para):
            continue
        if len(para) < 80:
            continue
        # Truncate at last sentence boundary <= 400.
        if len(para) <= 400:
            return para
        head = para[:400]
        last_dot = head.rfind(".")
        if last_dot >= 80:
            return head[: last_dot + 1]
        return head.rstrip() + "..."
    return None


_FIRST_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"[*_]+")


def derive_title(body: str, title_hint: str | None, fallback: str) -> str:
    """Pick title: first H1, else hint, else cleaned filename stem."""
    m = _FIRST_H1_RE.search(body)
    if m:
        title = _MD_EMPHASIS_RE.sub("", m.group(1)).strip()
        if title:
            return title
    if title_hint:
        return title_hint.strip()
    stem = fallback.rsplit(".", 1)[0]
    return stem.replace("_", " ").strip() or "Untitled"
