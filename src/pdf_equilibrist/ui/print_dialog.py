"""
ui/print_dialog.py — Dialogue d'impression avec aperçu live
============================================================
Aperçu :  QScrollArea custom — pages adaptées à la largeur du panneau.
Rendu :   chaque page est dessinée sur un "papier" blanc aux dimensions
          choisies, selon le mode d'échelle sélectionné.
Modes d'échelle :
  - 100 %   : contenu non mis à l'échelle, rogné si déborde.
  - Ajuster : contenu mis à l'échelle pour remplir le papier (KeepAspectRatio).
  - Réduire : réduction si le contenu dépasse le papier, sinon 100 %.
"""
from __future__ import annotations
import sys
import fitz
import logging
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QGroupBox, QPushButton, QLineEdit,
    QScrollArea, QWidget, QFrame, QLabel, QProgressBar,
)
from PyQt6.QtGui import QPainter, QImage, QPixmap, QPageSize, QPageLayout
from PyQt6.QtCore import QRect, Qt, QThread, pyqtSignal
from pdf_equilibrist.core.document import Document

_IS_WINDOWS = sys.platform == "win32"

_log = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

_PREVIEW_MARGIN = 20   # px autour des pages dans l'aperçu
_PAGE_GAP       = 12   # px entre les pages

_STYLE = """
QDialog { background: #1E1E1E; color: #F0F0F0; }
QGroupBox {
    color: #AAAAAA; font-size: 8pt; font-weight: bold;
    border: 1px solid #3A3A3A; border-radius: 4px;
    margin-top: 8px; padding-top: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QLabel  { color: #C0C0C0; font-size: 9pt; }
QComboBox, QSpinBox, QLineEdit {
    background: #2D2D2D; color: #F0F0F0;
    border: 1px solid #444; border-radius: 3px;
    padding: 3px 6px; font-size: 9pt; min-height: 22px;
}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus { border-color: #6BBF4E; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #2D2D2D; color: #F0F0F0;
    selection-background-color: #3A3A3A; color: #F0F0F0;
}
QPushButton {
    background: #2D2D2D; color: #F0F0F0;
    border: 1px solid #444; border-radius: 4px;
    padding: 6px 18px; font-size: 9pt; min-width: 90px;
}
QPushButton:hover  { background: #3A3A3A; border-color: #6BBF4E; }
QPushButton:pressed { background: #1A1A1A; }
QPushButton#btn_print {
    background: #6BBF4E; color: #000; border-color: #5AA83D; font-weight: bold;
}
QPushButton#btn_print:hover { background: #7DD05F; }
QScrollArea { border: none; background: #2A2A2A; }
"""


# ── Aperçu custom ─────────────────────────────────────────────────────────────

def _compose_page(pdf_page: fitz.Page,
                  paper_w_px: int, paper_h_px: int,
                  scale_mode: str,
                  orient: str) -> QPixmap:
    """
    Crée un QPixmap de taille paper_w_px × paper_h_px (fond blanc)
    avec le contenu de pdf_page rendu selon scale_mode.

    scale_mode : "100" | "ajuster" | "reduire"
    """
    page_w_pts = pdf_page.rect.width
    page_h_pts = pdf_page.rect.height

    # Zoom pour le mode 100 % : 1 pt PDF → 1 px préview (1:1 relatif au papier)
    ratio_w = paper_w_px / page_w_pts
    ratio_h = paper_h_px / page_h_pts

    if scale_mode == "100":
        # Rendu à 72 DPI (1 pt = 1 px) : le contenu n'est pas mis à l'échelle
        zoom = 1.0
    elif scale_mode == "ajuster":
        # Contenu mis à l'échelle pour tenir dans le papier (KeepAspectRatio)
        zoom = min(ratio_w, ratio_h)
    else:  # "reduire"
        zoom = min(ratio_w, ratio_h)
        if zoom > 1.0:
            zoom = 1.0   # ne jamais agrandir

    mat = fitz.Matrix(zoom, zoom)
    pix = pdf_page.get_pixmap(matrix=mat, alpha=False)
    img = QImage(pix.samples, pix.width, pix.height,
                 pix.stride, QImage.Format.Format_RGB888)
    content_pix = QPixmap.fromImage(img)

    # Fond blanc = papier
    paper = QPixmap(paper_w_px, paper_h_px)
    paper.fill(Qt.GlobalColor.white)

    painter = QPainter(paper)
    if scale_mode == "100":
        # Centré, rogné aux bords du papier si déborde
        painter.setClipRect(0, 0, paper_w_px, paper_h_px)
        x = (paper_w_px - content_pix.width())  // 2
        y = (paper_h_px - content_pix.height()) // 2
        painter.drawPixmap(x, y, content_pix)
    else:
        x = (paper_w_px - content_pix.width())  // 2
        y = (paper_h_px - content_pix.height()) // 2
        painter.drawPixmap(x, y, content_pix)
    painter.end()

    return paper


