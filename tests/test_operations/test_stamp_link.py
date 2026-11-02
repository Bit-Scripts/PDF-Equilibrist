"""Tampon à taille dynamique et zones cliquables (liens)."""
import pymupdf
import pytest

from pdf_equilibrist.operations.annotate import add_link
from pdf_equilibrist.operations.edit import STAMP_PAD, add_stamp_fitted


def _page():
    doc = pymupdf.open()
    return doc, doc.new_page()


def test_stamp_text_fills_its_box_and_scales_with_it():
    _, page = _page()
    big = add_stamp_fitted(page, pymupdf.Rect(50, 50, 350, 130), "APPROUVÉ", (0, 0.5, 0))
    _, page2 = _page()
    small = add_stamp_fitted(page2, pymupdf.Rect(50, 50, 200, 90), "APPROUVÉ", (0, 0.5, 0))
    assert big > small
    x0, y0, x1, y1 = page.get_text("words")[0][:4]
    assert x0 >= 50 + STAMP_PAD - 1 and x1 <= 350 - STAMP_PAD + 1
    assert y0 >= 50 + STAMP_PAD - 1 and y1 <= 130 - STAMP_PAD + 1


def test_stamp_rotation_any_angle():
    _, page = _page()
    add_stamp_fitted(page, pymupdf.Rect(100, 100, 300, 160), "BROUILLON", angle=25.0)
    assert "BROUILLON" in page.get_text()


def test_add_link_uri_and_page():
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    page = doc[0]   # relue après l'ajout des pages, comme le fait l'application
    add_link(page, pymupdf.Rect(10, 10, 110, 30), uri="https://example.org")
    add_link(page, pymupdf.Rect(10, 50, 110, 70), goto_page=1)
    links = pymupdf.open("pdf", doc.tobytes())[0].get_links()   # relecture du PDF écrit
    assert {lk["kind"] for lk in links} == {pymupdf.LINK_URI, pymupdf.LINK_GOTO}
    assert any(lk.get("uri") == "https://example.org" for lk in links)
    assert any(lk.get("page") == 1 for lk in links)


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "file:///etc/passwd", "ftp://x", "abc"])
def test_add_link_refuses_dangerous_schemes(bad):
    _, page = _page()
    with pytest.raises(ValueError):
        add_link(page, pymupdf.Rect(0, 0, 10, 10), uri=bad)


def test_add_link_needs_a_target():
    _, page = _page()
    with pytest.raises(ValueError):
        add_link(page, pymupdf.Rect(0, 0, 10, 10))
