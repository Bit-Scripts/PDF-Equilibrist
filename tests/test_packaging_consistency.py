"""La version de RapidOCR (modèles inclus dans la wheel) doit être la même partout où elle est figée.

Des canaux qui embarquent des versions différentes donneraient un OCR différent d'une plateforme à
l'autre, et une version non testée en CI de paquets pourrait partir en release.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# fichier → motif capturant la version figée de rapidocr
_PINS = {
    "requirements.txt": r"^rapidocr==([\d.]+)",
    "environment.yml": r"^\s*-\s*rapidocr==([\d.]+)",
    "packaging/copr/pdf-equilibrist.spec": r"rapidocr-([\d.]+)-py3-none-any\.whl",
    "packaging/aur/PKGBUILD": r"rapidocr-([\d.]+)-py3-none-any\.whl",
    "packaging/ppa/fetch_wheelhouse.sh": r"rapidocr==([\d.]+)",
    ".github/workflows/linux-copr-publish.yml": r"rapidocr==([\d.]+)",
    ".github/workflows/linux-packages-check.yml": r"rapidocr==([\d.]+)",
}


def _version(rel: str, pattern: str) -> str:
    text = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(pattern, text, re.M)
    assert m, f"{rel} : version figée de rapidocr introuvable"
    return m.group(1)


def test_rapidocr_is_pinned_to_the_same_version_everywhere():
    versions = {rel: _version(rel, pat) for rel, pat in _PINS.items()}
    assert len(set(versions.values())) == 1, versions


def test_pyproject_range_contains_the_pinned_version():
    pinned = _version("requirements.txt", _PINS["requirements.txt"])
    m = re.search(r'"rapidocr>=([\d.]+),<([\d.]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert m, "pyproject.toml : plage rapidocr introuvable"

    def key(v):
        return tuple(int(x) for x in v.split("."))
    assert key(m.group(1)) <= key(pinned) < key(m.group(2)), (pinned, m.groups())


def test_aur_wheel_checksum_is_declared():
    """Le PKGBUILD doit déclarer autant de sommes que de sources (la wheel rapidocr en dernier)."""
    text = (ROOT / "packaging/aur/PKGBUILD").read_text(encoding="utf-8")
    src = re.search(r"^source=\((.*?)^\)", text, re.S | re.M).group(1)
    sums = re.search(r"^sha256sums=\((.*?)^\)", text, re.S | re.M).group(1)
    n_src = len(re.findall(r'^\s*"', src, re.M))
    n_sum = len(re.findall(r"^\s*'[0-9a-f]{64}'", sums, re.M))
    assert n_src == n_sum, (n_src, n_sum)
    assert "rapidocr" in src.strip().splitlines()[-1], "la wheel rapidocr doit rester la dernière source"
