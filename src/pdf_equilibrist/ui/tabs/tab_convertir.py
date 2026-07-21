"""
tabs/tab_convertir.py — Onglet "Convertir" du ribbon
======================================================
Conversions de format depuis et vers le PDF.

Conversions PDF → autre format
--------------------------------
Chaque bouton ouvre un dialogue "Enregistrer sous" puis appelle
la fonction correspondante de ``operations.convert`` :
- Word      : ``to_word()``      via pdf2docx
- Excel     : ``to_excel()``     via pdfplumber + openpyxl
- PowerPoint: ``to_powerpoint()`` via python-pptx (image par slide)
- Image     : ``to_images()``    via PyMuPDF (un fichier par page)

Conversion Office → PDF
------------------------
``_office_to_pdf()`` appelle ``detect_office_engine()`` pour déterminer
si MS Office ou LibreOffice est disponible, puis lance la conversion.
Supporte la sélection multiple de fichiers et affiche un rapport
de succès/erreurs par fichier.

Traitement par lot
-------------------
Ouvre ``BatchDialog`` qui permet de sélectionner N PDFs, choisir
une opération et un dossier de sortie. Le traitement tourne dans
un ``QThread`` (``_Worker``) pour ne pas bloquer l'UI.
"""
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QFileDialog
from pdf_equilibrist.ui.widgets import RibbonButton, RibbonGroup
from pdf_equilibrist.ui.dialogs import ask_image_format, show_info, show_error
from pdf_equilibrist.core.document import Document
from pdf_equilibrist.operations import convert
from pdf_equilibrist.operations.convert import office_to_pdf, detect_office_engine


