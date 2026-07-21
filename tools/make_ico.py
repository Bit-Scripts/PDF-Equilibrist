"""Convertit le logo PNG en .ico multi-résolution pour PyInstaller."""
from pathlib import Path
from PIL import Image

src  = Path("assets/logo/PDF-Equilibrist-logo.png")
dest = Path("assets/logo/PDF-Equilibrist-logo.ico")

img = Image.open(src).convert("RGBA")

# Tailles standard Windows
sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
icons = [img.resize(s, Image.LANCZOS) for s in sizes]

icons[0].save(dest, format="ICO", sizes=sizes, append_images=icons[1:])
print(f"✓  ICO généré : {dest}  ({dest.stat().st_size // 1024} Ko)")
