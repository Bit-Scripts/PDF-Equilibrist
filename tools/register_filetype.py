"""
register_filetype.py
====================
Enregistre PDF-Equilibrist dans le registre Windows pour "Ouvrir avec..."
Vérifie si la clé existe avant d'agir — idempotent.
Lance le script PowerShell via subprocess si l'enregistrement est absent.

Usage :
    python tools/register_filetype.py                    # exe dans dist/
    python tools/register_filetype.py --exe "C:\...\PDF-Equilibrist.exe"
    python tools/register_filetype.py --unregister
"""
from __future__ import annotations
import sys
import subprocess
import argparse
from pathlib import Path

PROG_ID  = "PDFEquilibrist.Document"
REG_KEY  = rf"HKCU\Software\Classes\{PROG_ID}"
PS1_PATH = Path(__file__).parent / "register_filetype.ps1"


def is_registered() -> bool:
    """Vérifie si la clé ProgID existe déjà dans le registre."""
    try:
        import winreg
        winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       rf"Software\Classes\{PROG_ID}")
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def run_ps1(exe_path: Path, unregister: bool = False):
    """Lance register_filetype.ps1 via PowerShell."""
    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(PS1_PATH),
        "-ExePath", str(exe_path),
    ]
    if unregister:
        args.append("-Unregister")

    result = subprocess.run(args, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f"⚠  PowerShell a retourné {result.returncode}")
        if result.stderr:
            print(result.stderr.strip())
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Enregistre PDF-Equilibrist pour 'Ouvrir avec...' Windows")
    parser.add_argument(
        "--exe",
        help="Chemin vers PDF-Equilibrist.exe (défaut : dist/PDF-Equilibrist.exe)",
    )
    parser.add_argument(
        "--unregister",
        action="store_true",
        help="Supprime l'enregistrement",
    )
    args = parser.parse_args()

    # Résoudre le chemin de l'exe
    if args.exe:
        exe_path = Path(args.exe)
    else:
        exe_path = Path(__file__).parent.parent / "dist" / "PDF-Equilibrist.exe"

    if not args.unregister and not exe_path.exists():
        print(f"✗  Exe introuvable : {exe_path}")
        print("   Compilez d'abord avec :  pyinstaller PDF-Equilibrist.spec")
        sys.exit(1)

    if args.unregister:
        print("Suppression de l'association .pdf...")
        ok = run_ps1(exe_path, unregister=True)
        sys.exit(0 if ok else 1)

    # ── Vérifier si déjà enregistré ──────────────────────────────────────────
    if is_registered():
        print(f"✓  Déjà enregistré ({PROG_ID}) — rien à faire.")
        print(f"   Exe associé : {exe_path}")
        sys.exit(0)

    # ── Enregistrement via PowerShell ─────────────────────────────────────────
    print(f"Enregistrement de PDF-Equilibrist pour les fichiers .pdf...")
    print(f"Exe : {exe_path}")
    ok = run_ps1(exe_path)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
