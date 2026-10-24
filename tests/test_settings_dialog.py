# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the SettingsDialog security gates.

Covers the API-key security constraint of the desktop settings:

* ``_confirm_insecure_api_key`` - the API key is never sent over an
  ``http://`` URL or with SSL verification disabled without an explicit
  user confirmation.
"""

from __future__ import annotations

import pytest
from hsync_common import defaults
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import _P2P_TAB_INDEX, _SERVER_TAB_INDEX, SettingsDialog


class TestInsecureApiKeyGate:
    """The API key is gated against insecure transports."""

    def test_skipped_in_p2p_mode(self, dialog):
        dialog.p2p_mode.setChecked(True)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is True

    def test_allowed_when_api_key_empty(self, dialog):
        dialog.p2p_mode.setChecked(False)
        dialog.api_key.setText("")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is True

    def test_allowed_when_https_and_verify(self, dialog):
        dialog.p2p_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("https://host")
        dialog.insecure.setChecked(False)
        assert dialog._confirm_insecure_api_key() is True

    def test_warns_on_http_url_and_user_cancels(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        dialog.p2p_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is False

    def test_warns_on_http_url_and_user_proceeds(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
        dialog.p2p_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("http://host")
        assert dialog._confirm_insecure_api_key() is True

    def test_warns_when_skip_ssl_enabled(self, dialog, monkeypatch):
        shown = {}

        def fake_exec(self):
            shown["value"] = True
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        dialog.p2p_mode.setChecked(False)
        dialog.api_key.setText("secret")
        dialog.server_url.setText("https://host")
        dialog.insecure.setChecked(True)
        assert dialog._confirm_insecure_api_key() is False
        assert shown.get("value") is True


class TestCapabilityGating:
    """p2p toggles are gated by the binary's advertised capabilities."""

    def _make_dialog(self, qtbot, monkeypatch, p2p_supported=True, p2p_flags=()):
        """Build a dialog whose binary advertises the ``p2p`` subcommand with
        exactly ``p2p_flags`` (or no ``p2p`` subcommand when ``p2p_supported``
        is False). The maintenance ``state`` subcommand is always advertised, so
        this fixture exercises the p2p gates only."""
        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop.settings import dialog as dialog_mod

        doc = build_capabilities(
            app_version="1.0.0",
            subcommands=["p2p", "state"] if p2p_supported else ["server", "state"],
            cli_options_by_subcommand=({"p2p": list(p2p_flags)} if p2p_supported else {}),
        )
        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: doc)
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        return dlg

    def test_unsupported_flag_disables_widget_and_label(self, qtbot, monkeypatch):
        dlg = self._make_dialog(qtbot, monkeypatch, p2p_flags=["--prefer-master"])
        dlg.p2p_mode.setChecked(True)
        assert not dlg.never_master.isEnabled()
        assert not dlg.require_pairing.isEnabled()
        assert not dlg._lbl_never_master.isEnabled()
        assert dlg.never_master.toolTip() == tr("tip.capability_unsupported")

    def test_supported_flags_remain_enabled(self, qtbot, monkeypatch):
        dlg = self._make_dialog(
            qtbot,
            monkeypatch,
            p2p_flags=[
                "--prefer-master",
                "--never-master",
                "--require-pairing",
                "--port",
                "--upnp",
                "--no-autotune",
                "--max-concurrent-transfers",
                "--no-delta",
                "--delta-min-file-size",
                "--delta-min-file-size-p2p",
                "--mass-delete-guard",
                "--mass-delete-threshold",
                "--mass-delete-percent",
                "--limit-upload",
                "--limit-download",
                "--no-peer-download",
            ],
        )
        dlg.p2p_mode.setChecked(True)
        assert dlg.prefer_master.isEnabled()
        assert dlg.never_master.isEnabled()
        assert dlg.require_pairing.isEnabled()
        assert dlg.p2p_bootnode.isEnabled()
        assert dlg.p2p_upnp.isEnabled()
        assert not dlg._unsupported_widgets

    def test_bootnode_field_gated_on_the_port_flag(self, qtbot, monkeypatch):
        """The bootnode host/UPnP belong to the bootnode plan (its --port flag)."""
        dlg = self._make_dialog(
            qtbot, monkeypatch, p2p_flags=["--prefer-master", "--port", "--upnp"]
        )
        dlg.p2p_mode.setChecked(True)
        assert dlg.p2p_bootnode.isEnabled()
        dlg2 = self._make_dialog(qtbot, monkeypatch, p2p_flags=["--prefer-master"])
        dlg2.p2p_mode.setChecked(True)
        assert not dlg2.p2p_bootnode.isEnabled()
        assert dlg2.p2p_bootnode.toolTip() == tr("tip.capability_unsupported")

    def test_p2p_mode_unsupported_disables_toggle(self, qtbot, monkeypatch):
        dlg = self._make_dialog(qtbot, monkeypatch, p2p_supported=False)
        assert not dlg.p2p_mode.isEnabled()
        assert dlg.p2p_mode.toolTip() == tr("tip.capability_unsupported")

    def test_unknown_capabilities_leave_controls_enabled(self, qtbot, monkeypatch):
        from hsync_desktop.settings import dialog as dialog_mod

        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: None)
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        dlg.p2p_mode.setChecked(True)
        assert dlg.never_master.isEnabled()
        assert dlg.require_pairing.isEnabled()
        assert not dlg._unsupported_widgets

    def test_unsupported_widget_is_unchecked(self, qtbot, monkeypatch):
        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop.settings import dialog as dialog_mod

        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: None)
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        dlg.never_master.setChecked(True)
        doc = build_capabilities(
            app_version="1.0.0", subcommands=["p2p"], cli_options_by_subcommand={"p2p": []}
        )
        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: doc)
        dlg._apply_capabilities()
        assert not dlg.never_master.isChecked()
        assert not dlg.never_master.isEnabled()

    def test_unsupported_widget_stays_disabled_after_connection_cycle(self, qtbot, monkeypatch):
        dlg = self._make_dialog(
            qtbot,
            monkeypatch,
            p2p_flags=["--prefer-master", "--never-master"],
        )
        dlg.p2p_mode.setChecked(True)
        assert not dlg.require_pairing.isEnabled()


