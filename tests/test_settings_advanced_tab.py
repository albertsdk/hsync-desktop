# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the SettingsDialog Advanced and General tabs.

Covers the tab restructure (Log/Appearance retired), the Advanced engine-tuning
controls, their persistence, capability gating and the disabled-while-syncing
behaviour (Advanced yes, General no).
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from hsync_desktop.settings.tab_indices import _ADVANCED_TAB_INDEX, _GENERAL_TAB_INDEX


def _make_dialog(qtbot, monkeypatch, tmp_path, values: dict | None = None):
    import hsync_desktop.settings.dialog as dialog_mod

    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    for key, value in (values or {}).items():
        store.setValue(key, value)
    store.sync()
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: store)
    dlg = dialog_mod.SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg, store


class TestTabStructure:
    def test_has_five_tabs_no_log_or_appearance(self, qtbot, monkeypatch, tmp_path):
        dlg, _ = _make_dialog(qtbot, monkeypatch, tmp_path)
        assert dlg._tabs.count() == 5
        names = {dlg._tabs.tabText(i) for i in range(dlg._tabs.count())}
        assert not any("Log" in n or "Appearance" in n or "Aspetto" in n for n in names)

    def test_advanced_and_general_positions(self, dialog):
        assert dialog._tabs.widget(_ADVANCED_TAB_INDEX) is not None
        assert dialog._tabs.widget(_GENERAL_TAB_INDEX) is not None

    def test_advanced_groups_exist(self, dialog):
        for attr in (
            "_grp_advanced_perf",
            "_grp_advanced_delta",
            "_grp_advanced_guard",
            "_grp_advanced_network",
            "_grp_advanced_logging",
        ):
            assert getattr(dialog, attr) is not None

    def test_general_holds_start_at_login_and_log_panel(self, dialog):
        tab = dialog._tabs.widget(_GENERAL_TAB_INDEX)
        assert tab.isAncestorOf(dialog.start_at_login)
        assert tab.isAncestorOf(dialog.show_log_panel)

    def test_peer_download_lives_in_the_p2p_advanced_group(self, dialog):
        assert dialog._grp_p2p_advanced.isAncestorOf(dialog.peer_download)
        assert dialog._grp_p2p_advanced.isAncestorOf(dialog.peer_read_cap)
        assert dialog._grp_p2p_advanced.isAncestorOf(dialog.peer_sources_max)


class TestPersistence:
    def test_round_trip(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _make_dialog(
            qtbot,
            monkeypatch,
            tmp_path,
            {
                "advanced/autotune": False,
                "advanced/max_concurrent_transfers": 4,
                "advanced/delta_enabled": False,
                "advanced/delta_min_file_size_kb": 128,
                "advanced/mass_delete_guard": False,
                "advanced/mass_delete_threshold": 7,
                "advanced/mass_delete_percent": 25,
                "p2p/peer_download": False,
                "p2p/peer_read_cap": 5,
                "p2p/peer_sources_max": 2,
            },
        )
        assert dlg.autotune.isChecked() is False
        assert dlg.max_concurrent_transfers.value() == 4
        assert dlg.delta_enabled.isChecked() is False
        assert dlg.delta_min_file_size.value() == 128
        assert dlg.mass_delete_guard.isChecked() is False
        assert dlg.mass_delete_threshold.value() == 7
        assert dlg.mass_delete_percent.value() == 25
        assert dlg.peer_download.isChecked() is False
        assert dlg.peer_read_cap.value() == 5
        assert dlg.peer_sources_max.value() == 2

        dlg.max_concurrent_transfers.setValue(6)
        # save() also persists bandwidth via cli_args' own QSettings; stub it so
        # the test never touches the real user store.
        import hsync_desktop.settings.dialog as dialog_mod

        monkeypatch.setattr(dialog_mod, "save_bandwidth_limits", lambda *a, **k: None)
        dlg.save()
        assert store.value("advanced/max_concurrent_transfers", 0, int) == 6


class TestDisabledDuringSync:
    def test_advanced_grayed_general_live(self, dialog):
        dialog.set_connection_active(True)
        assert not dialog.autotune.isEnabled()
        assert not dialog.mass_delete_guard.isEnabled()
        # General is a live preference:  theme / language / startup stay usable.
        assert dialog.theme_combo.isEnabled()
        assert dialog.start_at_login.isEnabled()

    def test_advanced_restored_when_sync_stops(self, dialog):
        dialog.set_connection_active(True)
        dialog.set_connection_active(False)
        assert dialog.autotune.isEnabled()
        assert dialog.mass_delete_guard.isEnabled()


class TestCapabilityGating:
    def _with_flags(self, qtbot, monkeypatch, flags: list[str]):
        from hsync_common.protocol.capabilities import build_capabilities

        import hsync_desktop.settings.dialog as dialog_mod

        doc = build_capabilities(
            app_version="1.0.0",
            subcommands=["p2p"],
            cli_options_by_subcommand={"p2p": flags},
        )
        monkeypatch.setattr(dialog_mod, "get_binary_capabilities_cached", lambda: doc)
        dlg = dialog_mod.SettingsDialog()
        qtbot.addWidget(dlg)
        return dlg

    def test_missing_flags_disable_advanced_controls(self, qtbot, monkeypatch):
        dlg = self._with_flags(qtbot, monkeypatch, [])
        assert not dlg.autotune.isEnabled()
        assert not dlg.mass_delete_threshold.isEnabled()
        assert not dlg.peer_download.isEnabled()

    def test_advertised_flags_keep_controls_enabled(self, qtbot, monkeypatch):
        dlg = self._with_flags(
            qtbot,
            monkeypatch,
            [
                "--no-peer-download",
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
            ],
        )
        assert dlg.autotune.isEnabled()
        assert dlg.mass_delete_threshold.isEnabled()
        assert dlg.peer_download.isEnabled()
