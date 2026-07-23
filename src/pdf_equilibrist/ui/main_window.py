"""
ui/main_window.py — Fenêtre principale de PDF-Equilibrist
==========================================================
Ce module contient ``MainWindow``, le widget racine de l'application.

Fenêtre frameless
-----------------
``MainWindow`` hérite de ``QWidget`` (et non ``QMainWindow``) avec le flag
``FramelessWindowHint``. Cela supprime la barre de titre et les bordures
système pour permettre un design personnalisé :

- ``TitleBar`` custom en haut (logo, onglets documents, contrôles fenêtre)
- Bordure 1px dessinée dans ``paintEvent``
- Déplacement via ``TitleBar.mousePressEvent`` → ``startSystemMove()``
- Redimensionnement via ``mousePressEvent`` sur les bords → ``startSystemResize()``
  (API Qt6 native qui délègue au gestionnaire de fenêtres Windows, AeroSnap inclus)

Gestion multi-documents
------------------------
``MainWindow`` maintient une liste de ``Document`` (un par onglet ouvert) ::

    _documents : list[Document]   ← tous les PDFs ouverts
    _active_idx : int             ← index du doc affiché dans _documents
    _current_doc : Document       ← référence directe au doc actif (rebindée)

Quand l'utilisateur change d'onglet, ``_switch_to(idx)`` appelle ``_rebind_doc(doc)``
qui :
1. Déconnecte **tous** les signaux de l'ancien document (``old.changed.disconnect()``)
2. Reconnecte les signaux du nouveau document vers :
   - ``self._on_doc_changed`` (barre de statut, titre d'onglet, actions menu)
   - ``viewer._on_doc_changed`` (rafraîchissement des pages)
   - ``_thumbs.rebuild`` (rafraîchissement des miniatures)
3. Repointe ``document`` sur tous les tabs du ribbon (référence directe)
4. Force un refresh immédiat du viewer et des miniatures

Ribbon
------
Le ribbon est implémenté avec ``QTabBar`` + ``QStackedWidget`` séparés
(et non ``QTabWidget``) pour un contrôle total sur les hauteurs et marges :

- ``_ribbon_tabbar`` : barre d'onglets (Afficher, Modifier, Convertir…)
- ``_ribbon_stack``  : widget empilé contenant le contenu de chaque onglet

Résolution des chemins
-----------------------
Le viewer et le panneau miniatures accèdent aux assets via ``resource_path()``
de ``utils.py`` pour la compatibilité dev/exe PyInstaller.
"""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTabBar, QStackedWidget, QFileDialog, QLabel, QSplitter,
)
from PyQt6.QtGui import QAction, QKeySequence, QColor, QPainter, QPen
from PyQt6.QtCore import Qt, QPoint, QSettings, QThread, pyqtSignal

_RECENT_MAX = 10   # nombre maximum de fichiers dans "Ouvrir récemment"

from pdf_equilibrist.ui.title_bar import TitleBar
from pdf_equilibrist.ui.tabs.tab_afficher  import TabAfficher
from pdf_equilibrist.ui.tabs.tab_modifier  import TabModifier
from pdf_equilibrist.ui.tabs.tab_convertir import TabConvertir
from pdf_equilibrist.ui.tabs.tab_annoter   import TabAnnoter
from pdf_equilibrist.ui.tabs.tab_page      import TabPage
from pdf_equilibrist.ui.tabs.tab_proteger  import TabProteger
from pdf_equilibrist.ui.viewer             import PdfViewer
from pdf_equilibrist.ui.thumbnail_panel    import ThumbnailPanel
from pdf_equilibrist.core.document         import Document

ACCENT       = "#6BBF4E"
BORDER_COLOR = "#2A2A2A"
RESIZE_MARGIN = 6

TABBAR_STYLE = """
QTabBar { background: #1A1A1A; padding: 3px 4px 0 4px; }
QTabBar::tab {
    background: transparent; color: #888888;
    padding: 5px 18px; border: none;
    border-radius: 5px 5px 0 0;
    font-size: 12px; font-family: "Segoe UI"; margin-right: 2px;
}
QTabBar::tab:selected { background: #2D2D2D; color: #F0F0F0; }
QTabBar::tab:hover:!selected { background: #242424; color: #C0C0C0; }
"""


