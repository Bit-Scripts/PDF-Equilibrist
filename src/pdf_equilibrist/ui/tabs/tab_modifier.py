"""
tabs/tab_modifier.py — Onglet "Modifier" du ribbon
====================================================
Modifications du contenu textuel et graphique du PDF.

Édition de texte (flux principal)
-----------------------------------
1. Clic "✎ Modifier texte" → ``_toggle_edit()``
2. Extrait tous les ``TextBlock`` via ``extract_text_blocks()`` (toutes les pages)
3. Appelle ``viewer.enter_edit_mode(blocks_by_page)``
   → les ``QLabel`` de pages sont remplacés par des ``PageEditWidget``
4. L'utilisateur clique sur un bloc → éditeur inline ``_BlockEditor``
5. Valide → ``apply_text_edits()`` (redaction + réinsertion) + refresh
6. Clic "✔ Valider" → ``_commit()`` → quitte le mode édition
7. Clic "✘ Annuler" → ``_cancel()`` → quitte sans modifier

Placement flottant (texte / image / signature)
-----------------------------------------------
Plutôt qu'une position fixe, ces actions créent un ``FloatingItem``
via ``viewer.show_floating_item()``. L'utilisateur positionne visuellement
l'élément, valide, et ``_on_placement_commit()`` grave le résultat dans le PDF.

État du mode édition
--------------------
``_btn_commit`` et ``_btn_cancel`` sont masqués par défaut et apparaissent
uniquement quand le mode édition est actif. ``_btn_edit`` change de style
(fond vert semi-transparent) pour indiquer l'état actif.
"""
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QFileDialog
from pdf_equilibrist.ui.widgets import RibbonButton, RibbonGroup
from pdf_equilibrist.ui.dialogs import ask_watermark_text, ask_text_input, show_info, show_error
from pdf_equilibrist.core.document import Document
from pdf_equilibrist.operations.edit import (
    compress, add_watermark, add_text,
    extract_text_blocks, apply_text_edits,
)
import fitz

ACCENT = "#6BBF4E"


