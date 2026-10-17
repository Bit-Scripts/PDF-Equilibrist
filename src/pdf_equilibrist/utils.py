"""
utils.py — Utilitaires partagés de PDF-Equilibrist
====================================================
Ce module fournit des helpers bas niveau utilisés dans tout le projet.

Problème résolu
---------------
PyInstaller (mode onefile) extrait les fichiers dans un dossier temporaire
``sys._MEIPASS`` à l'exécution. Les chemins relatifs classiques (ex. ``"assets/logo.png"``)
ne fonctionnent donc qu'en développement. Un paquet Linux installé via pip/pacman/apt/dnf
n'est ni l'un ni l'autre : le wheel ne contient que ``src/pdf_equilibrist/``, pas le
dossier ``assets/`` de la racine du dépôt — les packagings système installent donc ce
dossier séparément sous ``$PREFIX/share/pdf-equilibrist/assets/``. ``resource_path()``
centralise ces trois cas pour que tout le code appelant reste identique.

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

    Paquet système Linux (AUR, PPA, COPR…)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Ni ``sys._MEIPASS`` ni le repli dev ne s'appliquent : le code tourne depuis
    ``site-packages`` et le dossier ``assets/`` n'y est pas embarqué. Les recettes
    de packaging (ex. ``packaging/aur/PKGBUILD``) installent ce dossier à part sous
    ``$PREFIX/share/pdf-equilibrist/assets/`` — on vérifie cet emplacement avant de
    retomber sur le calcul relatif au dépôt (qui, lui, ne pointera vers rien de valide
    une fois installé en paquet, mais reste le comportement historique en dev).

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

    # Mode paquet système Linux : assets installés à part sous $PREFIX/share/pdf-equilibrist/
    installed = Path(sys.prefix) / "share" / "pdf-equilibrist" / relative
    if installed.exists():
        return installed

    # Mode dev : remonter src/pdf_equilibrist/utils.py → projet root
    return Path(__file__).resolve().parent.parent.parent / relative


def external_env() -> dict[str, str]:
    """
    Environnement à donner aux programmes externes (xdg-open, gio…).

    Un exécutable PyInstaller (AppImage comprise) place ses propres bibliothèques en tête de
    ``LD_LIBRARY_PATH`` : un programme système qui les charge (ex. ``gio`` avec la glib embarquée)
    plante avec « undefined symbol ». On restitue la valeur d'origine, que le lanceur PyInstaller
    garde dans ``LD_LIBRARY_PATH_ORIG``.
    """
    import os

    env = dict(os.environ)
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
    elif getattr(sys, "frozen", False):
        env.pop("LD_LIBRARY_PATH", None)
    return env


def open_external(target: str) -> bool:
    """Ouvre une URL ou un fichier avec l'application par défaut du système (sans polluer son environnement)."""
    import os
    import shutil
    import subprocess  # nosec B404
    import webbrowser

    if sys.platform.startswith("linux"):
        xdg_open = shutil.which("xdg-open")
        if xdg_open:
            try:
                subprocess.Popen(  # nosec B603
                    [xdg_open, target], env=external_env(), start_new_session=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return True
            except OSError:
                pass
    elif sys.platform == "win32" and not target.startswith(("http://", "https://")):
        os.startfile(target)  # nosec B606
        return True
    # Repli : webbrowser lance gio / gvfs-open / un navigateur avec NOTRE environnement. On le
    # nettoie le temps de l'appel (open() rend la main tout de suite, les enfants sont déjà créés).
    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(external_env())
        return webbrowser.open(target)
    finally:
        os.environ.clear()
        os.environ.update(saved)
