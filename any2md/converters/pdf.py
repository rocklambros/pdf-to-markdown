"""PDF to Markdown converter (v1.0). Phase 1: pymupdf4llm only."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pymupdf
import pymupdf4llm

from any2md import pipeline
from any2md.frontmatter import SourceMeta, compose
from any2md.pipeline import PipelineOptions
from any2md.utils import sanitize_filename


def _parse_pdf_authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for sep in (";", ",", "&", "/"):
        if sep in raw:
            parts = [p.strip() for p in raw.split(sep) if p.strip()]
            break
    return parts or [raw.strip()]


def _parse_pdf_date(raw: str | None) -> str | None:
    """Convert 'D:20250315120000Z' -> '2025-03-15'."""
    if not raw:
        return None
    s = raw.lstrip("D:").strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


def _parse_pdf_metadata(doc: "pymupdf.Document") -> dict[str, object]:
    meta = doc.metadata or {}
    return {
        "title_hint": (meta.get("title") or "").strip() or None,
        "authors": _parse_pdf_authors(meta.get("author")),
        "organization": (meta.get("creator") or "").strip() or None,
        "date": _parse_pdf_date(meta.get("creationDate")),
        "keywords": [
            k.strip() for k in (meta.get("keywords") or "").split(",") if k.strip()
        ],
    }


def convert_pdf(
    pdf_path: Path,
    output_dir: Path,
    options: PipelineOptions | None = None,
    force: bool = False,
    strip_links_flag: bool = False,
) -> bool:
    if options is None:
        options = PipelineOptions(strip_links=strip_links_flag)

    out_name = sanitize_filename(pdf_path.name)
    out_path = output_dir / out_name
    if out_path.exists() and not force:
        print(f"  SKIP (exists): {out_name}")
        return True

    try:
        with pymupdf.open(str(pdf_path)) as doc:
            page_count = len(doc)
            md_text = pymupdf4llm.to_markdown(
                doc,
                write_images=False,
                show_progress=False,
                force_text=True,
            )
            props = _parse_pdf_metadata(doc)

        md_text, warnings = pipeline.run(md_text, "text", options)

        meta = SourceMeta(
            title_hint=props["title_hint"],
            authors=props["authors"],
            organization=props["organization"],
            date=(
                props["date"]
                or date.fromtimestamp(pdf_path.stat().st_mtime).isoformat()
            ),
            keywords=props["keywords"],
            pages=page_count,
            word_count=None,
            source_file=pdf_path.name,
            source_url=None,
            doc_type="pdf",
            extracted_via="pymupdf4llm",
            lane="text",
        )
        full = compose(md_text, meta, options)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(full, encoding="utf-8", newline="\n")
        suffix = f", {len(warnings)} warning(s)" if warnings else ""
        print(f"  OK: {out_name} ({page_count} pages{suffix})")
        return True

    except (OSError, ValueError, RuntimeError) as e:
        print(f"  FAIL: {pdf_path.name} -- {e}", file=sys.stderr)
        return False
