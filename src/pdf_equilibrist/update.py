from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_GITHUB_REPO = os.getenv(
    "PDF_EQUILIBRIST_UPDATE_REPO",
    "PDF-Equilibrist/PDF-Equilibrist",
)
USER_AGENT = "PDF-Equilibrist-Updater/0.1"
GITHUB_API_URL = "https://api.github.com/repos"


def _normalize_repo(repo: str) -> tuple[str, str]:
    repo = repo.strip()
    if "/" not in repo:
        raise ValueError("Le dépôt GitHub doit être au format owner/repo")
    owner, name = repo.split("/", 1)
    return owner.strip(), name.strip()


def _fetch_json(url: str, timeout: int = 10):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
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


def download_release_asset(asset: dict, target_path: Path, timeout: int = 120) -> Path:
    url = asset.get("browser_download_url")
    if not url:
        raise ValueError("L'asset ne contient pas d'URL de téléchargement valide.")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/octet-stream",
        },
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    target_path.write_bytes(data)
    return target_path


def get_release_page_url(release: dict) -> str | None:
    return release.get("html_url")


def get_download_target(asset: dict) -> Path:
    filename = asset.get("name") or "PDF-Equilibrist-Update.exe"
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
