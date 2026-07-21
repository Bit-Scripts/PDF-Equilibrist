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
import fitz
import logging
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
import ctypes, ctypes.wintypes
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QGroupBox, QPushButton, QLineEdit,
    QScrollArea, QWidget, QFrame, QLabel, QProgressBar,
)
from PyQt6.QtGui import QPainter, QImage, QPixmap, QPageSize
from PyQt6.QtCore import QRect, Qt, QThread, pyqtSignal
from pdf_equilibrist.core.document import Document

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


# ── Dialogue driver natif (Win32) ────────────────────────────────────────────

class _PRINTER_INFO_9(ctypes.Structure):
    """Structure Win32 PRINTER_INFO_9 — contient un pointeur vers DEVMODE."""
    _fields_ = [("pDevMode", ctypes.c_void_p)]


def _open_driver_properties(printer_name: str, hwnd: int,
                             current_devmode: bytes | None = None) -> bytes | None:
    """
    Ouvre le dialogue de propriétés du driver d'imprimante (``DocumentProperties``).

    Si ``current_devmode`` est fourni, il est utilisé comme point de départ du
    dialogue — les modifications précédentes (agrafe, finition…) sont conservées.
    Retourne les octets DEVMODE modifiés si l'utilisateur clique OK, sinon None.
    """
    DM_IN_PROMPT  = 0x0004
    DM_OUT_BUFFER = 0x0002
    DM_IN_BUFFER  = 0x0008
    IDOK          = 1

    try:
        winspool = ctypes.WinDLL("winspool.drv")
        hPrinter = ctypes.wintypes.HANDLE()
        if not winspool.OpenPrinterW(printer_name, ctypes.byref(hPrinter), None):
            return None
        try:
            needed = winspool.DocumentPropertiesW(
                hwnd, hPrinter, printer_name, None, None, 0)
            if needed <= 0:
                return None

            buf_in  = ctypes.create_string_buffer(needed)
            buf_out = ctypes.create_string_buffer(needed)

            if current_devmode and len(current_devmode) <= needed:
                # Repartir du DEVMODE précédemment configuré (agrafe, finition…)
                buf_in[:len(current_devmode)] = current_devmode
            else:
                # Première ouverture : lire les defaults du driver
                winspool.DocumentPropertiesW(
                    hwnd, hPrinter, printer_name, buf_in, None, DM_OUT_BUFFER)

            result = winspool.DocumentPropertiesW(
                hwnd, hPrinter, printer_name, buf_out, buf_in,
                DM_IN_BUFFER | DM_IN_PROMPT | DM_OUT_BUFFER)

            if result != IDOK:
                return None
            return bytes(buf_out)   # DEVMODE modifié

        finally:
            winspool.ClosePrinter(hPrinter)

    except OSError:
        return None


# Structures GDI pour l'impression Win32 directe
class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize",          ctypes.wintypes.DWORD),
        ("biWidth",         ctypes.wintypes.LONG),
        ("biHeight",        ctypes.wintypes.LONG),
        ("biPlanes",        ctypes.wintypes.WORD),
        ("biBitCount",      ctypes.wintypes.WORD),
        ("biCompression",   ctypes.wintypes.DWORD),
        ("biSizeImage",     ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed",       ctypes.wintypes.DWORD),
        ("biClrImportant",  ctypes.wintypes.DWORD),
    ]

class _DOCINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize",       ctypes.c_int),
        ("lpszDocName",  ctypes.c_wchar_p),
        ("lpszOutput",   ctypes.c_wchar_p),
        ("lpszDatatype", ctypes.c_wchar_p),
        ("fwType",       ctypes.wintypes.DWORD),
    ]


