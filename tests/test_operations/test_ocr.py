"""Tests de operations/ocr.py — moteur embarqué, hors-ligne, accents français."""
import socket

import fitz
import pytest

pytest.importorskip("rapidocr")

from pdf_equilibrist.operations import ocr  # noqa: E402

PHRASE = "Société Équilibre : réglement déjà versé, façade où"


def _scanned_doc() -> fitz.Document:
    """PDF d'une page ne contenant qu'une image (aucune couche texte)."""
    src = fitz.open()
    sp = src.new_page()
    sp.insert_text((50, 100), PHRASE, fontsize=18)
    pix = sp.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
    doc = fitz.open()
    page = doc.new_page(width=sp.rect.width, height=sp.rect.height)
    page.insert_image(page.rect, pixmap=pix)
    return doc


@pytest.fixture
def no_network(monkeypatch):
    """Toute tentative de connexion ou de résolution DNS fait échouer le test."""
    def _refuse(*a, **k):
        raise AssertionError("connexion réseau tentée pendant l'OCR")
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)


def test_models_are_shipped_in_the_package():
    d = ocr._models_dir()
    for name in ocr._MODEL_FILES:
        assert (d / name).is_file(), name


def test_missing_models_raise_instead_of_downloading(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_models_dir", lambda: tmp_path)
    with pytest.raises(ocr.OcrModelsMissingError):
        ocr._get_ocr_engine()


def test_scanned_page_detection():
    doc = _scanned_doc()
    assert ocr._is_scanned_page(doc[0])


def test_apply_ocr_makes_page_searchable_offline(no_network):
    doc = _scanned_doc()
    assert doc[0].get_text().strip() == ""
    assert ocr.apply_ocr_to_pdf(doc) == 1
    text = doc[0].get_text()
    assert "Société" in text and "Équilibre" in text
    assert "déjà" in text and "façade" in text


def test_ocr_to_markdown_offline(no_network, tmp_path):
    out = ocr.ocr_to_markdown(_scanned_doc(), tmp_path / "out.md")
    assert "Société" in out.read_text(encoding="utf-8")


def test_text_pdf_is_not_ocred(no_network):
    doc = fitz.open()
    doc.new_page().insert_text((50, 100), "Déjà du texte", fontsize=14)
    assert ocr.apply_ocr_to_pdf(doc) == 0
