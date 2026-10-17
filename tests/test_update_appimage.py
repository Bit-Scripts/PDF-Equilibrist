from __future__ import annotations

from pathlib import Path

import pytest

from pdf_equilibrist import update


def _release(*names: str, tag: str = "v0.1.26") -> dict:
    return {"tag_name": tag, "assets": [{"name": n, "browser_download_url": f"https://x/{n}"} for n in names]}


def test_find_appimage_asset_ignores_exe_and_checksum():
    rel = _release(
        "PDF-Equilibrist-Setup.exe",
        "PDF-Equilibrist-x86_64.AppImage.sha256",
        "PDF-Equilibrist-x86_64.AppImage",
    )
    assert update.find_appimage_asset(rel)["name"] == "PDF-Equilibrist-x86_64.AppImage"
    assert update.find_installer_asset(rel)["name"] == "PDF-Equilibrist-Setup.exe"
    assert update.find_appimage_asset(_release("PDF-Equilibrist-Setup.exe")) is None


def test_is_appimage_requires_a_real_file(tmp_path, monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert not update.is_appimage()
    monkeypatch.setenv("APPIMAGE", str(tmp_path / "absent.AppImage"))
    assert not update.is_appimage()
    f = tmp_path / "PDF-Equilibrist-x86_64.AppImage"
    f.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(f))
    assert update.is_appimage()
    assert update.linux_update_command() is None


def test_appimage_target_is_versioned_next_to_current(tmp_path, monkeypatch):
    f = tmp_path / "PDF-Equilibrist-x86_64.AppImage"
    f.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(f))
    target = update.appimage_download_target(_release(tag="v0.1.26"))
    assert target == tmp_path / "PDF-Equilibrist-v0.1.26-x86_64.AppImage"
    assert target != f


def test_appimage_target_sanitizes_tag(tmp_path, monkeypatch):
    f = tmp_path / "a.AppImage"
    f.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(f))
    target = update.appimage_download_target(_release(tag="../../evil"))
    assert target.parent == tmp_path


def test_download_checks_sha256(tmp_path, monkeypatch):
    import hashlib
    import io

    data = b"payload"

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(update.network, "urlopen", lambda *a, **k: _Resp(data))
    asset = {"browser_download_url": "https://x/f", "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
    assert update.download_release_asset(asset, tmp_path / "ok").read_bytes() == data
    asset["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        update.download_release_asset(asset, Path(tmp_path / "bad"))
    assert not (tmp_path / "bad").exists()


def test_external_env_restores_original_library_path(monkeypatch):
    from pdf_equilibrist.utils import external_env

    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/custom")
    assert external_env()["LD_LIBRARY_PATH"] == "/usr/lib/custom"
    assert "LD_LIBRARY_PATH_ORIG" not in external_env()


def test_install_script_asset_and_target(tmp_path, monkeypatch):
    rel = _release("PDF-Equilibrist-x86_64.AppImage", "install.sh")
    assert update.find_install_script_asset(rel)["name"] == "install.sh"
    assert update.find_install_script_asset(_release("PDF-Equilibrist-x86_64.AppImage")) is None
    f = tmp_path / "PDF-Equilibrist-x86_64.AppImage"
    f.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(f))
    assert update.install_script_target(rel) == tmp_path / "install.sh"