class TabModifier(QWidget):
    def __init__(self, document: Document, viewer):
        super().__init__()
        self.document = document
        self.viewer   = viewer
        self._edit_blocks: dict[int, list] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        # ── Groupe Edition texte ─────────────────────────────────────────────
        self._btn_edit = RibbonButton("✎", "Modifier\ntexte")
        self._btn_commit = RibbonButton("✔", "Valider")
        self._btn_commit.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT}22; color:{ACCENT};
                border:1px solid {ACCENT}; border-radius:5px;
                padding:4px 6px 2px 6px; font-size:11px; }}
            QPushButton:hover {{ background:{ACCENT}44; }}
        """)
        self._btn_cancel = RibbonButton("✘", "Annuler")
        self._btn_commit.hide()
        self._btn_cancel.hide()

        grp_edit = RibbonGroup("Édition texte")
        grp_edit.add(self._btn_edit, self._btn_commit, self._btn_cancel)
        layout.addWidget(grp_edit)

        # ── Groupe Insertion ─────────────────────────────────────────────────
        self._btn_text  = RibbonButton("T", "Ajouter\ntexte")
        self._btn_image = RibbonButton("🖼", "Ajouter\nimage")
        grp_ins = RibbonGroup("Insertion")
        grp_ins.add(self._btn_text, self._btn_image)
        layout.addWidget(grp_ins)

        # ── Groupe Mise en page ──────────────────────────────────────────────
        self._btn_wm   = RibbonButton("◈", "Filigrane")
        self._btn_comp = RibbonButton("⊟", "Compres\nser")
        grp_page = RibbonGroup("Mise en page")
        grp_page.add(self._btn_wm, self._btn_comp)
        layout.addWidget(grp_page)

        # ── Groupe OCR ───────────────────────────────────────────────────────
        self._btn_ocr = RibbonButton("🔍", "Rendre\ncherchable")
        grp_ocr = RibbonGroup("OCR")
        grp_ocr.add(self._btn_ocr)
        layout.addWidget(grp_ocr)

        # ── Non câblés ───────────────────────────────────────────────────────
        self._btn_sign = RibbonButton("✒", "Signature\n/ Tampon")
        grp_sign = RibbonGroup("Signature")
        grp_sign.add(self._btn_sign)
        layout.addWidget(grp_sign)

        grp_misc = RibbonGroup("À venir")
        grp_misc.add(RibbonButton("🔗", "Lien"))
        layout.addWidget(grp_misc)
        layout.addStretch()

        self._btn_ocr.clicked.connect(self._run_ocr)
        self._btn_sign.clicked.connect(self._open_signature)
        self._btn_edit.clicked.connect(self._toggle_edit)
        self._btn_commit.clicked.connect(self._commit)
        self._btn_cancel.clicked.connect(self._cancel)
        self._btn_text.clicked.connect(self._add_text)
        self._btn_image.clicked.connect(self._add_image)
        self._btn_wm.clicked.connect(self._watermark)
        self._btn_comp.clicked.connect(self._compress)

    def _toggle_edit(self):
        if not self.document.is_open:
            return
        if self.viewer.is_edit_mode:
            self._cancel()
            return
        self._edit_blocks = {}
        for i in range(len(self.document.fitz_doc)):
            blocks = extract_text_blocks(self.document.fitz_doc, i)
            if blocks:
                self._edit_blocks[i] = blocks
        if not self._edit_blocks:
            show_error(self, "Modifier", "Aucun texte extractible (PDF scanné ?).")
            return
        if self.viewer.enter_edit_mode(self._edit_blocks):
            self._btn_edit.setText(f"✎\nActif")
            self._btn_edit.setStyleSheet(f"""
                QPushButton {{ background:{ACCENT}22; color:{ACCENT};
                    border:1px solid {ACCENT}; border-radius:5px;
                    padding:4px 6px 2px 6px; font-size:11px; }}
            """)
            self._btn_commit.show()
            self._btn_cancel.show()

    def _commit(self):
        self._reset_edit_ui()
        self.viewer.exit_edit_mode()
        show_info(self, "Modifications", "Terminé — Fichier › Enregistrer pour sauvegarder.")

    def _cancel(self):
        self.viewer.exit_edit_mode()
        self._reset_edit_ui()

    def _reset_edit_ui(self):
        self._edit_blocks = {}
        self._btn_edit.setText("✎\nModifier\ntexte")
        self._btn_edit.setStyleSheet("")
        self._btn_commit.hide()
        self._btn_cancel.hide()

    def _add_text(self):
        if not self.document.is_open:
            return
        text = ask_text_input(self, "Ajouter du texte", "Texte à insérer :")
        if not text:
            return
        data = {"type": "text", "text": text,
                "fontsize": 14, "color": (0, 0, 0)}
        self.viewer.show_floating_item(data, self.viewer.current_page_index,
                                       self._on_placement_commit, None)

    def _add_image(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if not path:
            return
        data = {"type": "image", "path": path}
        self.viewer.show_floating_item(data, self.viewer.current_page_index,
                                       self._on_placement_commit, None)

    def _watermark(self):
        if not self.document.is_open:
            return
        text = ask_watermark_text(self)
        if text:
            self.document.checkpoint()
            add_watermark(self.document.fitz_doc, text)
            self.document.changed.emit()

    def _open_signature(self):
        if not self.document.is_open:
            return
        from pdf_equilibrist.ui.signature_dialog import SignatureDialog
        dlg = SignatureDialog(self.document.fitz_doc, self)
        if dlg.exec() != SignatureDialog.DialogCode.Accepted:
            return
        r = dlg.get_result()
        if not r:
            return
        page_idx = r.get("page", 0)
        self.viewer.show_floating_item(r, page_idx,
                                       self._on_placement_commit, None)

    def _on_placement_commit(self, result: dict, page_index: int):
        """Grave l'élément flottant dans le PDF à la position validée."""
        self.document.checkpoint()
        x0, y0, x1, y1 = result["pdf_rect"]
        angle = result.get("angle", 0.0)
        page  = self.document.fitz_doc[page_index]
        rect  = fitz.Rect(x0, y0, x1, y1)

        dtype = result.get("type")
        if dtype == "text":
            page.insert_text(
                fitz.Point(x0, y1),
                result.get("text", ""),
                fontsize=result.get("fontsize", 14),
                color=result.get("color", (0, 0, 0)),
                rotate=int(-angle),
                overlay=True,
            )
        elif dtype == "image":
            page.insert_image(rect, filename=result["path"])
        elif dtype == "stamp":
            color = result.get("color", (0, 0.5, 0))
            text  = result.get("text", "TAMPON")
            page.draw_rect(rect, color=color, fill=None, width=2)
            page.insert_text(
                fitz.Point(x0 + 4, y1 - 6),
                text, fontsize=14, color=color,
                rotate=int(-angle), overlay=True,
            )
        self.document.changed.emit()

    def _run_ocr(self):
        if not self.document.is_open:
            return
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal

        class _OcrWorker(QThread):
            progress = Signal(int, int, str)
            finished = Signal(int)
            error    = Signal(str)

            def __init__(self, fitz_doc):
                super().__init__()
                self._doc = fitz_doc

            def run(self):
                try:
                    from pdf_equilibrist.operations.ocr import apply_ocr_to_pdf
                    n = apply_ocr_to_pdf(self._doc, self.progress.emit)
                    self.finished.emit(n)
                except Exception as e:
                    self.error.emit(str(e))

        dlg = QProgressDialog("Initialisation OCR…", "Annuler", 0, len(self.document.fitz_doc), self)
        dlg.setWindowTitle("OCR — Rendre cherchable")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumWidth(380)
        dlg.show()

        self._ocr_worker = _OcrWorker(self.document.fitz_doc)

        def _on_progress(cur, total, msg):
            dlg.setLabelText(msg)
            dlg.setValue(cur)

        def _on_done(n):
            dlg.close()
            self.document.changed.emit()
            if n == 0:
                show_info(self, "OCR", "Aucune page scannée détectée.\nLe document contient déjà une couche texte.")
            else:
                show_info(self, "OCR", f"{n} page(s) rendue(s) cherchables.\nPensez à enregistrer le document.")

        def _on_error(msg):
            dlg.close()
            show_error(self, "OCR — Erreur", msg)

        self._ocr_worker.progress.connect(_on_progress)
        self._ocr_worker.finished.connect(_on_done)
        self._ocr_worker.error.connect(_on_error)
        dlg.canceled.connect(self._ocr_worker.terminate)
        self._ocr_worker.start()

    def _compress(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer compressé",
            str(self.document.path.with_stem(self.document.path.stem + "_compressé")),
            "PDF (*.pdf)")
        if path:
            try:
                compress(self.document.fitz_doc, Path(path))
                show_info(self, "Compresser", f"Enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))