class _PreviewArea(QScrollArea):
    """
    Aperçu live des pages PDF :
    - pages adaptées à la largeur disponible du viewer
    - fond papier blanc aux dimensions choisies
    - mode d'échelle appliqué visuellement
    """

    # Largeur fixe du papier dans l'aperçu (px) — pas de resize dynamique
    _PAPER_W_PX = 500

    def __init__(self, fitz_doc: fitz.Document, parent=None):
        super().__init__(parent)
        self._fitz_doc   = fitz_doc
        self._paper_w_mm = 210.0
        self._paper_h_mm = 297.0
        self._orient     = "auto"
        self._scale_mode = "reduire"

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._container = QWidget()
        self._container.setStyleSheet("background: #2A2A2A;")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setSpacing(_PAGE_GAP)
        self._vbox.setContentsMargins(
            _PREVIEW_MARGIN, _PREVIEW_MARGIN,
            _PREVIEW_MARGIN, _PREVIEW_MARGIN,
        )
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setWidget(self._container)
        self._labels: list[QLabel] = []

    def configure(self, paper_w_mm: float, paper_h_mm: float,
                  orient: str, scale_mode: str):
        self._paper_w_mm = paper_w_mm
        self._paper_h_mm = paper_h_mm
        self._orient     = orient
        self._scale_mode = scale_mode
        self._rebuild()

    def _rebuild(self):
        """
        Met à jour l'aperçu en place : réutilise les QLabel existants (mise à
        jour du pixmap) et crée/cache ceux qui manquent.
        Ne détruit jamais de widget pendant un rebuild — évite les crashes Qt.
        """
        pages = list(self._fitz_doc)

        # Créer les labels manquants
        while len(self._labels) < len(pages):
            lbl = QLabel()
            lbl.setStyleSheet("border: 1px solid #555;")
            self._vbox.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)
            self._labels.append(lbl)

        # Mettre à jour chaque label visible
        for i, page in enumerate(pages):
            pw_mm, ph_mm = self._effective_paper(page)
            ratio = ph_mm / pw_mm
            paper_w_px = self._PAPER_W_PX
            paper_h_px = round(paper_w_px * ratio)
            pix = _compose_page(page, paper_w_px, paper_h_px,
                                 self._scale_mode, self._orient)
            lbl = self._labels[i]
            lbl.setPixmap(pix)
            lbl.setFixedSize(paper_w_px, paper_h_px)
            lbl.show()

        # Cacher les labels en surplus (ex. changement de plage de pages)
        for i in range(len(pages), len(self._labels)):
            self._labels[i].hide()

        self._container.adjustSize()

    def _effective_paper(self, pdf_page: fitz.Page) -> tuple[float, float]:
        short = min(self._paper_w_mm, self._paper_h_mm)
        long_ = max(self._paper_w_mm, self._paper_h_mm)
        if self._orient == "paysage":
            return long_, short
        elif self._orient == "portrait":
            return short, long_
        else:  # auto
            pdf_land = pdf_page.rect.width > pdf_page.rect.height
            return (long_, short) if pdf_land else (short, long_)


# ── Impression Win32 (import paresseux, module dédié) ────────────────────────
# Tout le backend GDI (ctypes.wintypes, winspool, gdi32…) vit dans
# print_dialog_win32.py, importé uniquement sur Windows — ctypes.wintypes
# n'existe pas sous Linux/macOS et un import au niveau module ferait planter
# l'application entière au démarrage sur ces plateformes.

def _open_driver_properties(printer_name: str, hwnd: int,
                             current_devmode: bytes | None = None) -> bytes | None:
    from pdf_equilibrist.ui.print_dialog_win32 import open_driver_properties
    return open_driver_properties(printer_name, hwnd, current_devmode)


