from pathlib import Path

import fitz
from pdf_equilibrist.operations.pages import (
    rotate_pages,
    invert_pages,
    split_pdf,
    merge_pdfs,
    insert_page,
    crop_page,
    set_page_size,
)


def _create_sample_doc():
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")
    return doc


def test_rotate_pages():
    doc = _create_sample_doc()
    rotate_pages(doc, 90, [0, 2])
    assert doc[0].rotation == 90
    assert doc[1].rotation == 0
    assert doc[2].rotation == 90
    doc.close()


def test_invert_pages():
    doc = _create_sample_doc()
    result = invert_pages(doc)
    assert result.page_count == 3
    assert "Page 3" in result[0].get_text()
    assert "Page 1" in result[2].get_text()
    doc.close()
    result.close()


def test_split_pdf(tmp_path: Path):
    doc = _create_sample_doc()
    paths = split_pdf(doc, tmp_path)
    assert len(paths) == 3
    assert all(p.exists() for p in paths)
    assert fitz.open(str(paths[0])).page_count == 1
    doc.close()


def test_merge_pdfs(tmp_path: Path):
    paths = []
    for i in range(2):
        temp_doc = fitz.open()
        temp_doc.new_page().insert_text((72, 72), f"Doc {i + 1}")
        path = tmp_path / f"doc_{i + 1}.pdf"
        temp_doc.save(str(path))
        temp_doc.close()
        paths.append(path)

    merged = merge_pdfs(paths)
    assert merged.page_count == 2
    assert "Doc 1" in merged[0].get_text()
    assert "Doc 2" in merged[1].get_text()
    merged.close()


def test_insert_page_blank():
    doc = _create_sample_doc()
    insert_page(doc, 0, None)
    assert doc.page_count == 4
    doc.close()


def test_crop_page():
    doc = _create_sample_doc()
    rect = fitz.Rect(0, 0, 100, 100)
    crop_page(doc, 0, rect)
    assert doc[0].cropbox == rect
    doc.close()


def test_set_page_size():
    doc = _create_sample_doc()
    set_page_size(doc, 0, 595, 842)
    assert doc[0].mediabox.width == 595
    assert doc[0].mediabox.height == 842
    doc.close()
