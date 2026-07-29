#!/usr/bin/env python3
"""
Build script — generates language-specific HTML files from templates.

Usage:
    python build_i18n.py              # all languages, all templates
    python build_i18n.py fr           # French only, all templates
    python build_i18n.py en docs      # English only, docs template only

Output structure:
    fr  + index  → index.html
    fr  + docs   → docs/index.html
    en  + index  → en/index.html
    en  + docs   → docs/en/index.html
    es  + index  → es/index.html
    es  + docs   → docs/es/index.html
"""

import json
import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
L18N_DIR = os.path.join(ROOT_DIR, "l18n")

# (template_path, fr_output, other_output_pattern)
TEMPLATES = [
    ("multilingual/index.template.html", "index.html",      "{lang}/index.html"),
    ("multilingual/docs.template.html",  "docs/index.html", "docs/{lang}/index.html"),
]

target_lang = sys.argv[1] if len(sys.argv) > 1 else None
target_tpl  = sys.argv[2] if len(sys.argv) > 2 else None

dict_files = sorted(
    fn for fn in os.listdir(L18N_DIR)
    if fn.endswith(".json") and (not target_lang or fn == f"{target_lang}.json")
)

if not dict_files:
    sys.exit(f"No dictionary found{f' for lang \"{target_lang}\"' if target_lang else ''}.")

built = 0
for file in dict_files:
    lang = file[:-5]
    with open(os.path.join(L18N_DIR, file), encoding="utf-8") as f:
        dictionary = json.load(f)

    for tpl_rel, fr_out, other_out in TEMPLATES:
        if target_tpl and target_tpl not in tpl_rel:
            continue

        with open(os.path.join(ROOT_DIR, tpl_rel), encoding="utf-8") as f:
            template = f.read()

        missing = []

        def _replace(m, d=dictionary, miss=missing):
            key = m.group(1)
            if key in d:
                return d[key]
            miss.append(key)
            return m.group(0)

        html = re.sub(r"\{\{([\w.]+)\}\}", _replace, template)

        if missing:
            label = f"{lang}/{os.path.basename(tpl_rel)}"
            print(f"[{label}] Missing keys: {', '.join(missing)}", file=sys.stderr)

        out_path = os.path.join(
            ROOT_DIR,
            fr_out if lang == "fr" else other_out.format(lang=lang)
        )
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[{lang}] → {os.path.relpath(out_path, ROOT_DIR)}")
        built += 1

print(f"Done. {built} file(s) built.")
