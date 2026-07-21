# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PDF-Equilibrist is a Python-based PDF editor desktop application built with PyQt6 + PyMuPDF.

## Environment

```powershell
conda activate D:\Developpement\CONDA\envs\Equilibrist
pip install -e .
python src/pdf_equilibrist/main.py
```

Restaurer le venv : `conda env create -p D:\Developpement\CONDA\envs\Equilibrist -f environment.yml`

## Build

```powershell
python tools/prepare_build.py   # génère ICO + splash.png
pip install pyinstaller
pyinstaller PDF-Equilibrist.spec
# → dist/PDF-Equilibrist.exe
```

## Architecture

```
src/pdf_equilibrist/
├── main.py                  # point d'entrée — splash PyQt6 + chargement progressif
├── app.py                   # configure QApplication, stylesheet globale, crée MainWindow
├── utils.py                 # resource_path() — résolution chemins dev / PyInstaller
│
├── core/
│   └── document.py          # Document(QObject) — détient le fitz.Document ouvert,
│                            #   émet changed(pyqtSignal) à chaque modification
│
├── ui/
│   ├── main_window.py       # QWidget frameless : TitleBar + ribbon + splitter
│   │                        #   gestion multi-documents (liste de Document)
│   ├── title_bar.py         # barre de titre custom : logo, onglets docs, min/max/close
│   ├── viewer.py            # PdfViewer(QScrollArea) : rendu pages + mode édition texte
│   │                        #   + show_floating_item() pour placement interactif
│   ├── thumbnail_panel.py   # panneau miniatures latéral toujours visible
│   │                        #   drag & drop interne (réorganisation) + PDF externe
│   ├── floating_item.py     # FloatingItem : élément draggable/resizable/pivotable
│   │                        #   pour texte, image, tampon avant gravure PDF
│   ├── page_edit_widget.py  # PageEditWidget : survol/clic-to-edit bloc par bloc
│   ├── splash_screen.py     # SplashScreen PyQt6 avec barre de progression verte
│   ├── signature_dialog.py  # dialogue tampons prédéfinis + import PNG signature
│   ├── batch_dialog.py      # traitement par lot (QThread) avec progression
│   ├── widgets.py           # RibbonButton (vertical), RibbonGroup (avec titre)
│   ├── dialogs.py           # ask_password, ask_encrypt_passwords, ask_watermark…
│   ├── print_dialog.py      # print_document() — impression Win32 GDI directe
│   │                        #   _win32_print() : StretchDIBits UPSAMPLE=2 + overlay GDI
│   │                        #   _draw_vector_strokes() : re-trace les traits vectoriels
│   │                        #   _GdiCtx : bindings ctypes gdi32 (Pen, Polyline…)
│   └── tabs/
│       ├── tab_afficher.py   zoom (25–400 %, Ctrl+molette), rotation
│       ├── tab_modifier.py   modifier texte, ajouter texte/image, filigrane,
│       │                     signature/tampon, compresser
│       ├── tab_convertir.py  Word, Excel, PowerPoint, Image, Office→PDF, Image→PDF,
│       │                     traitement par lot
│       ├── tab_annoter.py    surligner, barrer, souligner, zone de texte
│       ├── tab_page.py       insérer, diviser, fusionner, inverser
│       └── tab_proteger.py   chiffrer (AES-256), déchiffrer
│
└── operations/              # logique PDF pure, sans UI, testable unitairement
    ├── edit.py              # extract_text_blocks, apply_text_edits, compress,
    │                        #   add_watermark, add_text, add_image
    ├── pages.py             # rotate_pages, invert_pages, split_pdf, merge_pdfs,
    │                        #   insert_page, crop_page, set_page_size
    ├── annotate.py          # highlight, strikeout, underline, add_text_box, add_stamp
    ├── convert.py           # to_images, to_word, to_excel, to_powerpoint,
    │                        #   image_to_pdf, office_to_pdf, detect_office_engine
    └── protect.py           # encrypt (AES-256), decrypt, is_encrypted
```

## Flux de données

```
UI (tabs/) → operations/ → fitz.Document (dans core/Document)
                                  ↓
                        document.changed.emit()
                                  ↓
                  ┌───────────────┼───────────────┐
            viewer.refresh()  thumbs.rebuild()  status update
```

- `core/Document` est le **seul** détenteur du `fitz.Document` ouvert
- Les `operations/` ne connaissent pas Qt — elles reçoivent `fitz.Document` directement
- Les tabs ne font qu'appeler les operations puis `document.changed.emit()`
- `MainWindow` gère une liste de `Document` pour le multi-onglets ; `_rebind_doc()` rebanche viewer + thumbnails sur le doc actif

## Multi-documents

```
MainWindow._documents: list[Document]   ← tous les PDFs ouverts
MainWindow._active_idx: int             ← index du doc affiché
MainWindow._rebind_doc(doc)             ← déconnecte l'ancien, reconnecte le nouveau
                                           sur viewer, thumbnails et tous les tabs
```

## Edition de texte (tab Modifier)

