#!/usr/bin/env bash
# Construit l'AppDir (et, si appimagetool est disponible, l'AppImage) de PDF-Equilibrist.
#
# Source unique pour la CI (.github/workflows/linux-appimage.yml) ET les essais locaux.
#
# Usage (depuis n'importe où) :
#   packaging/appimage/build_appimage.sh            # PyInstaller + AppDir
#   APPIMAGETOOL=/chemin/appimagetool packaging/appimage/build_appimage.sh   # + .AppImage
#
# Prérequis : Python 3.12 avec `pip install -r requirements.txt pyinstaller`, libxcb-cursor0 (Qt6/xcb).
# Sortie : build/appimage/AppDir/  et  build/appimage/PDF-Equilibrist-x86_64.AppImage
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/build/appimage"
APPDIR="$OUT/AppDir"
PYTHON="${PYTHON:-python3}"

cd "$ROOT"
rm -rf "$OUT"
mkdir -p "$OUT"

echo "== 1/4  PyInstaller (onedir)"
"$PYTHON" -m PyInstaller --noconfirm --clean \
  --distpath "$OUT/dist" --workpath "$OUT/work" \
  "$HERE/PDF-Equilibrist-linux.spec"

echo "== 2/4  AppDir"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/applications"
cp -a "$OUT/dist/PDF-Equilibrist" "$APPDIR/usr/lib/pdf-equilibrist"
install -m755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m644 "$HERE/pdf-equilibrist.desktop" "$APPDIR/pdf-equilibrist.desktop"
install -m644 "$HERE/pdf-equilibrist.desktop" "$APPDIR/usr/share/applications/pdf-equilibrist.desktop"
install -m644 "$ROOT/packaging/ppa/debian/pdf-equilibrist-256.png" "$APPDIR/pdf-equilibrist.png"
install -m644 "$ROOT/packaging/ppa/debian/pdf-equilibrist-256.png" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps/pdf-equilibrist.png"
ln -sf pdf-equilibrist.png "$APPDIR/.DirIcon"

# AppStream metainfo (AppImageHub, logiciels de gestion d'applications) : version et date injectées
APP_VERSION="$("$PYTHON" -c 'import re,sys; print(re.search(r"__version__ = \"(.*?)\"", open(sys.argv[1], encoding="utf-8").read()).group(1))' "$ROOT/src/pdf_equilibrist/__init__.py")"
mkdir -p "$APPDIR/usr/share/metainfo"
sed -e "s/@VERSION@/${APP_VERSION}/" -e "s/@DATE@/$(date -u +%Y-%m-%d)/" \
  "$HERE/org.pdf_equilibrist.pdf_equilibrist.metainfo.xml" \
  > "$APPDIR/usr/share/metainfo/org.pdf_equilibrist.pdf_equilibrist.metainfo.xml"
if command -v appstreamcli >/dev/null 2>&1; then
  appstreamcli validate --no-net "$APPDIR/usr/share/metainfo/org.pdf_equilibrist.pdf_equilibrist.metainfo.xml"
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$APPDIR/pdf-equilibrist.desktop"
fi

echo "== 3/4  Bibliothèques xcb pour Qt6 (libxcb-cursor n'est pas installée par défaut sur toutes les distributions)"
INTERNAL="$APPDIR/usr/lib/pdf-equilibrist/_internal"
# (pas de `exit` dans awk : avec pipefail, ldconfig recevrait SIGPIPE et set -e arrêterait le script)
cursor="$(ldconfig -p | awk '/libxcb-cursor\.so\.0 /{p=$NF} END{print p}')"
if [ -n "$cursor" ]; then
  # la bibliothèque + ses dépendances libxcb-* (hors libxcb.so.1 : fournie par tout système X11)
  for lib in "$cursor" $(ldd "$cursor" | awk '/libxcb-/{print $3}'); do
    cp -nL "$lib" "$INTERNAL/" 2>/dev/null || true
  done
  echo "   embarquée : $(ls "$INTERNAL" | grep -c '^libxcb-' || true) bibliothèque(s) libxcb-*"
else
  echo "   AVERTISSEMENT : libxcb-cursor.so.0 introuvable sur la machine de build (apt install libxcb-cursor0)"
fi

du -sh "$APPDIR" | awk '{print "   AppDir : " $1}'

echo "== 4/4  AppImage"
if [ -n "${APPIMAGETOOL:-}" ] && [ -x "$APPIMAGETOOL" ]; then
  ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUT/PDF-Equilibrist-x86_64.AppImage" 2>&1 | tail -3 \
    || ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUT/PDF-Equilibrist-x86_64.AppImage"
  ls -la "$OUT"/*.AppImage
else
  echo "   APPIMAGETOOL non défini : AppDir seulement (l'AppImage est produite par la CI)."
fi