class _StartupUpdateCheckThread(QThread):
    """Vérifie en arrière-plan si une nouvelle version est disponible, sans
    bloquer le démarrage ni afficher quoi que ce soit tant qu'on ne sait pas."""
    found = pyqtSignal(object)   # dict de la release si plus récente, sinon None

    def run(self):
        try:
            from pdf_equilibrist import __version__
            from pdf_equilibrist import update as updater
            release = updater.get_latest_release_info(__version__)
        except Exception:
            release = None
        self.found.emit(release)


class MainWindow(QWidget):
    """
    Fenêtre principale frameless de PDF-Equilibrist.

    Hérite de ``QWidget`` (pas ``QMainWindow``) pour permettre un design
    entièrement personnalisé sans chrome système.

    Layout vertical de haut en bas ::

        TitleBar          ← drag fenêtre, onglets docs, min/max/close
        QMenuBar          ← Fichier (Ouvrir, Enregistrer…)
        Ribbon            ← QTabBar + QStackedWidget (6 onglets fonctions)
        QSplitter         ← ThumbnailPanel (gauche) + PdfViewer (droite)
        Status bar        ← chemin fichier + nombre de pages

    Attributes
    ----------
    viewer : PdfViewer
        Widget de rendu PDF. Partagé entre tous les onglets documents —
        rebindé à chaque changement d'onglet via ``_rebind_doc()``.
    _documents : list[Document]
        Liste de tous les documents ouverts (un par onglet de la TitleBar).
    _active_idx : int
        Index dans ``_documents`` du document actuellement affiché. -1 si aucun.
    _current_doc : Document
        Référence directe au document actif. Rebindée par ``_rebind_doc()``.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Equilibrist")
        self.resize(1280, 800)
        self.setMinimumSize(800, 600)

        # Mode frameless : supprime la barre de titre et les bordures système.
        # WA_TranslucentBackground=False : fond opaque (nécessaire pour le thème sombre).
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # ── Gestion multi-documents ───────────────────────────────────────────
        self._documents: list[Document] = []  # un Document par onglet ouvert
        self._active_idx = -1                 # -1 = aucun document actif

        # ── Barre de titre ───────────────────────────────────────────────────
        self._title_bar = TitleBar(self)
        self._title_bar.minimize_requested.connect(self.showMinimized)
        self._title_bar.maximize_requested.connect(self._toggle_maximize)
        self._title_bar.close_requested.connect(self.close)
        self._title_bar.new_tab_requested.connect(self._open_file_dialog)
        self._title_bar.tab_close_requested.connect(self._close_tab)
        self._title_bar.tab_changed.connect(self._switch_to)

        # ── Viewer + Thumbnails (partagés, rebindés à chaque switch) ─────────
        # On crée un Document "vide" initial pour initialiser les widgets
        self._current_doc = Document()
        self.viewer  = PdfViewer(self._current_doc)
        self._thumbs = ThumbnailPanel(self._current_doc, self.viewer)
        self._thumbs.width_changed.connect(self._on_thumbs_width_changed)
        # Lien GOTOR dans un PDF → ouvrir dans un nouvel onglet
        self.viewer.open_pdf_requested.connect(self._open_document)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._thumbs)
        self._splitter.addWidget(self.viewer)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet("QSplitter::handle { background: #3A3A3A; }")

        # ── Ribbon ───────────────────────────────────────────────────────────
        TABBAR_H = 30
        STACK_H  = 84
        RIBBON_H = TABBAR_H + STACK_H

        self._ribbon_tabbar = QTabBar()
        self._ribbon_tabbar.setStyleSheet(TABBAR_STYLE)
        self._ribbon_tabbar.setExpanding(False)
        self._ribbon_tabbar.setDrawBase(False)
        self._ribbon_tabbar.setFixedHeight(TABBAR_H)

        self._ribbon_stack = QStackedWidget()
        self._ribbon_stack.setFixedHeight(STACK_H)
        self._ribbon_stack.setStyleSheet("background: #2D2D2D;")

        self._tab_afficher  = TabAfficher(self._current_doc, self.viewer)
        self._tab_modifier  = TabModifier(self._current_doc, self.viewer)
        self._tab_convertir = TabConvertir(self._current_doc)
        self._tab_annoter   = TabAnnoter(self._current_doc, self.viewer)
        self._tab_page      = TabPage(self._current_doc, self.viewer)
        self._tab_proteger  = TabProteger(self._current_doc)

        for name, widget in [
            ("Afficher",  self._tab_afficher),
            ("Modifier",  self._tab_modifier),
            ("Convertir", self._tab_convertir),
            ("Annoter",   self._tab_annoter),
            ("Page",      self._tab_page),
            ("Protéger",  self._tab_proteger),
        ]:
            self._ribbon_tabbar.addTab(name)
            widget.setStyleSheet("background: #2D2D2D;")
            self._ribbon_stack.addWidget(widget)

        self._ribbon_tabbar.currentChanged.connect(self._ribbon_stack.setCurrentIndex)

        ribbon = QWidget()
        ribbon.setStyleSheet("background: #1A1A1A; border-bottom: 1px solid #333;")
        ribbon.setFixedHeight(RIBBON_H)
        r_layout = QVBoxLayout(ribbon)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(0)
        r_layout.addWidget(self._ribbon_tabbar)
        sc = QWidget()
        sc.setStyleSheet("background: #2D2D2D;")
        sc_l = QHBoxLayout(sc)
        sc_l.setContentsMargins(0, 0, 0, 0)
        sc_l.addWidget(self._ribbon_stack)
        r_layout.addWidget(sc)

        # ── Menu bar ─────────────────────────────────────────────────────────
        self._menu_bar = self._build_menu_bar()

        # ── Status bar ───────────────────────────────────────────────────────
        self._status_file = QLabel("Aucun document ouvert")
        self._status_page = QLabel("")
        status = QWidget()
        status.setFixedHeight(22)
        status.setStyleSheet(
            "background: #141414; border-top: 1px solid #2A2A2A;")
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 0, 8, 0)
        sl.addWidget(self._status_file)
        sl.addStretch()
        sl.addWidget(self._status_page)
        self._status_file.setStyleSheet("color: #666666; font-size: 11px;")
        self._status_page.setStyleSheet("color: #666666; font-size: 11px;")

        # ── Barre de recherche (cachée par défaut) ────────────────────────────
        from pdf_equilibrist.ui.search_bar import SearchBar
        self._search_bar = SearchBar(self.viewer)
        self._search_bar.hide()

        # ── Layout principal ──────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)   # bordure 1px
        root.setSpacing(0)
        root.addWidget(self._title_bar)
        root.addWidget(self._menu_bar)
        root.addWidget(ribbon)
        root.addWidget(self._search_bar)
        root.addWidget(self._splitter, 1)
        root.addWidget(status)

        self._set_ribbon_enabled(False)
        self._resize_edge = ""
        self.setAcceptDrops(True)
        self._current_doc.changed.connect(self._on_doc_changed)

        # Géométrie du bouton max pour HTMAXBUTTON (Snap Layout hover)
        # Recalculée dans showEvent après rendu réel
        self._max_btn_rect_screen = None

    # ── Menu ─────────────────────────────────────────────────────────────────

    # ── showEvent : styles Win32 + Ctrl+P ────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self.setAcceptDrops(True)
        self._apply_win32_styles()

    def _apply_win32_styles(self):
        """
        Ajoute WS_THICKFRAME + WS_MAXIMIZEBOX + WS_MINIMIZEBOX au style Win32.

        Ces flags sont nécessaires pour :
        - **PowerToys FancyZones** : détecte la fenêtre comme redimensionnable
        - **Windows Snap** (Win+flèche, glisser bord écran) : activé par WS_THICKFRAME
        - **Snap Layout** (hover bouton max) : activé par WS_MAXIMIZEBOX
        - Toujours silencieux : une exception n'interrompt pas le démarrage.
        """
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_STYLE    = -16
            WS_THICKFRAME  = 0x00040000
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            # Forcer Windows à recalculer le cadre (nécessaire après SetWindowLong)
            SWP_FLAGS = 0x0027  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:  # nosec B110
            pass

    # ── Ctrl+P ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        from PyQt6.QtCore import Qt as _Qt
        mods = event.modifiers()
        ctrl = _Qt.KeyboardModifier.ControlModifier
        if event.key() == _Qt.Key.Key_P and mods == ctrl:
            self._print()
        elif event.key() == _Qt.Key.Key_Z and mods == ctrl:
            self._undo()
        elif event.key() == _Qt.Key.Key_F and mods == ctrl:
            self._search_bar.toggle()
        else:
            super().keyPressEvent(event)

    def _print(self):
        """Lance l'impression du document actif (Ctrl+P ou bouton Imprimer)."""
        if not self._current_doc.is_open:
            return
        from pdf_equilibrist.ui.print_dialog import print_document
        print_document(self._current_doc, self)

    def _undo(self):
        """Annule la dernière modification (Ctrl+Z)."""
        if self._current_doc.undo():
            self.viewer.clear_search()

    def _build_menu_bar(self) -> QWidget:
        from PyQt6.QtWidgets import QMenuBar
        mb = QMenuBar()
        mb.setStyleSheet("""
            QMenuBar { background:#1A1A1A; color:#AAAAAA;
                       border-bottom:1px solid #2A2A2A; padding:2px 0; }
            QMenuBar::item:selected { background:#2D2D2D; color:#FFFFFF; }
            QMenu { background:#2D2D2D; color:#F0F0F0; border:1px solid #3A3A3A; }
            QMenu::item:selected { background:#3A3A3A; }
            QMenu::separator { height:1px; background:#3A3A3A; margin:3px 0; }
        """)

        fichier = mb.addMenu("Fichier")

        act_open = QAction("Ouvrir…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_file_dialog)
        fichier.addAction(act_open)

        # Sous-menu "Ouvrir récemment" — peuplé dynamiquement
        self._recent_menu = fichier.addMenu("Ouvrir récemment")
        self._rebuild_recent_menu()
        fichier.addSeparator()

        self._act_print = QAction("Imprimer…", self)
        self._act_print.setShortcut(QKeySequence.StandardKey.Print)
        self._act_print.triggered.connect(self._print)
        fichier.addAction(self._act_print)
        fichier.addSeparator()

        self._act_save = QAction("Enregistrer", self)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save.triggered.connect(self._save)
        fichier.addAction(self._act_save)

        self._act_save_as = QAction("Enregistrer sous…", self)
        self._act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_save_as.triggered.connect(self._save_as)
        fichier.addAction(self._act_save_as)
        fichier.addSeparator()

        self._act_close_doc = QAction("Fermer l'onglet", self)
        self._act_close_doc.setShortcut(QKeySequence("Ctrl+W"))
        self._act_close_doc.triggered.connect(
            lambda: self._close_tab(self._active_idx))
        fichier.addAction(self._act_close_doc)
        fichier.addSeparator()

        act_quit = QAction("Quitter", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        fichier.addAction(act_quit)

        edition = mb.addMenu("Édition")
        self._act_undo = QAction("Annuler", self)
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.triggered.connect(self._undo)
        self._act_undo.setEnabled(False)
        edition.addAction(self._act_undo)

        act_search = QAction("Rechercher…", self)
        act_search.setShortcut(QKeySequence.StandardKey.Find)
        act_search.triggered.connect(lambda: self._search_bar.toggle())
        edition.addAction(act_search)

        # ── Aide / Mises à jour / Sécurité ──────────────────────────────────
        aide = mb.addMenu("Aide")
        act_updates = QAction("Vérifier les mises à jour…", self)
        act_updates.triggered.connect(self._check_for_updates)
        aide.addAction(act_updates)

        act_cve = QAction("Vérifier les vulnérabilités CVE…", self)
        act_cve.triggered.connect(self._check_for_cves)
        aide.addAction(act_cve)

        aide.addSeparator()

        # Même fenêtre que "Vérifier les mises à jour" : elle affiche déjà le
        # logo, la version et les mises à jour dans un seul dialogue.
        act_about = QAction("À propos de PDF-Equilibrist…", self)
        act_about.triggered.connect(self._check_for_updates)
        aide.addAction(act_about)

        return mb

    def check_updates_on_startup(self):
        """
        Vérifie silencieusement les mises à jour au démarrage.

        Contrairement à ``_check_for_updates()``, n'ouvre le dialogue que
        si une version plus récente est réellement disponible — sinon
        aucune fenêtre n'apparaît (vérification en arrière-plan uniquement).
        """
        self._startup_update_thread = _StartupUpdateCheckThread(self)
        self._startup_update_thread.found.connect(self._on_startup_update_found)
        self._startup_update_thread.start()

    def _on_startup_update_found(self, release: object | None):
        if release:
            self._check_for_updates()

    def _check_for_updates(self):
        """Ouvre le dialogue de vérification des mises à jour (non bloquant)."""
        try:
            from pdf_equilibrist.ui.update_dialog import UpdateDialog
            dlg = UpdateDialog(self)
            dlg.exec()
        except Exception as exc:
            # Ne doit pas empêcher l'application de fonctionner, mais on informe
            # l'utilisateur plutôt que d'échouer silencieusement.
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Vérification des mises à jour",
                                f"Impossible d'ouvrir le dialogue de mise à jour :\n{exc}")

    def _check_for_cves(self):
        """Ouvre le dialogue de vérification CVE des dépendances."""
        try:
            from pdf_equilibrist.ui.cve_dialog import CVEDialog
            dlg = CVEDialog(self)
            dlg.exec()
        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Vérification CVE",
                                f"Impossible d'ouvrir le dialogue CVE :\n{exc}")

    # ── Fichiers récents ──────────────────────────────────────────────────────

    def _add_recent(self, path: str):
        """Ajoute un chemin en tête de la liste des fichiers récents (QSettings)."""
        s = QSettings("PDFEquilibrist", "PDFEquilibrist")
        recents: list[str] = s.value("recent_files", []) or []
        # Dédupliquer et mettre en tête
        norm = str(Path(path))
        if norm in recents:
            recents.remove(norm)
        recents.insert(0, norm)
        recents = recents[:_RECENT_MAX]
        s.setValue("recent_files", recents)
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self):
        """Reconstruit le sous-menu "Ouvrir récemment" depuis QSettings."""
        self._recent_menu.clear()
        s = QSettings("PDFEquilibrist", "PDFEquilibrist")
        recents: list[str] = s.value("recent_files", []) or []
        # Filtrer les fichiers qui n'existent plus sur le disque
        recents = [r for r in recents if Path(r).exists()]
        if not recents:
            empty = QAction("(vide)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for path in recents:
            p = Path(path)
            act = QAction(p.name, self)
            act.setToolTip(str(p))
            act.setStatusTip(str(p))
            # Capturer path par valeur dans la lambda
            act.triggered.connect(lambda checked=False, fp=path: self._open_document(fp))
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        act_clear = QAction("Effacer l'historique", self)
        act_clear.triggered.connect(self._clear_recents)
        self._recent_menu.addAction(act_clear)

    def _clear_recents(self):
        """Vide la liste des fichiers récents."""
        QSettings("PDFEquilibrist", "PDFEquilibrist").remove("recent_files")
        self._rebuild_recent_menu()

    def _set_ribbon_enabled(self, enabled: bool):
        """Active ou désactive le ribbon et les actions de fichier.

        Appelé avec ``False`` quand aucun document n'est ouvert,
        ``True`` dès qu'un document est chargé. Empêche l'utilisateur
        d'interagir avec les outils sans document ouvert.
        """
        self._ribbon_stack.setEnabled(enabled)
        for act in (self._act_print, self._act_save,
                    self._act_save_as, self._act_close_doc):
            act.setEnabled(enabled)
        if not enabled:
            self._act_undo.setEnabled(False)

    # ── Gestion multi-documents ───────────────────────────────────────────────

    def _open_file_dialog(self):
        """Ouvre un dialogue de sélection de fichiers PDF (multi-sélection)."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ouvrir un PDF", "", "Fichiers PDF (*.pdf)")
        for path in paths:
            self._open_document(path)

    def _open_document(self, path: str):
        """
        Ouvre un PDF dans un nouvel onglet ou donne le focus à l'onglet existant.

        Si le fichier est déjà ouvert (même chemin absolu), ne crée pas un
        second onglet mais se contente de sélectionner l'onglet existant.

        Parameters
        ----------
        path : str
            Chemin absolu du fichier PDF à ouvrir.
        """
        # Éviter les doublons : si déjà ouvert, focus sur l'onglet existant
        for i, doc in enumerate(self._documents):
            if doc.path and str(doc.path) == path:
                self._title_bar.set_current_index(i)
                return

        # Créer un nouveau Document et l'ouvrir
        doc = Document()
        doc.open(path)
        self._documents.append(doc)
        idx = len(self._documents) - 1

        # Mémoriser dans les fichiers récents
        self._add_recent(path)

        # Ajouter l'onglet dans la TitleBar et basculer dessus
        self._title_bar.add_tab(Path(path).name)
        self._switch_to(idx)

    def _close_tab(self, idx: int):
        """
        Ferme un onglet et libère le Document associé.

        Si c'était le dernier onglet, rebinde un Document vide pour
        afficher l'écran d'accueil. Sinon, sélectionne l'onglet adjacent.

        Parameters
        ----------
        idx : int
            Index dans ``_documents`` de l'onglet à fermer.
        """
        if idx < 0 or idx >= len(self._documents):
            return

        self._documents[idx].close()  # libère fitz.Document (mémoire)
        self._documents.pop(idx)
        self._title_bar.remove_tab(idx)

        if not self._documents:
            # Plus aucun document : revenir à l'écran d'accueil
            self._active_idx = -1
            self._rebind_doc(Document())   # doc vide → welcome page
            self._set_ribbon_enabled(False)
            self._update_status()
        else:
            # Sélectionner l'onglet le plus proche (sans dépasser la liste)
            new_idx = min(idx, len(self._documents) - 1)
            self._title_bar.set_current_index(new_idx)

    def _switch_to(self, idx: int):
        """
        Bascule l'affichage sur le document à l'index ``idx``.

        Appelé par ``TitleBar.tab_changed`` quand l'utilisateur clique
        sur un onglet, ou par ``_open_document`` après ouverture.
        """
        if idx < 0 or idx >= len(self._documents):
            return
        self._active_idx = idx
        doc = self._documents[idx]
        self._rebind_doc(doc)
        self._set_ribbon_enabled(doc.is_open)
        self._update_status()

    def _rebind_doc(self, doc: Document):
        """
        Rebanche tous les widgets sur un nouveau document actif.

        C'est la méthode centrale du multi-document. Elle :
        1. Déconnecte TOUS les signaux de l'ancien document (``disconnect()``
           sans argument = déconnecte toutes les connexions).
        2. Reconnecte le nouveau document sur les 3 slots principaux.
        3. Met à jour la référence ``document`` dans chaque tab du ribbon
           (attribut direct — les tabs stockent la référence pour les opérations).
        4. Force un rafraîchissement immédiat du viewer et des miniatures.

        Parameters
        ----------
        doc : Document
            Nouveau document à activer. Peut être un Document vide (sans fichier ouvert)
            pour afficher la welcome page quand tous les onglets sont fermés.
        """
        old = self._current_doc

        # Déconnecter tous les signaux de l'ancien document.
        # try/except car disconnect() lève RuntimeError si aucun signal n'est connecté
        # (cas du Document vide initial créé dans __init__).
        try:
            old.changed.disconnect()
        except RuntimeError:
            pass

        self._current_doc = doc

        # Reconnecter les 3 slots essentiels sur le nouveau document
        doc.changed.connect(self._on_doc_changed)        # barre de statut, titre onglet
        doc.changed.connect(self.viewer._on_doc_changed) # re-render des pages
        doc.changed.connect(self._thumbs.rebuild)        # re-render des miniatures

        # Rebrancher la référence document dans tous les tabs du ribbon.
        # Les tabs utilisent self.document pour passer à operations/*.
        for tab in (self._tab_afficher, self._tab_modifier,
                    self._tab_annoter, self._tab_page,
                    self._tab_convertir, self._tab_proteger):
            tab.document = doc

        # Rebrancher les références dans viewer et panneau miniatures
        self.viewer.document = doc
        self._thumbs.document = doc

        # Forcer un rafraîchissement immédiat (sans attendre changed.emit)
        self.viewer._on_doc_changed()
        self._thumbs.rebuild()

    # ── Événements document ───────────────────────────────────────────────────

    def _on_doc_changed(self):
        """
        Slot connecté à ``document.changed`` — met à jour l'UI après modification.

        Met à jour le titre de l'onglet (nom du fichier), la barre de statut
        (chemin complet + nombre de pages) et active le ribbon.
        """
        doc = self._current_doc
        if doc.is_open:
            n = len(doc.fitz_doc)
            self._title_bar.set_tab_title(self._active_idx, doc.path.name)
            self._status_file.setText(str(doc.path))
            self._status_page.setText(f"{n} page{'s' if n > 1 else ''}")
            self._set_ribbon_enabled(True)
            self._act_undo.setEnabled(doc.can_undo)
        else:
            self._update_status()

    def _update_status(self):
        """Rafraîchit la barre de statut sans émettre de signal."""
        doc = self._current_doc
        if doc.is_open:
            n = len(doc.fitz_doc)
            self._status_file.setText(str(doc.path))
            self._status_page.setText(f"{n} page{'s' if n > 1 else ''}")
        else:
            self._status_file.setText("Aucun document ouvert")
            self._status_page.setText("")

    # ── Sauvegarde ───────────────────────────────────────────────────────────

    def _save(self):
        """Sauvegarde le document actif en place (Ctrl+S)."""
        if self._current_doc.is_open:
            self._current_doc.save()
            self._status_file.setText(
                f"Enregistré : {self._current_doc.path.name}")

    def _save_as(self):
        """Sauvegarde le document actif sous un nouveau chemin (Ctrl+Shift+S)."""
        if not self._current_doc.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer sous",
            str(self._current_doc.path), "PDF (*.pdf)")
        if path:
            self._current_doc.save(path)

    # ── Thumbnails ────────────────────────────────────────────────────────────

    def _on_thumbs_width_changed(self, new_w: int):
        """
        Force le splitter à respecter la nouvelle largeur du panneau miniatures.

        ``QSplitter`` ne réagit pas automatiquement aux changements de ``setFixedWidth``
        sur ses enfants après l'initialisation. On doit appeler ``setSizes()``
        explicitement pour redistribuer l'espace.

        Parameters
        ----------
        new_w : int
            Nouvelle largeur du panneau miniatures (en pixels).
        """
        viewer_w = self._splitter.width() - new_w - self._splitter.handleWidth()
        self._splitter.setSizes([new_w, max(viewer_w, 400)])

    # ── Maximize / Restore ────────────────────────────────────────────────────

    def _toggle_maximize(self):
        """Bascule entre fenêtre maximisée et restaurée."""
        if self.isMaximized():
            self.showNormal()
            self._title_bar.update_max_button(False)
        else:
            self.showMaximized()
            self._title_bar.update_max_button(True)

    def changeEvent(self, event):
        """Met à jour l'icône du bouton max quand la fenêtre est maximisée
        par un moyen externe (double-clic barre des tâches, raccourci Windows…)."""
        super().changeEvent(event)
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            self._title_bar.update_max_button(self.isMaximized())

    # ── Bordure & resize fenêtre ──────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(QPen(QColor(BORDER_COLOR), 1))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos  = event.position().toPoint()
        edge = self._edge_at(pos)
        if edge is not None:
            handle = self.windowHandle()
            if handle:
                handle.startSystemResize(edge)

    def mouseMoveEvent(self, event):
        edge   = self._edge_at(event.position().toPoint())
        cursor = self._EDGE_CURSORS.get(edge, Qt.CursorShape.ArrowCursor)
        self.setCursor(cursor)

    def _edge_at(self, pos: QPoint):
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        m = RESIZE_MARGIN
        top    = y < m
        bottom = y > h - m
        left   = x < m
        right  = x > w - m
        if top    and left:  return Qt.Edge.TopEdge    | Qt.Edge.LeftEdge
        if top    and right: return Qt.Edge.TopEdge    | Qt.Edge.RightEdge
        if bottom and left:  return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if bottom and right: return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        if top:              return Qt.Edge.TopEdge
        if bottom:           return Qt.Edge.BottomEdge
        if left:             return Qt.Edge.LeftEdge
        if right:            return Qt.Edge.RightEdge
        return None

    _EDGE_CURSORS = {
        Qt.Edge.TopEdge:                         Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge:                      Qt.CursorShape.SizeVerCursor,
        Qt.Edge.LeftEdge:                        Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge:                       Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge    | Qt.Edge.LeftEdge:   Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.BottomEdge | Qt.Edge.RightEdge:  Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.TopEdge    | Qt.Edge.RightEdge:  Qt.CursorShape.SizeBDiagCursor,
        Qt.Edge.BottomEdge | Qt.Edge.LeftEdge:   Qt.CursorShape.SizeBDiagCursor,
    }

    # ── Drag & drop (fenêtre principale) ─────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(".pdf")
                   for u in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self._open_document(path)