1. `extract_text_blocks(doc, page_index)` → liste de `TextBlock` (rect, origin baseline, font, size, color)
2. `viewer.enter_edit_mode(blocks_by_page)` → remplace les QLabel par des `PageEditWidget`
3. Clic sur un bloc → `_BlockEditor` (QTextEdit) positionné pixel-perfect sur le span
4. Entrée → `apply_text_edits` : redaction `fill=None` (transparent) + `insert_text` à l'`origin` baseline
5. Bouton "Terminer" → `viewer.exit_edit_mode()` + refresh

> Les PDF scannés (type=1 image) n'ont pas de texte extractible — message d'erreur affiché.

## Placement flottant (texte / image / tampon)

1. `viewer.show_floating_item(data, page_index, on_commit, on_cancel)`
2. `FloatingItem` apparaît sur la page — drag pour déplacer, coins pour redimensionner, poignée verte pour pivoter
3. Clic "Valider" → `on_commit(result_dict, page_index)` avec `pdf_rect` en coordonnées PDF
4. Le tab grave l'élément dans `fitz.Document` puis `document.changed.emit()`

## Conversion Office → PDF

`detect_office_engine()` → `'msoffice'` (registre Windows) → `'libreoffice'` (PATH) → `None`

## Impression (Ctrl+P)

- Bouton "Imprimer" dans l'onglet Afficher + raccourci `Ctrl+P` + menu Fichier
- `ui/print_dialog.py` : `print_document(document, parent)` — dialogue Qt puis impression Win32 GDI

### Stratégie hairline (plans AutoCAD)

**Problème** : les traits fins (0–0.25 pt) rastorisés à la résolution imprimante deviennent invisibles.

**Solution** : rendu PyMuPDF à `dpi / UPSAMPLE` (UPSAMPLE=2), puis `StretchDIBits HALFTONE` ×2.
Les hairlines font 1 px fitz → 2 px sur papier. Ensuite overlay GDI vectoriel par `_draw_vector_strokes()`.

### `_draw_vector_strokes()` — overlay vectoriel

Appelée après `StretchDIBits`, re-trace en GDI les paths stroke-only du PDF :

- `get_drawings(extended=True)` — traverse les Form XObjects (cartouche AutoCAD = bloc)
- Types gérés : `l` (ligne), `re` (rect → 4 lignes), `qu` (quad → 4 lignes), `c` (bézier cubique → 8 segments)
- `Polyline` GDI : segments consécutifs regroupés en chaîne → pas de pâtés aux jonctions
- `pen_px = max(5, round(width * zoom_native))` — épaisseur normalisée à la résolution A4

### Filtres hachures (ne pas re-tracer)

| Filtre | Condition | Cible |
|---|---|---|
| Pré-passe run | ≥ 10 paths consécutifs, 1 seul `l`, même couleur, hairline | Hachures exportées ligne par ligne |
| Clippath | `clip is not None` | Hachures AutoCAD dans un clippath |
| Bbox micro | `max(w,h) < 15 pt` | Symboles, détails de blocs |
| Multi-lignes | `len(items) > 30` et tous `l` | Hachures dans un seul path multi-segments |
| Pas de stroke | `color` absent ou `width < 0` | Fills solides, polylignes larges (fill only) |
| Image large | image > 15 % page | Plans avec photo aérienne ou fond scanné |
| < 500 drawings | total drawings < 500 | Excel, Word, PDF simples |

## UI / Theme

- Fenêtre **frameless** — `FramelessWindowHint` + `TitleBar` custom
- Resize par les bords via `windowHandle().startSystemResize(edge)` (Qt6 natif)
- **PowerToys FancyZones** : `WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX` ajoutés via `SetWindowLong` dans `showEvent`
- **Snap Layout Windows 11** : `nativeEvent` retourne `HTMAXBUTTON` au survol du bouton max → popup Snap
- **WM_SYSCOMMAND** intercepté : SC_MAXIMIZE / SC_RESTORE / SC_MINIMIZE depuis Snap et PowerToys
- Lecture mémoire sécurisée : `ctypes.string_at` + `from_buffer_copy` (évite le segfault de `from_address`)
- Style sombre façon Windows 11 (fond `#1E1E1E` / `#2D2D2D`, texte `#F0F0F0`)
- Couleur d'accentuation tirée du logo : vert `#6BBF4E` (hover, sélection active, barre de progression)
- Ribbon : `QTabBar` + `QStackedWidget`, boutons verticaux `RibbonButton` groupés par `RibbonGroup`

## Assets

- Logo / app icon : `assets/logo/PDF-Equilibrist-logo.png` + `.ico` (généré)
- Splash screen  : `assets/Splashscreen.jpg` → `assets/splash.png` (généré par `prepare_build.py`)
- Boutons fenêtre : `assets/buttons/{close,reduce,maximized,unmaximized}.png`

## Fonctionnalités non câblées (nécessitent canvas interactif)

- Crayon (dessin libre sur page)
- Lien (sélection zone cliquable)
- Signature manuscrite dessinée (import PNG OK via FloatingItem)
- Rogner la page (sélection rectangle)
- Office en PDF nécessite MS Office ou LibreOffice installé
