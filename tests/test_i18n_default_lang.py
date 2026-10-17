"""Langue par défaut : préférence enregistrée > langue du système > anglais."""
import pytest

from pdf_equilibrist import i18n


class _FakeLocale:
    name_value = "C"

    @classmethod
    def system(cls):
        return cls()

    def name(self):
        return self.name_value


class _FakeSettings:
    store: dict = {}

    def __init__(self, *_args):
        pass

    def value(self, key, default=None):
        return self.store.get(key, default)


@pytest.fixture
def env(monkeypatch):
    _FakeSettings.store = {}
    monkeypatch.setattr(i18n, "QLocale", _FakeLocale)
    monkeypatch.setattr(i18n, "QSettings", _FakeSettings)
    return _FakeLocale


@pytest.mark.parametrize("locale, expected", [
    ("C", "en"),          # pas de locale (conteneur, machine de test) : anglais
    ("en_US", "en"),
    ("fr_FR", "fr"),
    ("fr_CA", "fr"),
    ("de_DE", "en"),      # langue non prise en charge : anglais
])
def test_follows_system_when_nothing_saved(env, locale, expected):
    env.name_value = locale
    assert i18n.current_lang() == expected


def test_saved_choice_wins_over_system(env):
    env.name_value = "fr_FR"
    _FakeSettings.store["language"] = "en"
    assert i18n.current_lang() == "en"


def test_invalid_saved_value_falls_back_to_system(env):
    env.name_value = "fr_FR"
    _FakeSettings.store["language"] = "xx"
    assert i18n.current_lang() == "fr"
