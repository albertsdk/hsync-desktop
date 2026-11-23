# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the SettingsDialog security gates.

Covers the API-key security constraint of the desktop settings:

* ``_confirm_insecure_api_key`` - the API key is never sent over an
  ``http://`` URL or with SSL verification disabled without an explicit
  user confirmation.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from hsync_desktop import docs_links
from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import (
    _ADVANCED_TAB_INDEX,
    _CONNECTION_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _SYNC_TAB_INDEX,
)
from hsync_desktop.widgets.text import escape_mnemonics


class TestConnectionPageStartsAtTheChoice:
    """The connection page explains itself through its options, not a purpose line.

    The two options carry the sentences, so the page opens straight on the choice
    and stays as tall as one mode. No settings tab has a purpose line: the group
    titles and the options read as their own index.
    """

    def test_the_mode_box_comes_first(self, dialog):
        content = dialog._tabs.widget(_CONNECTION_TAB_INDEX).layout().itemAt(0).widget()
        assert content is not None
        groups = content.findChildren(QGroupBox)
        assert groups[0] is dialog._grp_mode

    def test_the_option_sentences_stay_readable_while_a_mode_is_hidden(self, dialog):
        dialog.mode_direct.setChecked(True)
        assert not dialog.server_url.isEnabled()
        # Both sentences explain the choice, so hiding a mode must not gray them.
        for label in dialog._connection_hint_labels():
            assert label.isEnabled()


class TestAdvancedLoggingPanel:
    """Verbose + log file live in the Advanced tab's Logging group; the log
    panel visibility toggle lives in General."""

    def test_logging_group_holds_verbose_and_logfile(self, dialog):
        grp = dialog._grp_advanced_logging
        assert grp.isAncestorOf(dialog.verbose)
        assert grp.isAncestorOf(dialog.logfile)

    def test_show_log_panel_is_in_general(self, dialog):
        assert dialog._tabs.widget(_GENERAL_TAB_INDEX).isAncestorOf(dialog.show_log_panel)

    def test_show_log_panel_label_is_translated(self, dialog):
        assert dialog._lbl_show_log_panel.text() == tr("settings.show_log_panel")


class TestP2pTooltips:
    """The p2p panel's previously tip-less fields now explain themselves."""

    _KEYS = {
        "p2p_rendezvous": "tip.p2p_rendezvous",
        "p2p_rendezvous_trust": "tip.p2p_rendezvous_trust",
        "p2p_rendezvous_transport": "tip.p2p_rendezvous_transport",
        "btn_manage_trusted_keys": "tip.manage_trusted_keys",
        "p2p_upnp": "tip.p2p_upnp",
    }

    def test_tooltips_shown_when_enabled(self, dialog, monkeypatch):
        monkeypatch.setattr(type(dialog), "_tips_enabled", lambda self: True)
        dialog._unsupported_widgets.clear()
        dialog._apply_tooltips()
        for name, key in self._KEYS.items():
            assert getattr(dialog, name).toolTip() == tr(key)

    def test_tooltips_hidden_when_disabled(self, dialog, monkeypatch):
        monkeypatch.setattr(type(dialog), "_tips_enabled", lambda self: False)
        dialog._unsupported_widgets.clear()
        dialog._apply_tooltips()
        for name in self._KEYS:
            assert getattr(dialog, name).toolTip() == ""


