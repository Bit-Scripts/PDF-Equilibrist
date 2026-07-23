"""
ui/viewer.py — Visualiseur de pages PDF
========================================
Ce module contient le widget principal d'affichage des pages PDF.

Architecture interne
--------------------
``PdfViewer`` est un ``QScrollArea`` contenant un widget interne ``_stack``
qui empile deux vues :

- ``_WelcomePage`` : affichée quand aucun document n'est ouvert.
  Dessine une icône PDF stylisée et le message d'accueil via ``paintEvent``.
- ``_pages_widget`` : contient une ``QVBoxLayout`` de widgets de page
  (un ``QLabel`` ou ``PageEditWidget`` par page du document ouvert).

La liste ``_page_widgets`` garde une référence à chaque widget de page pour
permettre au panneau miniatures de scroller vers une page précise via
``ensureWidgetVisible()``.

Modes de fonctionnement
------------------------
Le viewer a deux modes distincts :

**Mode normal** (``_edit_mode = False``)
    Chaque page est rendue en ``QLabel`` avec un ``QPixmap``.
    Le rendu est déclenché par ``refresh()`` qui est connecté à
    ``document.changed``.

**Mode édition** (``_edit_mode = True``)
    Activé par ``enter_edit_mode(blocks_by_page)``.
    Les ``QLabel`` sont remplacés par des ``PageEditWidget`` qui permettent
    le survol et le clic pour éditer les blocs de texte individuellement.
    Les modifications sont appliquées directement dans ``fitz.Document``
    à chaque validation de bloc, sans re-render global.

Zoom
----
Le zoom est synchronisé bidirectionnellement avec ``TabAfficher`` :
- ``set_zoom(float)`` → appelé par le combo box ou les boutons +/−
- ``wheelEvent`` (Ctrl+molette) → émet ``zoom_changed(float)`` → met à jour le combo

Les niveaux de zoom disponibles (``_ZOOM_LEVELS``) sont définis ici et
doivent rester identiques à ceux de ``tab_afficher.py``.

Placement flottant
------------------
``show_floating_item()`` crée un ``FloatingItem`` posé sur le widget de page.
Le ``FloatingItem`` est un enfant direct du widget de page (pas du viewer),
ce qui lui permet d'utiliser les coordonnées locales de la page.
"""
from __future__ import annotations
import webbrowser
from pathlib import Path
from PyQt6.QtWidgets import QScrollArea, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen
import fitz
from pdf_equilibrist.core.document import Document


