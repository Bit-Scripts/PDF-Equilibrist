import tempfile
from pathlib import Path

import fitz

from pdf_equilibrist.core.document import Document


def _create_pdf(path: Path, page_texts):
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


def test_document_open_and_save(tmp_path: Path):
    source_path = tmp_path / "source.pdf"
    output_path = tmp_path / "saved.pdf"
    _create_pdf(source_path, ["Page 1", "Page 2"])

    document = Document()
    document.open(source_path)

    assert document.is_open
    assert document.path == source_path
    assert document.fitz_doc.page_count == 2

    document.save(output_path)
    assert output_path.exists()

    saved_doc = fitz.open(str(output_path))
    assert saved_doc.page_count == 2
    saved_doc.close()


def test_document_checkpoint_undo(tmp_path: Path):
    source_path = tmp_path / "source.pdf"
    _create_pdf(source_path, ["Original text"])

    document = Document()
    document.open(source_path)
    document.checkpoint()

    page = document.fitz_doc[0]
    page.insert_text((72, 72), " Added text")
    assert "Added text" in page.get_text()

    assert document.undo()
    assert "Added text" not in document.fitz_doc[0].get_text()
    assert document.can_undo is False
