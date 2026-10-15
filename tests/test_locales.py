# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.locales modules."""

from hsync_desktop.locales import de, en, es, fr, it, ja, nl, pl, pt, ru, zh

ALL_MODULES = [en, it, de, fr, es, pt, zh, ru, nl, pl, ja]


class TestTranslationsPresent:
    """Every locale module exposes a non-empty string-to-string map."""

    def test_translations_dict_exists(self):
        for module in ALL_MODULES:
            assert hasattr(module, "translations"), module.__name__
            assert isinstance(module.translations, dict), module.__name__

    def test_translations_not_empty(self):
        for module in ALL_MODULES:
            assert len(module.translations) > 0, module.__name__

    def test_all_values_are_strings(self):
        for module in ALL_MODULES:
            for key, value in module.translations.items():
                assert isinstance(value, str), f"{module.__name__}:{key}"

    def test_app_name(self):
        for module in ALL_MODULES:
            assert module.translations["app.name"] == "HSYNC Desktop", module.__name__


class TestTranslationConsistency:
    """Test that all languages have consistent keys."""

    def test_all_languages_have_same_keys(self):
        """All languages should have the same translation keys as English."""
        en_keys = set(en.translations.keys())
        for module in ALL_MODULES:
            assert set(module.translations.keys()) == en_keys, (
                f"{module.__name__} has different keys than English"
            )


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

    def test_important_keys_exist_in_all_languages(self):
        """Important keys should exist in all languages."""
        for module in ALL_MODULES:
            for key in self.IMPORTANT_KEYS:
                assert key in module.translations, f"Missing key '{key}' in {module.__name__}"


class TestTerminologyConsistency:
    """Keep the visible wording coherent for non-technical users, in every locale.

    Guards the regression where the incompatibility warnings quoted an option
    name ("Force master") that no longer matched the checkbox label
    ("Force primary role"), and the leftover master/bootnode jargon.
    """

    ALL = ALL_MODULES

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


class TestAboutContent:
    """The splash / About content stays short and correctly attributed."""

    ALL = ALL_MODULES

    def test_tagline_is_short(self):
        for module in self.ALL:
            tagline = module.translations["app.tagline"]
            if any(ch.isspace() for ch in tagline):
                words = tagline.split()
                assert 3 <= len(words) <= 6, module.__name__
            else:
                # Space-less scripts (Chinese, Japanese) are measured by length.
                assert 4 <= len(tagline) <= 20, module.__name__

    def test_copyright_and_author_are_present(self):
        for module in self.ALL:
            assert module.translations["about.copyright"].startswith("Copyright ©")
            assert module.translations["about.author"] == "Alberto Basso"

    def test_about_menu_item_is_short(self):
        for module in self.ALL:
            label = module.translations["menu.help.about"]
            assert "HSYNC" not in label, module.__name__
