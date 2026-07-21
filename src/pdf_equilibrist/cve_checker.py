from __future__ import annotations

import importlib.metadata
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "PDF-Equilibrist-CVE-Checker/0.1",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
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
