"""
ui/title_bar.py — Barre de titre personnalisée
================================================
Ce module fournit ``TitleBar``, la barre de titre custom de la fenêtre frameless.

Rôle et position
-----------------
``TitleBar`` remplace entièrement la barre de titre système Windows.
Elle est placée en premier dans le layout vertical de ``MainWindow``
et contient de gauche à droite :

1. **Logo** (22×22 px, scaled depuis le PNG)
2. **Nom de l'application** (grisé, discret)
3. **Séparateur vertical**
4. **QTabBar des documents** (un onglet par PDF ouvert)
5. **Bouton "+"** (ouvrir un PDF)
6. **Espace extensible** (zone de drag)
7. **Contrôles fenêtre** : Réduire / Agrandir / Fermer (icônes PNG custom)

Déplacement de la fenêtre
--------------------------
``mousePressEvent`` appelle ``startSystemMove()`` sur le handle de fenêtre natif.
Cette API Qt6 délègue au gestionnaire de fenêtres Windows, ce qui donne un
déplacement natif (snapback aux bords, multi-moniteur, accessibilité).

IMPORTANT : ``startSystemMove()`` est appelé sans vérifier si le clic est sur
un onglet ou un bouton, car ces widgets consomment l'événement avant qu'il
n'atteigne la TitleBar. Un clic sur un onglet → l'onglet gère l'événement.
Un clic sur la zone vide → la TitleBar reçoit l'événement et lance le déplacement.

Boutons de fermeture d'onglet
------------------------------
Qt's ``QTabBar`` avec ``setTabsClosable(True)`` utilise une icône système
invisible sur fond sombre. On utilise à la place des ``QPushButton`` custom
ajoutés via ``setTabButton(idx, RightSide, btn)``.

La connexion du bouton utilise une closure qui recherche l'index de l'onglet
**au moment du clic** (pas au moment de la création) via ``setTabButton()``
→ ``tabButton()`` lookup. Ceci est nécessaire car les index changent
quand des onglets sont fermés avant celui-ci.

Icônes des contrôles fenêtre
-----------------------------
Les icônes (PNG custom) sont chargées depuis ``assets/buttons/``.
``resource_path()`` assure la compatibilité dev/exe PyInstaller.
L'icône du bouton max bascule entre ``maximized.png`` et ``unmaximized.png``
via ``update_max_button(is_maximized)``.
"""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QTabBar,
    QFrame, QSizePolicy,
)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPainter, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize

ACCENT = "#6BBF4E"

# Style des boutons de contrôle fenêtre (min/max) — fond hover gris sombre
_CTRL_BASE = """
QPushButton {
    background: transparent;
    border: none;
    padding: 4px 6px;
}
QPushButton:hover  { background: #2E2E2E; border-radius: 6px; }
QPushButton:pressed { background: #222222; border-radius: 6px; }
"""

# Style du bouton Fermer — fond hover rouge (convention Windows)
_CLOSE_BTN = """
QPushButton {
    background: transparent;
    border: none;
    padding: 4px 6px;
}
QPushButton:hover  { background: #6B1010; border-radius: 6px; }
QPushButton:pressed { background: #4A0A0A; border-radius: 6px; }
"""

# Style du QTabBar des documents ouverts
_TAB_STYLE = f"""
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: #1E1E1E;
    color: #888888;
    padding: 4px 14px 4px 14px;
    border: none;
    border-right: 1px solid #2A2A2A;
    min-width: 80px;
    max-width: 200px;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background: #2D2D2D;
    color: #F0F0F0;
}}
QTabBar::tab:hover:!selected {{
    background: #252525;
    color: #CCCCCC;
}}
QTabBar::close-button {{
    image: none;       /* désactiver l'icône système — on utilise des QPushButton custom */
    subcontrol-position: right;
}}
"""


