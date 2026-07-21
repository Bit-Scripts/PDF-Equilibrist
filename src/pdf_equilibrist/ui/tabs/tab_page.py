"""
tabs/tab_page.py — Onglet "Page" du ribbon
===========================================
Opérations sur la structure du document (pages).

Insérer
-------
Demande un numéro de page via ``ask_page_index``, puis optionnellement
un PDF source. Appelle ``insert_page()`` qui insère une page blanche
ou les pages du PDF source à la position demandée.

Diviser
-------
Appelle ``split_pdf()`` qui crée un PDF par page dans le dossier choisi.
Le document actif n'est pas modifié — les fichiers sont écrits à côté.

Fusionner
----------
Sélection multi-fichiers PDF → ``merge_pdfs()`` → dialogue "Enregistrer sous".
Le résultat est un nouveau fichier (le document actif n'est pas modifié).

Inverser
---------
``invert_pages()`` retourne un **nouveau** ``fitz.Document``.
L'ancien document est fermé, le nouveau est assigné à ``document.fitz_doc``,
puis ``changed`` est émis. Ce pattern de remplacement du doc est
différent des autres opérations qui modifient en place.
"""
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QFileDialog
from pdf_equilibrist.ui.widgets import RibbonButton, RibbonGroup
from pdf_equilibrist.ui.dialogs import ask_page_index, show_info, show_error
from pdf_equilibrist.core.document import Document
from pdf_equilibrist.operations.pages import invert_pages, split_pdf, merge_pdfs, insert_page


class TabPage(QWidget):
    def __init__(self, document: Document, viewer):
        super().__init__()
        self.document = document
        self.viewer   = viewer

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        # ── Groupe Organisation ──────────────────────────────────────────────
        self._btn_insert = RibbonButton("⊕", "Insérer")
        self._btn_split  = RibbonButton("⊣⊢", "Diviser")
        self._btn_merge  = RibbonButton("⊢⊣", "Fusion\nner")
        self._btn_inv    = RibbonButton("⇅", "Inverser")
        grp_org = RibbonGroup("Organisation")
        grp_org.add(self._btn_insert, self._btn_split,
                    self._btn_merge, self._btn_inv)
        layout.addWidget(grp_org)

        # ── Groupe Mise en page ──────────────────────────────────────────────
        grp_layout = RibbonGroup("Mise en page")
        grp_layout.add(RibbonButton("⊡", "Rogner"),
                       RibbonButton("⬜", "Taille"))
        layout.addWidget(grp_layout)

        layout.addStretch()

        self._btn_insert.clicked.connect(self._insert)
        self._btn_split.clicked.connect(self._split)
        self._btn_merge.clicked.connect(self._merge)
        self._btn_inv.clicked.connect(self._invert)

    def _insert(self):
        if not self.document.is_open:
            return
        n     = len(self.document.fitz_doc)
        after = ask_page_index(self, n, f"Insérer après la page (1–{n}) :")
        if after is None:
            return
        src, _ = QFileDialog.getOpenFileName(
            self, "PDF source (vide = page blanche)", "", "PDF (*.pdf)")
        self.document.checkpoint()
        insert_page(self.document.fitz_doc, after, Path(src) if src else None)
        self.document.changed.emit()

    def _split(self):
        if not self.document.is_open:
            return
        out = QFileDialog.getExistingDirectory(self, "Dossier de sortie")
        if out:
            try:
                paths = split_pdf(self.document.fitz_doc, Path(out))
                show_info(self, "Diviser", f"{len(paths)} fichier(s) dans :\n{out}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _merge(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "PDF à fusionner", "", "PDF (*.pdf)")
        if not files:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "PDF fusionné", "", "PDF (*.pdf)")
        if out:
            try:
                merged = merge_pdfs([Path(f) for f in files])
                merged.save(out)
                merged.close()
                show_info(self, "Fusionner", f"PDF fusionné :\n{out}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _invert(self):
        if not self.document.is_open:
            return
        self.document.checkpoint()
        new_doc = invert_pages(self.document.fitz_doc)
        self.document.fitz_doc.close()
        self.document.fitz_doc = new_doc
        self.document.changed.emit()
