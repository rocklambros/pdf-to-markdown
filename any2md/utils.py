"""Shared utility functions for any2md."""

import re
import urllib.parse
from pathlib import Path

# Pre-compiled regex patterns
_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_SPECIAL_CHARS_RE = re.compile(r"[,;:'\"\u2014\u2013]")
_COLLAPSE_UNDERSCORES_RE = re.compile(r"_+")
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)", re.MULTILINE)
_BOLD_RE = re.compile(r"\*+")
_UNDERSCORE_COLLAPSE_RE = re.compile(r"_+")
_BLANK_LINES_RE = re.compile(r"\n{4,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def sanitize_filename(name: str) -> str:
    """Convert a source filename to a sanitized .md filename.

    Strips control characters, null bytes, and path separators.
    Matches existing convention: spaces -> underscores, extension -> .md.
    """
    stem = Path(name).stem
    # Strip control characters and null bytes
    stem = _CTRL_CHARS_RE.sub("", stem)
    # Remove path separators
    stem = stem.replace("/", "").replace("\\", "")
    # Replace spaces with underscores
    stem = stem.replace(" ", "_")
    # Replace characters problematic in filenames
    stem = _SPECIAL_CHARS_RE.sub("", stem)
    # Collapse multiple underscores
    stem = _COLLAPSE_UNDERSCORES_RE.sub("_", stem)
    # Strip leading/trailing underscores
    stem = stem.strip("_")
    # Guard empty stem
    if not stem:
        stem = "untitled"
    return stem + ".md"


def extract_title(markdown_text: str, fallback: str) -> str:
    """Extract the first markdown heading as the document title."""
    match = _HEADING_RE.search(markdown_text)
    if match:
        title = match.group(1).strip()
        # Clean markdown formatting from title
        title = _BOLD_RE.sub("", title)
        title = _UNDERSCORE_COLLAPSE_RE.sub(" ", title)
        title = title.strip()
        if len(title) > 10:
            return title
    # Fallback: derive from filename
    return fallback.replace("_", " ").strip()


def clean_markdown(text: str) -> str:
    """Clean up markdown for LLM consumption.

    Reduces excessive whitespace while preserving structure.
    """
    # Collapse 3+ consecutive blank lines to 2
    text = _BLANK_LINES_RE.sub("\n\n\n", text)
    # Remove trailing whitespace on each line
    text = _TRAILING_WS_RE.sub("", text)
    # Ensure file ends with single newline
    text = text.rstrip() + "\n"
    return text


def escape_yaml_string(value: str) -> str:
    """Escape a string for safe inclusion in double-quoted YAML values."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def strip_links(text: str) -> str:
    """Replace markdown links with their display text.

    Converts ``[text](url)`` to ``text``.
    """
    return _LINK_RE.sub(r"\1", text)


def build_frontmatter(
    title: str,
    source: str,
    source_key: str = "source_file",
    doc_type: str = "",
    **extra: object,
) -> str:
    """Build a YAML frontmatter block with proper escaping.

    Parameters
    ----------
    title : str
        Document title (will be YAML-escaped).
    source : str
        Source file name or URL (will be YAML-escaped).
    source_key : str
        YAML key for the source field (default ``"source_file"``).
    doc_type : str
        Document type tag (e.g. ``"pdf"``, ``"html"``).
    **extra
        Additional key-value pairs to include in frontmatter.
    """
    lines = [
        "---",
        f'title: "{escape_yaml_string(title)}"',
        f'{source_key}: "{escape_yaml_string(source)}"',
    ]
    for key, value in extra.items():
        if isinstance(value, str):
            lines.append(f'{key}: "{escape_yaml_string(value)}"')
        else:
            lines.append(f"{key}: {value}")
    if doc_type:
        lines.append(f"type: {doc_type}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def read_text_with_fallback(path: Path) -> str:
    """Read a text file, trying utf-8 first then falling back to latin-1."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def url_to_filename(url: str) -> str:
    """Convert a URL to a sanitized .md filename.

    Uses the netloc and path components, replacing dots and slashes
    with underscores and collapsing duplicates.

    Example::

        >>> url_to_filename("https://example.com/blog/my-post")
        'example_com_blog_my-post.md'
    """
    parsed = urllib.parse.urlparse(url)
    raw = parsed.netloc + parsed.path
    # Replace dots and slashes with underscores
    raw = raw.replace(".", "_").replace("/", "_")
    # Strip leading/trailing underscores
    raw = raw.strip("_")
    # Collapse multiple underscores
    raw = _COLLAPSE_UNDERSCORES_RE.sub("_", raw)
    return raw + ".md"
