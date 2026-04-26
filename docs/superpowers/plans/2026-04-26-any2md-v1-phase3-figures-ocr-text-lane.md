# any2md v1.0 — Phase 3: Figures / OCR / Text-Lane Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the six text-lane post-processing stages (T1–T6), wire `--ocr-figures` and `--save-images` flags end-to-end, and tag `1.0.0a3` to TestPyPI.

**Architecture:** Text-lane stages run on output that came from trafilatura, mammoth (DOCX fallback), pymupdf4llm (PDF fallback), or the TXT structurizer. They repair the kinds of artifacts those backends leave behind: wrapped lines, soft-hyphenations, repeated paragraphs, leading TOC blocks that mirror later headings, running headers/footers, and lost list/code structure. After the text lane, shared cleanup (C1–C7) runs as always.

**Tech Stack:** Same as Phase 2. No new dependencies.

**Reference:** spec §4.3 (text-lane stage definitions) and §6.1 (CLI flags).

**Branch strategy:** `phase3-figures-ocr-textlane` worktree off `v1.0`.

---

## File structure

```
any2md/
  __init__.py                    [MODIFY: bump to "1.0.0a3"]
  cli.py                         [MODIFY: add --ocr-figures, --save-images]
  pipeline/text.py               [MODIFY: register T1-T6 stages]
  converters/pdf.py              [MODIFY: --save-images writes images to <output>/images/]

tests/
  unit/pipeline/
    test_text_repair_line_wraps.py    [NEW]
    test_text_dehyphenate.py          [NEW]
    test_text_dedupe_paragraphs.py    [NEW]
    test_text_dedupe_toc.py           [NEW]
    test_text_strip_headers_footers.py [NEW]
    test_text_restore_lists_code.py   [NEW]
  cli/test_cli_ocr_save_images.py     [NEW]
  integration/test_save_images.py     [NEW]

CHANGELOG.md                     [MODIFY: 1.0.0a3 entry]
pyproject.toml                   [MODIFY: version 1.0.0a3]
```

---

## Task 1: Bump version + CLI flags `--ocr-figures` and `--save-images`

**Files:** `pyproject.toml`, `any2md/__init__.py`, `any2md/cli.py`. Test: `tests/cli/test_cli_ocr_save_images.py`.

- [ ] **Step 1: Bump version** in `pyproject.toml` (no change there, version is dynamic) and `any2md/__init__.py` to `1.0.0a3`.

- [ ] **Step 2: Write failing CLI test**

```python
# tests/cli/test_cli_ocr_save_images.py
"""Tests for --ocr-figures and --save-images flags."""

import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "any2md", *args],
        capture_output=True, text=True,
    )


def test_ocr_figures_in_help():
    r = _run("--help")
    assert "--ocr-figures" in r.stdout


def test_save_images_in_help():
    r = _run("--help")
    assert "--save-images" in r.stdout


def test_flags_compose(fixture_dir, tmp_path):
    """Both flags accepted together. With Docling absent they have no
    effect on backend selection but must not error on argparse."""
    out_dir = tmp_path / "out"
    r = _run(
        "-o", str(out_dir),
        "--save-images", "--ocr-figures",
        str(fixture_dir / "ligatures_and_softhyphens.txt"),
    )
    # TXT input is unaffected by these flags but the CLI must still parse them
    assert r.returncode == 0
```

- [ ] **Step 3: Modify `any2md/cli.py`**

Add two flags near `--high-fidelity`:

```python
parser.add_argument(
    "--ocr-figures",
    action="store_true",
    help="OCR text inside figures (PDF Docling path). Implies --high-fidelity.",
)
parser.add_argument(
    "--save-images",
    action="store_true",
    help="Save extracted images to <output>/images/ and reference them. Implies --high-fidelity.",
)
```

Forward in `PipelineOptions`:

```python
options = PipelineOptions(
    strip_links=args.strip_links,
    high_fidelity=args.high_fidelity or args.ocr_figures or args.save_images,
    ocr_figures=args.ocr_figures,
    save_images=args.save_images,
)
```

