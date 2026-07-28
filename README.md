# PDF-Equilibrist

<div align="center">

[![Website](https://img.shields.io/badge/site-pdf--equilibrist.org-6BBF4E)](https://pdf-equilibrist.org)
[![Release](https://img.shields.io/github/v/release/Bit-Scripts/PDF-Equilibrist?cacheSeconds=3600)](https://github.com/Bit-Scripts/PDF-Equilibrist/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Bit-Scripts/PDF-Equilibrist/total?cacheSeconds=3600)](https://github.com/Bit-Scripts/PDF-Equilibrist/releases)
[![AUR](https://img.shields.io/aur/version/pdf-equilibrist)](https://aur.archlinux.org/packages/pdf-equilibrist)
[![PPA Ubuntu](https://img.shields.io/badge/PPA-ubuntu-orange)](https://launchpad.net/~paulwoisard/+archive/ubuntu/pdf-equilibrist)
[![COPR Fedora](https://img.shields.io/badge/COPR-fedora-blue)](https://copr.fedorainfracloud.org/coprs/paullux/PDF-Equilibrist/)

[![CI](https://github.com/Bit-Scripts/PDF-Equilibrist/actions/workflows/ci.yml/badge.svg)](https://github.com/Bit-Scripts/PDF-Equilibrist/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE.md)
[![Bandit](https://img.shields.io/badge/Bandit-Passed-brightgreen.svg)](.)
[![Dependencies](https://img.shields.io/badge/Dependencies-Clean-brightgreen.svg)](.)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Local-brightgreen.svg)](.)

</div>

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

🌐 Site officiel : [pdf-equilibrist.org](https://pdf-equilibrist.org)

📦 **Windows** — téléchargez le dernier installeur dans les [Releases GitHub](https://github.com/Bit-Scripts/PDF-Equilibrist/releases/latest).

🐧 **Arch Linux** (AUR) :

```bash
yay -S pdf-equilibrist
# ou : paru -S pdf-equilibrist
```

→ [Page AUR](https://aur.archlinux.org/packages/pdf-equilibrist)

🐧 **Ubuntu / Debian** (PPA) :

```bash
sudo add-apt-repository ppa:paulwoisard/pdf-equilibrist
sudo apt update
sudo apt install pdf-equilibrist
```

→ [Page Launchpad](https://launchpad.net/~paulwoisard/+archive/ubuntu/pdf-equilibrist)

🐧 **Fedora** (COPR) :

```bash
sudo dnf copr enable paullux/PDF-Equilibrist
sudo dnf install pdf-equilibrist
```

→ [Page COPR](https://copr.fedorainfracloud.org/coprs/paullux/PDF-Equilibrist/)

### Installation depuis les sources (développeurs)

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
