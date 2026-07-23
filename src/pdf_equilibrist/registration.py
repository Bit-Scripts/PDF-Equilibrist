"""
registration.py — Enregistrement Windows "Ouvrir avec..."
==========================================================
Enregistre automatiquement PDF-Equilibrist dans le registre Windows
pour apparaître dans "Ouvrir avec..." lors du premier lancement de l'exe.

Comportement
------------
- **Dev** (script Python) : ne fait rien — l'exe n'existe pas encore.
- **Exe PyInstaller** : vérifie si la clé registre existe, la crée si absente.
- **Déjà enregistré** : ne fait rien (idempotent).
- **Échec silencieux** : toute erreur est ignorée pour ne pas bloquer le démarrage.

Registre utilisé
----------------
``HKEY_CURRENT_USER`` uniquement — **pas besoin de droits administrateur**.
L'enregistrement est personnel à l'utilisateur courant.

Clés créées
-----------
::

    HKCU\\Software\\Classes\\PDFEquilibrist.Document
        (Default)                    = "PDF Equilibrist Document"
        DefaultIcon\\(Default)       = "C:\\...\\PDF-Equilibrist.exe,0"
        shell\\open\\command\\(Default) = "\"C:\\...\\PDF-Equilibrist.exe\" \"%1\""

    HKCU\\Software\\Classes\\.pdf\\OpenWithProgids
        PDFEquilibrist.Document      = ""   ← apparaît dans "Ouvrir avec..."
"""
from __future__ import annotations
import sys
import shutil
from pathlib import Path

# Identifiant unique de l'application dans le registre Windows
_PROG_ID = "PDFEquilibrist.Document"
_APP_DESC = "PDF Equilibrist Document"


