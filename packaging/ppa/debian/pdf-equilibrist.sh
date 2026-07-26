#!/bin/sh
# Lance le vrai script d'entrée généré par pip dans le venv (son shebang est
# déjà réécrit vers le chemin d'install final par debian/rules), plutôt que
# `python3 -m pdf_equilibrist.main` : ce dernier fait apparaître le process
# sous le nom "python3", pas "pdf-equilibrist" — Qt/X11 en déduisent alors un
# WM_CLASS qui ne correspond plus à StartupWMClass dans le .desktop, et le
# bureau ne peut plus associer l'icône de la fenêtre à celle du lanceur.
exec /usr/lib/pdf-equilibrist/venv/bin/pdf-equilibrist "$@"
