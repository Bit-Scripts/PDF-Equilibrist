"""
tools/build_docs_pdf.py — Conversion de la documentation Markdown en PDF
=========================================================================
Convertit les 4 fichiers MD de docs/ en PDFs liés entre eux,
avec un sommaire général (INDEX.pdf) contenant des liens vers chaque doc.

Librairies utilisées
--------------------
- ``markdown``  : conversion MD → HTML
- ``PyMuPDF``   : génération des PDFs, insertion des liens croisés

Fichiers générés dans docs/pdf/
---------------------------------
- INDEX.pdf        : sommaire général avec liens vers les 4 docs
- ARCHITECTURE.pdf
- CONTRIBUTING.pdf
- OPERATIONS.pdf
- BUILD.pdf

Usage
-----
    python tools/build_docs_pdf.py

Prérequis
---------
    pip install markdown
    (PyMuPDF déjà installé dans l'environnement Equilibrist)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# ── Constantes de style ───────────────────────────────────────────────────────
ACCENT      = (0.42, 0.75, 0.31)    # #6BBF4E en 0–1
BG_DARK     = (0.12, 0.12, 0.12)    # #1E1E1E
BG_MID      = (0.18, 0.18, 0.18)    # #2D2D2D
FG_WHITE    = (0.94, 0.94, 0.94)    # #F0F0F0
FG_GREY     = (0.67, 0.67, 0.67)    # #AAAAAA
FG_DARK_GREY= (0.35, 0.35, 0.35)    # #575757

PAGE_W  = 595   # A4 portrait
PAGE_H  = 842
MARGIN  = 50
CONTENT_W = PAGE_W - 2 * MARGIN

# Titre → couleur de badge
DOC_COLORS = {
    "ARCHITECTURE": (0.20, 0.47, 0.68),   # bleu
    "CONTRIBUTING": (0.42, 0.75, 0.31),   # vert
    "OPERATIONS":   (0.68, 0.47, 0.20),   # orange
    "BUILD":        (0.68, 0.20, 0.27),   # rouge
    "SECURITE":     (0.55, 0.20, 0.68),   # violet
}

# (numéro, clé, description)
DOCS = [
    (2, "ARCHITECTURE", "Architecture & flux de données"),
    (3, "CONTRIBUTING", "Guide du developpeur"),
    (4, "OPERATIONS",   "Reference des operations PDF"),
    (5, "BUILD",        "Guide de build & deploiement"),
    (6, "SECURITE",     "Analyse de securite — PISO / SSI"),
]


# ── Helpers de rendu PyMuPDF ──────────────────────────────────────────────────

def new_page(doc) -> tuple:
    """Crée une nouvelle page avec fond sombre et retourne (page, y_courant)."""
    import fitz
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, PAGE_H),
                   color=None, fill=BG_DARK)
    return page, MARGIN


def insert_text(page, x: float, y: float, text: str,
                fontsize: float = 11, color=FG_WHITE,
                fontname: str = "helv", bold: bool = False) -> float:
    """Insère du texte et retourne la nouvelle position Y."""
    import fitz
    fn = "hebo" if bold else fontname   # hebo = Helvetica Bold dans fitz
    page.insert_text(
        fitz.Point(x, y), text,
        fontname=fn, fontsize=fontsize, color=color
    )
    return y + fontsize * 1.4


def draw_hline(page, y: float, color=FG_DARK_GREY, width: float = 0.5):
    """Dessine une ligne horizontale."""
    import fitz
    page.draw_line(fitz.Point(MARGIN, y), fitz.Point(PAGE_W - MARGIN, y),
                   color=color, width=width)


def insert_wrapped(page, x: float, y: float, text: str,
                   fontsize: float = 10, color=FG_WHITE,
                   max_width: float = CONTENT_W) -> float:
    """Insère du texte avec retour à la ligne automatique."""
    import fitz
    # Estimation de la largeur : ~0.55 * fontsize par caractère (Helvetica)
    chars_per_line = max(1, int(max_width / (fontsize * 0.55)))
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if len(test) <= chars_per_line:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        page.insert_text(fitz.Point(x, y), line,
                         fontname="helv", fontsize=fontsize, color=color)
        y += fontsize * 1.5
    return y


def badge(page, x: float, y: float, label: str,
          color: tuple, width: float = 90) -> None:
    """Dessine un badge coloré avec label."""
    import fitz
    h = 16
    r = fitz.Rect(x, y - h + 3, x + width, y + 3)
    page.draw_rect(r, color=None, fill=color + (0.25,)
                   if len(color) == 3 else color, width=0)
    page.draw_rect(r, color=color, fill=None, width=1)
    cx = x + width / 2 - len(label) * 3
    page.insert_text(fitz.Point(cx, y - 2), label,
                     fontname="helv", fontsize=9, color=color)


# ── Parsing Markdown simplifié ────────────────────────────────────────────────

def parse_md(md_path: Path) -> list[dict]:
    """
    Parse un fichier Markdown et retourne une liste de blocs :
    {'type': 'h1'|'h2'|'h3'|'h4'|'p'|'code'|'hr'|'nav'|'li', 'text': str}
    """
    blocks = []
    in_code = False
    code_buf = []

    for raw in md_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()

        # Bloc de code
        if line.startswith("```"):
            if in_code:
                blocks.append({"type": "code", "text": "\n".join(code_buf)})
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        # Navigation retour ← [Index](1.INDEX.md) · ...
        if line.startswith("> ←") or line.startswith("> <-") or (
                line.startswith(">") and "[Index]" in line):
            nav_links = []
            for m in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', line):
                label = m.group(1)
                href  = m.group(2)
                # Convertir .md -> .pdf pour le lien GoToR
                pdf_file = Path(href).name.replace(".md", ".pdf")
                nav_links.append((label, pdf_file))
            blocks.append({"type": "nav_links", "links": nav_links})
            continue

        # Lignes de tableau
        if line.startswith("| ") or (line.startswith("|") and "|" in line[1:]):
            cols = [c.strip() for c in line.split("|") if c.strip()]
            # Ignorer les lignes de séparateur |---|---|
            if all(re.match(r"^[-:]+$", c) for c in cols):
                continue
            if cols:
                blocks.append({"type": "table_row", "cols": cols})
            continue

        # Titres
        if line.startswith("#### "):
            blocks.append({"type": "h4", "text": line[5:]})
        elif line.startswith("### "):
            blocks.append({"type": "h3", "text": line[4:]})
        elif line.startswith("## "):
            blocks.append({"type": "h2", "text": line[3:]})
        elif line.startswith("# "):
            blocks.append({"type": "h1", "text": line[2:]})
        elif line.startswith("---"):
            blocks.append({"type": "hr", "text": ""})
        elif line.startswith("- ") or line.startswith("* "):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1",
                          re.sub(r"`(.+?)`", r"\1", line[2:]))
            blocks.append({"type": "li", "text": text})
        elif line.strip():
            # Paragraphe : nettoyer le markdown inline
            text = re.sub(r"\*\*(.+?)\*\*", r"\1",
                          re.sub(r"`(.+?)`", r"\1",
                                 re.sub(r"\[(.+?)\]\(.+?\)", r"\1", line)))
            blocks.append({"type": "p", "text": text})
        else:
            blocks.append({"type": "blank", "text": ""})

    return blocks


# ── Rendu d'un document MD ────────────────────────────────────────────────────

def render_doc(fitz_doc, blocks: list[dict],
               title: str, color: tuple) -> None:
    """Rend tous les blocs d'un document Markdown dans fitz_doc."""
    import fitz

    page, y = new_page(fitz_doc)

    # En-tête du document
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 70), color=None, fill=BG_MID)
    page.insert_text(fitz.Point(MARGIN, 30),
                     "PDF Equilibrist",
                     fontname="helv", fontsize=10, color=FG_GREY)
    page.insert_text(fitz.Point(MARGIN, 52),
                     title,
                     fontname="hebo", fontsize=18, color=color)
    # Badge couleur sur le côté droit
    page.draw_rect(fitz.Rect(PAGE_W - 8, 0, PAGE_W, 70),
                   color=None, fill=color)
    y = 90

    for block in blocks:
        btype = block["type"]
        text  = block.get("text", "")

        # Vérifier l'espace restant — nouvelle page si besoin
        if y > PAGE_H - MARGIN - 20:
            page, y = new_page(fitz_doc)
            # En-tête de continuation
            page.draw_rect(fitz.Rect(0, 0, PAGE_W, 28),
                           color=None, fill=BG_MID)
            page.insert_text(fitz.Point(MARGIN, 20), title,
                             fontname="helv", fontsize=9, color=FG_GREY)
            page.draw_rect(fitz.Rect(PAGE_W - 8, 0, PAGE_W, 28),
                           color=None, fill=color)
            y = 40

        if btype == "h1":
            y += 6
            page.draw_rect(fitz.Rect(MARGIN, y - 14, PAGE_W - MARGIN, y + 6),
                           color=None, fill=(color[0]*0.3, color[1]*0.3, color[2]*0.3))
            page.insert_text(fitz.Point(MARGIN + 4, y),
                             text, fontname="hebo", fontsize=15, color=color)
            y += 20

        elif btype == "h2":
            y += 10
            page.draw_line(fitz.Point(MARGIN, y - 4),
                           fitz.Point(MARGIN + 4, y - 4),
                           color=color, width=3)
            page.insert_text(fitz.Point(MARGIN + 10, y),
                             text, fontname="hebo", fontsize=13, color=FG_WHITE)
            y += 8
            draw_hline(page, y, color=color, width=0.5)
            y += 8

        elif btype == "h3":
            y += 6
            page.insert_text(fitz.Point(MARGIN, y),
                             text, fontname="hebo", fontsize=11, color=ACCENT)
            y += 16

        elif btype == "h4":
            page.insert_text(fitz.Point(MARGIN + 8, y),
                             text, fontname="hebo", fontsize=10, color=FG_GREY)
            y += 14

        elif btype == "p":
            y = insert_wrapped(page, MARGIN, y, text, fontsize=10, color=FG_WHITE)
            y += 2

        elif btype == "li":
            page.draw_circle(fitz.Point(MARGIN + 6, y - 3), 2,
                             color=color, fill=color)
            y = insert_wrapped(page, MARGIN + 16, y, text,
                               fontsize=10, color=FG_WHITE,
                               max_width=CONTENT_W - 16)

        elif btype == "code":
            lines = text.split("\n")
            code_h = len(lines) * 13 + 10
            # Fond de code
            page.draw_rect(fitz.Rect(MARGIN, y, PAGE_W - MARGIN, y + code_h),
                           color=None,
                           fill=(0.15, 0.15, 0.15))
            page.draw_rect(fitz.Rect(MARGIN, y, MARGIN + 3, y + code_h),
                           color=None, fill=color)
            cy = y + 8
            for cl in lines:
                page.insert_text(fitz.Point(MARGIN + 8, cy), cl,
                                 fontname="cour", fontsize=8,
                                 color=(0.75, 0.92, 0.65))
                cy += 13
            y += code_h + 6

        elif btype == "table_row":
            cols     = block.get("cols", [block.get("text", "")])
            n        = max(len(cols), 1)
            col_w    = CONTENT_W / n
            row_h    = 16
            is_first = (blocks.index(block) == 0 or
                        blocks[blocks.index(block) - 1].get("type") != "table_row")
            fill = (0.20, 0.20, 0.20) if is_first else (0.16, 0.16, 0.16)
            txt_color = color if is_first else FG_WHITE

            page.draw_rect(fitz.Rect(MARGIN, y - 12, PAGE_W - MARGIN, y + 4),
                           color=None, fill=fill)
            for ci, col in enumerate(cols):
                cx = MARGIN + 4 + ci * col_w
                page.insert_text(fitz.Point(cx, y),
                                 col[:40],   # tronquer si trop long
                                 fontname="hebo" if is_first else "helv",
                                 fontsize=9, color=txt_color)
                if ci < n - 1:
                    page.draw_line(
                        fitz.Point(MARGIN + (ci + 1) * col_w, y - 12),
                        fitz.Point(MARGIN + (ci + 1) * col_w, y + 4),
                        color=FG_DARK_GREY, width=0.4)
            y += row_h

        elif btype == "hr":
            draw_hline(page, y, color=FG_DARK_GREY)
            y += 8

        elif btype == "nav_links":
            # Ligne de navigation retour avec liens GoToR cliquables
            import fitz as _fitz
            links = block.get("links", [])
            x = MARGIN
            page.insert_text(fitz.Point(x, y), "<-",
                             fontname="helv", fontsize=8, color=FG_DARK_GREY)
            x += 16
            for i, (label, pdf_file) in enumerate(links):
                lw = len(label) * 5.5 + 4
                link_rect = fitz.Rect(x, y - 9, x + lw, y + 2)
                page.insert_text(fitz.Point(x, y), label,
                                 fontname="helv", fontsize=8, color=ACCENT)
                # Lien GoToR relatif vers le PDF correspondant
                page.insert_link({
                    "kind": _fitz.LINK_GOTOR,
                    "from": link_rect,
                    "file": pdf_file,
                    "page": 0,
                })
                x += lw
                if i < len(links) - 1:
                    page.insert_text(fitz.Point(x, y), " · ",
                                     fontname="helv", fontsize=8,
                                     color=FG_DARK_GREY)
                    x += 12
            draw_hline(page, y + 5, color=FG_DARK_GREY, width=0.3)
            y += 18

        elif btype == "blank":
            y += 5


