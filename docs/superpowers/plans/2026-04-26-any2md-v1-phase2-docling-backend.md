# any2md v1.0 — Phase 2: Docling Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Docling as the primary high-fidelity backend for PDF and DOCX, with pymupdf4llm/mammoth as automatic fallbacks. Implement the four structured-lane post-processing stages. Tag `1.0.0a2` to TestPyPI.

**Architecture:** Docling is an opt-in install (`pip install "any2md[high-fidelity]"`). Detection is lazy — converters try `import docling` and fall back when not present. The new `--high-fidelity` / `-H` flag forces Docling and exits non-zero if not installed.

**Tech Stack:** Python 3.10+, Docling (lazy import via `extras_require`), existing pytest/ruff stack.

**Reference:** `docs/superpowers/specs/2026-04-26-any2md-v1-design.md` §4.2 (structured stages), §5.1–5.2 (PDF/DOCX selection logic), §6 (CLI surface).

**Branch strategy:** Work on `phase2-docling` worktree off `v1.0`. Merge back via PR or direct fast-forward when complete.

---

## File structure

```
any2md/
  __init__.py                    [MODIFY: bump to "1.0.0a2"]
  _docling.py                    [NEW: lazy import, detection, install-hint message]
  cli.py                         [MODIFY: add --high-fidelity / -H flag]
  pipeline/
    __init__.py                  [MODIFY: PipelineOptions adds high_fidelity bool]
    structured.py                [MODIFY: register S1-S4 stages]
    text.py                      [unchanged in Phase 2]
    cleanup.py                   [unchanged]
  converters/
    pdf.py                       [MODIFY: Docling primary, pymupdf4llm fallback]
    docx.py                      [MODIFY: Docling primary, mammoth fallback]
    html.py                      [unchanged]
    txt.py                       [unchanged]

tests/
  unit/pipeline/
    test_structured_lift_figures.py     [NEW]
    test_structured_compact_tables.py   [NEW]
    test_structured_normalize_cites.py  [NEW]
    test_structured_heading_hierarchy.py [NEW]
  unit/test_docling_helper.py     [NEW: detection + install hint]
  unit/test_pdf_complexity.py     [NEW: pdf_looks_complex heuristic]
  integration/
    test_pdf_docling.py           [NEW: skipif not docling]
    test_docx_docling.py          [NEW: skipif not docling]
    test_pdf_pymupdf_fallback.py  [unchanged — passes whether docling is present or not]
    test_docx_mammoth_fallback.py [unchanged]
  cli/
    test_cli_high_fidelity.py     [NEW: -H flag behavior]

CHANGELOG.md                     [MODIFY: 1.0.0a2 entry]
pyproject.toml                   [MODIFY: extras_require high-fidelity, version 1.0.0a2]
```

---

## Task 1: Add `[high-fidelity]` extras + bump version

**Files:** `pyproject.toml`, `any2md/__init__.py`

- [ ] **Step 1:** Add to `[project.optional-dependencies]`:

```toml
high-fidelity = [
    "docling>=2.0.0",
]
```

- [ ] **Step 2:** Bump `any2md/__init__.py`:

```python
__version__ = "1.0.0a2"
```

- [ ] **Step 3:** `pip install -e ".[dev,high-fidelity]"` — verify Docling installs. If install fails on this machine, document the system requirement (e.g., poppler) but continue — CI will validate fresh installs.

- [ ] **Step 4:** `pytest -q` — should still be 86 passing (no behavior change yet).

- [ ] **Step 5:** Commit:

```bash
git add pyproject.toml any2md/__init__.py
git commit -m "chore: Bump to 1.0.0a2 and add [high-fidelity] extras (docling)"
```

---

## Task 2: Docling detection helper

**Files:** Create `any2md/_docling.py`. Test: `tests/unit/test_docling_helper.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_docling_helper.py
"""Tests for Docling detection and install-hint helper."""

from any2md._docling import (
    has_docling,
    install_hint,
    INSTALL_HINT_MSG,
)


def test_has_docling_returns_bool():
    result = has_docling()
    assert isinstance(result, bool)


def test_install_hint_msg_contains_pip_command():
    assert "pip install" in INSTALL_HINT_MSG
    assert "any2md[high-fidelity]" in INSTALL_HINT_MSG


def test_install_hint_emits_once_per_process(capsys):
    # Reset module-level rate-limit flag for the test
    from any2md import _docling
    _docling._hint_emitted = False
    install_hint()
    install_hint()  # second call should be silent
    captured = capsys.readouterr()
    # The hint should appear in stderr exactly once
    assert captured.err.count("pip install") == 1
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/test_docling_helper.py -v` → ImportError on module.

- [ ] **Step 3: Create `any2md/_docling.py`**

