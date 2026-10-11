"""
ui/ocr_job.py — Exécution d'un OCR en arrière-plan, avec annulation coopérative
===============================================================================
Partagé par les onglets Modifier (« Rendre cherchable ») et Convertir (OCR → PDF/Markdown/Word/
Excel).

Pourquoi pas ``QThread.terminate()`` : il tue le thread n'importe où, y compris en plein calcul
ONNX ou pendant une écriture PyMuPDF, sur un document modifié en place — état incohérent,
verrous jamais relâchés. Ici le clic sur « Annuler » appelle ``requestInterruption()`` ; le
travail (``operations/ocr.py``) interroge ``isInterruptionRequested`` entre deux pages, lève
``OcrCancelled`` et laisse le document **strictement intact** (le texte OCR n'est inséré
qu'une fois toutes les pages reconnues).

Le dialogue reste ouvert, bouton grisé, jusqu'à l'arrêt effectif du thread (au plus une page) :
l'utilisateur ne peut donc ni fermer le document ni relancer un OCR pendant que le thread lit
encore le document.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QProgressDialog, QPushButton


class OcrWorker(QThread):
    """Exécute ``fn(progress_cb, cancel_cb)`` hors du thread de l'interface."""

    progress  = pyqtSignal(int, int, str)
    succeeded = pyqtSignal(object)
    failed    = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, fn: Callable, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        from pdf_equilibrist.operations.ocr import OcrCancelled
        try:
            result = self._fn(self.progress.emit, self.isInterruptionRequested)
        except OcrCancelled:
            self.cancelled.emit()
        except Exception as exc:   # noqa: BLE001 — remonté à l'utilisateur
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


def is_running(worker: OcrWorker | None) -> bool:
    return worker is not None and worker.isRunning()


def start_ocr_job(
    parent,
    title: str,
    total: int,
    fn: Callable,
    on_succeeded: Callable[[object], None],
    on_failed: Callable[[str], None],
    *,
    init_text: str,
    cancel_text: str,
    cancelling_text: str,
) -> OcrWorker:
    """
    Lance ``fn`` dans un ``OcrWorker`` avec un dialogue de progression annulable.

    Les textes sont passés par l'appelant (``self.tr(...)``) pour rester traduits. Retourne le
    worker : l'appelant doit en garder une référence (``is_running`` empêche d'en lancer un
    second tant que celui-ci tourne).
    """
    dlg = QProgressDialog(init_text, cancel_text, 0, max(total, 1), parent)
    dlg.setWindowTitle(title)
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.setMinimumWidth(380)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setMinimumDuration(0)       # visible tout de suite, pas de réaffichage différé

    worker = OcrWorker(fn, parent)

    def _request_cancel():
        # Ne PAS laisser QProgressDialog se fermer seul : le thread lit encore le document.
        worker.requestInterruption()
        dlg.setLabelText(cancelling_text)
        button = dlg.findChild(QPushButton)
        if button is not None:
            button.setEnabled(False)

    # le signal canceled() est connecté par défaut à cancel(), qui masque le dialogue
    dlg.canceled.disconnect()
    dlg.canceled.connect(_request_cancel)

    def _progress(cur: int, tot: int, msg: str):
        if not worker.isInterruptionRequested():
            dlg.setLabelText(msg)
        dlg.setValue(min(cur, max(total, 1)))

    def _finish(callback, *args):
        # close() ÉMET canceled() (le handler afficherait un faux « Annulation en cours… ») et ne
        # stoppe pas le minuteur interne de QProgressDialog, qui ré-afficherait le dialogue ~4 s plus
        # tard par-dessus la boîte « enregistré » (deleteLater n'est pas traité dans la boucle
        # imbriquée d'un QMessageBox). On coupe donc le signal, puis reset() arrête le minuteur.
        dlg.canceled.disconnect()
        dlg.reset()
        dlg.hide()
        dlg.deleteLater()
        if callback is not None:
            callback(*args)

    worker.progress.connect(_progress)
    worker.succeeded.connect(lambda result: _finish(on_succeeded, result))
    worker.failed.connect(lambda msg: _finish(on_failed, msg))
    worker.cancelled.connect(lambda: _finish(None))
    dlg.show()
    worker.start()
    return worker