class TestBootnodeTrustPolicy:
    """The bootnode trust policy is a combo offering the four ADR-0035 policies."""

    def test_combo_offers_the_four_policies_and_defaults_to_ask(self, dialog):
        combo = dialog.p2p_bootnode_trust
        assert [combo.itemData(i) for i in range(combo.count())] == [
            "ask",
            "accept-new",
            "strict",
            "none",
        ]
        assert combo.currentData() == "ask"

    def test_label_sits_in_form_label_column(self, dialog):
        """The trust label aligns under Bootnode, not inside the field row."""

        layout = dialog.p2p_bootnode_trust.parent().layout()
        assert layout is not None
        assert dialog.p2p_bootnode_trust.parent() is not dialog._lbl_p2p_bootnode_trust.parent()
        form = dialog.p2p_bootnode.parentWidget().layout()
        assert isinstance(form, QFormLayout)
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if field_item is not None and field_item.widget() is dialog.p2p_bootnode:
                bootnode_row = row
                break
        else:
            raise AssertionError("bootnode field not in form layout")
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label_item is not None and label_item.widget() is dialog._lbl_p2p_bootnode_trust:
                trust_row = row
                break
        else:
            raise AssertionError("trust label not in form label column")
        assert trust_row == bootnode_row + 1


class TestTrustedKeysUi:
    """The fingerprint field is gone; the store is managed via the dialog."""

    def test_bootnode_fingerprint_widget_is_absent(self, dialog):
        assert dialog.findChild(QLineEdit, "p2pBootnodeFingerprint") is None

    def test_manage_trusted_keys_buttons_open_the_matching_tab(self, dialog, monkeypatch):
        from hsync_desktop.settings import dialog as dialog_mod

        opened: list[str] = []

        class _Fake:
            def __init__(self, parent, *, initial_tab="bootnodes"):
                self._tab = initial_tab

            def exec(self):
                opened.append(self._tab)
                return 0

        monkeypatch.setattr(dialog_mod, "TrustedKeysDialog", _Fake)
        # Each button is only clickable in its own mode (p2p / server).
        dialog.p2p_mode.setChecked(True)
        dialog.btn_manage_trusted_keys.click()
        dialog.p2p_mode.setChecked(False)
        dialog.btn_manage_trusted_keys_server.click()
        assert opened == ["bootnodes", "servers"]


