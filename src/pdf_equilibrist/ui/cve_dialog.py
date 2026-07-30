from __future__ import annotations

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
    progress = pyqtSignal(int, int)   # (done, total)
    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)

    def __init__(self, packages: dict[str, str] | None = None):
        super().__init__()
        self.packages = packages

    def run(self):
        try:
            pkgs = self.packages or cve_checker.get_installed_packages()
            total = len(pkgs)
            self.progress.emit(0, total)
            packages = cve_checker.scan_dependencies(pkgs)
            self.progress.emit(total, total)
            code_scan = cve_checker.scan_source_code()
            self.finished_ok.emit({"packages": packages, "code_scan": code_scan})
        except Exception as exc:
            self.finished_err.emit(str(exc))


class CVEDialog(QDialog):
    def __init__(self, parent=None, packages: dict[str, str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Vérifier les vulnérabilités CVE"))
        self.setMinimumWidth(600)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self._lbl = QLabel(self.tr("Analyse des paquets installés et du code source…"))
        layout.addWidget(self._lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText(self.tr("Les résultats s'afficheront ici une fois l'analyse terminée."))
        layout.addWidget(self._output)

        button_row = QHBoxLayout()
        self._btn_refresh = QPushButton(self.tr("Relancer"))
        self._btn_refresh.clicked.connect(self._start_scan)
        self._btn_close = QPushButton(self.tr("Fermer"))
        self._btn_close.clicked.connect(self.accept)
        button_row.addStretch()
        button_row.addWidget(self._btn_refresh)
        button_row.addWidget(self._btn_close)
        layout.addLayout(button_row)

        self._packages = packages
        self._start_scan()

    def _render_results(self, results: list[dict]) -> str:
        if not results:
            return self.tr("Aucun paquet installé détecté.")

        vulnerable = [r for r in results if r["vulnerabilities"]]
        total = len(results)

        if not vulnerable:
            return (
                self.tr("Aucune vulnérabilité CVE détectée ({0} paquets analysés).\n\n").format(total)
                + "\n".join(f"  {r['package']} {r['version']}" for r in results)
            )

        lines: list[str] = [
            self.tr("{0} paquet(s) vulnérable(s) sur {1} analysés :").format(len(vulnerable), total),
            "",
        ]
        for item in vulnerable:
            lines.append(f"{item['package']} {item['version']} :")
            for vuln in item["vulnerabilities"]:
                ids = vuln["cve_ids"] or [vuln["id"]]
                lines.append(f"  - {', '.join(ids)}")
                if vuln["severity"]:
                    lines.append(self.tr("    Gravité : {0}").format(', '.join(vuln['severity'])))
                if vuln["summary"]:
                    lines.append(self.tr("    Résumé : {0}").format(vuln['summary']))
                for ref in vuln["references"][:3]:
                    url = ref.get("url")
                    if url:
                        lines.append(f"      {ref.get('type', 'ref')}: {url}")
            lines.append("")

        lines.append("─" * 40)
        lines.append(self.tr("Paquets sans vulnérabilité connue :"))
        for r in results:
            if not r["vulnerabilities"]:
                lines.append(f"  {r['package']} {r['version']}")
        return "\n".join(lines)

    def _render_code_scan(self, code_scan: dict) -> str:
        lines: list[str] = ["", "═" * 40, self.tr("Analyse statique du code source (bandit)"), "═" * 40, ""]

        if not code_scan["available"]:
            lines.append(code_scan["reason"])
            return "\n".join(lines)

        issues = code_scan["issues"]
        if not issues:
            lines.append(self.tr("Aucun problème détecté dans le code source du projet."))
            return "\n".join(lines)

        lines.append(self.tr("{0} problème(s) détecté(s) dans le code source :").format(len(issues)))
        lines.append("")
        for issue in issues:
            lines.append(
                self.tr("[{0}/confiance {1}] {2}:{3} — {4} ({5})").format(
                    issue['severity'], issue['confidence'],
                    issue['file'], issue['line'], issue['test_id'], issue['test_name'])
            )
            lines.append(f"    {issue['issue_text']}")
        return "\n".join(lines)

    def _on_progress(self, done: int, total: int):
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(done)
            self._lbl.setText(self.tr("Analyse en cours… {0}/{1} paquets").format(done, total))

    def _on_result(self, results: dict):
        packages = results["packages"]
        code_scan = results["code_scan"]
        total = len(packages)
        vuln_count = sum(1 for r in packages if r["vulnerabilities"])
        code_issue_count = len(code_scan["issues"]) if code_scan["available"] else 0

        self._progress.setRange(0, 1)
        self._progress.setValue(1)

        status_parts = []
        if vuln_count:
            status_parts.append(self.tr("⚠ {0} paquet(s) vulnérable(s)/{1}").format(vuln_count, total))
        else:
            status_parts.append(self.tr("✓ {0} paquets OK").format(total))
        if code_scan["available"]:
            if code_issue_count:
                status_parts.append(self.tr("⚠ {0} problème(s) dans le code").format(code_issue_count))
            else:
                status_parts.append(self.tr("✓ code source OK"))
        self._lbl.setText("  |  ".join(status_parts))

        self._output.setPlainText(
            self._render_results(packages) + "\n" + self._render_code_scan(code_scan)
        )

    def _on_error(self, message: str):
        self._progress.setRange(0, 1)
        self._lbl.setText(self.tr("Échec de l'analyse"))
        self._output.setPlainText(self.tr("Erreur : {0}").format(message))

    def _start_scan(self):
        self._lbl.setText(self.tr("Analyse des paquets installés et du code source…"))
        self._output.clear()
        self._progress.setRange(0, 0)
        self._thread = _ScanThread(self._packages)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.start()
