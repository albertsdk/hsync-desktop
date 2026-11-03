# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Which release artifact the update dialog must offer to this installation."""

from __future__ import annotations

import pytest

from hsync_desktop import release_assets
from hsync_desktop.docs_links import RELEASES, is_allowed_docs_url

VERSION = "1.0.18"
DOWNLOAD = "https://github.com/albertsdk/hsync-desktop/releases/download/v1.0.18/"
TAG_PAGE = "https://github.com/albertsdk/hsync-desktop/releases/tag/v1.0.18"


class TestInstallChannel:
    """The packaging channel the process runs from."""

    @pytest.mark.parametrize(
        ("platform_name", "environ", "expected"),
        [
            ("linux", {"SNAP": "/snap/hsync-desktop/42"}, "snap"),
            ("linux", {"APPIMAGE": "/opt/hsync-desktop.AppImage"}, "appimage"),
            ("win32", {}, "windows"),
            ("darwin", {}, "macos"),
        ],
    )
    def test_the_runtime_markers_are_checked_first(self, platform_name, environ, expected):
        """A snap on Ubuntu is a snap before it is a `.deb` host."""
        assert (
            release_assets.install_channel(platform_name=platform_name, environ=environ) == expected
        )

    @pytest.mark.parametrize(
        ("os_release", "expected"),
        [
            ("ID=debian\n", "deb"),
            ("ID=ubuntu\nID_LIKE=debian\n", "deb"),
            ('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "deb"),
            ("ID=fedora\n", "rpm"),
            ('ID=rocky\nID_LIKE="rhel centos fedora"\n', "rpm"),
            ("ID=alpine\n", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_the_linux_family_names_the_package_manager(
        self, tmp_path, monkeypatch, os_release, expected
    ):
        path = tmp_path / "os-release"
        path.write_text(os_release, encoding="utf-8")
        monkeypatch.setattr(release_assets, "OS_RELEASE_PATH", path)

        assert release_assets.install_channel(platform_name="linux", environ={}) == expected

    def test_an_unreadable_os_release_is_unknown_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(release_assets, "OS_RELEASE_PATH", tmp_path / "missing")

        assert release_assets.install_channel(platform_name="linux", environ={}) == "unknown"


class TestPackageAsset:
    @pytest.mark.parametrize(
        ("channel", "machine", "expected"),
        [
            ("deb", "x86_64", "hsync-desktop-amd64.deb"),
            ("deb", "aarch64", "hsync-desktop-arm64.deb"),
            ("rpm", "x86_64", "hsync-desktop-x86_64.rpm"),
            ("rpm", "aarch64", "hsync-desktop-aarch64.rpm"),
            ("appimage", "x86_64", "hsync-desktop-x86_64.AppImage"),
            ("windows", "AMD64", "hsync-desktop-windows-amd64-setup.exe"),
            ("macos", "arm64", "hsync-desktop-darwin-arm64.dmg"),
            ("macos", "x86_64", "hsync-desktop-darwin-amd64.dmg"),
        ],
    )
    def test_every_shipped_format_names_its_stable_alias(self, channel, machine, expected):
        assert release_assets.package_asset(channel, machine) == expected

    @pytest.mark.parametrize(
        ("channel", "machine"),
        [
            ("snap", "x86_64"),  # refreshes itself; the tag page carries the offline `.snap`
            ("appimage", "aarch64"),  # no arm64 AppImage is built
            ("deb", "armv7l"),  # no 32-bit build
            ("unknown", "x86_64"),
        ],
    )
    def test_a_format_without_a_build_has_no_asset(self, channel, machine):
        assert release_assets.package_asset(channel, machine) is None


class TestPackageUrl:
    def test_the_artifact_of_this_installation_wins(self):
        url = release_assets.package_url(VERSION, channel="deb", machine="x86_64")

        assert url == f"{DOWNLOAD}hsync-desktop-amd64.deb"
        assert is_allowed_docs_url(url)

    def test_an_unresolvable_channel_falls_back_to_the_tag_page(self):
        """The tag page lists every asset; the index hides all but the first ten."""
        url = release_assets.package_url(VERSION, channel="snap", machine="x86_64")

        assert url == TAG_PAGE
        assert is_allowed_docs_url(url)

    def test_an_unusable_version_never_builds_a_download_url(self):
        assert release_assets.package_url("nightly", channel="deb", machine="x86_64") == RELEASES
