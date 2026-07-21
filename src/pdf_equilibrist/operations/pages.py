"""
operations/pages.py — Organisation et structure des pages PDF
=============================================================
Ce module regroupe toutes les opérations qui modifient la **structure** du document
(ordre, nombre, taille des pages) sans toucher au contenu textuel ou graphique.

Toutes les fonctions reçoivent un ``fitz.Document`` et le modifient en place,
sauf ``invert_pages`` et ``merge_pdfs`` qui retournent un **nouveau** document
(car PyMuPDF ne permet pas de réordonner les pages in-place de façon fiable).

Après chaque appel, le tab appelant doit émettre ``document.changed.emit()``
pour rafraîchir le viewer et les miniatures.
"""
from pathlib import Path
import fitz


def rotate_pages(
    doc: fitz.Document,
    angle: int,
    page_indices: list[int] | None = None,
):
    """
    Applique une rotation aux pages spécifiées (ou toutes si non précisé).

    La rotation s'ajoute à la rotation existante de la page et est normalisée
    modulo 360. PyMuPDF stocke la rotation dans le dictionnaire de page PDF
    (attribut ``/Rotate``), les angles valides sont 0, 90, 180, 270.

    Parameters
    ----------
    doc : fitz.Document
        Document à modifier en place.
    angle : int
        Angle en degrés à ajouter. Positif = sens anti-horaire (convention PDF).
        Utiliser +90 pour rotation droite, -90 pour rotation gauche.
    page_indices : list[int] | None
        Liste des indices 0-based des pages à faire pivoter.
        Si ``None``, toutes les pages sont concernées.
    """
    indices = list(page_indices) if page_indices is not None else list(range(len(doc)))
    for i in indices:
        # Additionner la rotation existante et normaliser dans [0, 360[
        doc[i].set_rotation((doc[i].rotation + angle) % 360)


def invert_pages(doc: fitz.Document) -> fitz.Document:
    """
    Inverse l'ordre de toutes les pages du document.

    Crée un **nouveau** document en insérant les pages de la dernière
    à la première. Le document original n'est pas modifié.

    Le tab appelant est responsable de fermer l'ancien ``fitz_doc``
    et d'assigner le nouveau avant d'émettre ``document.changed``.

    Parameters
    ----------
    doc : fitz.Document
        Document source (non modifié).

    Returns
    -------
    fitz.Document
        Nouveau document avec pages en ordre inverse.
    """
    result = fitz.open()
    # Itérer de la dernière page (len-1) vers la première (0)
    for i in range(len(doc) - 1, -1, -1):
        result.insert_pdf(doc, from_page=i, to_page=i)
    return result


def split_pdf(doc: fitz.Document, output_dir: Path) -> list[Path]:
    """
    Divise le document en autant de fichiers PDF que de pages.

    Chaque fichier de sortie contient une seule page et est nommé
    ``page_1.pdf``, ``page_2.pdf``, etc. Le dossier de sortie est
    créé s'il n'existe pas.

    Parameters
    ----------
    doc : fitz.Document
        Document source à diviser.
    output_dir : Path
        Dossier de destination des fichiers générés.

    Returns
    -------
    list[Path]
        Liste des chemins des fichiers PDF créés, dans l'ordre des pages.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(len(doc)):
        out = fitz.open()
        out.insert_pdf(doc, from_page=i, to_page=i)
        p = output_dir / f"page_{i + 1}.pdf"
        out.save(str(p))
        out.close()
        paths.append(p)
    return paths


def merge_pdfs(paths: list[Path]) -> fitz.Document:
    """
    Fusionne plusieurs fichiers PDF en un seul document en mémoire.

    Les pages sont concaténées dans l'ordre de la liste ``paths``.
    Le document retourné est en mémoire (non sauvegardé) — le tab appelant
    doit appeler ``.save()`` sur le résultat.

    Parameters
    ----------
    paths : list[Path]
        Chemins des fichiers PDF à fusionner, dans l'ordre voulu.

    Returns
    -------
    fitz.Document
        Nouveau document contenant toutes les pages, non sauvegardé.
    """
    result = fitz.open()
    for p in paths:
        src = fitz.open(str(p))
        result.insert_pdf(src)
        src.close()
    return result


def insert_page(
    doc: fitz.Document,
    after_index: int,
    src_path: Path | None = None,
):
    """
    Insère une page dans le document à la position indiquée.

    Deux modes :
    - **Page blanche** (``src_path=None``) : insère une page vide aux dimensions
      par défaut de PyMuPDF (A4 portrait).
    - **Depuis un PDF** (``src_path`` fourni) : insère toutes les pages du PDF
      source à partir de la position ``after_index + 1``.

    Parameters
    ----------
    doc : fitz.Document
        Document cible (modifié en place).
    after_index : int
        Index 0-based de la page **après laquelle** insérer.
        Ex : 0 = insérer après la 1ère page.
    src_path : Path | None
        Chemin d'un PDF source dont les pages seront insérées.
        Si ``None``, une page blanche est insérée.
    """
    if src_path:
        src = fitz.open(str(src_path))
        # start_at = position d'insertion dans le doc cible
        doc.insert_pdf(src, start_at=after_index + 1)
        src.close()
    else:
        # Insère une page blanche (dimensions par défaut : A4)
        doc.insert_page(after_index + 1)


def crop_page(doc: fitz.Document, page_index: int, rect: fitz.Rect):
    """
    Rogne une page en définissant sa CropBox.

    La CropBox définit la zone visible de la page à l'affichage et à
    l'impression. Le contenu en dehors reste dans le PDF mais n'est
    pas visible (non destructif).

    Parameters
    ----------
    doc : fitz.Document
        Document à modifier en place.
    page_index : int
        Numéro de page 0-based.
    rect : fitz.Rect
        Nouveau rectangle visible en coordonnées PDF (points).
    """
    doc[page_index].set_cropbox(rect)


def set_page_size(
    doc: fitz.Document,
    page_index: int,
    width: float,
    height: float,
):
    """
    Modifie les dimensions d'une page via sa MediaBox.

    La MediaBox définit le format physique de la page (bord extérieur).
    Origine en bas-gauche selon la convention PDF.

    Parameters
    ----------
    doc : fitz.Document
        Document à modifier en place.
    page_index : int
        Numéro de page 0-based.
    width : float
        Nouvelle largeur en points PDF (1 pt = 1/72 pouce).
    height : float
        Nouvelle hauteur en points PDF.

    Examples
    --------
    A4 portrait  : width=595, height=842
    A4 paysage   : width=842, height=595
    Letter       : width=612, height=792
    """
    doc[page_index].set_mediabox(fitz.Rect(0, 0, width, height))
