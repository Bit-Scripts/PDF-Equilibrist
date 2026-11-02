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
4. Le tab appelant grave l'élément dans ``pymupdf.Document`` et émet ``changed``.
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
from PyQt6.QtWidgets import (QWidget, QPushButton, QHBoxLayout, QComboBox,
                             QDoubleSpinBox, QColorDialog)
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPixmap,
                          QFont, QFontMetricsF)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPointF, QRectF, QSizeF

from pdf_equilibrist.operations.edit import (
    STAMP_PAD, fit_fontsize, text_line_metrics, text_natural_size,
)
from pdf_equilibrist.ui.dialogs import PDF_FONTS, pdf_fontname

ACCENT   = "#6BBF4E"
HANDLE_R = 6     # rayon des poignées de redimensionnement (px)
ROT_DIST = 28    # distance de la poignée de rotation au-dessus du bord haut (px)
MIN_SIZE = 40    # taille minimale de l'élément lors du redimensionnement (px)
BAR_H    = 32    # hauteur d'une barre d'outils sous l'élément (px)

# Familles Qt de repli pour l'aperçu (la gravure utilise les polices PDF standard)
_QT_FAMILIES = {
    "Helvetica": ["Helvetica", "Arial", "Liberation Sans"],
    "Times":     ["Times New Roman", "Times", "Liberation Serif"],
    "Courier":   ["Courier New", "Courier", "Liberation Mono"],
}


