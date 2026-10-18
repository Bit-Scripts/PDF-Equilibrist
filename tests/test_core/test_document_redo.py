"""Document : Annuler / Rétablir."""
import pymupdf
import pytest

from pdf_equilibrist.core.document import Document


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "a.pdf"
    d = pymupdf.open()
    d.new_page()
    d.save(path)
    d.close()
    document = Document()
    document.open(path)
    return document


def _add_page(document):
    document.checkpoint()
    document.fitz_doc.new_page()


def test_nothing_to_redo_initially(doc):
    assert not doc.can_redo
    assert not doc.redo()


def test_undo_then_redo_restores_the_change(doc):
    _add_page(doc)
    assert len(doc.fitz_doc) == 2
    assert doc.undo()
    assert len(doc.fitz_doc) == 1 and doc.can_redo
    assert doc.redo()
    assert len(doc.fitz_doc) == 2
    assert not doc.can_redo and doc.can_undo   # on peut ré-annuler


def test_new_change_clears_redo(doc):
    _add_page(doc)
    doc.undo()
    assert doc.can_redo
    _add_page(doc)           # nouvelle modification : l'ancien futur n'a plus de sens
    assert not doc.can_redo


def test_several_steps(doc):
    _add_page(doc)
    _add_page(doc)
    assert len(doc.fitz_doc) == 3
    doc.undo()
    doc.undo()
    assert len(doc.fitz_doc) == 1
    doc.redo()
    doc.redo()
    assert len(doc.fitz_doc) == 3
    assert not doc.redo()


def test_close_clears_stacks(doc):
    _add_page(doc)
    doc.undo()
    doc.close()
    assert not doc.can_undo and not doc.can_redo