# ── INDEX — sommaire général ──────────────────────────────────────────────────

def render_index(fitz_doc, pdf_dir: Path) -> None:
    """Génère la page INDEX avec liens cliquables vers chaque document."""
    import fitz

    page, y = new_page(fitz_doc)

    # En-tête
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 90), color=None, fill=BG_MID)
    # Logo / nom
    page.insert_text(fitz.Point(MARGIN, 35),
                     "PDF Equilibrist",
                     fontname="hebo", fontsize=22, color=ACCENT)
    page.insert_text(fitz.Point(MARGIN, 60),
                     "Documentation technique — Index",
                     fontname="helv", fontsize=12, color=FG_GREY)
    draw_hline(page, 90, color=ACCENT, width=1.5)
    y = 115

    page.insert_text(fitz.Point(MARGIN, y),
                     "Cette documentation couvre l'architecture, le développement,",
                     fontname="helv", fontsize=10, color=FG_WHITE)
    y += 15
    page.insert_text(fitz.Point(MARGIN, y),
                     "les opérations PDF disponibles et le processus de build.",
                     fontname="helv", fontsize=10, color=FG_WHITE)
    y += 35

    # Cartes de navigation
    for num, doc_name, doc_desc in DOCS:
        color    = DOC_COLORS.get(doc_name, ACCENT)
        pdf_name = f"{num}.{doc_name}.pdf"

        card_h    = 70
        card_rect = fitz.Rect(MARGIN, y, PAGE_W - MARGIN, y + card_h)

        page.draw_rect(card_rect, color=None, fill=(0.15, 0.15, 0.15))
        page.draw_rect(card_rect, color=color, fill=None, width=1)

        # Barre de couleur + numero
        page.draw_rect(fitz.Rect(MARGIN, y, MARGIN + 28, y + card_h),
                       color=None, fill=color)
        page.insert_text(fitz.Point(MARGIN + 8, y + 42),
                         str(num), fontname="hebo", fontsize=16,
                         color=(0.08, 0.08, 0.08))

        # Titre + description + nom fichier
        page.insert_text(fitz.Point(MARGIN + 36, y + 22),
                         doc_name, fontname="hebo", fontsize=14, color=color)
        page.insert_text(fitz.Point(MARGIN + 36, y + 40),
                         doc_desc, fontname="helv", fontsize=10, color=FG_WHITE)
        page.insert_text(fitz.Point(MARGIN + 36, y + 56),
                         f"-> {pdf_name}",
                         fontname="helv", fontsize=9, color=FG_DARK_GREY)

        # LINK_GOTOR = GoTo Remote = standard PDF cross-document
        # Chemin RELATIF pour qu'Acrobat Reader accepte le lien
        link = {
            "kind": fitz.LINK_GOTOR,
            "from": card_rect,
            "file": pdf_name,   # relatif : meme dossier que INDEX.pdf
            "page": 0,
        }
        page.insert_link(link)

        y += card_h + 12

    # Pied de page
    y = PAGE_H - 40
    draw_hline(page, y - 10, color=FG_DARK_GREY)
    page.insert_text(fitz.Point(MARGIN, y),
                     "Genere automatiquement par tools/build_docs_pdf.py",
                     fontname="helv", fontsize=8, color=FG_DARK_GREY)
    from datetime import date
    page.insert_text(fitz.Point(PAGE_W - MARGIN - 60, y),
                     str(date.today()), fontname="helv",
                     fontsize=8, color=FG_DARK_GREY)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import fitz

    root    = Path(__file__).parent.parent
    docs_md = root / "docs"
    pdf_dir = docs_md / "pdf"
    pdf_dir.mkdir(exist_ok=True)

    print("Generation de la documentation PDF...")

    # 1. Convertir chaque MD en PDF (noms numerotes)
    for num, doc_name, doc_desc in DOCS:
        md_path  = docs_md / f"{num}.{doc_name}.md"
        pdf_path = pdf_dir / f"{num}.{doc_name}.pdf"

        if not md_path.exists():
            print(f"  --  {md_path.name} introuvable - ignore")
            continue

        blocks   = parse_md(md_path)
        fitz_doc = fitz.open()
        color    = DOC_COLORS.get(doc_name, ACCENT)
        render_doc(fitz_doc, blocks, doc_desc, color)
        fitz_doc.save(str(pdf_path))
        fitz_doc.close()
        print(f"  OK  {pdf_path.name}  ({pdf_path.stat().st_size // 1024} Ko)")

    # 2. Generer l'INDEX (1.INDEX.pdf) avec liens GoToR relatifs
    index_path = pdf_dir / "1.INDEX.pdf"
    fitz_doc = fitz.open()
    render_index(fitz_doc, pdf_dir)
    fitz_doc.save(str(index_path))
    fitz_doc.close()
    print(f"  OK  {index_path.name}  ({index_path.stat().st_size // 1024} Ko)")

    print(f"\nDocumentation generee dans : {pdf_dir}")
    print("   Ouvrez 1.INDEX.pdf pour naviguer entre les documents.")


if __name__ == "__main__":
    main()
