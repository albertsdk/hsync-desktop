# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Shared pytest fixtures for the hsync-desktop test suite.

Provides ``autouse`` fixtures that guarantee a clean environment for every test,
preventing state leakage between tests — especially critical for Qt-based
projects where a stray ``QApplication`` or registered callback can cascade.
"""

from collections.abc import Generator

import pytest

from tests._helpers import _patch_all, _settings


@pytest.fixture
def dialog(qtbot):
    """A SettingsDialog registered with qtbot."""
    from hsync_desktop.settings import SettingsDialog

    dlg = SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def settings(tmp_path):
    """An isolated QSettings store with the p2p pre-flight defaults."""
    return _settings(tmp_path)


@pytest.fixture
def window(qtbot, monkeypatch, settings):
    """A MainWindow with QSettings and binary rendezvous patched."""
    from hsync_desktop.engine import HsyncEngine
    from hsync_desktop.main_window import MainWindow

    _patch_all(monkeypatch, "QSettings", lambda *a, **k: settings)
    # Settings readers that live in settings/cli_args (e.g. is_simulation_mode,
    # build_hsync_args) open their own QSettings: isolate those too, or a host
    # setting would leak into the test expectations.
    import hsync_desktop.settings.cli_args as cli_args_module

    monkeypatch.setattr(cli_args_module, "QSettings", lambda *a, **k: settings)
    _patch_all(monkeypatch, "find_hsync_binary", lambda: "/fake/hsync")
    engine = HsyncEngine(binary_path="/fake/hsync")
    win = MainWindow(engine)
    qtbot.addWidget(win)
    return win


@pytest.fixture(autouse=True)
def _reset_i18n_callbacks() -> Generator[None]:
    """Clear registered language-change callbacks before and after each test.

    The ``i18n._language_change_callbacks`` list is module-level state.  A test
    that registers a callback and crashes before removing it would leak a stale
    closure into later tests.  This fixture ensures the list is always clean.
    """
    import hsync_desktop.i18n as i18n

    i18n._language_change_callbacks.clear()
    yield
    i18n._language_change_callbacks.clear()


@pytest.fixture(autouse=True)
def _restore_app_font() -> Generator[None]:
    """Restore the application font after a test that scales it.

    The UI-font tests call ``QApplication.setFont``; a leaked larger font changes
    every widget's size hint and breaks later layout assertions that assume the
    default metrics.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    saved = QFont(app.font()) if app is not None else None
    yield
    if app is not None and saved is not None:
        app.setFont(saved)


class _FakeAutostart:
    """Stand-in for ``hsync_desktop.autostart`` used by the dialog tests.

    Guarantees no test ever writes to (or reads from) the real per-user
    autostart location. ``fail`` makes ``set_enabled`` raise, to exercise the
    dialog's failure path.
    """

    def __init__(self) -> None:
        self.supported = True
        self.enabled = False
        self.fail = False
        self.calls: list[bool] = []

    def is_supported(self) -> bool:
        return self.supported

    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.calls.append(enabled)
        if self.fail:
            raise OSError("denied")
        self.enabled = enabled


@pytest.fixture(autouse=True)
def fake_autostart(monkeypatch) -> _FakeAutostart:
    """Replace the dialog/wizard autostart module with an isolated fake."""
    import hsync_desktop.settings.dialog as dialog_mod
    import hsync_desktop.wizard.apply as apply_mod

    fake = _FakeAutostart()
    monkeypatch.setattr(dialog_mod, "autostart", fake)
    monkeypatch.setattr(apply_mod, "autostart", fake)
    return fake
