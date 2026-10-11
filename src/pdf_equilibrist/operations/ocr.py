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
import re
from pathlib import Path
from typing import Callable
import pymupdf


# ── Résolution de rastérisation pour l'OCR ───────────────────────────────────
_OCR_DPI = 300          # DPI de rastérisation (300 dpi = bon compromis précision/vitesse)
_OCR_ZOOM = _OCR_DPI / 72.0   # facteur zoom PyMuPDF (1 pt PDF = 1/72 pouce)


def _is_scanned_page(page: pymupdf.Page) -> bool:
    """
    Retourne True si la page est une image sans couche texte.

    Critères : texte vide ET au moins une image embarquée.
    """
    has_text  = bool(page.get_text().strip())
    has_image = bool(page.get_images())
    return (not has_text) and has_image


class OcrModelsMissingError(RuntimeError):
    """Modèles OCR embarqués introuvables (installation incomplète)."""


class OcrCancelled(Exception):
    """OCR interrompu à la demande de l'utilisateur (annulation coopérative)."""


def _check_cancel(cancel_cb: Callable[[], bool] | None) -> None:
    if cancel_cb is not None and cancel_cb():
        raise OcrCancelled()


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


def _page_to_pil(page: pymupdf.Page):
    """Rastérise une page PDF en image PIL à _OCR_DPI."""
    from PIL import Image
    mat = pymupdf.Matrix(_OCR_ZOOM, _OCR_ZOOM)
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
        {"text": _repair_currency_in_text(text), "score": float(score),
         "bbox": [[float(x), float(y)] for x, y in box]}
        for box, text, score in zip(out.boxes, out.txts, out.scores)
    ]


def _bbox_to_pdf_rect(bbox_pts: list, zoom: float) -> pymupdf.Rect:
    """
    Convertit les 4 points du bbox OCR (coordonnées image @zoom)
    en pymupdf.Rect dans le repère PDF (points).
    """
    xs = [p[0] for p in bbox_pts]
    ys = [p[1] for p in bbox_pts]
    return pymupdf.Rect(min(xs) / zoom, min(ys) / zoom,
                     max(xs) / zoom, max(ys) / zoom)


# ── API publique ──────────────────────────────────────────────────────────────

