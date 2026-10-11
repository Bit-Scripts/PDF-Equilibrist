"""tools/sync_docs_to_pages.py : synchronise docs/ → gh-pages sans toucher au reste du site."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sync_docs_to_pages", ROOT / "tools" / "sync_docs_to_pages.py")
sync_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_mod)


def _make_site(tmp_path: Path) -> Path:
    site = tmp_path / "pages"
    (site / "docs" / "en").mkdir(parents=True)
    # Fichiers du site qui ne doivent JAMAIS être modifiés
    keep = {
        "index.html": "<html>accueil</html>",
        "style.css": "body{}",
        "stats.json": "{}",
        "docs/index.html": "<html>viewer FR</html>",
        "docs/en/index.html": "<html>viewer EN</html>",
    }
    for rel, content in keep.items():
        (site / rel).write_text(content, encoding="utf-8")
    return site


def _make_docs(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    (docs / "en").mkdir(parents=True)
    (docs / "1.INDEX.md").write_text("# FR", encoding="utf-8")
    (docs / "en" / "1.INDEX.md").write_text("# EN", encoding="utf-8")
    (docs / "notes.txt").write_text("pas un .md", encoding="utf-8")
    return docs


def test_sync_copies_markdown_and_preserves_the_rest_of_the_site(tmp_path):
    site, docs = _make_site(tmp_path), _make_docs(tmp_path)
    before = {p: p.read_bytes() for p in site.rglob("*") if p.is_file()}

    report = sync_mod.sync(site, docs)

    assert (site / "docs" / "1.INDEX.md").read_text(encoding="utf-8") == "# FR"
    assert (site / "docs" / "en" / "1.INDEX.md").read_text(encoding="utf-8") == "# EN"
    assert sorted(report["added"]) == ["docs/1.INDEX.md", "docs/en/1.INDEX.md"]
    for p, content in before.items():          # rien d'existant n'a été modifié
        assert p.read_bytes() == content, p
    assert not (site / "docs" / "notes.txt").exists()       # seuls les .md sont publiés


def test_sync_updates_and_removes_stale_markdown_only(tmp_path):
    site, docs = _make_site(tmp_path), _make_docs(tmp_path)
    (site / "docs" / "1.INDEX.md").write_text("# ancien", encoding="utf-8")
    (site / "docs" / "OBSOLETE.md").write_text("retiré de main", encoding="utf-8")

    report = sync_mod.sync(site, docs)

    assert report["updated"] == ["docs/1.INDEX.md"]
    assert report["removed"] == ["docs/OBSOLETE.md"]
    assert (site / "docs" / "1.INDEX.md").read_text(encoding="utf-8") == "# FR"
    assert (site / "docs" / "index.html").exists() and (site / "index.html").exists()


def test_sync_is_idempotent_and_dry_run_writes_nothing(tmp_path):
    site, docs = _make_site(tmp_path), _make_docs(tmp_path)
    sync_mod.sync(site, docs, dry_run=True)
    assert not (site / "docs" / "1.INDEX.md").exists()
    sync_mod.sync(site, docs)
    assert not any(sync_mod.sync(site, docs).values())


def test_main_refuses_a_folder_that_is_not_the_site(tmp_path, capsys):
    assert sync_mod.main([str(tmp_path)]) == 2
