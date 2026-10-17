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
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.dialog import (
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    SettingsDialog,
)


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
        "p2p_bootnode": "tip.p2p_bootnode",
        "p2p_bootnode_trust": "tip.p2p_bootnode_trust",
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


class TestBootnodeTestButton:
    """'Test Connection' in the p2p panel probes the configured bootnode."""

    def _capture(self, monkeypatch, name):
        seen: list[str] = []
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: seen.append(a[2])))
        return seen

    def test_no_bootnode_warns_without_probing(self, dialog, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod

        warned = self._capture(monkeypatch, "warning")
        probed: list = []
        monkeypatch.setattr(
            dialog_mod, "fetch_bootnode_fingerprint", lambda *a, **k: probed.append(a)
        )
        dialog.p2p_bootnode.setText("")
        dialog._on_test_bootnode()
        assert warned == [tr("settings.test_bootnode_no_host")]
        assert probed == []

    def test_invalid_endpoint_warns(self, dialog, monkeypatch):
        warned = self._capture(monkeypatch, "warning")
        dialog.p2p_bootnode.setText("https://boot.example.net")
        dialog._on_test_bootnode()
        assert warned == [tr("settings.invalid_bootnode_endpoint")]

    def test_unreachable_warns(self, dialog, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod

        warned = self._capture(monkeypatch, "warning")
        monkeypatch.setattr(dialog_mod, "find_hsync_binary", lambda: "/fake/hsync")
        monkeypatch.setattr(dialog_mod, "fetch_bootnode_fingerprint", lambda *a, **k: None)
        dialog.p2p_bootnode.setText("boot.example.net")
        dialog._on_test_bootnode()
        assert warned == [tr("settings.test_bootnode_failure")]

    def test_reachable_reports_the_fingerprint(self, dialog, monkeypatch):
        import hsync_desktop.settings.dialog as dialog_mod

        infos = self._capture(monkeypatch, "information")
        monkeypatch.setattr(dialog_mod, "find_hsync_binary", lambda: "/fake/hsync")
        captured: dict = {}
        fingerprint = "sha256:" + "a" * 64

        def fake_probe(binary, host, port=None):
            captured.update(binary=binary, host=host, port=port)
            return fingerprint

        monkeypatch.setattr(dialog_mod, "fetch_bootnode_fingerprint", fake_probe)
        dialog.p2p_bootnode.setText("boot.example.net:443")
        dialog._on_test_bootnode()
        assert captured == {"binary": "/fake/hsync", "host": "boot.example.net", "port": 443}
        assert infos == [tr("settings.test_bootnode_success").replace("{fingerprint}", fingerprint)]

    def test_button_disabled_in_server_mode(self, dialog):
        dialog.p2p_mode.setChecked(False)
        assert not dialog.btn_test_bootnode.isEnabled()
        dialog.p2p_mode.setChecked(True)
        assert dialog.btn_test_bootnode.isEnabled()


class TestP2pPanelSections:
    """The p2p tab is grouped into four sections like the sync tab."""

    @staticmethod
    def _groups(dialog) -> dict[str, QGroupBox]:
        tab = dialog._tabs.widget(_P2P_TAB_INDEX)
        assert tab is not None
        return {g.title(): g for g in tab.findChildren(QGroupBox)}

    def test_four_sections_with_expected_titles(self, dialog):
        assert set(self._groups(dialog)) == {
            tr("settings.group.p2p_mode"),
            tr("settings.group.p2p_discovery"),
            tr("settings.group.p2p_role"),
            tr("settings.group.advanced"),
        }

    def test_fields_are_in_the_expected_section(self, dialog):
        groups = self._groups(dialog)
        mode = groups[tr("settings.group.p2p_mode")]
        discovery = groups[tr("settings.group.p2p_discovery")]
        role = groups[tr("settings.group.p2p_role")]
        advanced = groups[tr("settings.group.advanced")]

        assert dialog.p2p_group.parent() is mode
        assert dialog.p2p_key.parent() is mode
        assert dialog.p2p_bootnode.parent() is discovery
        assert dialog.p2p_bootnode_trust.parent().parent() is discovery
        assert dialog.prefer_master.parent().parent() is role
        assert dialog.require_pairing.parent().parent() is role
        assert dialog.p2p_port.parent() is advanced
        assert dialog.discovery_timeout.parent() is advanced
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
        assert dialog.btn_test_bootnode.text() == tr("settings.test_connection")

    def test_server_verify_button_is_labelled(self, dialog):
        assert dialog.btn_test_connection.text() == tr("settings.test_connection")

    def test_p2p_actions_are_in_one_horizontal_row(self, dialog):
        parent = dialog.btn_manage_trusted_keys.parent()
        assert parent is dialog.btn_test_bootnode.parent()
        assert isinstance(parent.layout(), QHBoxLayout)

    def test_server_actions_are_in_one_horizontal_row(self, dialog):
        parent = dialog.btn_manage_trusted_keys_server.parent()
        assert parent is dialog.btn_test_connection.parent()
        assert isinstance(parent.layout(), QHBoxLayout)


class TestDisabledDuringSyncVisual:
    """The Sync and p2p panels gray their labels while a sync runs, the same
    visual the Server Mode tab uses when p2p mode is active."""

    @staticmethod
    def _labels(dialog, index: int, exclude: tuple = ()) -> list[QLabel]:
        tab = dialog._tabs.widget(index)
        assert tab is not None
        return [
            lbl
            for lbl in tab.findChildren(QLabel)
            if lbl not in dialog._unsupported_labels and lbl not in exclude
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
