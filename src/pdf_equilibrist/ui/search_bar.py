"""
ui/search_bar.py — Barre de recherche de texte (Ctrl+F)
=========================================================
Widget horizontal glissé entre le ribbon et le viewer.
Utilise ``PdfViewer.search_in_doc()`` pour trouver les occurrences
et les surligner en jaune. Navigation entre résultats avec Entrée / ↑ ↓.
"""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QToolButton
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut


class SearchBar(QWidget):
    """
    Barre de recherche compacte — s'affiche sous le ribbon, cachée par défaut.

    Usage
    -----
    - ``toggle()`` : affiche ou cache la barre (Ctrl+F)
    - ``hide()``   : cache et efface les surlignages
    """

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer  = viewer
        self._results: list[tuple[int, list]] = []   # [(page_idx, [rects])]
        self._cur     = -1   # index courant dans _results

        self.setStyleSheet(
            "background: #252525; border-bottom: 1px solid #3A3A3A;")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Champ de saisie
        self._input = QLineEdit()
        self._input.setPlaceholderText("Rechercher dans le document…")
        self._input.setStyleSheet("""
            QLineEdit {
                background: #1E1E1E; color: #F0F0F0;
                border: 1px solid #444; border-radius: 3px;
                padding: 2px 6px; font-size: 12px;
            }
            QLineEdit:focus { border-color: #6BBF4E; }
        """)
        self._input.setFixedWidth(280)
        layout.addWidget(self._input)

        # Bouton précédent
        self._btn_prev = QToolButton()
        self._btn_prev.setText("▲")
        self._btn_prev.setToolTip("Résultat précédent (Maj+Entrée)")
        self._btn_prev.setStyleSheet(self._btn_style())
        layout.addWidget(self._btn_prev)

        # Bouton suivant
        self._btn_next = QToolButton()
        self._btn_next.setText("▼")
        self._btn_next.setToolTip("Résultat suivant (Entrée)")
        self._btn_next.setStyleSheet(self._btn_style())
        layout.addWidget(self._btn_next)

        # Compteur
        self._label = QLabel("")
        self._label.setStyleSheet("color: #888; font-size: 11px; min-width: 80px;")
        layout.addWidget(self._label)

        layout.addStretch()

        # Bouton fermer
        btn_close = QToolButton()
        btn_close.setText("✕")
        btn_close.setToolTip("Fermer (Échap)")
        btn_close.setStyleSheet(self._btn_style())
        layout.addWidget(btn_close)

        # ── Connexions ────────────────────────────────────────────────────────
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._next)
        self._btn_next.clicked.connect(self._next)
        self._btn_prev.clicked.connect(self._prev)
        btn_close.clicked.connect(self.close_bar)

        # Échap pour fermer
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self.close_bar)

        # Délai de recherche pour ne pas chercher à chaque frappe
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._run_search)

    @staticmethod
    def _btn_style() -> str:
        return """
            QToolButton {
                background: transparent; color: #AAAAAA;
                border: none; font-size: 12px; padding: 2px 6px;
                border-radius: 3px;
            }
            QToolButton:hover { background: #3A3A3A; color: #FFFFFF; }
        """

    # ── API publique ──────────────────────────────────────────────────────────

    def toggle(self):
        """Affiche la barre si cachée, la cache si visible."""
        if self.isHidden():
            self.show()
            self._input.setFocus()
            self._input.selectAll()
        else:
            self.close_bar()

    def close_bar(self):
        """Cache la barre et efface les surlignages."""
        self.hide()
        self._viewer.clear_search()
        self._results = []
        self._cur = -1
        self._label.setText("")

    # ── Recherche ─────────────────────────────────────────────────────────────

    def _on_text_changed(self):
        self._timer.start()   # relance le délai à chaque frappe

    def _run_search(self):
        text = self._input.text().strip()
        if not text:
            self._viewer.clear_search()
            self._results = []
            self._cur = -1
            self._label.setText("")
            return

        self._results = self._viewer.search_in_doc(text)
        total = sum(len(rects) for _, rects in self._results)

        if not self._results:
            self._label.setText("Aucun résultat")
            self._label.setStyleSheet("color: #E05555; font-size: 11px; min-width: 80px;")
            self._cur = -1
            return

        self._label.setStyleSheet("color: #888; font-size: 11px; min-width: 80px;")
        self._cur = 0
        self._scroll_to_current()
        self._update_label(total)

    def _next(self):
        if not self._results:
            return
        self._cur = (self._cur + 1) % len(self._results)
        self._scroll_to_current()
        self._update_label()

    def _prev(self):
        if not self._results:
            return
        self._cur = (self._cur - 1) % len(self._results)
        self._scroll_to_current()
        self._update_label()

    def _scroll_to_current(self):
        if 0 <= self._cur < len(self._results):
            page_idx, _ = self._results[self._cur]
            self._viewer.scroll_to_search_result(page_idx)

    def _update_label(self, total: int | None = None):
        if total is None:
            total = sum(len(r) for _, r in self._results)
        pages = len(self._results)
        self._label.setText(
            f"{total} résultat{'s' if total > 1 else ''} "
            f"sur {pages} page{'s' if pages > 1 else ''}"
        )
