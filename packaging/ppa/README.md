# Packaging PPA (Launchpad) — PDF-Equilibrist

Ce dossier contient les fichiers `debian/` pour publier PDF-Equilibrist sur un
PPA Launchpad (`ppa:paulwoisard/pdf-equilibrist`).

## Fichiers

- `debian/` — recette de build Debian (`control`, `rules`, `changelog`, `copyright`,
  `source/format`, l'entrée `.desktop` et le script de lancement).
- `vendor/wheelhouse/` — **non commité** (voir `.gitignore`), wheels vendorisées
  pour les dépendances non empaquetées sur Ubuntu/Debian (`pdf2docx`, `pdfplumber`,
  `python-pptx` et leurs propres sous-dépendances) — les builders Launchpad n'ont
  **pas d'accès réseau**, contrairement à l'AUR (`makepkg`) : impossible de faire
  un `pip install` réseau au moment du build.

## Pourquoi un venv privé plutôt que des paquets `python3-*` ?

Contrairement à l'AUR (où `python-pdf2docx`/`python-pdfplumber`/`python-pptx`
existent comme paquets AUR tiers), Ubuntu/Debian n'ont pas d'équivalent — il aurait
fallu les empaqueter séparément, avec leurs propres sous-dépendances (`opencv-python-headless`,
`pypdfium2`, `python-docx`, `fonttools`, `lxml`, `numpy`…), certaines elles-mêmes
absentes des dépôts. Plus simple et robuste : un venv privé sous
`/usr/lib/pdf-equilibrist/venv`, créé avec `--system-site-packages` pour voir
`python3-pyqt6` (paquet système, jamais vendorisé — évite d'embarquer Qt en double),
et peuplé hors-ligne depuis le wheelhouse pour tout le reste.

**Piège rencontré** : avec `--system-site-packages`, `pip install <pkg>` (sans
`--no-deps` explicite sur chaque wheel) considère une dépendance transitive
"déjà satisfaite" si la machine de *build* a le paquet système équivalent (ex.
`numpy`) — et ne l'installe alors nulle part dans le venv. Sur la machine
*cible*, sans ce paquet système, l'app crashe au démarrage
(`ModuleNotFoundError`). D'où `debian/rules` qui installe **chaque wheel du
wheelhouse explicitement avec `--no-deps`**, sans laisser pip décider quoi
sauter.

**Autre piège** : `resource_path()` (`src/pdf_equilibrist/utils.py`) résout les
assets sous `{sys.prefix}/share/pdf-equilibrist/assets/` — dans le venv privé,
`sys.prefix` vaut `/usr/lib/pdf-equilibrist/venv`, **pas** `/usr` (contrairement
au paquet AUR qui installe directement en site-packages système). Les assets
sont donc copiés dans le venv lui-même (`debian/rules`), pas sous `usr/share/`
du paquet.

## Régénérer le wheelhouse

Nécessite un environnement Linux + Python 3.12 + réseau (WSL Ubuntu convient) :

```bash
python3 -m venv /tmp/wheelhouse-venv
/tmp/wheelhouse-venv/bin/pip install --upgrade pip
/tmp/wheelhouse-venv/bin/pip download --dest packaging/ppa/vendor/wheelhouse \
    PyMuPDF pdf2docx pdfplumber openpyxl python-pptx Pillow pyparsing
```

Ne pas inclure `PyQt6` (fourni par `python3-pyqt6`, jamais vendorisé) ni `bandit`
(dev/scan uniquement, absent des dépôts Ubuntu — dégradation gracieuse déjà en
place, voir `cve_checker.py`).

## Build local de test

Nécessite `debhelper devscripts dpkg-dev python3-pyqt6 python3-pyqt6.qtsvg` :

```bash
mkdir -p /tmp/ppa-build/pdf-equilibrist-<version>
cp -r . /tmp/ppa-build/pdf-equilibrist-<version>/
rm -rf /tmp/ppa-build/pdf-equilibrist-<version>/.git
cp -r packaging/ppa/debian /tmp/ppa-build/pdf-equilibrist-<version>/debian
cd /tmp/ppa-build/pdf-equilibrist-<version>
dpkg-buildpackage -us -uc -b
```

## Publication (source-only, revue automatique du build farm — pas de comité humain)

Launchpad exige un upload **source seulement** (pas de binaire pré-construit) :

```bash
debuild -S -sa
dput ppa:paulwoisard/pdf-equilibrist ../pdf-equilibrist_<version>-1_source.changes
```

Nécessite une clé GPG uploadée sur le compte Launchpad (voir
[aur.archlinux.org/account](https://launchpad.net/~/+editpgpkeys) — format du
fingerprint : `<taille><type>/<fingerprint complet 40 caractères>`, ex.
`4096R/1FCB47E680BB2BFAB15BF4666FEB8D3A40A17D3E`).

## Mise à jour à chaque nouvelle release

1. Régénérer le wheelhouse si les dépendances ont changé.
2. Bump `pkgver`/ajouter une entrée dans `debian/changelog` (`dch -v <version>-1`).
3. Rebuild + retest localement.
4. `debuild -S -sa` + `dput` comme ci-dessus.
