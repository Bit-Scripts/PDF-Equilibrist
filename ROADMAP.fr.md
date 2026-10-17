# Feuille de route

[English version](ROADMAP.md)

Liste simple de ce qui est prévu ou envisagé. Ce n'est pas un calendrier : les points avancent selon le temps
disponible et les retours. Les suggestions sont les bienvenues sous forme d'[issues](https://github.com/Bit-Scripts/PDF-Equilibrist/issues).

## Prévu

- **Suivre le réglage clair/sombre du système.** L'interface est uniquement sombre aujourd'hui. Elle doit utiliser
  un thème clair par défaut quand le système n'est pas en mode sombre, et rester sombre quand le système (ou
  l'utilisateur, dans les réglages) le demande. Demandé lors de la revue du catalogue AppImageHub, engagement pris
  publiquement dans [AppImage/appimage.github.io#10396](https://github.com/AppImage/appimage.github.io/pull/10396).
- **Outils interactifs pas encore câblés** (ils demandent un canevas interactif) : crayon libre, zones de lien,
  signature dessinée à la main, rognage de page. Certains sont déjà visibles dans le ruban mais ne font rien pour l'instant.

## Envisagé

- **Informations de mise à jour de l'AppImage** (`appimagetool -u` et un fichier `.zsync` publié), pour que
  AppImageUpdate et les outils similaires puissent la mettre à jour. L'AppImage a déjà sa mise à jour intégrée
  (Aide › À propos).
- **Capture de l'outil de sécurité en anglais** pour `README.md` (la boîte du contrôle CVE ; elle demande un vrai
  contrôle réseau).
- **macOS** : seulement si le projet gagne assez en traction ; une formule Homebrew plutôt qu'une application
  signée, pour éviter le coût d'un certificat développeur Apple.

## Maintenance

- Remplacer `license = {text = ...}` dans `pyproject.toml` par la forme SPDX avant la date d'abandon de setuptools
  (février 2027).
- Publication PPA Linux : envoyer l'archive source une seule fois puis la seconde série sans elle, en interrogeant
  Launchpad entre les deux, au lieu de relancer à la main une seule série quand un envoi expire.
- COPR Fedora : décider de garder ou non le chroot `rawhide`, qui échoue indépendamment du code.
