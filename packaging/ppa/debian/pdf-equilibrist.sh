#!/bin/sh
# Wrapper : lance l'app depuis le venv privé plutôt que de dépendre d'un
# shebang absolu dans venv/bin/pdf-equilibrist (fragile si le chemin
# d'installation change entre le build et l'exécution).
exec /usr/lib/pdf-equilibrist/venv/bin/python3 -m pdf_equilibrist.main "$@"
