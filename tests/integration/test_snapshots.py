"""Snapshot tests: golden outputs for synthetic fixtures.

Snapshots are committed under tests/fixtures/snapshots/. To regenerate
after an intentional change run:
    UPDATE_SNAPSHOTS=1 pytest tests/integration/test_snapshots.py
"""

import os
import re
from pathlib import Path

import pytest

from any2md.converters.docx import convert_docx
from any2md.converters.html import convert_html
from any2md.converters.pdf import convert_pdf
from any2md.converters.txt import convert_txt
from any2md.pipeline import PipelineOptions

SNAPSHOTS = {
    "web_page.html": ("html", convert_html),
    "ligatures_and_softhyphens.txt": ("txt", convert_txt),
    "multi_column.pdf": ("pdf", convert_pdf),
    "table_heavy.docx": ("docx", convert_docx),
}


_DATE_RE = re.compile(r'^date: ".*?"', re.MULTILINE)
_HASH_RE = re.compile(r'^content_hash: ".*?"', re.MULTILINE)


def _normalize(text: str) -> str:
    """Strip volatile fields (date, content_hash) so snapshots are stable."""
    text = _DATE_RE.sub('date: "<volatile>"', text)
    text = _HASH_RE.sub('content_hash: "<volatile>"', text)
    return text


@pytest.mark.parametrize("fixture_name", list(SNAPSHOTS))
def test_snapshot(fixture_name, fixture_dir, snapshot_dir, tmp_output_dir):
    _, convert = SNAPSHOTS[fixture_name]
    ok = convert(
        fixture_dir / fixture_name,
        tmp_output_dir,
        options=PipelineOptions(),
        force=True,
    )
    assert ok
    out = next(tmp_output_dir.glob("*.md"))
    actual = _normalize(out.read_text(encoding="utf-8"))

    snap_name = Path(fixture_name).stem + ".md"
    snap_path = snapshot_dir / snap_name

    if os.environ.get("UPDATE_SNAPSHOTS"):
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(actual, encoding="utf-8")
        return

    expected = snap_path.read_text(encoding="utf-8") if snap_path.exists() else None
    if expected is None:
        pytest.fail(
            f"Snapshot missing: {snap_path}. "
            f"Run UPDATE_SNAPSHOTS=1 pytest to create."
        )
    assert actual == expected, "Snapshot diff. Inspect or run UPDATE_SNAPSHOTS=1."
