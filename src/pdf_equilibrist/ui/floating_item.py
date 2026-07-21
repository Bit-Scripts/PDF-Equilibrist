"""
ui/floating_item.py — Élément flottant interactif sur une page PDF
===================================================================
Ce module fournit ``FloatingItem``, un widget superposé sur une page PDF
permettant à l'utilisateur de placer visuellement un élément (texte, image,
tampon) avant de le graver définitivement dans le document.

Cycle de vie
------------
1. ``PdfViewer.show_floating_item(data, page_index, on_commit, on_cancel)``
   crée un ``FloatingItem`` en tant qu'enfant direct du widget de page.
2. L'utilisateur interagit : déplace, redimensionne, pivote l'élément.
3. Clic sur "✔ Valider" → ``committed(result_dict)`` est émis.
   ``result_dict`` contient ``pdf_rect`` en coordonnées PDF (points).
4. Le tab appelant grave l'élément dans ``fitz.Document`` et émet ``changed``.
   Ou : clic sur "✘" → ``cancelled()`` est émis, le widget est détruit.

Système de coordonnées
-----------------------
Le ``FloatingItem`` fonctionne en **coordonnées écran** (pixels) pendant
l'interaction. À la validation (``_commit()``), les coordonnées sont converties
en **coordonnées PDF** (points) en divisant par le facteur de zoom courant.

Cette conversion est fondamentale : un point PDF = 1/72 de pouce, indépendant
de la résolution d'affichage. La position gravée dans le PDF est donc toujours
correcte quelle que soit la résolution de l'écran ou le zoom d'affichage.

Dessin des poignées
--------------------
Toutes les poignées sont dessinées dans ``paintEvent`` via ``QPainter`` :
- 8 poignées de redimensionnement (cercles verts) aux coins et milieux des côtés
- 1 poignée de rotation (cercle vert plein) reliée au bord supérieur par une ligne
- La bordure tiretée verte délimite la zone de l'élément

La rotation est appliquée via ``QPainter.rotate()`` autour du centre de l'élément.
"""
from __future__ import annotations
import math
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPixmap,
                          QFont)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPointF, QRectF, QSizeF

ACCENT   = "#6BBF4E"
HANDLE_R = 6     # rayon des poignées de redimensionnement (px)
ROT_DIST = 28    # distance de la poignée de rotation au-dessus du bord haut (px)
MIN_SIZE = 40    # taille minimale de l'élément lors du redimensionnement (px)


