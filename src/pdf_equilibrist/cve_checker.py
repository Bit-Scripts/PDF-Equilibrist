from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib

OSV_API_URL = "https://api.osv.dev/v1/query"
PACKAGE_ECOSYSTEM = "PyPI"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"


def _clean_requirement_name(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("#"):
        return ""
    line = re.split(r"\s|[<>=!~\[]", line, 1)[0].strip()
    return line


def _parse_requirements(path: Path) -> list[str]:
    if not path.exists():
        return []
    result: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        name = _clean_requirement_name(raw_line)
        if name:
            result.append(name)
    return result


def _parse_pyproject(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    deps: list[str] = []
    project = data.get("project", {}) or {}
    for section in ("dependencies",):
        for item in project.get(section, []) or []:
            name = _clean_requirement_name(item)
            if name:
                deps.append(name)
    optional = project.get("optional-dependencies", {}) or {}
    for extras in optional.values():
        for item in extras or []:
            name = _clean_requirement_name(item)
            if name:
                deps.append(name)
    return deps


def get_project_dependencies() -> list[str]:
    dependencies = []
    dependencies.extend(_parse_requirements(REQUIREMENTS_FILE))
    dependencies.extend(_parse_pyproject(PYPROJECT_FILE))
    normalized = []
    seen: set[str] = set()
    for pkg in dependencies:
        normalized_name = pkg.strip()
        if normalized_name and normalized_name not in seen:
            seen.add(normalized_name)
            normalized.append(normalized_name)
    return normalized


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


def query_package_vulnerabilities(package_name: str) -> list[dict]:
    payload = {
        "package": {
            "name": package_name,
            "ecosystem": PACKAGE_ECOSYSTEM,
        }
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
        cve_ids = [alias for alias in aliases if alias.upper().startswith("CVE-")]
        severity = []
        for sev in item.get("severity", []) or []:
            severity_type = sev.get("type", "")
            score = sev.get("score", "")
            severity.append(f"{severity_type}={score}" if severity_type or score else "N/A")
        vulnerabilities.append(
            {
                "id": item.get("id", ""),
                "cve_ids": cve_ids,
                "summary": item.get("summary", ""),
                "details": item.get("details", ""),
                "severity": severity,
                "references": item.get("references", []) or [],
            }
        )
    return vulnerabilities


def scan_dependencies(package_names: list[str] | None = None) -> list[dict]:
    if package_names is None:
        package_names = get_project_dependencies()
    result = []
    for package_name in sorted(set(package_names), key=str.lower):
        result.append(
            {
                "package": package_name,
                "vulnerabilities": query_package_vulnerabilities(package_name),
            }
        )
    return result