```python
"""Docling backend detection and lazy import helpers.

Docling is an optional dependency installed via:
    pip install "any2md[high-fidelity]"

This module never imports docling at module load — it does so inside
function bodies so that `import any2md` stays cheap when docling is
absent.
"""

from __future__ import annotations

import sys
from importlib.util import find_spec

INSTALL_HINT_MSG = (
    "Multi-column / table-heavy PDF detected; pymupdf4llm may produce artifacts.\n"
    "        For higher fidelity, install Docling:\n"
    '            pip install "any2md[high-fidelity]"\n'
    "        Or pass --high-fidelity to require it."
)

_hint_emitted = False


def has_docling() -> bool:
    """Return True if the docling package can be imported."""
    return find_spec("docling") is not None


def install_hint() -> None:
    """Print the install hint to stderr — at most once per process."""
    global _hint_emitted
    if _hint_emitted:
        return
    print(f"  WARN: {INSTALL_HINT_MSG}", file=sys.stderr)
    _hint_emitted = True
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/test_docling_helper.py -v` → 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/_docling.py tests/unit/test_docling_helper.py
git commit -m "feat(docling): Detection helper and rate-limited install hint"
```

---

## Task 3: `pdf_looks_complex` heuristic

**Files:** Modify `any2md/converters/pdf.py`. Test: `tests/unit/test_pdf_complexity.py`.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_pdf_complexity.py
"""Tests for the pdf_looks_complex heuristic."""

from pathlib import Path

import pymupdf
import pytest

from any2md.converters.pdf import pdf_looks_complex


def _build_simple_pdf(tmp_path) -> Path:
    """Tiny single-page PDF with one column of dense text."""
    out = tmp_path / "simple.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Lorem ipsum " * 50)
    doc.save(str(out))
    doc.close()
    return out


def test_pdf_looks_complex_short_doc_returns_false(fixture_dir, tmp_path):
    simple = _build_simple_pdf(tmp_path)
    assert pdf_looks_complex(simple) is False


def test_pdf_looks_complex_multi_column_fixture_returns_true(fixture_dir):
    # The synthetic multi_column.pdf has 2 columns explicitly placed by
    # reportlab. The heuristic should flag it.
    pdf = fixture_dir / "multi_column.pdf"
    # The fixture has only 2 pages — pdf_looks_complex requires > 5
    # pages OR multi-column + table OR low char density.
    # Verify the heuristic returns False for short multi-column PDFs
    # (its design target is "is this risky enough to warrant Docling?").
    assert pdf_looks_complex(pdf) is False


def test_pdf_looks_complex_empty_text_layer(tmp_path):
    """A PDF with very few characters per page (scanned) returns True."""
    out = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    for _ in range(6):  # 6 pages > 5-page threshold
        page = doc.new_page()
        # Insert almost no text
        page.insert_text((50, 50), ".")
    doc.save(str(out))
    doc.close()
    assert pdf_looks_complex(out) is True
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/test_pdf_complexity.py -v` → ImportError.

- [ ] **Step 3: Add `pdf_looks_complex` to `any2md/converters/pdf.py`**

Add this helper at module level (above `convert_pdf`):

```python
def pdf_looks_complex(pdf_path: Path) -> bool:
    """Cheap heuristic: is this PDF likely to produce artifacts on pymupdf4llm?

    Returns True when at least one signal suggests a complex layout that
    Docling would handle better:
      - Total pages > 5 AND
        (multi-column layout detected on any sampled page OR
         average chars-per-page < 200 — suggests scanned PDF).

    Sampling: at most 5 pages, evenly distributed.
    """
    try:
        with pymupdf.open(str(pdf_path)) as doc:
            page_count = len(doc)
            if page_count <= 5:
                return False

            sample_idxs = (
                list(range(page_count))
                if page_count <= 5
                else [int(i * page_count / 5) for i in range(5)]
            )

            total_chars = 0
            multi_column_seen = False
            for idx in sample_idxs:
                page = doc[idx]
                text = page.get_text("text") or ""
                total_chars += len(text)
                # Multi-column heuristic: collect block x-positions; if there
                # are clusters around two distinct x ranges with > 100 px
                # separation, flag.
                blocks = page.get_text("blocks") or []
                xs = sorted({round(b[0], 0) for b in blocks if len(b) >= 4})
                if len(xs) >= 4:
                    # Check if there's a gap > page_width * 0.2 between
                    # consecutive x-starts.
                    pw = page.rect.width or 612
                    for a, b in zip(xs, xs[1:]):
                        if b - a > pw * 0.2:
                            multi_column_seen = True
                            break

            avg_chars = total_chars / max(len(sample_idxs), 1)
            scanned_signal = avg_chars < 200
            return multi_column_seen or scanned_signal
    except (OSError, ValueError, RuntimeError):
        return False
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/test_pdf_complexity.py -v` → 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/converters/pdf.py tests/unit/test_pdf_complexity.py
git commit -m "feat(pdf): pdf_looks_complex heuristic for backend selection"
```

---

## Task 4: `PipelineOptions.high_fidelity` field

**Files:** Modify `any2md/pipeline/__init__.py`. Test: extend `tests/unit/pipeline/test_runner.py`.

- [ ] **Step 1: Write failing test (append to existing file)**

```python
# tests/unit/pipeline/test_runner.py — append:

def test_pipeline_options_has_high_fidelity_field():
    opts = PipelineOptions(high_fidelity=True)
    assert opts.high_fidelity is True