def apply_ocr_to_pdf(
    doc: pymupdf.Document,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> int:
    """
    Rend le PDF « searchable » en réinjectant le texte OCR sur les pages image.

    Le texte est inséré en mode invisible (``render_mode=3``) : visuellement
    rien ne change, mais le texte devient cherchable, copiable, et extractible
    par PyMuPDF pour l'édition ultérieure.

    Annulation coopérative et **atomique** : l'OCR de toutes les pages se fait d'abord, sans
    toucher au document ; ``cancel_cb`` est interrogée avant chaque page. Si elle renvoie True,
    ``OcrCancelled`` est levée et le document est resté strictement inchangé. Le texte n'est
    inséré (étape rapide) qu'une fois toutes les pages reconnues.

    Parameters
    ----------
    doc : pymupdf.Document
        Document PyMuPDF ouvert, modifié en place (seulement en cas de succès).
    progress_cb : callable | None
        Fonction ``(page_actuelle, total_pages, message)`` pour la progression.
    cancel_cb : callable | None
        Fonction sans argument, True quand l'utilisateur a demandé l'annulation.

    Returns
    -------
    int
        Nombre de pages OCR-isées.
    """
    ocr_engine = None
    n_pages    = len(doc)
    results: list[tuple[int, list[dict]]] = []

    # ── Phase 1 : reconnaissance (document intact, annulable) ────────────────
    for i, page in enumerate(doc):
        _check_cancel(cancel_cb)
        if progress_cb:
            progress_cb(i, n_pages, f"Page {i + 1}/{n_pages}…")

        if not _is_scanned_page(page):
            continue   # page avec texte → rien à faire

        # Charger le moteur OCR au premier besoin (évite le délai si aucune page scannée)
        if ocr_engine is None:
            if progress_cb:
                progress_cb(i, n_pages, "Chargement du moteur OCR…")
            ocr_engine = _get_ocr_engine()
            _check_cancel(cancel_cb)

        results.append((i, _ocr_image(ocr_engine, _page_to_pil(page))))

    _check_cancel(cancel_cb)

    # ── Phase 2 : insertion (rapide, non annulable : jamais d'état à moitié appliqué) ──
    for i, items in results:
        page = doc[i]
        for item in items:
            rect      = _bbox_to_pdf_rect(item["bbox"], _OCR_ZOOM)
            text      = item["text"]
            fontsize  = max(6.0, rect.height * 0.7)   # taille approx selon hauteur bbox

            # Insertion en mode invisible (render_mode=3) : texte cherchable mais non visible
            try:
                page.insert_text(
                    pymupdf.Point(rect.x0, rect.y1 - rect.height * 0.2),   # ligne de base
                    text,
                    fontsize=fontsize,
                    render_mode=3,
                    overlay=True,
                )
            except Exception:  # nosec B110
                pass   # certains glyphes non supportés → on ignore

    if progress_cb:
        progress_cb(n_pages, n_pages, f"OCR terminé — {len(results)} page(s) traitée(s).")

    return len(results)


def ocr_to_markdown(
    doc: pymupdf.Document,
    output_path: Path,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> Path:
    """
    Exporte le contenu texte d'un PDF (y compris pages scannées) en Markdown.

    - Pages avec couche texte : extraction PyMuPDF directe (rapide, fidèle).
    - Pages image (scannées)  : OCR RapidOCR puis mise en forme Markdown.

    Parameters
    ----------
    doc : pymupdf.Document
        Document source.
    output_path : Path
        Chemin du fichier .md de sortie.
    progress_cb : callable | None
        Fonction ``(page_actuelle, total_pages, message)`` pour la progression.
    cancel_cb : callable | None
        True quand l'utilisateur a demandé l'annulation : ``OcrCancelled`` est levée et
        **aucun fichier n'est écrit** (le .md n'est créé qu'à la toute fin).

    Returns
    -------
    Path
        Chemin du fichier .md généré.
    """
    ocr_engine = None
    n_pages    = len(doc)
    md_lines: list[str] = []

    for i, page in enumerate(doc):
        _check_cancel(cancel_cb)
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

    _check_cancel(cancel_cb)
    if progress_cb:
        progress_cb(n_pages, n_pages, "Export Markdown terminé.")

    output_path.write_text("\n".join(md_lines), encoding="utf-8")
    return output_path


# ── Tableaux scannés → Excel ──────────────────────────────────────────────────
# Un tableau scanné n'est qu'une image : ni traits ni cellules exploitables par pdfplumber. On
# retrouve donc la grille dans l'IMAGE (traits horizontaux/verticaux, OpenCV), puis on range chaque
# texte reconnu dans la cellule qui contient son centre. Sans grille (tableau « aéré », sans bordures),
# repli : chaque boîte de texte détectée par l'OCR devient une cellule, rangée par ligne.

_AMOUNT_CELL = re.compile(r"^(-?\d[\d\s .]*,\d{2})\s*[·•.]$")
_AMOUNT_IN_TEXT = re.compile(r"(?<=\d,\d\d)\s*[·•](?=\s|$)")


def _repair_currency_in_text(text: str) -> str:
    """« 1 284,60 · TTC » → « 1 284,60 € TTC » : le modèle lit souvent « € » comme un point médian."""
    return _AMOUNT_IN_TEXT.sub(" €", text)


def _repair_currency_in_cell(text: str) -> str:
    """Cellule réduite à un montant suivi d'un point/point médian (« 420,00. ») : c'est un « € » mal lu."""
    m = _AMOUNT_CELL.match(text.strip())
    return f"{m.group(1)} €" if m else text.strip()


def _cluster(values: list[float], tol: float) -> list[float]:
    """Regroupe des positions proches (traits épais ou dédoublés) et renvoie leurs moyennes, triées."""
    out: list[list[float]] = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def _detect_grid(pil_image) -> tuple[list[float], list[float]]:
    """
    Positions (en pixels) des traits verticaux ``xs`` et horizontaux ``ys`` d'un tableau à bordures.

    Retourne ``([], [])`` si l'image n'a pas de grille (au moins 2 traits dans chaque sens).
    """
    import cv2
    import numpy as np

    gray = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    h, w = binary.shape
    h_len, v_len = max(w // 25, 40), max(h // 25, 40)
    hmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1)))
    vmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len)))
    ys = [y + bh / 2 for (_x, y, bw, bh) in
          (cv2.boundingRect(c) for c in cv2.findContours(hmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
          if bw >= h_len]
    xs = [x + bw / 2 for (x, _y, bw, bh) in
          (cv2.boundingRect(c) for c in cv2.findContours(vmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
          if bh >= v_len]
    xs, ys = _cluster(xs, 12), _cluster(ys, 12)
    return (xs, ys) if len(xs) >= 2 and len(ys) >= 2 else ([], [])


def _box_center_and_height(item: dict) -> tuple[float, float, float]:
    xs = [p[0] for p in item["bbox"]]
    ys = [p[1] for p in item["bbox"]]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(ys) - min(ys)


def _slot(value: float, edges: list[float]) -> int | None:
    """Indice de l'intervalle [edges[i], edges[i+1]) contenant ``value`` (None si hors grille)."""
    import bisect
    if value < edges[0] or value >= edges[-1]:
        return None
    return bisect.bisect_right(edges, value) - 1


def _rows_from_boxes(items: list[dict]) -> list[list[str]]:
    """Repli sans grille : une boîte de texte OCR = une cellule, rangée par ligne visuelle."""
    boxes = sorted((_box_center_and_height(it) + (it["text"],) for it in items), key=lambda b: b[1])
    rows: list[list[tuple[float, str]]] = []
    last_y, last_h = None, 0.0
    for cx, cy, bh, text in boxes:
        if last_y is not None and abs(cy - last_y) <= max(last_h, bh) * 0.6:
            rows[-1].append((cx, text))
        else:
            rows.append([(cx, text)])
        last_y, last_h = cy, bh
    return [[_repair_currency_in_cell(t) for _x, t in sorted(r)] for r in rows]


_BARE_AMOUNT = re.compile(r"^-?\d[\d\s ]*,\d{2}$")
_EURO_AMOUNT = re.compile(r"^-?\d[\d\s ]*,\d{2}\s*€$")


def _restore_currency_by_column(table: list[list[str]]) -> None:
    """
    Le modèle lit « € » de façon instable (€, point, point médian, ou rien du tout). Si au moins une
    cellule d'une colonne porte « € », les autres montants nus de cette même colonne
    (``420,00``) l'ont perdu : on le remet. Modifie ``table`` en place.
    """
    for c in range(len(table[0]) if table else 0):
        if not any(_EURO_AMOUNT.match(row[c]) for row in table):
            continue
        for row in table:
            if _BARE_AMOUNT.match(row[c]):
                row[c] = f"{row[c]} €"


def table_rows_from_items(items: list[dict], xs: list[float], ys: list[float]) -> list[list[str]]:
    """
    Construit les lignes d'un tableau à partir des textes OCR (``items``) et de la grille détectée.

    Les textes hors de la grille (titre, mentions) deviennent des lignes à une seule cellule, placées
    avant ou après le tableau selon leur position verticale.
    """
    if not xs or not ys:
        return _rows_from_boxes(items)
    n_rows, n_cols = len(ys) - 1, len(xs) - 1
    cells: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    before: list[dict] = []
    after: list[dict] = []
    for it in items:
        cx, cy, _h = _box_center_and_height(it)
        r, c = _slot(cy, ys), _slot(cx, xs)
        if r is None or c is None:
            (before if cy < ys[0] else after).append(it)
        else:
            cells.setdefault((r, c), []).append((cy, cx, it["text"]))
    table = [[""] * n_cols for _ in range(n_rows)]
    for (r, c), parts in cells.items():
        table[r][c] = _repair_currency_in_cell(" ".join(t for _cy, _cx, t in sorted(parts)))
    _restore_currency_by_column(table)
    rows = [[_line_text(g)] for g in _group_lines(before)]
    rows += table
    rows += [[_line_text(g)] for g in _group_lines(after)]
    return rows


def _line_text(group: list[dict]) -> str:
    return " ".join(i["text"] for i in sorted(group, key=lambda i: _box_center_and_height(i)[0]))


def _group_lines(items: list[dict]) -> list[list[dict]]:
    """Regroupe des boîtes de texte en lignes visuelles (même ordonnée à ~60 % de la hauteur près)."""
    groups: list[list[dict]] = []
    last_y, last_h = None, 0.0
    for it in sorted(items, key=lambda i: _box_center_and_height(i)[1]):
        _cx, cy, bh = _box_center_and_height(it)
        if last_y is not None and abs(cy - last_y) <= max(last_h, bh) * 0.6:
            groups[-1].append(it)
        else:
            groups.append([it])
        last_y, last_h = cy, bh
    return groups


def ocr_to_excel(
    doc: pymupdf.Document,
    output_path: Path,
    progress_cb: Callable[[int, int, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> Path:
    """
    Exporte les tableaux d'un PDF — scanné ou non — vers un fichier Excel (.xlsx), sans modifier ``doc``.

    - Page scannée : OCR, détection de la grille dans l'image, une cellule Excel par cellule du tableau.
    - Page avec couche texte : extraction ``pdfplumber`` habituelle (``convert.to_excel``).

    Annulable entre deux pages (``OcrCancelled`` ; aucun fichier n'est écrit dans ce cas).
    """
    from pdf_equilibrist.operations import convert

    ocr_engine = None
    n_pages = len(doc)
    scanned_tables: dict[int, list[list[str]]] = {}
    for i, page in enumerate(doc):
        _check_cancel(cancel_cb)
        if progress_cb:
            progress_cb(i, n_pages, f"Page {i + 1}/{n_pages}…")
        if not _is_scanned_page(page):
            continue
        if ocr_engine is None:
            if progress_cb:
                progress_cb(i, n_pages, "Chargement du moteur OCR…")
            ocr_engine = _get_ocr_engine()
            _check_cancel(cancel_cb)
        pil = _page_to_pil(page)
        items = _ocr_image(ocr_engine, pil)
        xs, ys = _detect_grid(pil)
        scanned_tables[i] = table_rows_from_items(items, xs, ys)
    _check_cancel(cancel_cb)
    convert.to_excel(doc, output_path, ocr_tables=scanned_tables)
    if progress_cb:
        progress_cb(n_pages, n_pages, "Export Excel terminé.")
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
        src = pymupdf.open()
        sp = src.new_page()
        sp.insert_text((50, 100), "Société Équilibre : réglement déjà versé", fontsize=18)
        pix = sp.get_pixmap(matrix=pymupdf.Matrix(_OCR_ZOOM, _OCR_ZOOM), alpha=False)
        doc = pymupdf.open()
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