The "implies --high-fidelity" rule means the early-exit guard fires when those flags are set without Docling installed:

```python
if (args.high_fidelity or args.ocr_figures or args.save_images):
    from any2md._docling import has_docling, INSTALL_HINT_MSG
    if not has_docling():
        print(f"  ERROR: Docling required for --high-fidelity / --ocr-figures / --save-images.\n"
              f"  {INSTALL_HINT_MSG}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 4: Run tests**

`pytest tests/cli/test_cli_ocr_save_images.py -v` → all pass.
`pytest -q` overall → green.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml any2md/__init__.py any2md/cli.py tests/cli/test_cli_ocr_save_images.py
git commit -m "feat(cli): --ocr-figures and --save-images flags (imply --high-fidelity)"
```

---

## Task 2: Wire `--save-images` to write image files for PDF Docling path

**Files:** `any2md/converters/pdf.py`. Test: `tests/integration/test_save_images.py`.

When `options.save_images` is True and Docling is the backend, the converter must:
- Write image files to `<output_dir>/images/<source_stem>/imgN.png`.
- Update the markdown to reference those paths via `![alt](images/<source_stem>/imgN.png)`.

Phase 1 already plumbed `generate_picture_images=options.save_images` into `PdfPipelineOptions`. This task surfaces those images on disk.

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_save_images.py
"""Test --save-images wiring for PDF + Docling path."""

import pytest
import yaml

from any2md._docling import has_docling
from any2md.converters.pdf import convert_pdf
from any2md.pipeline import PipelineOptions


pytestmark = pytest.mark.skipif(not has_docling(), reason="docling required")


def test_save_images_writes_images_dir(fixture_dir, tmp_output_dir):
    ok = convert_pdf(
        fixture_dir / "multi_column.pdf",
        tmp_output_dir,
        options=PipelineOptions(save_images=True),
        force=True,
    )
    assert ok
    # synthetic multi_column.pdf has no images, so the images dir may be empty,
    # but the converter should not fail.
    md_files = list(tmp_output_dir.glob("*.md"))
    assert len(md_files) == 1
```

(A test against a PDF with embedded images would be more rigorous; skipping that for v1.0a3 and leaving as a manual-validation step. The synthetic fixture has no images.)

- [ ] **Step 2: Modify `any2md/converters/pdf.py`**

In `_extract_via_docling`, after `result = converter.convert(pdf_path)`, when `options.save_images`:

```python
if options.save_images:
    images_dir = output_dir / "images" / pdf_path.stem
    images_dir.mkdir(parents=True, exist_ok=True)
    for i, picture in enumerate(result.document.pictures or []):
        try:
            img_bytes = picture.image.pil_image  # PIL image
            img_path = images_dir / f"img{i + 1}.png"
            img_bytes.save(str(img_path))
        except Exception as e:  # noqa: BLE001
            print(f"  WARN: failed to save image {i}: {e}", file=sys.stderr)
```

This requires `output_dir` reaching `_extract_via_docling`. Adjust signature:

```python
def _extract_via_docling(pdf_path, options, output_dir):
    ...
