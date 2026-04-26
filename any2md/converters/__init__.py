"""Converter dispatcher for any2md."""

import sys
from pathlib import Path

from any2md.pipeline import PipelineOptions

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".txt"}


def convert_file(
    file_path: Path,
    output_dir: Path,
    options: PipelineOptions | None = None,
    force: bool = False,
    strip_links_flag: bool = False,
) -> bool:
    """Dispatch to the appropriate converter based on file extension."""
    if options is None:
        options = PipelineOptions(strip_links=strip_links_flag)
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        from any2md.converters.pdf import convert_pdf
        return convert_pdf(file_path, output_dir, options=options, force=force)
    if ext == ".docx":
        from any2md.converters.docx import convert_docx
        return convert_docx(file_path, output_dir, options=options, force=force)
    if ext in (".html", ".htm"):
        from any2md.converters.html import convert_html
        return convert_html(file_path, output_dir, options=options, force=force)
    if ext == ".txt":
        from any2md.converters.txt import convert_txt
        return convert_txt(file_path, output_dir, options=options, force=force)
    print(
        f"  UNSUPPORTED: {file_path.name} (no converter for {ext})", file=sys.stderr
    )
    return False
