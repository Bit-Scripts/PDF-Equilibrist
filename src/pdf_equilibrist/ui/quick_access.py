"""
ui/quick_access.py — Barre d'accès rapide de la barre de titre
==============================================================
Cinq boutons (Annuler, Rétablir, Ouvrir, Enregistrer, Enregistrer sous) placés après le nom de
l'application. Chaque bouton est le miroir d'une ``QAction`` du menu de ``MainWindow`` : il la
déclenche au clic, et reprend son état activé/désactivé, son texte et son raccourci. Les
actions agissent donc sur le document de l'onglet actif, comme le menu et les raccourcis.

Les icônes sont dessinées au ``QPainter`` (pas de police ni de fichier image) : elles suivent
le thème clair/sombre via ``theme.qcolor``.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor, QKeySequence, QAction
from PyQt6.QtCore import Qt, QPointF, QRectF

from pdf_equilibrist import theme

UNDO, REDO, OPEN, SAVE, SAVE_AS = "undo", "redo", "open", "save", "save_as"
ORDER = (UNDO, REDO, OPEN, SAVE, SAVE_AS)
SIZE = 26


def _pen(color: QColor, width: float = 1.6) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _arrow(p: QPainter) -> None:
    """Flèche arrondie vers la gauche (Annuler) dans une boîte de 18 × 18."""
    p.drawArc(QRectF(4.5, 4.5, 11, 9), 0, 180 * 16)           # demi-cercle supérieur
    p.drawLine(QPointF(4.5, 9), QPointF(4.5, 12))              # descente sur la pointe
    p.drawLine(QPointF(4.5, 12), QPointF(1.8, 9.4))            # branches de la pointe
    p.drawLine(QPointF(4.5, 12), QPointF(7.2, 9.4))


def _folder(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(2, 14.5)
    path.lineTo(2, 4)
    path.lineTo(6.8, 4)
    path.lineTo(8.4, 6)
    path.lineTo(15, 6)
    path.lineTo(15, 14.5)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(2, 8.5), QPointF(15, 8.5))


def _floppy(p: QPainter, dx: float = 0, dy: float = 0, s: float = 1.0) -> None:
    def r(x, y, w, h):
        return QRectF(dx + x * s, dy + y * s, w * s, h * s)
    p.drawRoundedRect(r(2.5, 2.5, 13, 13), 1.6 * s, 1.6 * s)
    p.drawRect(r(5.5, 2.5, 7, 4))      # volet métallique
    p.drawRect(r(5.5, 10, 7, 5.5))     # étiquette


def _pencil(p: QPainter) -> None:
    p.drawLine(QPointF(9.5, 16.5), QPointF(16.5, 9.5))         # corps
    p.drawLine(QPointF(9.5, 16.5), QPointF(8.5, 18))           # pointe
    p.drawLine(QPointF(14.8, 7.8), QPointF(18, 11))            # gomme


class QuickButton(QPushButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(SIZE, SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # ne vole pas le focus clavier au viewer

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()
        if enabled and (self.underMouse() or self.isDown()):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.qcolor("#3A3A3A" if self.isDown() else "#2E2E2E"))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 5, 5)
        color = theme.qcolor("#D8D8D8" if enabled else "#555555")
        p.setPen(_pen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.translate((SIZE - 18) / 2, (SIZE - 18) / 2)
        if self.kind == UNDO:
            _arrow(p)
        elif self.kind == REDO:
            p.translate(18, 0)
            p.scale(-1, 1)             # image miroir de la flèche d'annulation
            _arrow(p)
        elif self.kind == OPEN:
            _folder(p)
        elif self.kind == SAVE:
            _floppy(p)
        else:                          # SAVE_AS : disquette réduite + crayon
            _floppy(p, -1.5, -1.5, 0.85)
            p.setPen(_pen(color, 1.4))
            _pencil(p)
        p.end()


class QuickAccessBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 6, 0)
        layout.setSpacing(2)
        self._buttons: dict[str, QuickButton] = {}
        for kind in ORDER:
            btn = QuickButton(kind)
            self._buttons[kind] = btn
            layout.addWidget(btn)

    def bind(self, kind: str, action: QAction) -> None:
        """Relie le bouton ``kind`` à ``action`` : clic → déclenche l'action ; l'état activé,
        le texte et le raccourci de l'action sont répercutés sur le bouton."""
        btn = self._buttons[kind]
        btn.clicked.connect(action.trigger)

        def sync():
            btn.setEnabled(action.isEnabled())
            keys = action.shortcuts()
            hint = keys[0].toString(QKeySequence.SequenceFormat.NativeText) if keys else ""
            label = action.text().replace("&", "").rstrip("…")
            btn.setToolTip(f"{label} ({hint})" if hint else label)
            btn.update()

        action.changed.connect(sync)
        sync()
