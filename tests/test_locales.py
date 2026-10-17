# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.locales modules."""

import re

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

    Guards that the incompatibility warnings name the option exactly as its
    checkbox label reads, and that role/relay wording avoids master/bootnode
    jargon.
    """

    ALL = ALL_MODULES

    def test_prefer_role_warning_quotes_the_visible_label(self):
        """The warnings must name the option exactly as its label reads."""
        for module in self.ALL:
            label = module.translations["settings.prefer_master"]
            for key in (
                "warn.prefer_master_msg",
                "warn.prefer_master_disable_msg",
                "warn.prefer_master_sync_msg",
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
                "tip.prefer_master",
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

    def test_p2p_warning_names_the_credential_like_its_label(self):
        """The keyless-run prompt says "shared password", not "shared key"."""
        en_t = en.translations
        for key in ("warn.keyless_p2p_title", "warn.keyless_p2p_msg", "p2pauth.retrying"):
            assert "password" in en_t[key].lower(), key
        assert "shared key" not in en_t["warn.keyless_p2p_title"].lower()

    def test_p2p_warning_avoids_peer_and_node_jargon(self):
        """Warnings and tooltips call peers "devices", never "peers"/"nodes"."""
        en_t = en.translations
        body = en_t["warn.keyless_p2p_msg"].lower()
        assert "peer" not in body and "node" not in body, body
        assert "devices" in body
        assert "peer" not in en_t["tip.p2p_group"].lower()

    def test_p2p_mode_is_spelled_lowercase_across_locales(self):
        """The mode is written "p2p", matching every label that names it."""
        for module in self.ALL:
            body = module.translations["warn.keyless_p2p_msg"]
            assert "P2P" not in body, module.__name__

    def test_sync_paused_warning_avoids_guard_jargon(self):
        """Deletion protection is worded plainly, never as a "guard"."""
        for module in self.ALL:
            for key in ("notif.sync_paused_title", "notif.sync_paused_msg"):
                low = module.translations[key].lower()
                for token in ("guard", "garde", "guarda"):
                    assert re.search(rf"\b{token}\b", low) is None, (
                        f"{module.__name__}:{key}:{token}"
                    )
                assert "ガード" not in low, f"{module.__name__}:{key}"

    def test_connection_and_direction_warnings_use_label_wording(self):
        """Warnings reuse the settings labels, not raw protocol terms."""
        en_t = en.translations
        assert "certificate" in en_t["warn.api_key_insecure_msg"].lower()
        assert "receive" in en_t["notif.deletion_risk_download"].lower()

    # Locale token maps for the terminology guards below. Inflected languages are
    # matched on a stem: the guard only needs to catch the jargon, not the case.
    _BINARY = {
        "en": "binary",
        "it": "binario",
        "de": "binär",
        "es": "binario",
        "fr": "binaire",
        "pt": "binário",
        "zh": "二进制",
        "ru": "двоичн",
        "nl": "binary",
        "pl": "binar",
        "ja": "バイナリ",
    }
    _NODE = {
        "en": "node",
        "it": "nodo",
        "de": "knoten",
        "es": "nodo",
        "fr": "nœud",
        "pt": "nó",
        "zh": "节点",
        "ru": "узл",
        "nl": "node",
        "pl": "węzł",
        "ja": "ノード",
    }
    _DIRECTION_WORD = {
        "en": "direction",
        "it": "direzione",
        "de": "richtung",
        "es": "dirección",
        "fr": "direction",
        "pt": "direção",
        "zh": "方向",
        "ru": "направление",
        "nl": "richting",
        "pl": "kierunek",
        "ja": "方向",
    }
    _JARGON_KEYS = (
        "settings.test_bootnode_no_binary",
        "dialogs.trust_failed",
        "trusted_keys.failed",
        "trusted_keys.capability_missing",
        "tip.capability_unsupported",
    )

    def test_server_mode_is_not_called_cloud(self):
        """The tab is "Server Mode" in every locale, matching the fields in it."""
        for module in self.ALL:
            assert "cloud" not in module.translations["settings.server_mode"].lower(), (
                module.__name__
            )

    def test_engine_terms_avoid_binary_jargon(self):
        """Messages call the bundled component a "sync engine", never a binary."""
        for module in self.ALL:
            token = self._BINARY[module.__name__.rsplit(".", 1)[-1]]
            for key in self._JARGON_KEYS:
                assert token not in module.translations[key].lower(), f"{module.__name__}:{key}"

    def test_read_from_uses_server_not_node(self):
        """The trusted-key dialog reads from a server, not from a node."""
        for module in self.ALL:
            token = self._NODE[module.__name__.rsplit(".", 1)[-1]]
            value = module.translations["trusted_keys.read_from_node"].lower()
            assert token not in value, f"{module.__name__}:trusted_keys.read_from_node"

    def test_primary_role_prompts_quote_the_visible_label(self):
        """Deletion-risk and force-role text name the option as its label reads."""
        for module in self.ALL:
            label = module.translations["settings.prefer_master"]
            assert label in module.translations["notif.deletion_risk_p2p"], module.__name__

    def test_duplicate_identity_uses_device_id_label(self):
        """The duplicate-identity warning names the identifier as its label does."""
        for module in self.ALL:
            label = module.translations["trusted_keys.device_id"].lower()
            value = module.translations["notif.duplicate_identity_msg"].lower()
            assert label in value, f"{module.__name__}:notif.duplicate_identity_msg"

    def test_direction_wording_drops_bidirectional_jargon(self):
        """Direction term is the visible option, not the protocol word."""
        for module in self.ALL:
            direction = module.translations["settings.sync_direction.bidirectional"]
            assert "bidirec" not in direction.lower(), module.__name__
            for key in (
                "warn.prefer_master_msg",
                "warn.prefer_master_disable_msg",
                "warn.prefer_master_sync_msg",
            ):
                assert "bidirec" not in module.translations[key].lower(), f"{module.__name__}:{key}"
            assert direction in module.translations["warn.prefer_master_msg"], module.__name__

    def test_sync_type_labels_are_not_called_direction(self):
        """The field and its menu read "sync type" in every locale."""
        for module in self.ALL:
            token = self._DIRECTION_WORD[module.__name__.rsplit(".", 1)[-1]]
            for key in ("settings.sync_direction", "menu.sync.direction"):
                value = module.translations[key].lower()
                assert token not in value, f"{module.__name__}:{key}"

    def test_endpoint_warnings_avoid_raw_host_grammar(self):
        """Invalid-endpoint prompts give an example, not host/port/IPv6 grammar."""
        server_word = {
            "en": "server",
            "de": "server",
            "es": "servidor",
            "fr": "serveur",
            "it": "server",
            "ja": "サーバー",
            "nl": "server",
            "pl": "serwer",
            "pt": "servidor",
            "ru": "сервер",
            "zh": "服务器",
        }
        for module in self.ALL:
            for key in (
                "settings.invalid_server_endpoint",
                "settings.invalid_bootnode_endpoint",
            ):
                value = module.translations[key].lower()
                assert "ipv6" not in value and "host:port" not in value, f"{module.__name__}:{key}"
                assert "example.com" in value, f"{module.__name__}:{key}"
            code = module.__name__.rsplit(".", 1)[-1]
            assert (
                server_word[code] in module.translations["settings.test_connection_failure"].lower()
            ), module.__name__


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