class _PageLabel(QLabel):
    """
    QLabel de page qui détecte et gère les clics sur les liens PDF.

    Supporte tous les types de liens PyMuPDF :
    - ``LINK_URI``    → ouvre l'URL dans le navigateur par défaut
    - ``LINK_GOTOR``  → ouvre le PDF lié dans l'app (nouvel onglet) ou le viewer système
    - ``LINK_GOTO``   → scrolle vers la page cible dans le même document
    - ``LINK_LAUNCH`` → ouvre le fichier avec l'application par défaut

    La résolution des chemins relatifs (LINK_GOTOR) est faite par rapport
    au dossier du document courant.
    """

    # Émis quand un lien GOTO interne est cliqué (page 0-based)
    goto_page = pyqtSignal(int)
    # Émis quand un PDF externe doit être ouvert
    open_pdf = pyqtSignal(str)
    # Émis quand l'utilisateur sélectionne du texte par glissement
    # (page_index, [(fitz.Quad, ...)])
    text_selected = pyqtSignal(int, list)

    def __init__(self, fitz_page: fitz.Page, zoom: float,
                 pixmap: QPixmap, doc_path: Path | None = None,
                 page_index: int = 0):
        super().__init__()
        self._fitz_page  = fitz_page
        self._zoom       = zoom
        self._doc_path   = doc_path
        self._page_index = page_index

        # État de sélection texte
        self._sel_start: QPoint | None = None
        self._sel_rect:  QRect  | None = None
        self._dragging   = False
        # Résultats de recherche : liste de fitz.Rect en coords PDF
        self._search_rects: list = []

        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ── Détection de lien ─────────────────────────────────────────────────────

    def _link_at(self, pos: QPoint) -> dict | None:
        """Retourne le lien PDF sous le curseur ou None."""
        px = pos.x() / max(self._zoom, 0.01)
        py = pos.y() / max(self._zoom, 0.01)
        pt = fitz.Point(px, py)
        for link in self._fitz_page.get_links():
            if fitz.Rect(link["from"]).contains(pt):
                return link
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._sel_start = event.position().toPoint()
        self._sel_rect  = None
        self._dragging  = False
        # Redonner le focus au scroll area pour que les flèches/PageDown fonctionnent
        scroll_area = self.parent()
        while scroll_area and not isinstance(scroll_area, QScrollArea):
            scroll_area = scroll_area.parent()
        if scroll_area:
            scroll_area.setFocus()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._sel_start and (event.buttons() & Qt.MouseButton.LeftButton):
            if not self._dragging and (pos - self._sel_start).manhattanLength() > 5:
                self._dragging = True
            if self._dragging:
                self._sel_rect = QRect(self._sel_start, pos).normalized()
                self.setCursor(Qt.CursorShape.IBeamCursor)
                self.update()
                return

        # Pas de glissement — curseur lien habituel
        link = self._link_at(pos)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if link
            else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging and self._sel_rect:
            self._emit_selection(self._sel_rect)
        else:
            # Clic simple → lien
            link = self._link_at(event.position().toPoint())
            if link:
                self._handle_link(link)
            else:
                # Clic sans lien → effacer sélection
                self._sel_rect = None
                self.update()
        self._sel_start = None
        self._dragging  = False

    def set_search_rects(self, rects: list):
        """Définit les rectangles de résultats de recherche (coords PDF)."""
        self._search_rects = rects
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = max(self._zoom, 0.01)
        # Résultats de recherche — surlignage jaune
        for r in self._search_rects:
            sr = QRect(int(r.x0 * z), int(r.y0 * z),
                       int((r.x1 - r.x0) * z), int((r.y1 - r.y0) * z))
            p.fillRect(sr, QColor(255, 200, 0, 120))
            p.setPen(QPen(QColor(255, 160, 0), 1))
            p.drawRect(sr)
        # Sélection texte — contour vert
        if self._sel_rect:
            p.fillRect(self._sel_rect, QColor(107, 191, 78, 60))
            p.setPen(QPen(QColor(107, 191, 78), 1))
            p.drawRect(self._sel_rect)

    def _emit_selection(self, rect: QRect):
        """Convertit le rect écran en quads PDF et émet text_selected."""
        z = max(self._zoom, 0.01)
        pdf_rect = fitz.Rect(
            rect.left()   / z, rect.top()    / z,
            rect.right()  / z, rect.bottom() / z,
        )
        words = self._fitz_page.get_text("words")
        quads = [
            fitz.Rect(w[:4]).quad
            for w in words
            if fitz.Rect(w[:4]).intersects(pdf_rect)
        ]
        if quads:
            self.text_selected.emit(self._page_index, quads)

    # ── Gestion des liens ─────────────────────────────────────────────────────

    def _handle_link(self, link: dict):
        kind = link.get("kind")

        if kind == fitz.LINK_URI:
            # Lien web → navigateur par défaut
            webbrowser.open(link.get("uri", ""))

        elif kind == fitz.LINK_GOTOR:
            # Lien vers un autre PDF — résoudre le chemin relatif
            file_rel = link.get("file", "")
            if not file_rel:
                return
            # Résolution relative au dossier du doc courant
            if self._doc_path and not Path(file_rel).is_absolute():
                target = (self._doc_path.parent / file_rel).resolve()
            else:
                target = Path(file_rel).resolve()

            if target.exists():
                self.open_pdf.emit(str(target))
            else:
                # Fallback : ouvrir avec le viewer système
                self._open_with_system(str(target))

        elif kind == fitz.LINK_GOTO:
            # Lien interne → scrolle vers la page cible
            page = link.get("page", 0)
            self.goto_page.emit(int(page))

        elif kind == fitz.LINK_LAUNCH:
            file = link.get("file", "")
            if file:
                self._confirm_and_launch(file)

    def _confirm_and_launch(self, path: str):
        """
        Demande confirmation avant d'exécuter un fichier référencé par une action
        'Launch' du PDF. Ces liens peuvent pointer vers n'importe quel exécutable
        local — un PDF piégé pourrait sinon lancer un programme à l'insu de
        l'utilisateur dès qu'il clique sur le lien.
        """
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.warning(
            self,
            "Ouverture d'un fichier externe",
            "Ce document PDF demande à ouvrir :\n\n"
            f"{path}\n\n"
            "N'acceptez que si vous faites confiance à ce document.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._open_with_system(path)

    @staticmethod
    def _open_with_system(path: str):
        """Ouvre un fichier avec l'application par défaut du système."""
        try:
            import os
            # Action Launch confirmée explicitement par l'utilisateur (voir _confirm_and_launch)
            os.startfile(path)  # nosec B606
        except Exception:  # nosec B110
            pass

ACCENT       = "#6BBF4E"
PAGE_MARGIN  = 24    # marge extérieure autour des pages (px)
PAGE_SPACING = 12    # espacement entre les pages (px)

# Niveaux de zoom disponibles — DOIT être identique à tab_afficher.ZOOM_LEVELS
# Format : facteur multiplicateur (1.0 = 72 dpi natif PDF)
_ZOOM_LEVELS = [0.25, 0.33, 0.50, 0.67, 0.75,
                1.00, 1.25, 1.50, 2.00, 3.00, 4.00]


class _WelcomePage(QWidget):
    """
    Page d'accueil affichée quand aucun document n'est ouvert.

    Dessine une icône PDF stylisée (rectangle gris + barres vertes) et
    un message d'instruction via ``paintEvent`` custom (pas de widgets enfants).

    Le signal ``open_requested`` est émis au clic, mais n'est pas actuellement
    connecté — le glisser-déposer et le menu Fichier sont les entrées principales.
    """
    open_requested = pyqtSignal()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fond sombre uniforme
        p.fillRect(self.rect(), QColor("#1E1E1E"))

        # Centre de l'icône
        cx, cy = self.width() // 2, self.height() // 2 - 40

        # Corps du document (rectangle gris arrondi)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2D2D2D"))
        p.drawRoundedRect(cx - 50, cy - 60, 100, 120, 8, 8)

        # Lignes de texte symboliques (barres vertes de largeur décroissante)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(cx - 30, cy - 40, 60, 8, 3, 3)
        p.drawRoundedRect(cx - 30, cy - 24, 60, 8, 3, 3)
        p.drawRoundedRect(cx - 30, cy - 8,  40, 8, 3, 3)

        # Message d'instruction sous l'icône
        p.setPen(QColor("#AAAAAA"))
        p.setFont(QFont("Segoe UI", 13))
        p.drawText(
            self.rect().adjusted(0, cy + 90, 0, 0),
            Qt.AlignmentFlag.AlignHCenter,
            "Glissez un PDF ici ou utilisez  Fichier › Ouvrir"
        )

    def mousePressEvent(self, event):
        self.open_requested.emit()


class PdfViewer(QScrollArea):
    """
    Widget principal d'affichage et d'interaction avec les pages PDF.

    Hérite de ``QScrollArea`` pour gérer le défilement automatique
    sur les documents multi-pages.

    Signals
    -------
    zoom_changed : pyqtSignal(float)
        Émis quand l'utilisateur change le zoom via Ctrl+molette.
        Connecté à ``TabAfficher._on_viewer_zoom`` pour synchroniser le combo.

    Attributes
    ----------
    document : Document
        Référence au document courant. Rebindée par ``MainWindow._rebind_doc()``
        lors du changement d'onglet.
    zoom : float
        Facteur de zoom courant (1.0 = taille native PDF).
    _edit_mode : bool
        ``True`` quand le viewer est en mode édition de texte.
    _page_widgets : list[QWidget]
        Un widget par page : ``QLabel`` en mode normal, ``PageEditWidget``
        en mode édition. Utilisé par ``ThumbnailPanel`` pour le scroll.
    """

    zoom_changed       = pyqtSignal(float)       # Ctrl+molette → sync combo zoom
    open_pdf_requested = pyqtSignal(str)         # lien GOTOR → ouvrir PDF dans nouvel onglet
    text_selected      = pyqtSignal(int, list)   # (page_index, [fitz.Quad]) sélection texte


    def __init__(self, document: Document):
        super().__init__()
        self.document = document
        self.zoom     = 1.0
        self._edit_mode    = False
        self._page_widgets: list[QWidget] = []

        # ── Page d'accueil ────────────────────────────────────────────────────
        self._welcome = _WelcomePage()

        # ── Zone de pages ─────────────────────────────────────────────────────
        # Un QLabel par page, empilés verticalement avec marges et espacement
        self._pages_widget = QWidget()
        self._pages_layout = QVBoxLayout(self._pages_widget)
        self._pages_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._pages_layout.setSpacing(PAGE_SPACING)
        self._pages_layout.setContentsMargins(
            PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)

        # ── Stack : welcome + pages ───────────────────────────────────────────
        # Les deux vues sont dans le même widget conteneur.
        # On montre/cache l'une ou l'autre selon l'état du document.
        self._stack = QWidget()
        from PyQt6.QtWidgets import QVBoxLayout as VL
        sl = VL(self._stack)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self._welcome)
        sl.addWidget(self._pages_widget)

        # Le stack est le widget scrollable principal
        self.setWidget(self._stack)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QScrollArea { border: none; background: #1E1E1E; }")

        # Abonnement au signal changed du document
        document.changed.connect(self._on_doc_changed)
        self.refresh()

    # ── Rafraîchissement ──────────────────────────────────────────────────────

    def _on_doc_changed(self):
        """
        Slot connecté à ``document.changed``.
        Quitte le mode édition si actif et redessine toutes les pages.
        """
        self._edit_mode = False
        self.refresh()

    def refresh(self):
        """
        Reconstruit l'affichage complet depuis le document courant.

        Supprime tous les widgets de page existants (``deleteLater()`` pour
        laisser Qt libérer la mémoire proprement), puis recrée un ``QLabel``
        par page avec le ``QPixmap`` rendu au zoom courant.

        Affiche la page d'accueil si aucun document n'est ouvert.
        """
        # Vider la liste de références et supprimer les anciens widgets
        self._page_widgets.clear()
        for i in reversed(range(self._pages_layout.count())):
            w = self._pages_layout.itemAt(i).widget()
            if w:
                w.deleteLater()   # suppression différée (Qt nettoie au prochain cycle)

        if not self.document.is_open:
            self._welcome.show()
            self._pages_widget.hide()
            return

        self._welcome.hide()
        self._pages_widget.show()

        # Créer un _PageLabel cliquable par page
        doc_path = self.document.path
        for page_num in range(len(self.document.fitz_doc)):
            pixmap    = self.document.render_page(page_num, self.zoom)
            fitz_page = self.document.fitz_doc[page_num]
            label     = _PageLabel(fitz_page, self.zoom, pixmap, doc_path, page_num)
            label.setStyleSheet(
                "background: white; border: 1px solid #3A3A3A; border-radius: 2px;"
            )
            label.goto_page.connect(self._scroll_to_page)
            label.open_pdf.connect(self._request_open_pdf)
            label.text_selected.connect(self.text_selected)
            self._pages_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._page_widgets.append(label)

    # ── Mode édition texte ────────────────────────────────────────────────────

    def enter_edit_mode(self, blocks_by_page: dict[int, list]) -> bool:
        """
        Active le mode édition de texte sur les pages qui ont des blocs.

        Remplace les ``QLabel`` de pages par des ``PageEditWidget`` qui gèrent
        le survol (surlignage du bloc) et le clic (ouverture de l'éditeur inline).

        Seules les pages présentes dans ``blocks_by_page`` sont transformées —
        les pages sans texte extractible restent des ``QLabel`` normaux.

        Parameters
        ----------
        blocks_by_page : dict[int, list[TextBlock]]
            Mapping ``{page_index: [TextBlock, ...]}`` produit par
            ``operations.edit.extract_text_blocks()``.

        Returns
        -------
        bool
            ``True`` si au moins une page a été mise en mode édition.
            ``False`` si le document est fermé ou si aucun bloc n'est fourni.
        """
        if not self.document.is_open:
            return False
        if not any(blocks_by_page.values()):
            return False

        from pdf_equilibrist.ui.page_edit_widget import PageEditWidget

        for page_num in range(len(self.document.fitz_doc)):
            blocks = blocks_by_page.get(page_num, [])
            if not blocks:
                continue
            if page_num >= len(self._page_widgets):
                break

            old    = self._page_widgets[page_num]
            pixmap = self.document.render_page(page_num, self.zoom)

            # Remplacer le QLabel par un PageEditWidget interactif
            new_w = PageEditWidget(
                pixmap=pixmap,
                blocks=blocks,
                zoom=self.zoom,
                doc=self.document.fitz_doc,
                page_index=page_num,
                page_origin=(0, 0),
            )
            new_w.setStyleSheet(
                "background: white; border: 1px solid #3A3A3A; border-radius: 2px;"
            )

            # Remplacer dans le layout à la même position
            idx = self._pages_layout.indexOf(old)
            self._pages_layout.removeWidget(old)
            old.deleteLater()
            self._pages_layout.insertWidget(
                idx, new_w, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._page_widgets[page_num] = new_w

        self._edit_mode = True
        return True

    def exit_edit_mode(self):
        """Quitte le mode édition et redessine les pages en mode normal."""
        self._edit_mode = False
        self.refresh()

    @property
    def is_edit_mode(self) -> bool:
        """``True`` si le viewer est actuellement en mode édition de texte."""
        return self._edit_mode

    # ── Placement flottant ────────────────────────────────────────────────────

    def show_floating_item(self, data: dict, page_index: int,
                           on_commit, on_cancel):
        """
        Crée et affiche un ``FloatingItem`` sur la page indiquée.

        Le ``FloatingItem`` est un widget enfant direct du widget de page,
        ce qui lui permet d'être positionné en coordonnées locales à la page.
        Il est détruit automatiquement (``deleteLater``) après validation ou annulation.

        Parameters
        ----------
        data : dict
            Données de l'élément à placer :
            ``{'type': 'text'|'image'|'stamp', ...}``
        page_index : int
            Numéro de page 0-based sur laquelle afficher l'élément.
        on_commit : callable
            Callback ``(result_dict, page_index)`` appelé quand l'utilisateur
            valide. ``result_dict`` contient ``pdf_rect`` en coordonnées PDF.
        on_cancel : callable | None
            Callback appelé si l'utilisateur annule. Peut être ``None``.
        """
        from pdf_equilibrist.ui.floating_item import FloatingItem

        if page_index >= len(self._page_widgets):
            return

        page_widget = self._page_widgets[page_index]
        item = FloatingItem(data, self.zoom, page_widget)
        item.show()
        item.raise_()   # au-dessus de tous les autres widgets enfants

        def _on_commit(result):
            item.deleteLater()
            on_commit(result, page_index)

        def _on_cancel():
            item.deleteLater()
            if on_cancel:
                on_cancel()

        item.committed.connect(_on_commit)
        item.cancelled.connect(_on_cancel)

    # ── Page courante / sélection ─────────────────────────────────────────────

    @property
    def current_page_index(self) -> int:
        """Retourne l'index (0-based) de la page la plus visible dans le viewport."""
        if not self._page_widgets:
            return 0
        scroll_y = self.verticalScrollBar().value()
        vp_h     = self.viewport().height()
        best_idx, best_vis = 0, -1
        for i, w in enumerate(self._page_widgets):
            # Position du widget dans le scroll widget (_stack), indépendante du scroll
            y        = w.mapTo(self.widget(), QPoint(0, 0)).y()
            vis_top  = max(y, scroll_y)
            vis_bot  = min(y + w.height(), scroll_y + vp_h)
            visible  = max(0, vis_bot - vis_top)
            if visible > best_vis:
                best_vis, best_idx = visible, i
        return best_idx

    def clear_selection(self):
        """Efface la sélection de texte sur toutes les pages."""
        for w in self._page_widgets:
            if isinstance(w, _PageLabel):
                w._sel_rect = None
                w.update()

    def search_in_doc(self, text: str) -> list[tuple[int, list]]:
        """
        Cherche ``text`` dans toutes les pages du document.
        Retourne [(page_index, [fitz.Rect, ...]), ...] pour les pages avec des résultats.
        Met à jour l'affichage avec les surlignages jaunes.
        """
        if not self.document.is_open or not text:
            self.clear_search()
            return []

        results = []
        for i, w in enumerate(self._page_widgets):
            if not isinstance(w, _PageLabel):
                continue
            rects = w._fitz_page.search_for(text)
            w.set_search_rects(rects)
            if rects:
                results.append((i, rects))
        return results

    def clear_search(self):
        """Supprime tous les surlignages de recherche."""
        for w in self._page_widgets:
            if isinstance(w, _PageLabel):
                w.set_search_rects([])

    def scroll_to_search_result(self, page_index: int):
        """Scrolle vers la page contenant un résultat de recherche."""
        if 0 <= page_index < len(self._page_widgets):
            self.ensureWidgetVisible(self._page_widgets[page_index], 0, 50)

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _scroll_to_page(self, page_index: int):
        """Scrolle vers la page cible (lien GOTO interne)."""
        if 0 <= page_index < len(self._page_widgets):
            self.ensureWidgetVisible(self._page_widgets[page_index], 0, 20)

    def _request_open_pdf(self, path: str):
        """Relaie la demande d'ouverture d'un PDF externe vers MainWindow."""
        self.open_pdf_requested.emit(path)

    def set_zoom(self, zoom: float):
        """
        Applique un nouveau facteur de zoom et redessine les pages.

        Le zoom est clampé entre 0.25 (25%) et 4.0 (400%).
        Ne redessine pas si le mode édition est actif (évite de perdre l'état
        des éditeurs de blocs en cours).

        Parameters
        ----------
        zoom : float
            Nouveau facteur de zoom. Clampé dans [0.25, 4.0].
        """
        self.zoom = max(0.25, min(zoom, 4.0))
        if not self._edit_mode:
            self.refresh()

    def wheelEvent(self, event):
        """
        Gère le zoom par Ctrl+molette.

        Sans Ctrl : défilement normal (délégué à ``QScrollArea``).
        Avec Ctrl  : monte/descend d'un cran dans ``_ZOOM_LEVELS`` et émet
                     ``zoom_changed`` pour synchroniser le combo de ``TabAfficher``.

        La navigation par niveaux discrets (plutôt qu'un zoom continu) assure
        des valeurs de zoom propres et lisibles dans le combo box.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                super().wheelEvent(event)
                return

            # Trouver l'index du niveau de zoom le plus proche du zoom courant
            idx = min(range(len(_ZOOM_LEVELS)),
                      key=lambda i: abs(_ZOOM_LEVELS[i] - self.zoom))

            # Monter ou descendre d'un cran selon le sens de la molette
            if delta > 0:
                idx = min(idx + 1, len(_ZOOM_LEVELS) - 1)   # zoom +
            else:
                idx = max(idx - 1, 0)                         # zoom −

            new_zoom = _ZOOM_LEVELS[idx]
            if new_zoom != self.zoom:
                self.zoom = new_zoom
                if not self._edit_mode:
                    self.refresh()
                # Notifier TabAfficher pour mettre à jour le combo box
                self.zoom_changed.emit(self.zoom)

            event.accept()   # consommer l'event pour éviter le scroll
        else:
            super().wheelEvent(event)   # défilement normal de la ScrollArea
