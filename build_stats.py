#!/usr/bin/env python3
"""Relève les compteurs de diffusion et écrit `stats.json` à la racine.

Les chiffres changent tous les jours, les libellés non : ils ne passent donc pas
par `build_i18n.py`. Ce script écrit un `stats.json` que la page lit au
chargement, ce qui évite de reconstruire le site à chaque relevé.

Sources, toutes publiques et en lecture seule :

    GitHub      API releases, somme des `download_count` des assets
    Launchpad   API du PPA : getPublishedBinaries puis getDownloadCount
    COPR        page HTML — pas d'API pour ces compteurs
    AUR         RPC v5 : ni téléchargements ni installations, mais votes
                et popularité

COPR affiche deux compteurs par version de Fedora, tirés des journaux de ses
serveurs. `total` est celui des paquets RPM téléchargés (« x86_64 (N)* ») :
comme pour Launchpad et GitHub, chaque installation *et chaque mise à jour*
compte, ce n'est pas un nombre d'utilisateurs. `enablements` est celui du
fichier `.repo`, c'est-à-dire des `dnf copr enable` ; il est conservé à part.

Usage :
    python build_stats.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "stats.json")

GITHUB_REPO = "Bit-Scripts/PDF-Equilibrist"
LP_PPA = "https://api.launchpad.net/devel/~paulwoisard/+archive/ubuntu/pdf-equilibrist"
COPR_PAGE = "https://copr.fedorainfracloud.org/coprs/paullux/PDF-Equilibrist/"
PKG = "pdf-equilibrist"

UA = {"User-Agent": f"{PKG}-stats/1.0 (+https://pdf-equilibrist.org)"}


def get(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def get_json(url: str, headers: dict | None = None):
    return json.loads(get(url, headers))


def github() -> dict:
    # Sans jeton, l'API GitHub plafonne à 60 requêtes/heure par IP — et les
    # runners Actions partagent leurs IP. Le workflow fournit GITHUB_TOKEN.
    token = os.environ.get("GITHUB_TOKEN")
    auth = {"Authorization": f"Bearer {token}"} if token else {}
    releases: list[dict] = []
    page = 1
    while True:
        batch = get_json(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=100&page={page}", auth
        )
        releases += batch
        if len(batch) < 100:
            break
        page += 1
    if not releases:
        raise ValueError("aucune release publiée")
    latest = next((r for r in releases if not r["prerelease"]), releases[0])
    return {
        "total": sum(a["download_count"] for r in releases for a in r["assets"]),
        "releases": len(releases),
        "latest": latest["tag_name"],
        "latest_date": latest["published_at"][:10],
    }


def launchpad() -> dict:
    url = f"{LP_PPA}?ws.op=getPublishedBinaries&binary_name={PKG}&exact_match=true"
    by_series: dict[str, int] = {}
    # Réponse paginée (75 entrées par page) : suivre next_collection_link, sinon
    # les anciennes versions finiraient par disparaître du total sans bruit.
    while url:
        data = get_json(url)
        for entry in data["entries"]:
            series = entry["distro_arch_series_link"].rsplit("/", 2)[-2]
            count = get_json(entry["self_link"] + "?ws.op=getDownloadCount")
            by_series[series] = by_series.get(series, 0) + count
        url = data.get("next_collection_link")
    if not by_series:
        raise ValueError("aucun binaire publié dans le PPA")
    return {"total": sum(by_series.values()), "by_series": by_series}


def copr() -> dict:
    """Une ligne du tableau « Active Releases » de la page COPR par version :

        Fedora 44 | x86_64 (123)* | [Fedora 44] (29 downloads)

    `(N)*` : paquets RPM téléchargés, par architecture ; `(N downloads)` :
    téléchargements du fichier `.repo`, soit les activations du dépôt.
    """
    downloads: dict[str, int] = {}
    enablements: dict[str, int] = {}
    for row in re.findall(r"<tr\b.*?</tr>", get(COPR_PAGE), re.S):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row))
        release = re.search(r"Fedora [\w.]+", text)
        repo = re.search(r"\((\d+) downloads?\)", text)
        if not (release and repo):
            continue
        rpms = re.findall(r"\((\d+)\)\s*\*", text)
        if not rpms:
            # Mieux vaut un échec (et le chiffre d'hier, marqué `stale`)
            # qu'un zéro silencieux si COPR change sa mise en page.
            raise ValueError(f"compteur de paquets absent pour {release.group()}")
        downloads[release.group()] = sum(map(int, rpms))
        enablements[release.group()] = int(repo.group(1))
    if not downloads:
        raise ValueError("aucun compteur trouvé (mise en page COPR changée ?)")
    return {
        "total": sum(downloads.values()),
        "by_release": downloads,
        "enablements": sum(enablements.values()),
        "enablements_by_release": enablements,
    }


def aur() -> dict:
    results = get_json(f"https://aur.archlinux.org/rpc/v5/info?arg[]={PKG}").get("results") or []
    if not results:
        raise ValueError("paquet introuvable")
    pkg = results[0]
    return {
        "version": pkg["Version"],
        "votes": pkg["NumVotes"],
        "popularity": round(pkg["Popularity"], 4),
        "first_submitted": date.fromtimestamp(pkg["FirstSubmitted"]).isoformat(),
        "last_modified": date.fromtimestamp(pkg["LastModified"]).isoformat(),
    }


SOURCES = (("github", github), ("launchpad", launchpad), ("copr", copr), ("aur", aur))


def read_previous() -> dict:
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main() -> int:
    previous = read_previous()
    channels: dict[str, dict] = {}
    failed: list[str] = []

    for name, fetch in SOURCES:
        try:
            channels[name] = fetch()
        except Exception as exc:  # réseau, quota, mise en page changée...
            print(f"[{name}] échec : {exc}", file=sys.stderr)
            failed.append(name)
            # Mieux vaut le chiffre d'hier qu'un trou dans la page ; `stale`
            # signale qu'il n'a pas été rafraîchi.
            old = (previous.get("channels") or {}).get(name)
            if old:
                channels[name] = {**old, "stale": True}

    if not channels:
        print("aucune source disponible : stats.json laissé inchangé", file=sys.stderr)
        return 1

    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total": sum(c.get("total", 0) for c in channels.values()),
        "channels": channels,
    }
    if failed:
        payload["failed"] = failed

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