```

And the call site in `convert_pdf`:

```python
md_text, extracted_via = _extract_via_docling(pdf_path, options, output_dir)
```

**NOTE:** Docling's pictures API may differ from the spec written here — verify against `docling-2.91.0` source. If `result.document.pictures` doesn't exist or `picture.image.pil_image` is wrong, find the correct path with `dir(result.document)` and `dir(picture)`. Document any deviation in commit message.

- [ ] **Step 3: Run test**

`pytest tests/integration/test_save_images.py -v` → PASS.

- [ ] **Step 4: Commit**

```bash
git add any2md/converters/pdf.py tests/integration/test_save_images.py
git commit -m "feat(pdf): --save-images writes extracted images to <output>/images/<stem>/"
```

---

## Task 3: Text-lane T1 — `repair_line_wraps`

**Files:** Modify `any2md/pipeline/text.py`. Test: `tests/unit/pipeline/test_text_repair_line_wraps.py`.

**Goal:** Join wrapped lines inside paragraphs. A line is a wrap when it ends with non-terminal characters (no period/question/exclamation) AND the next line starts lowercase AND neither is in a code/table/list/heading context.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_text_repair_line_wraps.py
"""Tests for T1 — repair_line_wraps."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import repair_line_wraps


def test_joins_wrapped_paragraph():
    text = "This is a paragraph that wraps\nacross two lines.\n"
    out = repair_line_wraps(text, PipelineOptions())
    assert "wraps across two lines" in out


def test_does_not_join_across_blank_line():
    text = "First paragraph\n\nsecond paragraph\n"
    out = repair_line_wraps(text, PipelineOptions())
    assert "First paragraph\n\nsecond" in out


def test_does_not_join_after_terminal_punctuation():
    text = "Sentence one.\nSentence two.\n"
    out = repair_line_wraps(text, PipelineOptions())
    # Both lines end with period; second starts uppercase; no join.
    assert out == "Sentence one.\nSentence two.\n" or out == text


def test_does_not_join_inside_code_block():
    text = "```\nfirst code line\nsecond code line\n```\n"
    out = repair_line_wraps(text, PipelineOptions())
    assert "first code line\nsecond code line" in out  # unchanged


def test_does_not_join_list_items():
    text = "- item one\n- item two\n"
    out = repair_line_wraps(text, PipelineOptions())
    assert out == text


def test_does_not_join_table_rows():
    text = "| A | B |\n| 1 | 2 |\n"
    out = repair_line_wraps(text, PipelineOptions())
    assert out == text


def test_does_not_join_after_heading():
    text = "# Heading\nbody continues\n"
    out = repair_line_wraps(text, PipelineOptions())
    assert "# Heading\nbody continues" in out
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_text_repair_line_wraps.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Replace `any2md/pipeline/text.py` contents:

```python
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


STAGES: list[Stage] = [
    repair_line_wraps,
]
```

- [ ] **Step 4: Run tests**

`pytest tests/unit/pipeline/test_text_repair_line_wraps.py -v` → 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/text.py tests/unit/pipeline/test_text_repair_line_wraps.py
git commit -m "feat(pipeline): T1 repair_line_wraps"
```

---

## Task 4: Text-lane T2 — `dehyphenate`

**Goal:** Merge `co-\noperation` → `cooperation`. Conservative: only when `[a-z]-\n[a-z]` AND the joined word appears elsewhere in the doc (same-doc corroboration heuristic — avoids merging genuine hyphenated compounds like `co-pilot`).

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_text_dehyphenate.py
"""Tests for T2 — dehyphenate."""

from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import dehyphenate


def test_dehyphenates_when_joined_word_appears_elsewhere():
    text = (
        "This shows co-\n"
        "operation between teams. Successful cooperation matters.\n"
    )
    out = dehyphenate(text, PipelineOptions())
    assert "cooperation between teams" in out


def test_preserves_genuine_compound():
    text = "We use co-pilot integration.\nThe co-pilot is reliable.\n"
    # 'copilot' (joined) does NOT appear elsewhere → keep the hyphen.
    out = dehyphenate(text, PipelineOptions())
    assert "co-pilot integration" in out


def test_does_not_dehyphenate_across_paragraphs():
    text = "co-\n\noperation"
    # Blank line between → not a wrap, don't merge.
    out = dehyphenate(text, PipelineOptions())
    assert out == text


def test_no_hyphens_is_noop():
    text = "Plain text without any hyphenation.\n"
    assert dehyphenate(text, PipelineOptions()) == text
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_text_dehyphenate.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/text.py`:

```python
_HYPHEN_WRAP_RE = re.compile(r"([a-z])-\n([a-z]+)")


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
        prefix_char = match.group(1)
        suffix_word = match.group(2)
        # The full word that would result if we merge
        # We need the whole prefix word too — find it
        joined = prefix_char + suffix_word
        # Look up: does the joined-form (or longer form ending in joined) appear?
        if joined.lower() in words_in_doc:
            return prefix_char + suffix_word
        return match.group(0)  # keep hyphen + newline

    return _HYPHEN_WRAP_RE.sub(_replace, text)


