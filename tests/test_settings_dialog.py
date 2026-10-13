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

    def test_manage_trusted_keys_button_opens_dialog(self, dialog, monkeypatch):
        from hsync_desktop.settings import dialog as dialog_mod

        opened: list[str] = []

        class _Fake:
            def exec(self):
                opened.append("yes")
                return 0

        monkeypatch.setattr(dialog_mod, "TrustedKeysDialog", lambda parent: _Fake())
        dialog.btn_manage_trusted_keys.click()
        assert opened == ["yes"]


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

    Selecting a non-bidirectional direction while p2p mode and force-master are
    both on shows the same incompatibility prompt used by the save gate; on
    "Yes" the direction is reset and the p2p tab is brought forward.
    """

    @staticmethod
    def _reset_conflict_state(dialog):
        """Force the three widgets to a known state (the fixture loads the
        real QSettings, whose saved p2p flags would otherwise leak in)."""
        dialog.sync_direction_combo.setCurrentIndex(0)
        dialog.force_master.setChecked(False)
        dialog.p2p_mode.setChecked(False)

    @staticmethod
    def _enable_conflict(dialog):
        """Activate p2p mode + force-master (the two required toggles)."""
        dialog.p2p_mode.setChecked(True)
        dialog.force_master.setChecked(True)

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

    def test_direction_change_warns_resets_and_shows_p2p_tab(self, dialog, monkeypatch):
        shown = {}

        def fake_exec(self):
            shown["value"] = True
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        self._reset_conflict_state(dialog)
        self._enable_conflict(dialog)
        dialog.sync_direction_combo.setCurrentIndex(2)  # download-only
        assert shown.get("value") is True
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert dialog._tabs.currentIndex() == 2  # p2p tab

    def test_direction_change_cancel_keeps_direction(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        self._enable_conflict(dialog)
        start_tab = dialog._tabs.currentIndex()
        dialog.sync_direction_combo.setCurrentIndex(1)  # upload-only
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert dialog._tabs.currentIndex() == start_tab

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
        dialog.sync_direction_combo.setCurrentIndex(1)  # p2p still off: silent
        self._enable_conflict(dialog)
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
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
        self._reset_conflict_state(dialog)
        saved = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(True))
        monkeypatch.setattr(dialog, "accept", lambda: None)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.force_master.setChecked(True)
        dialog.server_url.setText("")
        dialog.p2p_bootnode.setText("")
        dialog._on_accept()
        assert dialog.sync_direction_combo.currentData() == "bidirectional"
        assert saved == [True]

    def test_accept_gate_cancel_skips_save(self, dialog, monkeypatch):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        self._reset_conflict_state(dialog)
        saved = []
        monkeypatch.setattr(dialog, "save", lambda: saved.append(True))
        monkeypatch.setattr(dialog, "accept", lambda: None)
        dialog.p2p_mode.setChecked(True)
        dialog.sync_direction_combo.setCurrentIndex(1)
        dialog.force_master.setChecked(True)
        dialog.server_url.setText("")
        dialog.p2p_bootnode.setText("")
        dialog._on_accept()
        assert dialog.sync_direction_combo.currentData() == "upload-only"
        assert saved == []