class TestServerTrustPolicy:
    """The server trust combo replaces the dead fingerprint field (ADR-0036)."""

    def test_combo_offers_the_five_policies_and_defaults_to_chain(self, dialog):
        combo = dialog.server_trust
        assert [combo.itemData(i) for i in range(combo.count())] == [
            "chain",
            "ask",
            "accept-new",
            "strict",
            "none",
        ]
        assert combo.currentData() == "chain"

    def test_server_cert_fingerprint_widget_is_absent(self, dialog):
        assert dialog.findChild(QLineEdit, "serverCertFingerprint") is None

    def test_test_connection_ssl_context_follows_the_policy(self, dialog):
        import ssl

        # chain -> standard verification
        dialog.server_trust.setCurrentIndex(dialog.server_trust.findData("chain"))
        assert dialog._test_connection_ssl_context().verify_mode == ssl.CERT_REQUIRED
        # none -> no verification
        dialog.server_trust.setCurrentIndex(dialog.server_trust.findData("none"))
        assert dialog._test_connection_ssl_context().verify_mode == ssl.CERT_NONE
        # strict (pinning) -> no chain verification (the pin is the trust anchor)
        dialog.server_trust.setCurrentIndex(dialog.server_trust.findData("strict"))
        assert dialog._test_connection_ssl_context().verify_mode == ssl.CERT_NONE

    def test_combo_is_disabled_in_p2p_mode(self, dialog):
        dialog.p2p_mode.setChecked(False)
        assert dialog.server_trust.isEnabled()
        dialog.p2p_mode.setChecked(True)
        assert not dialog.server_trust.isEnabled()

    def test_combo_is_disabled_while_a_sync_is_active(self, dialog):
        dialog.p2p_mode.setChecked(False)
        dialog.set_connection_active(True)
        assert not dialog.server_trust.isEnabled()
        dialog.set_connection_active(False)
        assert dialog.server_trust.isEnabled()

    def test_manage_keys_button_is_disabled_in_p2p_mode(self, dialog):
        dialog.p2p_mode.setChecked(False)
        assert dialog.btn_manage_trusted_keys_server.isEnabled()
        dialog.p2p_mode.setChecked(True)
        assert not dialog.btn_manage_trusted_keys_server.isEnabled()


class TestP2pPanelGating:
    """The p2p trust controls disable with the panel when server mode is active."""

    def test_trust_controls_disabled_when_p2p_is_off(self, dialog):
        dialog.p2p_mode.setChecked(True)
        assert dialog.p2p_bootnode_trust.isEnabled()
        assert dialog.btn_manage_trusted_keys.isEnabled()
        dialog.p2p_mode.setChecked(False)
        assert not dialog.p2p_bootnode_trust.isEnabled()
        assert not dialog.btn_manage_trusted_keys.isEnabled()

    def test_trust_controls_disabled_while_a_sync_is_active(self, dialog):
        dialog.p2p_mode.setChecked(True)
        dialog.set_connection_active(True)
        assert not dialog.p2p_bootnode_trust.isEnabled()
        assert not dialog.btn_manage_trusted_keys.isEnabled()
        dialog.set_connection_active(False)
        assert dialog.p2p_bootnode_trust.isEnabled()
        assert dialog.btn_manage_trusted_keys.isEnabled()


class TestEndpointNormalization:
    """Server/bootnode fields validate + normalize through the shared grammar."""

    def test_server_url_normalizes_bare_host(self, dialog):
        dialog.server_url.setText("host.example.com")
        assert dialog._normalize_server_endpoint() == "https://host.example.com:9753"

    def test_server_url_ipv6_with_port(self, dialog):
        dialog.server_url.setText("[::1]:8443")
        assert dialog._normalize_server_endpoint() == "https://[::1]:8443"

    def test_server_url_rejects_http(self, dialog):

        dialog.server_url.setText("http://host.example.com")
        with pytest.raises(ValueError):
            dialog._normalize_server_endpoint()

    def test_bootnode_normalizes_ipv6_composite(self, dialog):
        dialog.p2p_bootnode.setText("[::1]:8443")
        assert dialog._normalize_bootnode_endpoint() == "[::1]:8443"

    def test_bootnode_bare_ipv6_is_unbracketed(self, dialog):
        dialog.p2p_bootnode.setText("[::1]")
        assert dialog._normalize_bootnode_endpoint() == "::1"

    def test_bootnode_rejects_scheme(self, dialog):

        dialog.p2p_bootnode.setText("https://boot.example.net")
        with pytest.raises(ValueError):
            dialog._normalize_bootnode_endpoint()