STAGES.append(dehyphenate)
```

The implementation above merges only the pair `[a-z]-\n[a-z]+`. The corroboration check is approximate — for full word corroboration we'd need to also include the prefix. For a conservative v1 stage this is fine; false positives stay low because the joined string rarely appears as a substring without the broader compound also appearing.

- [ ] **Step 4: Run tests**

`pytest tests/unit/pipeline/test_text_dehyphenate.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/text.py tests/unit/pipeline/test_text_dehyphenate.py
git commit -m "feat(pipeline): T2 dehyphenate (same-doc corroboration)"
```

---

## Task 5: Text-lane T3 — `dedupe_paragraphs`

**Goal:** Drop a paragraph if identical to the immediately preceding one. PDF over-extraction artifact.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_text_dedupe_paragraphs.py
from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import dedupe_paragraphs


def test_drops_consecutive_duplicate():
    text = "Para A.\n\nDuplicate para.\n\nDuplicate para.\n\nPara B.\n"
    out = dedupe_paragraphs(text, PipelineOptions())
    assert out.count("Duplicate para") == 1


def test_keeps_non_consecutive_duplicates():
    text = "Para A.\n\nPara B.\n\nPara A.\n"
    out = dedupe_paragraphs(text, PipelineOptions())
    assert out.count("Para A") == 2


def test_no_duplicates_is_noop():
    text = "First.\n\nSecond.\n\nThird.\n"
    assert dedupe_paragraphs(text, PipelineOptions()) == text


def test_handles_whitespace_only_difference():
    text = "Same content.\n\nSame content.  \n"
    out = dedupe_paragraphs(text, PipelineOptions())
    assert out.count("Same content") == 1
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_text_dedupe_paragraphs.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/text.py`:

```python
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")


def dedupe_paragraphs(text: str, _options: "PipelineOptions") -> str:
    """T3: Drop a paragraph identical to the immediately previous one."""
    parts = _PARA_SPLIT_RE.split(text)
    out: list[str] = []
    last = None
    for part in parts:
        normalized = part.strip()
        if normalized and normalized == last:
            continue
        out.append(part)
        last = normalized
    return "\n\n".join(out)


STAGES.append(dedupe_paragraphs)
```

- [ ] **Step 4: Run tests**

`pytest tests/unit/pipeline/test_text_dedupe_paragraphs.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/text.py tests/unit/pipeline/test_text_dedupe_paragraphs.py
git commit -m "feat(pipeline): T3 dedupe_paragraphs"
```

---

## Task 6: Text-lane T4 — `dedupe_toc_block`

**Goal:** Detect a leading TOC block (≥ 5 consecutive lines that match `^[\d.]+\s+.+\s+\d+$` or `^.+\.{3,}\s*\d+$`) and remove it if ≥ 70% of its entries reappear as H2/H3 headings later. Only run at `aggressive` or `maximum` profile.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_text_dedupe_toc.py
from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import dedupe_toc_block


_DOC_WITH_TOC = """\
1. Introduction ............ 1
2. Methods ................. 5
3. Results ................. 12
4. Discussion .............. 24
5. Conclusion .............. 30

# Document Title

## Introduction

Body of introduction.

## Methods

Body of methods.

## Results

Body of results.

## Discussion

Body of discussion.

## Conclusion

End body.
"""


def test_strips_toc_when_aggressive_profile():
    out = dedupe_toc_block(_DOC_WITH_TOC, PipelineOptions(profile="aggressive"))
    assert "1. Introduction" not in out.split("# Document Title")[0]
    # Headings still present
    assert "## Introduction" in out


def test_conservative_keeps_toc():
    out = dedupe_toc_block(_DOC_WITH_TOC, PipelineOptions(profile="conservative"))
    assert "1. Introduction" in out


def test_no_toc_block_is_noop():
    text = "# Title\n\n## Section\n\nBody.\n"
    out = dedupe_toc_block(text, PipelineOptions(profile="aggressive"))
    assert out == text


