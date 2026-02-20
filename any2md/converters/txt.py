"""Plain text to Markdown converter module."""

import re
import sys
from pathlib import Path

from any2md.utils import sanitize_filename, extract_title, clean_markdown, strip_links, escape_yaml_string

# Patterns
_SEPARATOR_RE = re.compile(r"^([=\-*_~])\1{2,}\s*$")
_BULLET_RE = re.compile(r"^[•–·]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\(?\d{1,3}[.)]\)?\s+(.*)$")
_LETTERED_RE = re.compile(r"^\(?[a-zA-Z][.)]\)?\s+(.*)$")
_INDENT_RE = re.compile(r"^(?:    |\t)(.*)$")
_ALL_CAPS_RE = re.compile(r"^[A-Z][A-Z0-9 /&,:\-]{2,78}$")


def _is_title_case(line: str) -> bool:
    """Check if a line is in Title Case (most words capitalized)."""
    words = line.split()
    if len(words) < 2:
        return False
    skip = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "is"}
    caps = sum(1 for w in words if w[0].isupper() or w.lower() in skip)
    return caps >= len(words) * 0.7


def _title_case_from_caps(text: str) -> str:
    """Convert ALL CAPS text to Title Case."""
    return text.title()


def structurize(text: str) -> str:
    """Convert plain text to Markdown by detecting implicit structure."""
    # Normalize tabs to spaces
    text = text.replace("\t", "    ")
    lines = text.split("\n")
    output = []
    i = 0
    title_emitted = False
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()
        prev_stripped = lines[i - 1].strip() if i > 0 else ""
        next_stripped = lines[i + 1].strip() if i < n - 1 else ""

        # --- 1. Separator / setext underline detection ---
        sep_match = _SEPARATOR_RE.match(stripped)
        if sep_match and stripped:
            char = sep_match.group(1)
            # Setext heading: previous non-empty line becomes heading
            if prev_stripped and output and output[-1].strip():
                prev_text = output[-1].strip()
                # Don't promote if prev line is already a markdown heading
                if not prev_text.startswith("#"):
                    if char == "=":
                        output[-1] = "# " + prev_text
                    else:
                        output[-1] = "## " + prev_text
                    i += 1
                    continue
            # Standalone separator
            output.append("---")
            i += 1
            continue

        # --- 2. Indented block detection ---
        if _INDENT_RE.match(line) and stripped:
            block_lines = []
            while i < n and (_INDENT_RE.match(lines[i]) or not lines[i].strip()):
                # Stop collecting blank lines if next non-blank isn't indented
                if not lines[i].strip():
                    # Peek ahead for more indented content
                    j = i + 1
                    while j < n and not lines[j].strip():
                        j += 1
                    if j < n and _INDENT_RE.match(lines[j]):
                        block_lines.append("")
                        i += 1
                        continue
                    else:
                        break
                indent_m = _INDENT_RE.match(lines[i])
                block_lines.append(indent_m.group(1) if indent_m else lines[i])
                i += 1
            output.append("```")
            output.extend(block_lines)
            output.append("```")
            continue

        # --- 3. Bullet list normalization ---
        bullet_m = _BULLET_RE.match(stripped)
        if bullet_m:
            output.append("- " + bullet_m.group(1))
            i += 1
            continue

        # --- 4. Numbered/lettered list normalization ---
        num_m = _NUMBERED_RE.match(stripped)
        let_m = _LETTERED_RE.match(stripped) if not num_m else None
        if num_m:
            output.append("1. " + num_m.group(1))
            i += 1
            continue
        if let_m:
            output.append("1. " + let_m.group(1))
            i += 1
            continue

        # --- 5. ALL CAPS heading detection ---
        if _ALL_CAPS_RE.match(stripped) and len(stripped) <= 80:
            # Must be followed by blank line or EOF to be a heading
            if not next_stripped or i == n - 1:
                if not title_emitted:
                    output.append("# " + _title_case_from_caps(stripped))
                    title_emitted = True
                else:
                    output.append("## " + _title_case_from_caps(stripped))
                i += 1
                continue

        # --- 6. Title Case sub-heading detection ---
        if (3 <= len(stripped) <= 80
                and not prev_stripped
                and not next_stripped
                and _is_title_case(stripped)
                and not stripped.endswith((".", "!", "?", ",", ";", ":"))
                and i > 0):
            output.append("### " + stripped)
            i += 1
            continue

        # --- 7. Default passthrough ---
        output.append(line)
        i += 1

    return "\n".join(output)


def convert_txt(
    txt_path: Path,
    output_dir: Path,
    force: bool = False,
    strip_links_flag: bool = False,
) -> bool:
    """Convert a plain text file to LLM-optimized Markdown.

    Returns True on success, False on failure.
    """
    out_name = sanitize_filename(txt_path.name)
    out_path = output_dir / out_name

    if out_path.exists() and not force:
        print(f"  SKIP (exists): {out_name}")
        return True

    try:
        # Read with encoding fallback
        try:
            raw_text = txt_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = txt_path.read_text(encoding="latin-1")

        # Reject empty files
        if not raw_text.strip():
            print(f"  FAIL: {txt_path.name} -- empty file", file=sys.stderr)
            return False

        # Structurize plain text to markdown
        md_text = structurize(raw_text)

        # Clean markdown
        md_text = clean_markdown(md_text)

        # Optional link stripping
        if strip_links_flag:
            md_text = strip_links(md_text)

        # Extract title for frontmatter
        title = extract_title(md_text, txt_path.stem)
        word_count = len(md_text.split())

        # Build frontmatter
        frontmatter = (
            f'---\n'
            f'title: "{escape_yaml_string(title)}"\n'
            f'source_file: "{escape_yaml_string(txt_path.name)}"\n'
            f'word_count: {word_count}\n'
            f'type: txt\n'
            f'---\n\n'
        )

        full_text = frontmatter + md_text

        # Write output
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(full_text, encoding="utf-8")
        print(f"  OK: {out_name} ({word_count} words)")
        return True

    except Exception as e:
        print(f"  FAIL: {txt_path.name} -- {e}", file=sys.stderr)
        return False
