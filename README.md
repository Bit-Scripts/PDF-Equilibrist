# ![PDF-Equilibrist Logo](assets/logo/PDF-Equilibrist-logo.png)

# PDF-Equilibrist!

![Build Status](https://github.com/Bit-Scripts/PDF-Equilibrist/workflows/build.yml/badge.svg)
![License](https://img.shields.io/github/license/Bit-Scripts/PDF-Equilibrist)
![Platform](https://img.shields.io/badge/platform-linux%20|%20macOS%20|%20windows-lightgrey)

## Description

**PDF-Equilibrist!** est un éditeur PDF open-source et polyvalent conçu pour manipuler les PDF avec précision. Le projet vise à offrir une solution intuitive et puissante pour visualiser, éditer, et annoter des fichiers PDF sans compromettre leur qualité. Avec des fonctionnalités avancées, telles que la sélection de texte et d'images, l'ajout de pages, et bien plus encore, **PDF-Equilibrist!** se distingue par sa flexibilité et son efficacité.

---

## Fonctionnalités

- **Affichage vectoriel** des pages PDF pour une qualité optimale.
- **Sélection et copie** de textes et d’images directement depuis le PDF.
- **Insertion, rotation et extraction** de pages pour une gestion avancée des documents.
- **Masquage et remplacement de texte** avec la police d’origine pour une édition discrète.
- **Interface utilisateur** basée sur Qt pour une expérience intuitive et fluide.

---

## Captures d'écran

![Capture d'écran de PDF-Equilibrist](assets/screenshots/screenshot1.png)

---

## Installation

### Prérequis

- **CMake** pour la gestion de la compilation.
- **Qt** (version 5 ou 6) pour l’interface graphique.
- **Poppler** avec bindings Qt pour la manipulation des PDF (installable via les gestionnaires de paquets comme Chocolatey, Winget, Homebrew, etc.).

### Instructions

1. Clonez le dépôt :
   ```bash
   git clone git@github.com:Bit-Scripts/PDF-Equilibrist.git
   cd PDF-Equilibrist
   ```

2. Créez le répertoire de build et compilez le projet avec CMake :
    ```bash
    mkdir build
    cd build
    cmake ..
    make
    ```
   
3. Lancez l'application :
    ```bash
    ./PDFEquilibrist
    ```
---

### Utilisation

- Ouvrir un PDF : Cliquez sur "Ouvrir un PDF" et sélectionnez le fichier PDF souhaité.
- Naviguer entre les pages : Utilisez la liste déroulante pour changer de page.
- Édition et annotation :
  - Masquage et réécriture de textes sélectionnés.
  - Ajout de nouvelles images sur des pages existantes.

---

### Développement

#### Structure du projet

    ```bash
    PDF-Equilibrist
    ├── assets/                 # Contient les ressources (ex : captures d'écran)
    ├── lib/                    # Bibliothèques externes (si nécessaire)
    ├── src/                    # Code source principal du projet
    │   ├── main.cpp            # Point d'entrée principal de l'application
    │   ├── PDFEditor.cpp/.h    # Classe pour l'édition de PDF
    │   └── ...                 # Autres fichiers sources et en-têtes
    ├── .github/workflows/      # Configuration CI/CD pour GitHub Actions
    ├── CMakeLists.txt          # Configuration de CMake
    ├── LICENSE.md              # Licence du projet
    └── README.md               # Documentation du projet
    ```

---

#### Contribuer

Les contributions sont les bienvenues ! Si vous avez une idée de fonctionnalité, n'hésitez pas à ouvrir une issue ou à soumettre une pull request.

1. Forkez le projet.
2. Créez une nouvelle branche (git checkout -b feature/ma-fonctionnalité).
3. Effectuez vos modifications et committez (git commit -m 'Ajout de ma fonctionnalité').
4. Poussez vers la branche (git push origin feature/ma-fonctionnalité).
5. Ouvrez une pull request.

---

#### Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE.md](./LICENSE.md) pour plus de détails.

---

#### Remerciements

Un grand merci à toutes les bibliothèques open-source et contributeurs qui rendent ce projet possible, en particulier Qt et Poppler pour leurs API puissantes.

**PDF-Equilibrist!** - Manipulez vos PDF avec équilibre et précision.