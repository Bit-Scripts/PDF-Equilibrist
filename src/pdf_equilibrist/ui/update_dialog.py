from __future__ import annotations

import os
import subprocess  # nosec B404
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QProgressBar, QFrame, QLineEdit, QApplication, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import QProcess, QProcessEnvironment, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from pdf_equilibrist import __version__
from pdf_equilibrist import network
from pdf_equilibrist import update as updater
from pdf_equilibrist.utils import external_env, open_external

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


class _DownloadThread(QThread):
    """Télécharge hors du fil de l'interface (un installeur / une AppImage pèse plusieurs centaines de Mo)."""
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal()
    finished_err = pyqtSignal(str)

    def __init__(self, asset: dict, target):
        super().__init__()
        self.asset = asset
        self.target = target

    def run(self):
        try:
            updater.download_release_asset(
                self.asset, self.target, progress=lambda done, total: self.progress.emit(done, total))
            self.finished_ok.emit()
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
        self.setWindowTitle(self.tr("À propos de PDF-Equilibrist"))
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
        desc_lbl = QLabel(self.tr("Éditeur PDF de bureau — © 2026 PDF Equilibrist — Licence GPLv3"))
        desc_lbl.setStyleSheet(f"color: {_GRAY}; font-size: 11px;")
        about_text.addWidget(desc_lbl)
        about_row.addLayout(about_text)
        about_row.addStretch()

        btn_github = QPushButton(self.tr("Dépôt GitHub"))
        btn_github.clicked.connect(self._open_github)
        about_row.addWidget(btn_github)
        layout.addLayout(about_row)

        layout.addWidget(_sep())

        # ── Vérification de version ───────────────────────────────────────────
        self._lbl = QLabel(self.tr("Vérification des nouvelles versions…"))
        self._lbl.setWordWrap(True)
        layout.addWidget(self._lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        # Dire où l'on se connecte, et ce qui part : rien d'autre qu'une requête.
        self._net_notice = QLabel(self.tr(
            "Connexion à api.github.com (GitHub) pour la version et les "
            "statistiques. Aucun document ni aucune donnée personnelle n'est envoyé."))
        self._net_notice.setWordWrap(True)
        self._net_notice.setStyleSheet(f"color: {_GRAY}; font-size: 11px;")
        layout.addWidget(self._net_notice)

        # ── Statistiques de téléchargement ────────────────────────────────────
        layout.addWidget(_sep())

        stats_title = QLabel(self.tr("Téléchargements"))
        stats_title.setStyleSheet(f"color: {_GRAY}; font-size: 11px;")
        layout.addWidget(stats_title)

        row_current = QHBoxLayout()
        row_current.addWidget(QLabel(self.tr("Cette version (v{0}) :").format(__version__)))
        self._lbl_current = QLabel("…")
        self._lbl_current.setStyleSheet(f"color: {_GREEN}; font-weight: bold;")
        self._lbl_current.setAlignment(Qt.AlignmentFlag.AlignRight)
        row_current.addWidget(self._lbl_current)
        layout.addLayout(row_current)

        row_total = QHBoxLayout()
        row_total.addWidget(QLabel(self.tr("Total toutes versions :")))
        self._lbl_total = QLabel("…")
        self._lbl_total.setStyleSheet(f"color: {_WHITE}; font-weight: bold;")
        self._lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        row_total.addWidget(self._lbl_total)
        layout.addLayout(row_total)

        layout.addWidget(_sep())

        # ── Commande de mise à jour Linux (AUR, etc.) ─────────────────────────
        # Masquée par défaut : affichée seulement si une nouvelle version existe
        # ET qu'on tourne sur un paquet système Linux connu (jamais l'exe Windows
        # à la place, voir update.linux_update_command()).
        self._linux_cmd_row = QHBoxLayout()
        self._linux_cmd_edit = QLineEdit()
        self._linux_cmd_edit.setReadOnly(True)
        self._btn_copy_cmd = QPushButton(self.tr("Copier"))
        self._linux_cmd_row.addWidget(QLabel(self.tr("Mise à jour :")))
        self._linux_cmd_row.addWidget(self._linux_cmd_edit)
        self._linux_cmd_row.addWidget(self._btn_copy_cmd)
        self._linux_cmd_widget = QFrame()
        self._linux_cmd_widget.setLayout(self._linux_cmd_row)
        self._linux_cmd_widget.setVisible(False)
        layout.addWidget(self._linux_cmd_widget)
        self._btn_copy_cmd.clicked.connect(self._copy_linux_command)

        # ── Adresse à copier à la main (affichée seulement si aucun navigateur ne s'ouvre) ──
        self._url_edit = QLineEdit()
        self._url_edit.setReadOnly(True)
        self._btn_copy_url = QPushButton(self.tr("Copier"))
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel(self.tr("Adresse :")))
        url_row.addWidget(self._url_edit)
        url_row.addWidget(self._btn_copy_url)
        self._url_widget = QFrame()
        self._url_widget.setLayout(url_row)
        self._url_widget.setVisible(False)
        layout.addWidget(self._url_widget)
        self._btn_copy_url.clicked.connect(
            lambda: QApplication.clipboard().setText(self._url_edit.text()))

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_open_page = QPushButton(self.tr("Ouvrir la page de la release"))
        self._btn_open_page.setEnabled(False)
        self._btn_download = QPushButton(self.tr("Télécharger et installer"))
        self._btn_download.setEnabled(False)
        self._btn_close = QPushButton(self.tr("Fermer"))
        btn_row.addWidget(self._btn_open_page)
        btn_row.addWidget(self._btn_download)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

        # Lien (AppImage seulement) : récupérer le script qui l'installe dans le menu et le PATH
        self._script_link = QLabel(
            f"<a href='#script' style='color:{_GREEN};'>"
            + self.tr("Télécharger le script d'installation (install.sh)") + "</a>")
        self._script_link.setTextFormat(Qt.TextFormat.RichText)
        self._script_link.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._script_link.setVisible(False)
        self._script_link.linkActivated.connect(lambda _href: self._download_script())
        layout.addWidget(self._script_link)

        self._btn_close.clicked.connect(self.accept)
        self._btn_open_page.clicked.connect(self._open_release_page)
        self._btn_download.clicked.connect(self._download_and_run)

        self._release = None

        if network.is_blocked():
            # Réglage de l'utilisateur : ni requête, ni fenêtre qui attend.
            self._progress.setRange(0, 1)
            self._lbl.setText(self.tr("Version installée : v{0}").format(__version__))
            self._net_notice.setText(self.tr(
                "Connexions Internet bloquées : aucune requête envoyée "
                "(menu Aide › Connexions Internet)."))
            self._lbl_current.setText("—")
            self._lbl_total.setText("—")
            return

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
            self._lbl.setText(self.tr("v{0} — version la plus récente.").format(__version__))
            return
        self._release = release
        tag = release.get("tag_name") or release.get("name")
        self._lbl.setText(self.tr("Nouvelle version disponible : {0}").format(tag))
        self._btn_open_page.setEnabled(True)

        linux_cmd = updater.linux_update_command()
        if linux_cmd is not None:
            # Paquet système Linux connu (AUR…) : la commande du gestionnaire
            # de paquets remplace le téléchargement de l'exe Windows, inutile
            # et trompeur ici.
            self._linux_cmd_edit.setText(linux_cmd)
            self._linux_cmd_widget.setVisible(True)
            self._btn_download.setEnabled(False)
            self._btn_download.setVisible(False)
        elif updater.is_appimage():
            # AppImage : la release contient la nouvelle AppImage, à télécharger.
            self._btn_download.setText(self.tr("Télécharger la nouvelle AppImage"))
            self._btn_download.setEnabled(bool(updater.find_appimage_asset(release)))
            self._script_link.setVisible(bool(updater.find_install_script_asset(release)))
        elif os.name != "nt":
            # Linux non reconnu (pas encore de PPA/COPR, ou distro inconnue) :
            # ni exe Windows ni commande fiable à proposer, on masque juste
            # l'action au lieu de télécharger un installeur inutilisable.
            self._btn_download.setEnabled(False)
            self._btn_download.setVisible(False)
        else:
            asset = updater.find_installer_asset(release)
            self._btn_download.setEnabled(bool(asset))

    def _copy_linux_command(self):
        QApplication.clipboard().setText(self._linux_cmd_edit.text())

    def _on_error(self, msg: str):
        self._progress.setRange(0, 1)
        self._lbl.setText(self.tr("Erreur lors de la vérification : {0}").format(msg))

    def _on_stats(self, stats: dict):
        self._lbl_current.setText(f"{stats['current']:,}".replace(",", " "))
        self._lbl_total.setText(f"{stats['total']:,}".replace(",", " "))

    def _on_stats_error(self, _msg: str):
        self._lbl_current.setText("—")
        self._lbl_total.setText("—")

    def _open_url(self, url: str):
        """Ouvre l'URL ; sans navigateur utilisable (WSL, serveur…), l'affiche et la copie dans le presse-papiers."""
        if open_external(url):
            return
        QApplication.clipboard().setText(url)
        self._url_edit.setText(url)
        self._url_edit.setCursorPosition(0)
        self._url_widget.setVisible(True)
        self._lbl.setText(self.tr("Aucun navigateur détecté : adresse copiée dans le presse-papiers."))

    def _open_github(self):
        self._open_url(_GITHUB_URL)

    def _open_release_page(self):
        if not self._release:
            return
        url = updater.get_release_page_url(self._release)
        if url:
            self._open_url(url)

    def _quit_for_installer(self):
        self.accept()
        QApplication.closeAllWindows()
        QApplication.quit()

    def _start_download(self, asset: dict, target, on_done):
        """Lance le téléchargement en arrière-plan, avec barre de progression."""
        self._pending_asset = asset
        self._btn_download.setEnabled(False)
        self._lbl.setText(self.tr("Téléchargement en cours…"))
        self._progress.setRange(0, 0)
        self._dl_thread = _DownloadThread(asset, target)
        self._dl_thread.progress.connect(self._on_download_progress)
        self._dl_thread.finished_ok.connect(lambda: self._on_download_done(target, on_done))
        self._dl_thread.finished_err.connect(self._on_download_error)
        self._dl_thread.start()

    def _on_download_progress(self, done: int, total: int):
        mb = done / 1_048_576
        if total:
            self._progress.setRange(0, total)
            self._progress.setValue(done)
            self._lbl.setText(self.tr("Téléchargement : {0:.0f} / {1:.0f} Mo").format(mb, total / 1_048_576))
        else:
            self._lbl.setText(self.tr("Téléchargement : {0:.0f} Mo").format(mb))

    def _on_download_error(self, msg: str):
        self._progress.setRange(0, 1)
        self._btn_download.setEnabled(True)
        self._lbl.setText(self.tr("Échec du téléchargement : {0}").format(msg))

    def _on_download_done(self, target, on_done):
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        on_done(target)

    def _download_appimage(self):
        asset = updater.find_appimage_asset(self._release)
        if not asset:
            return
        self._start_download(asset, updater.appimage_download_target(self._release), self._appimage_ready)

    def _download_script(self):
        asset = updater.find_install_script_asset(self._release) if self._release else None
        if asset:
            self._start_download(asset, updater.install_script_target(self._release), self._script_ready)

    def _script_ready(self, target):
        try:
            target.chmod(0o755)
        except OSError:
            pass
        self._btn_download.setEnabled(True)
        self._lbl.setText(self.tr(
            "Script d'installation téléchargé :\n{0}\nLancez : bash install.sh   (ou sudo bash install.sh --system)"
        ).format(target))

    def _appimage_ready(self, target):
        try:
            target.chmod(0o755)
        except OSError:
            pass
        self._btn_download.setEnabled(True)
        self._new_appimage = target
        if updater.bundled_install_script() is None:
            # AppImage sans script embarqué (ancienne version) : repli manuel
            self._lbl.setText(self.tr(
                "Nouvelle AppImage téléchargée :\n{0}\nFermez l'application puis lancez ce fichier "
                "(ou : bash install.sh --file <fichier>)."
            ).format(target))
            return
        try:
            self._new_sha = updater.expected_sha256(self._pending_asset, target)
        except OSError as e:
            self._lbl.setText(self.tr("Impossible de lire le fichier téléchargé : {0}").format(e))
            return
        self._lbl.setText(self.tr("Nouvelle version téléchargée et vérifiée :\n{0}").format(target))
        answer = QMessageBox.question(
            self, self.tr("Installer la nouvelle version"),
            self.tr("La nouvelle version est téléchargée. L'installer maintenant ?"),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._choose_scope_and_install()

    def _choose_scope_and_install(self):
        scope = updater.install_scope()
        if scope == "user":
            self._run_install("user")
            return
        box = QMessageBox(self)
        box.setWindowTitle(self.tr("Installer pour qui ?"))
        if scope == "system":
            box.setText(self.tr(
                "Cette version est installée pour tous les utilisateurs de l'ordinateur. Mettre à jour :\n\n"
                "• pour vous seulement : une copie dans votre dossier personnel, sans mot de passe ;\n"
                "• pour tous : le système vous demandera l'autorisation d'un administrateur."))
        else:
            box.setText(self.tr(
                "Cette copie n'est pas installée. L'installer :\n\n"
                "• pour vous seulement : dans votre dossier personnel, sans mot de passe ;\n"
                "• pour tous les utilisateurs : le système vous demandera l'autorisation d'un administrateur."))
        btn_me = box.addButton(self.tr("Pour moi uniquement"), QMessageBox.ButtonRole.AcceptRole)
        btn_all = box.addButton(self.tr("Pour tous les utilisateurs"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(self.tr("Annuler"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is btn_me:
            self._run_install("user")
        elif box.clickedButton() is btn_all:
            self._run_install("system")

    def _run_install(self, scope: str):
        command = updater.build_install_command(self._new_appimage, scope, self._new_sha)
        method = "user" if scope != "system" else "pkexec"
        if command is None and scope == "system":
            # Pas de pkexec (WSL, bureau minimal, serveur…) : repli sur sudo avec notre propre demande de mot de passe
            self._run_install_sudo()
            return
        if command is None:
            self._show_manual_install_hint(scope)
            return
        self._start_install(command, scope, method)

    def _run_install_sudo(self):
        command = updater.build_sudo_install_command(self._new_appimage, self._new_sha)
        if command is None:
            self._show_manual_install_hint("system")
            return
        password, accepted = QInputDialog.getText(
            self, self.tr("Mot de passe administrateur"),
            self.tr("Aucune fenêtre d'autorisation du système n'est disponible. Pour installer pour tous les "
                    "utilisateurs, saisissez votre mot de passe : il est transmis uniquement à sudo, jamais "
                    "enregistré ni affiché."),
            QLineEdit.EchoMode.Password,
        )
        if not accepted or not password:
            self._lbl.setText(self.tr("Installation annulée : rien n'a été installé."))
            return
        self._start_install(command, "system", "sudo", password)

    def _show_manual_install_hint(self, scope: str):
        hint = "sudo bash install.sh --system --file " if scope == "system" else "bash install.sh --file "
        self._lbl.setText(self.tr(
            "Installation automatique indisponible sur ce système (pkexec, sudo ou le script est introuvable).\n"
            "Dans un terminal : {0}{1}"
        ).format(hint, self._new_appimage))

    def _start_install(self, command: list[str], scope: str, method: str, stdin_text: str | None = None):
        self._install_scope = scope
        self._install_method = method
        self._install_output = ""
        self._btn_download.setEnabled(False)
        self._progress.setRange(0, 0)
        self._lbl.setText(self.tr("Installation en cours…"))
        env = QProcessEnvironment()
        for key, value in external_env().items():
            env.insert(key, value)
        if method == "sudo":
            env.insert("LC_ALL", "C")   # messages de sudo en anglais, pour reconnaître « mot de passe incorrect »
        self._proc = QProcess(self)
        self._proc.setProcessEnvironment(env)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_install_output)
        self._proc.finished.connect(self._on_install_finished)
        self._proc.errorOccurred.connect(self._on_install_error)
        if method == "sudo":
            # le mot de passe part sur l'entrée de sudo (-S) dès le démarrage, puis l'entrée est fermée
            self._proc.started.connect(lambda: self._send_to_stdin(stdin_text or ""))
        self._proc.start(command[0], command[1:])

    def _send_to_stdin(self, text: str):
        self._proc.write((text + "\n").encode("utf-8"))
        self._proc.closeWriteChannel()

    def _on_install_output(self):
        self._install_output += bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")

    def _on_install_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._progress.setRange(0, 1)
            self._btn_download.setEnabled(True)
            self._lbl.setText(self.tr("Impossible de lancer l'installation."))

    def _on_install_finished(self, exit_code: int, _status):
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._btn_download.setEnabled(True)
        if exit_code == 0:
            installed = updater.installed_appimage_path(self._install_scope)
            self._lbl.setText(self.tr("Installée : {0}").format(installed))
            answer = QMessageBox.question(
                self, self.tr("Installation terminée"),
                self.tr("La nouvelle version est installée. Relancer l'application maintenant ?"),
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._relaunch(installed)
            return
        output = self._install_output.lower()
        if self._install_method == "pkexec" and exit_code in (126, 127):
            if "no authentication agent" in output:
                # pkexec existe mais aucun agent graphique n'est lancé : on demande le mot de passe nous-mêmes
                self._run_install_sudo()
            else:
                self._lbl.setText(self.tr("Autorisation refusée ou annulée : rien n'a été installé."))
            return
        if self._install_method == "sudo" and any(
                text in output for text in ("incorrect password", "no password was provided", "try again")):
            self._lbl.setText(self.tr("Mot de passe incorrect : rien n'a été installé."))
            return
        lines = [line for line in self._install_output.splitlines() if line.strip()]
        detail = "\n".join(lines[-3:])
        self._lbl.setText(self.tr("L'installation a échoué (code {0}).\n{1}").format(exit_code, detail))

    def _relaunch(self, path):
        try:
            subprocess.Popen(  # nosec B603
                [str(path)], env=updater.relaunch_env(), start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            self._lbl.setText(self.tr("Impossible de relancer l'application : {0}").format(e))
            return
        self._quit_for_installer()

    def _download_and_run(self):
        if not self._release:
            return
        if updater.is_appimage():
            self._download_appimage()
            return
        asset = updater.find_installer_asset(self._release)
        if not asset:
            return
        self._start_download(asset, updater.get_download_target(asset), self._installer_ready)

    def _installer_ready(self, target):
        self._lbl.setText(self.tr("Téléchargé : {0}").format(target))
        try:
            if os.name == "nt":
                # Fichier qu'on vient nous-même de télécharger dans le temp
                os.startfile(str(target))  # nosec B606
                # Pas de fermeture automatique ici : c'est l'installeur NSIS qui détecte
                # l'application ouverte et propose de la fermer (macro CHECK_APP_RUNNING,
                # installer/PDF-Equilibrist.nsi). _quit_for_installer reste utilisé par
                # l'AppImage (_download_appimage), qui n'a pas d'installeur pour le faire.
            else:
                open_external(str(target))
        except Exception:
            open_external(target.parent.as_uri())
