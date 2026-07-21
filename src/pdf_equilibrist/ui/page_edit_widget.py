"""Widget page en mode édition : survol + clic pour éditer bloc par bloc."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QTextEdit
from PyQt6.QtGui import (QPixmap, QPainter, QColor, QFont, QPen,
                          QTextOption, QKeyEvent)
from PyQt6.QtCore import Qt, QRect, pyqtSignal
import fitz
from pdf_equilibrist.operations.edit import TextBlock, apply_text_edits

ACCENT       = "#6BBF4E"
HOVER_FILL   = QColor(107, 191, 78, 35)
HOVER_BORDER = QColor(ACCENT)
EDIT_BG      = "rgba(255, 255, 200, 230)"


class _BlockEditor(QTextEdit):
    """QTextEdit positionné sur un bloc, avec Échap = annuler, Entrée = valider."""

    confirmed = pyqtSignal(str)   # texte validé
    cancelled = pyqtSignal()

    def __init__(self, block: TextBlock, zoom: float, parent: QWidget):
        super().__init__(parent)
        self.block = block
        zoom = max(zoom, 0.1)

        r, g, b = (int(c * 255) for c in block.color)
        fs = max(7, int(block.fontsize * zoom))

        self.setPlainText(block.text)
        self.setFont(QFont("Segoe UI", fs))
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {EDIT_BG};
                border: 2px solid {ACCENT};
                border-radius: 3px;
                color: rgb({r},{g},{b});
                font-size: {fs}px;
                padding: 1px 3px;
            }}
        """)

        # Positionnement
        ox, oy = parent._page_origin
        x = int(block.rect.x0 * zoom) - ox
        y = int(block.rect.y0 * zoom) - oy
        w = max(int((block.rect.x1 - block.rect.x0) * zoom) + 10, 60)
        h = max(int((block.rect.y1 - block.rect.y0) * zoom) + 10, fs + 12)
        self.setGeometry(x, y, w, h)
        self.raise_()
        self.show()
        self.setFocus()
        self.selectAll()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) \
                and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.confirmed.emit(self.toPlainText())
        else:
            super().keyPressEvent(event)


class PageEditWidget(QWidget):
    """
    Affiche une page PDF en mode édition :
    - survol → surligne le bloc sous le curseur
    - clic   → ouvre un _BlockEditor sur ce bloc uniquement
    - Entrée / bouton ✔ → valide ce bloc (redact + réinsert)
    - Échap  / clic ailleurs → annule l'édition en cours
    """

    page_changed = pyqtSignal()   # émis quand un bloc est modifié

    def __init__(self, pixmap: QPixmap, blocks: list[TextBlock],
                 zoom: float, doc: fitz.Document, page_index: int,
                 page_origin: tuple[int, int] = (0, 0),
                 parent=None):
        super().__init__(parent)
        self._pixmap   = pixmap
        self._blocks   = blocks          # liste complète des blocs de la page
        self._zoom     = zoom
        self._doc      = doc
        self._page_idx = page_index
        self._page_origin = page_origin  # offset du coin supérieur gauche de la page dans le parent
        self._hover: TextBlock | None = None
        self._editor:  _BlockEditor | None = None

        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)

    # ── coordonnées ───────────────────────────────────────────────────────────

    def _block_at(self, qx: int, qy: int) -> TextBlock | None:
        ox, oy = self._page_origin
        px = (qx + ox) / self._zoom
        py = (qy + oy) / self._zoom
        pt = fitz.Point(px, py)
        for block in self._blocks:
            if block.rect.contains(pt):
                return block
        return None

    # ── événements souris ─────────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        if self._editor:
            return
        block = self._block_at(event.pos().x(), event.pos().y())
        if block is not self._hover:
            self._hover = block
            self.update()
            self.setCursor(Qt.CursorShape.IBeamCursor if block
                           else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # clic en dehors de l'éditeur actif → valide
        if self._editor:
            self._confirm(self._editor.toPlainText())
            return
        block = self._block_at(event.pos().x(), event.pos().y())
        if block:
            self._open_editor(block)

    # ── éditeur ───────────────────────────────────────────────────────────────

    def _open_editor(self, block: TextBlock):
        self._hover = None
        ed = _BlockEditor(block, self._zoom, self)
        ed.confirmed.connect(self._confirm)
        ed.cancelled.connect(self._cancel)
        self._editor = ed
        self.update()

    def _confirm(self, new_text: str):
        if self._editor is None:
            return
        block = self._editor.block
        if new_text != block.text:
            apply_text_edits(
                self._doc, self._page_idx,
                self._blocks,
                {block.block_id: new_text},
            )
            # met à jour le texte en cache pour éviter double-redaction
            block.text = new_text
            # re-render la page
            pix = self._doc[self._page_idx].get_pixmap(
                matrix=fitz.Matrix(self._zoom, self._zoom), alpha=False
            )
            img_data = pix.samples
            from PyQt6.QtGui import QImage
            img = QImage(img_data, pix.width, pix.height, pix.stride,
                         QImage.Format.Format_RGB888)
            self._pixmap = QPixmap.fromImage(img)
            self.setFixedSize(self._pixmap.size())
            self.page_changed.emit()

        self._close_editor()

    def _cancel(self):
        self._close_editor()

    def _close_editor(self):
        if self._editor:
            self._editor.deleteLater()
            self._editor = None
        self.update()

    # ── rendu ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)

        if self._editor:
            return   # ne pas dessiner le hover pendant l'édition

        if self._hover:
            r = self._hover.rect
            ox, oy = self._page_origin
            sx = int(r.x0 * self._zoom) - ox
            sy = int(r.y0 * self._zoom) - oy
            sw = max(int((r.x1 - r.x0) * self._zoom), 4)
            sh = max(int((r.y1 - r.y0) * self._zoom), 4)
            screen_rect = QRect(sx, sy, sw, sh)
            p.fillRect(screen_rect, HOVER_FILL)
            p.setPen(QPen(HOVER_BORDER, 1, Qt.PenStyle.DotLine))
            p.drawRect(screen_rect)

    def get_pixmap(self) -> QPixmap:
        return self._pixmap
