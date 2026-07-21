"""
app.py — Configuration de QApplication et stylesheet globale
=============================================================
Ce module est le point de configuration de l'application Qt.
Il est appelé depuis ``main.py`` après le chargement du splash screen.

Responsabilités
---------------
1. **Configurer** la ``QApplication`` existante (nom, icône, stylesheet).
2. **Créer** la ``MainWindow`` et l'afficher.
3. **Centraliser** le thème visuel via la constante ``STYLE``.

Thème sombre
------------
L'ensemble de l'UI repose sur un thème sombre façon Windows 11 :

- Fond principal   : ``#1E1E1E`` (noir profond)
- Fond secondaire  : ``#2D2D2D`` (gris foncé, ribbon et panneaux)
- Texte            : ``#F0F0F0`` (blanc cassé)
- Accentuation     : ``#6BBF4E`` (vert extrait du logo, hover/sélection/barre)

La constante ``ACCENT`` est définie ici et réutilisée dans les widgets
qui ont besoin de la couleur d'accentuation en dur (title_bar, splash…).

Note sur le chargement différé
--------------------------------
``MainWindow`` est importé à l'intérieur de ``create_app()`` (import différé)
et non au niveau du module. Cela permet à ``main.py`` d'afficher le splash
avant que PyQt6 ne charge tous les modules UI, ce qui accélère le rendu
de la barre de progression.
"""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

ACCENT = "#6BBF4E"

STYLE = f"""
* {{
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QWidget {{
    background-color: #1E1E1E;
    color: #F0F0F0;
}}
QMainWindow {{
    background-color: #1E1E1E;
}}

/* ── Ribbon / QTabWidget ── */
QTabWidget::pane {{
    border: none;
    background: #2D2D2D;
    border-bottom: 1px solid #3A3A3A;
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar {{
    background: #1E1E1E;
}}
QTabBar::tab {{
    background: transparent;
    color: #AAAAAA;
    padding: 6px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: #F0F0F0;
    background: #2A2A2A;
}}

/* ── Menus ── */
QMenuBar {{
    background: #1E1E1E;
    color: #CCCCCC;
    border-bottom: 1px solid #2D2D2D;
    padding: 2px 0;
}}
QMenuBar::item:selected {{
    background: #2D2D2D;
    color: #FFFFFF;
}}
QMenu {{
    background: #2D2D2D;
    color: #F0F0F0;
    border: 1px solid #3A3A3A;
}}
QMenu::item:selected {{
    background: #3A3A3A;
    color: {ACCENT};
}}
QMenu::separator {{
    height: 1px;
    background: #3A3A3A;
    margin: 3px 0;
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: #2A2A2A;
    width: 12px;
    border: none;
    border-left: 1px solid #3A3A3A;
}}
QScrollBar::handle:vertical {{
    background: #6A6A6A;
    border-radius: 5px;
    min-height: 32px;
    margin: 2px 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar::handle:vertical:pressed {{
    background: #4E9938;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: #2A2A2A;
    height: 12px;
    border: none;
    border-top: 1px solid #3A3A3A;
}}
QScrollBar::handle:horizontal {{
    background: #6A6A6A;
    border-radius: 5px;
    min-width: 32px;
    margin: 2px 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT};
}}
QScrollBar::handle:horizontal:pressed {{
    background: #4E9938;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status bar ── */
QStatusBar {{
    background: #1E1E1E;
    color: #888888;
    font-size: 11px;
}}

/* ── ComboBox ── */
QComboBox {{
    background: #2D2D2D;
    color: #F0F0F0;
    border: 1px solid #3A3A3A;
    border-radius: 4px;
    padding: 2px 6px;
}}
QComboBox:hover {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 16px;
}}
QComboBox QAbstractItemView {{
    background: #2D2D2D;
    color: #F0F0F0;
    selection-background-color: #3A3A3A;
}}

/* ── Dialogs ── */
QFileDialog {{
    background: #2D2D2D;
    color: #F0F0F0;
}}
"""


def create_app(app: QApplication) -> QApplication:
    """
    Configure la ``QApplication`` existante et crée la fenêtre principale.

    Cette fonction reçoit l'instance ``QApplication`` déjà créée par ``main.py``
    (nécessaire pour que le splash screen fonctionne avant le chargement de l'UI).

    Étapes
    ------
    1. Définit le nom de l'application (utilisé dans les dialogues système).
    2. Charge et applique l'icône de la fenêtre depuis les assets.
    3. Applique le stylesheet global ``STYLE`` à toute l'application.
    4. Crée et affiche la ``MainWindow``.
    5. Attache la fenêtre à l'attribut ``app._main_window`` pour éviter
       qu'elle soit garbage-collectée par Python avant la fin de ``app.exec()``.

    Parameters
    ----------
    app : QApplication
        Instance Qt existante créée dans ``main.py``.

    Returns
    -------
    QApplication
        La même instance, configurée et avec la fenêtre visible.

    Note
    ----
    L'import de ``MainWindow`` est intentionnellement différé ici (et non
    au niveau du module ``app.py``) pour que le splash screen de ``main.py``
    soit affiché avant le chargement de tous les modules UI.
    """
    from pdf_equilibrist.utils import resource_path

    app.setApplicationName("PDF Equilibrist")

    # Charger l'icône depuis les assets (compatible dev + exe PyInstaller)
    logo = resource_path("assets/logo/PDF-Equilibrist-logo.png")
    if logo.exists():
        app.setWindowIcon(QIcon(str(logo)))

    # Appliquer le thème sombre global à tous les widgets de l'application
    app.setStyleSheet(STYLE)

    # Import différé : MainWindow charge tous les modules UI au premier import
    from pdf_equilibrist.ui.main_window import MainWindow
    win = MainWindow()
    win.show()

    # Référence explicite pour éviter le garbage collection de la fenêtre
    # (Python libérerait `win` à la fin de cette fonction sans cette ligne)
    app._main_window = win
    return app
