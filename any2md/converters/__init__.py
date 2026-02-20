"""Converter dispatcher for any2md."""

import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".txt"}


def convert_file(
    file_path: Path,
    output_dir: Path,
    force: bool = False,
    strip_links_flag: bool = False,
) -> bool:
    """Dispatch to the appropriate converter based on file extension."""
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        from any2md.converters.pdf import convert_pdf

        return convert_pdf(
            file_path, output_dir, force=force, strip_links_flag=strip_links_flag
        )
    elif ext == ".docx":
        from any2md.converters.docx import convert_docx

        return convert_docx(
            file_path, output_dir, force=force, strip_links_flag=strip_links_flag
        )
    elif ext in (".html", ".htm"):
        from any2md.converters.html import convert_html

        return convert_html(
            file_path, output_dir, force=force, strip_links_flag=strip_links_flag
        )
    elif ext == ".txt":
        from any2md.converters.txt import convert_txt

        return convert_txt(
            file_path, output_dir, force=force, strip_links_flag=strip_links_flag
        )
    else:
        print(
            f"  UNSUPPORTED: {file_path.name} (no converter for {ext})", file=sys.stderr
        )
        return False
