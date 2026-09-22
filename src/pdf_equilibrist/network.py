"""
Point de passage unique de toute connexion sortante de l'application.

PDF-Equilibrist ne contacte que deux services, jamais avec le contenu d'un
document :

    api.github.com   vérification de version, statistiques de la fenêtre
                     « À propos », téléchargement de l'installeur Windows
    api.osv.dev      vérification CVE des dépendances (sur demande)

Tous les appels passent par ``urlopen()`` ci-dessous : quand l'utilisateur a
bloqué les connexions (menu Aide › Connexions Internet), la requête n'est
jamais émise — ``NetworkBlockedError`` est levée avant tout accès réseau.
Le blocage est appliqué ici, au plus bas niveau, et pas seulement en masquant
des boutons : aucun chemin de code ne peut le contourner par oubli.

Module sans dépendance Qt (comme ``operations/``) : l'état est poussé par
``settings.apply_network_policy()`` au démarrage et à chaque changement.
"""
from __future__ import annotations

import urllib.parse
import urllib.request

GITHUB_HOST = "api.github.com"
OSV_HOST = "api.osv.dev"

_blocked = False


class NetworkBlockedError(RuntimeError):
    """Connexion refusée : l'utilisateur a bloqué les accès Internet."""

    def __init__(self, host: str):
        super().__init__(f"Connexions Internet bloquées — requête vers {host} non envoyée")
        self.host = host


def set_blocked(blocked: bool) -> None:
    global _blocked
    _blocked = bool(blocked)


def is_blocked() -> bool:
    return _blocked


def urlopen(request: urllib.request.Request, timeout: float):
    """``urllib.request.urlopen`` soumis à la politique réseau de l'utilisateur."""
    if _blocked:
        raise NetworkBlockedError(urllib.parse.urlsplit(request.full_url).hostname or "?")
    return urllib.request.urlopen(request, timeout=timeout)  # nosec B310