class TestRendezvousTestButton:
    """'Test Connection' in the p2p panel probes the configured rendezvous."""

    def _capture(self, monkeypatch, name):
        seen: list[str] = []
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: seen.append(a[2])))
        return seen

    def test_no_rendezvous_warns_without_probing(self, dialog, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod

        warned = self._capture(monkeypatch, "warning")
        probed: list = []
        monkeypatch.setattr(
            dialog_mod, "fetch_rendezvous_fingerprint", lambda *a, **k: probed.append(a)
        )
        dialog.p2p_rendezvous.setText("")
        dialog._on_test_rendezvous()
        assert warned == [tr("settings.test_rendezvous_no_host")]
        assert probed == []

    def test_invalid_endpoint_warns(self, dialog, monkeypatch):
        warned = self._capture(monkeypatch, "warning")
        dialog.p2p_rendezvous.setText("https://rdv.example.net")
        dialog._on_test_rendezvous()
        assert warned == [tr("settings.invalid_rendezvous_endpoint")]

    def test_unreachable_warns(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod

        warned = self._capture(monkeypatch, "warning")
        monkeypatch.setattr(dialog_mod, "find_hsync_binary", lambda: "/fake/hsync")
        monkeypatch.setattr(dialog_mod, "fetch_rendezvous_fingerprint", lambda *a, **k: None)
        dialog.p2p_rendezvous.setText("rdv.example.net")
        dialog._on_test_rendezvous()
        # The probe is off the UI thread: the button shows the busy state and the
        # window keeps running instead of freezing for the CLI timeout.
        assert not dialog.btn_test_rendezvous.isEnabled()
        assert dialog.btn_test_rendezvous.text() == tr("common.checking")
        qtbot.waitUntil(lambda: bool(warned), timeout=5000)
        assert warned == [tr("settings.test_rendezvous_failure")]
        assert dialog.btn_test_rendezvous.isEnabled()
        assert dialog.btn_test_rendezvous.text() == tr("settings.test_connection")

    def test_reachable_reports_the_fingerprint(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod

        infos = self._capture(monkeypatch, "information")
        monkeypatch.setattr(dialog_mod, "find_hsync_binary", lambda: "/fake/hsync")
        captured: dict = {}
        fingerprint = "sha256:" + "a" * 64

        def fake_probe(binary, host, port=None):
            captured.update(binary=binary, host=host, port=port)
            return fingerprint

        monkeypatch.setattr(dialog_mod, "fetch_rendezvous_fingerprint", fake_probe)
        dialog.p2p_rendezvous.setText("rdv.example.net:443")
        dialog._on_test_rendezvous()
        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert captured == {"binary": "/fake/hsync", "host": "rdv.example.net", "port": 443}
        report = f"✓ rdv.example.net:443: {fingerprint}"
        assert infos == [tr("settings.test_rendezvous_success").replace("{fingerprint}", report)]

    def test_every_configured_server_is_probed(self, dialog, qtbot, monkeypatch):
        """The field is a list: one line per server, and a dead one is visible."""
        import hsync_desktop.settings.dialog as dialog_mod

        infos = self._capture(monkeypatch, "information")
        monkeypatch.setattr(dialog_mod, "find_hsync_binary", lambda: "/fake/hsync")
        fingerprint = "sha256:" + "b" * 64
        probed: list[tuple[str, int | None]] = []

        def fake_probe(binary, host, port=None):
            probed.append((host, port))
            return None if host == "dead.example.net" else fingerprint

        monkeypatch.setattr(dialog_mod, "fetch_rendezvous_fingerprint", fake_probe)
        dialog.p2p_rendezvous.setText("live.example.net,dead.example.net:8443")
        dialog._on_test_rendezvous()
        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert probed == [("live.example.net", 443), ("dead.example.net", 8443)]
        report = "\n".join(
            [
                f"✓ live.example.net:443: {fingerprint}",
                "✗ dead.example.net:8443: unreachable",
            ]
        )
        assert infos == [tr("settings.test_rendezvous_success").replace("{fingerprint}", report)]

    def test_button_disabled_in_server_mode(self, dialog):
        dialog.mode_server.setChecked(True)
        assert not dialog.btn_test_rendezvous.isEnabled()
        dialog.mode_direct.setChecked(True)
        assert dialog.btn_test_rendezvous.isEnabled()


class TestServerTestConnection:
    """'Test Connection' in the Server Mode panel probes /health off-thread."""

    def _capture(self, monkeypatch, name):
        seen: list[str] = []
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: seen.append(a[2])))
        return seen

    def test_no_url_warns_without_probing(self, dialog, monkeypatch):
        warned = self._capture(monkeypatch, "warning")
        dialog.server_url.setText("")
        dialog._on_test_connection()
        assert warned == [tr("settings.test_connection_no_url")]

    def test_success(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import ServerProbeResult

        infos = self._capture(monkeypatch, "information")
        monkeypatch.setattr(
            dialog_mod,
            "probe_server_health",
            lambda *a, **k: ServerProbeResult(True, 200, 3, False),
        )
        dialog.mode_server.setChecked(True)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        # Non-blocking: the busy state is visible before the probe returns.
        assert not dialog.btn_test_connection.isEnabled()
        assert dialog.btn_test_connection.text() == tr("common.checking")
        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert infos == [tr("settings.test_connection_success")]
        assert dialog.btn_test_connection.isEnabled()

    def test_failure(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import REASON_UNREACHABLE, ServerProbeResult

        warned = self._capture(monkeypatch, "warning")
        monkeypatch.setattr(
            dialog_mod,
            "probe_server_health",
            lambda *a, **k: ServerProbeResult(False, None, 3, False, REASON_UNREACHABLE),
        )
        dialog.mode_server.setChecked(True)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        qtbot.waitUntil(lambda: bool(warned), timeout=5000)
        assert warned == [tr("settings.test_connection_failure")]

    def test_a_bare_address_falls_back_to_the_443_proxy(self, dialog, qtbot, monkeypatch):
        """A server behind a 443 reverse proxy passes from a bare host.

        The field normalizes to ``https://host:9753``; the probe must then try
        the shared 443 fallback so the test agrees with the client's startup
        resolution instead of failing a server the sync reaches.
        """
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import REASON_UNREACHABLE, ServerProbeResult

        infos = self._capture(monkeypatch, "information")

        def fake_probe(base_url, **_kwargs):
            if base_url.endswith(":443"):
                return ServerProbeResult(True, 200, 3, False)
            return ServerProbeResult(False, None, 3, False, REASON_UNREACHABLE)

        monkeypatch.setattr(dialog_mod, "probe_server_health", fake_probe)
        dialog.mode_server.setChecked(True)
        dialog.server_url.setText("217.160.132.7")  # bare -> https://...:9753
        dialog._on_test_connection()

        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert infos == [tr("settings.test_connection_success")]

    def test_auto_trust_retries_a_self_signed_server_without_verification(
        self, dialog, qtbot, monkeypatch
    ):
        """auto falls back to TOFU when the chain is not trusted (ADR-0051)."""
        import ssl

        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import REASON_UNREACHABLE, ServerProbeResult

        infos = self._capture(monkeypatch, "information")
        seen: list[ssl.VerifyMode] = []

        def fake_probe(_url, *, ssl_context, timeout):
            seen.append(ssl_context.verify_mode)
            if ssl_context.verify_mode == ssl.CERT_REQUIRED:
                return ServerProbeResult(False, None, 3, False, REASON_UNREACHABLE)
            return ServerProbeResult(True, 200, 3, False)

        monkeypatch.setattr(dialog_mod, "probe_server_health", fake_probe)
        dialog.mode_server.setChecked(True)
        dialog.server_trust.setCurrentIndex(dialog.server_trust.findData("auto"))
        dialog.server_url.setText("https://self-signed.example.com:9753")
        dialog._on_test_connection()

        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert infos == [tr("settings.test_connection_success")]
        assert seen == [ssl.CERT_REQUIRED, ssl.CERT_NONE]

    def test_the_rendezvous_button_label_is_untouched(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import ServerProbeResult

        monkeypatch.setattr(
            dialog_mod,
            "probe_server_health",
            lambda *a, **k: ServerProbeResult(True, 200, 3, False),
        )
        infos = self._capture(monkeypatch, "information")
        dialog.mode_server.setChecked(True)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        assert dialog.btn_test_rendezvous.text() == tr("settings.test_connection")
        qtbot.waitUntil(lambda: bool(infos), timeout=5000)

    def test_closing_the_dialog_drops_a_pending_probe(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import ServerProbeResult

        shown = self._capture(monkeypatch, "information") + self._capture(monkeypatch, "warning")

        def slow_probe(*_a, **_k):
            time.sleep(0.2)
            return ServerProbeResult(True, 200, 3, False)

        monkeypatch.setattr(dialog_mod, "probe_server_health", slow_probe)
        dialog.mode_server.setChecked(True)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        dialog.done(0)
        assert dialog.btn_test_connection.text() == tr("settings.test_connection")
        assert dialog.btn_test_connection.isEnabled()
        qtbot.wait(500)
        assert shown == []

    def test_an_active_sync_keeps_the_button_disabled(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import ServerProbeResult

        infos = self._capture(monkeypatch, "information")

        def slow_probe(*_a, **_k):
            time.sleep(0.2)
            return ServerProbeResult(True, 200, 3, False)

        monkeypatch.setattr(dialog_mod, "probe_server_health", slow_probe)
        dialog.mode_server.setChecked(True)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        # A sync starting while the probe runs must keep the button locked: the
        # result never re-enables a control the connection gate disables.
        dialog.set_connection_active(True)
        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert not dialog.btn_test_connection.isEnabled()
        dialog.set_connection_active(False)
        assert dialog.btn_test_connection.isEnabled()

    def test_opening_with_an_active_sync_disables_the_button(self, dialog):
        """Opening Settings while a sync runs must disable the Server Mode button.

        ``start._open_settings`` calls ``set_connection_active(engine.is_running)``
        right after building the dialog, before any probe. That path used to leave
        the Test Connection button enabled because its gate only ran when a probe
        ended.
        """
        dialog.mode_server.setChecked(True)

        dialog.set_connection_active(True)

        assert not dialog.btn_test_connection.isEnabled()

        dialog.set_connection_active(False)

        assert dialog.btn_test_connection.isEnabled()


class TestConnectionSections:
    """The connection page groups one mode at a time into its own sections."""

    @staticmethod
    def _groups(dialog) -> dict[str, QGroupBox]:
        tab = dialog._tabs.widget(_CONNECTION_TAB_INDEX)
        assert tab is not None
        return {g.title(): g for g in tab.findChildren(QGroupBox)}

    def test_the_mode_box_and_both_modes_sections(self, dialog):
        # The choice, the four direct-mode boxes and the three server-mode ones.
        assert set(self._groups(dialog)) == {
            escape_mnemonics(tr("settings.group.connection_mode")),
            escape_mnemonics(tr("settings.group.p2p_group")),
            escape_mnemonics(tr("settings.group.p2p_rendezvous")),
            escape_mnemonics(tr("settings.group.p2p_role")),
            escape_mnemonics(tr("settings.group.advanced")),
            escape_mnemonics(tr("settings.group.server")),
            escape_mnemonics(tr("settings.group.server_certificates")),
        }

    def test_fields_are_in_the_expected_section(self, dialog):
        groups = self._groups(dialog)
        mode = groups[escape_mnemonics(tr("settings.group.p2p_group"))]
        rendezvous = groups[escape_mnemonics(tr("settings.group.p2p_rendezvous"))]
        role = groups[escape_mnemonics(tr("settings.group.p2p_role"))]
        # Both modes keep an Advanced box; the direct one is reached by
        # attribute because the title is shared with the server one.
        advanced = dialog._grp_p2p_advanced

        assert dialog.p2p_group.parent() is mode
        assert dialog.p2p_key.parent() is mode
        assert dialog.p2p_rendezvous.parent() is rendezvous
        assert dialog.p2p_rendezvous_trust.parent() is rendezvous
        assert dialog.p2p_rendezvous_transport.parent() is rendezvous
        assert dialog.prefer_master.parent() is role
        assert dialog.p2p_trust.parent() is role
        assert dialog.p2p_port.parent() is advanced
        assert dialog.rendezvous_timeout.parent() is advanced
        assert dialog.ntp_hosts.parent() is advanced


class TestShareNameLabel:
    """The remote 'bucket' is shown first, presented as 'Share name'."""

    def test_bucket_label_uses_the_settings_key(self, dialog):
        lbl = dialog.findChild(QLabel, "lblBucket")
        assert lbl is not None
        assert lbl.text() == tr("settings.bucket")

    def test_share_name_precedes_the_local_folder(self, dialog):
        form = dialog._grp_path.layout()
        assert isinstance(form, QFormLayout)
        order: list[str] = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item is None:
                continue
            if item.widget() is dialog.bucket:
                order.append("bucket")
            elif item.layout() is not None and item.layout().indexOf(dialog.shared_path) >= 0:
                order.append("shared_path")
        assert order == ["bucket", "shared_path"]

    def test_p2p_group_titles_are_retranslated(self, dialog, monkeypatch):
        import hsync_desktop.settings.tab_translations as tr_mod

        monkeypatch.setattr(tr_mod, "tr", lambda key: f"<{key}>")
        dialog._apply_translations()
        assert dialog._grp_mode.title() == "<settings.group.connection_mode>"
        assert dialog._grp_p2p_group.title() == "<settings.group.p2p_group>"
        assert dialog._grp_p2p_advanced.title() == "<settings.group.advanced>"


class TestLabelTooltips:
    """Tooltips are mirrored onto the paired labels, per the preference."""

    _PAIRS = [
        ("p2p_group", "lblP2pGroup", "tip.p2p_group"),
        ("ntp_hosts", "_lbl_ntp_hosts", "tip.ntp_hosts"),
        ("shared_path", "lblSharedPath", "tip.shared_path"),
        ("bucket", "lblBucket", "tip.bucket"),
        ("p2p_upnp", "_lbl_p2p_upnp", "tip.p2p_upnp"),
        ("verbose", "_lbl_verbose", "tip.verbose"),
    ]

    def _label(self, dialog, name):
        if name.startswith("_"):
            return getattr(dialog, name)
        return dialog.findChild(QLabel, name)

    def test_labels_mirror_the_field_tooltip(self, dialog, monkeypatch):
        monkeypatch.setattr(type(dialog), "_tips_enabled", lambda self: True)
        dialog._unsupported_widgets.clear()
        dialog._apply_tooltips()
        for _field, label_name, key in self._PAIRS:
            label = self._label(dialog, label_name)
            assert label is not None, label_name
            assert label.toolTip() == tr(key), label_name

    def test_labels_cleared_when_tooltips_disabled(self, dialog, monkeypatch):
        monkeypatch.setattr(type(dialog), "_tips_enabled", lambda self: False)
        dialog._unsupported_widgets.clear()
        dialog._apply_tooltips()
        for _field, label_name, _key in self._PAIRS:
            label = self._label(dialog, label_name)
            assert label is not None
            assert label.toolTip() == "", label_name


class TestDialogButtonIcons:
    """Apply/Cancel use the bundled app icons, not the platform theme ones."""

    def test_apply_and_cancel_use_app_icons(self, dialog):
        from PySide6.QtWidgets import QDialogButtonBox

        from hsync_desktop.icons import icon

        ok = dialog._button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel = dialog._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok is not None and cancel is not None
        assert ok.text() == tr("settings.apply")
        assert cancel.text() == tr("settings.cancel")
        # Apply carries the confirm check, not the floppy (which means Save).
        assert ok.icon().cacheKey() == icon("dialog-ok").cacheKey()
        assert cancel.icon().cacheKey() == icon("dialog-cancel").cacheKey()


class TestConnectionModeSwitch:
    """One mode at a time: the page shows the selected half and keeps both.

    The choice is exclusive, so the page is never as tall as the two modes: the
    option you did not pick stays one click away at the top, and its values
    survive a switch because only their visibility changes.
    """

    def test_the_selected_mode_shows_only_its_half(self, dialog):
        dialog.mode_direct.setChecked(True)
        assert not dialog._direct_section.isHidden()
        assert dialog._server_section.isHidden()

        dialog.mode_server.setChecked(True)
        assert dialog._direct_section.isHidden()
        assert not dialog._server_section.isHidden()

    def test_switching_back_keeps_the_other_modes_values(self, dialog):
        dialog.server_url.setText("https://server.example.com")
        dialog.p2p_group.setText("my-group")

        dialog.mode_direct.setChecked(True)
        dialog.mode_server.setChecked(True)

        assert dialog.server_url.text() == "https://server.example.com"
        assert dialog.p2p_group.text() == "my-group"

    def test_the_saved_mode_follows_the_selection(self, dialog, settings):
        dialog.mode_server.setChecked(True)
        assert dialog._commit() is True
        assert settings.value("p2p/enabled", True, bool) is False

        dialog.mode_direct.setChecked(True)
        assert dialog._commit() is True
        assert settings.value("p2p/enabled", False, bool) is True

    def test_only_the_selected_modes_endpoint_is_validated(self, dialog, monkeypatch):
        shown: list = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a))
        dialog.server_url.setText("ftp://example.com")

        dialog.mode_direct.setChecked(True)
        assert dialog._commit() is True
        assert shown == []

        dialog.mode_server.setChecked(True)
        assert dialog._commit() is False
        assert shown

    def test_the_choice_is_locked_during_a_sync(self, dialog):
        dialog.set_connection_active(True)
        assert not dialog.mode_direct.isEnabled()
        assert not dialog.mode_server.isEnabled()

        dialog.set_connection_active(False)
        assert dialog.mode_direct.isEnabled()
        assert dialog.mode_server.isEnabled()


class TestTabOrderAndDefaultMode:
    """The p2p tab precedes Server Mode and a fresh install defaults to p2p."""

    def test_the_connection_tab_sits_between_sync_and_general(self, dialog):
        assert dialog._tabs.tabText(_CONNECTION_TAB_INDEX) == tr("settings.connection")
        assert _SYNC_TAB_INDEX < _CONNECTION_TAB_INDEX < _GENERAL_TAB_INDEX

    def test_tab_indices_point_to_the_right_pages(self, dialog):
        assert (
            dialog._tabs.widget(_CONNECTION_TAB_INDEX).findChild(QLineEdit, "p2pGroup") is not None
        )
        assert (
            dialog._tabs.widget(_CONNECTION_TAB_INDEX).findChild(QLineEdit, "serverUrl") is not None
        )

    def test_fresh_install_defaults_to_p2p_mode(self, qtbot, monkeypatch, tmp_path):
        from PySide6.QtCore import QSettings

        import hsync_desktop.settings.dialog as dialog_mod

        s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        assert not s.contains("p2p/enabled")
        monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: s)
        dlg = dialog_mod.SettingsDialog()
        qtbot.addWidget(dlg)
        assert dlg.mode_direct.isChecked()
        # The transport selector defaults to the shared RFC 8305 default.
        assert dlg.p2p_rendezvous_transport.currentData() == "auto"

    def test_transport_selector_is_persisted(self, qtbot, monkeypatch, tmp_path):
        """The chosen transport survives a save/reopen round-trip via QSettings."""
        from PySide6.QtCore import QSettings

        import hsync_desktop.settings.dialog as dialog_mod

        s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: s)
        dlg = dialog_mod.SettingsDialog()
        qtbot.addWidget(dlg)
        idx = dlg.p2p_rendezvous_transport.findData("tcp")
        dlg.p2p_rendezvous_transport.setCurrentIndex(idx if idx >= 0 else 0)
        dlg.save()
        assert s.value("p2p/rendezvous_transport") == "tcp"

        dlg2 = dialog_mod.SettingsDialog()
        qtbot.addWidget(dlg2)
        assert dlg2.p2p_rendezvous_transport.currentData() == "tcp"


class TestActionButtonRows:
    """Manage-keys / Verify share one responsive row per panel."""

    def test_p2p_verify_button_is_labelled(self, dialog):
        assert dialog.btn_test_rendezvous.text() == tr("settings.test_connection")

    def test_server_verify_button_is_labelled(self, dialog):
        assert dialog.btn_test_connection.text() == tr("settings.test_connection")

    @staticmethod
    def _assert_row_matches_its_room(buttons) -> None:
        """Side by side when the pair fits the column, stacked when it does not.

        The column is capped, so "the window is roomy" no longer implies the pair
        fits: Windows' larger metrics stack it at the default font.
        """
        parent = buttons[0].parent()
        assert parent is buttons[1].parent()
        room = parent.width()
        needed = sum(button.sizeHint().width() for button in buttons) + parent.layout().spacing()
        horizontal = parent.layout().direction() == QBoxLayout.Direction.LeftToRight
        assert horizontal == (needed <= room), (needed, room, horizontal, buttons[0].text())
        for button in buttons:
            assert button.width() >= button.sizeHint().width(), button.text()

    def test_p2p_actions_fit_or_stack_with_the_column(self, dialog, qtbot, monkeypatch):
        from PySide6.QtCore import QSize

        import hsync_desktop.settings.tab_builders as tab_builders

        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: QSize(4000, 4000))
        dialog.show()
        qtbot.waitExposed(dialog)
        dialog.set_current_tab(_CONNECTION_TAB_INDEX)
        tab_builders.fit_current_tab(dialog)
        qtbot.wait(10)

        self._assert_row_matches_its_room(
            (dialog.btn_manage_trusted_keys, dialog.btn_test_rendezvous)
        )

    def test_server_actions_fit_or_stack_with_the_column(self, dialog, qtbot, monkeypatch):
        from PySide6.QtCore import QSize

        import hsync_desktop.settings.tab_builders as tab_builders

        monkeypatch.setattr(tab_builders, "_available_screen_size", lambda _dlg: QSize(4000, 4000))
        dialog.show()
        qtbot.waitExposed(dialog)
        dialog.set_current_tab(_CONNECTION_TAB_INDEX)
        tab_builders.fit_current_tab(dialog)
        qtbot.wait(10)

        self._assert_row_matches_its_room(
            (dialog.btn_manage_trusted_keys_server, dialog.btn_test_connection)
        )


class TestDisabledDuringSyncVisual:
    """The Sync, connection and Advanced panels gray their labels while a sync runs."""

    @staticmethod
    def _labels(dialog, index: int, exclude: tuple = ()) -> list[QLabel]:
        tab = dialog._tabs.widget(index)
        assert tab is not None
        # The connection page's option sentences stay readable: they explain the
        # choice, not a setting the lock could freeze.
        return [
            lbl
            for lbl in tab.findChildren(QLabel)
            if lbl not in dialog._unsupported_labels and lbl not in exclude
        ]

    def _p2p_labels(self, dialog) -> list[QLabel]:
        return self._labels(dialog, _CONNECTION_TAB_INDEX, exclude=dialog._connection_hint_labels())

    def test_labels_are_grayed_while_sync_is_active(self, dialog):
        dialog.mode_direct.setChecked(True)
        dialog.set_connection_active(True)
        sync_labels = self._labels(dialog, 0)
        p2p_labels = self._p2p_labels(dialog)
        assert sync_labels and p2p_labels
        assert all(not lbl.isEnabled() for lbl in sync_labels)
        assert all(not lbl.isEnabled() for lbl in p2p_labels)

    def test_labels_are_restored_when_sync_stops(self, dialog):
        dialog.mode_direct.setChecked(True)
        dialog.set_connection_active(True)
        dialog.set_connection_active(False)
        assert all(lbl.isEnabled() for lbl in self._labels(dialog, 0))
        assert all(lbl.isEnabled() for lbl in self._p2p_labels(dialog))

    def test_the_mode_not_in_use_leaves_no_grayed_page_after_a_sync(self, dialog):
        dialog.mode_server.setChecked(True)
        dialog.set_connection_active(True)
        dialog.set_connection_active(False)
        # The direct half is hidden, not a page of grayed controls left behind.
        assert dialog._direct_section.isHidden()
        assert not dialog._server_section.isHidden()
        assert dialog.server_url.isEnabled()


class TestServerModeSections:
    """The Server Mode tab is grouped like the other settings tabs."""

    def test_the_three_sections_exist(self, dialog):
        assert dialog._grp_server.title() == tr("settings.group.server")
        assert dialog._grp_server_certificates.title() == tr("settings.group.server_certificates")
        assert dialog._grp_server_advanced.title() == tr("settings.group.advanced")

    def test_each_section_holds_its_fields(self, dialog):
        assert dialog._grp_server.isAncestorOf(dialog.server_url)
        assert dialog._grp_server.isAncestorOf(dialog.api_key)
        assert dialog._grp_server.isAncestorOf(dialog.server_trust)
        assert dialog._grp_server.isAncestorOf(dialog.btn_manage_trusted_keys_server)
        assert dialog._grp_server.isAncestorOf(dialog.btn_test_connection)
        assert dialog._grp_server_certificates.isAncestorOf(dialog.insecure)
        assert dialog._grp_server_certificates.isAncestorOf(dialog.ca_cert)
        assert dialog._grp_server_advanced.isAncestorOf(dialog.http_timeout)

    def test_the_sections_live_in_the_connection_tab(self, dialog):
        tab = dialog._tabs.widget(_CONNECTION_TAB_INDEX)
        for group in (
            dialog._grp_server,
            dialog._grp_server_certificates,
            dialog._grp_server_advanced,
        ):
            assert tab.isAncestorOf(group)

    def test_the_mode_box_holds_the_two_exclusive_options(self, dialog):
        assert dialog._grp_mode.isAncestorOf(dialog.mode_direct)
        assert dialog._grp_mode.isAncestorOf(dialog.mode_server)
        assert dialog.mode_direct.autoExclusive() and dialog.mode_server.autoExclusive()


def _activate_tab(dialog, index: int) -> None:
    """Select *index*, revealing the Advanced tab first (hidden by default)."""
    if index == _ADVANCED_TAB_INDEX:
        dialog.show_advanced.setChecked(True)
    dialog._tabs.setCurrentIndex(index)


_TAB_HELP_LINKS = [
    (_SYNC_TAB_INDEX, "_lbl_help_sync", docs_links.SETTINGS_SYNC_GUIDE, "help.settings_sync"),
    (
        _CONNECTION_TAB_INDEX,
        "_lbl_help_connection",
        docs_links.SETTINGS_CONNECTION_GUIDE,
        "help.settings_connection",
    ),
    (
        _GENERAL_TAB_INDEX,
        "_lbl_help_general",
        docs_links.SETTINGS_GENERAL_GUIDE,
        "help.settings_general",
    ),
    (
        _ADVANCED_TAB_INDEX,
        "_lbl_help_advanced",
        docs_links.SETTINGS_ADVANCED_GUIDE,
        "help.settings_advanced",
    ),
]


class TestTheTabHelpLinks:
    """One documentation link per settings tab, on the tab's own page.

    The four guides mirror their tab group by group, so a link inside every group
    would repeat one destination and add a row to each of them. The single link
    sits above the first group, because the page scrolls.
    """

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_the_link_sits_on_its_tab_with_the_expected_target(
        self, dialog, index, attr, url, text_key
    ):
        label = getattr(dialog, attr)
        page = dialog._tabs.widget(index)

        assert page.isAncestorOf(label)
        assert label.objectName() == "helpLink"
        assert label.property("docsUrl") == url
        assert url in label.text()
        assert tr(text_key) in label.text()
        assert label.accessibleName() == tr(text_key)

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_the_link_carries_an_icon_before_the_text(self, dialog, index, attr, url, text_key):
        """The affordance is not text-only: the glyph gets its own inset."""
        label = getattr(dialog, attr)

        assert label.contentsMargins().left() > 0

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_it_opens_the_page_above_the_first_group(self, dialog, index, attr, url, text_key):
        label = getattr(dialog, attr)
        content = label.parentWidget()

        assert content.layout().itemAt(0).widget() is label

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_a_tab_has_exactly_one_help_link(self, dialog, index, attr, url, text_key):
        page = dialog._tabs.widget(index)

        assert len(page.findChildren(QLabel, "helpLink")) == 1

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_clicking_it_opens_that_tabs_guide(self, dialog, index, attr, url, text_key):
        label = getattr(dialog, attr)
        with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
            label.linkActivated.emit(url)

        assert open_url.call_args.args[0].toString() == url

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_the_link_occupies_one_text_line(self, dialog, qtbot, index, attr, url, text_key):
        """A rich-text label must not reserve three lines for one line of text."""
        _activate_tab(dialog, index)
        dialog.show()
        qtbot.wait(1)
        label = getattr(dialog, attr)

        assert label.height() <= 2 * label.fontMetrics().height()


class TestTheHelpShortcut:
    """F1 opens the guide of the tab in front.

    ``Help → Documentation`` binds F1 on the main window only, so the modal
    dialog is free to follow the desktop convention instead of stealing it.
    """

    def test_the_shortcut_is_the_platform_help_key(self, dialog):
        assert dialog._act_help_tab.shortcut() == QKeySequence(
            QKeySequence.StandardKey.HelpContents
        )

    @pytest.mark.parametrize(("index", "attr", "url", "text_key"), _TAB_HELP_LINKS)
    def test_it_opens_the_current_tabs_guide(self, dialog, index, attr, url, text_key):
        _activate_tab(dialog, index)

        with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
            dialog._act_help_tab.trigger()

        assert open_url.call_args.args[0].toString() == url
