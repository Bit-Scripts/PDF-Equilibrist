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

### Étape 3 — Documentation
- [ ] Rapatrier docs/en/ depuis gh-pages
- [ ] Corriger CONTRIBUTING (Windows-only), OPERATIONS (impression 2 backends), ARCHITECTURE (parité gh-pages)
- [ ] Page FONCTIONNALITES (FR/EN) avec `<details>`
- [ ] Workflow de sync main → gh-pages (docs/ uniquement)
- [ ] tests/test_docs.py (parité FR/EN, modules cités existants, hôtes réseau cités)
- [ ] Fichiers parasites : `crash.log`, `debug_text.py`, `D:DeveloppementPDF-Equilibristenvironment.yml`, `forensic/` — inspecter contenu avant toute suppression

## Problèmes / remarques
- Le dépôt suit des `.pyc` et `*.egg-info` (devrait être ignoré) — hors périmètre, à traiter à part.
- `D:\Developpement\CONDA\envs\Equilibrist` absent de cette machine (d'où l'env conda local).
