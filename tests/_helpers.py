# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Helpers shared by the hsync-desktop test modules.

Kept out of ``conftest.py`` because they are plain functions/classes, not
fixtures; the shared fixtures live in ``conftest.py``.
"""

from __future__ import annotations

import importlib

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

_WINDOW_MODULES = tuple(
    importlib.import_module(f"hsync_desktop.main_window.{name}")
    for name in ("actions", "events", "lifecycle", "start", "trust", "ui", "window")
)


def _patch_all(monkeypatch, name: str, value) -> None:
    """Patch *name* in every main_window submodule that defines it."""
    for module in _WINDOW_MODULES:
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)


def _settings(tmp_path) -> QSettings:
    s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    s.setValue("p2p/enabled", True)
    s.setValue("p2p/bootnode", "boot.example.net")
    s.setValue("p2p/bootnode_trust", "ask")
    return s


def _resolve_dialog(monkeypatch, label: str | None) -> list[int]:
    """Make QMessageBox.exec a no-op recording the call and clickedButton pick *label*.

    *label* None simulates a dialog dismissed without pressing a button (window
    close), for which ``clickedButton()`` is None. Returns the exec-call counter.
    """
    calls: list[int] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: calls.append(1) or 0)

    def fake_clicked(self):
        if label is None:
            return None
        for button in self.buttons():
            if button.text() == label:
                return button
        return None

    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked)
    return calls


class _FakeCompleted:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _capture(signal) -> list:
    """Record every emission of *signal* as a tuple of its arguments."""
    received: list = []
    signal.connect(lambda *args: received.append(args))
    return received
