# Packaging COPR (Fedora) — PDF-Equilibrist

Ce dossier contient le `.spec` pour publier PDF-Equilibrist sur un dépôt
COPR (Fedora/dérivées), équivalent Fedora d'un PPA Launchpad ou de l'AUR.

## Fichiers

- `pdf-equilibrist.spec` — recette RPM.
- `pdf-equilibrist.sh` / `.desktop` / `-128.png` / `-256.png` — mêmes
  assets embarqués que pour l'AUR et la PPA (copies locales, pas de
  dépendance au contenu figé du tag Git).
- `vendor/wheelhouse/` — **non commité** (voir `.gitignore`), wheels
  vendorisées pour les dépendances non empaquetées sur Fedora.

## Pourquoi un venv privé, et pourquoi si peu de wheels vendorisées ?

Contrairement à Ubuntu/Debian (PPA), les dépôts Fedora empaquettent déjà
la quasi-totalité des dépendances Python du projet : `python3-pyqt6`,
`python3-PyMuPDF`, `python3-openpyxl`, `python3-pyparsing`,
`python3-pillow`, `python3-opencv`, `python3-xlsxwriter`, `python3-lxml`,
`python3-numpy`, `python3-typing-extensions`, `python3-fire`,
`python3-pdfminer`. Seuls **5 paquets** manquent, vérifié par test réel
(`dnf install` + `import`, pas seulement la recherche web sur
packages.fedoraproject.org qui indiquait à tort `python3-docx` comme
disponible) :

- `pdf2docx`, `pdfplumber`, `python-docx`, `python-pptx` — purs Python
  (wheel `py3-none-any`), aucun souci de compatibilité binaire.
- `pypdfium2` — le seul avec une lib compilée (`libpdfium`), mais son
  wheel est tagué `py3-none-manylinux_*` (pas `cp3XX`) : indépendant de
  la version de CPython installée, juste de l'architecture (x86_64).

D'où un venv privé sous `/usr/lib64/pdf-equilibrist/venv` (note :
`/usr/lib64` sur Fedora x86_64, pas `/usr/lib` comme sur Debian/Ubuntu —
convention FHS de Fedora pour le contenu dépendant de l'architecture),
créé avec `--system-site-packages` pour voir tous les paquets système
ci-dessus, et peuplé hors-ligne avec seulement ces 5 wheels.

## Régénérer le wheelhouse

Nécessite un environnement Fedora + réseau (le WSL `FedoraLinux-44`
convient) :

```bash
python3 -m venv /tmp/wh-venv
/tmp/wh-venv/bin/pip install --upgrade pip
/tmp/wh-venv/bin/pip download --no-deps --dest packaging/copr/vendor/wheelhouse \
    pdf2docx pdfplumber python-pptx python-docx pypdfium2
```

`--no-deps` est important : sans lui, `pip download` embarque aussi les
sous-dépendances déjà fournies par les paquets système Fedora
(`numpy`, `opencv-python-headless`, `lxml`, `fonttools`,
`typing-extensions`...), ce qui gonfle le wheelhouse inutilement et,
pire, pourrait masquer une vraie dépendance manquante.

Ne pas inclure `PyQt6`/`PyMuPDF`/etc. (fournis par les paquets système,
jamais vendorisés) ni `bandit` (absent des dépôts Fedora comme d'Arch et
Ubuntu — dégradation gracieuse déjà en place, voir `cve_checker.py`).

## Build local de test

Nécessite `rpm-build rpmdevtools python3-devel python3-pyqt6` (+ tous
les `Requires` système du `.spec`) :

```bash
rpmdev-setuptree
cp packaging/copr/vendor/wheelhouse/*.whl ~/rpmbuild/SOURCES/
cp packaging/copr/pdf-equilibrist.sh packaging/copr/pdf-equilibrist.desktop \
   packaging/copr/pdf-equilibrist-128.png packaging/copr/pdf-equilibrist-256.png \
   ~/rpmbuild/SOURCES/
curl -L -o ~/rpmbuild/SOURCES/pdf-equilibrist-<version>.tar.gz \
   https://github.com/Bit-Scripts/PDF-Equilibrist/archive/refs/tags/v<version>.tar.gz
cp packaging/copr/pdf-equilibrist.spec ~/rpmbuild/SPECS/
rpmbuild -ba ~/rpmbuild/SPECS/pdf-equilibrist.spec
```

## Publication sur COPR (pas de comité humain, self-service)

Construire le SRPM localement (auto-suffisant, tous les Sources déjà
embarqués) plutôt que de dépendre de l'accès réseau du build COPR :

```bash
rpmbuild -bs ~/rpmbuild/SPECS/pdf-equilibrist.spec
```

Puis uploader le `.src.rpm` résultant sur `copr.fedorainfracloud.org`
(projet perso, méthode de build "Upload") — nécessite un compte Fedora
(FAS).

## Mise à jour à chaque nouvelle release

1. Régénérer le wheelhouse si les 5 dépendances vendorisées ont changé.
2. Bump `Version`/ajouter une entrée `%changelog` dans le `.spec`.
3. Rebuild + retest localement.
4. `rpmbuild -bs` + upload comme ci-dessus.
