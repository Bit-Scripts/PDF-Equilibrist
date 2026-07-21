"""
ui/dialogs.py — Dialogues modaux réutilisables
===============================================
Ce module centralise les dialogues de saisie utilisés par les tabs du ribbon.
Tous les dialogues sont thémés avec ``DIALOG_STYLE`` (fond sombre, thème cohérent).

Principe de conception
-----------------------
Chaque fonction retourne la valeur saisie ou ``None`` si l'utilisateur annule.
Les tabs appelants vérifient simplement ``if result:`` avant d'agir.
Aucun dialogue ne modifie directement le document — ils ne font que collecter
des paramètres qui sont ensuite passés aux fonctions de ``operations/``.

Fonctions disponibles
---------------------
- ``ask_password``          : saisie d'un mot de passe (masqué)
- ``ask_encrypt_passwords`` : deux mots de passe (user + owner) pour AES-256
- ``ask_page_index``        : numéro de page via QSpinBox
- ``ask_watermark_text``    : texte du filigrane
- ``ask_text_input``        : saisie de texte libre (générique)
- ``ask_image_format``      : sélection du format image (combo png/jpg/bmp/tiff)
- ``show_info``             : message d'information (non bloquant pour l'UX)
- ``show_error``            : message d'erreur critique
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QComboBox, QMessageBox,
)


DIALOG_STYLE = """
QDialog { background: #2D2D2D; color: #F0F0F0; }
QLabel { color: #F0F0F0; }
QLineEdit, QSpinBox, QComboBox {
    background: #1E1E1E; color: #F0F0F0;
    border: 1px solid #3A3A3A; border-radius: 4px; padding: 4px 8px;
}
QPushButton {
    background: #3A3A3A; color: #F0F0F0;
    border: 1px solid #4A4A4A; border-radius: 4px; padding: 5px 16px;
}
QPushButton:hover { background: #4A4A4A; }
QPushButton#primary {
    background: #6BBF4E; color: #1E1E1E; font-weight: bold; border: none;
}
QPushButton#primary:hover { background: #7ED45F; }
"""


def _ok_cancel(dialog: QDialog, layout: QVBoxLayout):
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    cancel = QPushButton("Annuler")
    ok = QPushButton("OK")
    ok.setObjectName("primary")
    cancel.clicked.connect(dialog.reject)
    ok.clicked.connect(dialog.accept)
    btn_row.addWidget(cancel)
    btn_row.addWidget(ok)
    layout.addLayout(btn_row)


def ask_password(parent, title: str, label: str = "Mot de passe :") -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(320)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    pw = QLineEdit()
    pw.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(pw)
    _ok_cancel(dlg, layout)
    return pw.text() if dlg.exec() == QDialog.DialogCode.Accepted else None


def ask_encrypt_passwords(parent) -> tuple[str, str] | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Chiffrer le PDF")
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(340)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Mot de passe utilisateur :"))
    user_pw = QLineEdit()
    user_pw.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(user_pw)
    layout.addWidget(QLabel("Mot de passe propriétaire (optionnel) :"))
    owner_pw = QLineEdit()
    owner_pw.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(owner_pw)
    _ok_cancel(dlg, layout)
    if dlg.exec() == QDialog.DialogCode.Accepted and user_pw.text():
        return user_pw.text(), owner_pw.text()
    return None


def ask_page_index(parent, max_page: int, label: str = "Après la page n° :") -> int | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Numéro de page")
    dlg.setStyleSheet(DIALOG_STYLE)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    spin = QSpinBox()
    spin.setRange(1, max_page)
    spin.setValue(1)
    layout.addWidget(spin)
    _ok_cancel(dlg, layout)
    return spin.value() - 1 if dlg.exec() == QDialog.DialogCode.Accepted else None


def ask_watermark_text(parent) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Filigrane")
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(320)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Texte du filigrane :"))
    txt = QLineEdit()
    txt.setPlaceholderText("ex: CONFIDENTIEL")
    layout.addWidget(txt)
    _ok_cancel(dlg, layout)
    return txt.text().strip() or None if dlg.exec() == QDialog.DialogCode.Accepted else None


def ask_text_input(parent, title: str, label: str) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(320)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    txt = QLineEdit()
    layout.addWidget(txt)
    _ok_cancel(dlg, layout)
    return txt.text().strip() or None if dlg.exec() == QDialog.DialogCode.Accepted else None


def ask_image_format(parent) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Format d'image")
    dlg.setStyleSheet(DIALOG_STYLE)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Format :"))
    combo = QComboBox()
    combo.addItems(["png", "jpg", "bmp", "tiff"])
    layout.addWidget(combo)
    _ok_cancel(dlg, layout)
    return combo.currentText() if dlg.exec() == QDialog.DialogCode.Accepted else None


def show_info(parent, title: str, message: str):
    QMessageBox.information(parent, title, message)


def show_error(parent, title: str, message: str):
    QMessageBox.critical(parent, title, message)
