"""
core/document.py — Modèle de document PDF
==========================================
Ce module contient la classe ``Document``, pièce centrale de l'architecture.

Rôle dans l'architecture
-------------------------
``Document`` est le **seul détenteur** du ``fitz.Document`` ouvert à un instant T.
Aucun autre module n'ouvre ou ne ferme directement un fichier PDF.

Le signal ``changed`` est le mécanisme de communication vers l'UI :
chaque modification du document (ouverture, sauvegarde, fermeture, ou toute
opération du dossier ``operations/``) doit se terminer par ``document.changed.emit()``.
Les widgets abonnés (viewer, panneau miniatures, barre de statut) se rafraîchissent
alors automatiquement.

Flux de données typique
-----------------------
::

    tab_modifier.py
        └── operations/edit.py          # modifie fitz_doc directement
            └── document.changed.emit() # notifie tous les abonnés
                ├── PdfViewer.refresh()
                ├── ThumbnailPanel.rebuild()
                └── MainWindow._on_doc_changed()

Multi-documents
---------------
``MainWindow`` maintient une liste de ``Document`` (un par onglet).
La méthode ``_rebind_doc()`` déconnecte les signaux de l'ancien document
et reconnecte ceux du nouveau, permettant de changer d'onglet sans
réinstancier viewer ni miniatures.
"""
from collections import deque
from pathlib import Path
import shutil
import tempfile
import fitz
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

_UNDO_MAX = 20   # nombre maximum d'états dans la pile d'annulation


class Document(QObject):
    """
    Encapsule un fichier PDF ouvert et notifie l'UI de tout changement.

    Hérite de ``QObject`` pour pouvoir émettre des signaux Qt.

    Attributes
    ----------
    fitz_doc : fitz.Document | None
        Le document PyMuPDF sous-jacent. ``None`` si aucun fichier n'est ouvert.
    path : Path | None
        Chemin du fichier sur le disque. ``None`` si aucun fichier n'est ouvert.

    Signals
    -------
    changed : pyqtSignal()
        Émis après toute modification : ouverture, fermeture, ou opération PDF.
        Les composants UI (viewer, miniatures) s'y abonnent pour se rafraîchir.
    """

    # Signal émis à chaque modification — abonné par PdfViewer et ThumbnailPanel
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.fitz_doc: fitz.Document | None = None
        self.path: Path | None = None
        self._undo_stack: deque[bytes] = deque(maxlen=_UNDO_MAX)

    # ── Propriété ──────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        """``True`` si un fichier PDF est actuellement chargé en mémoire."""
        return self.fitz_doc is not None

    # ── Opérations fichier ────────────────────────────────────────────────────

    def open(self, path: str | Path):
        """
        Ouvre un fichier PDF et notifie l'UI.

        Si un document était déjà ouvert, il est fermé proprement avant
        d'ouvrir le nouveau (libération mémoire PyMuPDF).

        Parameters
        ----------
        path : str | Path
            Chemin vers le fichier ``.pdf`` à ouvrir.
        """
        # Fermer l'éventuel document précédent pour libérer les ressources
        if self.fitz_doc:
            self.fitz_doc.close()

        self.path = Path(path)
        self.fitz_doc = fitz.open(str(self.path))
        self._undo_stack.clear()
        self.changed.emit()

    def save(self, path: str | Path | None = None):
        """
        Sauvegarde le document sur le disque.

        Parameters
        ----------
        path : str | Path | None
            Chemin de destination. Si ``None``, sauvegarde en place
            (écrase le fichier source).

        Note
        ----
        Pour une sauvegarde compressée (réduction de taille), utiliser
        ``operations.edit.compress()`` à la place.

        Chemin réseau (SSO / ZScaler)
        ------------------------------
        PyMuPDF utilise la couche C pour écrire les fichiers. Cette couche
        contourne les sessions d'authentification SSO et ZScaler, ce qui fait
        que l'écriture directe vers un chemin réseau échoue silencieusement.
        On passe donc systématiquement par un fichier temporaire local, puis
        ``shutil.copy2()`` qui utilise les API Windows authentifiées.
        """
        target = Path(path) if path else self.path

        # Détecter si la destination est un chemin réseau (UNC ou lecteur mappé)
        # On utilise toujours le passage par tmp pour être robuste dans tous les cas.
        suffix = target.suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # 1. PyMuPDF écrit dans le tmp local (toujours possible)
            self.fitz_doc.save(str(tmp_path))
            # 2. shutil.copy2 copie vers la destination avec les droits Windows
            #    (passe par SSO / ZScaler correctement)
            shutil.copy2(tmp_path, target)
        finally:
            # Nettoyage du fichier temporaire dans tous les cas
            try:
                tmp_path.unlink()
            except OSError:
                pass

    def close(self):
        """
        Ferme le document et libère la mémoire PyMuPDF.

        Remet ``fitz_doc`` et ``path`` à ``None``, puis émet ``changed``
        pour que l'UI affiche l'écran d'accueil vide.
        """
        if self.fitz_doc:
            self.fitz_doc.close()
        self.fitz_doc = None
        self.path = None
        self.changed.emit()

    # ── Annuler / Rétablir ────────────────────────────────────────────────────

    def checkpoint(self):
        """Sauvegarde l'état courant dans la pile d'annulation (avant toute modif)."""
        if self.fitz_doc:
            self._undo_stack.append(self.fitz_doc.tobytes())

    def undo(self) -> bool:
        """Restaure le dernier état sauvegardé. Retourne True si annulation effectuée."""
        if not self._undo_stack or not self.fitz_doc:
            return False
        state = self._undo_stack.pop()
        self.fitz_doc.close()
        self.fitz_doc = fitz.open(stream=state, filetype="pdf")
        self.changed.emit()
        return True

    @property
    def can_undo(self) -> bool:
        """True si au moins un état est disponible dans la pile d'annulation."""
        return len(self._undo_stack) > 0

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def render_page(self, page_num: int, zoom: float = 1.0) -> QPixmap:
        """
        Rastérise une page PDF en ``QPixmap`` pour l'affichage Qt.

        Utilise PyMuPDF pour rendre la page en RGB (sans canal alpha),
        puis convertit en ``QImage`` puis en ``QPixmap``.

        Parameters
        ----------
        page_num : int
            Index 0-based de la page à rendre.
        zoom : float
            Facteur de zoom (1.0 = 72 dpi natif PDF, 2.0 = 144 dpi, etc.).
            Un zoom de 1.0 donne environ 96 px par pouce sur écran standard.

        Returns
        -------
        QPixmap
            Image prête à être affichée dans un ``QLabel`` ou dessinée
            via ``QPainter``.

        Note
        ----
        ``fitz.Matrix(zoom, zoom)`` applique le zoom uniformément en X et Y.
        ``alpha=False`` améliore les performances (pas de canal transparence).
        ``QImage.Format.Format_RGB888`` correspond au format 24 bits RGB de PyMuPDF.
        """
        page = self.fitz_doc[page_num]

        # Matrice de transformation : zoom uniforme horizontal et vertical
        mat = fitz.Matrix(zoom, zoom)

        # Rasterisation PyMuPDF → objet Pixmap (données brutes RGB en mémoire)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # Conversion vers QImage : on réutilise le buffer mémoire de PyMuPDF
        # (pix.samples = bytes RGB bruts, pix.stride = octets par ligne)
        img = QImage(
            pix.samples, pix.width, pix.height,
            pix.stride, QImage.Format.Format_RGB888
        )

        # QPixmap est l'objet Qt optimisé pour l'affichage (GPU-backed)
        return QPixmap.fromImage(img)
