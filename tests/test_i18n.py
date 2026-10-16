# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.i18n module."""

import hsync_desktop.i18n as i18n


class TestConstants:
    """Test module constants."""

    def test_settings_org(self):
        assert i18n.SETTINGS_ORG == "HSYNC"

    def test_settings_app(self):
        assert i18n.SETTINGS_APP == "HSYNCDesktop"

    def test_language_codes(self):
        assert i18n.P2PG_EN == "en"
        assert i18n.P2PG_IT == "it"
        assert i18n.P2PG_DE == "de"
        assert i18n.P2PG_FR == "fr"
        assert i18n.P2PG_ES == "es"
        assert i18n.P2PG_PT == "pt"
        assert i18n.P2PG_ZH == "zh"
        assert i18n.P2PG_RU == "ru"
        assert i18n.P2PG_NL == "nl"
        assert i18n.P2PG_PL == "pl"
        assert i18n.P2PG_JA == "ja"

    def test_supported_languages(self):
        expected = {
            "en": "English",
            "it": "Italiano",
            "de": "Deutsch",
            "fr": "Français",
            "es": "Español",
            "pt": "Português (Brasil)",
            "zh": "中文（简体）",
            "ru": "Русский",
            "nl": "Nederlands",
            "pl": "Polski",
            "ja": "日本語",
        }
        assert expected == i18n.SUPPORTED_LANGUAGES

    def test_system_language_prefix_is_supported(self, monkeypatch):
        """A region-qualified locale (e.g. pt_BR, zh_CN) resolves to its base code."""
        for locale_name, expected in [
            ("pt_BR", i18n.P2PG_PT),
            ("zh_CN", i18n.P2PG_ZH),
            ("ru_RU", i18n.P2PG_RU),
            ("nl_NL", i18n.P2PG_NL),
            ("pl_PL", i18n.P2PG_PL),
            ("ja_JP", i18n.P2PG_JA),
        ]:
            monkeypatch.setattr(i18n.locale, "getlocale", lambda _n=locale_name: (_n, "UTF-8"))
            assert i18n._detect_system_language() == expected

    def test_unsupported_system_language_falls_back_to_english(self, monkeypatch):
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("xx_XX", "UTF-8"))
        assert i18n._detect_system_language() == i18n.P2PG_EN


class TestTranslations:
    """Test translation functionality."""

    def test_translations_loaded(self):
        """Verify translations are loaded for all supported languages."""
        assert i18n.P2PG_EN in i18n._translations
        assert i18n.P2PG_IT in i18n._translations
        assert i18n.P2PG_DE in i18n._translations
        assert i18n.P2PG_FR in i18n._translations
        assert i18n.P2PG_ES in i18n._translations
        assert i18n.P2PG_PT in i18n._translations
        assert i18n.P2PG_ZH in i18n._translations
        assert i18n.P2PG_RU in i18n._translations
        assert i18n.P2PG_NL in i18n._translations
        assert i18n.P2PG_PL in i18n._translations
        assert i18n.P2PG_JA in i18n._translations

    def test_every_supported_language_has_a_loaded_translation(self):
        for lang in i18n.SUPPORTED_LANGUAGES:
            assert lang in i18n._translations, lang

    def test_english_translations_not_empty(self):
        """English translations should not be empty."""
        en_dict = i18n._translations.get(i18n.P2PG_EN, {})
        assert len(en_dict) > 0

    def test_all_languages_have_same_keys(self):
        """All language dictionaries should have the same keys."""
        keys_by_lang = {}
        for lang in i18n.SUPPORTED_LANGUAGES:
            lang_dict = i18n._translations.get(lang, {})
            keys_by_lang[lang] = set(lang_dict.keys())

        # All should have the same keys as English
        en_keys = keys_by_lang.get(i18n.P2PG_EN, set())
        for lang, keys in keys_by_lang.items():
            assert keys == en_keys, f"{lang} has different keys than English"