class FloatingItem(QWidget):
    """
    Widget interactif superposé sur une page PDF pour le placement visuel.

    Supporte quatre types d'éléments via le dict ``data`` :
    - ``{'type': 'text',  'text': str, 'fontsize': int, 'color': tuple,
      'fontname': str (base 14), 'family': str, 'bold': bool, 'italic': bool}``
    - ``{'type': 'image', 'path': str}``
    - ``{'type': 'stamp', 'text': str, 'color': tuple}`` (texte ajusté à la boîte)
    - ``{'type': 'link', 'uri': str}`` ou ``{'type': 'link', 'goto_page': int}``
      (zone cliquable, sans rotation)

    Pour un texte, la **taille de police est dynamique** : elle suit la boîte
    (largeur ou hauteur, la contrainte la plus forte) quand on la redimensionne,
    et une barre de mise en forme (police, taille, gras, italique, couleur)
    reste utilisable jusqu'à la validation. Une image garde ses proportions :
    la redimensionner agrandit ou réduit l'image entière.

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
        self._fmt_bar: QWidget | None = None
        self._aspect: float | None = None   # ratio L/H imposé (images)

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
            # Taille initiale : l'image tient dans 300×300 pt (zoom compris) en gardant
            # ses proportions ; le redimensionnement conserve ensuite ce ratio.
            iw, ih = self._pixmap.width(), self._pixmap.height()
            self._aspect = iw / ih
            k = min(1.0, 300 * zoom / iw, 300 * zoom / ih)
            k = max(k, MIN_SIZE / min(iw, ih))
            self._item_size = QSizeF(iw * k, ih * k)
        elif data.get("type") == "text":
            self._data.setdefault("fontname", "helv")
            self._data.setdefault("family", "Helvetica")
            fs = float(data.get("fontsize", 12))
            w, h = text_natural_size(data.get("text", ""), self._data["fontname"], fs)
            self._item_size = QSizeF(max(MIN_SIZE, w * zoom), max(MIN_SIZE / 2, h * zoom))
            self._build_format_bar()
        elif data.get("type") == "stamp":
            self._data.setdefault("text", "TAMPON")
            self._data.update(fontname="hebo", family="Helvetica", bold=True, italic=False)
            fs = float(data.get("fontsize", 16))
            w, h = text_natural_size(self._data["text"], "hebo", fs)
            self._data["fontsize"] = fs
            self._item_size = QSizeF((w + 2 * STAMP_PAD) * zoom, (h + 2 * STAMP_PAD) * zoom)
        elif data.get("type") == "link":
            self._item_size = QSizeF(160 * zoom, 28 * zoom)

        self._place_at_center()

    # ── Placement initial ────────────────────────────────────────────────────

    def _place_at_center(self):
        if self.parent():
            pw, ph = self.parent().width(), self.parent().height()
            x = int(pw / 2 - self._item_size.width()  / 2)
            y = int(ph / 2 - self._item_size.height() / 2)
            self.move(x, y)
        self._update_size()

    def _keep_aspect(self, new_w: float, new_h: float) -> tuple[float, float]:
        """Ajuste (largeur, hauteur) au ratio de l'image : l'axe le plus tiré commande."""
        w0, h0 = self._size_at_drag.width(), self._size_at_drag.height()
        if abs(new_w - w0) / w0 >= abs(new_h - h0) / h0:
            new_h = new_w / self._aspect
        else:
            new_w = new_h * self._aspect
        low = min(new_w, new_h)
        if low < MIN_SIZE:
            new_w, new_h = new_w * MIN_SIZE / low, new_h * MIN_SIZE / low
        return new_w, new_h

    def place_center_at(self, pos: QPoint):
        """Centre la boîte de l'élément sur ``pos`` (coordonnées de la page), bornée à la page."""
        r = self._item_rect()
        x = int(pos.x() - r.center().x())
        y = int(pos.y() - r.center().y())
        if self.parent():
            x = max(0, min(x, self.parent().width() - self.width()))
            y = max(0, min(y, self.parent().height() - self.height()))
        self.move(x, y)

    def _update_size(self):
        margin = HANDLE_R + 2
        extra  = ROT_DIST + HANDLE_R
        w = int(self._item_size.width())  + margin * 2
        h = int(self._item_size.height()) + margin * 2 + extra
        bars = BAR_H
        self._toolbar.move(0, h + 2)
        if self._fmt_bar is not None:
            self._fmt_bar.move(0, h + 2 + BAR_H)
            bars += BAR_H
            w = max(w, self._fmt_bar.width())
        # le widget ne doit pas rogner les barres d'outils quand la boîte est petite
        w = max(w, self._toolbar.width())
        self.resize(w, h + bars)

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
            if self._aspect:
                new_w, new_h = self._keep_aspect(new_w, new_h)
            self._item_size = QSizeF(new_w, new_h)
            self._refit_text()
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
            p.drawRect(r)
            pad = self._pad_pt() * max(self._zoom, 0.01)
            self._draw_text(p, r.adjusted(pad, pad, -pad, -pad), center=True)

        elif dtype == "link":
            p.setPen(QPen(QColor("#3B82F6"), 2, Qt.PenStyle.DashLine))
            p.setBrush(QColor(59, 130, 246, 55))
            p.drawRect(r)
            p.setPen(QPen(QColor("#FFFFFF")))
            p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            label = self._data.get("uri") or self.tr("Page %1").replace(
                "%1", str(int(self._data.get("goto_page", 0)) + 1))
            p.drawText(r.adjusted(6, 0, -6, 0),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       "🔗  " + label)

        elif dtype == "text":
            p.fillRect(r, QColor(255, 255, 200, 180))
            self._draw_text(p, r)

    # ── Texte : taille dynamique et mise en forme ────────────────────────────

    def _text_font(self) -> str:
        return self._data.get("fontname", "helv")

    def _pad_pt(self) -> float:
        """Marge intérieure (pts) entre le cadre et le texte : tampon seulement."""
        return STAMP_PAD if self._data.get("type") == "stamp" else 0.0

    def _refit_text(self):
        """Recalcule la taille de police pour que le texte remplisse la boîte."""
        if self._data.get("type") not in ("text", "stamp"):
            return
        z = max(self._zoom, 0.01)
        pad = 2 * self._pad_pt()
        size = fit_fontsize(self._data.get("text", ""), self._text_font(),
                            self._item_size.width() / z - pad,
                            self._item_size.height() / z - pad)
        self._data["fontsize"] = round(size, 2)
        self._sync_size_spin()

    def _draw_text(self, p: QPainter, r: QRectF, center: bool = False):
        text = self._data.get("text", "")
        if not text:
            return
        z = max(self._zoom, 0.01)
        size_px = float(self._data.get("fontsize", 12)) * z
        asc, desc = text_line_metrics(self._text_font())
        # Aperçu fidèle à la gravure : la largeur suit les métriques de la police
        # PDF, même si la police Qt de remplacement est un peu différente.
        want_w = text_natural_size(text, self._text_font(),
                                   float(self._data.get("fontsize", 12)))[0] * z
        qf = QFont()
        qf.setFamilies(_QT_FAMILIES.get(self._data.get("family", "Helvetica"),
                                         _QT_FAMILIES["Helvetica"]))
        qf.setPixelSize(100)
        qf.setBold(bool(self._data.get("bold")))
        qf.setItalic(bool(self._data.get("italic")))
        qt_w = QFontMetricsF(qf).horizontalAdvance(text) or 1.0
        color = self._data.get("color", (0, 0, 0))
        p.save()
        p.setClipRect(r)
        p.setPen(QPen(QColor(*(int(c * 255) for c in color))))
        p.setFont(qf)
        baseline = r.top() + (r.height() - (asc + desc) * size_px) / 2 + asc * size_px
        p.translate(r.left() + ((r.width() - want_w) / 2 if center else 0), baseline)
        p.scale(want_w / qt_w, size_px / 100.0)
        p.drawText(QPointF(0, 0), text)
        p.restore()

    def _build_format_bar(self):
        """Barre sous la boîte : police, taille, gras, italique, couleur."""
        bar = QWidget(self)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        style = ("QWidget { background:#2D2D2D; color:#F0F0F0; font-size:11px; }"
                 "QComboBox, QDoubleSpinBox { background:#1E1E1E; border:1px solid #3A3A3A;"
                 " border-radius:4px; padding:1px 4px; }"
                 "QPushButton { background:#3A3A3A; border:1px solid #4A4A4A;"
                 " border-radius:4px; padding:2px 8px; }"
                 f"QPushButton:checked {{ background:{ACCENT}; color:#1E1E1E; }}")
        bar.setStyleSheet(style)

        self._cb_family = QComboBox()
        self._cb_family.addItems(list(PDF_FONTS))
        self._cb_family.setCurrentText(self._data.get("family", "Helvetica"))
        self._sp_size = QDoubleSpinBox()
        self._sp_size.setRange(1.0, 400.0)
        self._sp_size.setDecimals(1)
        self._sp_size.setSuffix(" pt")
        self._sp_size.setKeyboardTracking(False)
        self._bt_bold = QPushButton("G")
        self._bt_bold.setCheckable(True)
        self._bt_bold.setChecked(bool(self._data.get("bold")))
        self._bt_bold.setToolTip(self.tr("Gras"))
        self._bt_italic = QPushButton("I")
        self._bt_italic.setCheckable(True)
        self._bt_italic.setChecked(bool(self._data.get("italic")))
        self._bt_italic.setToolTip(self.tr("Italique"))
        self._bt_color = QPushButton("A")
        self._bt_color.setToolTip(self.tr("Couleur"))
        for w in (self._cb_family, self._sp_size, self._bt_bold,
                  self._bt_italic, self._bt_color):
            lay.addWidget(w)
        bar.adjustSize()

        self._fmt_bar = bar
        self._sync_size_spin()
        self._paint_color_button()
        self._cb_family.currentTextChanged.connect(self._on_style_changed)
        self._bt_bold.toggled.connect(self._on_style_changed)
        self._bt_italic.toggled.connect(self._on_style_changed)
        self._sp_size.valueChanged.connect(self._on_size_edited)
        self._bt_color.clicked.connect(self._pick_color)

    def _sync_size_spin(self):
        if self._fmt_bar is None:
            return
        self._sp_size.blockSignals(True)
        self._sp_size.setValue(float(self._data.get("fontsize", 12)))
        self._sp_size.blockSignals(False)

    def _paint_color_button(self):
        c = QColor(*(int(v * 255) for v in self._data.get("color", (0, 0, 0))))
        fg = "#000000" if c.lightness() > 128 else "#FFFFFF"
        self._bt_color.setStyleSheet(
            f"QPushButton {{ background:{c.name()}; color:{fg};"
            f" border:1px solid #4A4A4A; font-weight:bold; }}")

    def _on_style_changed(self, *_):
        """Police / gras / italique : la boîte ne bouge pas, la taille se réajuste."""
        family = self._cb_family.currentText()
        bold, italic = self._bt_bold.isChecked(), self._bt_italic.isChecked()
        self._data.update(family=family, bold=bold, italic=italic,
                          fontname=pdf_fontname(family, bold, italic))
        self._refit_text()
        self.update()

    def _on_size_edited(self, value: float):
        """Taille saisie : la boîte s'ajuste au texte à cette taille (coin haut-gauche fixe)."""
        self._data["fontsize"] = round(float(value), 2)
        w, h = text_natural_size(self._data.get("text", ""), self._text_font(), value)
        z = max(self._zoom, 0.01)
        self._item_size = QSizeF(max(MIN_SIZE / 2, w * z), max(MIN_SIZE / 4, h * z))
        self._update_size()
        self.update()

    def _pick_color(self):
        c0 = QColor(*(int(v * 255) for v in self._data.get("color", (0, 0, 0))))
        c = QColorDialog.getColor(c0, self, self.tr("Couleur du texte"))
        if c.isValid():
            self._data["color"] = (c.redF(), c.greenF(), c.blueF())
            self._paint_color_button()
            self.update()

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
