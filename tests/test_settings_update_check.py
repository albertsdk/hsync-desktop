# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the "Check for updates at startup" setting in Settings.

The Help dialog exposes the same preference; both read and write it through
``hsync_desktop.updates`` so the two surfaces cannot disagree about either the
value or where it is stored.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from hsync_desktop import updates
from hsync_desktop.i18n import tr
from hsync_desktop.settings.tab_indices import _GENERAL_TAB_INDEX


def _dialog(qtbot, monkeypatch, tmp_path):
    import hsync_desktop.settings.dialog as dialog_mod

    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: store)
    # ``updates`` keeps its own QSettings handle; point it at the same store.
    monkeypatch.setattr(updates, "_settings", lambda: store)
    dlg = dialog_mod.SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg, store


class TestUpdateCheckSetting:
    def test_the_toggle_lives_in_the_general_tab(self, dialog):
        assert dialog._tabs.widget(_GENERAL_TAB_INDEX).isAncestorOf(dialog.update_check)

    def test_the_caption_is_the_shared_updates_string(self, dialog):
        """One string for both surfaces: the Help dialog uses the same key."""
        assert dialog._lbl_update_check.text() == tr("updates.check_at_startup")

    def test_it_reflects_the_persisted_value(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _dialog(qtbot, monkeypatch, tmp_path)
        store.setValue("updates/check_enabled", True)

        dlg.load()

        assert dlg.update_check.isChecked() is True

    def test_saving_writes_through_the_shared_api(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _dialog(qtbot, monkeypatch, tmp_path)

        dlg.update_check.setChecked(True)
        dlg.save()

        # Same key the Help dialog reads, so the preference is one value.
        assert updates.is_enabled() is True
        assert bool(store.value("updates/check_enabled", False, bool)) is True

    def test_disabling_it_is_persisted_too(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _dialog(qtbot, monkeypatch, tmp_path)
        updates.set_enabled(True)

        dlg.update_check.setChecked(False)
        dlg.save()

        assert updates.is_enabled() is False

    def test_the_tooltip_names_the_prerelease_policy(self, dialog):
        """The operator must know alpha/beta builds are never offered."""
        assert "alpha" in dialog.update_check.toolTip().lower()