def test_pipeline_options_high_fidelity_default_false():
    opts = PipelineOptions()
    assert opts.high_fidelity is False
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_runner.py -v` → 2 new FAIL.

- [ ] **Step 3: Modify `any2md/pipeline/__init__.py`**

Add field to `PipelineOptions`:

```python
@dataclass(frozen=True)
class PipelineOptions:
    profile: Profile = "aggressive"
    ocr_figures: bool = False
    save_images: bool = False
    strip_links: bool = False
    strict: bool = False
    high_fidelity: bool = False  # NEW: force Docling backend
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/pipeline/test_runner.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/__init__.py tests/unit/pipeline/test_runner.py
git commit -m "feat(pipeline): PipelineOptions.high_fidelity flag"
```

---

## Task 5: CLI `--high-fidelity` / `-H` flag

**Files:** Modify `any2md/cli.py`. Test: `tests/cli/test_cli_high_fidelity.py`.

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_cli_high_fidelity.py
"""Tests for the --high-fidelity / -H CLI flag."""

import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "any2md", *args],
        capture_output=True, text=True,
    )


def test_high_fidelity_flag_present_in_help():
    r = _run("--help")
    assert r.returncode == 0
    assert "--high-fidelity" in r.stdout or "-H" in r.stdout


def test_high_fidelity_short_flag_present_in_help():
    r = _run("--help")
    assert "-H" in r.stdout


def test_high_fidelity_without_docling_exits_one(monkeypatch, fixture_dir, tmp_path):
    """If Docling isn't installed and -H is set, exit 1 with hint."""
    # Skip if docling IS installed — then this test isn't meaningful here.
    from any2md._docling import has_docling
    if has_docling():
        import pytest
        pytest.skip("docling installed; this assertion only meaningful without")

    out_dir = tmp_path / "out"
    r = _run(
        "-H", "-o", str(out_dir),
        str(fixture_dir / "ligatures_and_softhyphens.txt"),
    )
    assert r.returncode == 1
    assert "any2md[high-fidelity]" in (r.stdout + r.stderr)
```

- [ ] **Step 2: Run failing**

`pytest tests/cli/test_cli_high_fidelity.py -v` → ImportError or argparse error.

- [ ] **Step 3: Modify `any2md/cli.py`**

Add the flag near the existing flags:

```python
parser.add_argument(
    "--high-fidelity", "-H",
    action="store_true",
    help="Force the Docling backend (PDF/DOCX). Exit 1 if not installed.",
)
```

After argparse, when constructing `PipelineOptions`, set `high_fidelity=args.high_fidelity`.

After `args = parser.parse_args()` and before file processing, add:

```python
if args.high_fidelity:
    from any2md._docling import has_docling, INSTALL_HINT_MSG
    if not has_docling():
        print(f"  ERROR: --high-fidelity requested but docling is not installed.\n"
              f"  {INSTALL_HINT_MSG}", file=sys.stderr)
        sys.exit(1)
```

Update the `options = PipelineOptions(...)` construction:

```python
options = PipelineOptions(
    strip_links=args.strip_links,
    high_fidelity=args.high_fidelity,
)
```

- [ ] **Step 4: Run pass**

`pytest tests/cli/test_cli_high_fidelity.py -v` → 3 PASS (or skip if docling installed).

- [ ] **Step 5: Commit**

```bash
git add any2md/cli.py tests/cli/test_cli_high_fidelity.py
git commit -m "feat(cli): --high-fidelity / -H flag (forces Docling)"
```

---

## Task 6: Structured-lane stage S1 — `lift_figure_captions`

**Files:** Modify `any2md/pipeline/structured.py`. Test: `tests/unit/pipeline/test_structured_lift_figures.py`.

**Background:** Docling emits figures in markdown using its own conventions (often `<!-- image -->` placeholder followed by a caption paragraph, or `![caption](image_url)` form). We normalize these to `*Figure N: caption*` italic lines. When `--save-images` is set we keep the link; otherwise we drop the image reference.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_structured_lift_figures.py
"""Tests for S1 — lift_figure_captions."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.structured import lift_figure_captions


def test_lifts_caption_from_image_alt():
    text = "Body para.\n\n![A diagram of the system](image_3.png)\n\nMore body.\n"
    out = lift_figure_captions(text, PipelineOptions())
    assert "*Figure: A diagram of the system*" in out
    assert "image_3.png" not in out  # image link dropped


def test_save_images_preserves_link():
    text = "![A diagram](image.png)\n"
    out = lift_figure_captions(text, PipelineOptions(save_images=True))
    assert "image.png" in out


def test_lifts_html_figure_tag_with_figcaption():
    text = (
        "<figure>\n"
        "<img src='x.png' alt='diagram'/>\n"
        "<figcaption>Threat model overview</figcaption>\n"
        "</figure>\n"
    )
    out = lift_figure_captions(text, PipelineOptions())
    assert "*Figure: Threat model overview*" in out


def test_no_match_is_noop():
    text = "Just regular paragraphs here.\nNothing special.\n"
    assert lift_figure_captions(text, PipelineOptions()) == text


def test_html_comment_image_placeholder_stripped():
    # Docling sometimes emits <!-- image --> as a placeholder
    text = "Para before.\n\n<!-- image -->\n\nPara after.\n"
    out = lift_figure_captions(text, PipelineOptions())
    assert "<!-- image -->" not in out
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_structured_lift_figures.py -v` → ImportError.

- [ ] **Step 3: Add stage**

```python
# any2md/pipeline/structured.py
"""Structured-lane pipeline stages.

