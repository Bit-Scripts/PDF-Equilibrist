# Packaging Flatpak — PDF-Equilibrist

Ce dossier contient les fichiers nécessaires à la publication de PDF-Equilibrist
sur Flathub (App ID : `io.github.Bit-Scripts.PDFEquilibrist`).

## Fichiers

- `io.github.Bit-Scripts.PDFEquilibrist.yml` — manifest Flatpak (runtime, dépendances, permissions)
- `io.github.Bit-Scripts.PDFEquilibrist.desktop` — entrée de menu (nom, icône, MimeType PDF)
- `io.github.Bit-Scripts.PDFEquilibrist.metainfo.xml` — métadonnées AppStream (description, captures d'écran, licence)
- `icons/` — icônes hicolor (128×128, 256×256) dérivées de `assets/logo/PDF-Equilibrist-logo.png`

## Générer les dépendances Python (obligatoire avant tout build)

`generated-sources.json` n'est **pas** commité (il contient des URLs de wheels PyPI + sha256
qui doivent être régénérées à chaque changement de dépendances). À produire sur une machine
Linux avec accès réseau :

```bash
pip install --user git+https://github.com/flatpak/flatpak-builder-tools.git#subdirectory=pip
flatpak-pip-generator --output packaging/flatpak/generated-sources \
    PyQt6 PyMuPDF pdf2docx pdfplumber openpyxl python-pptx Pillow pyparsing
```

Ne pas inclure `bandit` (dev/scan uniquement) ni `paddleocr`/`paddlepaddle` (OCR exclu de la v1 —
voir la mémoire projet sur le portage Flathub).

## Build local de test

```bash
flatpak-builder --user --install --force-clean build-dir \
    packaging/flatpak/io.github.Bit-Scripts.PDFEquilibrist.yml
flatpak run io.github.Bit-Scripts.PDFEquilibrist
```

Pour itérer sur le code local sans repasser par un tag Git à chaque fois, remplacer
temporairement la source `type: git` du module `pdf-equilibrist` par :

```yaml
sources:
  - type: dir
    path: ../..
```

**Ne jamais soumettre ce `type: dir` à Flathub** — la revue exige une source reproductible
(`type: git` avec tag, ou `type: archive` avec sha256).

## Validation AppStream

```bash
appstreamcli validate packaging/flatpak/io.github.Bit-Scripts.PDFEquilibrist.metainfo.xml
```

## Soumission Flathub (manuelle, unique)

Flathub ne reçoit pas de binaire poussé par CI — la soumission initiale se fait via une PR
vers l'organisation `flathub` (voir https://docs.flathub.org/docs/for-app-authors/submission).
Une fois le repo `github.com/flathub/io.github.Bit-Scripts.PDFEquilibrist` créé et l'app
acceptée, les mises à jour se font en proposant une MAJ du manifest (nouveau tag + sha) dans
ce repo — c'est cette étape-là qui peut être automatisée par CI à chaque release.
