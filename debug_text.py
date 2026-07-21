import fitz
import sys

path = sys.argv[1] if len(sys.argv) > 1 else input("Chemin du PDF : ")
doc = fitz.open(path)
page = doc[0]

print(f"\n=== Page 0 — {page.rect.width:.0f}x{page.rect.height:.0f} pt ===")
print(f"is_encrypted: {doc.is_encrypted}")
print(f"needs_pass:   {doc.needs_pass}")

# Méthode 1 : blocks
raw_blocks = page.get_text("blocks")
print(f"\n[blocks] {len(raw_blocks)} blocs")
for b in raw_blocks[:5]:
    print(f"  type={b[6]}  text={repr(b[4][:80])}")

# Méthode 2 : dict
raw = page.get_text("dict")
all_blocks = raw.get("blocks", [])
print(f"\n[rawdict] {len(all_blocks)} blocs")
for b in all_blocks[:5]:
    print(f"  type={b.get('type')}  lines={len(b.get('lines', []))}")
    for line in b.get("lines", [])[:2]:
        for span in line.get("spans", [])[:2]:
            print(f"    span text={repr(span.get('text','')[:60])}  font={span.get('font')}  size={span.get('size')}")

# Méthode 3 : texte brut
plain = page.get_text("text")
print(f"\n[text brut] {len(plain)} chars")
print(repr(plain[:300]))

doc.close()
