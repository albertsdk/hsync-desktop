# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.locales modules."""

import re
import string

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

    def test_identity_check_labels_are_plain_and_shared(self):
        """The three trust labels read just "Identity check" in every locale.

        Each field already sits in its own tab and group box (server, discovery
        server, primary device), so the label must not repeat the endpoint type;
        the three must stay identical so no locale drifts back to a typed wording
        (the previous "New primary device" drift).
        """
        keys = ("settings.server_trust", "settings.p2p_rendezvous_trust", "settings.p2p_trust")
        for module in ALL_MODULES:
            values = {module.translations[key] for key in keys}
            assert len(values) == 1, f"{module.__name__}: {sorted(values)}"


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


class TestStatusBarBadges:
    """A status-bar badge stays short: it shares one row with the status."""

    def test_badges_stay_a_badge_in_every_language(self):
        """A badge shares the status row with the status text and the other badge.

        The bound is the longest approved label (`simulation.badge` in Italian,
        38 chars); it exists to stop a translation from turning a badge into a
        sentence, not to police the approved wording.
        """
        for module in ALL_MODULES:
            for key in ("simulation.badge", "deletion.badge"):
                value = module.translations[key]
                assert len(value) <= 38, (
                    f"{module.__name__}: {key} is {len(value)} chars: {value!r}"
                )

    def test_deletion_badge_exists_in_every_language(self):
        for module in ALL_MODULES:
            assert module.translations["deletion.badge"].strip(), module.__name__
            assert module.translations["deletion.tip"].strip(), module.__name__


