"""
tabs/tab_afficher.py — Onglet "Afficher" du ribbon
====================================================
Contrôles de visualisation : zoom et rotation des pages.

Zoom
----
- Niveaux discrets de 25 % à 400 % (11 paliers dans ``ZOOM_LEVELS``)
- Trois façons de changer le zoom :
  1. Boutons ``−`` / ``+`` → cran précédent/suivant
  2. Combo box → sélection directe
  3. ``Ctrl+molette`` dans le viewer → ``PdfViewer.zoom_changed`` → ``_on_viewer_zoom``
- La synchronisation bidirectionnelle est gérée par le flag ``_updating`` pour
  éviter les boucles infinies (combo → viewer → combo → viewer…)

Rotation
---------
Appelle ``operations.pages.rotate_pages()`` sur toutes les pages du document,
puis émet ``document.changed`` pour rafraîchir le viewer et les miniatures.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox
from PyQt6.QtCore import Qt
from pdf_equilibrist.ui.widgets import RibbonButton, RibbonGroup
from pdf_equilibrist.core.document import Document
from pdf_equilibrist.operations.pages import rotate_pages

ZOOM_LEVELS = [
    ("25 %",  0.25), ("33 %",  0.33), ("50 %",  0.50),
    ("67 %",  0.67), ("75 %",  0.75), ("100 %", 1.00),
    ("125 %", 1.25), ("150 %", 1.50), ("200 %", 2.00),
    ("300 %", 3.00), ("400 %", 4.00),
]
_ZOOM_VALUES = [z for _, z in ZOOM_LEVELS]
_DEFAULT_IDX = 5


class TabAfficher(QWidget):
    def __init__(self, document: Document, viewer):
        super().__init__()
        self.document  = document
        self.viewer    = viewer
        self._updating = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        # ── Groupe Zoom ──────────────────────────────────────────────────────
        self._btn_out = RibbonButton("−", "")
        self._btn_out.setFixedWidth(30)
        self._combo = QComboBox()
        self._combo.setFixedWidth(74)
        self._combo.setStyleSheet(
            "QComboBox { background:#2D2D2D; color:#F0F0F0;"
            " border:1px solid #3A3A3A; border-radius:4px; padding:2px 6px; }"
            "QComboBox::drop-down { border:none; }"
            "QComboBox QAbstractItemView { background:#2D2D2D; color:#F0F0F0; }"
        )
        for label, _ in ZOOM_LEVELS:
            self._combo.addItem(label)
        self._combo.setCurrentIndex(_DEFAULT_IDX)
        self._btn_in = RibbonButton("+", "")
        self._btn_in.setFixedWidth(30)

        grp_zoom = RibbonGroup("Zoom")
        grp_zoom.add(self._btn_out, self._combo, self._btn_in)
        layout.addWidget(grp_zoom)

        # ── Groupe Rotation ──────────────────────────────────────────────────
        self._btn_rot_l = RibbonButton("↺", "Gauche")
        self._btn_rot_r = RibbonButton("↻", "Droite")
        grp_rot = RibbonGroup("Rotation")
        grp_rot.add(self._btn_rot_l, self._btn_rot_r)
        layout.addWidget(grp_rot)

        # ── Groupe Impression ────────────────────────────────────────────────
        self._btn_print = RibbonButton("🖨", "Imprimer")
        grp_print = RibbonGroup("Impression")
        grp_print.add(self._btn_print)
        layout.addWidget(grp_print)

        layout.addStretch()

        # Connexions
        self._btn_out.clicked.connect(self._zoom_out)
        self._btn_in.clicked.connect(self._zoom_in)
        self._combo.currentIndexChanged.connect(self._on_combo)
        self._btn_rot_l.clicked.connect(lambda: self._rotate(-90))
        self._btn_rot_r.clicked.connect(lambda: self._rotate(90))
        self._btn_print.clicked.connect(self._print)
        self.viewer.zoom_changed.connect(self._on_viewer_zoom)

    def _zoom_out(self):
        idx = self._combo.currentIndex()
        if idx > 0:
            self._combo.setCurrentIndex(idx - 1)

    def _zoom_in(self):
        idx = self._combo.currentIndex()
        if idx < self._combo.count() - 1:
            self._combo.setCurrentIndex(idx + 1)

    def _on_combo(self, idx: int):
        if not self._updating:
            self.viewer.set_zoom(ZOOM_LEVELS[idx][1])

    def _on_viewer_zoom(self, zoom: float):
        closest = min(range(len(_ZOOM_VALUES)),
                      key=lambda i: abs(_ZOOM_VALUES[i] - zoom))
        self._updating = True
        self._combo.setCurrentIndex(closest)
        self._updating = False

    def _print(self):
        from pdf_equilibrist.ui.print_dialog import print_document
        print_document(self.document, self)

    def _rotate(self, angle: int):
        if not self.document.is_open:
            return
        self.document.checkpoint()
        rotate_pages(self.document.fitz_doc, angle)
        self.document.changed.emit()