class FloatingItem(QWidget):
    """
    Widget interactif superposé sur une page PDF pour le placement visuel.

    Supporte trois types d'éléments via le dict ``data`` :
    - ``{'type': 'text',  'text': str, 'fontsize': int, 'color': tuple}``
    - ``{'type': 'image', 'path': str}``
    - ``{'type': 'stamp', 'text': str, 'color': tuple}``

    Signals
    -------
    committed : pyqtSignal(dict)
        Émis quand l'utilisateur clique "✔ Valider".
        Le dict résultat contient tous les champs de ``data`` plus :
        - ``pdf_rect`` : tuple (x0, y0, x1, y1) en coordonnées PDF (points)
        - ``angle``    : float, rotation en degrés

    cancelled : pyqtSignal()
        Émis quand l'utilisateur clique "✘ Annuler" ou ferme l'élément.

    Attributes
    ----------
    _mode : int
        Mode d'interaction courant (NONE, MOVE, RESIZE, ROTATE).
    _angle : float
        Angle de rotation courant en degrés.
    _item_size : QSizeF
        Taille courante de l'élément en pixels écran.
    """

    committed = pyqtSignal(dict)
    cancelled = pyqtSignal()

    # Constantes de mode d'interaction (équivalent d'un enum)
    _MODE_NONE   = 0   # aucune interaction
    _MODE_MOVE   = 1   # déplacement de l'élément
    _MODE_RESIZE = 2   # redimensionnement via poignée
    _MODE_ROTATE = 3   # rotation via poignée verte

    _MODE_NONE   = 0
    _MODE_MOVE   = 1
    _MODE_RESIZE = 2
    _MODE_ROTATE = 3

    def __init__(self, data: dict, zoom: float, parent: QWidget):
        super().__init__(parent)
        self._data    = data
        self._zoom    = zoom
        self._angle   = 0.0          # degrés
        self._mode    = self._MODE_NONE
        self._drag_start  = QPointF()
        self._item_origin = QPoint()  # position avant drag
        self._item_size   = QSizeF(200, 60)
        self._resize_anchor = QPointF()

        # Pré-charger pixmap si image
        self._pixmap: QPixmap | None = None
        if data.get("type") == "image":
            self._pixmap = QPixmap(data["path"])

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Boutons Valider / Annuler
        self._toolbar = QWidget(self)
        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(2, 2, 2, 2)
        tb_layout.setSpacing(4)

        btn_ok = QPushButton("✔  Valider")
        btn_ok.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:#1E1E1E; font-weight:bold;"
            f" border:none; border-radius:4px; padding:3px 10px; font-size:11px; }}"
            f"QPushButton:hover {{ background:#7ED45F; }}"
        )
        btn_cancel = QPushButton("✘")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#3A3A3A; color:#F0F0F0; border:none;"
            " border-radius:4px; padding:3px 8px; font-size:11px; }"
            "QPushButton:hover { background:#555; }"
        )
        btn_ok.clicked.connect(self._commit)
        btn_cancel.clicked.connect(self.cancelled)
        tb_layout.addWidget(btn_ok)
        tb_layout.addWidget(btn_cancel)
        self._toolbar.adjustSize()

        # Taille initiale selon le contenu
        if self._pixmap and not self._pixmap.isNull():
            pw = min(self._pixmap.width(),  int(300 * zoom))
            ph = min(self._pixmap.height(), int(200 * zoom))
            self._item_size = QSizeF(pw, ph)
        elif data.get("type") == "text":
            fs = data.get("fontsize", 12)
            w  = max(120, len(data.get("text", "")) * int(fs * zoom * 0.7))
            self._item_size = QSizeF(w, fs * zoom * 2)
        elif data.get("type") == "stamp":
            self._item_size = QSizeF(200, 44)

        self._place_at_center()

    # ── Placement initial ────────────────────────────────────────────────────

    def _place_at_center(self):
        if self.parent():
            pw, ph = self.parent().width(), self.parent().height()
            x = int(pw / 2 - self._item_size.width()  / 2)
            y = int(ph / 2 - self._item_size.height() / 2)
            self.move(x, y)
        self._update_size()

    def _update_size(self):
        margin = HANDLE_R + 2
        extra  = ROT_DIST + HANDLE_R
        w = int(self._item_size.width())  + margin * 2
        h = int(self._item_size.height()) + margin * 2 + extra
        self.resize(w, h + 32)   # +32 pour la toolbar
        self._toolbar.move(0, h + 2)

    # ── Géométrie interne ────────────────────────────────────────────────────

    def _item_rect(self) -> QRectF:
        m  = HANDLE_R + 2
        ex = ROT_DIST + HANDLE_R
        return QRectF(m, m + ex,
                      self._item_size.width(),
                      self._item_size.height())

    def _rot_handle_center(self) -> QPointF:
        r  = self._item_rect()
        cx = r.x() + r.width() / 2
        return QPointF(cx, r.y() - ROT_DIST)

    def _handles(self) -> list[QPointF]:
        r = self._item_rect()
        return [
            r.topLeft(), r.topRight(),
            r.bottomLeft(), r.bottomRight(),
            QPointF(r.center().x(), r.top()),
            QPointF(r.center().x(), r.bottom()),
            QPointF(r.left(),  r.center().y()),
            QPointF(r.right(), r.center().y()),
        ]

    def _hit_handle(self, pos: QPointF) -> int:
        for i, h in enumerate(self._handles()):
            if (pos - h).manhattanLength() <= HANDLE_R + 3:
                return i
        return -1

    def _hit_rot(self, pos: QPointF) -> bool:
        rc = self._rot_handle_center()
        return (pos - rc).manhattanLength() <= HANDLE_R + 4

    def _hit_item(self, pos: QPointF) -> bool:
        return self._item_rect().contains(pos)

    # ── Mouse ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = QPointF(event.position())
        if self._hit_rot(pos):
            self._mode = self._MODE_ROTATE
            self._drag_start = pos
        elif self._hit_handle(pos) >= 0:
            self._mode = self._MODE_RESIZE
            self._resize_handle_idx = self._hit_handle(pos)
            self._drag_start   = pos
            self._item_origin  = QPoint(self.x(), self.y())
            self._size_at_drag = QSizeF(self._item_size)
        elif self._hit_item(pos):
            self._mode = self._MODE_MOVE
            self._drag_start  = event.globalPosition()
            self._item_origin = self.pos()

    def mouseMoveEvent(self, event):
        pos = QPointF(event.position())

        if self._mode == self._MODE_MOVE:
            delta = event.globalPosition() - self._drag_start
            new_pos = self._item_origin + QPoint(int(delta.x()), int(delta.y()))
            if self.parent():
                new_pos.setX(max(0, min(new_pos.x(),
                                        self.parent().width() - self.width())))
                new_pos.setY(max(0, min(new_pos.y(),
                                        self.parent().height() - self.height())))
            self.move(new_pos)

        elif self._mode == self._MODE_RESIZE:
            delta = pos - self._drag_start
            h_idx = self._resize_handle_idx
            new_w = self._size_at_drag.width()
            new_h = self._size_at_drag.height()
            if h_idx in (1, 3, 6):  new_w = max(MIN_SIZE, new_w + delta.x())
            if h_idx in (0, 2, 5):  new_w = max(MIN_SIZE, new_w - delta.x())
            if h_idx in (2, 3, 6):  new_h = max(MIN_SIZE, new_h + delta.y())
            if h_idx in (0, 1, 7):  new_h = max(MIN_SIZE, new_h - delta.y())
            if h_idx in (4,):       new_h = max(MIN_SIZE, new_h + delta.y())
            if h_idx in (5,):       new_h = max(MIN_SIZE, new_h - delta.y())
            self._item_size = QSizeF(new_w, new_h)
            self._update_size()
            self.update()

        elif self._mode == self._MODE_ROTATE:
            r   = self._item_rect()
            cx  = r.x() + r.width()  / 2
            cy  = r.y() + r.height() / 2
            dx  = pos.x() - cx
            dy  = pos.y() - cy
            self._angle = math.degrees(math.atan2(dy, dx)) + 90
            self.update()

        else:
            # Mise à jour du curseur
            if self._hit_rot(pos):
                self.setCursor(Qt.CursorShape.CrossCursor)
            elif self._hit_handle(pos) >= 0:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif self._hit_item(pos):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._mode = self._MODE_NONE

    # ── Dessin ───────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self._item_rect()
        cx = r.x() + r.width()  / 2
        cy = r.y() + r.height() / 2

        # Rotation autour du centre
        p.translate(cx, cy)
        p.rotate(self._angle)
        p.translate(-cx, -cy)

        # Contenu
        self._draw_content(p, r)

        # Bordure tiretée
        p.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)

        # Poignées de resize
        p.setPen(QPen(QColor(ACCENT), 1))
        p.setBrush(QBrush(QColor("#1E1E1E")))
        for h in self._handles():
            p.drawEllipse(h, HANDLE_R, HANDLE_R)

        # Ligne + poignée de rotation
        rc = self._rot_handle_center()
        p.setPen(QPen(QColor(ACCENT), 1))
        p.drawLine(QPointF(cx, r.top()), rc)
        p.setBrush(QBrush(QColor(ACCENT)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rc, HANDLE_R, HANDLE_R)

    def _draw_content(self, p: QPainter, r: QRectF):
        dtype = self._data.get("type")

        if dtype == "image" and self._pixmap and not self._pixmap.isNull():
            p.drawPixmap(r.toRect(),
                         self._pixmap.scaled(r.size().toSize(),
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

        elif dtype == "stamp":
            color = self._data.get("color", (0, 0.5, 0))
            r_val, g_val, b_val = (int(c * 255) for c in color)
            qc = QColor(r_val, g_val, b_val)
            p.setPen(QPen(qc, 2))
            p.setBrush(QColor(r_val, g_val, b_val, 20))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QPen(qc))
            font = QFont("Segoe UI", 14, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter,
                       self._data.get("text", "TAMPON"))

        elif dtype == "text":
            p.fillRect(r, QColor(255, 255, 200, 180))
            p.setPen(QPen(QColor("#333333")))
            color = self._data.get("color", (0, 0, 0))
            r_val, g_val, b_val = (int(c * 255) for c in color)
            p.setPen(QPen(QColor(r_val, g_val, b_val)))
            fs = max(8, int(self._data.get("fontsize", 12) * self._zoom))
            p.setFont(QFont("Segoe UI", fs))
            p.drawText(r.adjusted(4, 4, -4, -4),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self._data.get("text", ""))

    # ── Validation ───────────────────────────────────────────────────────────

    def _commit(self):
        """Calcule la position/taille en coordonnées PDF (points) et émet."""
        r = self._item_rect()
        # Coordonnées dans le parent (viewer page widget)
        px = self.x() + r.x()
        py = self.y() + r.y()
        pw = r.width()
        ph = r.height()
        # Convertir en points PDF (diviser par zoom)
        z = max(self._zoom, 0.01)
        self.committed.emit({
            **self._data,
            "pdf_rect": (px / z, py / z, (px + pw) / z, (py + ph) / z),
            "angle":    self._angle,
        })