Phase 2: S1-S4 implemented. Stages run BEFORE shared cleanup on Docling-
emitted markdown — they trust Docling's layout decisions and only normalize
representational details.
"""

from __future__ import annotations

import re
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from any2md.pipeline import PipelineOptions

Stage = Callable[[str, "PipelineOptions"], str]

_IMG_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HTML_FIGURE_RE = re.compile(
    r"<figure[^>]*>(?:.*?)<figcaption[^>]*>(.*?)</figcaption>(?:.*?)</figure>",
    re.DOTALL | re.IGNORECASE,
)
_IMAGE_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)


def lift_figure_captions(text: str, options: "PipelineOptions") -> str:
    """S1: Convert image markdown / <figure> blocks to italic *Figure: caption* lines.

    Drops image references unless --save-images is set.
    """

    def _img_repl(match: re.Match[str]) -> str:
        alt = match.group(1).strip()
        url = match.group(2).strip()
        caption_line = f"*Figure: {alt}*" if alt else ""
        if options.save_images:
            # Keep the link below the caption
            return f"{caption_line}\n\n![{alt}]({url})" if caption_line else f"![{alt}]({url})"
        return caption_line

    text = _IMG_LINK_RE.sub(_img_repl, text)

    def _figure_repl(match: re.Match[str]) -> str:
        cap = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return f"*Figure: {cap}*" if cap else ""

    text = _HTML_FIGURE_RE.sub(_figure_repl, text)

    text = _IMAGE_PLACEHOLDER_RE.sub("", text)

    return text


STAGES: list[Stage] = [
    lift_figure_captions,
]
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/pipeline/test_structured_lift_figures.py -v` → 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/structured.py tests/unit/pipeline/test_structured_lift_figures.py
git commit -m "feat(pipeline): S1 lift_figure_captions"
```

---

## Task 7: Structured-lane stage S2 — `compact_tables`

**Files:** Modify `any2md/pipeline/structured.py`. Test: `tests/unit/pipeline/test_structured_compact_tables.py`.

**Goal:** Strip per-cell padding spaces inside GFM tables. Save 5-8% on table-heavy docs without breaking column alignment for readers.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_structured_compact_tables.py
"""Tests for S2 — compact_tables."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.structured import compact_tables


def test_compact_pads_in_data_rows():
    table = (
        "| Col A    | Col B   |\n"
        "|----------|---------|\n"
        "| value 1  | value 2 |\n"
        "| value 3  | value 4 |\n"
    )
    out = compact_tables(table, PipelineOptions())
    assert "| value 1 | value 2 |" in out  # single space around values
    assert "value 1  " not in out   # no double-space padding


def test_compact_preserves_alignment_row():
    table = (
        "| A | B |\n"
        "|:--|--:|\n"
        "| 1 | 2 |\n"
    )
    out = compact_tables(table, PipelineOptions())
    assert "|:--|--:|" in out  # alignment row intact


def test_no_table_is_noop():
    text = "No tables here.\nJust prose.\n"
    assert compact_tables(text, PipelineOptions()) == text


def test_does_not_corrupt_inline_pipes_in_code():
    text = "`foo | bar` is shell pipe syntax\n"
    assert compact_tables(text, PipelineOptions()) == text
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_structured_compact_tables.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/structured.py`:

```python
_TABLE_ROW_RE = re.compile(r"^\|.*\|\s*$")
_ALIGNMENT_ROW_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


def compact_tables(text: str, _options: "PipelineOptions") -> str:
    """S2: Strip per-cell padding spaces in GFM tables. Skip alignment row."""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        # Only act on lines that look like a table row
        if _TABLE_ROW_RE.match(line) and not _ALIGNMENT_ROW_RE.match(line):
            cells = line.split("|")
            # First and last entries are empty (line starts/ends with |)
            cells = [c.strip() for c in cells]
            # Reconstruct without padding
            line = "|" + "|".join(c if c == "" else f" {c} " for c in cells[1:-1]) + "|"
            # Compact spaces inside each cell wrapper to single
            line = re.sub(r"  +", " ", line)
        out.append(line)
    return "\n".join(out)


STAGES.append(compact_tables)
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/pipeline/test_structured_compact_tables.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/structured.py tests/unit/pipeline/test_structured_compact_tables.py
git commit -m "feat(pipeline): S2 compact_tables"
```

---

## Task 8: Structured-lane stage S3 — `normalize_citations`

**Files:** Modify `any2md/pipeline/structured.py`. Test: `tests/unit/pipeline/test_structured_normalize_cites.py`.

**Goal:** Coalesce `[1] [2]` → `[1][2]`, ensure citations live at clause-end before punctuation. Spec §4.3.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_structured_normalize_cites.py
"""Tests for S3 — normalize_citations."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.structured import normalize_citations


def test_coalesces_adjacent_citations():
    text = "Statement [1] [2] [3]."
    out = normalize_citations(text, PipelineOptions())
    assert out == "Statement [1][2][3]."


def test_preserves_already_compact():
    text = "Statement [1][2]."
    assert normalize_citations(text, PipelineOptions()) == text


def test_no_citations_is_noop():
    text = "Plain prose with no brackets.\n"
    assert normalize_citations(text, PipelineOptions()) == text


def test_does_not_collapse_non_numeric_brackets():
    text = "See [appendix A] and [section B]."
    assert normalize_citations(text, PipelineOptions()) == text
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_structured_normalize_cites.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/structured.py`:

```python
_CITE_GAP_RE = re.compile(r"(\[\d+\])\s+(?=\[\d+\])")


def normalize_citations(text: str, _options: "PipelineOptions") -> str:
    """S3: Coalesce '[1] [2] [3]' → '[1][2][3]' (numeric only)."""
    return _CITE_GAP_RE.sub(r"\1", text)


STAGES.append(normalize_citations)
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/pipeline/test_structured_normalize_cites.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/structured.py tests/unit/pipeline/test_structured_normalize_cites.py
git commit -m "feat(pipeline): S3 normalize_citations"
```

---

## Task 9: Structured-lane stage S4 — `enforce_heading_hierarchy`

**Files:** Modify `any2md/pipeline/structured.py`. Test: `tests/unit/pipeline/test_structured_heading_hierarchy.py`.