class _GdiCtx:
    """Contexte GDI typé — évite la troncature des handles 64-bit."""

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    def __init__(self):
        g = ctypes.WinDLL("gdi32")
        H  = ctypes.wintypes.HANDLE
        I  = ctypes.c_int
        DW = ctypes.wintypes.DWORD
        VP = ctypes.c_void_p
        WP = ctypes.c_wchar_p

        g.CreateDCW.restype        = H;  g.CreateDCW.argtypes        = [WP, WP, WP, VP]
        g.DeleteDC.restype         = I;  g.DeleteDC.argtypes          = [H]
        g.GetDeviceCaps.restype    = I;  g.GetDeviceCaps.argtypes     = [H, I]
        g.StartDocW.restype        = I;  g.StartDocW.argtypes         = [H, VP]
        g.EndDoc.restype           = I;  g.EndDoc.argtypes            = [H]
        g.StartPage.restype        = I;  g.StartPage.argtypes         = [H]
        g.EndPage.restype          = I;  g.EndPage.argtypes           = [H]
        g.SetStretchBltMode.restype= I;  g.SetStretchBltMode.argtypes = [H, I]
        g.SetBrushOrgEx.restype    = I;  g.SetBrushOrgEx.argtypes     = [H, I, I, VP]
        g.StretchDIBits.restype    = I;  g.StretchDIBits.argtypes     = [
            H, I, I, I, I, I, I, I, I, VP, VP,
            ctypes.wintypes.UINT, DW]
        g.SetPolyFillMode.restype  = I;  g.SetPolyFillMode.argtypes   = [H, I]
        g.BeginPath.restype        = I;  g.BeginPath.argtypes         = [H]
        g.EndPath.restype          = I;  g.EndPath.argtypes           = [H]
        g.StrokePath.restype       = I;  g.StrokePath.argtypes        = [H]
        g.FillPath.restype         = I;  g.FillPath.argtypes          = [H]
        g.StrokeAndFillPath.restype= I;  g.StrokeAndFillPath.argtypes = [H]
        g.MoveToEx.restype         = I;  g.MoveToEx.argtypes          = [H, I, I, VP]
        g.LineTo.restype           = I;  g.LineTo.argtypes            = [H, I, I]
        g.PolyBezierTo.restype     = I;  g.PolyBezierTo.argtypes      = [H, VP, DW]
        g.PolyBezier.restype       = I;  g.PolyBezier.argtypes        = [H, VP, DW]
        g.Polygon.restype          = I;  g.Polygon.argtypes           = [H, VP, I]
        g.Polyline.restype         = I;  g.Polyline.argtypes          = [H, VP, I]
        g.CloseFigure.restype      = I;  g.CloseFigure.argtypes       = [H]
        g.CreatePen.restype        = H;  g.CreatePen.argtypes         = [I, I, DW]
        g.CreateSolidBrush.restype = H;  g.CreateSolidBrush.argtypes  = [DW]
        g.GetStockObject.restype   = H;  g.GetStockObject.argtypes    = [I]
        g.SelectObject.restype     = H;  g.SelectObject.argtypes      = [H, H]
        g.DeleteObject.restype     = I;  g.DeleteObject.argtypes      = [H]
        g.Rectangle.restype        = I;  g.Rectangle.argtypes         = [H, I, I, I, I]
        self.g = g

    def __getattr__(self, name):
        return getattr(self.g, name)


def _colorref(r, g, b) -> int:
    """Flottants RGB 0-1 → COLORREF GDI (BGR DWORD)."""
    return (int(r * 255) & 0xFF) | ((int(g * 255) & 0xFF) << 8) | ((int(b * 255) & 0xFF) << 16)


def _make_coord_transform(rotate_90: bool, angle: float, pw: float, ph: float, zoom: float, off_x: int, off_y: int):
    """Retourne une fonction (x_pdf, y_pdf) → (dc_x, dc_y) entiers."""
    if not rotate_90:
        def to_dc(x, y):
            return off_x + int(x * zoom), off_y + int(y * zoom)
    elif angle == -90:   # rotation CCW (bord long)
        def to_dc(x, y):
            return off_x + int(y * zoom), off_y + int((pw - x) * zoom)
    else:                # rotation CW (bord court)
        def to_dc(x, y):
            return off_x + int((ph - y) * zoom), off_y + int(x * zoom)
    return to_dc


