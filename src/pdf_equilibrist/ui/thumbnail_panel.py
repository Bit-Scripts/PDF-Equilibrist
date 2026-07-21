"""
ui/thumbnail_panel.py — Panneau miniatures latéral
====================================================
Ce module fournit le panneau de miniatures de pages toujours visible
à gauche du viewer. Il gère l'affichage, la navigation, le glisser-déposer
interne (réorganisation) et externe (insertion de PDF).

Architecture du drag & drop
-----------------------------
Le DnD est entièrement géré par ``ThumbnailPanel`` (le panneau conteneur),
et NON par ``_ThumbList`` (la liste Qt). Ce choix est délibéré :

- ``ThumbnailPanel.setAcceptDrops(True)`` garantit que Qt route les drag events
  vers le panneau, quel que soit le widget enfant sous le curseur.
- ``_ThumbList`` se contente de détecter le début du drag via un event filter
  sur son viewport (``mousePressEvent`` + ``mouseMoveEvent``), puis émet
  ``drag_started(row)`` vers le panneau.
- Le panneau lance le ``QDrag`` avec un mime type custom ``_MIME_ROW``,
  gère les événements ``dragEnterEvent/dragMoveEvent/dragLeaveEvent/dropEvent``
  et applique le ``doc.move_page()`` correspondant.

Pourquoi pas le DnD natif de QListWidget ?
-------------------------------------------
``QListWidget`` avec ``InternalMove`` gère le déplacement visuel des items
mais ne permet pas de hook fiable sur l'ordre réel des pages dans ``fitz.Document``.
De plus, les drops externes (fichiers PDF depuis l'explorateur) ne sont pas
gérés nativement. Le contrôle total via ``ThumbnailPanel`` est plus robuste.

Barre d'insertion (_DropLine)
------------------------------
Un widget ``_DropLine`` transparent aux events souris est posé sur le viewport
de la liste. Il dessine une ligne blanche avec cercles aux extrémités à la
position d'insertion calculée lors du ``dragMoveEvent``. Il est masqué dès
que le drag se termine (drop ou annulation).

Largeur dynamique
------------------
La largeur du panneau s'adapte au document ouvert via ``rebuild()`` :
chaque page est rendue à une hauteur fixe ``THUMB_H``, et la largeur est
calculée en respectant le ratio largeur/hauteur de la page. Le panneau
prend la largeur de la page la plus large + padding.
``width_changed`` est émis pour que ``MainWindow`` force le splitter
à respecter la nouvelle largeur.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QAbstractItemView, QMenu,
)
from PyQt6.QtGui import (QIcon, QPixmap, QImage, QAction,
                          QPainter, QPen, QColor, QDrag)
from PyQt6.QtCore import (Qt, pyqtSignal, QSize, QPoint,
                           QMimeData, QEvent)
import fitz
from pdf_equilibrist.core.document import Document

ACCENT    = "#6BBF4E"
THUMB_H   = 160    # hauteur fixe de toutes les miniatures (px)
THUMB_PAD = 16     # padding horizontal de chaque côté de la miniature
# Mime type custom pour identifier les drags internes (réorganisation)
# Différent des URLs de fichiers pour distinguer drop interne vs fichier externe
_MIME_ROW = "application/x-pdf-equilibrist-row"

THUMB_W = 110   # conservé pour compatibilité (valeur héritée, non utilisée)


# ── Barre d'insertion ─────────────────────────────────────────────────────────

class _DropLine(QWidget):
    """Overlay blanc transparent aux événements souris."""
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def show_at(self, y: int):
        w = self.parent().width()
        self.setGeometry(6, y - 4, w - 12, 8)
        self.show()
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("white"), 3, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        w, mid = self.width(), self.height() // 2
        p.drawLine(8, mid, w - 8, mid)
        p.setBrush(QColor("white"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(8, mid), 4, 4)
        p.drawEllipse(QPoint(w - 8, mid), 4, 4)


# ── Liste (display only + détection début drag) ───────────────────────────────

class _ThumbList(QListWidget):
    drag_started = pyqtSignal(int)   # row dont le drag commence

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setMovement(QListWidget.Movement.Static)
        self.setAcceptDrops(False)
        self._press_row = -1
        self._press_pos = QPoint()
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is not self.viewport():
            return False
        t = ev.type()
        if t == QEvent.Type.MouseButtonPress:
            if ev.button() == Qt.MouseButton.LeftButton:
                pt   = ev.position().toPoint()
                item = self.itemAt(pt)
                self._press_row = self.row(item) if item else -1
                self._press_pos = pt
        elif t == QEvent.Type.MouseMove:
            if (self._press_row >= 0
                    and (ev.position().toPoint()
                         - self._press_pos).manhattanLength() > 8):
                row = self._press_row
                self._press_row = -1
                self.drag_started.emit(row)
        elif t == QEvent.Type.MouseButtonRelease:
            self._press_row = -1
        return False


# ── Panneau principal ─────────────────────────────────────────────────────────

class ThumbnailPanel(QWidget):
    page_selected = pyqtSignal(int)
    width_changed  = pyqtSignal(int)   # nouvelle largeur après rebuild

    def __init__(self, document: Document, viewer, parent=None):
        super().__init__(parent)
        self.document    = document
        self.viewer      = viewer
        self._insert_row = -1
        self.setFixedWidth(THUMB_H + THUMB_PAD * 2)   # sera recalculé à rebuild()
        self.setStyleSheet("background: #181818;")
        self.setAcceptDrops(True)   # ← reçoit TOUS les drag events

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)

        title = QLabel("Pages")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        layout.addWidget(title)

        self._list = _ThumbList()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(THUMB_W, 155))
        self._list.setGridSize(QSize(THUMB_W + 4, 178))
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setSpacing(4)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.setStyleSheet(f"""
            QListWidget {{ background: #181818; border: none; }}
            QListWidget::item {{
                background: #2D2D2D; border: 1px solid #3A3A3A;
                border-radius: 4px; color: #AAAAAA;
                font-size: 10px; padding: 2px;
            }}
            QListWidget::item:selected {{
                background: #2D2D2D; border: 2px solid {ACCENT}; color: {ACCENT};
            }}
            QListWidget::item:hover {{ border-color: {ACCENT}88; }}
        """)
        layout.addWidget(self._list)

        # Barre d'insertion — posée sur le viewport de la liste
        self._drop_line = _DropLine(self._list.viewport())

        self._list.itemClicked.connect(self._on_click)
        self._list.drag_started.connect(self._start_drag)
        self._list.customContextMenuRequested.connect(self._on_right_click)

        document.changed.connect(self.rebuild)
        self.rebuild()

    # ── miniatures ────────────────────────────────────────────────────────────

    def rebuild(self):
        self._list.clear()
        if not self.document.is_open:
            # Taille par défaut quand aucun doc
            self._resize_panel(THUMB_H + THUMB_PAD * 2)
            return

        doc = self.document.fitz_doc
        n   = len(doc)

        # 1. Calculer la largeur max parmi toutes les pages
        max_thumb_w = 40
        for i in range(n):
            page = doc[i]
            ratio = page.rect.width / max(page.rect.height, 1)
            w = max(40, int(THUMB_H * ratio))
            max_thumb_w = max(max_thumb_w, w)

        panel_w = max_thumb_w + THUMB_PAD * 2
        self._resize_panel(panel_w)

        # Mettre à jour la grille de la liste
        self._list.setIconSize(QSize(max_thumb_w, THUMB_H))
        self._list.setGridSize(QSize(panel_w - 4, THUMB_H + 22))

        # 2. Ajouter les items
        for i in range(n):
            pix  = self._render_thumb(i)
            item = QListWidgetItem(QIcon(pix), f"  {i+1} / {n}")
            item.setSizeHint(QSize(panel_w - 4, THUMB_H + 22))
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self._list.addItem(item)

    def _resize_panel(self, width: int):
        """Met à jour la largeur fixe du panneau et notifie le splitter."""
        if self.width() != width:
            self.setFixedWidth(width)
            self.updateGeometry()
            self.width_changed.emit(width)

    def _render_thumb(self, idx: int) -> QPixmap:
        """Rendu à l'aspect ratio exact de la page, hauteur = THUMB_H."""
        page  = self.document.fitz_doc[idx]
        zoom  = THUMB_H / max(page.rect.height, 1)
        pix   = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img   = QImage(pix.samples, pix.width, pix.height,
                       pix.stride, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img)

    # ── clic gauche ───────────────────────────────────────────────────────────

    def _on_click(self, item: QListWidgetItem):
        row = self._list.row(item)
        self.page_selected.emit(row)
        widgets = getattr(self.viewer, "_page_widgets", [])
        if row < len(widgets):
            self.viewer.ensureWidgetVisible(widgets[row], 0, 20)

    # ── drag interne (initié par _ThumbList) ──────────────────────────────────

    def _start_drag(self, src: int):
        mime = QMimeData()
        mime.setData(_MIME_ROW, str(src).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        item = self._list.item(src)
        if item:
            pix = item.icon().pixmap(THUMB_W, 155)
            drag.setPixmap(pix)
            drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)
        self._drop_line.hide()
        self._insert_row = -1

    # ── drag events (panel level) ─────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if self._can_accept(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._can_accept(event.mimeData()):
            ins = self._ins_pos(event.position().toPoint())
            self._insert_row = ins
            self._update_line(ins)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_line.hide()
        self._insert_row = -1

    def dropEvent(self, event):
        ins  = self._insert_row
        self._drop_line.hide()
        self._insert_row = -1
        mime = event.mimeData()

        if mime.hasFormat(_MIME_ROW):
            src = int(mime.data(_MIME_ROW).data().decode())
            event.acceptProposedAction()
            if ins >= 0 and ins != src and ins != src + 1:
                self._apply_move(src, ins)

        elif self._is_pdf(mime):
            event.acceptProposedAction()
            for url in mime.urls():
                path = url.toLocalFile()
                if path.lower().endswith(".pdf"):
                    self._on_pdf_insert(path, ins if ins >= 0 else self._list.count())
                    break
        else:
            event.ignore()

    # ── position d'insertion ──────────────────────────────────────────────────

    def _ins_pos(self, panel_pt: QPoint) -> int:
        """Convertit un point (coords panneau) en index d'insertion."""
        vp_pt = self._list.viewport().mapFromParent(
            self._list.mapFromParent(panel_pt))
        n = self._list.count()
        for i in range(n):
            rect = self._list.visualItemRect(self._list.item(i))
            if vp_pt.y() < rect.center().y():
                return i
        return n

    def _update_line(self, ins: int):
        n = self._list.count()
        if n == 0:
            return
        vp = self._list.viewport()
        if ins < n:
            y = self._list.visualItemRect(self._list.item(ins)).top()
        else:
            y = self._list.visualItemRect(self._list.item(n - 1)).bottom()
        # géométrie relative au viewport
        self._drop_line.setGeometry(6, y - 4, vp.width() - 12, 8)
        self._drop_line.show()
        self._drop_line.raise_()

    @staticmethod
    def _can_accept(mime: QMimeData) -> bool:
        return mime.hasFormat(_MIME_ROW) or ThumbnailPanel._is_pdf(mime)

    @staticmethod
    def _is_pdf(mime: QMimeData) -> bool:
        return mime.hasUrls() and any(
            u.toLocalFile().lower().endswith(".pdf") for u in mime.urls())

    # ── actions ───────────────────────────────────────────────────────────────

    def _apply_move(self, src: int, ins: int):
        doc = self.document.fitz_doc
        n   = len(doc)
        to  = -1 if ins >= n else (ins - 1 if ins > src else ins)
        doc.move_page(src, to)
        self.document.changed.emit()
        self._list.setCurrentRow((n - 1) if to == -1 else to)

    def _on_pdf_insert(self, path: str, insert_before: int):
        # Aucun document ouvert → ouvrir directement
        if not self.document.is_open:
            self.document.open(path)
            return
        try:
            src = fitz.open(path)
        except Exception as e:
            from pdf_equilibrist.ui.dialogs import show_error
            show_error(self, "Insertion PDF", f"Impossible d'ouvrir :\n{e}")
            return
        doc      = self.document.fitz_doc
        n_before = len(doc)
        at       = insert_before if insert_before < n_before else -1
        doc.insert_pdf(src, start_at=at)
        src.close()
        self.document.changed.emit()
        self._list.setCurrentRow(
            insert_before if insert_before < n_before else n_before)

    # ── clic droit ───────────────────────────────────────────────────────────

    def _on_right_click(self, pos: QPoint):
        item = self._list.itemAt(pos)
        if not item:
            return
        row = self._list.row(item)
        n   = self._list.count()

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:#2D2D2D; color:#F0F0F0; border:1px solid #3A3A3A; }}
            QMenu::item {{ padding:4px 20px; }}
            QMenu::item:selected {{ background:#3A3A3A; color:{ACCENT}; }}
            QMenu::separator {{ height:1px; background:#3A3A3A; margin:3px 0; }}
        """)

        up = QAction(f"↑  Monter  ({row+1}/{n} → {row}/{n})", self)
        up.setEnabled(row > 0)
        up.triggered.connect(lambda _=False, r=row: self._move_page(r, r - 1))
        menu.addAction(up)

        dn = QAction(f"↓  Descendre  ({row+1}/{n} → {row+2}/{n})", self)
        dn.setEnabled(row < n - 1)
        dn.triggered.connect(lambda _=False, r=row: self._move_page(r, r + 1))
        menu.addAction(dn)

        menu.addSeparator()

        cw = QAction("↻  Rotation horaire", self)
        cw.triggered.connect(lambda _=False, r=row: self._rotate(r, 90))
        menu.addAction(cw)

        ccw = QAction("↺  Rotation antihoraire", self)
        ccw.triggered.connect(lambda _=False, r=row: self._rotate(r, -90))
        menu.addAction(ccw)

        menu.addSeparator()

        dup = QAction(f"⧉  Dupliquer la page {row+1}", self)
        dup.triggered.connect(lambda _=False, r=row: self._duplicate(r))
        menu.addAction(dup)

        dl = QAction(f"🗑  Supprimer la page {row+1}", self)
        dl.triggered.connect(lambda _=False, r=row: self._delete(r))
        menu.addAction(dl)

        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _move_page(self, src: int, dst: int):
        doc = self.document.fitz_doc
        n   = len(doc)
        if not (0 <= dst < n):
            return
        to = dst if dst < src else (dst + 1 if dst + 1 < n else -1)
        doc.move_page(src, to)
        self.document.changed.emit()
        self._list.setCurrentRow(dst)

    def _rotate(self, row: int, angle: int):
        doc = self.document.fitz_doc
        tmp = fitz.open()
        tmp.insert_pdf(doc, from_page=row, to_page=row)
        tmp[0].set_rotation((tmp[0].rotation + angle) % 360)
        doc.delete_page(row)
        doc.insert_pdf(tmp, start_at=row)
        tmp.close()
        self.document.changed.emit()
        self._list.setCurrentRow(row)

    def _duplicate(self, row: int):
        doc = self.document.fitz_doc
        tmp = fitz.open()
        tmp.insert_pdf(doc, from_page=row, to_page=row)
        at  = row + 1 if row + 1 < len(doc) else -1
        doc.insert_pdf(tmp, start_at=at if at != -1 else len(doc))
        tmp.close()
        self.document.changed.emit()

    def _delete(self, row: int):
        if len(self.document.fitz_doc) <= 1:
            from pdf_equilibrist.ui.dialogs import show_error
            show_error(self, "Supprimer", "Impossible de supprimer la seule page.")
            return
        self.document.fitz_doc.delete_page(row)
        self.document.changed.emit()
