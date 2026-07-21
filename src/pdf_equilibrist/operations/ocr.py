"""
operations/ocr.py — OCR via PaddleOCR
======================================
Reconnaissance de texte sur les pages scannées (images) d'un PDF.

Deux usages
-----------
1. **PDF searchable** (``apply_ocr_to_pdf``) :
   Réinjecte le texte reconnu comme couche invisible (``render_mode=3``)
   au-dessus de l'image. Le PDF reste visuellement identique mais devient
   cherchable / copiable / extractible par PyMuPDF.

2. **Export Markdown** (``ocr_to_markdown``) :
   Extrait le texte de toutes les pages (scannées ou non) et génère un .md.
   Les pages avec une couche texte existante utilisent PyMuPDF directement ;
   les pages image passent par PaddleOCR.

Détection page scannée
-----------------------
Une page est considérée « image » si ``page.get_text().strip()`` est vide
et qu'elle contient au moins une image (``page.get_images()``).

Dépendances
-----------
- ``paddlepaddle``  : moteur d'inférence Paddle (CPU)
- ``paddleocr``     : modèles PP-OCRv6 + orientation
- ``PyMuPDF``       : rastérisation + réinsertion couche texte
- ``Pillow``        : conversion pixmap → format PaddleOCR
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable
import fitz


# ── Résolution de rastérisation pour l'OCR ───────────────────────────────────
_OCR_DPI = 300          # DPI de rastérisation (300 dpi = bon compromis précision/vitesse)
_OCR_ZOOM = _OCR_DPI / 72.0   # facteur zoom PyMuPDF (1 pt PDF = 1/72 pouce)


def _is_scanned_page(page: fitz.Page) -> bool:
    """
    Retourne True si la page est une image sans couche texte.

    Critères : texte vide ET au moins une image embarquée.
    """
    has_text  = bool(page.get_text().strip())
    has_image = bool(page.get_images())
    return (not has_text) and has_image


def _get_ocr_engine():
    """
    Instancie PaddleOCR (chargement des modèles au premier appel).
    Utilise le français comme langue principale avec détection d'orientation.
    """
    from paddleocr import PaddleOCR
    return PaddleOCR(
        use_textline_orientation=True,
        lang="fr",
    )


def _page_to_pil(page: fitz.Page):
    """Rastérise une page PDF en image PIL à _OCR_DPI."""
    from PIL import Image
    mat = fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _ocr_image(ocr_engine, pil_image) -> list[dict]:
    """
    Lance PaddleOCR sur une image PIL.

    Retourne une liste de dicts :
    ``{"text": str, "bbox": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]], "score": float}``
    """
    import numpy as np
    img_array = np.array(pil_image)
    result = ocr_engine.ocr(img_array)
    items = []
    if not result or not result[0]:
        return items
    for line in result[0]:
        bbox_pts, (text, score) = line
        items.append({"text": text, "score": score, "bbox": bbox_pts})
    return items


def _bbox_to_pdf_rect(bbox_pts: list, zoom: float) -> fitz.Rect:
    """
    Convertit les 4 points du bbox PaddleOCR (coordonnées image @zoom)
    en fitz.Rect dans le repère PDF (points).
    """
    xs = [p[0] for p in bbox_pts]
    ys = [p[1] for p in bbox_pts]
    return fitz.Rect(min(xs) / zoom, min(ys) / zoom,
                     max(xs) / zoom, max(ys) / zoom)


# ── API publique ──────────────────────────────────────────────────────────────

def apply_ocr_to_pdf(
    doc: fitz.Document,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> int:
    """
    Rend le PDF « searchable » en réinjectant le texte OCR sur les pages image.

    Le texte est inséré en mode invisible (``render_mode=3``) : visuellement
    rien ne change, mais le texte devient cherchable, copiable, et extractible
    par PyMuPDF pour l'édition ultérieure.

    Parameters
    ----------
    doc : fitz.Document
        Document PyMuPDF ouvert, modifié en place.
    progress_cb : callable | None
        Fonction ``(page_actuelle, total_pages, message)`` pour la progression.

    Returns
    -------
    int
        Nombre de pages OCR-isées.
    """
    ocr_engine = None
    n_pages    = len(doc)
    n_ocr      = 0

    for i, page in enumerate(doc):
        if progress_cb:
            progress_cb(i, n_pages, f"Page {i + 1}/{n_pages}…")

        if not _is_scanned_page(page):
            continue   # page avec texte → rien à faire

        # Charger le moteur OCR au premier besoin (évite le délai si aucune page scannée)
        if ocr_engine is None:
            if progress_cb:
                progress_cb(i, n_pages, "Chargement du moteur OCR…")
            ocr_engine = _get_ocr_engine()

        pil_img = _page_to_pil(page)
        items   = _ocr_image(ocr_engine, pil_img)

        for item in items:
            rect      = _bbox_to_pdf_rect(item["bbox"], _OCR_ZOOM)
            text      = item["text"]
            fontsize  = max(6.0, rect.height * 0.7)   # taille approx selon hauteur bbox

            # Insertion en mode invisible (render_mode=3) : texte cherchable mais non visible
            try:
                page.insert_text(
                    rect.tl,
                    text,
                    fontsize=fontsize,
                    render_mode=3,
                    overlay=True,
                )
            except Exception:
                pass   # certains glyphes non supportés → on ignore

        n_ocr += 1

    if progress_cb:
        progress_cb(n_pages, n_pages, f"OCR terminé — {n_ocr} page(s) traitée(s).")

    return n_ocr


def ocr_to_markdown(
    doc: fitz.Document,
    output_path: Path,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> Path:
    """
    Exporte le contenu texte d'un PDF (y compris pages scannées) en Markdown.

    - Pages avec couche texte : extraction PyMuPDF directe (rapide, fidèle).
    - Pages image (scannées)  : OCR PaddleOCR puis mise en forme Markdown.

    Parameters
    ----------
    doc : fitz.Document
        Document source.
    output_path : Path
        Chemin du fichier .md de sortie.
    progress_cb : callable | None
        Fonction ``(page_actuelle, total_pages, message)`` pour la progression.

    Returns
    -------
    Path
        Chemin du fichier .md généré.
    """
    ocr_engine = None
    n_pages    = len(doc)
    md_lines: list[str] = []

    for i, page in enumerate(doc):
        if progress_cb:
            progress_cb(i, n_pages, f"Page {i + 1}/{n_pages}…")

        if _is_scanned_page(page):
            # ── Page scannée : OCR ────────────────────────────────────────────
            if ocr_engine is None:
                if progress_cb:
                    progress_cb(i, n_pages, "Chargement du moteur OCR…")
                ocr_engine = _get_ocr_engine()

            pil_img = _page_to_pil(page)
            items   = _ocr_image(ocr_engine, pil_img)

            if items:
                # Trier par position Y (haut → bas), puis X
                items.sort(key=lambda it: (
                    min(p[1] for p in it["bbox"]),
                    min(p[0] for p in it["bbox"]),
                ))
                for item in items:
                    md_lines.append(item["text"])
            else:
                md_lines.append("*(page image — aucun texte reconnu)*")

        else:
            # ── Page avec couche texte : extraction PyMuPDF ───────────────────
            text = page.get_text("text").strip()
            if text:
                md_lines.extend(text.splitlines())
            else:
                md_lines.append("*(page vide)*")

        # Séparateur entre pages
        if i < n_pages - 1:
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

    if progress_cb:
        progress_cb(n_pages, n_pages, "Export Markdown terminé.")

    output_path.write_text("\n".join(md_lines), encoding="utf-8")
    return output_path
