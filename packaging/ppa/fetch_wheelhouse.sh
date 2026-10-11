#!/usr/bin/env bash
# Télécharge les wheels vendorisées pour la PPA (builders Launchpad SANS réseau).
#
# Source unique de la liste des paquets : utilisée par le workflow de publication
# (.github/workflows/linux-ppa-publish.yml) ET par le workflow de vérification
# (.github/workflows/linux-packages-check.yml). Toute dépendance ajoutée ici doit
# aussi figurer dans la liste `pip install --no-deps` de packaging/ppa/debian/rules.
#
# Usage : packaging/ppa/fetch_wheelhouse.sh   (depuis la racine du dépôt)
#
# Résultat :
#   packaging/ppa/vendor/wheelhouse/           — noble (CPython 3.12) : TOUS les paquets
#   packaging/ppa/vendor/wheelhouse-resolute/  — resolute (CPython 3.14) : seulement les
#       wheels liées à l'ABI CPython ; les autres (py3-none-any, abi3) sont retrouvées dans
#       le wheelhouse noble grâce au double --find-links de debian/rules.
#
# Téléchargement croisé (--python-version/--abi/--platform) : indépendant de la version
# de Python de la machine qui exécute le script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NOBLE="$ROOT/packaging/ppa/vendor/wheelhouse"
RESOLUTE="$ROOT/packaging/ppa/vendor/wheelhouse-resolute"
mkdir -p "$NOBLE" "$RESOLUTE"

PLATFORMS=(--platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64
           --platform manylinux_2_24_x86_64 --platform manylinux_2_17_x86_64
           --platform manylinux2014_x86_64)

# cryptography est épinglée à >=50.0.0 : la 49.0.0 est vulnérable à CVE-2026-69247
# (GHSA-g6cj-pr64-35w5, oracle Bleichenbacher sur PKCS#7 EnvelopedData, corrigé en
# 50.0.0) — trouvée par le vérificateur de CVE intégré à l'app sur un paquet publié.
#
# OCR (RapidOCR + ONNX Runtime) : rapidocr livre ses modèles .onnx DANS sa wheel —
# aucun téléchargement à l'exécution. Fermeture complète des dépendances :
# rapidocr onnxruntime omegaconf protobuf pyclipper PyYAML shapely six colorlog
# colorama flatbuffers packaging requests idna urllib3 certifi tqdm.
PACKAGES=(
  cffi charset-normalizer "cryptography>=50.0.0" et-xmlfile fire fonttools lxml
  numpy opencv-python-headless openpyxl pdf2docx pdfminer.six
  pdfplumber Pillow pycparser PyMuPDF pyparsing pypdfium2
  python-docx python-pptx termcolor typing-extensions XlsxWriter
  rapidocr==3.10.0 onnxruntime omegaconf protobuf pyclipper PyYAML shapely six colorlog
  colorama flatbuffers packaging requests idna urllib3 certifi tqdm
)

# Wheels compilées liées à l'ABI CPython (pas abi3, pas py3-none-any)
ABI_PACKAGES=(
  cffi charset-normalizer fonttools lxml numpy pillow
  onnxruntime pyclipper PyYAML shapely
)

echo "== noble (cp312) : ${#PACKAGES[@]} paquets"
pip download --no-deps --only-binary=:all: --dest "$NOBLE" \
  --python-version 3.12 --implementation cp --abi cp312 "${PLATFORMS[@]}" \
  "${PACKAGES[@]}"

echo "== resolute (cp314) : ${#ABI_PACKAGES[@]} paquets liés à l'ABI"
pip download --no-deps --only-binary=:all: --dest "$RESOLUTE" \
  --python-version 3.14 --implementation cp --abi cp314 "${PLATFORMS[@]}" \
  "${ABI_PACKAGES[@]}"

ls "$NOBLE" | wc -l | xargs echo "wheelhouse noble :"
ls "$RESOLUTE" | wc -l | xargs echo "wheelhouse resolute :"
