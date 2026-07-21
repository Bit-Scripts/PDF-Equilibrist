"""Prépare les assets pour le build PyInstaller : ICO + splash PNG.

Dimensions cibles du splash : 600 × 338 px (ratio 16:9)
  - Overlay bas : 54 px
  - Barre verte  : y ≈ 317 (338 - 54 + 33)
  - Texte status : y ≈ 298 (338 - 54 + 14)
  → text_pos dans le spec = (14, 298)
"""
from pathlib import Path
from PIL import Image

# Dimensions fixes — DOIT correspondre à splash_screen.py et au spec
SPLASH_W, SPLASH_H = 600, 338
OVERLAY_H          = 54    # hauteur de la bande sombre en bas
TEXT_Y             = SPLASH_H - OVERLAY_H + 14   # 298
BAR_Y              = SPLASH_H - OVERLAY_H + 33   # 317

root = Path(__file__).parent.parent

# ── ICO ──────────────────────────────────────────────────────────────────────
# L'ICO multi-résolution fourni est conservé tel quel — pas de régénération.
dst_ico = root / "assets/logo/PDF-Equilibrist-logo.ico"
if dst_ico.exists():
    print(f"✓  ICO  → {dst_ico}  (existant, conservé)")
else:
    print(f"⚠  ICO  manquant : {dst_ico}")

# ── Splash PNG (taille exacte) ────────────────────────────────────────────────
src_splash = root / "assets/Splashscreen.jpg"
dst_splash = root / "assets/splash.png"
splash = Image.open(src_splash).convert("RGB")
splash = splash.resize((SPLASH_W, SPLASH_H), Image.LANCZOS)
splash.save(dst_splash, format="PNG", optimize=True)
print(f"✓  PNG  → {dst_splash}  ({SPLASH_W}×{SPLASH_H})")
print(f"   text_pos pour le spec : ({14}, {TEXT_Y})")
print(f"   bar_y                 : {BAR_Y}")
