"""
tools/sync_docs_to_pages.py — Publie la documentation de `main` sur `gh-pages`
==============================================================================
`main` est la source unique de la documentation :

    docs/*.md      (français)  →  <pages>/docs/*.md
    docs/en/*.md   (anglais)   →  <pages>/docs/en/*.md

Le script ne touche QU'À ces deux dossiers et QU'AUX fichiers .md : le reste du
site (index.html, style.css, pages générées docs/index.html, stats.json…) n'est
jamais écrasé. Un .md présent sur le site mais plus dans `main` est supprimé
(il a été retiré ou renommé à la source).

Usage :
    python tools/sync_docs_to_pages.py <dossier gh-pages> [--dry-run]

Code de sortie : 0 (affiche ce qui change ; rien à faire n'est pas une erreur).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _plan(src: Path, dst: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Retourne (à ajouter, à mettre à jour, à supprimer) pour un dossier .md plat."""
    src_files = {p.name: p for p in src.glob("*.md")}
    dst_files = {p.name: p for p in dst.glob("*.md")} if dst.is_dir() else {}
    added = [dst / n for n in sorted(src_files) if n not in dst_files]
    updated = [dst / n for n in sorted(src_files)
               if n in dst_files and src_files[n].read_bytes() != dst_files[n].read_bytes()]
    removed = [dst_files[n] for n in sorted(dst_files) if n not in src_files]
    return added, updated, removed


def sync(pages: Path, docs: Path | None = None, dry_run: bool = False) -> dict[str, list[str]]:
    docs = docs or ROOT / "docs"
    report: dict[str, list[str]] = {"added": [], "updated": [], "removed": []}
    for sub in ("", "en"):
        src, dst = docs / sub, pages / "docs" / sub
        added, updated, removed = _plan(src, dst)
        if not dry_run:
            dst.mkdir(parents=True, exist_ok=True)
            for p in added + updated:
                shutil.copyfile(src / p.name, p)
            for p in removed:
                p.unlink()
        for key, files in (("added", added), ("updated", updated), ("removed", removed)):
            report[key] += [str(p.relative_to(pages)).replace("\\", "/") for p in files]
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pages", type=Path, help="dossier de travail de la branche gh-pages")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not (args.pages / "docs").is_dir():
        print(f"ERREUR : {args.pages}/docs introuvable — ce n'est pas la branche gh-pages ?", file=sys.stderr)
        return 2
    report = sync(args.pages, dry_run=args.dry_run)
    for key, files in report.items():
        for f in files:
            print(f"{key:8} {f}")
    if not any(report.values()):
        print("Documentation déjà à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
