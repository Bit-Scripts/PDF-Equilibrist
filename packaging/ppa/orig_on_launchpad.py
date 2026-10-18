#!/usr/bin/env python3
"""Dit si l'orig.tar.gz d'une version est déjà chez Launchpad (PPA) et s'il est identique au local.

Usage : orig_on_launchpad.py ORIG.tar.gz VERSION [--wait SECONDES]

Affiche UN mot sur la sortie standard :
  same       l'orig est déjà dans le PPA avec la même taille et le même SHA-256 -> envoyer avec -sd
  absent     aucun orig de cette version dans le PPA                           -> envoyer avec -sa
  different  un orig de ce nom existe mais son contenu diffère                 -> Launchpad rejetterait
  unknown    l'API de Launchpad n'a pas répondu                                -> repli sur -sa

Méthode : l'API liste les sources publiées (en attente comprises) ; le .dsc d'une d'elles (quelques Ko)
contient le SHA-256 et la taille de l'orig dans « Checksums-Sha256 » : inutile de télécharger l'orig.
Avec --wait, on réessaie jusqu'à ce délai tant que l'orig est absent (file d'attente de Launchpad).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request

ARCHIVE = "https://api.launchpad.net/devel/~paulwoisard/+archive/ubuntu/pdf-equilibrist"
SOURCE = "pdf-equilibrist"


def local_digest(path: str) -> tuple[str, int]:
    h, size = hashlib.sha256(), 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def parse_dsc_orig(dsc_text: str, orig_name: str) -> tuple[str, int] | None:
    """(sha256, taille) de ``orig_name`` d'après la section Checksums-Sha256 d'un .dsc."""
    in_section = False
    for line in dsc_text.splitlines():
        if line.startswith("Checksums-Sha256:"):
            in_section = True
        elif in_section and line.startswith(" "):
            parts = line.split()
            if len(parts) == 3 and parts[2] == orig_name:
                return parts[0], int(parts[1])
        elif in_section:
            in_section = False
    return None


def compare(remote: tuple[str, int] | None, local: tuple[str, int]) -> str:
    if remote is None:
        return "absent"
    return "same" if remote == local else "different"


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:  # nosec B310 - URL https fixe de Launchpad
        return r.read()


def remote_orig(version: str) -> tuple[str, int] | None:
    """Empreinte de l'orig de ``version`` chez Launchpad, ou None s'il n'y est pas."""
    orig_name = f"{SOURCE}_{version}.orig.tar.gz"
    # Toutes les séries, plus récentes d'abord ; on filtre ensuite sur la version.
    query = urllib.parse.urlencode({"ws.op": "getPublishedSources", "source_name": SOURCE,
                                    "order_by_date": "true"})
    entries = json.loads(_get(f"{ARCHIVE}?{query}"))["entries"]
    for entry in entries:
        if not entry["source_package_version"].startswith(f"{version}-"):
            continue
        urls = json.loads(_get(entry["self_link"] + "?ws.op=sourceFileUrls"))
        if not any(u.endswith("/" + orig_name) for u in urls):
            continue
        dsc_url = next((u for u in urls if u.endswith(".dsc")), None)
        if dsc_url is None:
            continue
        found = parse_dsc_orig(_get(dsc_url).decode("utf-8", "replace"), orig_name)
        if found is not None:
            return found
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    path, version = argv[1], argv[2]
    wait = int(argv[argv.index("--wait") + 1]) if "--wait" in argv else 0
    local = local_digest(path)
    deadline = time.monotonic() + wait
    while True:
        try:
            state = compare(remote_orig(version), local)
        except Exception as exc:  # réseau / API : on ne bloque pas la publication
            print(f"avertissement : API Launchpad indisponible ({exc})", file=sys.stderr)
            print("unknown")
            return 0
        if state != "absent" or time.monotonic() >= deadline:
            print(state)
            return 0
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
