"""any2md/heuristics.py

Field-derivation refinements that go beyond what raw extractors give us.
Every function is pure (input → output, no side effects) except
arxiv_lookup which makes one network call and emits a warning on failure.

Called from frontmatter.compose() and converter modules to refine
candidate values before YAML emission.
"""

from __future__ import annotations

import html
import re
from typing import NamedTuple

from any2md.pipeline import Profile  # type alias


# --------------------------------------------------------------------- #
# Internal regexes & constants (spec §4.2)
# --------------------------------------------------------------------- #

# PDF Creator strings that mean "software", not "organization"
_SOFTWARE_CREATORS_RE = re.compile(
    r"^(LaTeX|.*acmart|.*pdfTeX|.*XeTeX|.*LuaTeX|"
    r"Adobe (InDesign|Acrobat|Illustrator|PageMaker|FrameMaker|Distiller)|"
    r"Microsoft.{0,20}Word|Microsoft.{0,20}Office|Microsoft.{0,20}PowerPoint|"
    r"Apple Pages|LibreOffice|OpenOffice|Calligra|"
    r"Pandoc|Typst|Quarto|Sphinx|MkDocs|"
    r"PyMuPDF|HTML Tidy|wkhtmltopdf|Chromium|Headless Chrome|"
    r"Word for|Mac OS X|Skia/PDF|Outlook|"
    r"Google Docs|Notion|Obsidian)",
    re.IGNORECASE,
)

# Cover-page H1 values to skip (case-insensitive after stripping)
_COVER_PAGE_H1_VALUES = frozenset({
    "international standard",
    "technical report",
    "technical specification",
    "publicly available specification",
    "draft international standard",
    "final draft international standard",
    "white paper",
    "whitepaper",
    "research note",
    "request for comments",
})

# H1 / H2 line detectors (markdown ATX style)
_H1_LINE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_LINE_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# DOCX line-break course-code / document-type prefix detector. Matches
# strings like "COMP 4441 Final Project " (course code followed by
# document-type marker). The trailing space is required so we only
# split when there's content after the marker.
_DOCX_PREFIX_RE = re.compile(
    r"^(?:[A-Z]{2,5}\s*\d{2,5}\s+)?"
    r"(?:Final Project|Final Paper|Term Paper|Thesis|Dissertation|"
    r"Research Paper|Capstone Project)\s+",
)

# Patterns marking a paragraph as byline / cover blurb / TOC
_BYLINE_DETECT_RE = re.compile(
    r"^[A-Z][A-Z .,\-&'/]{8,}\d.*,",
)
_COVER_BLURB_KEYWORDS = (
    "feedback", "qr code", "scan the", "customer feedback form",
    "third edition", "corrected version",
)
_TOC_LINE_HINTS_RE = re.compile(r"\.{3,}\s*\d+|^\s*page\s+\d+", re.IGNORECASE)

# Markdown inline link: [text](url) → text
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")

