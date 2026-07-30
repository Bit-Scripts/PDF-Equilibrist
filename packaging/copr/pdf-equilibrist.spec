Name:           pdf-equilibrist
Version:        0.1.14
Release:        1%{?dist}
Summary:        Free and open-source desktop PDF editor

# Le venv privé n'a ni sources C à débugger (pur Python + wheels manylinux
# déjà précompilées) ni shebangs utilisables par le scanner find-requires
# une fois hors du chroot de build : sans ces deux exclusions, rpmbuild
# échoue sur un %files debuginfo vide et génère un Requires bidon pointant
# vers %{_builddir} (chemin qui n'existe évidemment pas sur la machine
# cible) — même logique que dh_strip/dh_shlibdeps --exclude sur la PPA.
%global debug_package %{nil}
%global __requires_exclude_from ^%{_libdir}/%{name}/venv/.*$
%global __provides_exclude_from ^%{_libdir}/%{name}/venv/.*$

License:        GPL-3.0-or-later
URL:            https://github.com/Bit-Scripts/PDF-Equilibrist
# Le tag v0.1.10 (Flatpak) puis les tags AUR/PPA ont montré le même piège :
# le tarball de release ne contient pas forcément les derniers assets de
# packaging (.desktop/icônes) s'ils ont été ajoutés après le tag. On les
# embarque ici en sources locales plutôt que de dépendre du contenu du tag.
Source0:        %{name}-%{version}.tar.gz
Source1:        %{name}.desktop
Source2:        %{name}-128.png
Source3:        %{name}-256.png
Source4:        %{name}.sh
# Dépendances Python absentes des dépôts Fedora (vérifié par test réel avec
# dnf, pas seulement par recherche sur packages.fedoraproject.org — la
# recherche web indiquait à tort python3-docx comme empaqueté). Pures
# Python sauf pypdfium2 (wheel manylinux mais tag "py3", donc indépendant
# de la version de CPython) — pas besoin de wheelhouse complet comme pour
# la PPA Ubuntu, où opencv/numpy/etc. manquaient aussi.
Source10:       pdf2docx-0.5.13-py3-none-any.whl
Source11:       pdfplumber-0.11.10-py3-none-any.whl
Source12:       python_pptx-1.0.2-py3-none-any.whl
Source13:       python_docx-1.2.0-py3-none-any.whl
Source14:       pypdfium2-5.12.1-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

BuildArch:      x86_64
# x86_64 et non noarch : le wheel pypdfium2 vendorisé embarque une
# bibliothèque partagée précompilée (libpdfium) spécifique à cette
# architecture.

BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python3-pyqt6
BuildRequires:  desktop-file-utils

Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-PyMuPDF
Requires:       python3-openpyxl
Requires:       python3-pyparsing
Requires:       python3-pillow
Requires:       python3-opencv
Requires:       python3-xlsxwriter
Requires:       python3-lxml
Requires:       python3-numpy
Requires:       python3-typing-extensions
Requires:       python3-fire
Requires:       python3-fonttools
Requires:       python3-pdfminer
Requires:       hicolor-icon-theme
Requires:       desktop-file-utils

%description
PDF-Equilibrist is a free, open-source desktop PDF editor built with
Python (PyQt6 + PyMuPDF). It runs entirely locally: no cloud, no
telemetry, no account required.

Features: text editing, annotations, watermarks, signatures/stamps,
page management, conversion to/from Word/Excel/PowerPoint/images,
local OCR, and AES-256 encryption/decryption.

pdf2docx, pdfplumber, python-docx, python-pptx and pypdfium2 are not
packaged for Fedora — they are bundled in a private virtual
environment under %{_libdir}/%{name}/venv, built offline from
vendored wheels (this build has no network access).

%prep
%setup -q -n PDF-Equilibrist-%{version}
# Aligne __version__ sur la version du paquet — même logique que le sed
# du PKGBUILD AUR / debian/rules PPA : sans ça, l'app se pense en v0.1.0
# (valeur statique de src/pdf_equilibrist/__init__.py) et le vérificateur
# de MAJ affiche "nouvelle version disponible" pour la version qu'on
# vient d'installer soi-même.
sed -i 's/^__version__ = ".*"/__version__ = "%{version}"/' src/pdf_equilibrist/__init__.py
sed -i 's/^version = ".*"$/version = "%{version}"/' pyproject.toml

