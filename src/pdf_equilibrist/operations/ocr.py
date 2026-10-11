"""
operations/ocr.py — OCR local via RapidOCR (ONNX Runtime)
==========================================================
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
   les pages image passent par RapidOCR.

Détection page scannée
-----------------------
Une page est considérée « image » si ``page.get_text().strip()`` est vide
et qu'elle contient au moins une image (``page.get_images()``).

Dépendances
-----------
- ``rapidocr``      : modèles PP-OCRv6 (détection + reconnaissance) et classifieur
                      d'orientation, au format ONNX, **livrés dans la wheel**
- ``onnxruntime``   : moteur d'inférence CPU
- ``PyMuPDF``       : rastérisation + réinsertion couche texte
- ``Pillow``        : conversion pixmap → tableau numpy

Hors-ligne par construction
---------------------------
Les trois fichiers ``.onnx`` sont embarqués avec le paquet ``rapidocr``
(donc dans l'installeur Windows et les paquets Linux). RapidOCR saurait les
télécharger s'ils manquaient ; ``_get_ocr_engine()`` vérifie leur présence
avant tout et lève ``OcrModelsMissingError`` au lieu de laisser une requête
réseau partir : aucune connexion n'est jamais émise par l'OCR.
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


class OcrModelsMissingError(RuntimeError):
    """Modèles OCR embarqués introuvables (installation incomplète)."""


# Modèles livrés dans la wheel rapidocr (dossier ``rapidocr/models``)
_MODEL_FILES = (
    "PP-OCRv6_det_small.onnx",
    "PP-OCRv6_rec_small.onnx",
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
)


def _models_dir() -> Path:
    import importlib.util
    spec = importlib.util.find_spec("rapidocr")
    if spec is None or not spec.submodule_search_locations:
        raise OcrModelsMissingError("Le paquet rapidocr n'est pas installé.")
    return Path(next(iter(spec.submodule_search_locations))) / "models"


def _check_models() -> None:
    """Refuse de continuer si un modèle manque : RapidOCR le téléchargerait."""
    d = _models_dir()
    missing = [m for m in _MODEL_FILES if not (d / m).is_file()]
    if missing:
        raise OcrModelsMissingError(
            "Modèles OCR embarqués introuvables : " + ", ".join(missing)
            + f" (dossier {d}). Réinstallez PDF-Equilibrist.")


def _get_ocr_engine():
    """Instancie RapidOCR sur les modèles embarqués (aucun téléchargement)."""
    _check_models()
    from rapidocr import RapidOCR
    return RapidOCR(params={"Global.log_level": "error"})


def _page_to_pil(page: fitz.Page):
    """Rastérise une page PDF en image PIL à _OCR_DPI."""
    from PIL import Image
    mat = fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _ocr_image(ocr_engine, pil_image) -> list[dict]:
    """
    Lance RapidOCR sur une image PIL.

    Retourne une liste de dicts :
    ``{"text": str, "bbox": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]], "score": float}``
    """
    import numpy as np
    out = ocr_engine(np.array(pil_image))
    if out is None or out.boxes is None or out.txts is None:
        return []
    return [
        {"text": text, "score": float(score), "bbox": [[float(x), float(y)] for x, y in box]}
        for box, text, score in zip(out.boxes, out.txts, out.scores)
    ]


def _bbox_to_pdf_rect(bbox_pts: list, zoom: float) -> fitz.Rect:
    """
    Convertit les 4 points du bbox OCR (coordonnées image @zoom)
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
                    fitz.Point(rect.x0, rect.y1 - rect.height * 0.2),   # ligne de base
                    text,
                    fontsize=fontsize,
                    render_mode=3,
                    overlay=True,
                )
            except Exception:  # nosec B110
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
    - Pages image (scannées)  : OCR RapidOCR puis mise en forme Markdown.

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


def selftest(report_path: str | None = None) -> int:
    """
    Auto-test de l'OCR embarqué : ``PDF-Equilibrist.exe --ocr-selftest [fichier]``.

    Génère une page « scannée », lance l'OCR avec toute connexion réseau interdite
    et vérifie que le texte (accents compris) est reconnu. Sert à valider un
    exécutable figé (PyInstaller) ou un paquet Linux sur une machine vierge.
    Retourne 0 si tout va bien, 1 sinon ; le détail est écrit dans ``report_path``.
    """
    import socket

    def _refuse(*_a, **_k):
        raise RuntimeError("connexion réseau tentée pendant l'OCR")
    socket.socket.connect = _refuse
    socket.socket.connect_ex = _refuse
    socket.getaddrinfo = _refuse

    lines: list[str] = []
    code = 1
    try:
        src = fitz.open()
        sp = src.new_page()
        sp.insert_text((50, 100), "Société Équilibre : réglement déjà versé", fontsize=18)
        pix = sp.get_pixmap(matrix=fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM), alpha=False)
        doc = fitz.open()
        page = doc.new_page(width=sp.rect.width, height=sp.rect.height)
        page.insert_image(page.rect, pixmap=pix)
        n = apply_ocr_to_pdf(doc)
        text = doc[0].get_text().strip()
        lines += [f"models_dir={_models_dir()}", f"pages={n}", f"text={text!r}"]
        code = 0 if (n == 1 and "Société" in text and "Équilibre" in text and "déjà" in text) else 1
    except Exception as exc:  # noqa: BLE001 — le rapport doit toujours être écrit
        lines.append(f"ERREUR: {type(exc).__name__}: {exc}")
    lines.append("OK" if code == 0 else "ECHEC")
    out = "\n".join(lines)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    else:
        print(out)
    return code