# Abstract / Summary heading detection (H2 or H3, case-insensitive)
_ABSTRACT_HEADING_RE = re.compile(
    r"^#{2,3}\s+(?:Abstract|ABSTRACT|Summary|SUMMARY)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Sentence terminator for truncation (period/question/exclamation followed
# by whitespace or end-of-string)
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


class OrgFilterResult(NamedTuple):
    organization: str | None
    produced_by: str | None


def filter_organization(creator_value: str | None) -> OrgFilterResult:
    """Distinguish real organization names from PDF Creator software junk.

    - When `creator_value` matches a known software pattern, returns
      OrgFilterResult(None, creator_value).
    - Otherwise returns OrgFilterResult(creator_value, None).
    - Empty/None input returns OrgFilterResult(None, None).
    """
    if creator_value is None:
        return OrgFilterResult(None, None)
    stripped = creator_value.strip()
    if not stripped:
        return OrgFilterResult(None, None)
    if _SOFTWARE_CREATORS_RE.match(stripped):
        return OrgFilterResult(None, creator_value)
    return OrgFilterResult(creator_value, None)


def refine_title(
    candidate: str,
    body: str,
    *,
    source_url: str | None = None,
    profile: Profile = "aggressive",
) -> str:
    """Replace candidate when it looks like cover-page boilerplate.

    Behaviors:
      - If candidate (case-insensitive, stripped) matches a known
        cover-page-boilerplate H1 ("INTERNATIONAL STANDARD",
        "TECHNICAL REPORT", "WHITE PAPER", etc.), prefer the first H2
        in the body as the title.
      - For source_url ending in *.wikipedia.org, strip a leading
        "Wikipedia:" or "WP:" namespace prefix.
      - DOCX line-broken H1 (aggressive only): when candidate contains
        an explicit delimiter (" - ", colon-and-space at < 30% mark)
        AND the segment before the delimiter looks like a course code or
        document type prefix (e.g., "COMP 4441 Final Project"), drop the
        prefix.

    Conservative profile: only the cover-page-boilerplate skip and the
    Wikipedia namespace strip. DOCX line-break refinement stays off.
    """
    if not candidate:
        return candidate

    refined = candidate.strip()

    # Cover-page boilerplate skip (both profiles)
    if refined.lower() in _COVER_PAGE_H1_VALUES:
        m = _H2_LINE_RE.search(body)
        if m:
            return m.group(1).strip()

    # Wikipedia namespace prefix strip (aggressive only)
    if profile != "conservative" and source_url:
        try:
            from urllib.parse import urlparse
            host = (urlparse(source_url).hostname or "").lower()
        except Exception:  # noqa: BLE001
            host = ""
        if host.endswith("wikipedia.org"):
            for prefix in ("Wikipedia:", "WP:"):
                if refined.startswith(prefix):
                    refined = refined[len(prefix):].strip()
                    break

    # DOCX line-break course-code / document-type prefix split
    # (aggressive only). Best-effort: only fires when an explicit
    # "Final Project" / "Final Paper" / etc. marker is present.
    if profile != "conservative":
        m = _DOCX_PREFIX_RE.match(refined)
        if m and len(refined) > m.end():
            tail = refined[m.end():].strip()
            if tail:
                refined = tail

        # Also handle " - " explicit delimiter when prefix looks like
        # a document-type marker.
        if " - " in refined:
            head, _, tail = refined.partition(" - ")
            if _DOCX_PREFIX_RE.match(head + " ") and tail.strip():
                refined = tail.strip()

    return refined


def _is_skip_paragraph(para: str) -> bool:
    """Return True if a paragraph matches a byline / cover blurb / TOC pattern."""
    stripped = para.strip()
    if not stripped:
        return True
    # Byline: caps-heavy, has digit (affiliation), comma-separated.
    if _BYLINE_DETECT_RE.match(stripped):
        return True
    # Cover-page blurb keywords (case-insensitive).
    lowered = stripped.lower()
    for kw in _COVER_BLURB_KEYWORDS:
        if kw in lowered:
            return True
    # TOC line hints.
    if _TOC_LINE_HINTS_RE.search(stripped):
        return True
    return False


def _cleanup_abstract(text: str) -> str:
    """Apply post-selection cleanup: strip links, decode entities, truncate."""
    # Strip markdown links: [text](url) → text
    text = _MD_LINK_RE.sub(r"\1", text)
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse whitespace runs
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to <= 400 chars at last sentence boundary
    if len(text) > 400:
        head = text[:400]
        # Find last sentence terminator inside the head
        matches = list(_SENTENCE_END_RE.finditer(head))
        if matches:
            cut = matches[-1].end()
            text = head[:cut].rstrip()
        else:
            # No sentence boundary — hard truncate
            text = head.rstrip()
    return text


def _split_body_paragraphs(body: str) -> list[str]:
    """Split body into paragraphs (blank-line separated, headings excluded)."""
    paras: list[str] = []
    for chunk in re.split(r"\n\s*\n", body):
        line = chunk.strip()
        if not line:
            continue
        # Skip heading lines
        if line.startswith("#"):
            continue
        paras.append(line)
    return paras


def refine_abstract(
    candidate: str | None,
    body: str,
    *,
    profile: Profile = "aggressive",
) -> str | None:
    """Replace candidate when it looks like a byline / cover blurb / TOC.

    Selection (in order):
      1. Body section under "## Abstract" / "## ABSTRACT" / "## Summary"
         (case-insensitive H2/H3) — take its first paragraph >= 80 chars.
      2. First non-skip paragraph >= 80 chars after H1 (current
         heuristic with skip-list applied).
      3. None.

    Skip patterns (move to the next paragraph if these match):
      - Author byline: starts with caps-heavy text, >= 3 commas, >= 1
        digit (affiliation marker).
      - Cover-page blurb: contains any of "feedback", "qr code",
        "scan the", "customer feedback form" (case-insensitive).
      - TOC line: contains "....\\d+" or "page \\d+" / "Page \\d+".

    Post-selection cleanup (always applied):
      - Strip inline markdown link syntax: [text](url) → text.
      - Decode HTML entities (html.unescape).
      - Truncate to <= 400 chars at last sentence boundary.

    Conservative profile: skip-list still active, but if no qualifying
    paragraph found returns None instead of falling through to a
    skipped paragraph. (Default aggressive returns the first non-skip
    even if it's a fallback.)
    """
    # Step 1: prefer "## Abstract" / "## Summary" body section.
    m = _ABSTRACT_HEADING_RE.search(body)
    if m:
        rest = body[m.end():]
        # Take first non-empty paragraph until next heading or blank-line gap.
        for para in _split_body_paragraphs(rest):
            if len(para) >= 80 and not _is_skip_paragraph(para):
                return _cleanup_abstract(para)

    # Step 2: candidate. Apply skip-list; if candidate is clean, use it.
    if candidate and not _is_skip_paragraph(candidate):
        return _cleanup_abstract(candidate)

    # Candidate skipped or missing. Walk body paragraphs.
    for para in _split_body_paragraphs(body):
        # Skip the candidate itself if it appears verbatim in body.
        if candidate and para.strip() == candidate.strip():
            continue
        if _is_skip_paragraph(para):
            continue
        if len(para) < 80:
            continue
        return _cleanup_abstract(para)

    # Nothing acceptable.
    if profile == "conservative":
        return None
    # Aggressive fallback: if candidate exists but was skipped, return it
    # with cleanup applied (best-effort). Otherwise None.
    if candidate:
        return _cleanup_abstract(candidate)
    return None