def _draw_vector_strokes(gdi: _GdiCtx, hDC, pdf_page: fitz.Page,
                          zoom_dest: float, zoom_native: float,
                          rotate_90: bool, angle: float,
                          page_w: int, page_h: int):
    """
    Sur-impression vectorielle des TRAITS uniquement (pas de remplissages).

    Après le fond raster (texte, images, couleurs de fond), on redessine
    chaque chemin tracé (stroke) avec GDI en normalisant la largeur du stylo
    sur ``zoom_native`` (résolution A4 native).

    Effet : un trait de 0.5 pt issu d'un plan A3 réduit à A4 a la même
    épaisseur physique sur papier qu'un trait de 0.5 pt d'un plan A4 natif,
    parce que ``pen_px = max(1, round(width * zoom_native))`` est indépendant
    du facteur de réduction A3→A4.

    Les remplissages (zones colorées, fonds de cellules Excel…) restent ceux
    du fond raster — seuls les traits sont redessinés.
    """
    PS_SOLID = 0

    pw = pdf_page.rect.width
    ph = pdf_page.rect.height
    eff_w = int((ph if rotate_90 else pw) * zoom_dest)
    eff_h = int((pw if rotate_90 else ph) * zoom_dest)
    off_x = max(0, (page_w - eff_w) // 2)
    off_y = max(0, (page_h - eff_h) // 2)
    to_dc = _make_coord_transform(rotate_90, angle, pw, ph, zoom_dest, off_x, off_y)

    # extended=True traverse les Form XObjects (ex: cartouche AutoCAD = bloc)
    drawings = pdf_page.get_drawings(extended=True)
    _log.debug("_draw_vector_strokes page=%s drawings=%d off=(%d,%d) zoom_dest=%.3f zoom_native=%.3f",
               pdf_page.number, len(drawings), off_x, off_y, zoom_dest, zoom_native)

    # Plans avec une image occupant > 15 % de la page (photo aérienne, fond scanné) :
    # le raster seul suffit — ne pas confondre avec un logo dans le cartouche
    # qui n'occupe que quelques pourcents.
    page_area = pw * ph
    for img_info in pdf_page.get_image_info(xrefs=False):
        bbox = img_info.get('bbox')
        if bbox:
            iw = bbox[2] - bbox[0]
            ih = bbox[3] - bbox[1]
            if iw * ih > 0.50 * page_area:
                _log.debug("  large image (%.0f%% page > 50%%) → skip vector overlay",
                           100 * iw * ih / page_area)
                return

    # Seuil : documents simples (Excel, Word, PDF standard) n'ont que quelques
    # dizaines de paths de bordure — l'overlay 5 px les épaissit trop.
    # Les plans AutoCAD ont typiquement plusieurs milliers de drawings.
    if len(drawings) < 500:
        return

    POINT = _GdiCtx._POINT
    NULL_BRUSH_OBJ = gdi.GetStockObject(5)   # NULL_BRUSH
    old_brush = gdi.SelectObject(hDC, NULL_BRUSH_OBJ)

    strokes_drawn = 0
    skipped = 0

    for path in drawings:
        # Hachures AutoCAD avec clippath → ignorer (le raster suffit)
        if path.get('clip') is not None:
            skipped += 1
            continue

        items = path.get('items', [])
        if not items:
            continue

        # Hachure multi-segments dans un seul path (> 30 lignes parallèles)
        if len(items) > 30 and all(it[0] == 'l' for it in items):
            skipped += 1
            continue

        width  = path.get('width') or 0
        color  = path.get('color')

        # Seuls les paths avec stroke color explicite sont retracés.
        if not bool(color) or width < 0:
            skipped += 1
            continue

        # --- Collecter les segments du path --------------------------------
        segments: list[tuple[int,int,int,int]] = []

        for item in items:
            k = item[0]
            if k == 'l':
                x0, y0 = to_dc(item[1].x, item[1].y)
                x1, y1 = to_dc(item[2].x, item[2].y)
                segments.append((x0, y0, x1, y1))
            elif k == 're':
                r = item[1]
                rx0, ry0 = to_dc(r.x0, r.y0)
                rx1, ry1 = to_dc(r.x1, r.y1)
                segments += [(rx0, ry0, rx1, ry0), (rx1, ry0, rx1, ry1),
                              (rx1, ry1, rx0, ry1), (rx0, ry1, rx0, ry0)]
            elif k == 'qu':
                q = item[1]   # fitz.Quad : ul, ur, ll, lr
                corners = [to_dc(q.ul.x, q.ul.y), to_dc(q.ur.x, q.ur.y),
                           to_dc(q.lr.x, q.lr.y), to_dc(q.ll.x, q.ll.y)]
                for i in range(4):
                    x0, y0 = corners[i]
                    x1, y1 = corners[(i + 1) % 4]
                    segments.append((x0, y0, x1, y1))
            elif k == 'c':
                # Bézier cubique : approximation en 8 segments de ligne
                p0 = item[1]; p1 = item[2]; p2 = item[3]; p3 = item[4]
                prev = to_dc(p0.x, p0.y)
                for t_i in range(1, 9):
                    t = t_i / 8
                    mt = 1 - t
                    bx = mt**3*p0.x + 3*mt**2*t*p1.x + 3*mt*t**2*p2.x + t**3*p3.x
                    by = mt**3*p0.y + 3*mt**2*t*p1.y + 3*mt*t**2*p2.y + t**3*p3.y
                    cur = to_dc(bx, by)
                    segments.append((*prev, *cur))
                    prev = cur

        # --- Dessin stroke uniquement (MoveToEx/LineTo / Polyline) -------
        stroke_color = color
        if stroke_color and segments:
            pen_px = max(5, round(width * zoom_native))
            cr_pen = _colorref(*stroke_color[:3])
            hPen   = gdi.CreatePen(PS_SOLID, pen_px, cr_pen)
            old_pen = gdi.SelectObject(hDC, hPen)

            # Regrouper les segments consécutifs en chaînes → Polyline GDI
            # pour éviter les pâtés aux jonctions (caps carrés qui se chevauchent).
            chain: list[tuple[int,int]] = [(segments[0][0], segments[0][1]),
                                           (segments[0][2], segments[0][3])]
            for sx0, sy0, sx1, sy1 in segments[1:]:
                if (sx0, sy0) == chain[-1]:
                    chain.append((sx1, sy1))
                else:
                    arr = (POINT * len(chain))(*(POINT(x, y) for x, y in chain))
                    gdi.Polyline(hDC, ctypes.cast(arr, ctypes.c_void_p), len(chain))
                    chain = [(sx0, sy0), (sx1, sy1)]
            arr = (POINT * len(chain))(*(POINT(x, y) for x, y in chain))
            gdi.Polyline(hDC, ctypes.cast(arr, ctypes.c_void_p), len(chain))

            gdi.SelectObject(hDC, old_pen)
            gdi.DeleteObject(hPen)
            strokes_drawn += 1

    gdi.SelectObject(hDC, old_brush)
    _log.debug("  strokes_drawn=%d skipped=%d", strokes_drawn, skipped)


def _win32_print(printer_name: str, devmode_bytes: bytes | None,
                  doc_bytes: bytes, pages: list[int],
                  scale_mode: str, use_landscape: bool,
                  flip_long_edge: bool,
                  doc_name: str,
                  progress_cb=None) -> bool:
    """
    Impression via Win32 GDI directement, avec DEVMODE personnalisé.

    Stratégie hairline : rendu PyMuPDF à 1/UPSAMPLE de la résolution cible,
    puis StretchDIBits HALFTONE upscale ×UPSAMPLE.  Les traits fins (0–0.25 pt)
    atteignent le minimum 1 px de fitz à cette résolution réduite et
    ressortent UPSAMPLE× plus larges après upscale — visibles sur toute
    imprimante sans altérer texte ni images.
    """
    LOGPIXELSX     = 88
    HORZRES        = 8
    VERTRES        = 10
    DIB_RGB_COLORS = 0
    SRCCOPY        = 0x00CC0020
    HALFTONE       = 4

    kernel32 = ctypes.WinDLL("kernel32")
    gdi = _GdiCtx()

    devmode_ptr = None
    devmode_buf = None
    if devmode_bytes:
        devmode_buf = ctypes.create_string_buffer(devmode_bytes)
        devmode_ptr = ctypes.cast(devmode_buf, ctypes.c_void_p)

    hDC = gdi.CreateDCW("WINSPOOL", printer_name, None, devmode_ptr)
    if not hDC:
        _log.error("CreateDCW failed for %r — Win32 error %d",
                   printer_name, kernel32.GetLastError())
        return False

    fitz_doc = fitz.open(stream=doc_bytes, filetype="pdf")
    try:
        dpi    = gdi.GetDeviceCaps(hDC, LOGPIXELSX) or 300
        page_w = gdi.GetDeviceCaps(hDC, HORZRES)
        page_h = gdi.GetDeviceCaps(hDC, VERTRES)
        dc_is_portrait = page_w <= page_h

        gdi.SetStretchBltMode(hDC, HALFTONE)
        gdi.SetBrushOrgEx(hDC, 0, 0, None)

        doc_info = _DOCINFOW()
        doc_info.cbSize       = ctypes.sizeof(_DOCINFOW)
        doc_info.lpszDocName  = doc_name
        doc_info.lpszOutput   = None
        doc_info.lpszDatatype = None
        doc_info.fwType       = 0

        if gdi.StartDocW(hDC, ctypes.byref(doc_info)) <= 0:
            return False

        ok    = True
        total = len(pages)
        for n, page_i in enumerate(pages):
            if progress_cb:
                progress_cb(n, total)

            if gdi.StartPage(hDC) <= 0:
                ok = False
                break

            pdf_page  = fitz_doc[page_i]
            pdf_land  = _page_is_landscape(pdf_page)
            rotate_90 = pdf_land == dc_is_portrait
            angle     = (-90 if flip_long_edge else 90) if rotate_90 else 0

            pw = pdf_page.rect.width
            ph = pdf_page.rect.height
            eff_w = ph if rotate_90 else pw
            eff_h = pw if rotate_90 else ph

            base_zoom = dpi / 72.0
            if scale_mode == "ajuster":
                zoom = min(page_w / eff_w, page_h / eff_h)
            elif scale_mode == "reduire":
                zoom = min(min(page_w / eff_w, page_h / eff_h), base_zoom)
            else:
                zoom = base_zoom

            # Raster à demi-résolution (UPSAMPLE=2) puis StretchDIBits ×2.
            # Les traits fins (0.25–1 pt) ressortent 2× plus épais qu'en 1:1,
            # sans l'excès de UPSAMPLE=5 (texte encore très lisible).
            # La sur-impression vectorielle (min 5 px) prend le relais pour
            # les traits qui resteraient trop fins après l'upscale.
            UPSAMPLE  = 2
            zoom_dest = zoom
            zoom_render = max(base_zoom, zoom_dest) / UPSAMPLE

            mat = (fitz.Matrix(zoom_render, zoom_render).prerotate(angle)
                   if rotate_90 else fitz.Matrix(zoom_render, zoom_render))
            pix = pdf_page.get_pixmap(matrix=mat, alpha=False)

            img_w, img_h = pix.width, pix.height
            dest_w = min(int(eff_w * zoom_dest), page_w)
            dest_h = min(int(eff_h * zoom_dest), page_h)
            dst_x  = max(0, (page_w - dest_w) // 2)
            dst_y  = max(0, (page_h - dest_h) // 2)

            raw = bytearray(pix.samples)
            raw[0::3], raw[2::3] = raw[2::3], raw[0::3]   # RGB → BGR

            src_stride = img_w * 3
            gdi_stride = (src_stride + 3) & ~3
            if gdi_stride != src_stride:
                padded = bytearray(gdi_stride * img_h)
                for row in range(img_h):
                    s = row * src_stride
                    d = row * gdi_stride
                    padded[d:d + src_stride] = raw[s:s + src_stride]
                raw = padded

            buf = ctypes.create_string_buffer(bytes(raw))
            bmi = _BITMAPINFOHEADER()
            bmi.biSize          = ctypes.sizeof(_BITMAPINFOHEADER)
            bmi.biWidth         = img_w
            bmi.biHeight        = -img_h
            bmi.biPlanes        = 1
            bmi.biBitCount      = 24
            bmi.biCompression   = 0
            bmi.biSizeImage     = 0
            bmi.biXPelsPerMeter = int(dpi / UPSAMPLE * 39.3701)
            bmi.biYPelsPerMeter = int(dpi / UPSAMPLE * 39.3701)
            bmi.biClrUsed       = bmi.biClrImportant = 0

            gdi.StretchDIBits(
                hDC, dst_x, dst_y, dest_w, dest_h,
                0, 0, img_w, img_h,
                ctypes.cast(buf, ctypes.c_void_p),
                ctypes.cast(ctypes.pointer(bmi), ctypes.c_void_p),
                DIB_RGB_COLORS, SRCCOPY,
            )

            # Sur-impression vectorielle traits min 5 px.
            # pen_px normalisé sur zoom_native (résolution A4) → A3→A4 = A4 natif.
            _draw_vector_strokes(gdi, hDC, pdf_page,
                                 zoom_dest, base_zoom,
                                 rotate_90, angle, page_w, page_h)

            gdi.EndPage(hDC)

        if progress_cb:
            progress_cb(total, total)
        gdi.EndDoc(hDC)
        return ok

    except Exception as e:
        import traceback
        print(f"[DBG] _win32_print EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        _log.exception("_win32_print error")
        return False

    finally:
        fitz_doc.close()
        gdi.DeleteDC(hDC)


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
        ok = _win32_print(**self._args,
                          progress_cb=lambda d, t: self.progress.emit(d, t))
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
