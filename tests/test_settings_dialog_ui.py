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
from PySide6.QtCore import QPoint
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
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
    SettingsDialog,
)
from hsync_desktop.widgets.text import escape_mnemonics


class TestTabDescriptionAlignment:
    """The mode purpose lines reserve one height, so the tab forms align.

    The description wraps to a different number of lines per locale, and the
    shorter one used to let its first group box sit higher: the tabs must not
    shift when switching between them.
    """

    _DESCRIBED_TABS = (_SYNC_TAB_INDEX, _P2P_TAB_INDEX, _SERVER_TAB_INDEX)

    def test_descriptions_reserve_one_height(self, dialog, qtbot):
        dialog.resize(900, 700)
        dialog.show()
        qtbot.waitExposed(dialog)

        heights = {
            index: dialog._tab_descriptions[index].minimumHeight() for index in self._DESCRIBED_TABS
        }

        assert len(set(heights.values())) == 1
        assert next(iter(heights.values())) > 0

    def test_first_group_starts_at_the_same_offset(self, dialog, qtbot):
        dialog.resize(900, 700)
        dialog.show()
        qtbot.waitExposed(dialog)

        offsets = {}
        for index in (_SYNC_TAB_INDEX, _P2P_TAB_INDEX):
            dialog._tabs.setCurrentIndex(index)
            qtbot.wait(10)
            tab = dialog._tabs.widget(index)
            group = tab.findChild(QGroupBox)
            assert group is not None
            offsets[index] = group.mapTo(tab, QPoint(0, 0)).y()

        assert offsets[_SYNC_TAB_INDEX] == offsets[_P2P_TAB_INDEX]


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
        dialog.p2p_mode.setChecked(False)
        assert not dialog.btn_test_rendezvous.isEnabled()
        dialog.p2p_mode.setChecked(True)
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
        dialog.p2p_mode.setChecked(False)
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
        dialog.p2p_mode.setChecked(False)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        qtbot.waitUntil(lambda: bool(warned), timeout=5000)
        assert warned == [tr("settings.test_connection_failure")]

    def test_the_rendezvous_button_label_is_untouched(self, dialog, qtbot, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod
        from hsync_desktop.engine.probes import ServerProbeResult

        monkeypatch.setattr(
            dialog_mod,
            "probe_server_health",
            lambda *a, **k: ServerProbeResult(True, 200, 3, False),
        )
        infos = self._capture(monkeypatch, "information")
        dialog.p2p_mode.setChecked(False)
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
        dialog.p2p_mode.setChecked(False)
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
        dialog.p2p_mode.setChecked(False)
        dialog.server_url.setText("https://server.example.com:9753")
        dialog._on_test_connection()
        # A sync starting while the probe runs must keep the button locked: the
        # result never re-enables a control the connection gate disables.
        dialog.set_connection_active(True)
        qtbot.waitUntil(lambda: bool(infos), timeout=5000)
        assert not dialog.btn_test_connection.isEnabled()
        dialog.set_connection_active(False)
        assert dialog.btn_test_connection.isEnabled()


class TestP2pPanelSections:
    """The p2p tab is grouped into four sections like the sync tab."""

    @staticmethod
    def _groups(dialog) -> dict[str, QGroupBox]:
        tab = dialog._tabs.widget(_P2P_TAB_INDEX)
        assert tab is not None
        return {g.title(): g for g in tab.findChildren(QGroupBox)}

    def test_four_sections_with_expected_titles(self, dialog):
        assert set(self._groups(dialog)) == {
            escape_mnemonics(tr("settings.group.p2p_mode")),
            escape_mnemonics(tr("settings.group.p2p_rendezvous")),
            escape_mnemonics(tr("settings.group.p2p_role")),
            escape_mnemonics(tr("settings.group.advanced")),
        }

    def test_fields_are_in_the_expected_section(self, dialog):
        groups = self._groups(dialog)
        mode = groups[escape_mnemonics(tr("settings.group.p2p_mode"))]
        rendezvous = groups[escape_mnemonics(tr("settings.group.p2p_rendezvous"))]
        role = groups[escape_mnemonics(tr("settings.group.p2p_role"))]
        advanced = groups[escape_mnemonics(tr("settings.group.advanced"))]

        assert dialog.p2p_group.parent() is mode
        assert dialog.p2p_key.parent() is mode
        assert dialog.p2p_rendezvous.parent() is rendezvous
        assert dialog.p2p_rendezvous_trust.parent() is rendezvous
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
        assert dialog._grp_p2p_mode.title() == "<settings.group.p2p_mode>"
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
    """Save/Cancel use the bundled app icons, not the platform theme ones."""

    def test_save_and_cancel_use_app_icons(self, dialog):
        from PySide6.QtWidgets import QDialogButtonBox

        from hsync_desktop.icons import icon

        ok = dialog._button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel = dialog._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok is not None and cancel is not None
        assert ok.icon().cacheKey() == icon("document-save").cacheKey()
        assert cancel.icon().cacheKey() == icon("dialog-cancel").cacheKey()


class TestTabOrderAndDefaultMode:
    """The p2p tab precedes Server Mode and a fresh install defaults to p2p."""

    def test_p2p_tab_precedes_server_mode_tab(self, dialog):
        assert dialog._tabs.tabText(_P2P_TAB_INDEX) == tr("settings.p2p")
        assert dialog._tabs.tabText(_SERVER_TAB_INDEX) == tr("settings.server_mode")
        assert _P2P_TAB_INDEX < _SERVER_TAB_INDEX

    def test_tab_indices_point_to_the_right_pages(self, dialog):
        assert dialog._tabs.widget(_P2P_TAB_INDEX).findChild(QLineEdit, "p2pGroup") is not None
        assert dialog._tabs.widget(_SERVER_TAB_INDEX).findChild(QLineEdit, "serverUrl") is not None

    def test_fresh_install_defaults_to_p2p_mode(self, qtbot, monkeypatch, tmp_path):
        from PySide6.QtCore import QSettings

        import hsync_desktop.settings.dialog as dialog_mod

        s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        assert not s.contains("p2p/enabled")
        monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: s)
        dlg = dialog_mod.SettingsDialog()
        qtbot.addWidget(dlg)
        assert dlg.p2p_mode.isChecked()


