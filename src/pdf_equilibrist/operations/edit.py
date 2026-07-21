"""
operations/edit.py — Opérations d'édition de contenu PDF
=========================================================
Ce module contient toutes les opérations qui **modifient le contenu textuel
ou graphique** d'un document PDF existant.

Principe de conception
----------------------
Les fonctions de ce module sont **sans UI** : elles reçoivent un ``fitz.Document``
et le modifient directement. Elles ne connaissent pas Qt et sont donc testables
unitairement sans lancer d'interface graphique.

C'est le tab ``tab_modifier.py`` qui orchestre l'appel à ces fonctions,
puis émet ``document.changed`` pour rafraîchir l'UI.

Édition de texte : fonctionnement détaillé
------------------------------------------
L'édition de texte repose sur deux étapes PyMuPDF :

1. **Redaction** : ``page.add_redact_annot(rect, fill=None)`` + ``page.apply_redactions()``
   Supprime le texte original du flux de contenu PDF **sans peindre de rectangle
   blanc** (``fill=None`` = fond transparent → le fond naturel de la page s'affiche).

2. **Réinsertion** : ``page.insert_text(origin, new_text, ...)``
   Réinsère le nouveau texte au **point baseline exact** (``span["origin"]``),
   avec la même police et la même taille que l'original si la police est embarquée.

Pourquoi le point baseline ?
-----------------------------
Dans les PDF, le texte est positionné par son point **baseline** (ligne de base),
pas par le coin supérieur gauche du bounding box. Utiliser ``rect.tl`` (top-left)
provoquerait un décalage vertical visible. PyMuPDF expose ``span["origin"]``
qui est exactement ce point baseline.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import fitz


# ── Modèle de bloc texte ──────────────────────────────────────────────────────

@dataclass
class TextBlock:
    """
    Représente un span de texte extrait d'une page PDF avec toutes ses métadonnées
    de style nécessaires pour la réinsertion fidèle après édition.

    Un « span » est l'unité atomique de texte dans PyMuPDF : une séquence de
    caractères partageant la même police, taille et couleur sur une même ligne.

    Attributes
    ----------
    block_id : int
        Identifiant unique dans la page (index séquentiel d'extraction).
        Utilisé pour retrouver un bloc dans ``edited_texts`` lors de l'application.
    page_index : int
        Numéro de page 0-based d'où provient ce bloc.
    rect : fitz.Rect
        Rectangle englobant du span en coordonnées PDF (points, origine haut-gauche).
        Utilisé pour la zone de redaction.
    text : str
        Contenu textuel actuel. Sert de référence pour détecter les modifications
        (on ne re-grave que les blocs dont le texte a changé).
    fontsize : float
        Taille de police en points PDF.
    color : tuple[float, float, float]
        Couleur RGB normalisée 0.0–1.0, telle qu'attendue par ``page.insert_text()``.
    origin : fitz.Point
        Point baseline du span — position exacte d'insertion pour ``insert_text()``.
        IMPORTANT : utiliser ce point et non ``rect.tl`` pour éviter le décalage vertical.
    fontname : str
        Nom de la police d'origine (ex. "Calibri,Bold"). Utilisé comme fallback
        si la police n'est pas embarquée dans le PDF.
    font_buffer : bytes | None
        Données binaires de la police embarquée extraites du PDF.
        Si disponible, permet de réinsérer avec la police exacte de l'original.
        ``None`` si la police n'est pas embarquée (on utilise alors "helv" = Helvetica).
    """
    block_id:    int
    page_index:  int
    rect:        fitz.Rect
    text:        str
    fontsize:    float
    color:       tuple[float, float, float]
    origin:      fitz.Point
    fontname:    str = "helv"
    font_buffer: bytes | None = None


def _int_color_to_tuple(c: int) -> tuple[float, float, float]:
    """
    Convertit une couleur RGB encodée en entier (format PyMuPDF) vers un tuple
    normalisé (r, g, b) avec valeurs entre 0.0 et 1.0.

    PyMuPDF retourne les couleurs de span sous forme d'un entier 24 bits :
    ``0xRRGGBB``. Qt et fitz.insert_text() attendent des floats 0–1.

    Examples
    --------
    >>> _int_color_to_tuple(0xFF0000)   # rouge pur
    (1.0, 0.0, 0.0)
    >>> _int_color_to_tuple(0x000000)   # noir
    (0.0, 0.0, 0.0)
    """
    return (
        (c >> 16 & 0xFF) / 255,   # composante Rouge
        (c >>  8 & 0xFF) / 255,   # composante Verte
        (c       & 0xFF) / 255,   # composante Bleue
    )


# ── Extraction ────────────────────────────────────────────────────────────────

def extract_text_blocks(doc: fitz.Document, page_index: int) -> list[TextBlock]:
    """
    Extrait tous les spans de texte d'une page sous forme de ``TextBlock``.

    Utilise ``page.get_text("dict")`` qui retourne la structure complète du texte :
    blocs → lignes → spans. On travaille au niveau du **span** (unité de style
    homogène) plutôt qu'au niveau du bloc ou de la ligne pour une réinsertion
    précise.

    La police embarquée est extraite en amont via ``page.get_fonts()`` et
    ``doc.extract_font(xref)`` pour permettre une réinsertion avec la police exacte.

    Parameters
    ----------
    doc : fitz.Document
        Document PyMuPDF ouvert.
    page_index : int
        Numéro de page 0-based à analyser.

    Returns
    -------
    list[TextBlock]
        Liste ordonnée des spans de texte. Liste vide si la page est une image
        (PDF scanné sans couche texte).

    Note
    ----
    Les spans avec un texte vide ou uniquement des espaces sont ignorés
    car ils ne présentent pas d'intérêt pour l'édition.
    """
    page = doc[page_index]

    # --- Étape 1 : pré-charger les polices embarquées ---
    # get_fonts(full=True) retourne pour chaque police :
    # (xref, extension, type, basefont, name, encoding, ...)
    # On indexe par basefont pour retrouver le buffer à partir du nom de span.
    font_buffers: dict[str, bytes] = {}
    for xref, ext, ftype, basefont, name, enc, *_ in page.get_fonts(full=True):
        try:
            _, buf = doc.extract_font(xref)  # retourne (extension, bytes)
            if buf:
                font_buffers[basefont] = buf
        except Exception:
            # Certaines polices système ne sont pas extractibles → on continue
            pass

    # --- Étape 2 : parser la structure textuelle ---
    blocks: list[TextBlock] = []
    bid = 0   # identifiant séquentiel unique par span sur la page

    # get_text("dict") retourne un dict avec "blocks" contenant :
    # type 0 = texte, type 1 = image
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            # Ignorer les blocs image (type=1) — pas de texte extractible
            continue

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").rstrip("\n")
                if not text.strip():
                    continue   # ignorer les spans vides ou purement whitespace

                # Extraire les métadonnées du span
                rect     = fitz.Rect(span["bbox"])
                origin   = fitz.Point(span["origin"])  # point baseline
                color    = _int_color_to_tuple(span.get("color", 0))
                fontname = span.get("font", "helv")
                fontsize = span.get("size", 12.0)
                font_buf = font_buffers.get(fontname)   # None si non embarquée

                blocks.append(TextBlock(
                    block_id=bid,
                    page_index=page_index,
                    rect=rect,
                    text=text,
                    fontsize=fontsize,
                    color=color,
                    origin=origin,
                    fontname=fontname,
                    font_buffer=font_buf,
                ))
                bid += 1

    return blocks


# ── Application des modifications ─────────────────────────────────────────────

def apply_text_edits(
    doc: fitz.Document,
    page_index: int,
    original_blocks: list[TextBlock],
    edited_texts: dict[int, str],
):
    """
    Applique les modifications textuelles sur une page PDF.

    Seuls les blocs dont le texte a **réellement changé** sont traités,
    pour éviter des redactions inutiles qui dégradent légèrement la qualité.

    Le processus en deux passes est nécessaire car PyMuPDF ne peut pas
    modifier le texte en place dans le flux PDF — on doit effacer puis réécrire.

    Parameters
    ----------
    doc : fitz.Document
        Document PyMuPDF à modifier (modifié en place).
    page_index : int
        Numéro de page 0-based contenant les blocs à modifier.
    original_blocks : list[TextBlock]
        Blocs extraits par ``extract_text_blocks()`` — sert de référence
        pour les zones à redacter et les styles de réinsertion.
    edited_texts : dict[int, str]
        Mapping ``{block_id: nouveau_texte}`` — seuls les blocs présents
        dans ce dict et dont le texte diffère de l'original sont traités.

    Note importante sur fill=None
    ------------------------------
    ``page.add_redact_annot(rect, fill=None)`` efface le texte du flux PDF
    **sans peindre de rectangle de remplissage**. Sans ce paramètre, PyMuPDF
    peindrait un rectangle blanc par défaut, visible sur les pages avec un
    fond coloré ou une image en arrière-plan.
    """
    page = doc[page_index]

    # Identifier les blocs dont le texte a effectivement changé
    changed = {
        bid for bid, txt in edited_texts.items()
        if txt != original_blocks[bid].text
    }
    if not changed:
        return   # aucune modification réelle → rien à faire

    # --- Passe 1 : Redaction transparente ---
    # Supprime le texte original sans laisser de rectangle blanc visible.
    # fill=None = pas de fond de remplissage → fond naturel de la page préservé.
    #
    # Problème des tableaux PDF : le bbox d'un span s'étend souvent dans le bbox
    # de la cellule suivante (ex: baseline ligne A à y=395.6, bbox ligne B y0=395.5).
    # apply_redactions() efface tout span dont le bbox intersecte le rect de redaction.
    # Solution : on calcule un safe_rect basé sur le baseline et on plafonne le bas
    # (y1) juste en dessous du baseline, en s'assurant qu'il ne touche pas le bbox
    # du bloc le plus proche en dessous dans la même colonne.
    for block in original_blocks:
        if block.block_id not in changed:
            continue

        ascent = block.fontsize * 0.82

        # Trouver le y0 du bloc le plus proche en dessous dans la même colonne X.
        # On compare les baselines (origin.y) et non les bboxes : dans les tableaux
        # PDF, le bbox d'un span peut commencer AVANT le baseline du span précédent,
        # ce qui fausse la détection "est en dessous" si on compare rect.y0 > origin.y.
        nearest_below_y0 = float("inf")
        for other in original_blocks:
            if other.block_id == block.block_id:
                continue
            # Même colonne : les plages X se chevauchent
            x_overlap = (other.rect.x0 < block.rect.x1 and
                         other.rect.x1 > block.rect.x0)
            if x_overlap and other.origin.y > block.origin.y:
                nearest_below_y0 = min(nearest_below_y0, other.rect.y0)

        # Descente : fontsize*0.25 par défaut, plafonné juste avant le bloc suivant
        y1 = block.origin.y + block.fontsize * 0.25
        if nearest_below_y0 < float("inf"):
            y1 = min(y1, nearest_below_y0 - 0.5)   # garantit y1 < bloc suivant

        safe_rect = fitz.Rect(
            block.rect.x0 + 0.5,
            block.origin.y - ascent,
            block.rect.x1 - 0.5,
            y1,
        )
        page.add_redact_annot(safe_rect, fill=None)

    # apply_redactions() exécute réellement les redactions dans le flux PDF.
    # PDF_REDACT_IMAGE_NONE = ne pas toucher aux images qui se trouvent
    # sous les zones redactées (performance + préservation du fond).
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    # --- Passe 2 : Réinsertion avec style original ---
    for block in original_blocks:
        if block.block_id not in changed:
            continue

        new_text = edited_texts.get(block.block_id, block.text)
        if not new_text.strip():
            continue   # texte effacé → on laisse la zone vide

        # Paramètres communs de réinsertion
        kwargs = dict(
            fontsize=block.fontsize,
            color=block.color,
            overlay=True,   # placer le texte au-dessus du contenu existant
        )

        # Utiliser la police embarquée originale si disponible,
        # sinon fallback sur Helvetica (toujours disponible dans PyMuPDF)
        if block.font_buffer:
            kwargs["fontbuffer"] = block.font_buffer
        else:
            kwargs["fontname"] = "helv"

        # Insertion au point baseline exact pour un alignement vertical parfait
        page.insert_text(block.origin, new_text, **kwargs)


# ── Opérations de mise en page ────────────────────────────────────────────────

def compress(doc: fitz.Document, save_path: Path):
    """
    Sauvegarde le document avec une compression maximale.

    Paramètres de compression utilisés :
    - ``garbage=4`` : suppression de tous les objets PDF inutilisés (collecte complète)
    - ``deflate=True`` : compression zlib des flux de contenu
    - ``deflate_images=True`` : re-compression des images embarquées
    - ``deflate_fonts=True`` : compression des données de polices

    Parameters
    ----------
    doc : fitz.Document
        Document source (non modifié).
    save_path : Path
        Chemin du fichier compressé de sortie.
    """
    doc.save(
        str(save_path),
        garbage=4,
        deflate=True,
        deflate_images=True,
        deflate_fonts=True,
    )


def add_watermark(doc: fitz.Document, text: str,
                  color: tuple = (0.6, 0.6, 0.6)):
    """
    Ajoute un texte en filigrane diagonal sur toutes les pages du document.

    Le texte est pivoté de 45° et centré approximativement sur chaque page.
    ``render_mode`` par défaut (0 = fill) rend le texte visible.

    Parameters
    ----------
    doc : fitz.Document
        Document à modifier en place.
    text : str
        Texte du filigrane (ex. "CONFIDENTIEL").
    color : tuple
        Couleur RGB normalisée 0–1. Défaut : gris moyen (0.6, 0.6, 0.6).

    Note
    ----
    Le centrage est approximatif (13 pts par caractère à fontsize 48).
    Pour un centrage parfait, il faudrait mesurer la largeur réelle du texte
    rendu avec la police choisie.
    """
    for page in doc:
        rect = page.rect
        # Centrage horizontal approximatif basé sur la largeur estimée du texte
        x = rect.width  / 2 - len(text) * 13
        y = rect.height / 2
        page.insert_text(
            fitz.Point(x, y),
            text,
            fontsize=48,
            color=color,
            rotate=45,      # rotation 45° sens anti-horaire
            overlay=True,   # au-dessus du contenu existant
        )


def add_text(
    doc: fitz.Document,
    page_index: int,
    text: str,
    point: fitz.Point,
    fontsize: int = 12,
    color: tuple = (0, 0, 0),
):
    """
    Insère un texte libre à une position donnée sur une page.

    Parameters
    ----------
    doc : fitz.Document
        Document à modifier en place.
    page_index : int
        Numéro de page 0-based.
    text : str
        Texte à insérer.
    point : fitz.Point
        Point baseline d'insertion en coordonnées PDF.
    fontsize : int
        Taille en points (défaut 12).
    color : tuple
        Couleur RGB normalisée 0–1 (défaut noir).
    """
    doc[page_index].insert_text(
        point, text,
        fontsize=fontsize,
        color=color,
        overlay=True,
    )


def add_image(doc: fitz.Document, page_index: int,
              image_path: Path, rect: fitz.Rect):
    """
    Insère une image dans un rectangle donné sur une page.

    L'image est étirée pour remplir exactement ``rect``.
    Formats supportés : PNG, JPEG, BMP, TIFF (tout ce que PyMuPDF supporte).

    Parameters
    ----------
    doc : fitz.Document
        Document à modifier en place.
    page_index : int
        Numéro de page 0-based.
    image_path : Path
        Chemin vers le fichier image à insérer.
    rect : fitz.Rect
        Rectangle de destination en coordonnées PDF.
    """
    doc[page_index].insert_image(rect, filename=str(image_path))
