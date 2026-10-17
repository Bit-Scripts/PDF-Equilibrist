"""
i18n.py — Internationalisation de PDF-Equilibrist
==================================================
Charge le traducteur Qt au démarrage selon la langue enregistrée dans QSettings, à défaut
selon la langue du système (français ou anglais ; anglais si la locale est inconnue ou « C »).

Workflow :
1. ``install_translator(app)`` est appelé dans ``main.py`` juste après la création de
   la ``QApplication``, avant même le splash screen — sinon les tout premiers messages
   affichés (progression du splash) resteraient toujours en français.
2. L'utilisateur change la langue via le bouton 🌐 dans la TitleBar.
3. La préférence est sauvegardée dans QSettings ("Bit-Scripts"/"PDF-Equilibrist").
4. Un redémarrage applique le changement (le QTranslator doit être installé avant les widgets).

Ajouter une nouvelle langue :
1. Enregistrer le code dans SUPPORTED_LANGS.
2. Créer ``translations/pdf_equilibrist_{lang}.ts`` (via pylupdate6).
3. Traduire avec Qt Linguist ou un éditeur texte.
4. Compiler : ``lrelease translations/pdf_equilibrist_{lang}.ts``.
5. Embarquer le .qm dans PDF-Equilibrist.spec (section datas).
"""
from PyQt6.QtCore import QLocale, QTranslator, QSettings
from PyQt6.QtWidgets import QApplication

SUPPORTED_LANGS: dict[str, str] = {
    "fr": "Français",
    "en": "English",
}
# Langue des chaînes écrites dans le code : aucun traducteur n'est nécessaire pour elle.
SOURCE_LANG = "fr"

_translator = QTranslator()


def system_lang() -> str:
    """Langue du système si elle est prise en charge, sinon l'anglais.

    Sans réglage système (locale « C », conteneur, machine de test) c'est donc l'anglais,
    langue par défaut attendue d'une application distribuée dans le monde entier.
    """
    code = QLocale.system().name().split("_")[0].lower()
    return code if code in SUPPORTED_LANGS else "en"


def current_lang() -> str:
    """Langue choisie par l'utilisateur, à défaut celle du système."""
    settings = QSettings("Bit-Scripts", "PDF-Equilibrist")
    lang = str(settings.value("language", ""))
    return lang if lang in SUPPORTED_LANGS else system_lang()


def set_lang(lang: str) -> None:
    settings = QSettings("Bit-Scripts", "PDF-Equilibrist")
    settings.setValue("language", lang)


def install_translator(app: QApplication) -> None:
    """Charge et installe le fichier .qm correspondant à la langue stockée."""
    lang = current_lang()
    if lang == SOURCE_LANG:
        return
    from pdf_equilibrist.utils import resource_path
    qm_path = resource_path(f"translations/pdf_equilibrist_{lang}.qm")
    if qm_path.exists() and _translator.load(str(qm_path)):
        app.installTranslator(_translator)
