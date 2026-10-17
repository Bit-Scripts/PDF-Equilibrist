from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from pdf_equilibrist import network

DEFAULT_GITHUB_REPO = os.getenv(
    "PDF_EQUILIBRIST_UPDATE_REPO",
    "Bit-Scripts/PDF-Equilibrist",
)
USER_AGENT = "PDF-Equilibrist-Updater/0.1"
GITHUB_API_URL = "https://api.github.com/repos"


def is_flatpak() -> bool:
    """
    Détecte une exécution sandboxée Flatpak.

    Flathub gère ses propres mises à jour via ``flatpak update`` — un
    vérificateur applicatif maison est à la fois redondant et inadapté
    (le runtime est en lecture seule, et les assets de release sont des
    ``.exe`` Windows sans équivalent Flatpak).
    """
    return os.path.exists("/.flatpak-info") or "FLATPAK_ID" in os.environ


def appimage_path() -> Path | None:
    """
    Chemin du fichier ``.AppImage`` en cours d'exécution, ou ``None``.

    Le lanceur AppImage exporte ``APPIMAGE`` (chemin absolu du fichier d'origine).
    On exige un fichier réel : une variable héritée d'un autre processus ne doit
    pas faire croire à un AppImage.
    """
    value = os.environ.get("APPIMAGE")
    if not value:
        return None
    path = Path(value)
    return path if path.is_file() else None


def is_appimage() -> bool:
    return appimage_path() is not None


_LINUX_UPDATE_COMMANDS = {
    "arch": "yay -Syu",
    "ubuntu": "sudo apt update && sudo apt install --only-upgrade pdf-equilibrist",
    "fedora": "sudo dnf update pdf-equilibrist",
}


def linux_update_command() -> str | None:
    """
    Retourne la commande de mise à jour du gestionnaire de paquets Linux
    détecté (ex. ``"yay -Syu"`` sur Arch), ou ``None`` si aucun canal connu
    n'est identifié.

    Sur un paquet système Linux (AUR, PPA, COPR…), le vérificateur maison ne
    doit jamais proposer l'installeur ``.exe`` Windows en réponse — inutile et
    trompeur (voir ``find_installer_asset`` / ``UpdateDialog``). La vraie mise
    à jour se fait via le gestionnaire de paquets ; ``None`` signale à l'appelant
    de masquer toute action de mise à jour plutôt que d'en proposer une fausse.
    """
    if sys.platform == "win32" or is_flatpak() or is_appimage():
        # AppImage : posée sur n'importe quelle distribution, le gestionnaire de
        # paquets ne la met pas à jour (voir find_appimage_asset).
        return None
    try:
        os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return None
    ids: set[str] = set()
    for line in os_release.splitlines():
        if line.startswith("ID=") or line.startswith("ID_LIKE="):
            ids.update(line.split("=", 1)[1].strip().strip('"').split())
    if "arch" in ids:
        return _LINUX_UPDATE_COMMANDS["arch"]
    if "ubuntu" in ids:
        return _LINUX_UPDATE_COMMANDS["ubuntu"]
    if "fedora" in ids:
        return _LINUX_UPDATE_COMMANDS["fedora"]
    return None


def _normalize_repo(repo: str) -> tuple[str, str]:
    repo = repo.strip()
    if "/" not in repo:
        raise ValueError("Le dépôt GitHub doit être au format owner/repo")
    owner, name = repo.split("/", 1)
    return owner.strip(), name.strip()


def _fetch_json(url: str, timeout: int = 10):
    if not url.startswith("https://"):
        raise ValueError(f"Schéma d'URL non autorisé : {url}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with network.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)


def _normalize_version(version: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)+)", version)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def latest_release(repo: str | None = None) -> dict | None:
    repo = repo or DEFAULT_GITHUB_REPO
    owner, name = _normalize_repo(repo)
    url = f"{GITHUB_API_URL}/{owner}/{name}/releases/latest"
    try:
        return _fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def is_newer_release(current_version: str, release: dict) -> bool:
    current = _normalize_version(current_version)
    latest = _normalize_version(release.get("tag_name", "") or release.get("name", ""))
    if not latest or not current:
        return False
    return latest > current