class TestTerminologyConsistency:
    """Keep the visible wording coherent for non-technical users, in every locale.

    Guards that the incompatibility warnings name the option exactly as its
    checkbox label reads, and that role/rendezvous wording avoids
    master/relay/rendezvous jargon.
    """

    ALL = ALL_MODULES

    # User-facing name of the `rdv/1` node in each locale. It helps devices find
    # each other (it never relays file data), so "relay", "rendezvous" and
    # "discovery" are jargon: the UI says "search server".
    RENDEZVOUS_TERMS = {
        "en": "search",
        "it": "ricerca",
        "de": "such",
        "fr": "recherche",
        "es": "búsqueda",
        "pt": "pesquisa",
        "zh": "搜索",
        "ru": "поиска",
        "nl": "zoek",
        "pl": "wyszukiwania",
        "ja": "検索",
    }

    # Locale-independent tokens that wrongly imply a data relay.
    RELAY_TOKENS = ("relay", "relais", "中继", "リレー", "ретрансляц", "przekaźnik")

    RENDEZVOUS_KEYS = (
        "settings.test_rendezvous_no_host",
        "settings.test_rendezvous_no_binary",
        "settings.test_rendezvous_success",
        "settings.test_rendezvous_failure",
        "settings.invalid_rendezvous_endpoint",
        "settings.p2p_rendezvous",
        "dialogs.rendezvous_trust_title",
        "dialogs.rendezvous_trust_body",
        "dialogs.rendezvous_unreachable",
        "trusted_keys.tabs_rendezvouss",
        "tip.p2p_mode",
        "tip.p2p_rendezvous",
        "tip.p2p_rendezvous_trust",
        "tip.manage_trusted_keys",
        "tip.test_rendezvous",
        "tip.p2p_key",
        "wizard.mode.remote_sync.desc",
        "wizard.connection.rendezvous_server",
        "wizard.connection.test_rendezvous_server_ok",
        "wizard.error.rendezvous_server_required",
        "wizard.error.rendezvous_server_invalid",
        "wizard.connection.rendezvous_server_unreachable",
        "wizard.tip.rendezvous_server",
    )

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

    def test_role_labels_name_the_role(self):
        """The status-bar pill says which role the device holds.

        "This device" (the previous secondary label) named the device instead and
        read as redundant next to the connection state, so the pair must stay
        symmetric and role-shaped in every locale.
        """
        assert en.translations["role.master"] == "Primary device"
        assert en.translations["role.client"] == "Secondary device"
        for module in self.ALL:
            primary = module.translations["role.master"].strip()
            secondary = module.translations["role.client"].strip()
            assert primary and secondary, module.__name__
            assert primary != secondary, module.__name__

    def test_rendezvous_terms_avoid_relay_jargon(self):
        """The rdv/1 node is a search server; the wording must never use a relay term."""
        for module in self.ALL:
            name = module.__name__.rsplit(".", 1)[-1]
            term = self.RENDEZVOUS_TERMS[name]
            for key in self.RENDEZVOUS_KEYS:
                text = module.translations[key].lower()
                assert term in text, f"{module.__name__}:{key}: missing {term!r}"
                for token in self.RELAY_TOKENS:
                    assert token not in text, f"{module.__name__}:{key}: {token!r}"

    def test_the_deletion_warning_quotes_the_visible_option(self):
        """The warning must name the option exactly as its label reads."""
        for module in self.ALL:
            label = module.translations["settings.deletion_policy_propagate"]
            assert label in module.translations["warn.deletion_policy_msg"], module.__name__

    def test_deletion_wording_describes_the_outcome(self):
        """The policy labels say what happens to a file, not "propagate"/"backup"."""
        tokens = (
            "propagat",
            "backup",
            "back-up",
            "sauvegarde",
            "copia de seguridad",
            "cópia de segurança",
            "резервн",
            "kopia zapasowa",
            "バックアップ",
            "备份",
        )
        for module in self.ALL:
            for key in (
                "settings.deletion_policy_propagate",
                "settings.deletion_policy_keep",
                "deletion.tip",
            ):
                text = module.translations[key].lower()
                for token in tokens:
                    assert token not in text, f"{module.__name__}:{key}: {token}"

    def test_the_scoped_sync_messages_name_no_direction(self):
        """*Send now* and *Receive now* share these messages, so they stay neutral.

        The direction is already carried by the action the user invoked (its
        button, banner title and log line); a message that says "nothing to
        send" after a Receive is wrong for half the cases it is shown in. Only
        the result messages split by direction. The tokens are the direction
        verbs each locale used while these strings still claimed one.
        """
        tokens_by_locale = {
            "en": ("send", "receiv"),
            "it": ("invio", "inviare", "ricev"),
            "de": ("senden", "empfang"),
            "es": ("enviar", "enviando", "recib"),
            "fr": ("envoi", "envoyer", "recevr", "reçoiv"),
            "nl": ("verzend", "ontvang"),
            "pl": ("wysył", "odbier"),
            "pt": ("enviar", "enviando", "receb"),
            "ru": ("отправ", "получ"),
            "zh": ("发送", "接收"),
            "ja": ("送信", "受信"),
        }
        for module in self.ALL:
            name = module.__name__.rsplit(".", 1)[-1]
            for key in (
                "sync.sel_peers_fmt",
                "sync.sel_no_devices_msg",
                "sync.sel_already_synced",
            ):
                text = module.translations[key].lower()
                for token in tokens_by_locale[name]:
                    assert token not in text, f"{module.__name__}:{key}: {token!r}"

    def test_the_file_table_uses_plain_column_names(self):
        """No locale falls back to the "ETA" tool jargon."""
        for module in self.ALL:
            assert module.translations["file.eta"].strip() != "ETA", module.__name__

    def test_the_mode_labels_never_use_the_p2p_acronym(self):
        """The modes are named by their mechanism: Direct mode and Server mode."""
        for module in self.ALL:
            for key in ("settings.p2p", "settings.server_mode", "tip.p2p_mode"):
                assert "p2p" not in module.translations[key].lower(), f"{module.__name__}:{key}"

    def test_device_finding_group_is_about_devices_only(self):
        """The settings group names device finding, not the search server."""
        for module in self.ALL:
            text = module.translations["settings.group.p2p_rendezvous"].lower()
            for token in self.RELAY_TOKENS:
                assert token not in text, f"{module.__name__}:{token!r}"

    def test_translation_placeholders_match_english(self):
        """Every locale keeps the same {placeholders} as English."""

        def fields(text):
            return {name for _, name, _, _ in string.Formatter().parse(text) if name}

        for module in self.ALL:
            for key, english in en.translations.items():
                assert fields(module.translations[key]) == fields(english), (
                    f"{module.__name__}:{key}"
                )

    def test_invite_carries_share_group_and_password(self):
        """The invite must let another device join the same share and group.

        Its labels are injected from the Connection-step keys, so the invite
        names every value exactly as the wizard asks for it.
        """
        for module in self.ALL:
            text = module.translations["wizard.success.invite_text"]
            fields = {name for _, name, _, _ in string.Formatter().parse(text) if name}
            assert fields == {
                "share_label",
                "group_label",
                "password_label",
                "bucket",
                "group",
                "password",
            }, module.__name__

    # Row labels that keep a colon because they sit next to a value
    # ("Size: 12 MB", "Devices: 2/3"). Every other string is a form caption or a
    # sentence and carries no trailing colon (see the settings/wizard layout).
    # ``group_key.caption`` is the label above the masked provisioning line.
    KEY_VALUE_KEYS = {
        "detail.devices",
        "detail.elements",
        "detail.filename",
        "detail.last_synced",
        "detail.filepath",
        "detail.modified",
        "detail.size",
        "detail.status",
        "group_key.caption",
        "label.bucket",
        "label.group",
        "label.peers",
        "label.received",
        "label.sent",
        "label.users",
    }

    def test_only_key_value_labels_end_with_a_colon(self):
        """Form captions take no colon; only ``label: value`` rows keep one."""
        for module in self.ALL:
            with_colon = {
                key
                for key, value in module.translations.items()
                if value.rstrip().endswith((":", "："))
            }
            assert with_colon == self.KEY_VALUE_KEYS, (
                module.__name__,
                with_colon ^ self.KEY_VALUE_KEYS,
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

    def test_sync_paused_warning_describes_the_skipped_cycle(self):
        """Deletion protection skips deletions for a cycle; the sync keeps running."""
        en_t = en.translations
        title = en_t["notif.sync_paused_title"].lower()
        msg = en_t["notif.sync_paused_msg"].lower()
        assert "paused" not in title and "paused" not in msg
        assert "skipped" in title and "skipped" in msg
        assert "advanced" in msg

    def test_connection_and_direction_warnings_use_label_wording(self):
        """Warnings reuse the settings labels, not raw protocol terms."""
        en_t = en.translations
        assert "certificate" in en_t["warn.api_key_insecure_msg"].lower()
        assert "receive only" in en_t["notif.deletion_risk_msg"].lower()

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
        "fr": "sens",
        "pt": "direção",
        "zh": "方向",
        "ru": "направление",
        "nl": "richting",
        "pl": "kierunek",
        "ja": "方向",
    }
    _JARGON_KEYS = (
        "settings.test_rendezvous_no_binary",
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

    def test_sync_direction_labels_name_the_direction(self):
        """The field and its menu read "sync direction" in every locale.

        The control is literally the direction of the transfer, and the tooltip
        already describes it that way: a locale that drifts back to a vague
        "type" fails here.
        """
        for module in self.ALL:
            name = module.__name__.rsplit(".", 1)[-1]
            for key in ("settings.sync_direction", "menu.sync.direction"):
                value = module.translations[key].lower()
                assert self._DIRECTION_WORD[name] in value, f"{module.__name__}:{key}"

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
                "settings.invalid_rendezvous_endpoint",
            ):
                value = module.translations[key].lower()
                assert "ipv6" not in value and "host:port" not in value, f"{module.__name__}:{key}"
                assert "example.com" in value or "example.net" in value, f"{module.__name__}:{key}"
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


