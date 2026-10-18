"""Prépare les assets pour le build PyInstaller : ICO + splash PNG.

Dimensions cibles du splash : 600 × 338 px (ratio 16:9)
  - Overlay bas : 54 px
  - Barre verte  : y ≈ 317 (338 - 54 + 33)
  - Texte status : y ≈ 298 (338 - 54 + 14)
  → text_pos dans le spec = (14, 298)
"""
from pathlib import Path
import numpy as np
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


# ── Variantes de splash recolorées ────────────────────────────────────────────
# Le fond source est noir, texte blanc, logo vert : on re-compose les pixels sur
# un autre fond — texte et fond au choix, logo → vert d'origine.
def recolor(img: Image.Image, bg_hex: str, text_hex: str) -> Image.Image:
    def rgb(h):
        return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)])
    bg, text, green = rgb(bg_hex), rgb(text_hex), np.array((107, 191, 78))
    a = np.asarray(img.convert("RGB"), dtype=np.float64)
    mx, mn = a.max(axis=2), a.min(axis=2)
    is_green = ((mx - mn) / np.maximum(mx, 1) > 0.3)[..., None]
    alpha = np.where(is_green[..., 0], np.minimum(mx / green.max(), 1.0), mx / 255.0)[..., None]
    fg = np.where(is_green, green, text)
    out = bg * (1 - alpha) + fg * alpha
    return Image.fromarray(out.round().astype("uint8"), "RGB")


# Splash Qt, thème clair.
dst_light = root / "assets/splash_light.png"
recolor(splash, "#F3F3F3", "#1A1A1A").save(dst_light, format="PNG", optimize=True)
print(f"✓  PNG  → {dst_light}  (splash Qt, thème clair)")

# Splash natif PyInstaller : affiché avant Python, donc avant de connaître le thème
# → fond gris intermédiaire, lisible aussi bien avant un thème clair que sombre.
dst_native = root / "assets/splash_native.png"
recolor(splash, "#555555", "#F0F0F0").save(dst_native, format="PNG", optimize=True)
print(f"✓  PNG  → {dst_native}  (splash natif PyInstaller, gris neutre)")
