"""
operations/protect.py — Chiffrement et déchiffrement PDF
=========================================================
Ce module gère la protection par mot de passe des documents PDF
en utilisant le chiffrement AES-256 fourni par PyMuPDF/libmupdf.

Deux niveaux de mot de passe PDF
---------------------------------
Le standard PDF distingue deux rôles :

- **Mot de passe utilisateur** (``user_pw``) : demandé à l'ouverture du fichier.
  Sans lui, le document est illisible.
- **Mot de passe propriétaire** (``owner_pw``) : contrôle les permissions
  (impression, copie, modification). Si identique à ``user_pw``, les deux
  sont confondus.

Permissions accordées
----------------------
Par défaut, cette implémentation accorde uniquement :
- ``PDF_PERM_PRINT`` : autoriser l'impression
- ``PDF_PERM_COPY``  : autoriser la copie du texte

Toutes les autres permissions (modification, remplissage de formulaires,
annotations...) sont refusées.
"""
from pathlib import Path
import fitz


def encrypt(
    doc: fitz.Document,
    save_path: Path,
    user_password: str,
    owner_password: str = "",
):
    """
    Chiffre le document avec AES-256 et le sauvegarde dans un nouveau fichier.

    Le document source (``doc``) n'est pas modifié — un nouveau fichier
    chiffré est écrit à ``save_path``. Cette approche est plus sûre car
    elle laisse l'original intact si l'écriture échoue.

    Parameters
    ----------
    doc : fitz.Document
        Document PyMuPDF à chiffrer.
    save_path : Path
        Chemin du fichier de sortie chiffré.
    user_password : str
        Mot de passe demandé à l'ouverture. Ne peut pas être vide.
    owner_password : str
        Mot de passe propriétaire (contrôle des permissions).
        Si vide, le mot de passe utilisateur est utilisé pour les deux rôles.

    Raises
    ------
    Exception
        En cas d'erreur d'écriture ou de paramètre invalide PyMuPDF.
    """
    # Permissions accordées : impression + copie texte seulement
    perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY

    # Si owner_password vide, utiliser user_password pour les deux rôles
    owner_pw = owner_password or user_password

    doc.save(
        str(save_path),
        encryption=fitz.PDF_ENCRYPT_AES_256,  # chiffrement AES 256 bits
        user_pw=user_password,
        owner_pw=owner_pw,
        permissions=perm,
    )


def decrypt(doc: fitz.Document, password: str) -> bool:
    """
    Tente de déchiffrer un document PDF avec le mot de passe fourni.

    ``fitz.Document.authenticate()`` retourne un entier non nul en cas de succès.
    La valeur exacte indique quel mot de passe a fonctionné (utilisateur ou propriétaire),
    mais pour l'usage de cette application un bool suffit.

    Parameters
    ----------
    doc : fitz.Document
        Document chiffré à déchiffrer (modifié en place si succès).
    password : str
        Mot de passe à tester (utilisateur ou propriétaire).

    Returns
    -------
    bool
        ``True`` si le déchiffrement a réussi ou si le document n'était pas chiffré.
        ``False`` si le mot de passe est incorrect.
    """
    if doc.is_encrypted:
        # authenticate() retourne 0 si le mdp est incorrect, non-zéro sinon
        result = doc.authenticate(password)
        return result != 0
    # Document non chiffré : déjà accessible, retourner True
    return True


def is_encrypted(doc: fitz.Document) -> bool:
    """
    Indique si le document est actuellement chiffré (nécessite un mot de passe).

    Parameters
    ----------
    doc : fitz.Document
        Document à tester.

    Returns
    -------
    bool
        ``True`` si le document est chiffré et non encore authentifié.
    """
    return doc.is_encrypted