class TestTranslateFunction:
    """Test tr() function."""

    def test_tr_returns_key_if_not_found(self):
        """Unknown keys should return the key itself."""
        result = i18n.tr("nonexistent.key")
        assert result == "nonexistent.key"

    def test_tr_known_key(self):
        """Known keys should return translation."""
        # This key should exist in en.py
        result = i18n.tr("app.name")
        assert result == "HSYNC Desktop"

    def test_tr_with_format_args(self):
        """Keys with format placeholders should work."""
        result = i18n.tr("label.files_fmt").format(count=3, size="1 MB")
        assert "3" in result


class TestCallbacks:
    """Test callback registration."""

    def test_register_language_callback(self):
        """Should be able to register a callback."""
        callback_called = []

        def my_callback():
            callback_called.append(True)

        i18n.register_language_callback(my_callback)
        try:
            assert my_callback in i18n._language_change_callbacks
        finally:
            i18n.unregister_language_callback(my_callback)


class TestLanguageFunctions:
    """Test language get/set functions."""

    def test_get_language_returns_string(self):
        """get_language should return a string."""
        result = i18n.get_language()
        assert isinstance(result, str)

    def test_get_language_returns_supported(self):
        """get_language should return a supported language code."""
        result = i18n.get_language()
        assert result in i18n.SUPPORTED_LANGUAGES


class TestAutoLanguage:
    """The default preference follows the system locale ("auto")."""

    @staticmethod
    def _store(monkeypatch, values):
        data = dict(values)

        class _S:
            def value(self, key, default=None, type_=None):
                return data.get(key, default)

            def setValue(self, key, value):
                data[key] = value

            def contains(self, key):
                return key in data

        monkeypatch.setattr(i18n, "QSettings", lambda *a, **k: _S())
        return data

    @staticmethod
    def _hold_current(monkeypatch):
        # ``init_language``/``set_language`` mutate the module global; snapshot
        # it so monkeypatch restores it for the other tests.
        monkeypatch.setattr(i18n, "_current_lang", i18n.get_language())

    def test_auto_sentinel(self):
        assert i18n.AUTO_LANGUAGE == "auto"

    def test_missing_preference_follows_the_system(self, monkeypatch):
        self._store(monkeypatch, {})
        monkeypatch.setattr(i18n, "_detect_system_language", lambda: "it")
        self._hold_current(monkeypatch)

        i18n.init_language()

        assert i18n.get_language() == "it"

    def test_auto_preference_follows_the_system(self, monkeypatch):
        self._store(monkeypatch, {"appearance/language": "auto"})
        monkeypatch.setattr(i18n, "_detect_system_language", lambda: "it")
        self._hold_current(monkeypatch)

        i18n.init_language()

        assert i18n.get_language() == "it"

    def test_unsupported_preference_follows_the_system(self, monkeypatch):
        self._store(monkeypatch, {"appearance/language": "xx"})
        monkeypatch.setattr(i18n, "_detect_system_language", lambda: "it")
        self._hold_current(monkeypatch)

        i18n.init_language()

        assert i18n.get_language() == "it"

    def test_explicit_preference_wins_over_the_system(self, monkeypatch):
        self._store(monkeypatch, {"appearance/language": "fr"})
        monkeypatch.setattr(i18n, "_detect_system_language", lambda: "it")
        self._hold_current(monkeypatch)

        i18n.init_language()

        assert i18n.get_language() == "fr"

    def test_set_language_auto_resolves_and_persists(self, monkeypatch):
        data = self._store(monkeypatch, {"appearance/language": "fr"})
        monkeypatch.setattr(i18n, "_detect_system_language", lambda: "it")
        monkeypatch.setattr(i18n, "_current_lang", "fr")

        i18n.set_language("auto")

        assert i18n.get_language() == "it"
        assert data["appearance/language"] == "auto"

    def test_set_language_persists_an_explicit_choice(self, monkeypatch):
        data = self._store(monkeypatch, {"appearance/language": "auto"})
        monkeypatch.setattr(i18n, "_detect_system_language", lambda: "it")
        monkeypatch.setattr(i18n, "_current_lang", "it")

        i18n.set_language("fr")

        assert i18n.get_language() == "fr"
        assert data["appearance/language"] == "fr"
