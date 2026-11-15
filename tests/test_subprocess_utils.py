# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Alberto Basso

"""Tests for hsync_desktop.subprocess_utils."""

import subprocess

from hsync_desktop import subprocess_utils


class TestNoConsoleKwargs:
    def test_noop_off_windows(self, monkeypatch):
        monkeypatch.setattr(subprocess_utils, "_IS_WINDOWS", False)
        assert subprocess_utils.create_no_window() == 0
        assert subprocess_utils.no_console_kwargs() == {}

    def test_creates_no_window_on_windows(self, monkeypatch):
        flag = 0x08000000
        monkeypatch.setattr(subprocess_utils, "_IS_WINDOWS", True)
        monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", flag, raising=False)
        assert subprocess_utils.create_no_window() == flag
        assert subprocess_utils.no_console_kwargs() == {"creationflags": flag}

    def test_falls_back_when_constant_is_absent(self, monkeypatch):
        monkeypatch.setattr(subprocess_utils, "_IS_WINDOWS", True)
        monkeypatch.delattr(subprocess, "CREATE_NO_WINDOW", raising=False)
        assert subprocess_utils.create_no_window() == 0x08000000
