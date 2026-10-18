"""Easter-egg : 7 clics sur le logo de la barre de titre lancent une courte pluie « Matrix » verte."""
from __future__ import annotations
import math
import random

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer

ACCENT = (107, 191, 78)   # vert du logo, #6BBF4E
CLICKS_NEEDED = 7
CLICK_WINDOW_MS = 2500    # délai max entre deux clics pour que la série continue
DURATION_MS = 4000
FRAME_MS = 45
CELL = 16                 # taille d'une colonne / d'un caractère (px)
GLYPHS = "01ABCDEF<>/|=+*"   # ASCII seulement : aucune police spéciale requise
# random sert uniquement à l'effet visuel (B311 : aucun usage cryptographique)


class MatrixRain(QWidget):
    """Calque transparent aux clics, posé sur une fenêtre, qui se détruit tout seul."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setGeometry(host.rect())
        self._cols = max(1, self.width() // CELL)
        self._heads = [random.uniform(-30, 0) for _ in range(self._cols)]  # nosec B311
        self._speeds = [random.uniform(0.5, 1.4) for _ in range(self._cols)]  # nosec B311
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(FRAME_MS)
        QTimer.singleShot(DURATION_MS, self._finish)
        self.show()
        self.raise_()

    def _step(self):
        self._tick += 1
        for i in range(self._cols):
            self._heads[i] += self._speeds[i]
        self.update()

    def _finish(self):
        self._timer.stop()
        self.hide()
        self.deleteLater()

    def paintEvent(self, _event):
        p = QPainter(self)
        font = QFont("Consolas")
        font.setPixelSize(CELL - 2)
        p.setFont(font)
        # Fondu d'entrée et de sortie + pulsation du vert d'accent
        t = self._tick * FRAME_MS / DURATION_MS
        fade = min(1.0, t * 6, (1 - t) * 6) if 0 <= t <= 1 else 0
        pulse = 0.75 + 0.25 * math.sin(self._tick * 0.35)
        rows = self.height() // CELL + 1
        for c in range(self._cols):
            head = int(self._heads[c])
            for k in range(14):                       # traînée de 14 caractères
                r = head - k
                if not 0 <= r < rows:
                    continue
                alpha = int(255 * fade * pulse * (1 - k / 14))
                col = QColor(255, 255, 255, alpha) if k == 0 else QColor(*ACCENT, alpha)
                p.setPen(col)
                p.drawText(c * CELL, r * CELL + CELL - 3, random.choice(GLYPHS))  # nosec B311
        p.end()


def trigger(window: QWidget) -> None:
    """Lance la pluie sur ``window`` (ignoré si une est déjà en cours)."""
    if window.findChild(MatrixRain) is None:
        MatrixRain(window)