class TestActionButtonRows:
    """Manage-keys / Verify are labelled and share one horizontal row per panel."""

    def test_p2p_verify_button_is_labelled(self, dialog):
        assert dialog.btn_test_rendezvous.text() == tr("settings.test_connection")

    def test_server_verify_button_is_labelled(self, dialog):
        assert dialog.btn_test_connection.text() == tr("settings.test_connection")

    def test_p2p_actions_are_in_one_horizontal_row(self, dialog):
        parent = dialog.btn_manage_trusted_keys.parent()
        assert parent is dialog.btn_test_rendezvous.parent()
        assert parent.layout().direction() == QBoxLayout.Direction.LeftToRight

    def test_server_actions_are_in_one_horizontal_row(self, dialog):
        parent = dialog.btn_manage_trusted_keys_server.parent()
        assert parent is dialog.btn_test_connection.parent()
        assert parent.layout().direction() == QBoxLayout.Direction.LeftToRight


class TestDisabledDuringSyncVisual:
    """The Sync and p2p panels gray their labels while a sync runs, the same
    visual the Server Mode tab uses when p2p mode is active."""

    @staticmethod
    def _labels(dialog, index: int, exclude: tuple = ()) -> list[QLabel]:
        tab = dialog._tabs.widget(index)
        assert tab is not None
        # The tab's purpose line stays readable even when its controls are off.
        skip = (*exclude, dialog._tab_descriptions.get(index))
        return [
            lbl
            for lbl in tab.findChildren(QLabel)
            if lbl not in dialog._unsupported_labels and lbl not in skip
        ]

    def _p2p_labels(self, dialog) -> list[QLabel]:
        return self._labels(dialog, _P2P_TAB_INDEX, exclude=(dialog._lbl_p2p_mode,))

    def test_labels_are_grayed_while_sync_is_active(self, dialog):
        dialog.p2p_mode.setChecked(True)
        dialog.set_connection_active(True)
        sync_labels = self._labels(dialog, 0)
        p2p_labels = self._p2p_labels(dialog)
        assert sync_labels and p2p_labels
        assert all(not lbl.isEnabled() for lbl in sync_labels)
        assert all(not lbl.isEnabled() for lbl in p2p_labels)

    def test_labels_are_restored_when_sync_stops(self, dialog):
        dialog.p2p_mode.setChecked(True)
        dialog.set_connection_active(True)
        dialog.set_connection_active(False)
        assert all(lbl.isEnabled() for lbl in self._labels(dialog, 0))
        assert all(lbl.isEnabled() for lbl in self._p2p_labels(dialog))

    def test_p2p_labels_stay_grayed_when_p2p_is_off_after_sync(self, dialog):
        dialog.p2p_mode.setChecked(False)
        dialog.set_connection_active(True)
        dialog.set_connection_active(False)
        p2p_labels = self._p2p_labels(dialog)
        assert p2p_labels
        assert all(not lbl.isEnabled() for lbl in p2p_labels)
        assert all(lbl.isEnabled() for lbl in self._labels(dialog, 0))


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

    def test_the_sections_live_in_the_server_tab(self, dialog):
        tab = dialog._tabs.widget(_SERVER_TAB_INDEX)
        for group in (
            dialog._grp_server,
            dialog._grp_server_certificates,
            dialog._grp_server_advanced,
        ):
            assert tab.isAncestorOf(group)

    def test_the_p2p_banner_stays_outside_the_groups(self, dialog):
        tab = dialog._tabs.widget(_SERVER_TAB_INDEX)
        assert tab.isAncestorOf(dialog._p2p_banner)
        assert not dialog._grp_server.isAncestorOf(dialog._p2p_banner)


