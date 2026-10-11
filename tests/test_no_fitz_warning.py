"""Plus d'avertissement « The `fitz` API is deprecated… » (affiché par PyMuPDF à chaque `import fitz`)."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_our_code_never_imports_the_deprecated_fitz_module():
    offenders = []
    for base in ("src", "tests", "tools"):
        for p in (ROOT / base).rglob("*.py"):
            if p.name == "test_no_fitz_warning.py":
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if re.match(r"\s*(import fitz\b|from fitz\b)", line):
                    offenders.append(f"{p.relative_to(ROOT)}:{n}")
    assert not offenders, f"utiliser `import pymupdf` : {offenders}"


def test_starting_the_app_stack_prints_no_fitz_warning():
    """Un processus neuf qui charge le paquet, pdf2docx (qui importe encore `fitz`), l'OCR et les
    conversions ne doit rien afficher : l'alias `fitz` → `pymupdf` est posé avant la dépendance."""
    code = (
        "import pdf_equilibrist\n"
        "import pdf2docx\n"
        "from pdf2docx import Converter\n"
        "import pdf_equilibrist.operations.convert, pdf_equilibrist.operations.ocr\n"
        "import pymupdf, sys\n"
        "assert sys.modules['fitz'] is pymupdf\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    output = (r.stdout + r.stderr).lower()
    assert "deprecated" not in output and "fitz" not in output, output