class TabConvertir(QWidget):
    def __init__(self, document: Document):
        super().__init__()
        self.document = document

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        # ── Groupe PDF → Office ──────────────────────────────────────────────
        self._btn_word = RibbonButton("W", "Word")
        self._btn_xl   = RibbonButton("X", "Excel")
        self._btn_ppt  = RibbonButton("P", "Power\nPoint")
        grp_office = RibbonGroup("PDF → Office")
        grp_office.add(self._btn_word, self._btn_xl, self._btn_ppt)
        layout.addWidget(grp_office)

        # ── Groupe PDF → Image ───────────────────────────────────────────────
        self._btn_img = RibbonButton("🖼", "Image")
        grp_img = RibbonGroup("PDF → Image")
        grp_img.add(self._btn_img)
        layout.addWidget(grp_img)

        # ── Groupe PDF → Markdown ────────────────────────────────────────────
        self._btn_md = RibbonButton("M↓", "Markdown")
        grp_md = RibbonGroup("PDF → Texte")
        grp_md.add(self._btn_md)
        layout.addWidget(grp_md)

        # ── Groupe OCR → ... ─────────────────────────────────────────────────
        self._btn_ocr_pdf  = RibbonButton("🔍📄", "OCR →\nPDF")
        self._btn_ocr_md   = RibbonButton("🔍M↓", "OCR →\nMarkdown")
        self._btn_ocr_word = RibbonButton("🔍W",  "OCR →\nWord")
        self._btn_ocr_xl   = RibbonButton("🔍X",  "OCR →\nExcel")
        grp_ocr = RibbonGroup("OCR → ...")
        grp_ocr.add(self._btn_ocr_pdf, self._btn_ocr_md, self._btn_ocr_word, self._btn_ocr_xl)
        layout.addWidget(grp_ocr)

        # ── Groupe → PDF ─────────────────────────────────────────────────────
        self._btn_office2pdf = RibbonButton("🏢", "Office\nen PDF")
        self._btn_img2pdf    = RibbonButton("📄", "Image\nen PDF")
        grp_topdf = RibbonGroup("→ PDF")
        grp_topdf.add(self._btn_office2pdf, self._btn_img2pdf)
        layout.addWidget(grp_topdf)

        # ── Traitement par lot ────────────────────────────────────────────────
        self._btn_batch = RibbonButton("⚙", "Traitement\npar lot")
        grp_batch = RibbonGroup("Lot")
        grp_batch.add(self._btn_batch)
        layout.addWidget(grp_batch)

        layout.addStretch()

        self._btn_batch.clicked.connect(self._batch)
        self._btn_md.clicked.connect(self._to_markdown)
        self._btn_ocr_pdf.clicked.connect(self._ocr_to_pdf)
        self._btn_ocr_md.clicked.connect(self._ocr_to_markdown)
        self._btn_ocr_word.clicked.connect(self._ocr_to_word)
        self._btn_ocr_xl.clicked.connect(self._ocr_to_excel)
        self._btn_word.clicked.connect(self._to_word)
        self._btn_xl.clicked.connect(self._to_excel)
        self._btn_ppt.clicked.connect(self._to_ppt)
        self._btn_img.clicked.connect(self._to_images)
        self._btn_office2pdf.clicked.connect(self._office_to_pdf)
        self._btn_img2pdf.clicked.connect(self._image_to_pdf)

    def _to_markdown(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Vers Markdown",
            str(self.document.path.with_suffix(".md")), "Markdown (*.md)")
        if path:
            try:
                convert.to_markdown(self.document.fitz_doc, Path(path))
                show_info(self, "Conversion", f"Markdown enregistré :\n{path}")
            except ValueError as e:
                show_error(self, "Conversion impossible", str(e))
            except Exception as e:
                show_error(self, "Erreur", str(e))

    # ── Helpers OCR ──────────────────────────────────────────────────────────

    def _run_ocr_then(self, title: str, on_done_cb):
        """
        Lance l'OCR sur le document courant dans un QThread avec barre de progression,
        puis appelle ``on_done_cb()`` si l'OCR réussit.

        ``on_done_cb`` reçoit le fitz_doc (maintenant enrichi de texte) et peut
        lancer n'importe quelle conversion dessus.
        """
        if not self.document.is_open:
            return

        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt, QThread
        from PyQt6.QtCore import pyqtSignal as Signal

        class _OcrWorker(QThread):
            progress = Signal(int, int, str)
            finished = Signal()
            error    = Signal(str)

            def __init__(self, fitz_doc):
                super().__init__()
                self._doc = fitz_doc

            def run(self):
                try:
                    from pdf_equilibrist.operations.ocr import apply_ocr_to_pdf
                    apply_ocr_to_pdf(self._doc, self.progress.emit)
                    self.finished.emit()
                except Exception as e:
                    self.error.emit(str(e))

        n = len(self.document.fitz_doc)
        dlg = QProgressDialog("Initialisation OCR…", "Annuler", 0, n, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumWidth(380)
        dlg.show()

        worker = _OcrWorker(self.document.fitz_doc)
        self._ocr_worker_ref = worker   # éviter le GC

        def _on_progress(cur, total, msg):
            dlg.setLabelText(msg)
            dlg.setValue(cur)

        def _on_done():
            dlg.close()
            on_done_cb(self.document.fitz_doc)

        def _on_error(msg):
            dlg.close()
            show_error(self, "OCR — Erreur", msg)

        worker.progress.connect(_on_progress)
        worker.finished.connect(_on_done)
        worker.error.connect(_on_error)
        dlg.canceled.connect(worker.terminate)
        worker.start()

    def _ocr_to_pdf(self):
        if not self.document.is_open:
            return
        stem = self.document.path.stem
        path, _ = QFileDialog.getSaveFileName(
            self, "OCR → PDF cherchable",
            str(self.document.path.with_stem(stem + "_OCR")), "PDF (*.pdf)")
        if not path:
            return

        def _convert(fitz_doc):
            try:
                import tempfile, shutil
                # Sauvegarder le fitz_doc enrichi via fichier temp (chemin réseau safe)
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                fitz_doc.save(str(tmp_path))
                shutil.copy2(tmp_path, path)
                tmp_path.unlink(missing_ok=True)
                show_info(self, "OCR → PDF", f"PDF cherchable enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

        self._run_ocr_then("OCR → PDF", _convert)

    def _ocr_to_markdown(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "OCR → Markdown",
            str(self.document.path.with_suffix(".md")) if self.document.is_open else "",
            "Markdown (*.md)")
        if not path:
            return

        def _convert(fitz_doc):
            try:
                from pdf_equilibrist.operations.ocr import ocr_to_markdown
                ocr_to_markdown(fitz_doc, Path(path))
                show_info(self, "OCR → Markdown", f"Markdown enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

        self._run_ocr_then("OCR → Markdown", _convert)

    def _ocr_to_word(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "OCR → Word",
            str(self.document.path.with_suffix(".docx")), "Word (*.docx)")
        if not path:
            return

        def _convert(fitz_doc):
            try:
                convert.to_word(fitz_doc, self.document.path, Path(path))
                show_info(self, "OCR → Word", f"Word enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

        self._run_ocr_then("OCR → Word", _convert)

    def _ocr_to_excel(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "OCR → Excel",
            str(self.document.path.with_suffix(".xlsx")), "Excel (*.xlsx)")
        if not path:
            return

        def _convert(fitz_doc):
            try:
                convert.to_excel(fitz_doc, Path(path))
                show_info(self, "OCR → Excel", f"Excel enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

        self._run_ocr_then("OCR → Excel", _convert)

    def _to_word(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Vers Word",
            str(self.document.path.with_suffix(".docx")), "Word (*.docx)")
        if path:
            try:
                convert.to_word(self.document.fitz_doc, self.document.path, Path(path))
                show_info(self, "Conversion", f"Word enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _to_excel(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Vers Excel",
            str(self.document.path.with_suffix(".xlsx")), "Excel (*.xlsx)")
        if path:
            try:
                convert.to_excel(self.document.fitz_doc, Path(path))
                show_info(self, "Conversion", f"Excel enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _to_ppt(self):
        if not self.document.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Vers PowerPoint",
            str(self.document.path.with_suffix(".pptx")), "PowerPoint (*.pptx)")
        if path:
            try:
                convert.to_powerpoint(self.document.fitz_doc, Path(path))
                show_info(self, "Conversion", f"PowerPoint enregistré :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _to_images(self):
        if not self.document.is_open:
            return
        fmt = ask_image_format(self)
        if not fmt:
            return
        output_dir = QFileDialog.getExistingDirectory(self, "Dossier de sortie")
        if output_dir:
            try:
                paths = convert.to_images(self.document.fitz_doc,
                                          Path(output_dir), fmt=fmt)
                show_info(self, "Conversion",
                          f"{len(paths)} image(s) dans :\n{output_dir}")
            except Exception as e:
                show_error(self, "Erreur", str(e))

    def _batch(self):
        from pdf_equilibrist.ui.batch_dialog import BatchDialog
        dlg = BatchDialog(self)
        dlg.exec()

    def _office_to_pdf(self):
        engine = detect_office_engine()
        if engine is None:
            show_error(self, "Office en PDF",
                       "Aucun moteur trouvé.\n"
                       "Installez Microsoft Office ou LibreOffice.")
            return
        label = "Microsoft Office" if engine == "msoffice" else "LibreOffice"

        files, _ = QFileDialog.getOpenFileNames(
            self, "Fichiers Office à convertir", "",
            "Office (*.docx *.xlsx *.pptx *.doc *.xls *.ppt *.odt *.ods *.odp)"
        )
        if not files:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Dossier de sortie")
        if not out_dir:
            return

        errors, ok = [], 0
        for f in files:
            src  = Path(f)
            dest = Path(out_dir) / (src.stem + ".pdf")
            try:
                office_to_pdf(src, dest)
                ok += 1
            except Exception as e:
                errors.append(f"{src.name} : {e}")

        msg = f"Moteur : {label}\n{ok} fichier(s) converti(s)."
        if errors:
            msg += "\n\nErreurs :\n" + "\n".join(errors)
            show_error(self, "Office en PDF", msg)
        else:
            show_info(self, "Office en PDF", msg)

    def _image_to_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Choisir des images", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if not files:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le PDF", "", "PDF (*.pdf)")
        if path:
            try:
                convert.image_to_pdf([Path(f) for f in files], Path(path))
                show_info(self, "Conversion", f"PDF créé :\n{path}")
            except Exception as e:
                show_error(self, "Erreur", str(e))
