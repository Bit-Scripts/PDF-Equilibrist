"""
utils.py — Utilitaires partagés de PDF-Equilibrist
====================================================
Ce module fournit des helpers bas niveau utilisés dans tout le projet.

Problème résolu
---------------
PyInstaller (mode onefile) extrait les fichiers dans un dossier temporaire
``sys._MEIPASS`` à l'exécution. Les chemins relatifs classiques (ex. ``"assets/logo.png"``)
ne fonctionnent donc qu'en développement. ``resource_path()`` centralise cette
logique pour que tout le code reste identique entre dev et exe.

Usage
-----
    from pdf_equilibrist.utils import resource_path

    logo = resource_path("assets/logo/PDF-Equilibrist-logo.png")
    if logo.exists():
        icon = QIcon(str(logo))
"""
from __future__ import annotations
from pathlib import Path
import sys


def resource_path(relative: str) -> Path:
    """
    Retourne le chemin absolu vers un fichier asset, compatible dev ET exe PyInstaller.

    En développement
    ~~~~~~~~~~~~~~~~
    ``__file__`` pointe vers ``src/pdf_equilibrist/utils.py``.
    On remonte 3 niveaux de dossiers pour atteindre la racine du projet :
    ``utils.py`` → ``pdf_equilibrist/`` → ``src/`` → ``<racine>/``

    En production (exe PyInstaller onefile)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PyInstaller extrait tous les fichiers embarqués dans un dossier temporaire
    dont le chemin est stocké dans ``sys._MEIPASS``. Les assets (dossier ``assets/``)
    y sont copiés à la compilation via la directive ``datas`` du spec file.

    Parameters
    ----------
    relative : str
        Chemin relatif depuis la racine du projet, ex. ``"assets/logo/logo.png"``.

    Returns
    -------
    Path
        Chemin absolu utilisable directement avec ``open()``, ``QPixmap()``, etc.

    Examples
    --------
    >>> p = resource_path("assets/buttons/close.png")
    >>> print(p.exists())   # True si le fichier est présent
    """
    if hasattr(sys, "_MEIPASS"):
        # Mode exe : sys._MEIPASS est le dossier d'extraction temporaire de PyInstaller
        return Path(sys._MEIPASS) / relative

    # Mode dev : remonter src/pdf_equilibrist/utils.py → projet root
    return Path(__file__).resolve().parent.parent.parent / relative
