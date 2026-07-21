from __future__ import annotations

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QProgressBar,
)
from PyQt6.QtCore import QThread, pyqtSignal

from pdf_equilibrist import __version__
from pdf_equilibrist import update as updater


class _CheckThread(QThread):
    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)

    def __init__(self, repo: str | None = None):
        super().__init__()
        self.repo = repo

    def run(self):
        try:
            rel = updater.get_latest_release_info(__version__, self.repo)
            self.finished_ok.emit(rel)
        except Exception as e:
            self.finished_err.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, parent=None, repo: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Vérifier les mises à jour")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._repo = repo

        layout = QVBoxLayout(self)
        self._lbl = QLabel("Vérification des nouvelles versions…")
        layout.addWidget(self._lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_open_page = QPushButton("Ouvrir la page de la release")
        self._btn_open_page.setEnabled(False)
        self._btn_download = QPushButton("Télécharger et installer")
        self._btn_download.setEnabled(False)
        self._btn_close = QPushButton("Fermer")
        btn_row.addWidget(self._btn_open_page)
        btn_row.addWidget(self._btn_download)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

        self._btn_close.clicked.connect(self.accept)
        self._btn_open_page.clicked.connect(self._open_release_page)
        self._btn_download.clicked.connect(self._download_and_run)

        self._release = None

        # Lancer la vérification dans un thread pour ne pas bloquer l'UI
        self._thread = _CheckThread(repo=self._repo)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.start()

    def _on_result(self, release: object | None):
        self._progress.setRange(0, 1)
        if not release:
            self._lbl.setText("Aucune nouvelle version détectée.")
            return
        self._release = release
        tag = release.get("tag_name") or release.get("name")
        self._lbl.setText(f"Nouvelle version disponible : {tag}")
        self._btn_open_page.setEnabled(True)
        asset = updater.find_installer_asset(release)
        if asset:
            self._btn_download.setEnabled(True)
        else:
            self._btn_download.setEnabled(False)

    def _on_error(self, msg: str):
        self._progress.setRange(0, 1)
        self._lbl.setText(f"Erreur lors de la vérification : {msg}")

    def _open_release_page(self):
        if not self._release:
            return
        url = updater.get_release_page_url(self._release)
        if url:
            import webbrowser

            webbrowser.open(url)

    def _download_and_run(self):
        if not self._release:
            return
        asset = updater.find_installer_asset(self._release)
        if not asset:
            return
        target = updater.get_download_target(asset)
        try:
            self._lbl.setText("Téléchargement en cours…")
            self._progress.setRange(0, 0)
            updater.download_release_asset(asset, target)
            self._lbl.setText(f"Téléchargé : {target}")
            # Lancer l'installateur (Windows : os.startfile)
            try:
                if os.name == "nt":
                    os.startfile(str(target))
                else:
                    import subprocess

                    subprocess.Popen(["xdg-open", str(target)])
            except Exception:
                # Au moins ouvrir le dossier contenant
                import webbrowser

                webbrowser.open(target.parent.as_uri())
        except Exception as e:
            self._lbl.setText(f"Échec du téléchargement : {e}")
        finally:
            self._progress.setRange(0, 1)