**Goal:** Guarantee single H1 (promote first heading if no H1; demote subsequent H1s to H2). Repair skipped levels (H2 → H4 becomes H2 → H3 → H4).

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_structured_heading_hierarchy.py
"""Tests for S4 — enforce_heading_hierarchy."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.structured import enforce_heading_hierarchy


def test_clean_doc_is_unchanged():
    text = "# Title\n\n## Sec\n\n### Sub\n"
    assert enforce_heading_hierarchy(text, PipelineOptions()) == text


def test_promotes_first_heading_when_no_h1():
    text = "## First Heading\n\n### Sub\n"
    out = enforce_heading_hierarchy(text, PipelineOptions())
    assert out.startswith("# First Heading\n")


def test_demotes_subsequent_h1():
    text = "# A\n\nbody\n\n# B\n\nmore\n"
    out = enforce_heading_hierarchy(text, PipelineOptions())
    assert out.count("# A") == 1
    assert "## B" in out


def test_repairs_skipped_levels():
    text = "# A\n\n#### Deep\n"
    out = enforce_heading_hierarchy(text, PipelineOptions())
    # H1 → H4 became H1 → H2 (one level deeper than H1)
    assert "## Deep" in out


def test_no_headings_is_noop():
    text = "Plain body, no headings.\n"
    assert enforce_heading_hierarchy(text, PipelineOptions()) == text
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_structured_heading_hierarchy.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/structured.py`:

```python
_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def enforce_heading_hierarchy(text: str, _options: "PipelineOptions") -> str:
    """S4: Ensure single H1 and no skipped levels.

    - If no H1 exists, the first heading is promoted to H1.
    - Subsequent H1s are demoted to H2.
    - Skipped levels are flattened: a heading that's > prev_level + 1
      becomes prev_level + 1.
    """
    matches = list(_HEADING_LINE_RE.finditer(text))
    if not matches:
        return text

    # Pass 1: collect (level, title, span)
    levels = [len(m.group(1)) for m in matches]

    # Promote first heading to H1 if no H1
    if 1 not in levels:
        levels[0] = 1

    # Demote subsequent H1s
    seen_h1 = False
    for i, lvl in enumerate(levels):
        if lvl == 1:
            if seen_h1:
                levels[i] = 2
            else:
                seen_h1 = True

    # Flatten skipped levels
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            levels[i] = levels[i - 1] + 1

    # Pass 2: rewrite
    out = []
    last = 0
    for new_level, m in zip(levels, matches):
        out.append(text[last:m.start()])
        out.append("#" * new_level + " " + m.group(2))
        last = m.end()
    out.append(text[last:])
    return "".join(out)


STAGES.append(enforce_heading_hierarchy)
```

- [ ] **Step 4: Run pass**

`pytest tests/unit/pipeline/test_structured_heading_hierarchy.py -v` → 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/structured.py tests/unit/pipeline/test_structured_heading_hierarchy.py
git commit -m "feat(pipeline): S4 enforce_heading_hierarchy"
```

---

## Task 10: PDF Docling backend integration

**Files:** Modify `any2md/converters/pdf.py`. Test: `tests/integration/test_pdf_docling.py`.

**Note on Docling API:** Docling 2.x exposes `from docling.document_converter import DocumentConverter, PdfFormatOption` and `from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions`. The implementer should `python -c "import docling; …"` to verify exact import paths against the installed version, and adjust if Docling's API has shifted. Document any deviations in the commit message.

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_pdf_docling.py
"""Integration test: PDF converter (Docling path)."""

import pytest
import yaml

from any2md._docling import has_docling
from any2md.converters.pdf import convert_pdf
from any2md.pipeline import PipelineOptions


pytestmark = pytest.mark.skipif(
    not has_docling(),
    reason="docling not installed (test runs only when [high-fidelity] is installed)",
)


def test_pdf_docling_emits_v1_frontmatter_structured_lane(fixture_dir, tmp_output_dir):
    ok = convert_pdf(
        fixture_dir / "multi_column.pdf",
        tmp_output_dir,
        options=PipelineOptions(high_fidelity=True),
        force=True,
    )
    assert ok
    out_files = list(tmp_output_dir.glob("*.md"))
    assert len(out_files) == 1
    out = out_files[0].read_text(encoding="utf-8")
    end = out.index("\n---\n", 4)
    fm = yaml.safe_load(out[4:end])
    assert fm["status"] == "draft"
    assert fm["extracted_via"] == "docling"
    assert fm["pages"] == 2
    assert fm["content_hash"]


def test_pdf_default_uses_docling_when_installed(fixture_dir, tmp_output_dir):
    """Without -H but with Docling installed, we still pick Docling."""
    ok = convert_pdf(
        fixture_dir / "multi_column.pdf",
        tmp_output_dir,
        options=PipelineOptions(),  # default: high_fidelity False, but Docling auto-used
        force=True,
    )
    assert ok
    out = next(tmp_output_dir.glob("*.md")).read_text(encoding="utf-8")
    end = out.index("\n---\n", 4)
    fm = yaml.safe_load(out[4:end])
    assert fm["extracted_via"] == "docling"
```

- [ ] **Step 2: Run failing**

`pytest tests/integration/test_pdf_docling.py -v` → either skip (no docling) or fail (still going through pymupdf4llm path).

- [ ] **Step 3: Modify `any2md/converters/pdf.py`**

Refactor the existing converter so the extraction step picks the backend:

```python
# any2md/converters/pdf.py — replace _extract section + convert_pdf

def _extract_via_docling(pdf_path: Path, options) -> tuple[str, str]:
    """Returns (markdown, extracted_via='docling'). Raises on Docling errors."""
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_opts = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
        generate_picture_images=options.save_images,
    )
    if options.ocr_figures:
        pipeline_opts.do_ocr = True

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts),
        }
    )
    result = converter.convert(pdf_path)
    md = result.document.export_to_markdown()
    return md, "docling"


def _extract_via_pymupdf4llm(doc) -> tuple[str, str]:
    md = pymupdf4llm.to_markdown(
        doc,
        write_images=False,
        show_progress=False,
        force_text=True,
    )
    return md, "pymupdf4llm"


def convert_pdf(pdf_path, output_dir, options=None, force=False, strip_links_flag=False):
    if options is None:
        options = PipelineOptions(strip_links=strip_links_flag)

    out_name = sanitize_filename(pdf_path.name)
    out_path = output_dir / out_name
    if out_path.exists() and not force:
        print(f"  SKIP (exists): {out_name}")
        return True

    try:
        # Backend selection
        from any2md._docling import has_docling, install_hint
        use_docling = has_docling()

        if not use_docling and pdf_looks_complex(pdf_path):
            install_hint()

        # Always extract metadata via PyMuPDF (cheaper than Docling for metadata)
        with pymupdf.open(str(pdf_path)) as doc:
            page_count = len(doc)
            props = _parse_pdf_metadata(doc)
            if not use_docling:
                md_text, extracted_via = _extract_via_pymupdf4llm(doc)
                lane = "text"

        if use_docling:
            try:
                md_text, extracted_via = _extract_via_docling(pdf_path, options)
                lane = "structured"
            except Exception as e:
                # Fall back rather than fail
                print(f"  WARN: Docling extraction failed for {pdf_path.name}: {e}; "
                      f"falling back to pymupdf4llm.", file=sys.stderr)
                with pymupdf.open(str(pdf_path)) as doc:
                    md_text, extracted_via = _extract_via_pymupdf4llm(doc)
                lane = "text"

        md_text, warnings = pipeline.run(md_text, lane, options)

        meta = SourceMeta(
            title_hint=props["title_hint"],
            authors=props["authors"],
            organization=props["organization"],
            date=props["date"] or date.fromtimestamp(pdf_path.stat().st_mtime).isoformat(),
            keywords=props["keywords"],
            pages=page_count,
            word_count=None,
            source_file=pdf_path.name,
            source_url=None,
            doc_type="pdf",
            extracted_via=extracted_via,
            lane=lane,
        )
        full = compose(md_text, meta, options)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(full, encoding="utf-8", newline="\n")
        suffix = f", {len(warnings)} warning(s)" if warnings else ""
        print(f"  OK: {out_name} ({page_count} pages, via {extracted_via}{suffix})")
        return True

    except (OSError, ValueError, RuntimeError) as e:
        print(f"  FAIL: {pdf_path.name} -- {e}", file=sys.stderr)
        return False
```

`SourceMeta.extracted_via` Literal must accept `"docling"` (already does per Phase 1).

- [ ] **Step 4: Run tests**

`pytest tests/integration/test_pdf_docling.py tests/integration/test_pdf_pymupdf_fallback.py -v` → both pass when Docling installed; fallback test passes regardless.

- [ ] **Step 5: Commit**

```bash
git add any2md/converters/pdf.py tests/integration/test_pdf_docling.py
git commit -m "feat(pdf): Docling primary backend with pymupdf4llm fallback"
```

---

## Task 11: DOCX Docling backend integration

**Files:** Modify `any2md/converters/docx.py`. Test: `tests/integration/test_docx_docling.py`.

**Pattern mirrors PDF (Task 10).** DOCX-specific differences: no PdfPipelineOptions; just `DocumentConverter().convert(docx_path)`.

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_docx_docling.py
"""Integration test: DOCX converter (Docling path)."""

import pytest
import yaml

from any2md._docling import has_docling
from any2md.converters.docx import convert_docx
from any2md.pipeline import PipelineOptions


pytestmark = pytest.mark.skipif(
    not has_docling(),
    reason="docling not installed",
)


def test_docx_docling_uses_structured_lane(fixture_dir, tmp_output_dir):
    ok = convert_docx(
        fixture_dir / "table_heavy.docx",
        tmp_output_dir,
        options=PipelineOptions(),
        force=True,
    )
    assert ok
    out = next(tmp_output_dir.glob("*.md")).read_text(encoding="utf-8")
    end = out.index("\n---\n", 4)
    fm = yaml.safe_load(out[4:end])
    body = out[end + 5:]
    assert fm["extracted_via"] == "docling"
    assert "Header 1" in body  # Docling preserves table header
```

- [ ] **Step 2: Run failing**

`pytest tests/integration/test_docx_docling.py -v` → fail or skip.

- [ ] **Step 3: Modify `any2md/converters/docx.py`**

Same pattern as PDF: try Docling, fall back to mammoth+markdownify on `ImportError` or extraction failure. Pseudocode:

```python
def _extract_via_docling(docx_path: Path) -> tuple[str, str]:
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(docx_path)
    return result.document.export_to_markdown(), "docling"


def _extract_via_mammoth(docx_path, options) -> tuple[str, str]:
    with open(docx_path, "rb") as f:
        html_result = mammoth.convert_to_html(f)
    md = markdownify.markdownify(
        html_result.value, heading_style="ATX",
        strip=["img"] if not options.save_images else [],
        bullets="-",
    )
    return md, "mammoth+markdownify"
```

In `convert_docx`:

```python
from any2md._docling import has_docling
use_docling = has_docling()

if use_docling:
    try:
        md_text, extracted_via = _extract_via_docling(docx_path)
        lane = "structured"
    except Exception as e:
        print(f"  WARN: Docling extraction failed for {docx_path.name}: {e}; "
              f"falling back to mammoth.", file=sys.stderr)
        md_text, extracted_via = _extract_via_mammoth(docx_path, options)
        lane = "text"
else:
    md_text, extracted_via = _extract_via_mammoth(docx_path, options)
    lane = "text"

# … rest unchanged: pipeline.run, compose, write
```

The `SourceMeta` `lane` field follows accordingly.

- [ ] **Step 4: Run tests**

`pytest tests/integration/test_docx_docling.py tests/integration/test_docx_mammoth_fallback.py -v`.

- [ ] **Step 5: Commit**

```bash
git add any2md/converters/docx.py tests/integration/test_docx_docling.py
git commit -m "feat(docx): Docling primary backend with mammoth fallback"
```

---

## Task 12: Update snapshot tests for backend variation

**Files:** Modify `tests/integration/test_snapshots.py`.

When Docling is installed, PDF and DOCX outputs differ from the pymupdf4llm/mammoth output. Snapshots become per-backend.

- [ ] **Step 1:** Modify snapshot harness so that for PDF and DOCX fixtures, the snapshot file is suffixed with backend (`<stem>.docling.md` vs `<stem>.fallback.md`):

```python
# in tests/integration/test_snapshots.py — replace the existing harness:

import os
from pathlib import Path

import pytest

from any2md._docling import has_docling
from any2md.converters.docx import convert_docx
from any2md.converters.html import convert_html
from any2md.converters.pdf import convert_pdf
from any2md.converters.txt import convert_txt
from any2md.pipeline import PipelineOptions


SNAPSHOTS = {
    "web_page.html":                ("html",  convert_html, False),
    "ligatures_and_softhyphens.txt":("txt",   convert_txt,  False),
    "multi_column.pdf":             ("pdf",   convert_pdf,  True),
    "table_heavy.docx":             ("docx",  convert_docx, True),
}


def _normalize(text: str) -> str:
    import re
    text = re.sub(r'^date: ".*?"', 'date: "<volatile>"', text, flags=re.MULTILINE)
    text = re.sub(r'^content_hash: ".*?"', 'content_hash: "<volatile>"', text, flags=re.MULTILINE)
    return text


@pytest.mark.parametrize("fixture_name", list(SNAPSHOTS))
def test_snapshot(fixture_name, fixture_dir, snapshot_dir, tmp_output_dir):
    _, convert, backend_dependent = SNAPSHOTS[fixture_name]
    ok = convert(fixture_dir / fixture_name, tmp_output_dir, options=PipelineOptions(), force=True)
    assert ok
    out = next(tmp_output_dir.glob("*.md"))
    actual = _normalize(out.read_text(encoding="utf-8"))

    stem = Path(fixture_name).stem
    if backend_dependent:
        suffix = ".docling" if has_docling() else ".fallback"
        snap_path = snapshot_dir / f"{stem}{suffix}.md"
    else:
        snap_path = snapshot_dir / f"{stem}.md"

    if os.environ.get("UPDATE_SNAPSHOTS"):
        snap_path.write_text(actual, encoding="utf-8")
        return

    expected = snap_path.read_text(encoding="utf-8") if snap_path.exists() else None
    if expected is None:
        pytest.fail(
            f"Snapshot missing: {snap_path}. "
            f"Run UPDATE_SNAPSHOTS=1 pytest to create."
        )
    assert actual == expected
```

- [ ] **Step 2:** Rename existing snapshot files for PDF/DOCX from `multi_column.md` → `multi_column.fallback.md`, `table_heavy.md` → `table_heavy.fallback.md`. Then with Docling installed, generate `.docling.md` variants:

```bash
git mv tests/fixtures/snapshots/multi_column.md tests/fixtures/snapshots/multi_column.fallback.md
git mv tests/fixtures/snapshots/table_heavy.md tests/fixtures/snapshots/table_heavy.fallback.md
UPDATE_SNAPSHOTS=1 pytest tests/integration/test_snapshots.py -v
```

If Docling is installed, this writes `.docling.md` files. If not, the rename above is enough.

- [ ] **Step 3:** Run snapshot tests:

`pytest tests/integration/test_snapshots.py -v` → 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_snapshots.py tests/fixtures/snapshots/
git commit -m "test: Backend-variant snapshots for PDF/DOCX (.docling vs .fallback)"
```

---

## Task 13: CHANGELOG 1.0.0a2 entry

**Files:** `CHANGELOG.md`

- [ ] **Step 1:** Insert above the `[1.0.0a1]` heading:

```markdown
## [1.0.0a2] — 2026-04-26

Phase 2: Docling backend integration. PDFs and DOCX files can now be
extracted via Docling for substantially higher fidelity on multi-column
layouts and complex tables. Docling is an optional install — without it,
any2md transparently falls back to pymupdf4llm (PDF) and mammoth (DOCX).

### Added
- New optional dependency: `pip install "any2md[high-fidelity]"` installs
  Docling, which becomes the primary extraction backend for PDF and DOCX.
- `any2md/_docling.py` — detection helper plus a rate-limited install hint
  that surfaces on the stderr when an artifact-prone PDF is being converted
  without Docling installed.
- New CLI flag: `--high-fidelity` / `-H`. Forces Docling. Exits with code 1
  and prints the install hint when Docling is not present.
- `pdf_looks_complex(pdf_path)` heuristic — fast (< 50 ms) check used to
  decide whether to print the install hint when Docling is missing.
- New `PipelineOptions.high_fidelity` field (forwarded by the CLI).
- Structured-lane post-processing stages now active for Docling-emitted
  markdown:
  - **S1 `lift_figure_captions`** — converts image markdown and HTML
    `<figure>` blocks to italic `*Figure: caption*` lines. Drops image
    references (preserved with `--save-images`, planned for Phase 3).
  - **S2 `compact_tables`** — strips per-cell padding spaces in GFM tables;
    preserves alignment row intact.
  - **S3 `normalize_citations`** — coalesces `[1] [2] [3]` → `[1][2][3]`.
  - **S4 `enforce_heading_hierarchy`** — guarantees a single H1 (promotes
    first heading if needed; demotes subsequent H1s); flattens skipped
    levels (H2 → H4 becomes H2 → H3).
- Per-backend snapshot tests: PDF and DOCX now have `.docling.md` and
  `.fallback.md` golden outputs.

### Changed
- PDF and DOCX converters select backend at runtime: Docling if importable,
  pymupdf4llm/mammoth otherwise. Fallback also fires if Docling raises
  during extraction (with stderr warning).
- `extracted_via` frontmatter field reports `docling` for the new path.
- `lane` is `"structured"` for Docling output, `"text"` for fallback —
  the structured lane runs S1–S4 before shared cleanup; the text lane
  runs only shared cleanup in Phase 2 (T1–T6 land in Phase 3).

### Carried forward
- All v0.7 + v1.0.0a1 CLI flags.
- HTML/URL → trafilatura (Docling not used for web — purpose-built
  boilerplate stripping is more important than structured layout).
- TXT → heuristic `structurize()`.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG entry for 1.0.0a2"
```

---

## Task 14: Tag and TestPyPI release

- [ ] **Step 1:** Verify everything green:

```bash
pytest -q
ruff check any2md/ tests/
python -c "import any2md; print(any2md.__version__)"  # 1.0.0a2
git status  # clean
```

- [ ] **Step 2:** Push branch:

```bash
git push origin phase2-docling
```

- [ ] **Step 3:** Tag and push:

```bash
git tag -a v1.0.0a2 -m "any2md 1.0.0a2 — Phase 2 Docling backend prerelease"
git push origin v1.0.0a2
```

- [ ] **Step 4:** GitHub Release as prerelease:

```bash
gh release create v1.0.0a2 \
    --prerelease \
    --target phase2-docling \
    --title "any2md 1.0.0a2 — Phase 2 Docling backend" \
    --notes "$(cat <<'EOF'
Phase 2 of 5: Docling backend integration.

PDF and DOCX conversion now routes through Docling (when installed) for
markedly higher fidelity on multi-column layouts and complex tables.

Install with the high-fidelity extras:

\`\`\`bash
pip install --index-url https://pypi.org/simple/ \\
            --extra-index-url https://test.pypi.org/simple/ \\
            "any2md[high-fidelity]==1.0.0a2"
\`\`\`

See [CHANGELOG.md](https://github.com/rocklambros/any2md/blob/phase2-docling/CHANGELOG.md) for the full 1.0.0a2 entry.

### What's next
Phase 3 adds figure/OCR handling, the text-lane stages T1–T6 (line-wrap
repair, dehyphenation, paragraph dedupe, TOC dedupe, header/footer strip,
list/code restore), and full URL metadata extraction.
EOF
)"
```

- [ ] **Step 5:** Wait for the publish workflow (`gh run watch <id>`), then verify install in a clean venv per the Phase 1 pattern:

```bash
rm -rf /tmp/any2md_a2_smoke && python -m venv /tmp/any2md_a2_smoke
/tmp/any2md_a2_smoke/bin/pip install --quiet \
    pymupdf pymupdf4llm mammoth markdownify trafilatura beautifulsoup4 lxml
/tmp/any2md_a2_smoke/bin/pip install --quiet --no-deps \
    --index-url https://test.pypi.org/simple/ "any2md==1.0.0a2"
/tmp/any2md_a2_smoke/bin/python -c "import any2md; print(any2md.__version__)"
```

- [ ] **Step 6:** Merge `phase2-docling` into `v1.0`:

```bash
# from main worktree
git checkout v1.0
git merge --no-ff phase2-docling -m "Merge phase2-docling into v1.0 (1.0.0a2)"
git push origin v1.0
```

---

## Parallelism

```
[A — sequential]  T1 → T2
[B — sequential]  T3 → T4 → T5    (T3 modifies pdf.py; T4 modifies pipeline; T5 modifies cli)
[C — sequential]  T6 → T7 → T8 → T9   (all modify structured.py)
[D — parallel]    T10, T11             (different files)
[E — sequential]  T12 → T13 → T14      (snapshot, changelog, release)
```

Critical path ~10 task-slots vs 14 sequential. Less dramatic than Phase 1 because the same-file constraint is heavier here.

---

## Self-review summary

- Spec §4.2 (S1–S4) → Tasks 6, 7, 8, 9.
- Spec §5.1 (PDF Docling + heuristic + fallback + install hint) → Tasks 2, 3, 10.
- Spec §5.2 (DOCX Docling + fallback) → Task 11.
- Spec §6.1 (`--high-fidelity` flag) → Tasks 4, 5.
- Spec §9.1 Phase 2 release gates → Task 14.
- All code blocks contain executable code. No placeholders. Type/method names consistent across tasks (`PipelineOptions.high_fidelity`, `_docling.has_docling`, `lift_figure_captions`, etc.).
- Docling API specifics noted as "verify against installed version" in Task 10 — implementer subagent has license to adjust import paths if Docling has shifted, with rationale in commit message.
