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
from PySide6.QtWidgets import QLineEdit, QMessageBox

from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import SettingsDialog


@pytest.fixture
def dialog(qtbot):
    """Create a SettingsDialog registered with qtbot for cleanup."""
    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


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
        is False)."""
        from hsync_common.protocol.capabilities import build_capabilities

        from hsync_desktop.settings import dialog as dialog_mod

        doc = build_capabilities(
            app_version="1.0.0",
            subcommands=["p2p"] if p2p_supported else ["server"],
            cli_options_by_subcommand={"p2p": list(p2p_flags)} if p2p_supported else {},
        )
        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: doc)
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        return dlg

    def test_unsupported_flag_disables_widget_and_label(self, qtbot, monkeypatch):
        dlg = self._make_dialog(qtbot, monkeypatch, p2p_flags=["--force-master"])
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
                "--force-master",
                "--never-master",
                "--require-pairing",
                "--port",
                "--upnp",
            ],
        )
        dlg.p2p_mode.setChecked(True)
        assert dlg.force_master.isEnabled()
        assert dlg.never_master.isEnabled()
        assert dlg.require_pairing.isEnabled()
        assert dlg.p2p_bootnode.isEnabled()
        assert dlg.p2p_upnp.isEnabled()
        assert not dlg._unsupported_widgets

    def test_bootnode_field_gated_on_the_port_flag(self, qtbot, monkeypatch):
        """The bootnode host/UPnP belong to the bootnode plan (its --port flag)."""
        dlg = self._make_dialog(
            qtbot, monkeypatch, p2p_flags=["--force-master", "--port", "--upnp"]
        )
        dlg.p2p_mode.setChecked(True)
        assert dlg.p2p_bootnode.isEnabled()
        dlg2 = self._make_dialog(qtbot, monkeypatch, p2p_flags=["--force-master"])
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
            p2p_flags=["--force-master", "--never-master"],
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
        from PySide6.QtWidgets import QFormLayout

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
        import pytest

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
        import pytest

        dialog.p2p_bootnode.setText("https://boot.example.net")
        with pytest.raises(ValueError):
            dialog._normalize_bootnode_endpoint()


class TestForceMasterLiveWarning:
    """Force-master vs. directional sync is also gated live, not only on save.

    The prompt is diversified by trigger: picking a non-bidirectional
    direction offers to disable force-master (Yes: toggle off + jump to the
    p2p tab), while enabling force-master offers to go back to a
    bidirectional sync (Yes: direction reset + jump to the sync tab). The
    save gate keeps its own "reset the direction" message.
    """

    @staticmethod
    def _reset_conflict_state(dialog):
        """Force the three widgets to a known state (the fixture loads the
        real QSettings, whose saved p2p flags would otherwise leak in)."""
        dialog.sync_direction_combo.setCurrentIndex(0)
        dialog.force_master.setChecked(False)
        dialog.p2p_mode.setChecked(False)

    @staticmethod
    def _arm_conflict_silently(dialog):
        """Reach the p2p+force-master+direction conflict without its live
        prompts (signals blocked, used by the save-gate tests)."""
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.force_master.blockSignals(True)
        dialog.force_master.setChecked(True)
        dialog.force_master.blockSignals(False)

    def test_conflict_requires_p2p_and_force_master_and_direction(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)
        assert dialog._force_master_conflict() is False  # still bidirectional
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only (No: kept)
        assert dialog._force_master_conflict() is True
        dialog.p2p_mode.setChecked(False)
        assert dialog._force_master_conflict() is False  # force-master inert w/o p2p
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(False)
        assert dialog._force_master_conflict() is False

    def test_direction_change_offers_disabling_force_master(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)  # still bidirectional: silent
        dialog.sync_direction_combo.setCurrentIndex(2)  # download-only
        assert shown == [tr("warn.force_master_disable_msg")]
        assert dialog.force_master.isChecked() is False  # disabled on "Yes"
        assert dialog.sync_direction_combo.currentData() == "download-only"
        assert dialog._tabs.currentIndex() == 2  # p2p tab

    def test_direction_change_yes_emits_toggle_signal(self, dialog, monkeypatch):
        """Regression: "Yes" must let the toggle's own `toggled` fire.

        Swallowing it with blockSignals froze the thumb animation, so the
        switch kept painting as ON while checked was False: clicking it on
        the p2p tab flipped it back to ON and re-triggered the enable
        prompt in a loop.
        """
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)
        emitted: list[bool] = []
        dialog.force_master.toggled.connect(emitted.append)
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only → prompt → Yes
        assert emitted == [False]
        assert dialog.force_master.isChecked() is False
        assert dialog._tabs.currentIndex() == 2  # p2p tab

    def test_never_master_enabling_emits_force_master_off_signal(self, dialog):
        """Same stale-paint cause in the mutual exclusion: the forced
        uncheck must reach the animation so force-master stops drawing ON."""
        self._reset_conflict_state(dialog)
        dialog.never_master.setChecked(False)
        dialog.force_master.setChecked(True)
        emitted: list[bool] = []
        dialog.force_master.toggled.connect(emitted.append)
        dialog.never_master.setChecked(True)
        assert emitted == [False]
        assert dialog.force_master.isChecked() is False

    def test_direction_change_cancel_keeps_state(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)
        start_tab = dialog._tabs.currentIndex()
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only
        assert shown == [tr("warn.force_master_disable_msg")]
        assert dialog.force_master.isChecked() is True  # untouched on "No"
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert dialog._tabs.currentIndex() == start_tab

    def test_force_master_enable_offers_bidirectional_sync(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)  # force off: silent
        expected = tr("warn.force_master_sync_msg").format(
            direction=dialog.sync_direction_combo.currentText()
        )
        dialog.force_master.setChecked(True)
        assert shown == [expected]
        assert dialog.force_master.isChecked() is True  # the toggle stays on
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert dialog._tabs.currentIndex() == 0  # sync tab

    def test_force_master_enable_cancel_keeps_direction(self, dialog, monkeypatch):
        shown = []

        def fake_exec(self):
            shown.append(self.text())
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        start_tab = dialog._tabs.currentIndex()
        dialog.force_master.setChecked(True)
        assert shown == [
            tr("warn.force_master_sync_msg").format(
                direction=dialog.sync_direction_combo.currentText()
            )
        ]
        assert dialog.force_master.isChecked() is True
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert dialog._tabs.currentIndex() == start_tab

    def test_force_master_enable_silent_when_bidirectional(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)  # bidirectional: no prompt
        assert calls == []

    def test_force_master_enable_silent_without_p2p_mode(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.force_master.setChecked(True)  # force-master inert w/o p2p
        assert calls == []

    def test_no_warning_without_p2p_mode(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.force_master.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        assert calls == []
        assert dialog.sync_direction_combo.currentData() == "upload-only"

    def test_no_warning_without_force_master(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        assert calls == []

    def test_no_warning_when_selecting_bidirectional(self, dialog, monkeypatch):
        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        self._arm_conflict_silently(dialog)
        dialog.sync_direction_combo.setCurrentIndex(0)  # back to bidirectional
        assert calls == []

    def test_load_does_not_trigger_warning(self, qtbot, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG

        calls = []

        def fake_exec(self):
            calls.append(True)
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        saved = {k: s.value(k) for k in ("sync/direction", "p2p/enabled", "p2p/force_master")}
        try:
            s.setValue("sync/direction", "upload-only")
            s.setValue("p2p/enabled", True)
            s.setValue("p2p/force_master", True)
            s.sync()
            dlg = SettingsDialog()
            qtbot.addWidget(dlg)
            assert calls == []
        finally:
            for key, value in saved.items():
                if value is None:
                    s.remove(key)
                else:
                    s.setValue(key, value)
            s.sync()

    def test_accept_gate_resets_direction_on_yes(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        saved = []
        msg_keys = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(True))
        monkeypatch.setattr(dialog, "accept", lambda: None)
        monkeypatch.setattr(
            dialog,
            "_maybe_warn_force_master",
            lambda msg_key, **fmt: msg_keys.append(msg_key) or True,
        )
        self._arm_conflict_silently(dialog)
        dialog.server_url.setText("")
        dialog.p2p_bootnode.setText("")
        dialog._on_accept()
        assert msg_keys == ["warn.force_master_msg"]  # save-gate message
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert saved == [True]

    def test_accept_gate_cancel_skips_save(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        saved = []
        msg_keys = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(True))
        monkeypatch.setattr(dialog, "accept", lambda: None)
        monkeypatch.setattr(
            dialog,
            "_maybe_warn_force_master",
            lambda msg_key, **fmt: msg_keys.append(msg_key) or False,
        )
        self._arm_conflict_silently(dialog)
        dialog.server_url.setText("")
        dialog.p2p_bootnode.setText("")
        dialog._on_accept()
        assert msg_keys == ["warn.force_master_msg"]  # save-gate message
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert saved == []


class TestIgnoreDeleteWarning:
    """Declining the ignore-delete warning restores the toggle; the restore
    must fire `toggled` too, otherwise the switch keeps painting as OFF
    while checked is True (same stale-paint cause as the force-master
    prompt loop).
    """

    def test_decline_emits_toggle_signal_and_keeps_checked(self, dialog, monkeypatch):
        def fake_exec(self):
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        dialog.ignore_delete.setChecked(True)  # known starting state
        emitted: list[bool] = []
        dialog.ignore_delete.toggled.connect(emitted.append)
        dialog.ignore_delete.setChecked(False)  # user unchecks → warning → "No"
        # The nested restore signal is delivered before the outer uncheck
        # finishes, so assert both emissions rather than their order.
        assert sorted(emitted) == [False, True]
        assert dialog.ignore_delete.isChecked() is True
