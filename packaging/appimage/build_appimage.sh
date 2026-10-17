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

# Script d'installation embarqué : la mise à jour intégrée le lance depuis l'AppImage en cours d'exécution
# (rien à télécharger ; l'icône est prise dans usr/share/icons, donc sans exécuter de fichier téléchargé).
mkdir -p "$APPDIR/usr/share/pdf-equilibrist"
install -m755 "$HERE/install.sh" "$APPDIR/usr/share/pdf-equilibrist/install.sh"

# AppStream metainfo (AppImageHub, logiciels de gestion d'applications) : version et date injectées
APP_VERSION="$("$PYTHON" -c 'import re,sys; print(re.search(r"__version__ = \"(.*?)\"", open(sys.argv[1], encoding="utf-8").read()).group(1))' "$ROOT/src/pdf_equilibrist/__init__.py")"
mkdir -p "$APPDIR/usr/share/metainfo"
sed -e "s/@VERSION@/${APP_VERSION}/" -e "s/@DATE@/$(date -u +%Y-%m-%d)/" \
  "$HERE/org.pdf_equilibrist.pdf_equilibrist.metainfo.xml" \
  > "$APPDIR/usr/share/metainfo/org.pdf_equilibrist.pdf_equilibrist.metainfo.xml"
# Validation informative : appstreamcli varie beaucoup selon la distribution de build (Ubuntu 22.04 : 0.15),
# une divergence de version ne doit pas empêcher de produire l'AppImage. Seul .desktop est bloquant.
if command -v appstreamcli >/dev/null 2>&1; then
  appstreamcli validate --no-net "$APPDIR/usr/share/metainfo/org.pdf_equilibrist.pdf_equilibrist.metainfo.xml"     || echo "   AVERTISSEMENT : le metainfo AppStream n'est pas valide pour cette version d'appstreamcli"
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$APPDIR/pdf-equilibrist.desktop"
fi

echo "== 3/4  Bibliothèques xcb pour Qt6 (libxcb-cursor n'est pas installée par défaut sur toutes les distributions)"
INTERNAL="$APPDIR/usr/lib/pdf-equilibrist/_internal"
# (pas de `exit` dans awk : avec pipefail, ldconfig recevrait SIGPIPE et set -e arrêterait le script)
cursor="$(ldconfig -p | awk '/libxcb-cursor\.so\.0 /{p=$NF} END{print p}')"
xkbx11="$(ldconfig -p | awk '/libxkbcommon-x11\.so\.0 /{p=$NF} END{print p}')"
qxcb="$(find "$INTERNAL" -name libqxcb.so | head -1)"
if [ -z "$cursor" ] || [ -z "$xkbx11" ]; then
  echo "   ERREUR : libxcb-cursor.so.0 ou libxkbcommon-x11.so.0 introuvable sur la machine de build" >&2
  echo "            (apt install libxcb-cursor0 libxkbcommon-x11-0) : l'AppImage ne démarrerait pas sur un système minimal" >&2
  exit 1
fi
# les bibliothèques + leurs dépendances xcb-* / xkbcommon* (hors libxcb.so.1 et libX11 : fournies par tout système X11).
# Sans cela Qt échoue sur un système minimal : « Could not load the Qt platform plugin "xcb" ».
for lib in "$cursor" "$xkbx11" $(ldd "$cursor" "$xkbx11" ${qxcb:+"$qxcb"} | awk '/libxcb-|libxkbcommon/{print $3}' | sort -u); do
  cp -nL "$lib" "$INTERNAL/" 2>/dev/null || true
done
echo "   embarquées : $(ls "$INTERNAL" | grep -Ec '^(libxcb-|libxkbcommon)' || true) bibliothèque(s) xcb-*/xkbcommon*"

du -sh "$APPDIR" | awk '{print "   AppDir : " $1}'

echo "== 4/4  AppImage"
if [ -n "${APPIMAGETOOL:-}" ] && [ -x "$APPIMAGETOOL" ]; then
  ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUT/PDF-Equilibrist-x86_64.AppImage" 2>&1 | tail -3 \
    || ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUT/PDF-Equilibrist-x86_64.AppImage"
  ls -la "$OUT"/*.AppImage
else
  echo "   APPIMAGETOOL non défini : AppDir seulement (l'AppImage est produite par la CI)."
fi
