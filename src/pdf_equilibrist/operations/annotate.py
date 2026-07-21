"""
operations/annotate.py — Annotations PDF standard
==================================================
Ce module fournit des fonctions pour ajouter des **annotations PDF standard**
(au sens de la spec ISO 32000) sur les pages d'un document.

Différence avec edit.py
------------------------
- ``edit.py`` modifie le **contenu** du PDF (le flux de dessin de la page).
- ``annotate.py`` ajoute des **annotations** qui sont des objets PDF distincts,
  attachés à la page mais séparés de son contenu. Elles peuvent être lues,
  modifiées ou supprimées par n'importe quel lecteur PDF.

Type d'annotations implémentées
---------------------------------
- Highlight (surlignage jaune)
- Strikeout (biffure)
- Underline (soulignement)
- FreeText (zone de texte flottante avec fond)
- Stamp (tampon prédéfini PDF)

Paramètre ``quads``
-------------------
Les annotations de marquage (highlight, strikeout, underline) prennent des
``quads`` (quadrilatères) plutôt que de simples rectangles, ce qui permet
d'annoter du texte en ligne même s'il est légèrement incliné.
Obtenir les quads depuis PyMuPDF : ``fitz.Rect(bbox).quad``
"""
import fitz


def highlight(page: fitz.Page, quads) -> fitz.Annot:
    """
    Ajoute une annotation de surlignage sur les quads de texte spécifiés.

    L'annotation apparaît comme un fond jaune semi-transparent sur le texte,
    conformément au standard PDF.

    Parameters
    ----------
    page : fitz.Page
        Page sur laquelle ajouter l'annotation.
    quads : list[fitz.Quad] | fitz.Quad
        Un ou plusieurs quadrilatères couvrant le texte à surligner.
        Typiquement obtenu avec ``fitz.Rect(word_bbox).quad``.

    Returns
    -------
    fitz.Annot
        L'objet annotation créé et mis à jour.
    """
    annot = page.add_highlight_annot(quads)
    annot.update()   # finalise l'annotation dans le flux PDF
    return annot


def strikeout(page: fitz.Page, quads) -> fitz.Annot:
    """
    Ajoute une annotation de biffure (texte barré) sur les quads spécifiés.

    Trace une ligne horizontale au centre des rectangles de texte,
    indiquant que le contenu est supprimé ou invalide.

    Parameters
    ----------
    page : fitz.Page
        Page cible.
    quads : list[fitz.Quad] | fitz.Quad
        Quadrilatères couvrant le texte à barrer.

    Returns
    -------
    fitz.Annot
        L'objet annotation créé.
    """
    annot = page.add_strikeout_annot(quads)
    annot.update()
    return annot


def underline(page: fitz.Page, quads) -> fitz.Annot:
    """
    Ajoute une annotation de soulignement sous les quads spécifiés.

    Parameters
    ----------
    page : fitz.Page
        Page cible.
    quads : list[fitz.Quad] | fitz.Quad
        Quadrilatères couvrant le texte à souligner.

    Returns
    -------
    fitz.Annot
        L'objet annotation créé.
    """
    annot = page.add_underline_annot(quads)
    annot.update()
    return annot


def add_text_box(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    fontsize: int = 11,
    color: tuple = (0, 0, 0),
) -> fitz.Annot:
    """
    Ajoute une annotation de type « zone de texte libre » (FreeText).

    Crée une boîte avec fond jaune pâle et bordure dorée, contenant
    le texte fourni. Visible dans tous les lecteurs PDF conformes.

    Parameters
    ----------
    page : fitz.Page
        Page sur laquelle ajouter la zone de texte.
    rect : fitz.Rect
        Rectangle de la zone en coordonnées PDF.
    text : str
        Contenu textuel de la zone.
    fontsize : int
        Taille de police en points (défaut 11).
    color : tuple
        Couleur du texte RGB normalisée 0–1 (défaut noir).

    Returns
    -------
    fitz.Annot
        L'objet annotation créé.
    """
    annot = page.add_freetext_annot(
        rect,
        text,
        fontsize=fontsize,
        text_color=color,
        fill_color=(1, 1, 0.8),       # fond jaune pâle
        border_color=(0.8, 0.8, 0),   # bordure dorée
    )
    annot.update()
    return annot


def add_stamp(
    page: fitz.Page,
    rect: fitz.Rect,
    stamp_id: int = 0,
) -> fitz.Annot:
    """
    Ajoute un tampon PDF standard (Rubber Stamp annotation).

    Les tampons prédéfinis PDF (définis dans ISO 32000) ont des identifiants
    numériques. PyMuPDF en supporte plusieurs via ``stamp_id`` :
    0 = "Draft", 1 = "Approved", 2 = "Experimental", etc.

    Note : pour des tampons personnalisés avec texte et couleur custom,
    utiliser ``SignatureDialog`` et le placement via ``FloatingItem``.

    Parameters
    ----------
    page : fitz.Page
        Page sur laquelle ajouter le tampon.
    rect : fitz.Rect
        Rectangle de placement du tampon en coordonnées PDF.
    stamp_id : int
        Identifiant du tampon prédéfini (0 = Draft par défaut).

    Returns
    -------
    fitz.Annot
        L'objet annotation créé.
    """
    annot = page.add_stamp_annot(rect, stamp=stamp_id)
    annot.update()
    return annot
