"""i18n: bilingual (English / 中文) UI strings for the dashboard.

The dashboard is the only consumer; these tests pin the public contract of the
translation lookup so the UI can swap languages without touching its layout code.
"""

from polytrader import i18n


def test_translates_a_known_key_per_language():
    assert i18n.t("running", "en") == "RUNNING"
    assert i18n.t("running", "zh") == "运行中"


def test_unknown_language_falls_back_to_default_chinese():
    assert i18n.t("running", "fr") == "运行中"


def test_unknown_key_returns_the_key_itself():
    assert i18n.t("does_not_exist", "zh") == "does_not_exist"


def test_default_language_is_chinese():
    # Calling without a language code uses the default UI language, now Chinese.
    assert i18n.t("running") == "运行中"


def test_chinese_is_the_first_language_option():
    # The dashboard picker shows the first option by default, so 中文 must lead.
    assert list(i18n.LANGUAGES)[0] == "中文"


def test_every_key_is_defined_in_both_languages():
    codes = set(i18n.LANGUAGES.values())
    assert codes == {"en", "zh"}
    for key, entry in i18n.TRANSLATIONS.items():
        assert set(entry) == codes, f"{key} missing a language"
        assert all(entry.values()), f"{key} has an empty translation"


def test_strategy_label_is_semantic_and_localized():
    assert i18n.strategy_label("market_making", "zh") == "做市/价差捕获"
    assert i18n.strategy_label("market_making", "en") == "Market making"


def test_strategy_label_falls_back_to_raw_name_for_unknown():
    assert i18n.strategy_label("some_new_strategy", "zh") == "some_new_strategy"
