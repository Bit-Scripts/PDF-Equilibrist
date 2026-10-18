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
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor, QKeySequence, QAction, QPixmap, QPolygonF
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


# Disquette et crayon dessinés dans une boîte de 1200 × 1200 (réduite à 18 × 18 par ``_to_box``).
_STROKE = 85.0


def _floppy_paths(full: bool) -> list[QPainterPath]:
    """Contour (coin haut-droit coupé), volet du haut et étiquette du bas. ``full`` = tracé complet ;
    sinon le côté droit, le bas et l'étiquette s'arrêtent avant le crayon."""
    body = QPainterPath()
    body.moveTo(1012, 1012 if full else 520)
    body.lineTo(1012, 392)
    body.lineTo(800, 187)
    body.lineTo(290, 187)
    body.quadTo(187, 187, 187, 290)
    body.lineTo(187, 910)
    body.quadTo(187, 1012, 290, 1012)
    body.lineTo(1012 if full else 570, 1012)
    flap = QPainterPath()
    flap.moveTo(362, 187)
    flap.lineTo(362, 360)
    flap.quadTo(362, 412, 412, 412)
    flap.lineTo(712, 412)
    flap.quadTo(762, 412, 762, 360)
    flap.lineTo(762, 187)
    label = QPainterPath()
    label.moveTo(337, 1012)
    label.lineTo(337, 690)
    label.quadTo(337, 637, 390, 637)
    label.lineTo(812, 637)
    if full:
        label.quadTo(862, 637, 862, 690)
        label.lineTo(862, 1012)
    return [body, flap, label]


_PENCIL = QPolygonF([QPointF(990, 650), QPointF(1100, 760), QPointF(1100, 790), QPointF(800, 1080),
                     QPointF(640, 1125), QPointF(615, 1100), QPointF(665, 940), QPointF(960, 650)])


def _to_box(p: QPainter) -> None:
    p.translate((SIZE - 18) / 2, (SIZE - 18) / 2)
    p.scale(18 / 1200, 18 / 1200)


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
        if self.kind in (UNDO, REDO, OPEN):
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
            p.resetTransform()
            _to_box(p)
            p.setPen(_pen(color, _STROKE))
            for path in _floppy_paths(full=True):
                p.drawPath(path)
        else:                          # SAVE_AS : disquette + crayon plein, séparés par un halo
            dpr = self.devicePixelRatioF()
            layer = QPixmap(int(SIZE * dpr), int(SIZE * dpr))
            layer.setDevicePixelRatio(dpr)
            layer.fill(Qt.GlobalColor.transparent)
            lp = QPainter(layer)
            lp.setRenderHint(QPainter.RenderHint.Antialiasing)
            _to_box(lp)
            lp.setPen(_pen(color, _STROKE))
            lp.setBrush(Qt.BrushStyle.NoBrush)
            for path in _floppy_paths(full=False):
                lp.drawPath(path)
            lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)   # halo autour du crayon
            lp.setPen(_pen(color, 190))
            lp.setBrush(color)
            lp.drawPolygon(_PENCIL)
            lp.end()
            p.resetTransform()
            p.drawPixmap(0, 0, layer)
            _to_box(p)
            p.setPen(_pen(color, 60))
            p.setBrush(color)
            p.drawPolygon(_PENCIL)
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
