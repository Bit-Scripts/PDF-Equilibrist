"""Splash screen PyQt6 — fond image + barre verte."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QLabel, QProgressBar, QVBoxLayout, QApplication
from PyQt6.QtGui import QPixmap, QColor, QPalette
from PyQt6.QtCore import Qt
from pdf_equilibrist import theme
from pdf_equilibrist.utils import resource_path

ACCENT   = "#6BBF4E"
W, H     = 600, 338   # taille fixe = même que splash PyInstaller
OVERLAY  = 54         # hauteur de la bande bas


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setFixedSize(W, H)

        light = theme.theme_name() == theme.LIGHT

        # ── Fond par défaut (noir, ou gris clair en thème clair) ──────────────
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#F3F3F3" if light else "#1E1E1E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        # ── Image de fond ─────────────────────────────────────────────────────
        bg = QLabel(self)
        bg.setGeometry(0, 0, W, H)
        pix = QPixmap()
        candidates = ["assets/splash.png", "assets/Splashscreen.jpg",
                      "assets/Splashscreen.png"]
        if light:
            candidates.insert(0, "assets/splash_light.png")
        for rel in candidates:
            path = resource_path(rel)
            if path.exists():
                pix.load(str(path))
                break
        if not pix.isNull():
            pix = pix.scaled(W, H,
                             Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            bg.setPixmap(pix)

        # ── Overlay bas ───────────────────────────────────────────────────────
        overlay = QWidget(self)
        overlay.setGeometry(0, H - OVERLAY, W, OVERLAY)
        overlay.setStyleSheet(
            "background: rgba(255,255,255,225);" if light
            else "background: rgba(10,10,10,220);")
        accent = theme.ACCENT_TEXT_LIGHT if light else ACCENT

        ov = QVBoxLayout(overlay)
        ov.setContentsMargins(14, 6, 14, 10)
        ov.setSpacing(5)

        self._status = QLabel(self.tr("Initialisation…"))
        self._status.setStyleSheet(
            f"color: {accent}; font-family:'Segoe UI'; font-size:11px;"
            "background:transparent;")
        ov.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(7)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background:{"#D6D6D6" if light else "#2A2A2A"}; border:none; border-radius:3px;
            }}
            QProgressBar::chunk {{
                background:{ACCENT}; border-radius:3px;
            }}
        """)
        ov.addWidget(self._bar)

        self._center()

    def _center(self):
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x() - W // 2,
                  geo.center().y() - H // 2)

    def set_progress(self, value: int, text: str = ""):
        self._bar.setValue(max(0, min(value, 100)))
        if text:
            self._status.setText(text)
        QApplication.processEvents()
