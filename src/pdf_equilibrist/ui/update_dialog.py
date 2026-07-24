from __future__ import annotations

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QProgressBar, QFrame,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from pdf_equilibrist import __version__
from pdf_equilibrist import update as updater

_GREEN  = "#6BBF4E"
_GRAY   = "#888888"
_WHITE  = "#F0F0F0"

_GITHUB_URL = "https://github.com/Bit-Scripts/PDF-Equilibrist"


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


class _StatsThread(QThread):
    finished_ok = pyqtSignal(dict)
    finished_err = pyqtSignal(str)

    def __init__(self, repo: str | None = None):
        super().__init__()
        self.repo = repo

    def run(self):
        try:
            stats = updater.get_download_stats(self.repo, __version__)
            self.finished_ok.emit(stats)
        except Exception as e:
            self.finished_err.emit(str(e))


def _sep(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #3A3A3A;")
    return line


class UpdateDialog(QDialog):
    def __init__(self, parent=None, repo: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("À propos de PDF-Equilibrist")
        self.setMinimumWidth(460)
        self.setModal(True)

        self._repo = repo
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── À propos ──────────────────────────────────────────────────────────
        about_row = QHBoxLayout()
        from pdf_equilibrist.utils import resource_path
        logo_path = resource_path("assets/logo/PDF-Equilibrist-logo.png")
        if logo_path.exists():
            logo_lbl = QLabel()
            pix = QPixmap(str(logo_path)).scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_lbl.setPixmap(pix)
            about_row.addWidget(logo_lbl)

        about_text = QVBoxLayout()
        about_text.setSpacing(0)
        name_lbl = QLabel(f"PDF-Equilibrist <span style='color:{_GRAY};font-weight:normal;'>v{__version__}</span>")
        name_lbl.setTextFormat(Qt.TextFormat.RichText)
        name_lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        about_text.addWidget(name_lbl)
        desc_lbl = QLabel("Éditeur PDF de bureau — © 2026 PDF Equilibrist — Licence GPLv3")
        desc_lbl.setStyleSheet(f"color: {_GRAY}; font-size: 11px;")
        about_text.addWidget(desc_lbl)
        about_row.addLayout(about_text)
        about_row.addStretch()

        btn_github = QPushButton("Dépôt GitHub")
        btn_github.clicked.connect(self._open_github)
        about_row.addWidget(btn_github)
        layout.addLayout(about_row)

        layout.addWidget(_sep())

        # ── Vérification de version ───────────────────────────────────────────
        self._lbl = QLabel("Vérification des nouvelles versions…")
        layout.addWidget(self._lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        # ── Statistiques de téléchargement ────────────────────────────────────
        layout.addWidget(_sep())

        stats_title = QLabel("Téléchargements")
        stats_title.setStyleSheet(f"color: {_GRAY}; font-size: 11px;")
        layout.addWidget(stats_title)

        row_current = QHBoxLayout()
        row_current.addWidget(QLabel(f"Cette version (v{__version__}) :"))
        self._lbl_current = QLabel("…")
        self._lbl_current.setStyleSheet(f"color: {_GREEN}; font-weight: bold;")
        self._lbl_current.setAlignment(Qt.AlignmentFlag.AlignRight)
        row_current.addWidget(self._lbl_current)
        layout.addLayout(row_current)

        row_total = QHBoxLayout()
        row_total.addWidget(QLabel("Total toutes versions :"))
        self._lbl_total = QLabel("…")
        self._lbl_total.setStyleSheet(f"color: {_WHITE}; font-weight: bold;")
        self._lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        row_total.addWidget(self._lbl_total)
        layout.addLayout(row_total)

        layout.addWidget(_sep())

        # ── Boutons ───────────────────────────────────────────────────────────
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

        self._thread = _CheckThread(repo=self._repo)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.start()

        self._stats_thread = _StatsThread(repo=self._repo)
        self._stats_thread.finished_ok.connect(self._on_stats)
        self._stats_thread.finished_err.connect(self._on_stats_error)
        self._stats_thread.start()

    def _on_result(self, release: object | None):
        self._progress.setRange(0, 1)
        if not release:
            self._lbl.setText(f"v{__version__} — version la plus récente.")
            return
        self._release = release
        tag = release.get("tag_name") or release.get("name")
        self._lbl.setText(f"Nouvelle version disponible : {tag}")
        self._btn_open_page.setEnabled(True)
        asset = updater.find_installer_asset(release)
        self._btn_download.setEnabled(bool(asset))

    def _on_error(self, msg: str):
        self._progress.setRange(0, 1)
        self._lbl.setText(f"Erreur lors de la vérification : {msg}")

    def _on_stats(self, stats: dict):
        self._lbl_current.setText(f"{stats['current']:,}".replace(",", " "))
        self._lbl_total.setText(f"{stats['total']:,}".replace(",", " "))

    def _on_stats_error(self, _msg: str):
        self._lbl_current.setText("—")
        self._lbl_total.setText("—")

    def _open_github(self):
        import webbrowser
        webbrowser.open(_GITHUB_URL)

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
            try:
                if os.name == "nt":
                    # Fichier qu'on vient nous-même de télécharger dans le temp
                    os.startfile(str(target))  # nosec B606
                else:
                    import shutil
                    import subprocess  # nosec B404
                    xdg_open = shutil.which("xdg-open")
                    if xdg_open:
                        subprocess.Popen([xdg_open, str(target)])  # nosec B603
                    else:
                        raise FileNotFoundError("xdg-open introuvable")
            except Exception:
                import webbrowser
                webbrowser.open(target.parent.as_uri())
        except Exception as e:
            self._lbl.setText(f"Échec du téléchargement : {e}")
        finally:
            self._progress.setRange(0, 1)