def _isolated_dialog(qtbot, monkeypatch, tmp_path):
    """A SettingsDialog backed by an isolated INI store (never the real config)."""
    from PySide6.QtCore import QSettings

    import hsync_desktop.i18n as i18n_mod
    import hsync_desktop.settings.dialog as dialog_mod

    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: store)
    # ``set_language`` (called by ``save``) reads its own QSettings instance.
    monkeypatch.setattr(i18n_mod, "QSettings", lambda *a, **k: store)
    dlg = dialog_mod.SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg, store


class TestP2PGroupPersistence:
    """Clearing the p2p group name persists an empty value that is read back
    empty — the deleted group must not be resurrected as the default."""

    def test_clearing_the_group_saves_an_empty_value(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.p2p_group.setText("team-a")
        dlg.save()
        assert store.value("p2p/group", "sentinel", str) == "team-a"

        dlg.p2p_group.setText("")
        dlg.save()
        assert store.contains("p2p/group")
        assert store.value("p2p/group", "sentinel", str) == ""

    def test_group_is_saved_stripped(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.p2p_group.setText("  team-a  ")
        dlg.save()
        assert store.value("p2p/group", "sentinel", str) == "team-a"

    def test_empty_group_loads_back_empty(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        store.setValue("p2p/group", "")
        store.sync()

        dlg.load()

        assert dlg.p2p_group.text() == ""


class TestPreferMasterDirectionGuard:
    """Prefer-primary and a directional sync are mutually exclusive: declining
    the proposed fix must restore the invariant, not leave it broken."""

    @staticmethod
    def _non_bidirectional_index(dlg) -> int:
        for i in range(dlg.sync_direction_combo.count()):
            if dlg.sync_direction_combo.itemData(i) != "bidirectional":
                return i
        raise AssertionError("no non-bidirectional direction in the combo")

    def test_declining_reverts_the_direction_to_bidirectional(self, qtbot, monkeypatch, tmp_path):
        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.p2p_mode.setChecked(True)
        dlg.prefer_master.setChecked(True)
        monkeypatch.setattr(dlg, "_maybe_warn_prefer_master", lambda *a, **k: False)

        dlg.sync_direction_combo.setCurrentIndex(self._non_bidirectional_index(dlg))

        assert dlg.sync_direction_combo.currentData() == "bidirectional"
        assert dlg.prefer_master.isChecked() is True

    def test_accepting_disables_prefer_master(self, qtbot, monkeypatch, tmp_path):
        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.p2p_mode.setChecked(True)
        dlg.prefer_master.setChecked(True)
        monkeypatch.setattr(dlg, "_maybe_warn_prefer_master", lambda *a, **k: True)

        dlg.sync_direction_combo.setCurrentIndex(self._non_bidirectional_index(dlg))

        assert dlg.prefer_master.isChecked() is False

    def test_declining_prefer_master_reverts_the_toggle(self, qtbot, monkeypatch, tmp_path):
        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.p2p_mode.setChecked(True)
        dlg.sync_direction_combo.setCurrentIndex(self._non_bidirectional_index(dlg))
        monkeypatch.setattr(dlg, "_maybe_warn_prefer_master", lambda *a, **k: False)

        dlg.prefer_master.setChecked(True)

        assert dlg.prefer_master.isChecked() is False
        assert dlg.sync_direction_combo.currentData() != "bidirectional"


class TestLanguageCombo:
    """The language list is alphabetical by endonym and never translated."""

    def test_listed_alphabetically_by_endonym(self, dialog):
        from hsync_desktop.i18n import AUTO_LANGUAGE, SUPPORTED_LANGUAGES

        # Item 0 is the "System default" entry; the rest are the endonyms.
        assert dialog.lang_combo.itemData(0) == AUTO_LANGUAGE
        names = [dialog.lang_combo.itemText(i) for i in range(1, dialog.lang_combo.count())]

        assert len(names) == len(SUPPORTED_LANGUAGES)
        assert names == sorted(names, key=str.casefold)


class TestLanguageAutoDefault:
    """The default preference is "System default" (follow the system locale)."""

    def test_default_selection_is_system(self, qtbot, monkeypatch, tmp_path):
        from hsync_desktop.i18n import AUTO_LANGUAGE

        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)

        assert dlg.lang_combo.currentData() == AUTO_LANGUAGE

    def test_saving_persists_the_auto_sentinel(self, qtbot, monkeypatch, tmp_path):
        import hsync_desktop.i18n as i18n_mod

        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        monkeypatch.setattr(i18n_mod, "_current_lang", i18n_mod.get_language())

        dlg.save()

        assert store.value("appearance/language", "sentinel", str) == i18n_mod.AUTO_LANGUAGE


class TestFontScalePersistence:
    """The global font-size preference round-trips and falls back safely."""

    def test_round_trips(self, qtbot, monkeypatch, tmp_path):
        from hsync_desktop.config import FONT_SCALE_COMPACT

        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.font_scale_combo.setCurrentIndex(dlg.font_scale_combo.findData(FONT_SCALE_COMPACT))
        dlg.save()
        assert store.value("appearance/font_scale", "", str) == FONT_SCALE_COMPACT

        dlg.font_scale_combo.setCurrentIndex(0)
        dlg.load()
        assert dlg.font_scale_combo.currentData() == FONT_SCALE_COMPACT

    def test_unknown_saved_value_falls_back_to_standard(self, qtbot, monkeypatch, tmp_path):
        from hsync_desktop.config import FONT_SCALE_STANDARD

        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        store.setValue("appearance/font_scale", "huge")
        store.sync()

        dlg.load()

        assert dlg.font_scale_combo.currentData() == FONT_SCALE_STANDARD


class TestTimeSettingFloors:
    """Too-small intervals are rejected at the widget/load boundary."""

    def test_resync_snaps_between_zero_and_the_minimum(self, qtbot, monkeypatch, tmp_path):
        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)

        dlg.resync.setValue(5)
        assert dlg.resync.value() == 20
        dlg.resync.setValue(0)
        assert dlg.resync.value() == 0

    def test_defaults_are_permissive_and_bounded(self, qtbot, monkeypatch, tmp_path):
        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)

        assert dlg.max_wait.value() == defaults.MAX_WAIT_TIMEOUT_DEFAULT
        assert dlg.max_wait.minimum() == 60
        assert dlg.retry_delay.minimum() == 5
        assert dlg.http_timeout.minimum() == 5
        assert dlg.discovery_timeout.minimum() == 5
        assert dlg.resync.maximum() == 3600


