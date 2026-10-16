# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the 'Launch at login' setting.

The autostart side effect is always exercised through the ``fake_autostart``
fixture (conftest), so no test touches the real OS startup location.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from hsync_desktop.i18n import tr


def _dialog(qtbot, monkeypatch, tmp_path):
    import hsync_desktop.settings.dialog as dialog_mod

    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(dialog_mod, "QSettings", lambda *a, **k: store)
    dlg = dialog_mod.SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg, store


class TestToggle:
    def test_label_is_translated(self, dialog):
        assert dialog._lbl_start_at_login.text() == tr("settings.start_at_login")

    def test_default_is_off(self, qtbot, monkeypatch, tmp_path):
        dlg, _ = _dialog(qtbot, monkeypatch, tmp_path)
        assert not dlg.start_at_login.isChecked()

    def test_toggle_lives_in_the_sync_mode_group(self, dialog):
        """Launch-at-login sits with the sync options, not under Appearance."""
        assert dialog._grp_sync.isAncestorOf(dialog.start_at_login)


class TestPersistence:
    def test_save_persists_the_preference(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _dialog(qtbot, monkeypatch, tmp_path)
        dlg.start_at_login.setChecked(True)
        dlg.save()
        assert store.value("appearance/start_at_login", False, bool) is True

    def test_load_reflects_the_os_entry(self, qtbot, monkeypatch, tmp_path, fake_autostart):
        fake_autostart.enabled = True
        dlg, _ = _dialog(qtbot, monkeypatch, tmp_path)
        assert dlg.start_at_login.isChecked()


class TestApply:
    def test_enable_writes_the_login_item(self, dialog, fake_autostart):
        dialog.start_at_login.setChecked(True)
        assert dialog._apply_start_at_login() is True
        assert fake_autostart.calls == [True]
        assert fake_autostart.enabled is True

    def test_disable_removes_the_login_item(self, dialog, fake_autostart):
        fake_autostart.enabled = True
        dialog.start_at_login.setChecked(False)
        assert dialog._apply_start_at_login() is True
        assert fake_autostart.calls == [False]
        assert fake_autostart.enabled is False

    def test_failure_warns_and_restores_the_toggle(self, dialog, fake_autostart, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        warned: list[str] = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warned.append(a[2])))
        fake_autostart.fail = True
        fake_autostart.enabled = False
        dialog.start_at_login.setChecked(True)

        assert dialog._apply_start_at_login() is False
        assert warned == [tr("warn.start_at_login_failed").format(error="denied")]
        assert dialog.start_at_login.isChecked() is False

    def test_unsupported_platform_never_calls_the_backend(self, dialog, fake_autostart):
        fake_autostart.supported = False
        dialog.start_at_login.setChecked(True)
        assert dialog._apply_start_at_login() is True
        assert fake_autostart.calls == []

    def test_unsupported_platform_disables_the_toggle(self, qtbot, monkeypatch, tmp_path):
        dlg, store = _dialog(qtbot, monkeypatch, tmp_path)
        import hsync_desktop.settings.dialog as dialog_mod

        fake = dialog_mod.autostart
        fake.supported = False
        dlg.load()
        assert not dlg.start_at_login.isEnabled()
        assert dlg.start_at_login.toolTip() == tr("tip.start_at_login_unsupported")
