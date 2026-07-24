# PDF-Equilibrist

[![CI](https://github.com/Bit-Scripts/PDF-Equilibrist/actions/workflows/ci.yml/badge.svg)](https://github.com/Bit-Scripts/PDF-Equilibrist/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Bit-Scripts/PDF-Equilibrist?cacheSeconds=3600)](https://github.com/Bit-Scripts/PDF-Equilibrist/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Bit-Scripts/PDF-Equilibrist/total?cacheSeconds=3600)](https://github.com/Bit-Scripts/PDF-Equilibrist/releases)
[![License](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE.md)

PDF-Equilibrist est un éditeur PDF de bureau construit en Python avec PyQt6 et PyMuPDF.
Il permet de modifier, convertir, annoter, protéger et exporter des documents PDF.

## Installation

1. Créez un environnement Python compatible (`>=3.12`).
2. Installez les dépendances :

```powershell
python -m pip install -r requirements.txt
```

3. Exécutez l’application :

```powershell
python src/pdf_equilibrist/main.py
```

## Construction et packaging

- Le script NSIS d’installation se trouve dans `installer/PDF-Equilibrist.nsi`.
- Les artefacts compilés ne doivent pas être suivis dans le dépôt source.
- Les sorties de build sont ignorées par `.gitignore`.

## Documentation

La documentation source se trouve dans le dossier `docs/`.

## Licence

Ce projet est distribué sous licence GNU GPL v3.0 (ou ultérieure). Voir [LICENSE.md](LICENSE.md).
