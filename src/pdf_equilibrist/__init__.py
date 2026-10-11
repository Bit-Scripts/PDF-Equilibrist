"""Package PDF Equilibrist."""

__version__ = "0.1.0"


def _alias_legacy_fitz() -> None:
    """
    Évite l'avertissement « The `fitz` API is deprecated… » dû à une dépendance tierce.

    Notre code importe ``pymupdf``, mais ``pdf2docx`` fait encore ``import fitz`` et
    ``from fitz.utils import …``. Or ``fitz`` n'est plus qu'un module de compatibilité qui affiche
    cet avertissement à chaque import. On enregistre donc ``pymupdf`` sous le nom ``fitz`` AVANT que
    la dépendance ne l'importe : même objet, aucune copie, plus d'avertissement. Sans effet si
    ``fitz`` est déjà chargé.
    """
    import sys

    import pymupdf

    if "fitz" not in sys.modules:
        sys.modules["fitz"] = pymupdf
        sys.modules["fitz.utils"] = pymupdf.utils
        sys.modules["fitz.table"] = pymupdf.table


_alias_legacy_fitz()
