# Packaging AUR — PDF-Equilibrist

Ce dossier contient le `PKGBUILD` pour publier PDF-Equilibrist sur l'AUR
(`aur.archlinux.org/packages/pdf-equilibrist`).

## Fichiers

- `PKGBUILD` — recette de build (dépendances, build wheel + installer, installation
  des assets `.desktop`/AppStream/icônes).
- `.SRCINFO` — métadonnées lues par les helpers AUR (yay, paru…) et le site AUR.
- `io.github.BitScripts.PDFEquilibrist.desktop`, `.metainfo.xml`, `-128.png`, `-256.png`
  — copies locales des assets `packaging/flatpak/` (le tag `v0.1.10` a été créé
  **avant** leur ajout au dépôt, donc le tarball de release ne les contient pas —
  on ne peut pas les extraire de la source taggée, il faut les embarquer ici).

**Important** : `.SRCINFO` a été écrit à la main (pas de `makepkg` disponible sur la
machine de dev Windows) — à **régénérer avant tout push** avec :

```bash
makepkg --printsrcinfo > .SRCINFO
```

Ne jamais pousser un `.SRCINFO` désynchronisé du `PKGBUILD` : c'est une violation
des règles AUR (le site utilise `.SRCINFO` pour afficher les infos, `makepkg` utilise
le `PKGBUILD` pour builder — un écart entre les deux trompe les utilisateurs).

## Dépendances Arch/AUR utilisées

| Dépendance pip (`pyproject.toml`) | Paquet Arch/AUR |
|---|---|
| PyQt6 | `python-pyqt6` (officiel, extra) |
| PyMuPDF | `python-pymupdf` (officiel, extra) |
| pdf2docx | `python-pdf2docx` (AUR) |
| pdfplumber | `python-pdfplumber` (AUR) |
| openpyxl | `python-openpyxl` (officiel, extra) |
| python-pptx | `python-pptx` (AUR) |
| Pillow | `python-pillow` (officiel, extra) |
| pyparsing | `python-pyparsing` (officiel, extra) |
| bandit | **non empaqueté** (ni officiel ni AUR) — exclu, `optdepends` avec `pip install --user bandit` en solution manuelle, cohérent avec l'exclusion déjà faite côté Flatpak (voir `packaging/flatpak/README.md`) |

Les paquets AUR ci-dessus (`python-pdf2docx`, `python-pdfplumber`, `python-pptx`)
sont maintenus par des tiers — vérifier qu'ils sont toujours actifs/à jour avant
publication, sinon les vendoriser directement dans `depends` via leurs propres
sources ou les prendre en charge soi-même.

## Build local de test (nécessite un environnement Arch)

```bash
cd packaging/aur
makepkg -si
```

## Mise à jour à chaque nouvelle release

1. Bump `pkgver` (et remettre `pkgrel=1`) dans `PKGBUILD` pour matcher le nouveau tag Git.
2. Recalculer le sha256 de l'archive :

   ```bash
   curl -sL "https://github.com/Bit-Scripts/PDF-Equilibrist/archive/refs/tags/v<version>.tar.gz" \
       | sha256sum
   ```

3. Régénérer `.SRCINFO` (`makepkg --printsrcinfo > .SRCINFO`).
4. Tester avec `makepkg -si`.
5. Commit + push vers le dépôt git AUR (`ssh://aur@aur.archlinux.org/pdf-equilibrist.git`).

## Publication (manuelle, sans revue humaine)

Contrairement à Flathub, l'AUR n'a pas de comité de revue ni de politique éditoriale
sur le contenu — la publication est immédiate dès le push :

```bash
git clone ssh://aur@aur.archlinux.org/pdf-equilibrist.git aur-pdf-equilibrist
cp PKGBUILD .SRCINFO aur-pdf-equilibrist/
cd aur-pdf-equilibrist
git add PKGBUILD .SRCINFO
git commit -m "Initial import: pdf-equilibrist 0.1.10"
git push
```

Nécessite une clé SSH ajoutée au compte AUR (voir
[aur.archlinux.org/account](https://aur.archlinux.org/account)).