class TestWizardTerminology:
    """The setup wizard strings exist everywhere and avoid topology jargon."""

    MODE_TITLE_KEYS = [
        "wizard.mode.backup.title",
        "wizard.mode.lan_sync.title",
        "wizard.mode.remote_sync.title",
        "wizard.mode.team_share.title",
    ]

    def test_wizard_keys_exist_in_all_locales(self):
        required = [
            "wizard.title",
            "wizard.subtitle",
            "wizard.success.title",
            "wizard.error.mode_required",
            "menu.setup_wizard",
            *self.MODE_TITLE_KEYS,
        ]
        for module in ALL_MODULES:
            for key in required:
                assert key in module.translations, f"{module.__name__}:{key}"

    def test_wizard_strings_avoid_role_and_relay_jargon(self):
        for module in ALL_MODULES:
            for key, value in module.translations.items():
                if key.startswith("wizard.") or key == "menu.setup_wizard":
                    lowered = value.lower()
                    assert "master" not in lowered, f"{module.__name__}:{key}"
                    for token in TestTerminologyConsistency.RELAY_TOKENS:
                        assert token not in lowered, f"{module.__name__}:{key}: {token!r}"


class TestWizardReusesSettingsLabels:
    """One caption per setting: the wizard labels a field with the Settings key.

    The wizard configures the same fields as Settings, so it must not keep a
    second copy of a caption. The only wizard-only controls are the single
    required search-server address, the two trust toggles, the password-required
    error and the status lines, which echo the reference sentences without their
    status glyph.
    """

    SETTINGS_LABELS = (
        "wizard.connection.group",
        "wizard.connection.password",
        "wizard.connection.server_url",
        "wizard.connection.api_key",
        "wizard.connection.share",
        "wizard.connection.direction",
        "wizard.connection.receive_only",
        "wizard.connection.rendezvous_transport",
        "wizard.connection.trust_ask",
        "wizard.connection.trust_save",
        "wizard.connection.testing",
        "wizard.automation.continuous",
        "wizard.automation.auto_sync",
        "wizard.automation.start_at_login",
    )

    def test_the_shared_fields_carry_no_wizard_copy(self):
        for module in ALL_MODULES:
            for key in self.SETTINGS_LABELS:
                assert key not in module.translations, f"{module.__name__}:{key}"

    def test_no_wizard_string_duplicates_a_settings_string(self):
        # Only these namespaces label settings fields: the step names, the mode
        # scenarios and the folder helpers are the wizard's own vocabulary.
        for module in ALL_MODULES:
            settings = {
                value for key, value in module.translations.items() if key.startswith("settings.")
            }
            for key, value in module.translations.items():
                if key.startswith(("wizard.connection.", "wizard.automation.")):
                    assert value not in settings, f"{module.__name__}:{key}"


