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


# ── Installation depuis l'application (AppImage) ─────────────────────────────

def _fake_appimage(tmp_path, monkeypatch, subdir):
    folder = tmp_path / subdir
    folder.mkdir(parents=True)
    appimage = folder / update.INSTALLED_NAME
    appimage.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(appimage))
    return appimage


def test_install_scope_user_system_none(tmp_path, monkeypatch):
    monkeypatch.setattr(update.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(update, "SYSTEM_PREFIX", tmp_path / "usr_local")
    _fake_appimage(tmp_path, monkeypatch, "home/.local/share/pdf-equilibrist")
    assert update.install_scope() == "user"
    _fake_appimage(tmp_path, monkeypatch, "usr_local/share/pdf-equilibrist")
    assert update.install_scope() == "system"
    _fake_appimage(tmp_path, monkeypatch, "Downloads")
    assert update.install_scope() == "none"
    monkeypatch.delenv("APPIMAGE")
    assert update.install_scope() == "none"


def test_installed_appimage_path(tmp_path, monkeypatch):
    monkeypatch.setattr(update.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(update, "SYSTEM_PREFIX", tmp_path / "usr_local")
    assert update.installed_appimage_path("user") == (
        tmp_path / "home" / ".local" / "share" / "pdf-equilibrist" / "PDF-Equilibrist.AppImage")
    assert update.installed_appimage_path("system") == (
        tmp_path / "usr_local" / "share" / "pdf-equilibrist" / "PDF-Equilibrist.AppImage")


def _bundle_script(tmp_path, monkeypatch):
    script = tmp_path / "appdir" / "usr" / "share" / "pdf-equilibrist" / "install.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    monkeypatch.setenv("APPDIR", str(tmp_path / "appdir"))
    return script


def test_build_install_command_user(tmp_path, monkeypatch):
    script = _bundle_script(tmp_path, monkeypatch)
    monkeypatch.setattr(update.shutil, "which", lambda name: "/usr/bin/" + name)
    new = tmp_path / "new.AppImage"
    cmd = update.build_install_command(new, "user", "ab" * 32)
    assert cmd == ["/usr/bin/bash", str(script), "--file", str(new), "--sha256", "ab" * 32]


def test_build_install_command_system_uses_pkexec_and_inline_script(tmp_path, monkeypatch):
    script = _bundle_script(tmp_path, monkeypatch)
    monkeypatch.setattr(update.shutil, "which", lambda name: "/usr/bin/" + name)
    new = tmp_path / "new.AppImage"
    cmd = update.build_install_command(new, "system", "cd" * 32)
    assert cmd[:3] == ["/usr/bin/pkexec", "/usr/bin/bash", "-c"]
    assert cmd[3] == script.read_text(encoding="utf-8")        # le script voyage en texte, pas en chemin
    assert cmd[4:] == ["install.sh", "--system", "--file", str(new), "--sha256", "cd" * 32]


def test_build_install_command_unavailable(tmp_path, monkeypatch):
    new = tmp_path / "new.AppImage"
    monkeypatch.delenv("APPDIR", raising=False)
    assert update.build_install_command(new, "user", "00") is None        # pas de script embarqué
    _bundle_script(tmp_path, monkeypatch)
    monkeypatch.setattr(update.shutil, "which", lambda name: None if name == "pkexec" else "/usr/bin/" + name)
    assert update.build_install_command(new, "system", "00") is None      # pas de pkexec
    assert update.build_install_command(new, "user", "00") is not None


def test_expected_sha256_prefers_github_digest(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"payload")
    assert update.expected_sha256({"digest": "sha256:" + "AB" * 32}, f) == "ab" * 32
    assert update.expected_sha256({}, f) == update.file_sha256(f)
    assert update.expected_sha256({"digest": "sha256:zz"}, f) == update.file_sha256(f)


def test_relaunch_env_drops_appimage_variables(monkeypatch):
    for name in ("APPIMAGE", "APPDIR", "ARGV0", "OWD"):
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI1")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/x")
    env = update.relaunch_env()
    assert not {"APPIMAGE", "APPDIR", "ARGV0", "OWD"} & set(env)
    assert env["LD_LIBRARY_PATH"] == "/usr/lib/x"
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_build_sudo_install_command_reads_password_on_stdin(tmp_path, monkeypatch):
    script = _bundle_script(tmp_path, monkeypatch)
    monkeypatch.setattr(update.shutil, "which", lambda name: "/usr/bin/" + name)
    new = tmp_path / "new.AppImage"
    cmd = update.build_sudo_install_command(new, "ef" * 32)
    assert cmd[:6] == ["/usr/bin/sudo", "-S", "-k", "-p", "", "--"]       # mot de passe sur l'entrée, jamais en argument
    assert cmd[6:9] == ["/usr/bin/bash", "-c", script.read_text(encoding="utf-8")]
    assert cmd[9:] == ["install.sh", "--system", "--file", str(new), "--sha256", "ef" * 32]


def test_build_sudo_install_command_unavailable(tmp_path, monkeypatch):
    _bundle_script(tmp_path, monkeypatch)
    monkeypatch.setattr(update.shutil, "which", lambda name: None if name == "sudo" else "/usr/bin/" + name)
    assert update.build_sudo_install_command(tmp_path / "new.AppImage", "00") is None
