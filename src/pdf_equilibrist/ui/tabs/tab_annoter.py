"""
tabs/tab_annoter.py — Onglet "Annoter" du ribbon
==================================================
Annotations PDF standard via ``operations.annotate``.

Marquage (Surligner / Barrer / Souligner)
------------------------------------------
L'utilisateur sélectionne du texte dans le viewer en faisant glisser la
souris. La sélection est mise en évidence (vert semi-transparent) et stockée.
Un clic sur Surligner / Barrer / Souligner applique l'annotation sur les mots
sélectionnés, sur la page courante.

Zone de texte
-------------
Insère une annotation FreeText sur la page courante à position fixe (50, 50).
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout
from pdf_equilibrist.ui.widgets import RibbonButton, RibbonGroup
from pdf_equilibrist.ui.dialogs import ask_text_input, show_error, show_info
from pdf_equilibrist.core.document import Document
from pdf_equilibrist.operations import annotate
import fitz


class TabAnnoter(QWidget):
    def __init__(self, document: Document, viewer):
        super().__init__()
        self.document = document
        self.viewer   = viewer

        # Sélection courante : (page_index, [fitz.Quad])
        self._selection: tuple[int, list] | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        # ── Groupe Marquage texte ────────────────────────────────────────────
        self._btn_hl  = RibbonButton("▬", "Surligner")
        self._btn_str = RibbonButton("S̶", "Barrer")
        self._btn_ul  = RibbonButton("U̲", "Souligner")
        grp_mark = RibbonGroup("Marquage")
        grp_mark.add(self._btn_hl, self._btn_str, self._btn_ul)
        layout.addWidget(grp_mark)

        # ── Groupe Annotation ────────────────────────────────────────────────
        self._btn_tb = RibbonButton("T", "Zone\ntexte")
        grp_annot = RibbonGroup("Annotation")
        grp_annot.add(self._btn_tb)
        layout.addWidget(grp_annot)

        # ── Groupe À venir ───────────────────────────────────────────────────
        grp_soon = RibbonGroup("À venir")
        grp_soon.add(RibbonButton("✏", "Crayon"),
                     RibbonButton("◻", "Forme"),
                     RibbonButton("✒", "Signature"))
        layout.addWidget(grp_soon)

        layout.addStretch()

        self._btn_hl.clicked.connect(lambda: self._annotate("highlight"))
        self._btn_str.clicked.connect(lambda: self._annotate("strikeout"))
        self._btn_ul.clicked.connect(lambda: self._annotate("underline"))
        self._btn_tb.clicked.connect(self._textbox)

        # Écouter la sélection de texte dans le viewer
        viewer.text_selected.connect(self._on_text_selected)

        self._update_buttons()

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _on_text_selected(self, page_index: int, quads: list):
        """Reçoit la sélection glissée dans le viewer."""
        self._selection = (page_index, quads)
        self._update_buttons()

    def _update_buttons(self):
        """Active les boutons de marquage seulement si une sélection existe."""
        has_sel = self._selection is not None and len(self._selection[1]) > 0
        for btn in (self._btn_hl, self._btn_str, self._btn_ul):
            btn.setEnabled(has_sel)
            btn.setToolTip(
                "" if has_sel
                else "Sélectionnez du texte en faisant glisser la souris sur la page"
            )

    # ── Annotation ────────────────────────────────────────────────────────────

    def _annotate(self, kind: str):
        if not self.document.is_open:
            return
        if not self._selection:
            show_info(self, "Annoter",
                      "Sélectionnez d'abord du texte en faisant glisser la souris sur la page.")
            return

        page_index, quads = self._selection
        if page_index >= len(self.document.fitz_doc):
            return

        self.document.checkpoint()
        page = self.document.fitz_doc[page_index]
        {"highlight": annotate.highlight,
         "strikeout": annotate.strikeout,
         "underline": annotate.underline}[kind](page, quads)

        # Effacer la sélection après annotation
        self._selection = None
        self.viewer.clear_selection()
        self._update_buttons()
        self.document.changed.emit()

    def _textbox(self):
        if not self.document.is_open:
            return
        text = ask_text_input(self, "Zone de texte", "Contenu :")
        if not text:
            return
        try:
            page_index = self.viewer.current_page_index
            self.document.checkpoint()
            annotate.add_text_box(self.document.fitz_doc[page_index],
                                  fitz.Rect(50, 50, 250, 100), text)
            self.document.changed.emit()
        except Exception as e:
            show_error(self, "Zone de texte", str(e))
