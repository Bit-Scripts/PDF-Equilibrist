# AppImage — PDF-Equilibrist (PROTOTYPE)

Canal « autres distributions » (Debian, openSUSE, Mint…) : **un seul fichier à télécharger**, sans
dépôt à configurer. **Prototype** : rien n'est publié (pas de déclenchement sur tag, rien n'est joint à
la release). Le résultat est un artefact de run GitHub Actions, à tester à la main.

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
- **Mises à jour** : l'AppImage ne passe par aucun gestionnaire de paquets ; l'application ne sait pas encore
  la détecter (`update.py` ne connaît que `.exe` et les gestionnaires de paquets). À faire avant publication :
  détecter `APPIMAGE`, pointer vers la page de release, éventuellement zsync.
- **Version** : le prototype n'injecte pas la version du tag (`__version__`), comme le fait `release.yml`.
- **Sécurité** : les bibliothèques embarquées ne sont corrigées que par une nouvelle release.
