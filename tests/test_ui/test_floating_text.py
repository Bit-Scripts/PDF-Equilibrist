"""FloatingItem texte : taille dynamique et barre de mise en forme."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import QSizeF  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from pdf_equilibrist.ui.floating_item import FloatingItem  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def item(app):
    page = QWidget()
    page.resize(800, 1000)
    data = {"type": "text", "text": "Bonjour le monde", "fontsize": 20,
            "color": (1, 0, 0), "family": "Helvetica", "bold": False,
            "italic": False, "fontname": "helv"}
    it = FloatingItem(data, 1.5, page)
    it._page = page  # garde le parent vivant
    return it


def test_resizing_box_rescales_font(item):
    base = item._data["fontsize"]
    item._item_size = QSizeF(item._item_size.width() / 2, item._item_size.height() / 2)
    item._refit_text()
    assert item._data["fontsize"] == pytest.approx(base / 2, rel=0.02)
    item._item_size = QSizeF(item._item_size.width() * 2, item._item_size.height() * 2)
    item._refit_text()
    assert item._data["fontsize"] == pytest.approx(base, rel=0.02)


def test_narrower_box_is_limited_by_width(item):
    base = item._data["fontsize"]
    item._item_size = QSizeF(item._item_size.width() / 4, item._item_size.height())
    item._refit_text()
    assert item._data["fontsize"] == pytest.approx(base / 4, rel=0.02)


def test_style_controls_still_editable_before_commit(item):
    item._bt_bold.setChecked(True)
    item._bt_italic.setChecked(True)
    item._cb_family.setCurrentText("Times")
    assert item._data["fontname"] == "tibi"
    item._sp_size.setValue(30.0)
    assert item._data["fontsize"] == 30.0
    got = []
    item.committed.connect(got.append)
    item._commit()
    assert got[0]["fontname"] == "tibi" and got[0]["fontsize"] == 30.0
