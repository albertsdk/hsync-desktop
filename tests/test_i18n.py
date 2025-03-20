# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.i18n module."""

import hsync_desktop.i18n as i18n


class TestConstants:
    """Test module constants."""

    def test_settings_org(self):
        assert i18n.SETTINGS_ORG == "HSYNC"

    def test_settings_app(self):
        assert i18n.SETTINGS_APP == "HSYNCDesktop"

    def test_language_codes(self):
        assert i18n.LANG_EN == "en"
        assert i18n.LANG_IT == "it"
        assert i18n.LANG_DE == "de"
        assert i18n.LANG_FR == "fr"
        assert i18n.LANG_ES == "es"

    def test_supported_languages(self):
        expected = {
            "en": "English",
            "it": "Italiano",
            "de": "Deutsch",
            "fr": "Français",
            "es": "Español",
        }
        assert expected == i18n.SUPPORTED_LANGUAGES


class TestTranslations:
    """Test translation functionality."""

    def test_translations_loaded(self):
        """Verify translations are loaded for all supported languages."""
        assert i18n.LANG_EN in i18n._translations
        assert i18n.LANG_IT in i18n._translations
        assert i18n.LANG_DE in i18n._translations
        assert i18n.LANG_FR in i18n._translations
        assert i18n.LANG_ES in i18n._translations

    def test_english_translations_not_empty(self):
        """English translations should not be empty."""
        en_dict = i18n._translations.get(i18n.LANG_EN, {})
        assert len(en_dict) > 0

    def test_all_languages_have_same_keys(self):
        """All language dictionaries should have the same keys."""
        keys_by_lang = {}
        for lang in i18n.SUPPORTED_LANGUAGES:
            lang_dict = i18n._translations.get(lang, {})
            keys_by_lang[lang] = set(lang_dict.keys())

        # All should have the same keys as English
        en_keys = keys_by_lang.get(i18n.LANG_EN, set())
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
        result = i18n.tr("app.version").format(version="1.0.0")
        assert "1.0.0" in result


class TestCallbacks:
    """Test callback registration."""

    def test_register_language_callback(self):
        """Should be able to register a callback."""
        callback_called = []

        def my_callback():
            callback_called.append(True)

        i18n.register_language_callback(my_callback)
        assert my_callback in i18n._language_change_callbacks

    def test_unregister_language_callback(self):
        """Should be able to unregister a callback."""

        def my_callback():
            pass

        i18n.register_language_callback(my_callback)
        i18n.unregister_language_callback(my_callback)
        assert my_callback not in i18n._language_change_callbacks


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