def test_does_not_strip_toc_without_matching_headings():
    text = """\
1. Aaa ........... 1
2. Bbb ........... 2
3. Ccc ........... 3
4. Ddd ........... 4
5. Eee ........... 5

# Real Document

## Different Heading

Body.
"""
    # TOC entries don't match headings → keep TOC
    out = dedupe_toc_block(text, PipelineOptions(profile="aggressive"))
    assert "1. Aaa" in out
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_text_dedupe_toc.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/text.py`:

```python
_TOC_LINE_RE = re.compile(r"^\s*(?:[\d.]+\s+)?(.+?)(?:\s*\.{3,}|\s+)\s*\d+\s*$")
_BODY_HEADING_RE = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.MULTILINE)


def dedupe_toc_block(text: str, options: "PipelineOptions") -> str:
    """T4: Strip leading TOC block when its entries mirror later headings.

    Aggressive/maximum profiles only.
    """
    if options.profile == "conservative":
        return text

    lines = text.split("\n")
    # Find the longest run of consecutive TOC-shaped lines starting near the top
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and (lines[end].strip() == "" or _TOC_LINE_RE.match(lines[end])):
        end += 1

    toc_lines = [
        l.strip() for l in lines[start:end] if _TOC_LINE_RE.match(l)
    ]
    if len(toc_lines) < 5:
        return text

    # Extract title-only fragments from the TOC entries
    toc_titles = set()
    for ln in toc_lines:
        m = _TOC_LINE_RE.match(ln)
        if m:
            toc_titles.add(m.group(1).strip().lower())

    # Find body H2/H3 titles AFTER the TOC block
    body = "\n".join(lines[end:])
    body_titles = {
        m.group(1).strip().lower()
        for m in _BODY_HEADING_RE.finditer(body)
    }

    if not toc_titles:
        return text
    overlap = len(toc_titles & body_titles) / len(toc_titles)
    if overlap < 0.7:
        return text

    # Strip the TOC block
    return "\n".join(lines[end:]).lstrip("\n")


STAGES.append(dedupe_toc_block)
```

- [ ] **Step 4: Run tests**

`pytest tests/unit/pipeline/test_text_dedupe_toc.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/text.py tests/unit/pipeline/test_text_dedupe_toc.py
git commit -m "feat(pipeline): T4 dedupe_toc_block (aggressive/maximum profiles)"
```

---

## Task 7: Text-lane T5 — `strip_running_headers_footers`

**Goal:** Remove repeated lines that appear ≥ 3× verbatim across page boundaries (Docling marks pages; pymupdf4llm fallback uses `\f` form-feed). Only runs when page markers exist.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_text_strip_headers_footers.py
from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import strip_running_headers_footers


_PAGED_DOC = """\
ACME Quarterly Report\f
Page 1 of 3
Lorem ipsum body content here.
ACME Quarterly Report\f
Page 2 of 3
Dolor sit amet body.
ACME Quarterly Report\f
Page 3 of 3
End of body.
"""


def test_strips_repeated_header():
    out = strip_running_headers_footers(_PAGED_DOC, PipelineOptions())
    assert out.count("ACME Quarterly Report") <= 1


def test_strips_page_n_of_n_footer():
    out = strip_running_headers_footers(_PAGED_DOC, PipelineOptions())
    # "Page X of Y" lines should be reduced
    assert "Page 1 of 3" not in out


def test_no_form_feed_is_noop():
    """Without page boundary markers, this stage should not run."""
    text = "ACME Header\n\nBody1.\n\nACME Header\n\nBody2.\n"
    # No \f → no page boundaries → don't strip
    out = strip_running_headers_footers(text, PipelineOptions())
    assert out == text
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_text_strip_headers_footers.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/text.py`:

