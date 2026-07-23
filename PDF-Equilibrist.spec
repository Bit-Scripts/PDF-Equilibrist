# -*- mode: python ; coding: utf-8 -*-
# PDF-Equilibrist — PyInstaller onedir spec
#
# Avant de compiler :
#   python tools/prepare_build.py   ← génère ICO + splash.png
#   pip install pyinstaller
#   pyinstaller PDF-Equilibrist.spec
# → dist/PDF-Equilibrist/   (dossier à empaqueter avec Inno Setup)

import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)

import importlib.metadata

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# ── Données embarquées ────────────────────────────────────────────────────────
datas = [
    ("assets",              "assets"),
    ("src/pdf_equilibrist", "pdf_equilibrist"),
]
datas += collect_data_files("fitz")
datas += collect_data_files("paddleocr")
datas += collect_data_files("paddlex")

# Métadonnées (dist-info) de tous les paquets installés dans l'environnement
# de build. PyInstaller ne les embarque pas par défaut, or cve_checker.py
# s'appuie sur importlib.metadata.distributions() pour lister les paquets
# installés (scan CVE) — sans ça, l'exe figé n'en verrait presque aucun.
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
    "PyQt6.QtNetwork", "PyQt6.sip",
    "fitz", "fitz.utils",
    "zlib", "zipfile", "struct",
    "pdf2docx", "pdfplumber", "pdfminer",
    "openpyxl", "pptx", "docx",
    "PIL", "PIL.Image", "PIL.PngImagePlugin", "PIL.JpegImagePlugin",
    "cv2", "numpy",
    "pyparsing", "pypdfium2",
    "docx2pdf",
    "winreg",
    "ctypes", "ctypes.wintypes",
    "PyQt6.QtPrintSupport",
    # PaddleOCR / PaddlePaddle
    "paddleocr", "paddlex", "paddle", "paddle.base",
    "shapely", "pyclipper", "bidi", "bidi.algorithm",
    "aiohttp", "yarl", "multidict",
]
hidden += collect_submodules("pdf_equilibrist")
hidden += collect_submodules("paddleocr")
hidden += collect_submodules("paddlex")

# ── Modules lourds inutiles au runtime ───────────────────────────────────────
excludes = [
    "tkinter", "matplotlib", "scipy", "IPython",
    # Outil d'analyse statique (dev-only) : jamais invoqué depuis l'exe figé
    # (cve_checker.scan_source_code() se désactive quand sys.frozen est vrai).
    "bandit", "stevedore", "pbr",
]

# ── Analyse ───────────────────────────────────────────────────────────────────
a = Analysis(
    ["src/pdf_equilibrist/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Splash PyInstaller (bootstrap avant Python) ───────────────────────────────
splash = Splash(
    "assets/splash.png",
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(14, 298),
    text_size=11,
    text_color="#6BBF4E",
    text_default="Chargement des modules…",
    minify_script=True,
    always_on_top=True,
)

# ── Exécutable (sans bundler onefile) ─────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],                         # ← vide en onedir : les binaries vont dans COLLECT
    splash,
    splash.binaries,
    exclude_binaries=True,      # ← obligatoire pour onedir
    name="PDF-Equilibrist",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        "zlib1.dll", "zlib.dll",
        "vcruntime140.dll", "vcruntime140_1.dll",
        "msvcp140.dll", "msvcp140_1.dll",
        "libssl-*.dll", "libcrypto-*.dll",
        "api-ms-win-*.dll",
        "mupdf*.dll", "libmupdf*.dll",
        "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll",
    ],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/logo/PDF-Equilibrist-logo.ico",
)

# ── Collection finale → dist/PDF-Equilibrist/ ────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        "zlib1.dll", "zlib.dll",
        "vcruntime140.dll", "vcruntime140_1.dll",
        "msvcp140.dll", "msvcp140_1.dll",
        "libssl-*.dll", "libcrypto-*.dll",
        "api-ms-win-*.dll",
        "mupdf*.dll", "libmupdf*.dll",
        "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll",
    ],
    name="PDF-Equilibrist",
)
