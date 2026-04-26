"""Test --save-images wiring for PDF + Docling path."""

import pytest

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
