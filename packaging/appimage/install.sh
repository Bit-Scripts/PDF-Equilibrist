#!/usr/bin/env bash
# Installe (ou désinstalle) l'AppImage de PDF-Equilibrist : lanceur dans le menu, icône, commande
# `pdf-equilibrist`, association aux fichiers PDF.
#
#   install.sh                  utilisateur courant, sans root  → ~/.local
#   sudo install.sh --system    pour tous les utilisateurs      → /usr/local
#   install.sh --uninstall      retire l'installation (ajouter --system si faite avec sudo)
#   install.sh --file CHEMIN    utilise cette AppImage au lieu de la télécharger
#
# Sans --file : prend l'AppImage posée à côté du script, sinon télécharge la dernière release GitHub
# (api.github.com / github.com uniquement) et vérifie sa somme SHA-256 avant d'installer.
set -euo pipefail

REPO="Bit-Scripts/PDF-Equilibrist"
ASSET="PDF-Equilibrist-x86_64.AppImage"
MODE=user ; ACTION=install ; FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --system) MODE=system ;;
    --user) MODE=user ;;
    --uninstall) ACTION=uninstall ;;
    --file) FILE="${2:?--file demande un chemin}" ; shift ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' ; exit 0 ;;
    *) echo "Option inconnue : $1 (voir --help)" >&2 ; exit 2 ;;
  esac
  shift
done

if [ "$MODE" = system ]; then
  PREFIX=/usr/local
  [ "$(id -u)" -eq 0 ] || { echo "--system demande les droits root : sudo $0 --system" >&2 ; exit 1; }
else
  PREFIX="${HOME}/.local"
  [ "$(id -u)" -ne 0 ] || { echo "Ne lancez pas le mode utilisateur en root (utilisez --system)." >&2 ; exit 1; }
fi

APPDIR="$PREFIX/share/pdf-equilibrist"
TARGET="$APPDIR/PDF-Equilibrist.AppImage"
BIN="$PREFIX/bin/pdf-equilibrist"
DESKTOP="$PREFIX/share/applications/pdf-equilibrist.desktop"
ICON="$PREFIX/share/icons/hicolor/256x256/apps/pdf-equilibrist.png"

refresh_caches() {
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
}

if [ "$ACTION" = uninstall ]; then
  rm -f "$BIN" "$DESKTOP" "$ICON"
  rm -rf "$APPDIR"
  refresh_caches
  echo "PDF-Equilibrist désinstallé de $PREFIX (vos réglages dans ~/.config ne sont pas touchés)."
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ -z "$FILE" ]; then
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # AppImage posée à côté (nom de la release ou nom versionné de la mise à jour intégrée) : la plus récente
  LOCAL="$(ls -t "$HERE"/PDF-Equilibrist*x86_64.AppImage 2>/dev/null | head -n1 || true)"
  if [ -n "$LOCAL" ]; then
    FILE="$LOCAL"
    echo "AppImage trouvée à côté du script : $FILE"
  else
    command -v curl >/dev/null 2>&1 || { echo "curl est requis pour télécharger (ou utilisez --file)." >&2 ; exit 1; }
    BASE="https://github.com/$REPO/releases/latest/download"
    echo "Téléchargement de la dernière version depuis GitHub…"
    curl -fL --proto '=https' --tlsv1.2 -o "$WORK/$ASSET" "$BASE/$ASSET"
    curl -fsSL --proto '=https' --tlsv1.2 -o "$WORK/$ASSET.sha256" "$BASE/$ASSET.sha256" || true
    if [ -s "$WORK/$ASSET.sha256" ]; then
      expected="$(cut -d' ' -f1 "$WORK/$ASSET.sha256")"
      actual="$(sha256sum "$WORK/$ASSET" | cut -d' ' -f1)"
      [ "$expected" = "$actual" ] || { echo "Somme SHA-256 incorrecte : fichier rejeté." >&2 ; exit 1; }
      echo "SHA-256 vérifiée."
    else
      echo "AVERTISSEMENT : pas de fichier .sha256 sur cette release, somme non vérifiée." >&2
    fi
    FILE="$WORK/$ASSET"
  fi
fi
[ -f "$FILE" ] || { echo "Fichier introuvable : $FILE" >&2 ; exit 1; }

mkdir -p "$APPDIR" "$PREFIX/bin" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
install -m755 "$FILE" "$TARGET"
ln -sf "$TARGET" "$BIN"

# Icône : extraite de l'AppImage elle-même (--appimage-extract ne demande pas FUSE)
( cd "$WORK" && "$TARGET" --appimage-extract pdf-equilibrist.png >/dev/null 2>&1 \
    && install -m644 squashfs-root/pdf-equilibrist.png "$ICON" ) || echo "Icône non extraite (le lanceur utilisera l'icône par défaut)."

cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=PDF-Equilibrist
GenericName=Éditeur PDF
GenericName[en]=PDF editor
Comment=Éditer, annoter, convertir et protéger des PDF localement, sans télémétrie
Comment[en]=Edit, annotate, convert and protect PDF files locally, with no telemetry
Exec="$TARGET" %f
Icon=pdf-equilibrist
Terminal=false
Categories=Office;Viewer;
MimeType=application/pdf;
StartupWMClass=PDF-Equilibrist
DESK
chmod 644 "$DESKTOP"
refresh_caches

echo "Installé dans $PREFIX :"
echo "  application : $TARGET"
echo "  commande    : $BIN"
echo "  menu        : $DESKTOP"
case ":$PATH:" in *":$PREFIX/bin:"*) ;; *) echo "  (ajoutez $PREFIX/bin à votre PATH pour utiliser la commande pdf-equilibrist)" ;; esac
echo "Mise à jour : relancez ce script (il télécharge la dernière version), ou utilisez Aide › À propos."
