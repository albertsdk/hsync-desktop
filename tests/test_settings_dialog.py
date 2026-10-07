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
                "--no-upnp",
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
            qtbot, monkeypatch, p2p_flags=["--force-master", "--port", "--no-upnp"]
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
