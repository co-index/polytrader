"""i18n: bilingual (English / 中文) UI strings for the dashboard.

The dashboard is the only consumer; these tests pin the public contract of the
translation lookup so the UI can swap languages without touching its layout code.
"""

from polytrader import i18n


def test_translates_a_known_key_per_language():
    assert i18n.t("running", "en") == "RUNNING"
    assert i18n.t("running", "zh") == "运行中"


def test_unknown_language_falls_back_to_english():
    assert i18n.t("running", "fr") == "RUNNING"


def test_unknown_key_returns_the_key_itself():
    assert i18n.t("does_not_exist", "zh") == "does_not_exist"


def test_default_language_is_english():
    # Calling without a language code must keep the existing English UI unchanged.
    assert i18n.t("running") == "RUNNING"


def test_every_key_is_defined_in_both_languages():
    codes = set(i18n.LANGUAGES.values())
    assert codes == {"en", "zh"}
    for key, entry in i18n.TRANSLATIONS.items():
        assert set(entry) == codes, f"{key} missing a language"
        assert all(entry.values()), f"{key} has an empty translation"
