# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.i18n module."""

import pytest

import hsync_desktop.i18n as i18n


def _fake_qlocale(monkeypatch, name: str):
    """Replace ``QLocale`` with a stub reporting *name* as the system locale."""

    class _FakeQ:
        _locale_name = ""

        @classmethod
        def system(cls):
            return cls

        @classmethod
        def name(cls):
            return cls._locale_name

    _FakeQ._locale_name = name
    monkeypatch.setattr(i18n, "QLocale", _FakeQ)


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


class TestDetectSystemLanguage:
    """System-language detection resolves Qt first, Python's locale second."""

    @pytest.fixture(autouse=True)
    def _process_locale(self, monkeypatch):
        """Pin a process locale: these tests cover the process-level sources.

        A locale variable present is what keeps the machine-wide fallback out of
        the way (see ``TestSystemWideLocaleFallback``), so the assertions do not
        depend on the locale of the machine running the suite.
        """
        monkeypatch.setenv("LANG", "it_IT.UTF-8")

    def test_region_qualified_qlocale_resolves_to_its_base_code(self, monkeypatch):
        for locale_name, expected in [
            ("pt_BR", i18n.P2PG_PT),
            ("zh_CN", i18n.P2PG_ZH),
            ("ru_RU", i18n.P2PG_RU),
            ("nl_NL", i18n.P2PG_NL),
            ("pl_PL", i18n.P2PG_PL),
            ("ja_JP", i18n.P2PG_JA),
            ("it_IT", i18n.P2PG_IT),
        ]:
            _fake_qlocale(monkeypatch, locale_name)
            monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("C", "UTF-8"))
            assert i18n._detect_system_language() == expected

    def test_qt_locale_wins_over_the_c_locale(self, monkeypatch):
        # glibc reports LANG=it / it_IT@euro / ISO-8859-1 locales as
        # ("C", "UTF-8") before setlocale: Qt still resolves the real locale,
        # and that must win instead of falling back to English.
        _fake_qlocale(monkeypatch, "it_IT")
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("C", "UTF-8"))
        assert i18n._detect_system_language() == i18n.P2PG_IT

    def test_unsupported_qlocale_falls_back_to_python_locale(self, monkeypatch):
        _fake_qlocale(monkeypatch, "gsw_CH")
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("fr_FR", "UTF-8"))
        assert i18n._detect_system_language() == i18n.P2PG_FR

    def test_c_environment_falls_back_to_english(self, monkeypatch):
        _fake_qlocale(monkeypatch, "C")
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("C", "UTF-8"))
        assert i18n._detect_system_language() == i18n.P2PG_EN

    def test_unsupported_system_language_falls_back_to_english(self, monkeypatch):
        _fake_qlocale(monkeypatch, "C")
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("xx_XX", "UTF-8"))
        assert i18n._detect_system_language() == i18n.P2PG_EN


