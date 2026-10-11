"""ui/ocr_job.py : exécution en arrière-plan avec annulation coopérative (sans terminate())."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from pdf_equilibrist.operations.ocr import OcrCancelled  # noqa: E402
from pdf_equilibrist.ui import ocr_job  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wait_until(predicate, timeout=10.0):
    loop = QEventLoop()
    deadline = time.time() + timeout
    timer = QTimer()
    timer.setInterval(20)

    def _tick():
        if predicate() or time.time() > deadline:
            loop.quit()
    timer.timeout.connect(_tick)
    timer.start()
    loop.exec()
    timer.stop()
    return predicate()


def _run(worker):
    events = []
    worker.succeeded.connect(lambda r: events.append(("ok", r)))
    worker.failed.connect(lambda m: events.append(("failed", m)))
    worker.cancelled.connect(lambda: events.append(("cancelled", None)))
    worker.start()
    assert _wait_until(lambda: bool(events))
    worker.wait(5000)
    return events


def test_worker_success_and_failure(app):
    assert _run(ocr_job.OcrWorker(lambda p, c: 42)) == [("ok", 42)]
    events = _run(ocr_job.OcrWorker(lambda p, c: 1 / 0))
    assert events[0][0] == "failed" and "division" in events[0][1]


def test_worker_cancelled_signal(app):
    assert _run(ocr_job.OcrWorker(lambda p, c: (_ for _ in ()).throw(OcrCancelled()))) == [("cancelled", None)]


def test_request_interruption_is_seen_by_the_work_and_stops_it_cleanly(app):
    """Le travail interroge cancel_cb entre deux « pages » ; requestInterruption l'arrête sans terminate()."""
    pages_done = []

    def work(progress_cb, cancel_cb):
        for i in range(1000):
            if cancel_cb():
                raise OcrCancelled()
            pages_done.append(i)
            time.sleep(0.01)
        return len(pages_done)

    worker = ocr_job.OcrWorker(work)
    events = []
    worker.cancelled.connect(lambda: events.append("cancelled"))
    worker.succeeded.connect(lambda r: events.append("ok"))
    worker.start()
    assert _wait_until(lambda: len(pages_done) >= 3)
    worker.requestInterruption()
    assert _wait_until(lambda: bool(events))
    worker.wait(5000)
    assert events == ["cancelled"] and len(pages_done) < 1000
    assert not worker.isRunning()


def test_dialog_stays_open_until_the_thread_has_really_stopped(app):
    """Clic sur Annuler : bouton grisé + « Annulation… », dialogue fermé seulement à l'arrêt du thread."""
    parent = QWidget()
    stop_now = []
    cancelled = []

    def work(progress_cb, cancel_cb):
        while not cancel_cb():
            progress_cb(0, 5, "Page 1/5…")
            time.sleep(0.01)
        while not stop_now:               # simule la fin de la page en cours
            time.sleep(0.01)
        raise OcrCancelled()

    worker = ocr_job.start_ocr_job(
        parent, "OCR", 5, work, lambda r: cancelled.append("ok"), lambda m: cancelled.append(m),
        init_text="Init", cancel_text="Annuler", cancelling_text="Annulation en cours…")
    dlg = parent.findChild(QtWidgets.QProgressDialog)
    assert dlg is not None and dlg.isVisible()
    button = dlg.findChild(QPushButton)
    button.click()
    assert _wait_until(lambda: worker.isInterruptionRequested())
    assert dlg.labelText() == "Annulation en cours…" and not button.isEnabled()
    assert dlg.isVisible() and worker.isRunning()       # thread encore en train de finir sa page
    stop_now.append(True)
    assert _wait_until(lambda: not worker.isRunning())
    # le dialogue est fermé puis supprimé (deleteLater) : on ne touche plus à `dlg` après l'arrêt
    assert _wait_until(lambda: parent.findChild(QtWidgets.QProgressDialog) is None)
    assert cancelled == []                              # ni succès ni erreur signalés


def test_dialog_does_not_come_back_after_success_while_a_message_box_is_open(app):
    """Régression « fenêtre zombie » : la boîte « enregistré » s'ouvre dans une boucle imbriquée ;
    le dialogue de progression doit rester fermé (et ne pas afficher « Annulation en cours… »)
    même après le délai minimal interne de QProgressDialog (4 s par défaut)."""
    parent = QWidget()
    seen = {}

    def on_done(result):
        # équivalent de show_info() : boucle d'événements imbriquée plus longue que minimumDuration
        _wait_until(lambda: False, timeout=4.6)
        dlgs = parent.findChildren(QtWidgets.QProgressDialog)
        seen["visible"] = [d.isVisible() for d in dlgs]
        seen["labels"] = [d.labelText() for d in dlgs]

    worker = ocr_job.start_ocr_job(
        parent, "OCR", 3, lambda p, c: (p(3, 3, "fini"), 7)[1], on_done, lambda m: seen.setdefault("error", m),
        init_text="Init", cancel_text="Annuler", cancelling_text="Annulation en cours…")
    assert _wait_until(lambda: "visible" in seen, timeout=15)
    worker.wait(3000)
    assert not any(seen["visible"]), seen
    assert "Annulation en cours…" not in seen["labels"], seen