class TestServerSetupLink:
    """The Server group links to the hsync-server setup guide."""

    def test_it_lives_in_the_server_group_with_the_expected_target(self, dialog):
        label = dialog._lbl_help_server

        assert dialog._grp_server.isAncestorOf(label)
        assert label.objectName() == "helpLink"
        assert label.property("docsUrl") == docs_links.SERVER_SETUP
        assert docs_links.SERVER_SETUP in label.text()
        assert tr("help.server_setup") in label.text()

    def test_clicking_it_opens_the_server_guide(self, dialog):
        with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
            dialog._lbl_help_server.linkActivated.emit(docs_links.SERVER_SETUP)

        open_url.assert_called_once()

    def test_the_link_occupies_one_text_line(self, dialog, qtbot):
        """A rich-text label must not reserve three lines for one line of text."""
        dialog._tabs.setCurrentIndex(_SERVER_TAB_INDEX)
        dialog.show()
        qtbot.wait(1)
        label = dialog._lbl_help_server

        assert label.height() <= 2 * label.fontMetrics().height()


class TestRendezvousSetupLink:
    """The p2p rendezvous group links to the hsync-rendezvous guide."""

    def test_it_lives_in_the_rendezvous_group_with_the_expected_target(self, dialog):
        label = dialog._lbl_help_rendezvous

        assert dialog._grp_p2p_rendezvous.isAncestorOf(label)
        assert label.objectName() == "helpLink"
        assert label.property("docsUrl") == docs_links.RENDEZVOUS_SETUP
        assert docs_links.RENDEZVOUS_SETUP in label.text()
        assert tr("help.rendezvous_setup") in label.text()

    def test_clicking_it_opens_the_rendezvous_guide(self, dialog):
        with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
            dialog._lbl_help_rendezvous.linkActivated.emit(docs_links.RENDEZVOUS_SETUP)

        open_url.assert_called_once()

    def test_the_link_occupies_one_text_line(self, dialog, qtbot):
        """A rich-text label must not reserve three lines for one line of text."""
        dialog._tabs.setCurrentIndex(_P2P_TAB_INDEX)
        dialog.show()
        qtbot.wait(1)
        label = dialog._lbl_help_rendezvous

        assert label.height() <= 2 * label.fontMetrics().height()
