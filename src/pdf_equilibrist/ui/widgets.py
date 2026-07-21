"""
ui/widgets.py — Composants partagés du ribbon
===============================================
Ce module définit les briques visuelles réutilisables du ribbon :
``RibbonButton`` et ``RibbonGroup``.

Design du ribbon
-----------------
Le ribbon utilise un style « bouton vertical » : une icône (emoji Unicode)
sur la ligne du haut et un label court sur la ligne du bas, séparés par
un saut de ligne dans le texte du ``QPushButton``.

Les boutons sont regroupés dans des ``RibbonGroup`` qui affichent un titre
catégorie en bas (ex. "Zoom", "Rotation", "Édition texte") et un séparateur
vertical à droite pour délimiter visuellement les groupes.

Choix Unicode pour les icônes
------------------------------
Les emojis Unicode (✎ ⊕ 🔒…) sont utilisés comme icônes car :
- Pas de dépendance à des fichiers d'icônes externes
- Rendu multi-plateforme via les polices système
- Facilement modifiables dans le code sans outils graphiques

La limite est que l'apparence exacte dépend de la police emoji du système
(Segoe UI Emoji sur Windows, Apple Color Emoji sur macOS).

Largeur automatique des boutons
---------------------------------
``setMinimumWidth(68)`` avec ``SizePolicy.Minimum`` permet aux boutons
de s'élargir si leur texte est long (ex. "PowerPoint" vs "Word"),
tout en garantissant une largeur minimale cohérente.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (QPushButton, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt

ACCENT = "#6BBF4E"

# ── Style partagé des boutons ribbon ─────────────────────────────────────────

BTN_V_STYLE = f"""
QPushButton {{
    background: transparent;
    color: #C8C8C8;
    border: none;
    border-radius: 5px;
    padding: 6px 10px 4px 10px;
    font-size: 11px;
    text-align: center;
}}
QPushButton:hover {{
    background: #3D3D3D;
    color: #FFFFFF;
}}
QPushButton:pressed {{
    background: #2A2A2A;
    color: {ACCENT};
}}
QPushButton:disabled {{
    color: #585858;   /* gris plus visible que le défaut Qt sur fond sombre */
}}
"""


class RibbonButton(QPushButton):
    """
    Bouton ribbon vertical : icône (emoji) sur la ligne haute, label sur la ligne basse.

    Le texte du bouton est formaté ``"{icon}\\n{label}"`` pour obtenir
    le rendu vertical via le mécanisme natif de ``QPushButton``.

    Parameters
    ----------
    icon : str
        Caractère emoji ou symbole Unicode servant d'icône visuelle.
        Exemples : ``"✎"``, ``"🔒"``, ``"⊕"``, ``"W"``.
    label : str
        Label court affiché sous l'icône (1-2 mots max).
        Si vide, seule l'icône est affichée (pour les boutons très étroits
        comme les boutons +/− du zoom).
    parent : QWidget | None
        Widget parent Qt.

    Examples
    --------
    >>> btn = RibbonButton("✎", "Modifier\\ntexte")   # label sur 2 lignes
    >>> btn = RibbonButton("−", "")                   # icône seule (zoom out)
    """

    def __init__(self, icon: str, label: str = "", parent=None):
        # Formater le texte : icône + saut de ligne + label (si label non vide)
        text = f"{icon}\n{label}" if label else icon
        super().__init__(text, parent)
        self.setStyleSheet(BTN_V_STYLE)

        # Largeur auto selon le texte, avec minimum pour cohérence visuelle
        self.setMinimumWidth(68)
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,    # s'élargit si nécessaire
            QSizePolicy.Policy.Expanding,  # prend toute la hauteur du ribbon
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Taille de police légèrement réduite pour le double-texte (icône + label)
        font = self.font()
        font.setPointSize(10)
        self.setFont(font)


# ── Groupe de boutons ribbon ──────────────────────────────────────────────────

class RibbonGroup(QWidget):
    """
    Conteneur de boutons ribbon avec titre catégorie en bas et séparateur droite.

    Layout interne ::

        ┌──────────────────────────┐
        │  [btn1] [btn2] [btn3]    │  ← rangée de RibbonButton
        │  ─── Titre groupe ─────  │  ← label catégorie (9px, gris sombre)
        └──────────────────────────┤← séparateur vertical (1px, #3A3A3A)

    Le séparateur est un ``QFrame`` positionné absolument sur le bord droit
    via ``resizeEvent`` (pas dans le layout) pour ne pas perturber la largeur
    calculée du groupe.

    Parameters
    ----------
    title : str
        Nom du groupe affiché sous les boutons (ex. ``"Zoom"``, ``"Rotation"``).

    Usage
    -----
    ::

        grp = RibbonGroup("Zoom")
        grp.add(btn_minus, combo_zoom, btn_plus)
        layout.addWidget(grp)
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 0)
        outer.setSpacing(0)

        # Rangée de boutons (alignée à gauche et centrée verticalement)
        self._row = QHBoxLayout()
        self._row.setSpacing(2)
        self._row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(self._row, 1)  # stretch=1 : prend l'espace disponible

        # Label titre du groupe (discret, en bas)
        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #575757; font-size: 9px; padding: 1px 0 2px 0;")
        outer.addWidget(lbl)

        # Séparateur vertical à droite du groupe — positionné absolument
        # car le layout QVBoxLayout ne permet pas les séparateurs verticaux
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #3A3A3A;")
        sep.setFixedWidth(1)
        sep.setParent(self)   # enfant direct pour le positionnement absolu

    def add(self, *widgets) -> "RibbonGroup":
        """
        Ajoute un ou plusieurs widgets à la rangée de boutons.

        Retourne ``self`` pour permettre le chaînage :
        ``grp.add(btn1).add(btn2)`` ou ``grp.add(btn1, btn2, btn3)``.

        Parameters
        ----------
        *widgets : QWidget
            Un ou plusieurs widgets à ajouter (ordre = gauche à droite).

        Returns
        -------
        RibbonGroup
            ``self`` pour le chaînage.
        """
        for w in widgets:
            self._row.addWidget(w)
        return self

    def resizeEvent(self, event):
        """Repositionne le séparateur vertical sur le bord droit à chaque redimensionnement."""
        super().resizeEvent(event)
        for child in self.children():
            if isinstance(child, QFrame):
                # Coller le séparateur au bord droit, toute la hauteur du groupe
                child.setGeometry(self.width() - 1, 0, 1, self.height())
