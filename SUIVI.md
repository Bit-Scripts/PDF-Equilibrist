# Suivi — OCR embarqué, CI bloquante, documentation source unique

Branche locale : `chore/docs-ci-ocr` (rien n'est poussé sans accord explicite).
Environnement de test : `C:\Users\paulw\envs\eq312\python.exe` (conda, Python 3.12, hors dépôt).
Toujours `git add` des chemins explicites (des `.pyc` sont suivis par git et polluent `git status`).

## Décisions validées
1. OCR : embarquer tous les modèles (aucun téléchargement), tester hors-ligne, mettre à jour PRIVACY/SÉCURITÉ.
2. CI : ajouter Bandit, flake8 bloquant (corriger le lint d'abord), aucun build/release si contrôle KO.
3. Docs : source unique sur `main` (FR+EN), sync auto vers `gh-pages` sans écraser le reste du site,
   page fonctionnalités avec `<details>` grand public/dev, tests de cohérence documentaire.

## État
### Étape 0 — environnement
- [x] Env conda 3.12 + flake8/pytest/bandit/autopep8 installés
- [x] Constat : CI = `flake8 || true` ; aucun bandit ; pytest ramasse `forensic/` (gitignoré) en local

### Étape 1 — OCR embarqué (RapidOCR/ONNX, choix utilisateur) — FAIT localement
- Constat initial : `paddleocr`/`paddlepaddle` n'étaient déclarés NULLE PART (requirements, pyproject,
  release.yml, wheelhouse ; Flatpak les excluait) → l'exe publié n'avait sans doute pas d'OCR.
- [x] `ocr.py` réécrit sur RapidOCR 3.10 (PP-OCRv6 small det/rec + cls, ~30 Mo, livrés dans la wheel,
      deps `opencv-python-headless` déjà présent) ; garde `OcrModelsMissingError` (jamais de téléchargement)
- [x] Dépendances déclarées : requirements.txt, pyproject.toml, environment.yml (`rapidocr`, `onnxruntime`)
- [x] `PDF-Equilibrist.spec` : `collect_data_files("rapidocr")` (modèles inclus), plus de paddle
- [x] `tests/test_operations/test_ocr.py` (6 tests : modèles livrés, pas de download, accents FR, hors-ligne
      via socket interdit, markdown, page texte ignorée) — 32 tests verts au total
- [x] Test « machine vierge » : mini-exe PyInstaller (mêmes options) lancé depuis un dossier vierge, profil
      utilisateur vide, PATH minimal, proxy mort, socket interdit → OCR OK (accents corrects), aucun fichier
      créé dans le profil. L'exe complet de l'app n'a pas été rebuildé (CI release le fera).
- [x] PRIVACY.md (EN+FR) et docs/6.SECURITE.md (FR) : plus de `bj.bcebos.com`, OCR sans connexion
- [ ] À FAIRE ensuite : 6.SECURITE EN (après rapatriement, étape 3)
- [ ] À FAIRE à la prochaine release Linux : ajouter rapidocr + deps (onnxruntime, shapely, pyclipper,
      omegaconf, colorlog, PyYAML, requests, tqdm, six, flatbuffers, protobuf…) au wheelhouse PPA/COPR
      (`packaging/ppa/README.md` § Régénérer le wheelhouse + liste explicite dans `debian/rules`) et au
      PKGBUILD AUR ; NON testable depuis Windows. Flatpak : OCR toujours exclu (modifier si souhaité).
- Remarque qualité : € reconnu comme « · » (modèle small) ; accents OK.

### Étape 2 — CI bloquante — FAIT localement (non exécutable en vrai sans push)
- [x] Lint : `.flake8` (max 120 ; ignore volontaire E221/E222/E272/E701/E702/E127/E128/E251 = alignements
      de style du projet), autopep8 sur E225/E231/E261/E302/E303/E305/E401, 5 corrections manuelles
      (E402 main_window, E731 print_dialog, E741 win32 `noqa`, E501 tab_modifier) → `flake8 src tests` = 0
- [x] Bandit : `bandit -r src` = 0 finding (tous niveaux) avec la version locale
- [x] `pytest` : `testpaths = ["tests"]` (forensic/ n'est plus ramassé) — 32 verts
- [x] Nouveau workflow réutilisable `.github/workflows/checks.yml` (flake8 → bandit → pytest, bloquants)
- [x] `ci.yml` : job `test` = appel de checks.yml, `build` en dépend (workflow conservé)
- [x] Portes sur les workflows de publication : `release`, `linux-aur-publish`, `linux-copr-publish`,
      `linux-ppa-publish`, `update-site-version` ont un job `checks` et `needs: checks`
      (`linux-aur.yml` = build de test du PKGBUILD, `stats.yml` = compteurs : laissés tels quels)
- Limites : YAML validé par parsing (pas d'actionlint) ; le premier vrai run GitHub reste à observer.
  Le job s'appelle maintenant « test / Contrôles… » côté GitHub (si une règle de protection de branche
  exige l'ancien nom « Test and lint », la mettre à jour). Une version future de bandit peut ajouter des findings.

### Étape 3 — Documentation — FAIT localement
- [x] `docs/en/` rapatrié depuis gh-pages dans main, remis à niveau (sélection multiple, extract_pages, OCR)
- [x] Corrigés : CONTRIBUTING (plus « Windows-only »), OPERATIONS + ARCHITECTURE (impression 2 backends),
      BUILD (lien cassé `CONTRIBUTING.md` → `3.CONTRIBUTING.md`, FR+EN), 6.SECURITE (OCR)
- [x] `docs/0.FONCTIONNALITES.md` (FR) et `docs/en/0.FONCTIONNALITES.md` : 13 blocs `<details>`
      « 🛠 Pour les développeurs » ; INDEX FR/EN mis à jour
- [x] `tests/test_docs.py` (56 tests) : parité FR/EN (fichiers, hiérarchie des titres, nb de `<details>`),
      fichiers `.py` et fonctions citées existent, hôtes réseau cités ⊂ `network.py` + liste doc, `PRIVACY.md`
      liste les hôtes de l'app, plus de trace de l'ancien OCR, liens internes, plus de « Windows-only »
- [x] `tools/sync_docs_to_pages.py` + `tests/test_docs_sync.py` (4 tests : ne touche que les `.md` de docs/ et
      docs/en/, préserve index.html/style.css/stats.json/pages générées, idempotent, dry-run)
- [x] Workflow `docs-sync.yml` (push main sur docs/** → checks → copie vers gh-pages → commit/push si diff)
- [x] Site (worktree `I:\PDF-Equilibrist-site`, branche gh-pages, commit LOCAL `cc45c44`) : entrée « 0 » dans
      le viewer (template + l18n FR/EN), CSS `<details>`, pages régénérées par `build_i18n.py`, docs synchronisées.
      Rendu vérifié dans le navigateur (FR et EN : 13 panneaux repliés, dépliables, nav 0→6).
- [x] CLAUDE.md : OCR, backends d'impression, section Documentation et CI
- [x] Fichiers parasites : `crash.log` + `debug_text.py` (logs/script de débogage de juillet, suivis par git, non
      référencés, sans donnée sensible) retirés via `git rm` (récupérables dans l'historique) ; fichier
      `D:DeveloppementPDF-Equilibristenvironment.yml` (export conda cassé, 193 octets, non suivi) supprimé.
      `forensic/` (57 Mo, preuves d'antériorité, ignoré par git, politique de sauvegarde cloud) : **conservé**.

## Vérifications finales (locales)
- `flake8 src tests` : 0 · `bandit -r src` : exit 0 · `pytest` : 92 passés

## Reste à faire / à décider
- [ ] PUSH (attendre l'accord) : branche `chore/docs-ci-ocr` → main ; puis gh-pages (commit local `cc45c44`) — ou laisser
      `docs-sync.yml` le faire (mais le template/CSS/l18n du viewer ne passent QUE par un push gh-pages direct)
- [ ] Linux : wheelhouse PPA/COPR + PKGBUILD AUR à régénérer avec rapidocr (voir étape 1)
- [ ] Premier vrai run GitHub des workflows à surveiller (checks.yml, docs-sync.yml, build PyInstaller complet avec rapidocr)
- [ ] Hors périmètre : `.pyc` et `*.egg-info` suivis par git ; `.gitignore` et `.claude/settings.local.json` modifiés avant ma session (non touchés)

---

# Phase 2 — décisions utilisateur du 2026-10-11 (push, Linux, actionlint)

Décisions : push direct gh-pages OK ; nom des contrôles OK ; actionlint ajouté ; OCR Linux (PPA/COPR/AUR) à
intégrer et valider avant la prochaine release ; **Flatpak suspendu** (documenté, fichiers conservés) ;
nettoyage `.pyc`/`egg-info` dans un commit séparé ; pas de release de production sans validation.

- [x] Protection de branche : aucune (ni `main`, ni `gh-pages`, aucun ruleset) → rien ne référence « Test and lint »
- [x] actionlint 1.7.12 (pip `actionlint-py`) : 0 erreur sur tous les workflows ; ajouté à `checks.yml`
- [x] `--ocr-selftest` (main.py + `ocr.selftest()`) ; vérifié sur l'exe PyInstaller COMPLET local (417 Mo, dossier vierge,
      profil vide) ; étape ajoutée à `ci.yml` et `release.yml` après le build PyInstaller
- [x] AUR : PKGBUILD (wheel rapidocr en source + deps officielles), `.SRCINFO` régénéré ; build makepkg + selftest OK sous WSL Arch
- [x] COPR : spec (wheels rapidocr+omegaconf, Requires/BuildRequires, `%check`) ; rpmbuild + install + selftest OK sous WSL Fedora 43
- [x] PPA : `fetch_wheelhouse.sh` (source unique), `debian/rules` (liste + selftest) ; dpkg-buildpackage + install + selftest OK
      sous WSL Ubuntu 24.04 (noble, cp312) ET 26.04 (resolute, cp314)
- [x] `linux-packages-check.yml` (nouveau, réutilisable) ; `linux-ppa-publish` / `linux-copr-publish` en dépendent
- [x] Flatpak : bannière « suspendu » (packaging/flatpak/README.md, docs/5.BUILD FR+EN, PRIVACY), fichiers conservés
- [x] Nettoyage : 34 `.pyc` + `egg-info` + `.claude/settings.local.json` retirés de l'index (commit 2bc79b7) ; `.gitignore` local
      (`forensic/`) NON commité, préservé ; settings.local.json contenait un mot de passe de compte de test WSL (voir bilan)
- [x] gh-pages poussé (0c6932f) : entrée « 0 », CSS `<details>`, docs FR/EN ; stats.json/index.html intacts (rebase sur origin)
- [ ] Push branche `chore/docs-ci-ocr` + PR → surveiller CI, corriger, merger
- [ ] Vérifier le site public FR/EN + liens internes
- [ ] Surveiller `docs-sync.yml`, `linux-packages-check.yml` (Fedora 44, Ubuntu 26.04 en conteneur : tags d'images à confirmer)

---

# Phase 3 — corrections après relecture externe (2026-10-11), branche `fix/ocr-word-cancel-docs`

Constats vérifiés dans le code puis corrigés, dans l'ordre demandé :
- [x] **OCR → Word** (vrai bug) : `to_word()` rouvrait le PDF d'origine → couche OCR perdue ; de plus pdf2docx ignore le
      texte invisible. Corrigé : copie temporaire du doc EN MÉMOIRE + texte OCR rendu visible / image du scan retirée sur la
      copie jetable. Tests : scan→docx, ajout non enregistré, PDF mixte. Au passage `to_excel` : repli par position du texte
      OCR pour un tableau scanné (avant : classeur vide) — testé.
- [x] **Annulation** (vrai) : 2 × `QThread.terminate()` (tab_modifier, tab_convertir) remplacés par une annulation
      coopérative et ATOMIQUE (`cancel_cb`, `OcrCancelled`, `ui/ocr_job.py`) : le texte n'est inséré qu'après l'OCR de toutes
      les pages → document intact si annulé. Dialogue maintenu jusqu'à l'arrêt réel du thread. Tests unitaires + Qt.
      Piège évité : `tools/compile_translations.py` (générateur Python de secours) produit un .qm à 47/368 messages valides
      → .qm régénéré avec pyside6-lrelease (368/368).
- [x] **Docs** : 6.SECURITE FR/EN (« desktop Windows », « téléchargement initial », tableau Réseau, version/date),
      2.ARCHITECTURE FR/EN (onefile→onedir), PDF de doc régénérés ; `test_docs.py` : phrases périmées interdites, .spec onedir,
      version FR=EN, date. Vérifié : ces tests échouent sur les anciennes docs.
- [x] **Version RapidOCR** : `==3.10.0` partout (requirements, environment, PPA, COPR, AUR, workflows), `>=3.10,<3.11` dans
      pyproject ; `tests/test_packaging_consistency.py` garde l'alignement.
- [ ] Reste (checklist de RELEASE, pas des bugs) : entrées `debian/changelog` noble + resolute de la nouvelle version AVANT le tag ;
      `copr/*.spec` Version + `%changelog` ; vérifier AUR complet (dépendances AUR) ; essais sur vrais documents scannés ;
      test manuel de l'installeur Windows et d'un paquet Linux. Le tag `v*` déclenche release Windows PUBLIQUE + AUR/PPA/COPR.
