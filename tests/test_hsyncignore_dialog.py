# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the ignore-rules editor dialog (formerly "Edit .hsyncignore")."""

from __future__ import annotations

from hsync_common.constants import HSYNCIGNORE_FILENAME
from PySide6.QtWidgets import QDialogButtonBox

from hsync_desktop.i18n import tr
from hsync_desktop.settings.hsyncignore_dialog import HsyncIgnoreEditorDialog


def _dialog(qtbot, tmp_path):
    dlg = HsyncIgnoreEditorDialog(tmp_path)
    qtbot.addWidget(dlg)
    return dlg


class TestUi:
    def test_title_uses_friendly_name(self, qtbot, tmp_path):
        dlg = _dialog(qtbot, tmp_path)
        assert dlg.windowTitle() == tr("hsyncignore.title")

    def test_buttons_use_app_theme_icons(self, qtbot, tmp_path):
        dlg = _dialog(qtbot, tmp_path)
        box: QDialogButtonBox = dlg.findChild(QDialogButtonBox)
        ok = box.button(QDialogButtonBox.StandardButton.Ok)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok is not None and not ok.icon().isNull()
        assert cancel is not None and not cancel.icon().isNull()
        assert ok.text() == tr("settings.save")
        assert cancel.text() == tr("settings.cancel")


class TestSave:
    def test_save_writes_the_ignore_file(self, qtbot, tmp_path):
        dlg = _dialog(qtbot, tmp_path)
        dlg._editor.setPlainText("*.log\n/build/\n")
        dlg._on_save()
        written = (tmp_path / HSYNCIGNORE_FILENAME).read_text(encoding="utf-8")
        assert written == "*.log\n/build/\n"
