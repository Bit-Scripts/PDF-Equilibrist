"""Document : suivi des modifications non enregistrées (astérisque d'onglet, confirmation à la fermeture)."""
import pymupdf
import pytest

from pdf_equilibrist.core.document import Document


@pytest.fixture
def pdf_path(tmp_path):
    path = tmp_path / "a.pdf"
    d = pymupdf.open()
    d.new_page()
    d.save(path)
    d.close()
    return path


def test_fresh_document_is_not_modified(pdf_path):
    doc = Document()
    doc.open(pdf_path)
    assert not doc.is_modified


def test_checkpoint_marks_modified_and_signals_once(pdf_path):
    doc = Document()
    doc.open(pdf_path)
    seen = []
    doc.modified_changed.connect(seen.append)
    doc.checkpoint()
    doc.checkpoint()
    assert doc.is_modified
    assert seen == [True]   # une seule bascule, pas un signal par modification


def test_mark_modified_without_checkpoint(pdf_path):
    doc = Document()
    doc.open(pdf_path)
    doc.mark_modified()   # ex. édition de texte, déplacement de page
    assert doc.is_modified


def test_save_clears_modified(pdf_path, tmp_path):
    doc = Document()
    doc.open(pdf_path)
    doc.checkpoint()
    seen = []
    doc.modified_changed.connect(seen.append)
    doc.save(tmp_path / "b.pdf")
    assert not doc.is_modified
    assert seen == [False]


def test_failed_save_keeps_modified(pdf_path, tmp_path, monkeypatch):
    doc = Document()
    doc.open(pdf_path)
    doc.checkpoint()

    def boom(*_a, **_k):
        raise OSError("disque plein")

    monkeypatch.setattr(doc.fitz_doc, "save", boom, raising=False)
    with pytest.raises(OSError):
        doc.save(tmp_path / "c.pdf")
    assert doc.is_modified


def test_undo_stays_modified(pdf_path):
    doc = Document()
    doc.open(pdf_path)
    doc.checkpoint()
    assert doc.undo()
    assert doc.is_modified


def test_close_and_reopen_reset(pdf_path):
    doc = Document()
    doc.open(pdf_path)
    doc.mark_modified()
    doc.close()
    assert not doc.is_modified
    doc.open(pdf_path)
    assert not doc.is_modified


def test_save_as_rebinds_the_path(pdf_path, tmp_path):
    doc = Document()
    doc.open(pdf_path)
    doc.checkpoint()
    new = tmp_path / "copie.pdf"
    doc.save(new, rebind=True)
    assert doc.path == new and new.exists()
    assert not doc.is_modified


def test_plain_save_to_other_path_keeps_the_path(pdf_path, tmp_path):
    doc = Document()
    doc.open(pdf_path)
    doc.save(tmp_path / "export.pdf")   # sans rebind : copie, le document garde son fichier
    assert doc.path == pdf_path
