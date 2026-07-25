# PDF-Equilibrist

[![CI](https://github.com/Bit-Scripts/PDF-Equilibrist/actions/workflows/ci.yml/badge.svg)](https://github.com/Bit-Scripts/PDF-Equilibrist/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Bit-Scripts/PDF-Equilibrist?cacheSeconds=3600)](https://github.com/Bit-Scripts/PDF-Equilibrist/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Bit-Scripts/PDF-Equilibrist/total?cacheSeconds=3600)](https://github.com/Bit-Scripts/PDF-Equilibrist/releases)
[![License](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE.md)
[![Bandit](https://img.shields.io/badge/Bandit-Passed-brightgreen.svg)](.)
[![Dependencies](https://img.shields.io/badge/Dependencies-Clean-brightgreen.svg)](.)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Local-brightgreen.svg)](.)

**PDF-Equilibrist** est un éditeur PDF de bureau, gratuit et open-source, construit en Python
avec **PyQt6** et **PyMuPDF**. Il fonctionne entièrement en local — pas de cloud, pas de
télémétrie, pas de compte requis — et permet de lire, modifier, convertir, annoter et
protéger vos documents PDF.

![PDF-Equilibrist](assets/images/PDF-Equilibrist.png)

## Fonctionnalités

### Affichage
Zoom, rotation, navigation multi-onglets et multi-pages.

![Affichage](assets/images/feature-afficher.png)

### Édition
Modification de texte, filigrane, signatures et tampons.

![Édition](assets/images/feature-modifier.png)

### Annotation
Surlignage, barré, soulignement, zones de texte.

![Annotation](assets/images/feature-annoter.png)

### Pages
Insertion, division, fusion, inversion.

![Pages](assets/images/feature-page.png)

### Conversion
Word, Excel, PowerPoint, images, Office → PDF, image → PDF, OCR local, traitement par lot.

![Conversion](assets/images/feature-convertir.png)

### Protection
Chiffrement et déchiffrement AES-256.

![Protection](assets/images/feature-proteger.png)

## Sécurité & confidentialité

Contrairement aux outils PDF en ligne qui envoient vos fichiers sur des serveurs tiers,
PDF-Equilibrist exécute tous ses traitements à 100 % en local.

L'application embarque aussi son propre outil d'audit de sécurité, accessible en un clic
depuis l'interface :

- **Analyse SAST du code source** via [Bandit](https://github.com/PyCQA/bandit).
- **Vérification des dépendances** contre les vulnérabilités connues via l'API [OSV](https://osv.dev/).

![Outil d'analyse de sécurité](assets/images/Outil-Analyse-Security.png)

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
