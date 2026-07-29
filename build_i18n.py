#!/usr/bin/env python3
"""
Build script — generates language-specific index.html files from a template.

Usage:
    python build_i18n.py              # build all languages
    python build_i18n.py fr           # build only French

Output:
    fr  -> index.html        (canonical FR root)
    en  -> en/index.html
    ... -> {lang}/index.html
"""

import json
import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT_DIR, "multilingual", "index.template.html")
L18N_DIR = os.path.join(ROOT_DIR, "l18n")

target_lang = sys.argv[1] if len(sys.argv) > 1 else None

with open(TEMPLATE, encoding="utf-8") as f:
    template = f.read()

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

    missing = []

    def replace(m):
        key = m.group(1)
        if key in dictionary:
            return dictionary[key]
        missing.append(key)
        return m.group(0)

    html = re.sub(r"\{\{([\w.]+)\}\}", replace, template)

    if missing:
        print(f"[{lang}] Missing keys: {', '.join(missing)}", file=sys.stderr)

    if lang == "fr":
        out_path = os.path.join(ROOT_DIR, "index.html")
    else:
        out_dir = os.path.join(ROOT_DIR, lang)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "index.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    rel = os.path.relpath(out_path, ROOT_DIR)
    print(f"[{lang}] → {rel}")
    built += 1

print(f"Done. {built} file(s) built.")
