"""
theme.py — Thème clair (aperçu transitoire)
===========================================
Les couleurs du thème sombre sont encore écrites en dur dans ``app.py`` et dans
les ``setStyleSheet()`` de chaque widget. En attendant de les remplacer par des
jetons, ce module traduit à la volée ces valeurs vers leur équivalent clair.

Activation (aperçu) : variable d'environnement ``PDFEQ_THEME=light``.

Limite connue : les couleurs peintes en Python (``QColor``/``QPainter`` dans
viewer, floating_item, thumbnail_panel, page_edit_widget…) ne passent pas par
une feuille de style et restent sombres tant qu'elles ne sont pas migrées.
"""
import os
import re

DARK = "dark"
LIGHT = "light"

# Accent : fonds et sélections gardent le vert du logo ; en texte sur fond clair
# (contraste insuffisant à 2,2:1), on utilise la variante foncée.
ACCENT = "#6BBF4E"
ACCENT_TEXT_LIGHT = "#3A8A24"

# sombre -> clair (clés en minuscules, forme à 6 chiffres)
_DARK_TO_LIGHT = {
    # fonds
    "#1e1e1e": "#F3F3F3", "#2d2d2d": "#FFFFFF", "#2a2a2a": "#EAEAEA",
    "#252525": "#EDEDED", "#242424": "#EDEDED", "#222222": "#E6E6E6",
    "#2e2e2e": "#E9E9E9", "#1a1a1a": "#E4E4E4", "#181818": "#DCDCDC",
    "#141414": "#E0E0E0",
    # bordures / séparateurs
    "#3a3a3a": "#D6D6D6", "#3d3d3d": "#D2D2D2", "#444444": "#CFCFCF",
    "#333333": "#CFCFCF", "#4a4a4a": "#C8C8C8", "#555555": "#BDBDBD",
    "#575757": "#B5B5B5", "#585858": "#B5B5B5", "#606060": "#A5A5A5",
    "#666666": "#9A9A9A", "#6a6a6a": "#A8A8A8",
    # textes
    "#f0f0f0": "#1A1A1A", "#ffffff": "#111111", "#cccccc": "#3F3F3F", "#d8d8d8": "#3A3A3A",
    "#c8c8c8": "#444444", "#c0c0c0": "#4A4A4A", "#aaaaaa": "#555555",
    "#888888": "#6E6E6E",
    # accent au survol
    "#7ed45f": "#5BAE3E", "#7dd05f": "#5BAE3E",
}

_HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_ACCENT_AS_TEXT = re.compile(r"(?<![\w-])color:\s*" + re.escape(ACCENT), re.I)


def theme_name() -> str:
    """Thème actif : choix enregistré (switch THEME), sinon ``PDFEQ_THEME`` (aperçu), sinon sombre."""
    from PyQt6.QtCore import QSettings
    saved = str(QSettings("Bit-Scripts", "PDF-Equilibrist").value("theme", ""))
    if saved in (LIGHT, DARK):
        return saved
    return LIGHT if os.environ.get("PDFEQ_THEME", "").lower() == LIGHT else DARK


def set_theme(name: str) -> None:
    """Enregistre le choix de l'utilisateur (appliqué au prochain démarrage)."""
    from PyQt6.QtCore import QSettings
    QSettings("Bit-Scripts", "PDF-Equilibrist").setValue("theme", LIGHT if name == LIGHT else DARK)


def _swap(match: re.Match) -> str:
    h = match.group(0).lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return _DARK_TO_LIGHT.get(h, match.group(0))


def adapt(qss: str) -> str:
    """Traduit une feuille de style sombre vers le thème courant."""
    if theme_name() != LIGHT:
        return qss
    qss = _ACCENT_AS_TEXT.sub(f"color: {ACCENT_TEXT_LIGHT}", qss)
    return _HEX.sub(_swap, qss)


def install_widget_hook() -> None:
    """Fait passer tous les ``QWidget.setStyleSheet`` par ``adapt``."""
    if theme_name() != LIGHT:
        return
    from PyQt6.QtWidgets import QWidget

    if getattr(QWidget, "_theme_hooked", False):
        return
    original = QWidget.setStyleSheet

    def set_style_sheet(self, qss):
        original(self, adapt(qss))

    QWidget.setStyleSheet = set_style_sheet
    QWidget._theme_hooked = True


def qcolor(hex_dark: str):
    """``QColor`` d'une couleur sombre, traduite vers le thème courant (code de peinture)."""
    from PyQt6.QtGui import QColor
    return QColor(adapt(hex_dark))
