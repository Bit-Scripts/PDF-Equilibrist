"""Dialogue de sélection et placement de signature / tampon."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QFileDialog, QGridLayout,
    QSpinBox,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import fitz

ACCENT = "#6BBF4E"

DIALOG_STYLE = """
QDialog { background: #2D2D2D; color: #F0F0F0; }
QLabel  { color: #F0F0F0; }
QTabWidget::pane { border: 1px solid #3A3A3A; background: #2D2D2D; }
QTabBar::tab {
    background: #1E1E1E; color: #AAAAAA;
    padding: 5px 16px; border: none;
}
QTabBar::tab:selected { background: #2D2D2D; color: #F0F0F0; }
QSpinBox {
    background: #1E1E1E; color: #F0F0F0;
    border: 1px solid #3A3A3A; border-radius: 4px; padding: 3px 6px;
}
QPushButton {
    background: #3A3A3A; color: #F0F0F0;
    border: 1px solid #4A4A4A; border-radius: 4px; padding: 5px 14px;
}
QPushButton:hover { background: #4A4A4A; }
QPushButton#primary {
    background: #6BBF4E; color: #1E1E1E; font-weight: bold; border: none;
}
QPushButton#primary:hover { background: #7ED45F; }
"""

# Tampons prédéfinis : (label, couleur RGB 0-1, texte PDF)
STAMPS = [
    ("✓  Validé",        (0.0, 0.55, 0.15), "✓  VALIDÉ"),
    ("⚠  À revoir",      (0.8, 0.5,  0.0),  "⚠  À REVOIR"),
    ("✗  Rejeté",        (0.8, 0.0,  0.0),  "✗  REJETÉ"),
    ("🔒  Confidentiel", (0.4, 0.0,  0.6),  "CONFIDENTIEL"),
    ("✔  Approuvé",      (0.0, 0.4,  0.7),  "✔  APPROUVÉ"),
    ("📋  Brouillon",    (0.5, 0.5,  0.5),  "BROUILLON"),
]


class _StampBtn(QPushButton):
    def __init__(self, label: str, color: tuple, parent=None):
        super().__init__(label, parent)
        r, g, b = (int(c * 255) for c in color)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: rgb({r},{g},{b});
                border: 2px solid rgb({r},{g},{b});
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba({r},{g},{b},40);
            }}
            QPushButton:pressed {{
                background: rgba({r},{g},{b},80);
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SignatureDialog(QDialog):
    """
    Retourne via .result() un dict :
      {'type': 'stamp', 'text': str, 'color': tuple, 'page': int, 'x': int, 'y': int}
      {'type': 'image', 'path': str, 'page': int, 'x': int, 'y': int, 'w': int, 'h': int}
    """

    def __init__(self, doc: fitz.Document, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Signature / Tampon")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(420)
        self._doc    = doc
        self._result = None

        layout = QVBoxLayout(self)

        # ── Tabs ─────────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.addTab(self._make_stamp_tab(), "Tampons prédéfinis")
        tabs.addTab(self._make_image_tab(), "Signature PNG")
        layout.addWidget(tabs)

        # ── Position ─────────────────────────────────────────────────────────
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Page :"))
        self._spin_page = QSpinBox()
        self._spin_page.setRange(1, len(doc))
        self._spin_page.setValue(1)
        pos_row.addWidget(self._spin_page)

        pos_row.addSpacing(16)
        pos_row.addWidget(QLabel("X :"))
        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 1000)
        self._spin_x.setValue(50)
        pos_row.addWidget(self._spin_x)

        pos_row.addWidget(QLabel("Y :"))
        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 1000)
        self._spin_y.setValue(50)
        pos_row.addWidget(self._spin_y)
        pos_row.addStretch()
        layout.addLayout(pos_row)

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    # ── Tab Tampons ───────────────────────────────────────────────────────────

    def _make_stamp_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #2D2D2D;")
        grid = QGridLayout(w)
        grid.setSpacing(8)
        grid.setContentsMargins(12, 12, 12, 12)
        for i, (label, color, pdf_text) in enumerate(STAMPS):
            btn = _StampBtn(label, color)
            btn.clicked.connect(
                lambda _, c=color, t=pdf_text: self._apply_stamp(c, t))
            grid.addWidget(btn, i // 2, i % 2)
        return w

    def _apply_stamp(self, color: tuple, text: str):
        self._result = {
            "type":  "stamp",
            "text":  text,
            "color": color,
            "page":  self._spin_page.value() - 1,
            "x":     self._spin_x.value(),
            "y":     self._spin_y.value(),
        }
        self.accept()

    # ── Tab Image ─────────────────────────────────────────────────────────────

    def _make_image_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #2D2D2D;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        self._img_preview = QLabel("Aucune image sélectionnée")
        self._img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_preview.setFixedHeight(120)
        self._img_preview.setStyleSheet(
            "border: 1px dashed #4A4A4A; border-radius: 6px; color: #666666;")
        layout.addWidget(self._img_preview)

        self._img_path: str | None = None

        btn_pick = QPushButton("📁  Choisir une image PNG / JPG…")
        btn_pick.clicked.connect(self._pick_image)
        layout.addWidget(btn_pick)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Largeur :"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(10, 500)
        self._spin_w.setValue(150)
        size_row.addWidget(self._spin_w)
        size_row.addWidget(QLabel("px   Hauteur :"))
        self._spin_h = QSpinBox()
        self._spin_h.setRange(10, 500)
        self._spin_h.setValue(80)
        size_row.addWidget(self._spin_h)
        size_row.addStretch()
        layout.addLayout(size_row)

        self._btn_insert_img = QPushButton("Insérer la signature")
        self._btn_insert_img.setObjectName("primary")
        self._btn_insert_img.setEnabled(False)
        self._btn_insert_img.clicked.connect(self._apply_image)
        layout.addWidget(self._btn_insert_img)
        layout.addStretch()
        return w

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une signature", "",
            "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self._img_path = path
            pix = QPixmap(path).scaledToHeight(
                100, Qt.TransformationMode.SmoothTransformation)
            self._img_preview.setPixmap(pix)
            self._btn_insert_img.setEnabled(True)

    def _apply_image(self):
        if not self._img_path:
            return
        self._result = {
            "type": "image",
            "path": self._img_path,
            "page": self._spin_page.value() - 1,
            "x":    self._spin_x.value(),
            "y":    self._spin_y.value(),
            "w":    self._spin_w.value(),
            "h":    self._spin_h.value(),
        }
        self.accept()

    def get_result(self) -> dict | None:
        return self._result
