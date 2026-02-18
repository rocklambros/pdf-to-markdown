# mdconv

Convert PDF, DOCX, and HTML files — or web pages by URL — to clean, LLM-optimized Markdown with YAML frontmatter.

Built on [PyMuPDF](https://pymupdf.readthedocs.io/) and [pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) for PDF extraction, [mammoth](https://github.com/mwilliamson/python-mammoth) + [markdownify](https://github.com/matthewwithanm/python-markdownify) for DOCX conversion, and [trafilatura](https://trafilatura.readthedocs.io/) + [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for HTML/URL extraction. Preserves document structure — headings, lists, tables, and formatting — while stripping out noise like images and excessive whitespace.

## Features

- **Multi-format support** — Converts PDF, DOCX, and HTML files (.html, .htm) to Markdown
- **URL fetching** — Convert web pages directly by passing an http/https URL
- **LLM-ready output** — Clean markdown optimized for ingestion by language models
- **YAML frontmatter** — Each file includes title, source filename or URL, and format-specific metadata (page count for PDFs, word count for DOCX/HTML)
- **Batch processing** — Convert a single file or every supported file in a directory
- **Auto-detection** — Routes to the correct converter based on file extension
- **Smart skip** — Won't overwrite existing conversions unless `--force` is used
- **Filename sanitization** — Handles spaces, special characters, and unicode dashes
- **Title extraction** — Automatically pulls the document title from the first heading
- **`--strip-links` flag** — Remove markdown hyperlinks from output, keeping only the link text

## Installation

Requires Python 3.8+.

```bash
pip install pymupdf pymupdf4llm mammoth markdownify trafilatura beautifulsoup4
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

Clone the repository:

```bash
git clone https://github.com/rocklambros/mdconv.git
cd mdconv
```

## Usage

### Convert all supported files in the current directory

```bash
python3 mdconv.py
```

### Convert specific files

```bash
python3 mdconv.py report.pdf proposal.docx "meeting notes.pdf"
```

### Convert an HTML file

```bash
python3 mdconv.py page.html
```

### Convert a web page by URL

```bash
python3 mdconv.py https://example.com/article
```

### Mixed batch — PDFs, DOCX, HTML files, and URLs together

```bash
python3 mdconv.py doc.pdf page.html https://example.com
```

### Strip links from output

```bash
python3 mdconv.py --strip-links doc.pdf
```

### Scan a directory for supported files

```bash
python3 mdconv.py --input-dir ./documents
```

### Overwrite existing markdown files

```bash
python3 mdconv.py --force
```

### Custom output directory

```bash
python3 mdconv.py --output-dir ./converted
```

### Combine options

```bash
python3 mdconv.py -f -o ./out docs/*.pdf docs/*.docx docs/*.html
```

### Run as a module

```bash
python -m mdconv --help
```

By default, converted files are written to a `Text/` subdirectory next to the script.

## Output Format

Each converted file includes YAML frontmatter followed by the cleaned markdown content.

**PDF output:**

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

**DOCX output:**

```markdown
---
title: "Project Proposal"
source_file: "proposal.docx"
word_count: 3847
type: docx
---

# Project Proposal

Document content here...
```

**HTML file output:**

```markdown
---
title: "Page Title"
source_file: "page.html"
word_count: 1234
type: html
---

# Page Title

Document content here...
```

**URL output:**

```markdown
---
title: "Article Title"
source_url: "https://example.com/article"
word_count: 567
type: html
---

# Article Title

Document content here...
```

## CLI Reference

```
usage: mdconv.py [-h] [--input-dir PATH] [--force] [--output-dir PATH] [--strip-links] [files ...]

Convert PDF, DOCX, and HTML files to LLM-optimized Markdown.

positional arguments:
  files                 Files or URLs to convert. Supports PDF, DOCX, HTML files and
                        http(s) URLs. If omitted, converts all supported files in the
                        current directory.

options:
  -h, --help            show this help message and exit
  --input-dir, -i PATH  Directory to scan for supported files (PDF, DOCX, HTML)
  --force, -f           Overwrite existing .md files
  --output-dir, -o PATH Output directory (default: ./Text)
  --strip-links         Remove markdown links, keeping only the link text
```

## How It Works

1. **Discovery** — Finds PDF, DOCX, and HTML files from command-line args, or scans the current directory; URLs are detected automatically
2. **Routing** — Dispatches each file to the appropriate converter based on extension (or URL scheme)
3. **Extraction**
   - PDFs use `pymupdf4llm.to_markdown()`
   - DOCX files use `mammoth` (DOCX to HTML) then `markdownify` (HTML to Markdown)
   - HTML files and URLs pass through a pipeline: BS4 pre-cleaning (strips scripts, nav, footer, etc.) then `trafilatura` content extraction, with `markdownify` as a fallback
4. **Title detection** — Searches for the first H1-H3 heading; falls back to the filename (or hostname for URLs)
5. **Cleanup** — Collapses excessive blank lines and strips trailing whitespace
6. **Link stripping** — If `--strip-links` is set, removes markdown hyperlinks while preserving the link text
7. **Frontmatter** — Prepends YAML metadata (page count for PDFs, word count for DOCX/HTML, source URL for fetched pages)
8. **Write** — Saves to the output directory with a sanitized filename

## License

MIT
