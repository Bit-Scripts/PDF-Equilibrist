"""FloatingItem image : proportions conservées, pose par clic."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")
import pymupdf  # noqa: E402
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QImage, QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from pdf_equilibrist.core.document import Document  # noqa: E402
from pdf_equilibrist.ui.floating_item import FloatingItem  # noqa: E402
from pdf_equilibrist.ui.viewer import PdfViewer  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def png(tmp_path):
    img = QImage(800, 400, QImage.Format.Format_RGB32)   # ratio 2:1
    img.fill(QColor("red"))
    path = tmp_path / "wide.png"
    img.save(str(path))
    return str(path)


def _drag(item, handle_idx, dx, dy):
    item._mode = item._MODE_RESIZE
    item._resize_handle_idx = handle_idx
    item._drag_start = QPointF(0, 0)
    item._size_at_drag = item._item_size
    from PyQt6.QtGui import QMouseEvent as ME
    ev = ME(QEvent.Type.MouseMove, QPointF(dx, dy), QPointF(dx, dy),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
    item.mouseMoveEvent(ev)
    item._mode = item._MODE_NONE


def test_initial_size_keeps_ratio_and_fits(app, png):
    page = QWidget()
    page.resize(800, 1000)
    it = FloatingItem({"type": "image", "path": png}, 1.0, page)
    w, h = it._item_size.width(), it._item_size.height()
    assert w / h == pytest.approx(2.0, rel=1e-3)
    assert w <= 300 and h <= 300


@pytest.mark.parametrize("idx,dx,dy", [(3, 80, 5), (3, 5, 60), (7, -50, 0), (1, 40, -10)])
def test_resize_keeps_ratio(app, png, idx, dx, dy):
    page = QWidget()
    page.resize(800, 1000)
    it = FloatingItem({"type": "image", "path": png}, 1.0, page)
    _drag(it, idx, dx, dy)
    assert it._item_size.width() / it._item_size.height() == pytest.approx(2.0, rel=1e-3)


def test_click_to_place_image(app, png, tmp_path):
    pdf = pymupdf.open()
    pdf.new_page()
    path = tmp_path / "p.pdf"
    pdf.save(path)
    doc = Document()
    doc.open(str(path))
    v = PdfViewer(doc)
    v.resize(900, 700)
    v.show()
    app.processEvents()
    v.show_floating_item({"type": "image", "path": png}, 0, lambda *a: None, None,
                         click_to_place=True)
    assert "l'image" in v._place_bar.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)[0].text()
    page = v._page_widgets[0]
    app.sendEvent(page, QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(250, 300),
                                    page.mapToGlobal(QPointF(250, 300)),
                                    Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                    Qt.KeyboardModifier.NoModifier))
    item = page.findChildren(FloatingItem)[0]
    r = item._item_rect()
    c = item.pos() + QPoint(int(r.center().x()), int(r.center().y()))
    assert (c.x(), c.y()) == (250, 300)
    v.close()


def test_stamp_font_follows_box(app):
    from PyQt6.QtCore import QSizeF
    page = QWidget()
    page.resize(800, 1000)
    it = FloatingItem({"type": "stamp", "text": "APPROUVÉ", "color": (0, 0.5, 0)}, 1.0, page)
    base = it._data["fontsize"]
    it._item_size = QSizeF(it._item_size.width() * 2, it._item_size.height() * 2)
    it._refit_text()
    assert it._data["fontsize"] > base * 1.7


def test_link_item_has_a_zone_and_commits_rect(app):
    page = QWidget()
    page.resize(800, 1000)
    it = FloatingItem({"type": "link", "uri": "https://example.org"}, 1.0, page)
    got = []
    it.committed.connect(got.append)
    it._commit()
    x0, y0, x1, y1 = got[0]["pdf_rect"]
    assert x1 > x0 and y1 > y0 and got[0]["uri"] == "https://example.org"