%build
# --system-site-packages pour voir python3-pyqt6/PyMuPDF/opencv/numpy/...
# (paquets système, jamais vendorisés) — seuls pdf2docx/pdfplumber/
# python-docx/python-pptx/pypdfium2 manquent des dépôts Fedora.
python3 -m venv --system-site-packages venv-build
# --no-deps + liste explicite de chaque wheel vendorisé (pas seulement les
# paquets top-level) : avec --system-site-packages, pip pourrait sinon
# considérer une dépendance transitive "déjà satisfaite" par un paquet
# système présent sur la machine de *build* mais absent de la machine
# *cible* — piège déjà rencontré sur la PPA Ubuntu (numpy manquant au
# runtime). Ici les 5 wheels vendorisés n'ont pas de sous-dépendance
# propre en dehors des paquets système, mais on garde le même réflexe
# défensif.
venv-build/bin/pip install --no-index --no-deps \
    %{SOURCE10} %{SOURCE11} %{SOURCE12} %{SOURCE13} %{SOURCE14}
venv-build/bin/pip install --no-index --no-build-isolation --no-deps .

# pip n'est jamais invoqué au runtime (l'app n'installe rien elle-même) —
# on le retire du venv livré plutôt que de courir après chaque nouvelle CVE
# pip (le scanner CVE intégré à l'app le remontait alors qu'il ne sert à
# rien une fois le paquet construit) : ensurepip embarque systématiquement
# la version figée dans le Python système du chroot de build, jamais la
# dernière corrigée en amont.
rm -rf venv-build/bin/pip venv-build/bin/pip3 venv-build/bin/pip3.* \
    venv-build/lib/python3.*/site-packages/pip \
    venv-build/lib/python3.*/site-packages/pip-*.dist-info

%install
rm -rf %{buildroot}
install -d %{buildroot}%{_libdir}/%{name}
cp -r venv-build %{buildroot}%{_libdir}/%{name}/venv
# Chemin absolu correct une fois le paquet installé (pas le chroot de build)
sed -i "1s|^#!.*|#!%{_libdir}/%{name}/venv/bin/python3|" \
    %{buildroot}%{_libdir}/%{name}/venv/bin/pdf-equilibrist || true

install -Dm755 %{SOURCE4} %{buildroot}%{_bindir}/%{name}
install -Dm644 %{SOURCE1} %{buildroot}%{_datadir}/applications/%{name}.desktop
# hicolor plutôt que /usr/share/pixmaps/ (repli historique) : même choix
# que les paquets AUR et PPA, le dock GNOME résout mal les icônes en
# pixmaps seul.
install -Dm644 %{SOURCE2} %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/%{name}.png
install -Dm644 %{SOURCE3} %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

# resource_path() (src/pdf_equilibrist/utils.py) résout les assets sous
# {sys.prefix}/share/pdf-equilibrist/assets/ — dans le venv privé,
# sys.prefix vaut %{_libdir}/%{name}/venv, PAS %{_prefix} (même piège que
# sur la PPA Ubuntu). Les assets doivent donc vivre dans le venv lui-même.
install -d %{buildroot}%{_libdir}/%{name}/venv/share/%{name}
cp -r assets %{buildroot}%{_libdir}/%{name}/venv/share/%{name}/assets

desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop

%files
%license LICENSE.md
%{_bindir}/%{name}
%{_libdir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/128x128/apps/%{name}.png
%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

%changelog
* Sun Jul 26 2026 Paul Woisard <paulwoisard@gmail.com> - 0.1.14-1
- Fix CVE checker on frozen builds: the purelib-scoped dependency scan
  (added to avoid --system-site-packages noise on Linux venv packages,
  including this one) broke Windows' PyInstaller exe. Frozen builds now
  fall back to the unrestricted scan; this COPR package was never
  affected since it never takes the frozen code path.

* Sun Jul 26 2026 Paul Woisard <paulwoisard@gmail.com> - 0.1.13-1
- Explicitly declare the .desktop file id via QApplication.setDesktopFileName()
  (detected at runtime, same "pdf-equilibrist" id as the PPA package) —
  under GNOME/Wayland, the dock doesn't reliably match a window to its
  .desktop entry via WM_CLASS/process name alone.
- Initial COPR packaging, mirroring the AUR and PPA channels.
