# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0a1] — 2026-04-26

First prerelease of any2md v1.0. Phase 1 of 5: foundation only — no Docling
backend yet, no new CLI flags. Output frontmatter has been rewritten to be
SSRM-compatible (Structured Security Reasoning Markdown) — this is a
breaking change for downstream consumers parsing v0.7 output. See
`docs/superpowers/specs/2026-04-26-any2md-v1-design.md` for the full
v1.0 design and `docs/superpowers/plans/2026-04-26-any2md-v1-phase1-foundation.md`
for this phase's task plan.

### Added
- New `any2md/frontmatter.py` module — SSRM-compatible YAML emitter with the
  `SourceMeta` dataclass, deterministic `compute_content_hash`,
  `estimate_tokens`, `recommend_chunk_level`, `extract_abstract`, and
  `derive_title` helpers, plus the central `compose()` function (the only
  producer of the YAML block — converters never touch YAML directly).
- New `any2md/pipeline/` package with the two-lane post-processing runner
  (`structured` and `text` lanes both empty in Phase 1; filled in Phase 2/3)
  and seven shared cleanup stages C1–C7 in `pipeline/cleanup.py`:
  NFC normalization, soft-hyphen strip, ligature normalization (whitelist
  driven, NOT blanket NFKC), smart-quote/dash normalization, whitespace
  collapse, footnote-marker strip (aggressive/maximum profiles only), and
  read-only validation that emits non-fatal warnings via a contextvar.
- New `any2md/validators.py` — heading-hierarchy and `content_hash` round-trip
  checks. Used by C7 and exposed for programmatic consumers.
- pytest test suite: 86 tests covering pipeline stages, frontmatter helpers,
  content_hash determinism (including known empty-string SHA-256 vector),
  validators, all four converters end-to-end, CLI smoke tests, and
  snapshot tests for golden output.
- Synthetic test fixtures (HTML, TXT, multi-column PDF, table-heavy DOCX)
  under `tests/fixtures/docs/` — all owned, deterministic, and small.
  Generator script `tests/fixtures/make_fixtures.py` regenerates the binary
  fixtures (PDF via reportlab, DOCX via direct zip+XML — no python-docx dep).
- `[dev]` extras in `pyproject.toml`: `pytest`, `pytest-snapshot`,
  `reportlab`, `ruff`.

### Changed
- **BREAKING:** Output frontmatter shape is now SSRM-compatible. New required
  fields: `document_id` (empty string by default — opt-in via future
  `--auto-id`), `version`, `date`, `status: "draft"`, `document_type` (empty
  for non-security documents), `content_domain` (empty array),
  `authors`, `organization`, `generation_metadata.authored_by: "unknown"`,
  and `content_hash` (SHA-256 of NFC + LF body). Optional fields auto-filled
  when derivable: `keywords`, `token_estimate`, `recommended_chunk_level`,
  `abstract_for_rag` (only for documents ≥ 500 estimated tokens).
- v0.7 fields `source_file`, `source_url`, `pages`, `word_count`, and `type`
  are retained as any2md extension fields for traceability. A new
  `extracted_via` extension field records which library produced the
  markdown (`pymupdf4llm` / `mammoth+markdownify` / `trafilatura` /
  `trafilatura+bs4_fallback` / `heuristic`).
- Body is NFC-normalized with LF line endings before write — outputs are
  byte-deterministic for a given input + flag set.
- All four converters now route through the shared post-processing pipeline
  via `pipeline.run(text, lane, options)` and emit through
  `frontmatter.compose(body, meta, options)`. Converters return
  `(markdown, SourceMeta)` shape internally — they no longer touch YAML.
- DOCX metadata extraction: now reads `docProps/core.xml` and
  `docProps/app.xml` directly via `zipfile + xml.etree.ElementTree`. No
  python-docx dependency added.
- HTML converter: uses `trafilatura.bare_extraction(...)` for metadata
  (title/author/sitename/date/categories). For URL inputs, a single
  best-effort HEAD request captures HTTP `Last-Modified`.
- `.gitignore` now excludes `template/`, `test_docs/`, and `.worktrees/`.

### Carried forward unchanged
- All v0.7 CLI flags (`--input-dir`, `--output-dir`, `--force`,
  `--strip-links`, `--recursive`, `--max-file-size`, positional file/URL/dir
  arguments). The `--strip-links` flag is now wired through `PipelineOptions`.
- SSRF protection on URL fetching (private/reserved/loopback IP rejection).
- File size limits (default 100 MB).
- Filename sanitization rules.
- Skip-if-exists unless `--force`.
- pymupdf4llm, mammoth, markdownify, trafilatura, BeautifulSoup, lxml
  backends.
- Python 3.10+ floor.

### Out of scope for Phase 1
Phase 2 (Docling backend, `--high-fidelity`, structured-lane stages S1–S4),
Phase 3 (figure/OCR handling, text-lane stages T1–T6, full metadata
extraction), Phase 4 (`--meta`, `.any2md.toml`, `--auto-id`, `--strict`,
`--quiet`, `--verbose`, full documentation rewrite), Phase 5 (release
validation, 1.0.0).
