#!/usr/bin/env python3
"""
compile_translations.py — Compilation des fichiers .ts en .qm

Usage :
    python tools/compile_translations.py          # compile tous les .ts
    python tools/compile_translations.py en       # compile seulement fr/en

Essaie d'abord lrelease (Qt officiel) ; si absent, utilise le générateur
Python minimaliste intégré.
"""
import struct
import sys
import xml.etree.ElementTree as ET
from hashlib import md5
from pathlib import Path
import subprocess

ROOT = Path(__file__).parent.parent
TRANSLATIONS = ROOT / "translations"

# ── Constantes format QM ──────────────────────────────────────────────────────
_MAGIC = bytes([
    0x3c, 0xb8, 0x64, 0x18, 0xca, 0xef, 0x9c, 0x95,
    0xcd, 0x21, 0x1c, 0xbf, 0x60, 0xa1, 0xbd, 0xdd,
])
_SECTION_TRANSLATIONS = 0x42
_SECTION_CONTEXTS     = 0x69
_SECTION_HASHES       = 0x2F

_TAG_END           = 1
_TAG_TRANSLATION   = 3
_TAG_SOURCE_TEXT   = 4
_TAG_CONTEXT       = 5
_TAG_COMMENT       = 6
_TAG_NUMERUS_FORMS = 10


def _pack_section(tag: int, data: bytes) -> bytes:
    return struct.pack(">BI", tag, len(data)) + data


def _encode_string(s: str) -> bytes:
    encoded = s.encode("utf-16-be")
    return struct.pack(">I", len(encoded)) + encoded


def _encode_bytes(b: bytes) -> bytes:
    return struct.pack(">I", len(b)) + b


def _hash_str(s: str) -> int:
    h = 5381
    for ch in s:
        h = ((h << 5) + h) ^ ord(ch)
    return h & 0xFFFFFFFF


def _build_translations(messages: list[tuple[str, str, str]]) -> bytes:
    """messages = [(source, translation, context), ...]"""
    buf = bytearray()
    for source, translation, context in messages:
        entry = bytearray()
        entry += struct.pack("B", _TAG_TRANSLATION) + _encode_string(translation)
        entry += struct.pack("B", _TAG_SOURCE_TEXT) + _encode_bytes(source.encode("utf-8") + b"\x00")
        entry += struct.pack("B", _TAG_CONTEXT)     + _encode_bytes(context.encode("utf-8") + b"\x00")
        entry += struct.pack("B", _TAG_END)
        buf += bytes(entry)
    return bytes(buf)


def _build_hashes(messages: list[tuple[str, str, str]], offsets: list[int]) -> bytes:
    """Table de hachage pour la recherche rapide des traductions."""
    entries = []
    for (source, _translation, context), offset in zip(messages, offsets):
        h = _hash_str(context + source)
        entries.append((h, offset))
    entries.sort(key=lambda e: e[0])
    buf = bytearray()
    for h, offset in entries:
        buf += struct.pack(">II", h, offset)
    return bytes(buf)


def compile_ts_python(ts_path: Path, qm_path: Path) -> bool:
    """
    Compilation minimaliste .ts → .qm en Python pur — repli de dernier recours.

    ATTENTION (2026-07-30) : ce writer binaire maison a produit un .qm
    corrompu qui faisait planter QTranslator.load() (access violation), et
    les traductions ne se chargeaient jamais même quand load() ne plantait
    pas — les tags de section (_SECTION_HASHES/_SECTION_TRANSLATIONS/
    _SECTION_CONTEXTS) ne correspondent probablement pas au format .qm réel
    de Qt. Non corrigé faute de pouvoir revérifier le format exact avec
    certitude — mieux vaut un repli visiblement absent qu'un faux correctif
    silencieux. En pratique, préférer un vrai `lrelease` : soit via
    `pip install pyqt5-tools` (utilisé en CI, mais sans wheel pour toutes
    les versions de Python), soit via `pip install pyside6-essentials`
    (fournit `pyside6-lrelease`, compatible avec ce format .ts/.qm Qt6 —
    solution qui a fonctionné localement le 2026-07-30 quand pyqt5-tools
    échouait à s'installer).
    """
    try:
        tree = ET.parse(ts_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"  Erreur XML dans {ts_path.name}: {e}", file=sys.stderr)
        return False

    messages = []
    for ctx in root.findall("context"):
        ctx_name_el = ctx.find("name")
        ctx_name = ctx_name_el.text or "" if ctx_name_el is not None else ""
        for msg in ctx.findall("message"):
            src_el = ctx.find("source") or msg.find("source")
            src_el = msg.find("source")
            trans_el = msg.find("translation")
            if src_el is None or trans_el is None:
                continue
            source = src_el.text or ""
            translation = trans_el.text or ""
            if not translation or trans_el.get("type") == "unfinished":
                translation = source  # fallback = source
            messages.append((source, translation, ctx_name))

    # Construction des sections
    translations_data = bytearray()
    offsets = []
    for source, translation, context in messages:
        offsets.append(len(translations_data))
        entry = bytearray()
        entry += struct.pack("B", _TAG_TRANSLATION) + _encode_string(translation)
        entry += struct.pack("B", _TAG_SOURCE_TEXT)  + _encode_bytes(source.encode("utf-8") + b"\x00")
        entry += struct.pack("B", _TAG_CONTEXT)      + _encode_bytes(context.encode("utf-8") + b"\x00")
        entry += struct.pack("B", _TAG_END)
        translations_data += entry

    hashes_data = _build_hashes(messages, offsets)

    qm = bytearray(_MAGIC)
    qm += _pack_section(_SECTION_HASHES, hashes_data)
    qm += _pack_section(_SECTION_TRANSLATIONS, bytes(translations_data))

    qm_path.write_bytes(bytes(qm))
    print(f"  [Python] {ts_path.name} → {qm_path.name} ({len(messages)} message(s))")
    return True


def compile_ts_lrelease(ts_path: Path, qm_path: Path, lrelease: str) -> bool:
    result = subprocess.run(
        [lrelease, str(ts_path), "-qm", str(qm_path)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  [lrelease] {ts_path.name} → {qm_path.name}")
        return True
    print(f"  lrelease error: {result.stderr.strip()}", file=sys.stderr)
    return False


def find_lrelease() -> str | None:
    for candidate in ["lrelease", "lrelease-qt6", "lrelease6"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None


def main():
    lang_filter = sys.argv[1] if len(sys.argv) > 1 else None
    lrelease = find_lrelease()
    if lrelease:
        print(f"lrelease trouvé : {lrelease}")
    else:
        print("lrelease non trouvé — compilation Python minimaliste utilisée")
        print("(installer Qt tools pour une compilation officielle)\n")

    ts_files = sorted(TRANSLATIONS.glob("pdf_equilibrist_*.ts"))
    if lang_filter:
        ts_files = [f for f in ts_files if f.stem.endswith(f"_{lang_filter}")]

    if not ts_files:
        sys.exit(f"Aucun fichier .ts trouvé dans {TRANSLATIONS}")

    ok = 0
    for ts_path in ts_files:
        qm_path = ts_path.with_suffix(".qm")
        if lrelease:
            success = compile_ts_lrelease(ts_path, qm_path, lrelease)
        else:
            success = compile_ts_python(ts_path, qm_path)
        if success:
            ok += 1

    print(f"\nDone. {ok}/{len(ts_files)} fichier(s) compilé(s).")


if __name__ == "__main__":
    main()
