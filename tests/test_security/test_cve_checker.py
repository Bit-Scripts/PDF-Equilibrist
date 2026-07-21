from __future__ import annotations

import io
import json
from pathlib import Path
import pytest

from pdf_equilibrist import cve_checker


def test_parse_requirements(tmp_path: Path):
    content = """
    PyQt6>=6.11
    pdfplumber==0.11
    # comment
    openpyxl>=3.1
    """
    req = tmp_path / "requirements.txt"
    req.write_text(content, encoding="utf-8")

    result = cve_checker._parse_requirements(req)

    assert result == ["PyQt6", "pdfplumber", "openpyxl"]


def test_parse_pyproject(tmp_path: Path):
    content = """
    [project]
    dependencies = [
      "PyQt6>=6.11",
      "Pillow>=12",
    ]

    [project.optional-dependencies]
    dev = ["pytest>=8.0"]
    """
    file_path = tmp_path / "pyproject.toml"
    file_path.write_text(content, encoding="utf-8")

    result = cve_checker._parse_pyproject(file_path)

    assert result == ["PyQt6", "Pillow", "pytest"]


def test_query_package_vulnerabilities(monkeypatch: pytest.MonkeyPatch):
    sample = {
        "vulns": [
            {
                "id": "PYSEC-0000",
                "aliases": ["CVE-2024-12345"],
                "summary": "Example vulnerability.",
                "details": "Detail text.",
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

    result = cve_checker.query_package_vulnerabilities("PyQt6")

    assert len(result) == 1
    vuln = result[0]
    assert vuln["cve_ids"] == ["CVE-2024-12345"]
    assert vuln["severity"] == ["CVSS_V3=7.5"]
    assert vuln["references"][0]["url"] == "https://example.com"
