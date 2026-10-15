# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.locales modules."""

import hsync_desktop.locales.de as de
import hsync_desktop.locales.en as en
import hsync_desktop.locales.es as es
import hsync_desktop.locales.fr as fr
import hsync_desktop.locales.it as it


class TestEnglishTranslations:
    """Test English translations."""

    def test_translations_dict_exists(self):
        """English translations dict should exist."""
        assert hasattr(en, "translations")
        assert isinstance(en.translations, dict)

    def test_translations_not_empty(self):
        """English translations should not be empty."""
        assert len(en.translations) > 0

    def test_has_app_name(self):
        """Should have app.name translation."""
        assert "app.name" in en.translations
        assert en.translations["app.name"] == "HSYNC Desktop"


class TestItalianTranslations:
    """Test Italian translations."""

    def test_translations_dict_exists(self):
        """Italian translations dict should exist."""
        assert hasattr(it, "translations")
        assert isinstance(it.translations, dict)

    def test_translations_not_empty(self):
        """Italian translations should not be empty."""
        assert len(it.translations) > 0


class TestGermanTranslations:
    """Test German translations."""

    def test_translations_dict_exists(self):
        """German translations dict should exist."""
        assert hasattr(de, "translations")
        assert isinstance(de.translations, dict)

    def test_translations_not_empty(self):
        """German translations should not be empty."""
        assert len(de.translations) > 0


class TestFrenchTranslations:
    """Test French translations."""

    def test_translations_dict_exists(self):
        """French translations dict should exist."""
        assert hasattr(fr, "translations")
        assert isinstance(fr.translations, dict)

    def test_translations_not_empty(self):
        """French translations should not be empty."""
        assert len(fr.translations) > 0


class TestSpanishTranslations:
    """Test Spanish translations."""

    def test_translations_dict_exists(self):
        """Spanish translations dict should exist."""
        assert hasattr(es, "translations")
        assert isinstance(es.translations, dict)

    def test_translations_not_empty(self):
        """Spanish translations should not be empty."""
        assert len(es.translations) > 0


class TestTranslationConsistency:
    """Test that all languages have consistent keys."""

    def test_all_languages_have_same_keys(self):
        """All languages should have the same translation keys."""
        en_keys = set(en.translations.keys())
        it_keys = set(it.translations.keys())
        de_keys = set(de.translations.keys())
        fr_keys = set(fr.translations.keys())
        es_keys = set(es.translations.keys())

        assert en_keys == it_keys, "Italian has different keys than English"
        assert en_keys == de_keys, "German has different keys than English"
        assert en_keys == fr_keys, "French has different keys than English"
        assert en_keys == es_keys, "Spanish has different keys than English"

    def test_all_values_are_strings(self):
        """All translation values should be strings."""
        for lang_name, lang_module in [
            ("English", en),
            ("Italian", it),
            ("German", de),
            ("French", fr),
            ("Spanish", es),
        ]:
            for key, value in lang_module.translations.items():
                assert isinstance(value, str), f"{lang_name} key '{key}' is not a string"


class TestImportantTranslations:
    """Test that important translations exist in all languages."""

    IMPORTANT_KEYS = [
        "app.name",
        "btn.start",
        "btn.stop",
        "btn.settings",
        "status.connected",
        "status.disconnected",
        "settings.title",
    ]

    def test_important_keys_exist_in_english(self):
        """Important keys should exist in English."""
        for key in self.IMPORTANT_KEYS:
            assert key in en.translations, f"Missing key: {key}"

    def test_important_keys_exist_in_all_languages(self):
        """Important keys should exist in all languages."""
        all_modules = [en, it, de, fr, es]
        for key in self.IMPORTANT_KEYS:
            for lang_module in all_modules:
                assert key in lang_module.translations, (
                    f"Missing key '{key}' in {lang_module.__name__}"
                )


class TestTerminologyConsistency:
    """Keep the visible wording coherent for non-technical users, in every locale.

    Guards the regression where the incompatibility warnings quoted an option
    name ("Force master") that no longer matched the checkbox label
    ("Force primary role"), and the leftover master/bootnode jargon.
    """

    ALL = [en, it, de, fr, es]

    def test_force_role_warning_quotes_the_visible_label(self):
        """The warnings must name the option exactly as its label reads."""
        for module in self.ALL:
            label = module.translations["settings.force_master"]
            for key in (
                "warn.force_master_msg",
                "warn.force_master_disable_msg",
                "warn.force_master_sync_msg",
            ):
                assert label in module.translations[key], f"{module.__name__}:{key}"

    def test_role_terms_avoid_master_jargon(self):
        """Role labels and tips use primary/secondary, never 'master'."""
        for module in self.ALL:
            for key in (
                "role.master",
                "role.client",
                "role.master_tip",
                "role.client_tip",
                "tip.force_master",
                "tip.never_master",
            ):
                assert "master" not in module.translations[key].lower(), f"{module.__name__}:{key}"

    def test_relay_terms_avoid_bootnode_jargon(self):
        """User-facing strings call the bootnode a relay server."""
        for module in self.ALL:
            for key in (
                "settings.p2p_bootnode",
                "settings.p2p_bootnode_trust",
                "tip.p2p_bootnode",
                "trusted_keys.tabs_bootnodes",
                "dialogs.bootnode_trust_title",
            ):
                assert "bootnode" not in module.translations[key].lower(), (
                    f"{module.__name__}:{key}"
                )
