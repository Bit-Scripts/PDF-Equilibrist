# -*- mode: python ; coding: utf-8 -*-
# PDF-Equilibrist — PyInstaller onedir spec pour LINUX (base de l'AppImage)
#
# Variante de ../../PDF-Equilibrist.spec (Windows) sans ce qui n'existe pas sous Linux :
# pas de Splash (dépend de Tcl/Tk), pas d'icône .ico, pas de winreg/ctypes.wintypes, pas d'UPX.
# Construire avec packaging/appimage/build_appimage.sh (lance PyInstaller puis assemble l'AppDir).
#
# → build/appimage/dist/PDF-Equilibrist/   (dossier onedir)

import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)

import importlib.metadata
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# Racine du dépôt : les chemins relatifs d'un .spec dépendent du dossier de lancement, pas de ce fichier
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))   # noqa: F821 — SPECPATH fourni par PyInstaller

# ── Données embarquées (mêmes que Windows) ────────────────────────────────────
datas = [
    (os.path.join(ROOT, "assets"),              "assets"),
    (os.path.join(ROOT, "src", "pdf_equilibrist"), "pdf_equilibrist"),   # lu par l'analyse SAST intégrée (cve_checker)
    (os.path.join(ROOT, "translations"),        "translations"),
]
datas += collect_data_files("pymupdf")
# OCR : RapidOCR + modèles ONNX livrés dans la wheel (rapidocr/models/*.onnx) — aucun téléchargement.
datas += collect_data_files("rapidocr")

# Métadonnées (dist-info) de tous les paquets installés : le vérificateur de CVE intégré
# s'appuie sur importlib.metadata.distributions() — sans elles, le binaire figé n'en verrait presque aucun.
for _dist in importlib.metadata.distributions():
    _name = _dist.metadata.get("Name")
    if not _name:
        continue
    try:
        datas += copy_metadata(_name)
    except Exception:
        pass

# ── Imports cachés ────────────────────────────────────────────────────────────
hidden = [
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "PyQt6.QtNetwork", "PyQt6.sip", "PyQt6.QtPrintSupport",
    "pymupdf", "pymupdf.utils", "pymupdf.table",   # `fitz` = alias runtime (voir pdf_equilibrist/__init__.py)
    "zlib", "zipfile", "struct",
    "pdf2docx", "pdfplumber", "pdfminer",
    "openpyxl", "pptx", "docx",
    "PIL", "PIL.Image", "PIL.PngImagePlugin", "PIL.JpegImagePlugin",
    "cv2", "numpy",
    "pyparsing", "pypdfium2",
    "rapidocr", "onnxruntime",
    "shapely", "pyclipper",
    "omegaconf", "colorlog",
]
hidden += collect_submodules("pdf_equilibrist")
hidden += collect_submodules("rapidocr")
# bandit charge ses tests via des entry points (stevedore), invisibles à l'analyse statique
hidden += collect_submodules("bandit")
hidden += collect_submodules("stevedore")

excludes = ["tkinter", "matplotlib", "scipy", "IPython"]

a = Analysis(
    [os.path.join(ROOT, "src", "pdf_equilibrist", "main.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # onedir
    name="PDF-Equilibrist",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,               # utile en AppImage : les messages d'erreur restent visibles dans le terminal
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="PDF-Equilibrist",
)
