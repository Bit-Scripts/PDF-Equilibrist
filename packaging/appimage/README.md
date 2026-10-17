# AppImage — PDF-Equilibrist

Canal « autres distributions » (Debian, openSUSE, Mint…) : **un seul fichier à télécharger**, sans
dépôt à configurer. Publié sur chaque tag `v*` : l'AppImage est jointe à la release GitHub.

## Fichiers

| Fichier | Rôle |
|---|---|
| `PDF-Equilibrist-linux.spec` | Variante Linux du `.spec` PyInstaller Windows : onedir, sans Splash/icône/winreg/UPX |
| `build_appimage.sh` | **Source unique** (CI et essais locaux) : PyInstaller → AppDir → libxcb-cursor → AppImage |
| `AppRun`, `pdf-equilibrist.desktop` | Point d'entrée et lanceur de l'AppDir |
| `../../.github/workflows/linux-appimage.yml` | Build sur Ubuntu 22.04, auto-test OCR, démarrage offscreen, puis lancement dans Debian 12, Ubuntu 24.04, Fedora 44, Arch et openSUSE Tumbleweed |

## Essai local (sans appimagetool)

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt pyinstaller
sudo apt install libxcb-cursor0          # ou l'équivalent de la distribution
PYTHON=venv/bin/python packaging/appimage/build_appimage.sh
build/appimage/AppDir/AppRun --ocr-selftest /tmp/r.txt && cat /tmp/r.txt
```

Avec `APPIMAGETOOL=/chemin/appimagetool`, le script produit aussi
`build/appimage/PDF-Equilibrist-x86_64.AppImage` (la CI épingle appimagetool 1.9.1 par SHA-256).

## Mesuré (Ubuntu 24.04, WSL)

- AppDir : environ 570 Mo décompressé (PyQt6 104, OpenCV 150, PyMuPDF 55, OCR 59) ; l'AppImage, compressée
  en squashfs, sera nettement plus petite (mesure donnée par la CI).
- `AppRun --ocr-selftest` : OK, avec un environnement minimal (`env -i`) et un HOME vide.
- Démarrage de l'interface en `QT_QPA_PLATFORM=offscreen` : tient 12 s.
- Aucune bibliothèque système manquante ; les `libxcb-*` nécessaires à Qt6 (dont `libxcb-cursor`) sont embarquées.
- Un dossier `~/.cache` est créé pendant l'auto-test (origine à identifier ; la CI le liste).

## À décider / limites connues

- **FUSE** : sans `libfuse2`, lancer avec `--appimage-extract-and-run` ou extraire l'image.
- **glibc** : construire sur le système le plus ancien à couvrir (CI : Ubuntu 22.04 = glibc 2.35).
- **Impression (CUPS), polices d'emoji, Wayland** : dépendent du système hôte, non testés en vrai.
- **Mises à jour** : `update.py` détecte l'AppImage via `APPIMAGE`, cherche l'asset `*x86_64.AppImage` de la
  dernière release et la télécharge (SHA-256 vérifié si GitHub le fournit), puis propose de l'installer avec le
  `install.sh` embarqué (`usr/share/pdf-equilibrist/install.sh`) : pour l'utilisateur seul, ou pour tous via
  `pkexec` (script passé en texte, somme revérifiée en root sur une copie, icône existante conservée), puis de
  relancer. Sans `pkexec`, repli sur `sudo -S` avec une demande de mot de passe dans l'application (mot de passe
  sur l'entrée de sudo, jamais en argument). Pas de zsync (delta) pour l'instant.
- **Version** : le workflow injecte la version du tag dans `__version__`, comme `release.yml`.
- **Publication** : un tag `v*` construit l'AppImage puis la joint à la release (`gh release upload`, après avoir
  attendu que `release.yml` l'ait créée). Rattrapage d'une release existante : Actions › « Linux AppImage » ›
  Run workflow, champ `tag` = `v0.1.25` (le code construit est celui de la branche choisie).
- **Sécurité** : les bibliothèques embarquées ne sont corrigées que par une nouvelle release.

## Installation (script `install.sh`)

Joint à chaque release avec l'AppImage. Il crée le lanceur de menu, l'icône, la commande
`pdf-equilibrist` et l'association aux PDF.

```bash
bash install.sh                  # sans root → ~/.local
sudo bash install.sh --system    # tous les utilisateurs → /usr/local
bash install.sh --uninstall      # (ajouter --system si installé avec sudo)
bash install.sh --file ./PDF-Equilibrist-x86_64.AppImage   # AppImage déjà téléchargée
```

Sans `--file`, il utilise l'AppImage posée à côté de lui, sinon télécharge la dernière release et vérifie
son SHA-256. Pour mettre à jour : le relancer.