class TitleBar(QWidget):
    """
    Barre de titre personnalisée pour la fenêtre frameless.

    Signals
    -------
    minimize_requested : pyqtSignal()
        Connecté à ``MainWindow.showMinimized()``.
    maximize_requested : pyqtSignal()
        Connecté à ``MainWindow._toggle_maximize()``.
    close_requested : pyqtSignal()
        Connecté à ``MainWindow.close()``.
    new_tab_requested : pyqtSignal()
        Connecté à ``MainWindow._open_file_dialog()``.
    tab_close_requested : pyqtSignal(int)
        Émis avec l'index de l'onglet à fermer.
        Connecté à ``MainWindow._close_tab()``.
    tab_changed : pyqtSignal(int)
        Émis quand l'utilisateur clique sur un onglet.
        Connecté à ``MainWindow._switch_to()``.

    Class Attributes
    ----------------
    HEIGHT : int
        Hauteur fixe de la barre en pixels (38 px).
    """

    minimize_requested  = pyqtSignal()
    maximize_requested  = pyqtSignal()
    close_requested     = pyqtSignal()
    new_tab_requested   = pyqtSignal()
    tab_close_requested = pyqtSignal(int)
    tab_changed         = pyqtSignal(int)

    HEIGHT = 38

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setStyleSheet("background: #141414;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo ──────────────────────────────────────────────────────────────
        # Chargement via resource_path pour compatibilité dev/exe
        from pdf_equilibrist.utils import resource_path
        self._logo = QLabel()
        logo_path = resource_path("assets/logo/PDF-Equilibrist-logo.png")
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(
                22, 22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._logo.setPixmap(pix)
        self._logo.setFixedSize(26, 38)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._logo)

        # ── Nom de l'application ──────────────────────────────────────────────
        self._app_name = QLabel("PDF Equilibrist")
        self._app_name.setStyleSheet(
            "color: #606060; font-size: 11px; padding: 0 10px 0 4px;")
        layout.addWidget(self._app_name)

        # Séparateur visuel entre le nom et les onglets
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #2A2A2A; border: none;")
        layout.addWidget(sep)

        # ── QTabBar des documents ouverts ─────────────────────────────────────
        # setTabsClosable(False) : on gère les boutons ✕ manuellement
        # pour contrôler leur apparence (icône système invisible sur fond sombre)
        self._tabs = QTabBar()
        self._tabs.setTabsClosable(False)
        self._tabs.setMovable(False)
        self._tabs.setExpanding(False)
        self._tabs.setDrawBase(False)
        self._tabs.setStyleSheet(_TAB_STYLE)
        self._tabs.setUsesScrollButtons(True)  # flèches si trop d'onglets
        self._tabs.currentChanged.connect(self.tab_changed)
        layout.addWidget(self._tabs)

        # ── Bouton "+" : ouvrir un nouveau PDF ───────────────────────────────
        self._btn_new = QPushButton("+")
        self._btn_new.setFixedSize(32, 38)
        self._btn_new.setStyleSheet(_CTRL_BASE)
        self._btn_new.setToolTip("Ouvrir un PDF (Ctrl+O)")
        self._btn_new.clicked.connect(self.new_tab_requested)
        layout.addWidget(self._btn_new)

        # Espace extensible = zone de drag (reçoit mousePressEvent)
        layout.addStretch(1)

        # ── Contrôles fenêtre ─────────────────────────────────────────────────
        # Icônes PNG custom depuis assets/buttons/
        _ASSETS = resource_path("assets/buttons")
        # Deux icônes pour le bouton max : état normal et état maximisé
        self._icon_max   = QIcon(str(_ASSETS / "maximized.png"))
        self._icon_unmax = QIcon(str(_ASSETS / "unmaximized.png"))

        self._btn_min   = QPushButton()
        self._btn_max   = QPushButton()
        self._btn_close = QPushButton()

        self._btn_min.setIcon(QIcon(str(_ASSETS / "reduce.png")))
        self._btn_max.setIcon(self._icon_max)
        self._btn_close.setIcon(QIcon(str(_ASSETS / "close.png")))

        BTN_W, BTN_H = 52, 30
        for btn in (self._btn_min, self._btn_max, self._btn_close):
            btn.setIconSize(QSize(BTN_W - 10, BTN_H - 8))
            btn.setFixedSize(BTN_W, BTN_H)

        self._btn_min.setToolTip("Réduire")
        self._btn_max.setToolTip("Agrandir / Restaurer")
        self._btn_close.setToolTip("Fermer")
        self._btn_min.setStyleSheet(_CTRL_BASE)
        self._btn_max.setStyleSheet(_CTRL_BASE)
        self._btn_close.setStyleSheet(_CLOSE_BTN)  # rouge au hover

        layout.addSpacing(4)
        for btn in (self._btn_min, self._btn_max, self._btn_close):
            layout.addWidget(btn)
        layout.addSpacing(4)

        self._btn_min.clicked.connect(self.minimize_requested)
        self._btn_max.clicked.connect(self.maximize_requested)
        self._btn_close.clicked.connect(self.close_requested)

    # ── API onglets ───────────────────────────────────────────────────────────

    def add_tab(self, title: str) -> int:
        """
        Ajoute un onglet avec un bouton de fermeture ✕ custom.

        Le bouton ✕ est un ``QPushButton`` ajouté via ``setTabButton()``
        sur le côté droit de l'onglet. Sa connexion recherche l'index
        dynamiquement au moment du clic (pas à la création) pour rester
        correct si des onglets précédents ont été fermés.

        Parameters
        ----------
        title : str
            Texte de l'onglet (généralement le nom du fichier PDF).

        Returns
        -------
        int
            Index du nouvel onglet (toujours le dernier).
        """
        idx = self._tabs.addTab(title)

        # Bouton ✕ custom : gris par défaut, blanc sur fond gris au hover
        btn = QPushButton("✕")
        btn.setFixedSize(16, 16)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #AAAAAA;
                border: none; font-size: 10px;
                border-radius: 3px; padding: 0;
            }
            QPushButton:hover { background: #555555; color: #FFFFFF; }
        """)
        # Lookup dynamique de l'index au moment du clic (pas à la création)
        btn.clicked.connect(lambda: self._on_close_btn(btn))
        self._tabs.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)
        self._tabs.setCurrentIndex(idx)
        return idx

    def _on_close_btn(self, btn: QPushButton):
        """
        Trouve l'index de l'onglet associé au bouton ✕ cliqué et émet
        ``tab_close_requested``.

        La recherche par référence d'objet (``is``) est nécessaire car
        les index changent dynamiquement quand des onglets sont fermés.
        """
        for i in range(self._tabs.count()):
            if self._tabs.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                self.tab_close_requested.emit(i)
                return

    def remove_tab(self, idx: int):
        """Supprime l'onglet à l'index donné (et son bouton ✕ associé)."""
        self._tabs.removeTab(idx)

    def set_tab_title(self, idx: int, title: str):
        """Met à jour le texte d'un onglet (ex. après renommage du fichier)."""
        if 0 <= idx < self._tabs.count():
            self._tabs.setTabText(idx, title)

    def current_index(self) -> int:
        """Retourne l'index de l'onglet actuellement sélectionné."""
        return self._tabs.currentIndex()

    def set_current_index(self, idx: int):
        """Sélectionne programmatiquement un onglet."""
        self._tabs.setCurrentIndex(idx)

    def tab_count(self) -> int:
        """Nombre d'onglets ouverts."""
        return self._tabs.count()

    def update_max_button(self, is_maximized: bool):
        """
        Bascule l'icône du bouton max entre état normal et état maximisé.

        Appelé par ``MainWindow.changeEvent`` pour rester synchronisé
        même quand la fenêtre est maximisée par des moyens externes
        (raccourci Windows, double-clic barre des tâches).

        Parameters
        ----------
        is_maximized : bool
            ``True`` → icône "restaurer" (deux fenêtres superposées).
            ``False`` → icône "agrandir" (carré simple).
        """
        self._btn_max.setIcon(
            self._icon_unmax if is_maximized else self._icon_max
        )

    # ── Drag et double-clic ───────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """
        Lance le déplacement natif de la fenêtre au clic gauche.

        ``startSystemMove()`` délègue au gestionnaire de fenêtres Windows :
        déplacement natif avec support AeroSnap, multi-moniteur et accessibilité.
        N'est appelé que si le clic arrive sur la TitleBar elle-même
        (les onglets et boutons consomment leurs propres events).
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event):
        """Double-clic sur la barre de titre → maximise/restaure la fenêtre."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