def _win32_print(printer_name: str, devmode_bytes: bytes | None,
                  doc_bytes: bytes, pages: list[int],
                  scale_mode: str, use_landscape: bool,
                  flip_long_edge: bool,
                  doc_name: str,
                  progress_cb=None) -> bool:
    from pdf_equilibrist.ui.print_dialog_win32 import win32_print
    return win32_print(printer_name, devmode_bytes, doc_bytes, pages,
                       scale_mode, use_landscape, flip_long_edge,
                       doc_name, progress_cb)


# ── Impression Qt/CUPS (Linux, macOS) ────────────────────────────────────────

def _qt_print(printer_name: str, doc_bytes: bytes, pages: list[int],
              scale_mode: str, use_landscape: bool,
              doc_name: str, progress_cb=None) -> bool:
    """
    Impression via QPrinter/QPainter (pilote CUPS) — chemin non-Windows.

    Rendu raster direct, sans le hack hairline-upsampling ni l'overlay
    vectoriel GDI (spécifiques Win32/plans AutoCAD, cf. print_dialog_win32.py) :
    suffisant pour l'impression standard, la reprise complète de ces
    finitions n'a pas d'équivalent direct côté Qt/CUPS.
    """
    info = QPrinterInfo.printerInfo(printer_name)
    printer = QPrinter(info, QPrinter.PrinterMode.HighResolution) if not info.isNull() \
        else QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(doc_name)
    printer.setPageOrientation(
        QPageLayout.Orientation.Landscape if use_landscape
        else QPageLayout.Orientation.Portrait
    )

    fitz_doc = fitz.open(stream=doc_bytes, filetype="pdf")
    painter = QPainter()
    try:
        if not painter.begin(printer):
            _log.error("QPainter.begin() a échoué pour l'imprimante %r", printer_name)
            return False

        dpi = printer.resolution()
        paint_rect = printer.pageLayout().paintRectPixels(dpi)
        page_w, page_h = paint_rect.width(), paint_rect.height()

        total = len(pages)
        for n, page_i in enumerate(pages):
            if progress_cb:
                progress_cb(n, total)
            if n > 0:
                printer.newPage()

            pdf_page = fitz_doc[page_i]
            pw, ph = pdf_page.rect.width, pdf_page.rect.height

            base_zoom = dpi / 72.0
            if scale_mode == "ajuster":
                zoom = min(page_w / pw, page_h / ph)
            elif scale_mode == "reduire":
                zoom = min(min(page_w / pw, page_h / ph), base_zoom)
            else:
                zoom = base_zoom

            mat = fitz.Matrix(zoom, zoom)
            pix = pdf_page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height,
                         pix.stride, QImage.Format.Format_RGB888)

            dest_w = min(pix.width, page_w)
            dest_h = min(pix.height, page_h)
            dst_x  = max(0, (page_w - dest_w) // 2)
            dst_y  = max(0, (page_h - dest_h) // 2)
            painter.drawImage(QRect(dst_x, dst_y, dest_w, dest_h), img)

        if progress_cb:
            progress_cb(total, total)
        return True

    except Exception:
        _log.exception("_qt_print error")
        return False

    finally:
        painter.end()
        fitz_doc.close()


# ── Worker thread ──────────────────────────────────────────────────────────────

class _PrintWorker(QThread):
    """Exécute l'impression dans un thread secondaire pour ne pas geler l'UI."""

    progress = pyqtSignal(int, int)   # (pages_done, pages_total)
    finished = pyqtSignal(bool)        # success

    def __init__(self, printer_name: str, devmode_bytes, doc_bytes: bytes,
                 pages: list[int], scale_mode: str, use_landscape: bool,
                 flip_long_edge: bool, doc_name: str, parent=None):
        super().__init__(parent)
        self._args = dict(
            printer_name=printer_name, devmode_bytes=devmode_bytes,
            doc_bytes=doc_bytes, pages=pages,
            scale_mode=scale_mode, use_landscape=use_landscape,
            flip_long_edge=flip_long_edge, doc_name=doc_name,
        )

    def run(self):
        progress_cb = lambda d, t: self.progress.emit(d, t)
        if _IS_WINDOWS:
            ok = _win32_print(**self._args, progress_cb=progress_cb)
        else:
            args = {k: v for k, v in self._args.items()
                    if k not in ("devmode_bytes", "flip_long_edge")}
            ok = _qt_print(**args, progress_cb=progress_cb)
        self.finished.emit(ok)


# ── Helpers impression ────────────────────────────────────────────────────────

def _page_is_landscape(page: fitz.Page) -> bool:
    return page.rect.width > page.rect.height


def _parse_page_range(text: str, n: int) -> list[int]:
    result = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                lo, hi = int(a) - 1, int(b) - 1
                result.extend(range(max(0, lo), min(n - 1, hi) + 1))
            except ValueError:
                pass
        else:
            try:
                i = int(part) - 1
                if 0 <= i < n:
                    result.append(i)
            except ValueError:
                pass
    return result or list(range(n))


def _draw_fit(painter: QPainter, pixmap: QPixmap, target: QRect):
    scaled = pixmap.scaled(
        target.width(), target.height(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = target.x() + (target.width()  - scaled.width())  // 2
    y = target.y() + (target.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)


# ── Dialogue principal ────────────────────────────────────────────────────────

class PrintDialog(QDialog):

    def __init__(self, document: Document, parent=None):
        super().__init__(parent)
        self._doc      = document
        self._fitz_doc = document.fitz_doc
        self._n_pages  = len(self._fitz_doc)
        self._printer  = QPrinter(QPrinter.PrinterMode.HighResolution)
        self._printer.setDocName(document.path.name)

        # Tailles papier disponibles (remplies à la sélection d'imprimante)
        self._page_sizes: list[QPageSize] = []
        self._devmode:    bytes | None     = None   # DEVMODE driver (agrafe, etc.)

        self.setWindowTitle(f"Imprimer — {document.path.name}")
        self.resize(1150, 720)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(_STYLE)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        root.addWidget(self._build_options(), 0)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #3A3A3A;")
        root.addWidget(sep)

        self._preview = _PreviewArea(self._fitz_doc, self)
        root.addWidget(self._preview, 1)

        # Peupler les formats de la première imprimante
        self._populate_paper_sizes()
        self._refresh_preview()

    # ── Options ───────────────────────────────────────────────────────────────

    def _build_options(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(260)
        vbox = QVBoxLayout(w)
        vbox.setSpacing(8)
        vbox.setContentsMargins(0, 0, 0, 0)

        # Imprimante
        grp = QGroupBox("Imprimante")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_printer = QComboBox()
        names   = QPrinterInfo.availablePrinterNames()
        default = QPrinterInfo.defaultPrinterName()
        for n in names:
            self._cb_printer.addItem(n)
        if default in names:
            self._cb_printer.setCurrentText(default)
        f.addRow("Nom :", self._cb_printer)
        self._cb_printer.currentTextChanged.connect(self._on_printer_changed)
        self._btn_props = QPushButton("Propriétés avancées…")
        self._btn_props.setToolTip(
            "Ouvre les propriétés natives de l'imprimante\n"
            "(agrafe, perforation, format rouleau, découpe, …)"
        )
        self._btn_props.clicked.connect(self._open_native_props)
        # Dialogue DocumentProperties Win32 — pas d'équivalent Qt/CUPS sur Linux/macOS
        self._btn_props.setVisible(_IS_WINDOWS)
        f.addRow(self._btn_props)
        vbox.addWidget(grp)

        # Copies
        grp = QGroupBox("Copies")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._spin_copies = QSpinBox()
        self._spin_copies.setRange(1, 999)
        f.addRow("Nombre :", self._spin_copies)
        vbox.addWidget(grp)

        # Pages
        grp = QGroupBox("Pages à imprimer")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_pages = QComboBox()
        self._cb_pages.addItems(["Tout", "Pages personnalisées"])
        f.addRow("Plage :", self._cb_pages)
        self._edit_range = QLineEdit()
        self._edit_range.setPlaceholderText("ex: 1-3, 5, 8-10")
        self._edit_range.setEnabled(False)
        f.addRow("Numéros :", self._edit_range)
        self._cb_pages.currentIndexChanged.connect(
            lambda i: self._edit_range.setEnabled(i == 1))
        vbox.addWidget(grp)

        # Format papier
        grp = QGroupBox("Format papier")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_paper = QComboBox()
        f.addRow("Format :", self._cb_paper)
        self._cb_paper.currentIndexChanged.connect(self._refresh_preview)
        vbox.addWidget(grp)

        # Orientation
        grp = QGroupBox("Orientation")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_orient = QComboBox()
        self._cb_orient.addItems(["Auto (par page)", "Portrait", "Paysage"])
        f.addRow(self._cb_orient)
        self._cb_orient.currentIndexChanged.connect(self._refresh_preview)
        vbox.addWidget(grp)

        # Échelle
        grp = QGroupBox("Échelle / Dimensionnement")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_scale = QComboBox()
        self._cb_scale.addItems([
            "Ajuster (remplir le papier)",
            "Réduire uniquement",
            "100 % (rogner si déborde)",
        ])
        self._cb_scale.setCurrentIndex(1)   # défaut : réduire
        f.addRow(self._cb_scale)
        self._cb_scale.currentIndexChanged.connect(self._refresh_preview)
        vbox.addWidget(grp)

        # Recto/Verso
        grp = QGroupBox("Recto / Verso")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_duplex = QComboBox()
        self._cb_duplex.addItems([
            "Désactivé",
            "Retourner sur le bord long",
            "Retourner sur le bord court",
        ])
        self._cb_duplex.setCurrentIndex(1)   # défaut : bord long
        f.addRow(self._cb_duplex)
        vbox.addWidget(grp)

        # Couleur
        grp = QGroupBox("Couleur")
        f   = QFormLayout(grp)
        f.setSpacing(5)
        self._cb_color = QComboBox()
        self._cb_color.addItems(["Couleur", "Nuances de gris"])
        f.addRow(self._cb_color)
        vbox.addWidget(grp)

        vbox.addStretch()

        # Barre de progression (masquée jusqu'au lancement de l'impression)
        self._progress_bar   = QProgressBar()
        self._progress_label = QLabel("Impression en cours…")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.hide()
        self._progress_bar.hide()
        vbox.addWidget(self._progress_label)
        vbox.addWidget(self._progress_bar)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Annuler")
        self._btn_print  = QPushButton("Imprimer")
        self._btn_print.setObjectName("btn_print")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_print.clicked.connect(self._do_print)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_print)
        vbox.addLayout(btn_row)

        return w

    # ── Format papier ─────────────────────────────────────────────────────────

    def _open_native_props(self):
        """
        Ouvre le dialogue de propriétés du driver d'imprimante via
        ``DocumentProperties`` (Win32 winspool.drv).

        C'est le dialogue propre au fabricant — différent du dialogue générique
        Windows — qui expose les options avancées : agrafe, perforation,
        format rouleau, découpe bande blanche, qualité, bac papier, etc.

        Après fermeture (OK), les formats papier sont rechargés car l'utilisateur
        a pu définir un format personnalisé (ex. rouleau traceur).
        """
        printer_name = self._cb_printer.currentText()
        # Utiliser le hwnd DU dialogue (pas du parent) — DocumentProperties
        # apparaît au-dessus de lui, le dialogue reste dans la pile Qt correctement.
        # Ne pas hide()/show() : ça casse la hiérarchie de fenêtres et bloque le focus.
        hwnd = int(self.winId())
        devmode = _open_driver_properties(printer_name, hwnd, self._devmode)

        if devmode is not None:
            self._devmode = devmode
            self._btn_props.setText("Propriétés avancées ✓")
            self._btn_props.setToolTip(
                "Réglages driver configurés (agrafe, finition…)\n"
                "Ces réglages seront transmis directement au driver à l'impression.\n"
                "Cliquer pour modifier."
            )

        self.raise_()
        self.activateWindow()
        self._populate_paper_sizes()
        self._refresh_preview()

    def _on_printer_changed(self, name: str):
        info = QPrinterInfo.printerInfo(name)
        if not info.isNull():
            self._printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
            self._printer.setDocName(self._doc.path.name)
        # Réinitialiser le DEVMODE : il est propre à chaque imprimante
        self._devmode = None
        self._btn_props.setText("Propriétés avancées…")
        self._btn_props.setToolTip(
            "Ouvre les propriétés natives de l'imprimante\n"
            "(agrafe, perforation, format rouleau, découpe, …)"
        )
        self._populate_paper_sizes()
        self._refresh_preview()

    def _populate_paper_sizes(self):
        """Peuple le combo Format avec les tailles supportées par l'imprimante."""
        name = self._cb_printer.currentText()
        info = QPrinterInfo.printerInfo(name)
        sizes = info.supportedPageSizes() if not info.isNull() else []

        # Fallback si l'imprimante ne retourne rien
        if not sizes:
            sizes = [
                QPageSize(QPageSize.PageSizeId.A4),
                QPageSize(QPageSize.PageSizeId.A3),
                QPageSize(QPageSize.PageSizeId.A5),
                QPageSize(QPageSize.PageSizeId.Letter),
            ]

        self._page_sizes = sizes
        self._cb_paper.blockSignals(True)
        self._cb_paper.clear()
        for ps in sizes:
            sz = ps.size(QPageSize.Unit.Millimeter)
            self._cb_paper.addItem(
                f"{ps.name()}  ({sz.width():.0f}×{sz.height():.0f} mm)"
            )
        # Sélectionner A4 par défaut si disponible
        for i, ps in enumerate(sizes):
            if ps.id() == QPageSize.PageSizeId.A4:
                self._cb_paper.setCurrentIndex(i)
                break
        self._cb_paper.blockSignals(False)

    def _current_paper_mm(self) -> tuple[float, float]:
        """Retourne (w_mm, h_mm) du format papier sélectionné (portrait)."""
        idx = self._cb_paper.currentIndex()
        if 0 <= idx < len(self._page_sizes):
            sz = self._page_sizes[idx].size(QPageSize.Unit.Millimeter)
            short = min(sz.width(), sz.height())
            long_ = max(sz.width(), sz.height())
            return short, long_
        return 210.0, 297.0  # A4 fallback

    # ── Aperçu ────────────────────────────────────────────────────────────────

    def _refresh_preview(self):
        scale_map = {0: "ajuster", 1: "reduire", 2: "100"}
        orient_map = {0: "auto", 1: "portrait", 2: "paysage"}
        w_mm, h_mm = self._current_paper_mm()
        self._preview.configure(
            w_mm, h_mm,
            orient_map[self._cb_orient.currentIndex()],
            scale_map[self._cb_scale.currentIndex()],
        )

    # ── Impression ────────────────────────────────────────────────────────────

    def _pages_to_print(self) -> list[int]:
        if self._cb_pages.currentIndex() == 0:
            return list(range(self._n_pages))
        return _parse_page_range(self._edit_range.text(), self._n_pages)

    def _do_print(self):
        printer_name = self._cb_printer.currentText()
        scale_map    = {0: "ajuster", 1: "reduire", 2: "100"}
        scale_mode   = scale_map[self._cb_scale.currentIndex()]
        orient_idx   = self._cb_orient.currentIndex()
        pages        = self._pages_to_print()

        if orient_idx == 0:
            n_land = sum(1 for i in pages
                         if _page_is_landscape(self._fitz_doc[i]))
            use_landscape = n_land > len(pages) / 2
        else:
            use_landscape = (orient_idx == 2)

        flip_long_edge = (self._cb_duplex.currentIndex() != 2)

        # Sérialiser le document dans le thread principal (thread-safe),
        # le worker ouvrira sa propre instance fitz depuis ces bytes.
        doc_bytes = self._fitz_doc.tobytes()

        # ── UI : passer en mode "impression en cours" ─────────────────────────
        self._btn_print.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._progress_bar.setRange(0, max(1, len(pages)))
        self._progress_bar.setValue(0)
        self._progress_label.show()
        self._progress_bar.show()

        self._worker = _PrintWorker(
            printer_name  = printer_name,
            devmode_bytes = self._devmode,
            doc_bytes     = doc_bytes,
            pages         = pages,
            scale_mode    = scale_mode,
            use_landscape = use_landscape,
            flip_long_edge= flip_long_edge,
            doc_name      = self._doc.path.name,
            parent        = self,
        )
        self._worker.progress.connect(self._on_print_progress)
        self._worker.finished.connect(self._on_print_done)
        self._worker.start()

    def _on_print_progress(self, done: int, total: int):
        self._progress_bar.setMaximum(max(1, total))
        self._progress_bar.setValue(done)
        self._progress_label.setText(
            f"Impression en cours… page {done}/{total}"
        )

    def _on_print_done(self, ok: bool):
        if not ok:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erreur d'impression",
                                 "Impossible de démarrer le travail d'impression.\n"
                                 "Vérifiez que l'imprimante est disponible.")
        self.accept()


# ── Point d'entrée ────────────────────────────────────────────────────────────

def print_document(document: Document, parent=None) -> bool:
    if not document.is_open:
        return False
    PrintDialog(document, parent).exec()
    # Restaurer le focus sur la fenêtre principale — sinon Windows peut laisser
    # le focus dans le vide après fermeture d'un dialogue modal Qt + Win32 mixte.
    if parent is not None:
        parent.activateWindow()
        parent.raise_()
    return True
