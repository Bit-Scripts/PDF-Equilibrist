from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from pdf_equilibrist import cve_checker


def test_get_installed_packages():
    pkgs = cve_checker.get_installed_packages()
    assert isinstance(pkgs, dict)
    assert len(pkgs) > 0
    # vérifie qu'on a bien des versions non-vides
    for name, version in pkgs.items():
        assert name
        assert version


def test_query_package_vulnerabilities(monkeypatch: pytest.MonkeyPatch):
    sample = {
        "vulns": [
            {
                "id": "PYSEC-0000",
                "aliases": ["CVE-2024-12345"],
                "summary": "Example vulnerability.",
                "severity": [{"type": "CVSS_V3", "score": "7.5"}],
                "references": [{"type": "WEB", "url": "https://example.com"}],
            }
        ]
    }

    class DummyResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=...):
        return DummyResponse(json.dumps(sample).encode("utf-8"))

    monkeypatch.setattr(cve_checker.urllib.request, "urlopen", fake_urlopen)

    result = cve_checker.query_package_vulnerabilities("PyQt6", "6.11.0")

    assert len(result) == 1
    vuln = result[0]
    assert vuln["cve_ids"] == ["CVE-2024-12345"]
    assert vuln["severity"] == ["CVSS_V3=7.5"]
    assert vuln["references"][0]["url"] == "https://example.com"


def test_scan_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        cve_checker, "query_package_vulnerabilities", lambda name, version: []
    )
    results = cve_checker.scan_dependencies({"PyQt6": "6.11.0", "fitz": "1.27.0"})
    assert len(results) == 2
    assert all("version" in r for r in results)
    assert all(r["vulnerabilities"] == [] for r in results)


def test_scan_source_code_unavailable_when_frozen_without_bundled_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    # Simule un exe figé dont la copie de code source embarquée (datas du
    # .spec) serait absente/corrompue : doit rester indisponible proprement.
    monkeypatch.setattr(cve_checker.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cve_checker.sys, "_MEIPASS", str(tmp_path), raising=False)
    result = cve_checker.scan_source_code()
    assert result["available"] is False
    assert result["issues"] == []


def test_project_source_root_frozen_uses_bundled_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    # Simule un exe figé où le .spec a bien embarqué la copie du code source
    # (cas réel) : _project_source_root() doit la retrouver via resource_path().
    (tmp_path / "pdf_equilibrist").mkdir()
    monkeypatch.setattr(cve_checker.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cve_checker.sys, "_MEIPASS", str(tmp_path), raising=False)
    root = cve_checker._project_source_root()
    assert root == tmp_path / "pdf_equilibrist"


def test_scan_source_code_missing_bandit(monkeypatch: pytest.MonkeyPatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("bandit"):
            raise ImportError("no bandit")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = cve_checker.scan_source_code(source_dir=tmp_path)
    assert result["available"] is False
    assert "bandit" in result["reason"].lower()


def test_scan_source_code_runs_on_project():
    pytest.importorskip("bandit")
    source_dir = Path(cve_checker.__file__).resolve().parent
    result = cve_checker.scan_source_code(source_dir=source_dir)
    assert result["available"] is True
    assert isinstance(result["issues"], list)
    for issue in result["issues"]:
        assert issue["severity"] in {"HIGH", "MEDIUM", "LOW", "UNDEFINED"}
        assert issue["file"]
        assert issue["line"] >= 0
