"""Choix de police pour l'ajout de texte."""
import pymupdf
import pytest

from pdf_equilibrist.ui.dialogs import PDF_FONTS, pdf_fontname


@pytest.mark.parametrize("family", list(PDF_FONTS))
@pytest.mark.parametrize("bold", [False, True])
@pytest.mark.parametrize("italic", [False, True])
def test_pdf_fontname_is_insertable(family, bold, italic):
    name = pdf_fontname(family, bold, italic)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(pymupdf.Point(50, 50), "Éàç test", fontname=name, fontsize=12)
    assert "test" in page.get_text()


def test_pdf_fontname_unknown_family_falls_back():
    assert pdf_fontname("Inconnue", False, False) == "helv"
