"""
main.py — Point d'entrée de PDF-Equilibrist
============================================
Ce module est le premier exécuté au lancement de l'application.
Il orchestre le démarrage en trois phases :

Phase 1 — Splash screen
    Crée la ``QApplication`` et affiche immédiatement le splash screen
    avec barre de progression verte, avant tout chargement lourd.

Phase 2 — Chargement progressif
    Importe les bibliothèques lourdes (PyMuPDF, pdf2docx, pdfplumber…)
    une par une en mettant à jour la barre de progression. Cette approche
    permet à l'utilisateur de voir l'avancement au lieu d'un écran noir.
    En cas d'erreur, une boîte de dialogue affiche le traceback complet.

Phase 3 — Démarrage de la boucle Qt
    Ferme le splash, effectue l'enregistrement Windows "Ouvrir avec..."
    (silencieux, premier lancement uniquement), ouvre le fichier passé
    en argument si l'app est lancée depuis l'explorateur, puis démarre
    la boucle d'événements Qt principale.

Compatibilité PyInstaller
--------------------------
``pyi_splash.close()`` est appelé si le module existe (exe compilé avec splash
PyInstaller actif). En mode dev, l'``ImportError`` est silencieusement ignoré.

"Ouvrir avec..." Windows
-------------------------
Quand un PDF est double-cliqué (association fichier) ou ouvert via
"Ouvrir avec... PDF Equilibrist", Windows passe le chemin en ``sys.argv[1]``.
Ce chemin est transmis à ``MainWindow._open_document()`` après le démarrage.
"""
import sys
import traceback


def main():
    # ── Phase 1 : QApplication et splash ─────────────────────────────────────
    # QApplication DOIT être créée avant tout widget Qt (y compris le splash).
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    from pdf_equilibrist.ui.splash_screen import SplashScreen
    splash = SplashScreen()
    splash.show()
    app.processEvents()   # forcer le rendu immédiat du splash

    # ── Phase 2 : chargement progressif des modules ───────────────────────────
    try:
        # PyMuPDF est la bibliothèque la plus lourde (~20 Mo) — chargée en premier
        splash.set_progress(5, "Chargement de PyMuPDF…")
        import fitz                                             # noqa: F401

        splash.set_progress(20, "Chargement de PyQt6…")
        from PyQt6.QtCore import Qt                             # noqa: F401

        # Bibliothèques de conversion Office/tableur — plusieurs Mo chacune
        splash.set_progress(35, "Chargement des convertisseurs…")
        import pdf2docx                                         # noqa: F401
        import pdfplumber                                       # noqa: F401
        import openpyxl                                         # noqa: F401
        import pptx                                             # noqa: F401

        # Chargement de l'UI (importe tous les modules PyQt6 de l'application)
        splash.set_progress(55, "Chargement de l'interface…")
        from pdf_equilibrist.app import create_app

        # Création et affichage de la fenêtre principale
        splash.set_progress(75, "Initialisation de la fenêtre…")
        create_app(app)

        splash.set_progress(95, "Prêt !")
        app.processEvents()

    except Exception:
        # Capturer tout crash de démarrage et l'afficher à l'utilisateur
        err = traceback.format_exc()
        splash.hide()
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox()
        box.setWindowTitle("Erreur au démarrage")
        box.setText("PDF Equilibrist n'a pas pu démarrer.")
        box.setDetailedText(err)
        box.setIcon(QMessageBox.Icon.Critical)
        box.exec()
        sys.exit(1)

    # ── Phase 3 : fermeture du splash et démarrage ────────────────────────────

    # Fermer le splash natif PyInstaller s'il est actif
    # (affiché pendant le bootstrap C/Python avant que Qt démarre)
    try:
        import pyi_splash
        pyi_splash.close()
    except ModuleNotFoundError:
        pass   # normal en mode dev — pyi_splash n'existe que dans l'exe

    splash.close()
    splash.deleteLater()

    # Enregistrement "Ouvrir avec..." Windows au premier lancement de l'exe.
    # Silencieux : ne fait rien en dev (sys.frozen=False) ni si déjà enregistré.
    from pdf_equilibrist.registration import auto_register
    auto_register()

    # Vérification silencieuse des mises à jour au démarrage — n'affiche un
    # dialogue que si une nouvelle version est réellement disponible.
    win = getattr(app, "_main_window", None)
    if win and hasattr(win, "check_updates_on_startup"):
        win.check_updates_on_startup()

    # Ouvrir le fichier PDF passé en argument sur la ligne de commande.
    # Windows transmet sys.argv[1] lors d'un double-clic ou d'un "Ouvrir avec..."
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if pdf_path.lower().endswith(".pdf"):
            if win and hasattr(win, "_open_document"):
                win._open_document(pdf_path)

    # Démarrer la boucle d'événements Qt — bloque jusqu'à la fermeture de la fenêtre
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
