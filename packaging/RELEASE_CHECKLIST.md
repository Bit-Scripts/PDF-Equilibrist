# Checklist de release — PDF-Equilibrist

> Un tag `v*` déclenche **automatiquement et publiquement** : la release GitHub Windows (`release.yml`,
> `draft: false`), la mise à jour de l'AUR, l'envoi PPA (Launchpad, noble + resolute), la soumission COPR
> et la mise à jour du site (`update-site-version.yml`). Un tag ne se « retire » pas proprement :
> **ne le créer qu'une fois toute la checklist cochée.**

## 1. Préparation (avant le tag) — fait pour 0.1.26

- [x] `packaging/ppa/debian/changelog` : entrées `X.Y.Z-1~noble1` **et** `X.Y.Z-1~resolute1` en tête
      (le workflow PPA échoue explicitement si la version ne correspond pas au tag)
- [x] `packaging/copr/pdf-equilibrist.spec` : `Version:` et entrée `%changelog`
- [ ] `PKGBUILD` / `.SRCINFO` : **ne pas toucher**, `linux-aur-publish.yml` les met à jour après le tag
- [ ] `__version__` et `pyproject.toml` : injectés par les workflows à partir du tag, ne pas éditer
- [ ] Pas de PR ouverte avec une CI rouge ; `main` vert (CI, Linux packages check, Linux AUR, docs-sync)

## 2. Vérifications automatiques déjà couvertes par la CI

flake8, Bandit, pytest, actionlint · build PyInstaller Windows puis `PDF-Equilibrist.exe --ocr-selftest` sur l'exe figé ·
`.deb` noble et resolute, `.rpm` Fedora 44, paquet Arch : construits, installés, auto-test OCR réseau interdit.

## 3. Essais manuels recommandés avant le tag

### Windows (installeur)
Télécharger l'artefact `pdf-equilibrist-installer` du dernier run **CI** sur `main` (Actions › CI › Artifacts),
sur une machine ou une VM **sans** Python ni environnement de dev :
1. Installer, lancer. Vérifier : démarrage sans erreur, langue FR/EN, ouverture d'un PDF.
2. **Coupez Internet** (mode avion) puis : *Modifier › Rendre cherchable* sur un vrai scan → le texte devient
   sélectionnable/cherchable. Aucune demande de connexion, aucun dossier `.paddlex` créé.
3. *Convertir › OCR → Word* et *OCR → Excel* sur un scan (le Word doit contenir du **texte éditable**).
4. Lancer un OCR sur un document de plusieurs pages et cliquer **Annuler** : le dialogue passe à « Annulation en
   cours… », puis se ferme ; le document est inchangé ; un nouvel OCR peut être relancé.
5. *Aide › Connexions Internet › Bloquer* : vérifier que la vérification CVE refuse de partir.
6. Désinstaller proprement.

### Linux (au moins un canal, idéalement les trois)
- **Ubuntu** : `sudo apt install ./pdf-equilibrist_*.deb` (artefact du job *PPA* de *Linux packages check*) ou depuis le PPA.
- **Fedora** : `sudo dnf install ./pdf-equilibrist-*.rpm` (artefact du job *COPR*) ou depuis COPR.
- **Arch** : `yay -S pdf-equilibrist` après publication, ou `makepkg -si` dans `packaging/aur/` (dépendances AUR :
  `python-pdf2docx`, `python-pdfplumber`, `python-pptx`).
Puis les points 2 à 5 ci-dessus, hors ligne.

### Documents réels
Sur **vos** scans (contrat, facture, scan tabulaire, PDF mêlant pages numériques et scannées, photo de page) :
OCR → PDF cherchable, OCR → Word, OCR → Excel. Mesure synthétique de référence (`scan_stress`, scans simulés) :
~100 % des mots à ≥ 200 dpi bien droit ; 79 % à 150 dpi incliné 1,5° ; 65 % incliné 3°. L'inclinaison est le point faible.

## 4. Création du tag

```bash
git switch main && git pull
git tag -a v0.1.26 -m "PDF-Equilibrist 0.1.26"
git push origin v0.1.26      # ← déclenche TOUT : release publique + AUR + PPA + COPR + site
```

## 5. Après le tag — à surveiller

- [ ] `Release` : installeur publié et téléchargeable ; vérifier le contenu de la release GitHub
- [ ] `Linux AUR publish` : push AUR réussi, `.SRCINFO` à jour
- [ ] `Linux PPA publish` : upload accepté **et build Launchpad réussi** (peut échouer des heures plus tard,
      sans réseau côté builder : vérifier launchpad.net/~paulwoisard/+archive/ubuntu/pdf-equilibrist). Surveiller le
      quota du PPA (wheelhouse ≈ 250 Mo par version).
- [ ] `Linux COPR publish` : build COPR réussi pour les chroots Fedora
- [ ] `Linux AppImage` : build + 5 distributions vertes, puis la release contient `PDF-Equilibrist-x86_64.AppImage`,
      son `.sha256` et `install.sh` (le job `publish` attend la release Windows, jusqu'à 60 min). Rattrapage :
      Run workflow avec `tag` = `vX.Y.Z`.
- [ ] Site : `softwareVersion` mis à jour, liens de téléchargement valides
- [ ] Si un canal échoue : corriger puis bump du dernier chiffre (le PPA refuse de réutiliser une version avec un contenu différent)
