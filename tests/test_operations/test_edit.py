from pathlib import Path

import fitz
from pdf_equilibrist.operations.edit import extract_text_blocks, apply_text_edits


def _create_sample_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Bonjour PDF")
    doc.save(str(path))
    doc.close()
    return path


def test_extract_text_blocks_and_apply_text_edits(tmp_path: Path):
    pdf_path = _create_sample_pdf(tmp_path / "sample.pdf")
    doc = fitz.open(str(pdf_path))

    blocks = extract_text_blocks(doc, 0)
    assert len(blocks) >= 1
    assert any("Bonjour" in block.text for block in blocks)

    edited = {blocks[0].block_id: "Salut PDF"}
    apply_text_edits(doc, 0, blocks, edited)

    page_text = doc[0].get_text()
    assert "Salut PDF" in page_text
    assert "Bonjour PDF" not in page_text

    doc.close()