class TestEllipsisPolicy:
    """Ellipsis only in the tray menu; the menu bar stays clean."""

    def test_tray_labels_have_ellipsis(self):
        for module in ALL_MODULES:
            assert module.translations["tray.settings"].endswith("…"), module.__name__
            assert module.translations["tray.setup_wizard"].endswith("…"), module.__name__

    def test_menu_bar_labels_have_no_ellipsis(self):
        for module in ALL_MODULES:
            assert not module.translations["menu.settings"].endswith("…"), module.__name__
            assert not module.translations["menu.setup_wizard"].endswith("…"), module.__name__


class TestModeOptionSentences:
    """The two connection-mode sentences are short and jargon-free."""

    KEYS = (
        "settings.p2p.description",
        "settings.server_mode.description",
    )

    def test_keys_exist_in_all_locales(self):
        for module in ALL_MODULES:
            for key in self.KEYS:
                assert key in module.translations, f"{module.__name__}:{key}"

    def test_descriptions_stay_short(self):
        # Must fit one or two lines at the 640 px dialog width. Space-less
        # scripts are measured by length instead of word count.
        for module in ALL_MODULES:
            for key in self.KEYS:
                text = module.translations[key]
                if any(ch.isspace() for ch in text):
                    assert len(text.split()) <= 24, f"{module.__name__}:{key}"
                else:
                    assert len(text) <= 70, f"{module.__name__}:{key}"

    def test_descriptions_avoid_topology_jargon(self):
        for module in ALL_MODULES:
            for key in self.KEYS:
                lowered = module.translations[key].lower()
                assert "master" not in lowered, f"{module.__name__}:{key}"
                for token in TestTerminologyConsistency.RELAY_TOKENS:
                    assert token not in lowered, f"{module.__name__}:{key}"

    def test_p2p_description_names_the_rendezvous_server(self):
        # The discovery-server option is the non-obvious part of the tab: every
        # locale must call it a discovery service, never a relay or a rendezvous.
        for module in ALL_MODULES:
            code = module.__name__.rsplit(".", 1)[-1]
            lowered = module.translations["settings.p2p.description"].lower()
            assert TestTerminologyConsistency.RENDEZVOUS_TERMS[code] in lowered, module.__name__
