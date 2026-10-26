# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.autostart (launch-at-login integration).

Every test redirects the platform and home directory to a temp location so the
real ``~/.config/autostart`` and ``~/Library/LaunchAgents`` are never touched.
"""

from __future__ import annotations

import plistlib
import sys

import pytest

import hsync_desktop.autostart as autostart


@pytest.fixture
def linux_home(tmp_path, monkeypatch):
    """A Linux platform rooted at a temp XDG config home."""
    monkeypatch.setattr(autostart, "_platform", lambda: "linux")
    monkeypatch.setattr(autostart, "_home_dir", lambda: tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


@pytest.fixture
def macos_home(tmp_path, monkeypatch):
    """A macOS platform rooted at a temp home directory."""
    monkeypatch.setattr(autostart, "_platform", lambda: "darwin")
    monkeypatch.setattr(autostart, "_home_dir", lambda: tmp_path)
    return tmp_path


class TestSupport:
    @pytest.mark.parametrize("platform", ["linux", "linux2", "darwin", "win32"])
    def test_supported_platforms(self, monkeypatch, platform):
        monkeypatch.setattr(autostart, "_platform", lambda: platform)
        assert autostart.is_supported() is True

    def test_unsupported_platform(self, monkeypatch):
        monkeypatch.setattr(autostart, "_platform", lambda: "freebsd99")
        assert autostart.is_supported() is False
        assert autostart.is_enabled() is False
        # No mechanism: enabling is a silent no-op, never a crash.
        autostart.set_enabled(True)


class TestExecFieldQuote:
    def test_plain_argument_is_unquoted(self):
        assert autostart._exec_field_quote("hsync-desktop") == "hsync-desktop"

    def test_spaces_force_quoting(self):
        assert autostart._exec_field_quote("/opt/HSYNC App/x") == '"/opt/HSYNC App/x"'

    def test_quotes_and_backslashes_are_escaped(self):
        assert autostart._exec_field_quote('a"b\\c') == '"a\\"b\\\\c"'

    def test_line_breaks_are_dropped(self):
        assert "\n" not in autostart._exec_field_quote("/opt/a\nb")
        assert "\r" not in autostart._exec_field_quote("/opt/a\rb")


class TestCommandValidation:
    @pytest.fixture
    def linux_home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(autostart, "_platform", lambda: "linux")
        monkeypatch.setattr(autostart, "_home_dir", lambda: tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        return tmp_path

    def test_relative_command_is_rejected(self, linux_home, monkeypatch):
        monkeypatch.setattr(
            autostart, "_launch_command", lambda: ["relative/hsync-desktop", "--minimized"]
        )
        with pytest.raises(OSError):
            autostart.set_enabled(True)
        assert not autostart.is_enabled()

    def test_control_characters_in_command_are_rejected(self, linux_home, monkeypatch):
        monkeypatch.setattr(autostart, "_launch_command", lambda: ["/opt/a\nb", "--minimized"])
        with pytest.raises(OSError):
            autostart.set_enabled(True)
        assert not autostart.is_enabled()

    def test_relative_xdg_config_home_falls_back_to_home(self, linux_home, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/config")
        autostart.set_enabled(True)
        assert (linux_home / ".config" / "autostart" / "hsync-desktop.desktop").is_file()


class TestLinuxEntry:
    def test_write_read_remove(self, linux_home, monkeypatch):
        monkeypatch.setattr(
            autostart,
            "_launch_command",
            lambda: ["/opt/HSYNC Desktop/hsync-desktop", "--minimized"],
        )
        entry = linux_home / "config" / "autostart" / "hsync-desktop.desktop"
        assert not autostart.is_enabled()

        autostart.set_enabled(True)
        assert autostart.is_enabled()
        text = entry.read_text(encoding="utf-8")
        assert "[Desktop Entry]" in text
        assert 'Exec="/opt/HSYNC Desktop/hsync-desktop" --minimized' in text
        assert "X-GNOME-Autostart-enabled=true" in text

        autostart.set_enabled(False)
        assert not autostart.is_enabled()
        assert not entry.exists()

    def test_removing_a_missing_entry_is_safe(self, linux_home):
        autostart.set_enabled(False)  # never created
        assert not autostart.is_enabled()

    def test_defaults_to_home_config_without_xdg(self, linux_home, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        autostart.set_enabled(True)
        assert (linux_home / ".config" / "autostart" / "hsync-desktop.desktop").is_file()


class TestMacosEntry:
    def test_launch_agent_plist(self, macos_home, monkeypatch):
        command = ["/Applications/HSYNC.app/Contents/MacOS/hsync-desktop", "--minimized"]
        monkeypatch.setattr(autostart, "_launch_command", lambda: command)
        plist = macos_home / "Library" / "LaunchAgents" / "io.hsync.desktop.plist"
        assert not autostart.is_enabled()

        autostart.set_enabled(True)
        assert autostart.is_enabled()
        payload = plistlib.loads(plist.read_bytes())
        assert payload["Label"] == "io.hsync.desktop"
        assert payload["ProgramArguments"] == command
        assert payload["RunAtLoad"] is True

        autostart.set_enabled(False)
        assert not autostart.is_enabled()


class TestLaunchCommand:
    @pytest.fixture(autouse=True)
    def _clean_launcher_env(self, monkeypatch):
        """Isolate the launcher from a host SNAP/APPIMAGE environment."""
        monkeypatch.delenv("SNAP", raising=False)
        monkeypatch.delenv("APPIMAGE", raising=False)

    def test_snap_uses_snap_run(self, monkeypatch):
        """In a snap the entry must not point at a revision-specific binary."""
        monkeypatch.setenv("SNAP", "/snap/hsync-desktop/current")
        monkeypatch.setattr(
            autostart.shutil,
            "which",
            lambda name: "/usr/bin/snap" if name == "snap" else None,
        )
        assert autostart._launch_command() == [
            "/usr/bin/snap",
            "run",
            "hsync-desktop",
            "--minimized",
        ]

    def test_a_missing_snap_binary_falls_through(self, monkeypatch):
        monkeypatch.setenv("SNAP", "/snap/hsync-desktop/current")
        monkeypatch.setattr(autostart.shutil, "which", lambda name: None)
        assert autostart._launch_command() == [
            sys.executable,
            "-m",
            "hsync_desktop",
            "--minimized",
        ]

    def test_appimage_wins(self, monkeypatch):
        monkeypatch.setenv("APPIMAGE", "/apps/HSYNC.AppImage")
        assert autostart._launch_command() == ["/apps/HSYNC.AppImage", "--minimized"]

    def test_frozen_bundle_uses_executable(self, monkeypatch):
        monkeypatch.delenv("APPIMAGE", raising=False)
        monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
        assert autostart._launch_command() == [sys.executable, "--minimized"]

    def test_installed_launcher_on_path(self, monkeypatch):
        import shutil

        monkeypatch.delenv("APPIMAGE", raising=False)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/hsync-desktop")
        assert autostart._launch_command() == ["/usr/bin/hsync-desktop", "--minimized"]

    def test_source_run_falls_back_to_module(self, monkeypatch):
        import shutil

        monkeypatch.delenv("APPIMAGE", raising=False)
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert autostart._launch_command() == [
            sys.executable,
            "-m",
            "hsync_desktop",
            "--minimized",
        ]
