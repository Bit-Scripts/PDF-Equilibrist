"""
Préférences réseau persistées dans QSettings ("Bit-Scripts"/"PDF-Equilibrist",
comme la langue — voir ``i18n.py``).

Deux réglages, exposés dans le menu Aide › Connexions Internet :

``network/blocked``
    Bloque toute connexion sortante (vérification de version, statistiques,
    vérification CVE, téléchargement). Appliqué dans ``network.urlopen()``.
    Désactivé par défaut.

``network/check_updates_on_startup``
    Vérifie au démarrage si une nouvelle version existe. Activé par défaut
    **uniquement sous Windows**, seul canal où l'application se met à jour
    elle-même : sous Linux (AUR, PPA, COPR, Flatpak), c'est le travail du
    gestionnaire de paquets, et une requête au lancement n'y a pas sa place.
    La vérification manuelle (menu Aide) reste disponible partout.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import QSettings

from pdf_equilibrist import network

_KEY_BLOCKED = "network/blocked"
_KEY_STARTUP_CHECK = "network/check_updates_on_startup"


def _settings() -> QSettings:
    return QSettings("Bit-Scripts", "PDF-Equilibrist")


def network_blocked() -> bool:
    return bool(_settings().value(_KEY_BLOCKED, False, type=bool))


def set_network_blocked(blocked: bool) -> None:
    _settings().setValue(_KEY_BLOCKED, bool(blocked))
    network.set_blocked(blocked)


def startup_update_check() -> bool:
    return bool(_settings().value(_KEY_STARTUP_CHECK, sys.platform == "win32", type=bool))


def set_startup_update_check(enabled: bool) -> None:
    _settings().setValue(_KEY_STARTUP_CHECK, bool(enabled))


def apply_network_policy() -> None:
    """Pousse la préférence enregistrée dans ``network`` — à appeler au démarrage."""
    network.set_blocked(network_blocked())