class TestGeneralAppearanceOrder:
    """The font-size selector sits immediately below Theme."""

    def test_font_size_row_is_immediately_below_theme(self, dialog):
        form = dialog.font_scale_combo.parentWidget().layout()
        assert isinstance(form, QFormLayout)

        def row_of(widget):
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item is not None and item.widget() is widget:
                    return row
            return -1

        assert row_of(dialog.font_scale_combo) == row_of(dialog.theme_combo) + 1


class TestNotificationCategoriesUi:
    """The master switch gates the per-event category toggles."""

    def test_master_toggle_disables_the_category_group(self, dialog):
        dialog.notifications_enabled.setChecked(False)
        assert not dialog.notification_group.isEnabled()

        dialog.notifications_enabled.setChecked(True)
        assert dialog.notification_group.isEnabled()

    def test_categories_default_to_enabled(self, qtbot, monkeypatch, tmp_path):
        dlg, _store = _isolated_dialog(qtbot, monkeypatch, tmp_path)

        assert all(toggle.isChecked() for toggle, _label in dlg.notification_toggles.values())

    def test_categories_round_trip(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _isolated_dialog(qtbot, monkeypatch, tmp_path)
        dlg.notification_toggles["peers"][0].setChecked(False)
        dlg.save()

        assert store.value("appearance/notifications/peers", True, bool) is False

        dlg.notification_toggles["peers"][0].setChecked(True)
        dlg.load()

        assert dlg.notification_toggles["peers"][0].isChecked() is False
