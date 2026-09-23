"""Vérification temporaire : compare l'ancien et le nouveau parseur COPR
sur la vraie page. À supprimer une fois validé."""
import json, re, sys, urllib.request

COPR_PAGE = "https://copr.fedorainfracloud.org/coprs/paullux/PDF-Equilibrist/"
UA = {"User-Agent": "pdf-equilibrist-stats/1.0 (+https://pdf-equilibrist.org)"}
html = urllib.request.urlopen(urllib.request.Request(COPR_PAGE, headers=UA), timeout=30).read().decode("utf-8", "replace")

def flat(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()

# Ancien parseur (tel quel sur gh-pages)
text = flat(html)
old = {r.strip(): int(c) for r, c in re.findall(r"(Fedora [\w.]+).{0,120}?\((\d+) downloads?\)", text)}
print("ANCIEN (activations):", old, "total", sum(old.values()))

# Lignes brutes du tableau, pour contrôle visuel
for row in re.findall(r"<tr\b.*?</tr>", html, re.S):
    if "downloads)" in row:
        print("ROW:", flat(row))

sys.path.insert(0, ".")
from new_copr import parse
print("NOUVEAU:", json.dumps(parse(html), indent=2))
