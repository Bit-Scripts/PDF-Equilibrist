import urllib.error
import urllib.request

import pytest

from pdf_equilibrist import cve_checker, network, update


@pytest.fixture
def blocked():
    network.set_blocked(True)
    yield
    network.set_blocked(False)


@pytest.fixture
def no_real_network(monkeypatch: pytest.MonkeyPatch):
    """Échoue si une requête atteint réellement urllib."""
    calls = []

    def fake_urlopen(request, timeout=...):
        calls.append(request.full_url)
        raise AssertionError(f"requête émise malgré le blocage : {request.full_url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def test_blocked_urlopen_never_reaches_urllib(blocked, no_real_network):
    request = urllib.request.Request("https://api.github.com/repos/x/y")
    with pytest.raises(network.NetworkBlockedError) as exc:
        network.urlopen(request, timeout=1)
    assert exc.value.host == "api.github.com"
    assert no_real_network == []


def test_update_check_blocked(blocked, no_real_network):
    with pytest.raises(network.NetworkBlockedError):
        update.latest_release("Bit-Scripts/PDF-Equilibrist")
    with pytest.raises(network.NetworkBlockedError):
        update.download_release_asset(
            {"browser_download_url": "https://github.com/x/y/releases/download/v1/a.exe"},
            update.get_download_target({"name": "a.exe"}),
        )
    assert no_real_network == []


def test_download_stats_blocked_raises(blocked, no_real_network):
    # all_releases() avale URLError/HTTPError (statistiques facultatives) mais
    # pas le blocage : la fenêtre doit pouvoir le distinguer d'un échec réseau.
    with pytest.raises(network.NetworkBlockedError):
        update.get_download_stats("Bit-Scripts/PDF-Equilibrist", "0.1.0")


def test_cve_query_blocked(blocked, no_real_network):
    with pytest.raises(network.NetworkBlockedError):
        cve_checker.query_package_vulnerabilities("PyQt6", "6.11.0")
    assert no_real_network == []


def test_cve_query_offline_is_not_reported_as_clean(monkeypatch: pytest.MonkeyPatch):
    # Hors ligne, le paquet n'a pas été vérifié : il ne doit pas apparaître
    # comme « sans vulnérabilité connue ».
    def offline(request, timeout=...):
        raise urllib.error.URLError("hors ligne")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    with pytest.raises(urllib.error.URLError):
        cve_checker.query_package_vulnerabilities("PyQt6", "6.11.0")
