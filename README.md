# pdf-to-markdown

Convert PDF files to clean, LLM-optimized Markdown with YAML frontmatter.

Built on [PyMuPDF](https://pymupdf.readthedocs.io/) and [pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) for accurate text extraction that preserves document structure — headings, lists, tables, and formatting — while stripping out noise like images and excessive whitespace.

## Features

- **LLM-ready output** — Clean markdown optimized for ingestion by language models
- **YAML frontmatter** — Each file includes title, source filename, page count, and type metadata
- **Batch processing** — Convert a single file or every PDF in a directory
- **Smart skip** — Won't overwrite existing conversions unless `--force` is used
- **Filename sanitization** — Handles spaces, special characters, and unicode dashes
- **Title extraction** — Automatically pulls the document title from the first heading

## Installation

Requires Python 3.8+.

```bash
pip install pymupdf pymupdf4llm
```

Clone the repository:

```bash
git clone https://github.com/rocklambros/pdf-to-markdown.git
cd pdf-to-markdown
```

## Usage

### Convert all PDFs in the script directory

```bash
python3 pdf2md.py
```

### Convert specific files

```bash
python3 pdf2md.py report.pdf invoice.pdf "meeting notes.pdf"
```

### Overwrite existing markdown files

```bash
python3 pdf2md.py --force
```

### Custom output directory

```bash
python3 pdf2md.py --output-dir ./converted
```

### Combine options

```bash
python3 pdf2md.py -f -o ./out docs/*.pdf
```

By default, converted files are written to a `Text/` subdirectory next to the script.

## Output Format

Each converted file includes YAML frontmatter followed by the cleaned markdown content:

```markdown
---
title: "Quarterly Financial Report"
source_file: "Q3 Report 2024.pdf"
pages: 12
type: pdf
---

# Quarterly Financial Report

Document content here...
```

## CLI Reference

```
usage: pdf2md.py [-h] [--force] [--output-dir PATH] [files ...]

positional arguments:
  files                 PDF files to convert (default: all PDFs in script dir)

options:
  -h, --help            show this help message and exit
  --force, -f           Overwrite existing .md files
  --output-dir, -o PATH Output directory (default: ./Text)
```

## How It Works

1. **Discovery** — Finds PDFs from command-line args or scans the script directory
2. **Extraction** — Uses `pymupdf4llm.to_markdown()` with `force_text=True` for reliable text extraction (images are excluded)
3. **Title detection** — Searches for the first H1-H3 heading; falls back to the filename
4. **Cleanup** — Collapses excessive blank lines and strips trailing whitespace
5. **Frontmatter** — Prepends YAML metadata block with title, source file, page count, and type
6. **Write** — Saves to the output directory with a sanitized filename (spaces become underscores, special characters removed)

## License

MIT
