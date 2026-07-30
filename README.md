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

**🇫🇷 [Lire en français](README.fr.md)**

</div>

**PDF-Equilibrist** is a free, open-source desktop PDF editor built in Python with
**PyQt6** and **PyMuPDF**. It runs entirely locally — no cloud, no telemetry, no account
required — and lets you read, edit, convert, annotate and protect your PDF documents.

![PDF-Equilibrist](assets/images/PDF-Equilibrist.png)

## Features

### Display
Zoom, rotation, multi-tab and multi-page navigation.

![Display](assets/images/feature-afficher.png)

### Edit
Text editing, watermarks, signatures and stamps.

![Edit](assets/images/feature-modifier.png)

### Annotate
Highlight, strikethrough, underline, text boxes.

![Annotate](assets/images/feature-annoter.png)

### Pages
Insert, split, merge, reverse.

![Pages](assets/images/feature-page.png)

### Convert
Word, Excel, PowerPoint, images, Office → PDF, image → PDF, local OCR, batch processing.

![Convert](assets/images/feature-convertir.png)

### Protect
AES-256 encryption and decryption.

![Protect](assets/images/feature-proteger.png)

## Security & privacy

Unlike online PDF tools that send your files to third-party servers, PDF-Equilibrist runs
all its processing 100% locally.

The application also embeds its own security audit tool, accessible in one click from the
interface:

- **SAST analysis of the source code** via [Bandit](https://github.com/PyCQA/bandit).
- **Dependency checking** against known vulnerabilities via the [OSV](https://osv.dev/) API.

![Security analysis tool](assets/images/Outil-Analyse-Security.png)

## Installation

🌐 Official website: [pdf-equilibrist.org](https://pdf-equilibrist.org)

📦 **Windows** — download the latest installer from the [GitHub Releases](https://github.com/Bit-Scripts/PDF-Equilibrist/releases/latest).

🐧 **Arch Linux** (AUR):

```bash
yay -S pdf-equilibrist
# or: paru -S pdf-equilibrist
```

→ [AUR page](https://aur.archlinux.org/packages/pdf-equilibrist)

🐧 **Ubuntu / Debian** (PPA):

```bash
sudo add-apt-repository ppa:paulwoisard/pdf-equilibrist
sudo apt update
sudo apt install pdf-equilibrist
```

→ [Launchpad page](https://launchpad.net/~paulwoisard/+archive/ubuntu/pdf-equilibrist)

🐧 **Fedora** (COPR):

```bash
sudo dnf copr enable paullux/PDF-Equilibrist
sudo dnf install pdf-equilibrist
```

→ [COPR page](https://copr.fedorainfracloud.org/coprs/paullux/PDF-Equilibrist/)

### Installing from source (developers)

1. Create a compatible Python environment (`>=3.12`).
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Run the application:

```powershell
python src/pdf_equilibrist/main.py
```

## Building and packaging

- The NSIS install script lives in `installer/PDF-Equilibrist.nsi`.
- Build artifacts must not be tracked in the source repository.
- Build outputs are ignored via `.gitignore`.

## Documentation

Source documentation lives in the `docs/` folder.

## License

This project is distributed under the GNU GPL v3.0 license (or later). See [LICENSE.md](LICENSE.md).
