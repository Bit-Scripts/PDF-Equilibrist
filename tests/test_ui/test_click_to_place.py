"""Pose d'un texte par clic sur le PDF (« Cliquez sur la page pour poser… »)."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")
import pymupdf  # noqa: E402
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PyQt6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from pdf_equilibrist.core.document import Document  # noqa: E402
from pdf_equilibrist.ui.floating_item import FloatingItem  # noqa: E402
from pdf_equilibrist.ui.viewer import PdfViewer  # noqa: E402

DATA = {"type": "text", "text": "Salut", "fontsize": 14, "color": (0, 0, 0)}


@pytest.fixture
def viewer(tmp_path):
    app = QApplication.instance() or QApplication([])
    pdf = pymupdf.open()
    pdf.new_page()
    pdf.new_page()
    path = tmp_path / "two.pdf"
    pdf.save(path)
    doc = Document()
    doc.open(str(path))
    v = PdfViewer(doc)
    v.resize(900, 700)
    v.show()
    app.processEvents()
    yield v
    v.close()


def _click(widget, x, y):
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x, y),
                     widget.mapToGlobal(QPointF(x, y)), Qt.MouseButton.LeftButton,
                     Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, ev)


def test_item_is_placed_where_the_user_clicks(viewer):
    viewer.show_floating_item(DATA.copy(), 0, lambda *a: None, None, click_to_place=True)
    assert viewer._placing is not None
    assert "Cliquez sur la page" in viewer._place_bar.findChild(QLabel).text()
    assert not viewer._page_widgets[0].findChildren(FloatingItem)   # rien avant le clic

    page = viewer._page_widgets[1]   # on clique sur la 2e page, pas la « courante »
    _click(page, 200, 300)
    assert viewer._placing is None and viewer._place_bar is None
    items = page.findChildren(FloatingItem)
    assert len(items) == 1 and not viewer._page_widgets[0].findChildren(FloatingItem)
    r = items[0]._item_rect()
    center = items[0].pos() + QPoint(int(r.center().x()), int(r.center().y()))
    assert (center.x(), center.y()) == (200, 300)


def test_escape_cancels_and_calls_back(viewer):
    called = []
    viewer.show_floating_item(DATA.copy(), 0, lambda *a: None,
                              lambda: called.append("cancel"), click_to_place=True)
    QApplication.sendEvent(viewer, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                              Qt.KeyboardModifier.NoModifier))
    assert called == ["cancel"] and viewer._placing is None and viewer._place_bar is None
