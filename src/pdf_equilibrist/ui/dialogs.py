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
- ``ask_text_format``       : texte + police, taille, gras/italique, couleur
- ``ask_link_target``       : cible d'un lien (adresse web ou page du document)
- ``ask_image_format``      : sélection du format image (combo png/jpg/bmp/tiff)
- ``show_info``             : message d'information (non bloquant pour l'UX)
- ``show_error``            : message d'erreur critique
- ``ensure_suffix``         : force l'extension d'un chemin issu de getSaveFileName
"""
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QComboBox, QMessageBox, QCheckBox, QColorDialog,
)

# Polices PDF standard (base 14) : famille -> (normal, gras, italique, gras+italique)
PDF_FONTS = {
    "Helvetica": ("helv", "hebo", "heit", "hebi"),
    "Times":     ("tiro", "tibo", "tiit", "tibi"),
    "Courier":   ("cour", "cobo", "coit", "cobi"),
}


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
    cancel = QPushButton(QCoreApplication.translate("dialogs", "Annuler"))
    ok = QPushButton(QCoreApplication.translate("dialogs", "OK"))
    ok.setObjectName("primary")
    cancel.clicked.connect(dialog.reject)
    ok.clicked.connect(dialog.accept)
    btn_row.addWidget(cancel)
    btn_row.addWidget(ok)
    layout.addLayout(btn_row)


def ask_password(parent, title: str, label: str | None = None) -> str | None:
    if label is None:
        label = QCoreApplication.translate("dialogs", "Mot de passe :")
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
    dlg.setWindowTitle(QCoreApplication.translate("dialogs", "Chiffrer le PDF"))
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(340)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(QCoreApplication.translate("dialogs", "Mot de passe utilisateur :")))
    user_pw = QLineEdit()
    user_pw.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(user_pw)
    layout.addWidget(QLabel(QCoreApplication.translate("dialogs", "Mot de passe propriétaire (optionnel) :")))
    owner_pw = QLineEdit()
    owner_pw.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(owner_pw)
    _ok_cancel(dlg, layout)
    if dlg.exec() == QDialog.DialogCode.Accepted and user_pw.text():
        return user_pw.text(), owner_pw.text()
    return None


def ask_page_index(parent, max_page: int, label: str | None = None) -> int | None:
    if label is None:
        label = QCoreApplication.translate("dialogs", "Après la page n° :")
    dlg = QDialog(parent)
    dlg.setWindowTitle(QCoreApplication.translate("dialogs", "Numéro de page"))
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
    dlg.setWindowTitle(QCoreApplication.translate("dialogs", "Filigrane"))
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(320)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(QCoreApplication.translate("dialogs", "Texte du filigrane :")))
    txt = QLineEdit()
    txt.setPlaceholderText(QCoreApplication.translate("dialogs", "ex: CONFIDENTIEL"))
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


def pdf_fontname(family: str, bold: bool, italic: bool) -> str:
    """Nom de police PDF (base 14) pour une famille et un style."""
    names = PDF_FONTS.get(family, PDF_FONTS["Helvetica"])
    return names[(1 if bold else 0) + (2 if italic else 0)]


def ask_text_format(parent, title: str, label: str) -> dict | None:
    """Saisie d'un texte avec police, taille, style et couleur.

    Retourne ``{'text', 'fontname', 'family', 'bold', 'italic', 'fontsize',
    'color'}`` (couleur RGB 0–1) ou ``None`` si annulé / texte vide.
    """
    tr = QCoreApplication.translate
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(380)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    txt = QLineEdit()
    layout.addWidget(txt)

    row = QHBoxLayout()
    family = QComboBox()
    family.addItems(list(PDF_FONTS))
    size = QSpinBox()
    size.setRange(4, 200)
    size.setValue(14)
    size.setSuffix(" pt")
    bold = QCheckBox(tr("dialogs", "Gras"))
    italic = QCheckBox(tr("dialogs", "Italique"))
    row.addWidget(QLabel(tr("dialogs", "Police :")))
    row.addWidget(family, 1)
    row.addWidget(QLabel(tr("dialogs", "Taille :")))
    row.addWidget(size)
    layout.addLayout(row)

    row2 = QHBoxLayout()
    row2.addWidget(bold)
    row2.addWidget(italic)
    row2.addStretch()
    color_btn = QPushButton(tr("dialogs", "Couleur…"))
    chosen = {"c": QColor(0, 0, 0)}

    def _refresh():
        c = chosen["c"]
        fg = "#000" if c.lightness() > 128 else "#FFF"
        color_btn.setStyleSheet(
            f"background:{c.name()}; color:{fg}; border:1px solid #4A4A4A;")

    def _pick():
        c = QColorDialog.getColor(chosen["c"], dlg, tr("dialogs", "Couleur du texte"))
        if c.isValid():
            chosen["c"] = c
            _refresh()

    color_btn.clicked.connect(_pick)
    _refresh()
    row2.addWidget(color_btn)
    layout.addLayout(row2)

    _ok_cancel(dlg, layout)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    text = txt.text().strip()
    if not text:
        return None
    c = chosen["c"]
    return {
        "text": text,
        "family": family.currentText(),
        "bold": bold.isChecked(),
        "italic": italic.isChecked(),
        "fontname": pdf_fontname(family.currentText(), bold.isChecked(), italic.isChecked()),
        "fontsize": size.value(),
        "color": (c.redF(), c.greenF(), c.blueF()),
    }


def ask_link_target(parent, max_page: int) -> dict | None:
    """Choisit la cible d'un lien : ``{'uri': str}`` ou ``{'goto_page': int}`` (0-based)."""
    tr = QCoreApplication.translate
    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("dialogs", "Ajouter un lien"))
    dlg.setStyleSheet(DIALOG_STYLE)
    dlg.setMinimumWidth(360)
    layout = QVBoxLayout(dlg)
    kind = QComboBox()
    kind.addItems([tr("dialogs", "Adresse web ou e-mail"), tr("dialogs", "Page du document")])
    layout.addWidget(kind)
    url = QLineEdit()
    url.setPlaceholderText(tr("dialogs", "https://exemple.fr  ou  nom@exemple.fr"))
    layout.addWidget(url)
    page = QSpinBox()
    page.setRange(1, max(1, max_page))
    page.setPrefix(tr("dialogs", "Page "))
    page.hide()
    layout.addWidget(page)

    def _switch(i):
        url.setVisible(i == 0)
        page.setVisible(i == 1)
    kind.currentIndexChanged.connect(_switch)
    _ok_cancel(dlg, layout)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    if kind.currentIndex() == 1:
        return {"goto_page": page.value() - 1}
    text = url.text().strip()
    if not text:
        return None
    if "@" in text and ":" not in text:
        text = "mailto:" + text
    elif "://" not in text and not text.lower().startswith("mailto:"):
        text = "https://" + text
    return {"uri": text}


def ask_image_format(parent) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(QCoreApplication.translate("dialogs", "Format d'image"))
    dlg.setStyleSheet(DIALOG_STYLE)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(QCoreApplication.translate("dialogs", "Format :")))
    combo = QComboBox()
    combo.addItems(["png", "jpg", "bmp", "tiff"])
    layout.addWidget(combo)
    _ok_cancel(dlg, layout)
    return combo.currentText() if dlg.exec() == QDialog.DialogCode.Accepted else None


def show_info(parent, title: str, message: str):
    QMessageBox.information(parent, title, message)


def show_error(parent, title: str, message: str):
    QMessageBox.critical(parent, title, message)


def ensure_suffix(path: str, suffix: str) -> str:
    """
    Garantit que ``path`` se termine par ``suffix`` (ex. ``.pdf``).

    QFileDialog.getSaveFileName n'ajoute pas toujours l'extension du filtre
    sélectionné selon la plateforme — le dialogue natif Windows le fait,
    mais pas systématiquement sous Linux (confirmé sur Arch) si l'utilisateur
    ne la tape pas lui-même.
    """
    if not path or path.lower().endswith(suffix.lower()):
        return path
    return path + suffix
