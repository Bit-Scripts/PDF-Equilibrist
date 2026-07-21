from __future__ import annotations

import io
import json

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