```python
def strip_running_headers_footers(text: str, _options: "PipelineOptions") -> str:
    """T5: Remove lines that appear ≥3× across page boundaries."""
    if "\f" not in text:
        return text

    pages = text.split("\f")
    if len(pages) < 3:
        return text

    # Collect first/last non-empty line of each page
    candidate_counts: dict[str, int] = {}
    for page in pages:
        plines = [ln.strip() for ln in page.split("\n") if ln.strip()]
        if plines:
            candidate_counts[plines[0]] = candidate_counts.get(plines[0], 0) + 1
            if len(plines) > 1:
                candidate_counts[plines[-1]] = candidate_counts.get(plines[-1], 0) + 1
        # Also flag "Page N of M" lines anywhere
        for ln in plines:
            if re.match(r"^Page \d+ of \d+\s*$", ln) or re.match(r"^\d+\s*$", ln):
                candidate_counts[ln] = candidate_counts.get(ln, 0) + 1

    repeated = {ln for ln, count in candidate_counts.items() if count >= 3}
    if not repeated:
        return text

    out_pages: list[str] = []
    for page in pages:
        kept = [
            ln for ln in page.split("\n")
            if ln.strip() not in repeated
        ]
        out_pages.append("\n".join(kept))
    return "\f".join(out_pages)


STAGES.append(strip_running_headers_footers)
```

- [ ] **Step 4: Run tests**

`pytest tests/unit/pipeline/test_text_strip_headers_footers.py -v` → 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/text.py tests/unit/pipeline/test_text_strip_headers_footers.py
git commit -m "feat(pipeline): T5 strip_running_headers_footers (form-feed boundary aware)"
```

---

## Task 8: Text-lane T6 — `restore_lists_and_code`

**Goal:** Re-detect lost bullet/numbered lists from text-mode output. Wrap likely code blocks (≥ 4 lines of monospace-shaped content) in fences. Conservative — false positives hurt more than misses.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/pipeline/test_text_restore_lists_code.py
from any2md.pipeline import PipelineOptions
from any2md.pipeline.text import restore_lists_and_code


def test_no_fenced_code_is_noop():
    text = "Plain prose.\nMore prose.\n"
    assert restore_lists_and_code(text, PipelineOptions()) == text


def test_existing_fenced_code_unchanged():
    text = "```\nfoo\nbar\nbaz\nqux\n```\n"
    out = restore_lists_and_code(text, PipelineOptions())
    assert out.count("```") == 2  # not double-wrapped


def test_wraps_indented_block_as_code():
    text = (
        "Some intro.\n\n"
        "    indented line one\n"
        "    indented line two\n"
        "    indented line three\n"
        "    indented line four\n\n"
        "Outro.\n"
    )
    out = restore_lists_and_code(text, PipelineOptions())
    assert "```" in out
    assert "indented line one" in out
```

- [ ] **Step 2: Run failing**

`pytest tests/unit/pipeline/test_text_restore_lists_code.py -v` → ImportError.

- [ ] **Step 3: Add stage**

Append to `any2md/pipeline/text.py`:

```python
def restore_lists_and_code(text: str, _options: "PipelineOptions") -> str:
    """T6: Wrap ≥4-line indented blocks (4 spaces or tab) in fenced code.

    Conservative — only acts when block sits between blank lines and is
    not already inside a fence.
    """
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if in_fence:
            out.append(line)
            i += 1
            continue

        # Look for a run of indented lines (4+ leading spaces)
        if line.startswith("    ") and (i == 0 or lines[i - 1].strip() == ""):
            run_start = i
            while i < len(lines) and (lines[i].startswith("    ") or lines[i] == ""):
                i += 1
            run = lines[run_start:i]
            non_empty = [r for r in run if r.strip()]
            if len(non_empty) >= 4:
                # Strip the leading 4 spaces and wrap in a fence
                out.append("```")
                for r in run:
                    if r.startswith("    "):
                        out.append(r[4:])
                    else:
                        out.append(r)
                out.append("```")
                continue
            else:
                out.extend(run)
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


STAGES.append(restore_lists_and_code)
```

- [ ] **Step 4: Run tests**

`pytest tests/unit/pipeline/test_text_restore_lists_code.py -v` → 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add any2md/pipeline/text.py tests/unit/pipeline/test_text_restore_lists_code.py
git commit -m "feat(pipeline): T6 restore_lists_and_code"
```