class TestSystemWideLocaleFallback:
    """A process started without a locale variable still has the machine's.

    ``sudo``, a service, a container or a launcher that drops the environment
    leaves Qt and Python on ``C``. Reading the machine-wide configuration is what
    keeps such a start in the user's language instead of silently falling back to
    English (the shipped build showed an English wizard on an ``it_IT.UTF-8``
    machine).
    """

    @staticmethod
    def _no_process_locale(monkeypatch):
        for name in i18n._LANGUAGE_ENV_VARS:
            monkeypatch.delenv(name, raising=False)

    @staticmethod
    def _c_locale(monkeypatch):
        """A stripped environment: both process-level sources report ``C``."""
        _fake_qlocale(monkeypatch, "C")
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("C", "UTF-8"))

    @staticmethod
    def _locale_files(monkeypatch, *contents: str, tmp_path):
        """Point the machine-wide lookup at temp files, in order."""
        paths = []
        for index, content in enumerate(contents):
            path = tmp_path / f"locale{index}.conf"
            path.write_text(content, encoding="utf-8")
            paths.append(str(path))
        monkeypatch.setattr(i18n, "_SYSTEM_LOCALE_FILES", tuple(paths))

    def test_no_locale_variable_uses_the_machine_wide_language(self, monkeypatch, tmp_path):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(monkeypatch, "LANG=it_IT.UTF-8\n", tmp_path=tmp_path)

        assert i18n._detect_system_language() == i18n.P2PG_IT

    def test_a_quoted_value_is_read(self, monkeypatch, tmp_path):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(monkeypatch, 'LANG="de_DE.UTF-8"\n', tmp_path=tmp_path)

        assert i18n._detect_system_language() == i18n.P2PG_DE

    def test_lc_all_decides_over_lang(self, monkeypatch, tmp_path):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(monkeypatch, "LANG=it_IT.UTF-8\nLC_ALL=fr_FR.UTF-8\n", tmp_path=tmp_path)

        assert i18n._detect_system_language() == i18n.P2PG_FR

    def test_an_empty_override_falls_through_to_the_next_key(self, monkeypatch, tmp_path):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(
            monkeypatch,
            "LC_ALL=\nLC_MESSAGES=pt_BR.UTF-8\nLANG=it_IT.UTF-8\n",
            tmp_path=tmp_path,
        )

        assert i18n._detect_system_language() == i18n.P2PG_PT

    def test_the_first_file_with_a_locale_decides(self, monkeypatch, tmp_path):
        # systemd's /etc/locale.conf comes before Debian's /etc/default/locale.
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(
            monkeypatch, "LANG=de_DE.UTF-8\n", "LANG=it_IT.UTF-8\n", tmp_path=tmp_path
        )

        assert i18n._detect_system_language() == i18n.P2PG_DE

    def test_a_missing_file_falls_through_to_the_next_one(self, monkeypatch, tmp_path):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(monkeypatch, "LANG=it_IT.UTF-8\n", tmp_path=tmp_path)
        monkeypatch.setattr(
            i18n,
            "_SYSTEM_LOCALE_FILES",
            (str(tmp_path / "absent.conf"), *i18n._SYSTEM_LOCALE_FILES),
        )

        assert i18n._detect_system_language() == i18n.P2PG_IT

    def test_no_machine_wide_locale_at_all_falls_back_to_english(self, monkeypatch, tmp_path):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        monkeypatch.setattr(i18n, "_SYSTEM_LOCALE_FILES", (str(tmp_path / "absent.conf"),))

        assert i18n._detect_system_language() == i18n.P2PG_EN

    def test_an_unsupported_machine_wide_language_falls_back_to_english(
        self, monkeypatch, tmp_path
    ):
        self._no_process_locale(monkeypatch)
        self._c_locale(monkeypatch)
        self._locale_files(monkeypatch, "LANG=sv_SE.UTF-8\n", tmp_path=tmp_path)

        assert i18n._detect_system_language() == i18n.P2PG_EN

    def test_an_explicit_c_locale_is_not_replaced_by_the_machine_wide_one(
        self, monkeypatch, tmp_path
    ):
        # ``LC_ALL=C`` is an explicit request for English and must never be
        # overridden by the machine's default.
        self._c_locale(monkeypatch)
        self._locale_files(monkeypatch, "LANG=it_IT.UTF-8\n", tmp_path=tmp_path)
        monkeypatch.setenv("LC_ALL", "C")

        assert i18n._detect_system_language() == i18n.P2PG_EN

    def test_a_process_locale_still_wins_over_the_machine_wide_one(self, monkeypatch, tmp_path):
        _fake_qlocale(monkeypatch, "de_DE")
        monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("de_DE", "UTF-8"))
        self._locale_files(monkeypatch, "LANG=it_IT.UTF-8\n", tmp_path=tmp_path)
        monkeypatch.setenv("LANG", "de_DE.UTF-8")

        assert i18n._detect_system_language() == i18n.P2PG_DE


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
