"""
tabs/tab_proteger.py — Onglet "Protéger" du ribbon
====================================================
Chiffrement et déchiffrement AES-256 des documents PDF.

Chiffrer
---------
1. ``ask_encrypt_passwords`` → saisie du mot de passe utilisateur
   et optionnellement du mot de passe propriétaire.
2. ``ask_save_path`` → dialogue "Enregistrer sous" pour le fichier chiffré.
3. ``operations.protect.encrypt()`` → sauvegarde avec AES-256.
   Le document actif reste inchangé en mémoire.

Déchiffrer
-----------
1. Vérifie que le document est bien chiffré (``fitz_doc.is_encrypted``).
2. ``ask_password`` → saisie du mot de passe.
3. ``operations.protect.decrypt()`` → ``doc.authenticate(password)``.
   Retourne ``True`` si succès, ``False`` si mot de passe incorrect.
4. En cas de succès, ``document.changed`` est émis pour rafraîchir l'UI.

Note : le déchiffrement est en place (``authenticate`` déverrouille le doc
en mémoire sans créer de nouveau fichier). Pour sauvegarder un PDF déchiffré
sur le disque, l'utilisateur doit utiliser "Enregistrer sous".
"""
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QFileDialog
from pdf_equilibrist.ui.widgets import RibbonButton, RibbonGroup
from pdf_equilibrist.ui.dialogs import ask_encrypt_passwords, ask_password, show_info, show_error
from pdf_equilibrist.core.document import Document
from pdf_equilibrist.operations.protect import encrypt, decrypt


class TabProteger(QWidget):
    def __init__(self, document: Document):
        super().__init__()
        self.document = document

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        self._btn_enc = RibbonButton("🔒", "Chiffrer")
        self._btn_dec = RibbonButton("🔓", "Déchif\nfrer")

        grp = RibbonGroup("Protection")
        grp.add(self._btn_enc, self._btn_dec)
        layout.addWidget(grp)
        layout.addStretch()

        self._btn_enc.clicked.connect(self._encrypt)
        self._btn_dec.clicked.connect(self._decrypt)

    def _encrypt(self):
        if not self.document.is_open:
            return
        result = ask_encrypt_passwords(self)
        if not result:
            return
        user_pw, owner_pw = result
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF chiffré",
            str(self.document.path.with_stem(self.document.path.stem + "_chiffré")),
            "PDF (*.pdf)")
        if path:
            try:
                encrypt(self.document.fitz_doc, Path(path), user_pw, owner_pw)
                show_info(self, "Chiffrer", f"PDF chiffré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _decrypt(self):
        if not self.document.is_open:
            return
        if not self.document.fitz_doc.is_encrypted:
            show_info(self, "Déchiffrer", "Ce document n'est pas chiffré.")
            return
        pw = ask_password(self, "Déchiffrer")
        if pw is None:
            return
        self.document.checkpoint()
        if decrypt(self.document.fitz_doc, pw):
            self.document.changed.emit()
            show_info(self, "Déchiffrer", "Document déchiffré.")
        else:
            show_error(self, "Déchiffrer", "Mot de passe incorrect.")