def _get_exe_path() -> str | None:
    """
    Retourne le chemin de l'exe en cours d'exécution.
    Fonctionne uniquement dans un exe PyInstaller (sys.frozen = True).
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    return None   # mode dev : pas d'exe


def is_registered() -> bool:
    """
    Vérifie si la clé ProgID existe déjà dans le registre.

    Returns
    -------
    bool
        ``True`` si l'association est déjà présente.
    """
    try:
        import winreg
        winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{_PROG_ID}"
        )
        return True
    except Exception:
        return False


def _ensure_file_icon(exe_path: str) -> str:
    """
    Copie ``fichier.ico`` vers ``%LOCALAPPDATA%\\PDFEquilibrist\\fichier.ico``
    et retourne ce chemin stable.

    Pourquoi un emplacement stable ?
    ---------------------------------
    En mode PyInstaller onefile, les assets sont extraits dans un répertoire
    temporaire (``_MEIPASS``) dont le chemin change à chaque lancement.
    Le registre Windows ne peut pas pointer vers un chemin éphémère.
    On copie donc l'icône une fois dans ``%LOCALAPPDATA%`` (permanent, sans
    droits admin) et on enregistre ce chemin fixe.

    Fallback
    --------
    Si ``fichier.ico`` est introuvable (build sans l'asset), retourne
    ``"exe_path,0"`` pour utiliser la première icône de l'exe.
    """
    try:
        # Localiser fichier.ico via resource_path (compatible dev + PyInstaller)
        from pdf_equilibrist.utils import resource_path
        src = Path(resource_path("assets/logo/fichier.ico"))
        if not src.exists():
            return f'"{exe_path}",0'

        # Dossier de destination stable
        dest_dir = Path(
            __import__("os").environ.get("LOCALAPPDATA", ""),
            "PDFEquilibrist"
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "fichier.ico"

        # Copier seulement si absent ou différent (évite l'écriture inutile)
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)

        return str(dest)
    except Exception:
        return f'"{exe_path}",0'


def register(exe_path: str) -> bool:
    """
    Enregistre PDF-Equilibrist pour "Ouvrir avec..." dans HKCU.

    Crée les clés nécessaires pour que :
    - L'application apparaisse dans "Ouvrir avec..." pour les .pdf
    - Double-cliquer sur un .pdf (si défini comme app par défaut) ouvre l'exe
    - L'icône de l'exe est utilisée comme icône d'association

    Parameters
    ----------
    exe_path : str
        Chemin complet de l'exe, ex. ``C:\\Program Files\\PDF-Equilibrist.exe``.

    Returns
    -------
    bool
        ``True`` si l'enregistrement a réussi, ``False`` en cas d'erreur.
    """
    try:
        import winreg

        def _set(path: str, name: str, value: str):
            """Crée ou met à jour une valeur de registre (REG_SZ)."""
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

        # ProgID principal
        _set(rf"Software\Classes\{_PROG_ID}",
             "", _APP_DESC)

        # Icône de fichier PDF : fichier.ico copié dans %LOCALAPPDATA%\PDFEquilibrist\
        # Le chemin _MEIPASS change à chaque lancement (onefile) → on copie vers
        # un emplacement stable que le registre peut référencer de façon permanente.
        icon_path = _ensure_file_icon(exe_path)
        _set(rf"Software\Classes\{_PROG_ID}\DefaultIcon",
             "", f'"{icon_path}"')

        # Commande d'ouverture : passe le chemin du fichier en %1
        _set(rf"Software\Classes\{_PROG_ID}\shell\open\command",
             "", f'"{exe_path}" "%1"')

        # Ajout dans OpenWithProgids de .pdf → apparaît dans "Ouvrir avec..."
        _set(r"Software\Classes\.pdf\OpenWithProgids",
             _PROG_ID, "")

        # Nom lisible dans "Ouvrir avec..." à la place du nom de l'exe
        _set(r"Software\Classes\Applications\PDF-Equilibrist.exe",
             "FriendlyAppName", "PDF Equilibrist")
        _set(r"Software\Classes\Applications\PDF-Equilibrist.exe\shell\open\command",
             "", f'"{exe_path}" "%1"')

        # Supprimer les entrées directes pour éviter les doublons dans "Ouvrir avec..."
        _clean_mru_duplicates()
        _clean_open_with_progids()

        # Notifier l'explorateur Windows du changement
        _notify_shell()
        return True

    except Exception:
        # Enregistrement silencieux : ne jamais bloquer le démarrage
        return False


def unregister() -> bool:
    """
    Supprime les clés d'association créées par ``register()``.

    Returns
    -------
    bool
        ``True`` si la suppression a réussi.
    """
    try:
        import winreg

        # Supprimer l'entrée dans OpenWithProgids
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Classes\.pdf\OpenWithProgids",
                                access=winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, _PROG_ID)
        except Exception:  # nosec B110
            pass

        # Supprimer l'arbre ProgID complet
        _delete_tree(winreg.HKEY_CURRENT_USER,
                     rf"Software\Classes\{_PROG_ID}")

        # Supprimer l'entrée FriendlyAppName
        _delete_tree(winreg.HKEY_CURRENT_USER,
                     r"Software\Classes\Applications\PDF-Equilibrist.exe")

        _notify_shell()
        return True
    except Exception:
        return False


def _clean_mru_duplicates():
    """
    Supprime les entrées directes de l'exe dans la liste MRU OpenWithList.

    Windows ajoute automatiquement l'exe dans :
    ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\
    FileExts\\.pdf\\OpenWithList``
    quand l'utilisateur ouvre un fichier avec l'application.
    Cela crée un doublon visible dans "Ouvrir avec..." à côté de l'entrée ProgID.
    On supprime ces entrées directes pour ne garder que le ProgID.

    Le MRUList (ordre des entrées) est reconstruit après suppression pour éviter
    que Windows affiche des entrées fantômes basées sur des lettres supprimées.
    """
    try:
        import winreg
        key_path = (r"Software\Microsoft\Windows\CurrentVersion"
                    r"\Explorer\FileExts\.pdf\OpenWithList")
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path,
            access=winreg.KEY_ALL_ACCESS
        ) as key:
            # Lister toutes les valeurs
            all_entries = {}
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    all_entries[name] = value
                    i += 1
                except OSError:
                    break

            # Identifier les entrées à supprimer (lettre unique = entrée MRU)
            to_delete = []
            for name, value in all_entries.items():
                if name == "MRUList":
                    continue
                if "PDF-Equilibrist" in str(value) or "PDF-Equilibrist" in str(name):
                    to_delete.append(name)

            if not to_delete:
                return

            # Supprimer les entrées trouvées
            deleted_letters = set()
            for name in to_delete:
                try:
                    winreg.DeleteValue(key, name)
                    deleted_letters.add(name)
                except Exception:  # nosec B110
                    pass

            # Reconstruire MRUList en retirant les lettres supprimées
            mru = all_entries.get("MRUList", "")
            new_mru = "".join(c for c in mru if c not in deleted_letters)
            try:
                winreg.SetValueEx(key, "MRUList", 0, winreg.REG_SZ, new_mru)
            except Exception:  # nosec B110
                pass

    except Exception:  # nosec B110
        pass


def _clean_open_with_progids():
    """
    Supprime les entrées directes de l'exe dans OpenWithProgids.

    Windows peut enregistrer l'exe lui-même (pas seulement le ProgID) dans
    ``OpenWithProgids`` après une mise à jour depuis un chemin différent,
    créant un doublon dans "Ouvrir avec...".
    """
    try:
        import winreg
        key_path = r"Software\Classes\.pdf\OpenWithProgids"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path,
            access=winreg.KEY_ALL_ACCESS
        ) as key:
            to_delete = []
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    # Supprimer les entrées directes exe (pas notre ProgID)
                    if ("PDF-Equilibrist" in str(name) and
                            name != _PROG_ID):
                        to_delete.append(name)
                    i += 1
                except OSError:
                    break
            for name in to_delete:
                try:
                    winreg.DeleteValue(key, name)
                except Exception:  # nosec B110
                    pass
    except Exception:  # nosec B110
        pass


def _delete_tree(hive, path: str):
    """Supprime récursivement une clé de registre et toutes ses sous-clés."""
    import winreg
    try:
        with winreg.OpenKey(hive, path, access=winreg.KEY_ALL_ACCESS) as key:
            # Supprimer les sous-clés d'abord (le registre ne supprime pas récursivement)
            while True:
                try:
                    sub = winreg.EnumKey(key, 0)
                    _delete_tree(hive, rf"{path}\{sub}")
                except OSError:
                    break
        winreg.DeleteKey(hive, path)
    except Exception:  # nosec B110
        pass


def _notify_shell():
    """Notifie l'explorateur Windows que les associations ont changé."""
    try:
        import ctypes
        # SHChangeNotify avec SHCNE_ASSOCCHANGED (0x08000000)
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:  # nosec B110
        pass


def auto_register():
    """
    Point d'entrée principal — appelé au démarrage de l'application.

    Enregistre ou **met à jour** l'association à chaque lancement de l'exe.
    Cela garantit que le chemin dans le registre correspond toujours
    à l'exe courant, même après un déplacement, une mise à jour ou
    une réinstallation depuis un zip.

    Ne fait rien si :
    - On est en mode développement (pas d'exe PyInstaller)
    - On n'est pas sur Windows

    Appelé depuis ``main.py`` après la fermeture du splash screen,
    de façon silencieuse et non bloquante.
    """
    if not getattr(sys, "frozen", False):
        return
    if sys.platform != "win32":
        return

    exe_path = _get_exe_path()
    if not exe_path:
        return

    # Nettoyer les doublons à chaque lancement (Windows les recrée automatiquement)
    _clean_mru_duplicates()
    _clean_open_with_progids()

    # Vérifier si le chemin enregistré correspond à l'exe courant
    if _is_registered_for(exe_path):
        return   # déjà à jour → rien à faire

    # Mettre à jour (ou créer) l'enregistrement avec le chemin actuel
    register(exe_path)


def _is_registered_for(exe_path: str) -> bool:
    """
    Vérifie si le registre pointe déjà vers le bon exe.

    Retourne ``False`` si la clé est absente OU si le chemin enregistré
    ne correspond pas à ``exe_path`` (exe déplacé / mis à jour).
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{_PROG_ID}\shell\open\command"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "")
            # La commande est : "C:\...\PDF-Equilibrist.exe" "%1"
            return exe_path.lower() in value.lower()
    except Exception:
        return False