def get_latest_release_info(
    current_version: str,
    repo: str | None = None,
) -> dict | None:
    release = latest_release(repo)
    if release is None:
        return None
    if is_newer_release(current_version, release):
        return release
    return None


def find_installer_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []) or []:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            return asset
    return None


def find_appimage_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []) or []:
        name = asset.get("name", "").lower()
        if name.endswith(".appimage") and "x86_64" in name:
            return asset
    return None


def appimage_download_target(release: dict) -> Path:
    """
    Où poser la nouvelle AppImage : à côté de l'actuelle (même dossier), sous un nom
    versionné pour ne jamais écraser celle qui tourne ; ``~/Downloads`` si le dossier
    n'est pas modifiable.
    """
    tag = re.sub(r"[^0-9A-Za-z.\-]", "", release.get("tag_name") or "") or "update"
    filename = f"PDF-Equilibrist-{tag}-x86_64.AppImage"
    current = appimage_path()
    folder = current.parent if current else Path.home() / "Downloads"
    if not os.access(folder, os.W_OK):
        folder = Path.home() / "Downloads"
    return folder / filename


def download_release_asset(asset: dict, target_path: Path, timeout: int = 120, progress=None) -> Path:
    """
    Télécharge l'asset vers ``target_path`` (fichier ``.part`` puis renommage : jamais de fichier
    tronqué sous le nom final). ``progress(octets_lus, total_ou_0)`` est appelé à chaque bloc.
    """
    url = asset.get("browser_download_url")
    if not url:
        raise ValueError("L'asset ne contient pas d'URL de téléchargement valide.")
    if not url.startswith("https://"):
        # L'URL vient de la réponse de l'API GitHub : ne jamais suivre un schéma
        # inattendu (file:/, ftp:/...) même si le JSON semble légitime.
        raise ValueError(f"Schéma d'URL de téléchargement non autorisé : {url}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/octet-stream",
        },
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    part = target_path.with_name(target_path.name + ".part")
    sha = hashlib.sha256()
    done = 0
    try:
        with network.urlopen(request, timeout=timeout) as response, open(part, "wb") as out:
            headers = getattr(response, "headers", None)
            total = int(headers.get("Content-Length") or 0) if headers is not None else 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        # GitHub publie l'empreinte de chaque asset (« sha256:… ») : si elle est là, on la vérifie.
        digest = str(asset.get("digest") or "")
        if digest.startswith("sha256:") and sha.hexdigest() != digest[7:].lower():
            raise ValueError("Empreinte SHA-256 du fichier téléchargé incorrecte.")
        os.replace(part, target_path)
    finally:
        part.unlink(missing_ok=True)
    return target_path


def get_release_page_url(release: dict) -> str | None:
    return release.get("html_url")


def get_download_target(asset: dict) -> Path:
    # os.path.basename() : le nom vient de la réponse de l'API GitHub, on ne
    # veut jamais qu'un séparateur/".." dans ce champ sorte du dossier temp.
    filename = os.path.basename(asset.get("name") or "") or "PDF-Equilibrist-Update.exe"
    return Path(tempfile.gettempdir()) / filename


def all_releases(repo: str | None = None) -> list[dict]:
    """Retourne toutes les releases GitHub (max 100)."""
    owner, name = _normalize_repo(repo or DEFAULT_GITHUB_REPO)
    url = f"{GITHUB_API_URL}/{owner}/{name}/releases?per_page=100"
    try:
        data = _fetch_json(url)
        return data if isinstance(data, list) else []
    except (urllib.error.URLError, urllib.error.HTTPError):
        return []


def get_download_stats(
    repo: str | None = None,
    current_version: str | None = None,
) -> dict:
    """
    Retourne les compteurs de téléchargements depuis GitHub.

    Returns
    -------
    dict avec les clés :
        "current"   : téléchargements de la version courante (0 si inconnue)
        "total"     : téléchargements cumulés de toutes les releases
        "releases"  : nombre de releases trouvées
    """
    releases = all_releases(repo)
    total = 0
    current = 0
    for release in releases:
        tag = release.get("tag_name", "")
        is_current = current_version and tag in (
            current_version,
            f"v{current_version}",
        )
        for asset in release.get("assets", []) or []:
            count = asset.get("download_count", 0) or 0
            total += count
            if is_current:
                current += count
    return {"current": current, "total": total, "releases": len(releases)}
