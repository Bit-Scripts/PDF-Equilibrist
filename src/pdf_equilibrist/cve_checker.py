from __future__ import annotations

import importlib.metadata
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OSV_API_URL = "https://api.osv.dev/v1/query"
PACKAGE_ECOSYSTEM = "PyPI"
_MAX_WORKERS = 8


def get_installed_packages() -> dict[str, str]:
    """Retourne {nom_normalisé: version} pour tous les paquets installés."""
    packages: dict[str, str] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name", "")
        version = dist.metadata.get("Version", "")
        if name and version:
            packages[name] = version
    return packages


def _fetch_json(url: str, data: bytes, timeout: int = 15) -> dict:
    if not url.startswith("https://"):
        raise ValueError(f"Schéma d'URL non autorisé : {url}")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "PDF-Equilibrist-CVE-Checker/0.1",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return json.load(response)


def query_package_vulnerabilities(package_name: str, version: str) -> list[dict]:
    """Interroge OSV.dev pour un paquet à une version précise."""
    payload = {
        "package": {"name": package_name, "ecosystem": PACKAGE_ECOSYSTEM},
        "version": version,
    }
    try:
        response = _fetch_json(OSV_API_URL, json.dumps(payload).encode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    except urllib.error.URLError:
        return []

    vulnerabilities = []
    for item in response.get("vulns", []) or []:
        aliases = item.get("aliases", []) or []
        cve_ids = [a for a in aliases if a.upper().startswith("CVE-")]
        severity = []
        for sev in item.get("severity", []) or []:
            t = sev.get("type", "")
            s = sev.get("score", "")
            severity.append(f"{t}={s}" if t or s else "N/A")
        vulnerabilities.append({
            "id": item.get("id", ""),
            "cve_ids": cve_ids,
            "summary": item.get("summary", ""),
            "severity": severity,
            "references": item.get("references", []) or [],
        })
    return vulnerabilities


def scan_dependencies(packages: dict[str, str] | None = None) -> list[dict]:
    """
    Scanne les paquets installés contre OSV.dev en parallèle.

    Parameters
    ----------
    packages:
        Dict {nom: version}. Si None, utilise get_installed_packages().

    Returns
    -------
    Liste triée par nom : [{"package", "version", "vulnerabilities"}, ...]
    """
    if packages is None:
        packages = get_installed_packages()

    items = sorted(packages.items(), key=lambda kv: kv[0].lower())

    def _scan_one(name: str, version: str) -> dict:
        return {
            "package": name,
            "version": version,
            "vulnerabilities": query_package_vulnerabilities(name, version),
        }

    results: list[dict] = [None] * len(items)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        future_to_idx = {
            pool.submit(_scan_one, name, ver): i
            for i, (name, ver) in enumerate(items)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    return results


def _project_source_root() -> Path | None:
    """
    Retourne le dossier de code source à analyser (bandit).

    En dev, c'est simplement le dossier de ce fichier. Dans l'exe figé,
    le .spec PyInstaller embarque une copie complète de `src/pdf_equilibrist`
    (datas) précisément pour cet usage — on la retrouve via resource_path().
    Ne retourne None que si, contre toute attente, cette copie est absente.
    """
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        from pdf_equilibrist.utils import resource_path
        bundled = resource_path("pdf_equilibrist")
        return bundled if bundled.exists() else None
    return Path(__file__).resolve().parent


_SEVERITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNDEFINED": 0}


def scan_source_code(source_dir: Path | None = None) -> dict:
    """
    Analyse statique (SAST) du code source du projet lui-même avec bandit,
    en complément du scan des dépendances (SCA) fait par `scan_dependencies`.

    Returns
    -------
    dict :
        {"available": bool, "reason": str, "issues": [...]}
        Chaque issue : {"file", "line", "severity", "confidence",
                        "test_id", "test_name", "issue_text"}
    """
    if source_dir is None:
        source_dir = _project_source_root()

    if source_dir is None:
        return {
            "available": False,
            "reason": "Analyse du code source indisponible : code source introuvable "
                      "(installation corrompue ou incomplète).",
            "issues": [],
        }

    try:
        import logging as _logging

        # Bandit tente de charger tous ses formatteurs de sortie (sarif, csv...)
        # via stevedore ; ceux dont les dépendances optionnelles manquent (ex.
        # sarif_om) loggent une erreur bruyante alors qu'on ne s'en sert jamais
        # ici (on lit les résultats via get_issue_list(), pas via un formatteur).
        _logging.getLogger("stevedore.extension").setLevel(_logging.CRITICAL)

        from bandit.core import config as bandit_config
        from bandit.core import manager as bandit_manager
    except ImportError:
        return {
            "available": False,
            "reason": "Le paquet 'bandit' n'est pas installé (pip install bandit) : "
                      "analyse du code source ignorée.",
            "issues": [],
        }

    try:
        b_conf = bandit_config.BanditConfig()
        b_mgr = bandit_manager.BanditManager(b_conf, "file")
        b_mgr.discover_files([str(source_dir)], recursive=True)
        b_mgr.run_tests()

        issues = []
        for result in b_mgr.get_issue_list():
            try:
                rel_path = os.path.relpath(result.fname, start=str(source_dir.parent))
            except ValueError:
                rel_path = result.fname
            issues.append({
                "file": rel_path,
                "line": result.lineno,
                "severity": str(result.severity),
                "confidence": str(result.confidence),
                "test_id": result.test_id,
                "test_name": result.test,
                "issue_text": result.text,
            })
    except Exception as exc:  # défensif : ne jamais faire planter le scan CVE
        return {
            "available": False,
            "reason": f"Erreur pendant l'analyse bandit : {exc}",
            "issues": [],
        }

    issues.sort(
        key=lambda i: (
            -_SEVERITY_RANK.get(i["severity"].upper(), 0),
            i["file"],
            i["line"],
        )
    )
    return {"available": True, "reason": "", "issues": issues}
