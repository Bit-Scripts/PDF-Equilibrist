"""Cohérence documentation ↔ code ↔ confidentialité.

La documentation (docs/*.md en français, docs/en/*.md en anglais) est la source
unique, synchronisée vers gh-pages. Ces tests échouent quand elle dérive :

* une traduction manque ou n'a plus la même structure que l'original ;
* un fichier ou module cité n'existe plus dans le code ;
* un hôte réseau est cité sans figurer dans network.py / PRIVACY.md ;
* un lien interne est cassé.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SRC = ROOT / "src" / "pdf_equilibrist"

FR_FILES = sorted(DOCS.glob("*.md"))
EN_FILES = sorted((DOCS / "en").glob("*.md"))

_FENCE = re.compile(r"^```.*?^```", re.S | re.M)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _prose(p: Path) -> str:
    """Texte sans blocs de code clôturés (les schémas ASCII ne sont pas vérifiés)."""
    return _FENCE.sub("", _read(p))


def _headings(p: Path) -> list[int]:
    return [len(m.group(1)) for m in re.finditer(r"^(#{1,4}) ", _prose(p), re.M)]


def _details(p: Path) -> int:
    return len(re.findall(r"<details", _read(p)))


# ── 1. Parité FR / EN ────────────────────────────────────────────────────────

def test_docs_exist():
    assert FR_FILES, "aucun document FR"


def test_every_french_doc_has_an_english_twin_and_vice_versa():
    fr = {p.name for p in FR_FILES}
    en = {p.name for p in EN_FILES}
    assert fr == en, f"manquent en EN : {sorted(fr - en)} ; manquent en FR : {sorted(en - fr)}"


@pytest.mark.parametrize("fr", FR_FILES, ids=lambda p: p.name)
def test_translation_has_same_structure(fr):
    en = DOCS / "en" / fr.name
    if not en.exists():
        pytest.skip("couvert par le test de parité des fichiers")
    assert _headings(fr) == _headings(en), (
        f"{fr.name} : la hiérarchie des titres FR et EN diffère — "
        "une section a été ajoutée/retirée d'un seul côté")
    assert _details(fr) == _details(en), f"{fr.name} : nombre de blocs <details> différent"


# ── 2. Références au code ────────────────────────────────────────────────────

# Fichiers cités qui n'appartiennent pas à src/pdf_equilibrist (outils, build…)
_NON_SRC = {"build_docs_pdf.py", "prepare_build.py", "create_pptx_v2.py", "setup.py",
            "conf.py", "split_docs.py"}

_PY_REF = re.compile(r"`((?:[\w./-]+/)?[\w]+\.py)`")


def _known_modules() -> set[str]:
    return {p.name for p in SRC.rglob("*.py")} | {p.name for p in (ROOT / "tools").glob("*.py")} \
        | {p.name for p in (ROOT / "tests").rglob("*.py")}


@pytest.mark.parametrize("doc", FR_FILES + EN_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_cited_python_files_exist(doc):
    known = _known_modules()
    missing = sorted({Path(m).name for m in _PY_REF.findall(_prose(doc))}
                     - known - _NON_SRC)
    assert not missing, f"{doc.name} cite des fichiers .py inexistants : {missing}"


def test_operations_reference_matches_code():
    """Chaque fonction documentée comme `### `nom(...)`` existe dans le code."""
    defined = set()
    for f in SRC.rglob("*.py"):
        defined |= set(re.findall(r"^(?:async )?def (\w+)\(", _read(f), re.M))
    for doc in (DOCS / "4.OPERATIONS.md", DOCS / "en" / "4.OPERATIONS.md"):
        documented = set(re.findall(r"^#{3,4} `(\w+)\(", _read(doc), re.M))
        assert documented, doc
        missing = sorted(documented - defined)
        assert not missing, f"{doc.name} documente des fonctions absentes du code : {missing}"


# ── 3. Hôtes réseau ──────────────────────────────────────────────────────────

_HOST = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|dev|org|io|net|fr|app))\b")


# Hôtes réellement contactés par l'application (source : network.py)
def _app_hosts() -> set[str]:
    net = _read(SRC / "network.py")
    return set(re.findall(r'_HOST = "([^"]+)"', net))


# Hôtes qui peuvent figurer dans la doc sans être contactés par l'application
_DOC_ONLY_HOSTS = {
    "github.com",                # dépôt, releases
    "pdf-equilibrist.org",       # site
    "img.shields.io",            # badges README
    "aur.archlinux.org", "launchpad.net", "copr.fedorainfracloud.org",   # canaux de distribution
    "timestamp.digicert.com",    # horodatage de signature (build uniquement)
    "osv.dev",                   # lien vers la base publique
}


@pytest.mark.parametrize("doc", FR_FILES + EN_FILES + [ROOT / "PRIVACY.md"],
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_hosts_cited_are_declared(doc):
    allowed = _app_hosts() | _DOC_ONLY_HOSTS
    found = {h for h in _HOST.findall(_read(doc))
             if not any(h == a or h.endswith("." + a) for a in allowed)}
    assert not found, (
        f"{doc.name} cite des hôtes que l'application ne déclare pas dans network.py : {sorted(found)}. "
        "Si l'application les contacte, passez par network.urlopen() et documentez-les dans PRIVACY.md.")


def test_privacy_lists_every_app_host():
    privacy = _read(ROOT / "PRIVACY.md")
    for host in _app_hosts():
        assert host in privacy, f"PRIVACY.md ne mentionne pas {host}"


def test_no_stale_ocr_download_claims():
    banned = ("bcebos", ".paddlex", "paddlepaddle", "paddleocr")
    for doc in FR_FILES + EN_FILES + [ROOT / "PRIVACY.md"]:
        text = _read(doc).lower()
        hits = [b for b in banned if b in text]
        assert not hits, f"{doc.name} décrit encore l'ancien OCR ({hits})"


# ── 4. Liens internes ────────────────────────────────────────────────────────

_MD_LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)#\s]+\.md)(?:#[^)]*)?\)")


@pytest.mark.parametrize("doc", FR_FILES + EN_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_internal_links_resolve(doc):
    broken = [t for t in _MD_LINK.findall(_read(doc)) if not (doc.parent / t).exists()]
    assert not broken, f"{doc.name} : liens internes cassés {broken}"


# ── 5. Affirmations obsolètes connues ────────────────────────────────────────

def test_no_windows_only_claim():
    for doc in FR_FILES + EN_FILES:
        text = _read(doc).lower()
        assert "windows-only" not in text and "windows only" not in text, doc.name