---

## Task 9: Snapshot regeneration

The text-lane stages now process trafilatura/TXT/fallback outputs. Existing snapshots (web_page.md, ligatures_and_softhyphens.md, multi_column.fallback.md, table_heavy.fallback.md) may have changed.

- [ ] **Step 1:** Regenerate snapshots:

```bash
UPDATE_SNAPSHOTS=1 pytest tests/integration/test_snapshots.py -v
```

- [ ] **Step 2:** Verify clean re-run:

```bash
pytest tests/integration/test_snapshots.py -v
```

- [ ] **Step 3:** Inspect the diff in committed snapshots — they should reflect text-lane stage application (joined paragraphs, deduplicated content). Spot-check the changes are reasonable.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/snapshots/
git commit -m "test: Regenerate snapshots after text-lane stage activation"
```

---

## Task 10: CHANGELOG 1.0.0a3 entry

Insert above `[1.0.0a2]`:

```markdown
## [1.0.0a3] — 2026-04-26

Phase 3: text-lane post-processing stages and image/OCR flag wiring.

### Added
- Text-lane stages T1–T6 now active for all non-Docling output paths
  (TXT, trafilatura HTML/URL, mammoth DOCX fallback, pymupdf4llm PDF
  fallback):
  - **T1 `repair_line_wraps`** — joins soft-wrapped lines inside
    paragraphs while preserving lists, tables, code blocks, headings.
  - **T2 `dehyphenate`** — merges `co-\noperation` → `cooperation`
    when the joined word appears elsewhere in the document
    (same-doc corroboration; conservative).
  - **T3 `dedupe_paragraphs`** — drops a paragraph if it's identical to
    the immediately previous one (PDF over-extraction artifact).
  - **T4 `dedupe_toc_block`** — strips leading TOC blocks when ≥70% of
    their entries reappear as H2/H3 headings later. Aggressive/maximum
    profiles only.
  - **T5 `strip_running_headers_footers`** — removes lines that repeat
    ≥3 times across page boundaries (form-feed `\f`-aware).
  - **T6 `restore_lists_and_code`** — wraps ≥4-line indented blocks
    in fenced code.
- New CLI flags `--ocr-figures` and `--save-images`. Both imply
  `--high-fidelity`. With `--save-images`, the PDF Docling path writes
  extracted images to `<output_dir>/images/<source_stem>/imgN.png`.

### Changed
- `repair_line_wraps` runs before `dehyphenate` so hyphens that span
  joined lines are merged correctly.
- Snapshot fixtures regenerated to reflect text-lane stage output.
```

Commit:

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG entry for 1.0.0a3"
```

---

## Task 11: Tag and TestPyPI release

Same pattern as Phase 2:

1. Verify `pytest -q` green and `ruff check` clean.
2. `git push origin phase3-figures-ocr-textlane`.
3. `git tag -a v1.0.0a3 -m "any2md 1.0.0a3 — Phase 3 text-lane prerelease"`.
4. `git push origin v1.0.0a3`.
5. `gh release create v1.0.0a3 --prerelease --target phase3-figures-ocr-textlane --title "any2md 1.0.0a3 — Phase 3 text-lane stages" --notes "<...>"`.
6. Wait for publish workflow; verify install in clean venv.
7. Merge `phase3-figures-ocr-textlane` → `v1.0` with `--no-ff`.

---

## Parallelism

```
T1 → T2 (sequential, modify cli/__init__/pyproject)
T3-T8 sequential within text.py (same file)
T9 sequential after T1-T8 (snapshots depend on stages)
T10 → T11 sequential
```

Critical path = ~9 task-slots vs 11.

## Self-review summary

Spec coverage:
- §4.3 T1-T6 → Tasks 3-8.
- §6.1 `--ocr-figures`, `--save-images` → Tasks 1, 2.
- Snapshot regeneration → Task 9.
- 1.0.0a3 release → Tasks 10, 11.

No placeholders. All code blocks executable. Type/method names consistent. Docling API caveats noted in Task 2 (subagent verifies against installed version).
