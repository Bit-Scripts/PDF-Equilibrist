"""Taille de police dynamique : le texte remplit la boîte (largeur ou hauteur)."""
import pymupdf
import pytest

from pdf_equilibrist.operations.edit import (
    add_text_fitted, fit_fontsize, text_natural_size,
)


@pytest.mark.parametrize("fontname", ["helv", "hebo", "tiit", "cour"])
def test_text_fits_inside_box(fontname):
    for box in [(200, 40), (60, 100), (400, 20), (30, 30)]:
        size = fit_fontsize("Bonjour le monde", fontname, *box)
        w, h = text_natural_size("Bonjour le monde", fontname, size)
        assert w <= box[0] + 1e-6 and h <= box[1] + 1e-6
        # la contrainte la plus forte est atteinte (largeur OU hauteur)
        assert abs(w - box[0]) < 1e-6 or abs(h - box[1]) < 1e-6


def test_shrinking_box_shrinks_font_and_back():
    big = fit_fontsize("Texte", "helv", 300, 100)
    small = fit_fontsize("Texte", "helv", 150, 50)
    assert small == pytest.approx(big / 2)
    assert fit_fontsize("Texte", "helv", 300, 100) == pytest.approx(big)


def test_narrow_box_is_limited_by_width_wide_box_by_height():
    narrow = fit_fontsize("Un texte assez long", "helv", 50, 200)
    wide = fit_fontsize("Un texte assez long", "helv", 500, 20)
    assert narrow < 20
    assert wide == pytest.approx(20 / (1.075 + 0.299), rel=1e-2)


def test_add_text_fitted_stays_in_rect_and_returns_size():
    doc = pymupdf.open()
    page = doc.new_page()
    rect = pymupdf.Rect(100, 100, 300, 140)
    size = add_text_fitted(page, rect, "Hello world", "helv", (1, 0, 0))
    x0, y0, x1, y1 = page.get_text("words")[0][:4]
    xe, ye = page.get_text("words")[-1][2:4]
    assert size > 0
    assert x0 >= rect.x0 - 1 and xe <= rect.x1 + 1
    assert y0 >= rect.y0 - 1 and ye <= rect.y1 + 1


def test_add_text_fitted_rotation_arbitrary_angle():
    doc = pymupdf.open()
    page = doc.new_page()
    add_text_fitted(page, pymupdf.Rect(100, 100, 300, 140), "Hello", "helv", angle=33.0)
    assert "Hello" in page.get_text()
