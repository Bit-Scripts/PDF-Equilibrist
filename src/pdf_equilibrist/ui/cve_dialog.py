from __future__ import annotations

import webbrowser
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QHBoxLayout,
    QProgressBar,
)
from PyQt6.QtCore import QThread, pyqtSignal

from pdf_equilibrist import cve_checker


class _ScanThread(QThread):
    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)

    def __init__(self, packages: list[str] | None = None):
        super().__init__()
        self.packages = packages

    def run(self):
        try:
            summary = cve_checker.scan_dependencies(self.packages)
            self.finished_ok.emit(summary)
        except Exception as exc:
            self.finished_err.emit(str(exc))


class CVEDialog(QDialog):
    def __init__(self, parent=None, packages: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Vérifier les vulnérabilités CVE")
        self.setMinimumWidth(560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self._lbl = QLabel("Recherche des vulnérabilités CVE pour les dépendances…")
        layout.addWidget(self._lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Les résultats s'afficheront ici une fois l'analyse terminée.")
        layout.addWidget(self._output)

        button_row = QHBoxLayout()
        self._btn_refresh = QPushButton("Relancer")
        self._btn_refresh.clicked.connect(self._start_scan)
        self._btn_close = QPushButton("Fermer")
        self._btn_close.clicked.connect(self.accept)
        button_row.addStretch()
        button_row.addWidget(self._btn_refresh)
        button_row.addWidget(self._btn_close)
        layout.addLayout(button_row)

        self._packages = packages
        self._results: list[dict] = []

        self._thread = _ScanThread(self._packages)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.start()

    def _render_results(self, results: list[dict]) -> str:
        if not results:
            return "Aucune dépendance n'a été trouvée pour analyse."
        vulnerable = [item for item in results if item["vulnerabilities"]]
        if not vulnerable:
            return "Aucune vulnérabilité CVE détectée pour les dépendances analysées.\n\nPackages scannés:\n" + "\n".join(item["package"] for item in results)

        lines: list[str] = [
            f"Vulnérabilités détectées pour {len(vulnerable)} package(s) :",
            "",
        ]
        for item in vulnerable:
            lines.append(f"{item['package']} :")
            for vuln in item["vulnerabilities"]:
                ids = vuln["cve_ids"] or [vuln["id"]]
                lines.append(f"  - {', '.join(ids)}")
                if vuln["severity"]:
                    lines.append(f"    Gravité : {', '.join(vuln['severity'])}")
                if vuln["summary"]:
                    lines.append(f"    Résumé : {vuln['summary']}")
                if vuln["references"]:
                    for ref in vuln["references"][:3]:
                        url = ref.get("url")
                        if url:
                            lines.append(f"      {ref.get('type', 'ref')}: {url}")
            lines.append("")
        return "\n".join(lines)

    def _on_result(self, results: list[dict]):
        self._results = results
        self._progress.setRange(0, 1)
        self._lbl.setText("Analyse des vulnérabilités terminée")
        self._output.setPlainText(self._render_results(results))

    def _on_error(self, message: str):
        self._progress.setRange(0, 1)
        self._lbl.setText("Échec de l'analyse des vulnérabilités")
        self._output.setPlainText(f"Erreur : {message}")

    def _start_scan(self):
        self._lbl.setText("Recherche des vulnérabilités CVE pour les dépendances…")
        self._output.clear()
        self._progress.setRange(0, 0)
        self._thread = _ScanThread(self._packages)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.start()
