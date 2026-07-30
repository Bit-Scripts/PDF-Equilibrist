"""Dialogue de traitement par lot."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QLineEdit,
    QFileDialog, QProgressBar, QTextEdit, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

DIALOG_STYLE = """
QDialog  { background: #2D2D2D; color: #F0F0F0; min-width: 580px; }
QLabel   { color: #F0F0F0; }
QListWidget {
    background: #1E1E1E; color: #F0F0F0;
    border: 1px solid #3A3A3A; border-radius: 4px;
}
QComboBox, QLineEdit {
    background: #1E1E1E; color: #F0F0F0;
    border: 1px solid #3A3A3A; border-radius: 4px; padding: 4px 8px;
}
QComboBox QAbstractItemView { background: #2D2D2D; color: #F0F0F0; }
QProgressBar {
    background: #1E1E1E; border: 1px solid #3A3A3A;
    border-radius: 4px; text-align: center; color: #F0F0F0;
}
QProgressBar::chunk { background: #6BBF4E; border-radius: 3px; }
QTextEdit {
    background: #1E1E1E; color: #AAAAAA;
    border: 1px solid #3A3A3A; border-radius: 4px;
    font-family: "Consolas"; font-size: 11px;
}
QPushButton {
    background: #3A3A3A; color: #F0F0F0;
    border: 1px solid #4A4A4A; border-radius: 4px; padding: 5px 14px;
}
QPushButton:hover { background: #4A4A4A; }
QPushButton:disabled { color: #555555; }
QPushButton#primary {
    background: #6BBF4E; color: #1E1E1E; font-weight: bold; border: none;
}
QPushButton#primary:hover { background: #7ED45F; }
"""

# (clé interne stable, texte source à traduire) — la clé sert de point de
# comparaison dans _Worker/_on_op_changed pour ne pas dépendre du texte
# affiché, qui change selon la langue active.
OPERATIONS = [
    ("compress",     "Compresser"),
    ("watermark",    "Ajouter un filigrane"),
    ("to_word",      "Convertir en Word (.docx)"),
    ("to_excel",     "Convertir en Excel (.xlsx)"),
    ("to_powerpoint","Convertir en PowerPoint (.pptx)"),
    ("to_images",    "Convertir en Images (PNG)"),
    ("merge",        "Fusionner en un seul PDF"),
]


class _Worker(QThread):
    progress = pyqtSignal(int, str)   # (index, message)
    finished = pyqtSignal(int, int)   # (ok, errors)

    def __init__(self, files: list[str], operation: str,
                 output_dir: str, watermark_text: str = ""):
        super().__init__()
        self.files         = files
        self.operation     = operation
        self.output_dir    = Path(output_dir)
        self.watermark_text = watermark_text

    def run(self):
        import fitz
        from pdf_equilibrist.operations.edit    import compress, add_watermark
        from pdf_equilibrist.operations.convert import (
            to_word, to_excel, to_powerpoint, to_images
        )

        ok = errors = 0
        files = self.files

        # Cas spécial : fusion
        if self.operation == "merge":
            try:
                merged = fitz.open()
                for f in files:
                    src = fitz.open(f)
                    merged.insert_pdf(src)
                    src.close()
                out = self.output_dir / self.tr("fusionné.pdf")
                merged.save(str(out))
                merged.close()
                self.progress.emit(len(files), self.tr("✓ Fusionné → {0}").format(out.name))
                ok = len(files)
            except Exception as e:
                self.progress.emit(len(files), self.tr("✗ Erreur fusion : {0}").format(e))
                errors = 1
            self.finished.emit(ok, errors)
            return

        for i, f in enumerate(files):
            name = Path(f).stem
            try:
                doc = fitz.open(f)

                if self.operation == "compress":
                    out = self.output_dir / f"{name}_compressé.pdf"
                    compress(doc, out)

                elif self.operation == "watermark":
                    add_watermark(doc, self.watermark_text or "CONFIDENTIEL")
                    out = self.output_dir / f"{name}_filigrane.pdf"
                    doc.save(str(out))

                elif self.operation == "to_word":
                    out = self.output_dir / f"{name}.docx"
                    to_word(doc, Path(f), out)

                elif self.operation == "to_excel":
                    out = self.output_dir / f"{name}.xlsx"
                    to_excel(doc, out)

                elif self.operation == "to_powerpoint":
                    out = self.output_dir / f"{name}.pptx"
                    to_powerpoint(doc, out)

                elif self.operation == "to_images":
                    out_dir = self.output_dir / name
                    to_images(doc, out_dir, fmt="png")
                    out = out_dir

                doc.close()
                self.progress.emit(i + 1, self.tr("✓ {0}").format(Path(f).name))
                ok += 1

            except Exception as e:
                self.progress.emit(i + 1, self.tr("✗ {0} : {1}").format(Path(f).name, e))
                errors += 1

        self.finished.emit(ok, errors)


class BatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Traitement par lot"))
        self.setStyleSheet(DIALOG_STYLE)
        self._worker: _Worker | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Fichiers ──────────────────────────────────────────────────────────
        layout.addWidget(QLabel(self.tr("Fichiers PDF à traiter :")))
        self._file_list = QListWidget()
        self._file_list.setFixedHeight(140)
        layout.addWidget(self._file_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton(self.tr("➕  Ajouter des fichiers…"))
        btn_add.clicked.connect(self._add_files)
        btn_clear = QPushButton(self.tr("🗑  Vider la liste"))
        btn_clear.clicked.connect(self._file_list.clear)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3A3A3A;")
        layout.addWidget(sep)

        # ── Opération ────────────────────────────────────────────────────────
        layout.addWidget(QLabel(self.tr("Opération :")))
        self._combo_op = QComboBox()
        for key, label in OPERATIONS:
            self._combo_op.addItem(self.tr(label), key)
        self._combo_op.currentIndexChanged.connect(self._on_op_changed)
        layout.addWidget(self._combo_op)

        self._wm_label = QLabel(self.tr("Texte du filigrane :"))
        self._wm_input = QLineEdit("CONFIDENTIEL")
        self._wm_label.hide()
        self._wm_input.hide()
        layout.addWidget(self._wm_label)
        layout.addWidget(self._wm_input)

        # ── Dossier de sortie ─────────────────────────────────────────────────
        layout.addWidget(QLabel(self.tr("Dossier de sortie :")))
        out_row = QHBoxLayout()
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText(self.tr("Choisir un dossier…"))
        btn_out = QPushButton("📁")
        btn_out.setFixedWidth(36)
        btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self._out_edit)
        out_row.addWidget(btn_out)
        layout.addLayout(out_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #3A3A3A;")
        layout.addWidget(sep2)

        # ── Progression ───────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(110)
        layout.addWidget(self._log)

        # ── Boutons ───────────────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.addStretch()
        self._btn_close = QPushButton(self.tr("Fermer"))
        self._btn_close.clicked.connect(self.reject)
        self._btn_run = QPushButton(self.tr("▶  Lancer le traitement"))
        self._btn_run.setObjectName("primary")
        self._btn_run.clicked.connect(self._run)
        action_row.addWidget(self._btn_close)
        action_row.addWidget(self._btn_run)
        layout.addLayout(action_row)

        self._on_op_changed(self._combo_op.currentIndex())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Ajouter des PDFs"), "", self.tr("Fichiers PDF (*.pdf)"))
        for f in files:
            if not self._file_list.findItems(f, Qt.MatchFlag.MatchExactly):
                self._file_list.addItem(QListWidgetItem(f))

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, self.tr("Dossier de sortie"))
        if d:
            self._out_edit.setText(d)

    def _on_op_changed(self, index: int):
        show_wm = self._combo_op.itemData(index) == "watermark"
        self._wm_label.setVisible(show_wm)
        self._wm_input.setVisible(show_wm)

    def _run(self):
        files = [self._file_list.item(i).text()
                 for i in range(self._file_list.count())]
        if not files:
            self._log.append(self.tr("⚠ Aucun fichier sélectionné."))
            return
        out = self._out_edit.text().strip()
        if not out:
            self._log.append(self.tr("⚠ Choisissez un dossier de sortie."))
            return

        self._btn_run.setEnabled(False)
        self._progress.setMaximum(len(files))
        self._progress.setValue(0)
        self._log.clear()

        self._worker = _Worker(
            files, self._combo_op.currentData(), out,
            self._wm_input.text()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, n: int, msg: str):
        self._progress.setValue(n)
        self._log.append(msg)

    def _on_finished(self, ok: int, errors: int):
        self._log.append(
            self.tr("\n── Terminé : {0} réussi(s), {1} erreur(s) ──").format(ok, errors))
        self._btn_run.setEnabled(True)
        self._btn_close.setText(self.tr("Fermer"))
