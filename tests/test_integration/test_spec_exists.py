from pathlib import Path


def test_spec_file_exists_and_is_valid():
    spec = Path("PDF-Equilibrist.spec")
    assert spec.exists(), "PDF-Equilibrist.spec is missing at repo root"
    content = spec.read_text(encoding="utf-8")
    assert "Analysis(" in content or "PYZ(" in content, "Spec file doesn't look like a PyInstaller spec"
