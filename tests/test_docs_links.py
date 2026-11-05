# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Documentation links: fixed HTTPS targets and safe external opening."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hsync_desktop import docs_links


@pytest.mark.parametrize(
    "url",
    [
        docs_links.SERVER_SETUP,
        docs_links.RENDEZVOUS_SETUP,
        docs_links.CONNECTION_MODES,
        docs_links.DOCS_INDEX,
        docs_links.GITHUB_REPO,
        docs_links.LATEST_RELEASE,
        docs_links.RELEASES,
        docs_links.TROUBLESHOOTING,
        docs_links.WATCHER_LIMITS,
    ],
)
def test_targets_are_fixed_https_github_links(url):
    assert url.startswith("https://github.com/albertsdk/hsync-")
    assert docs_links.is_allowed_docs_url(url)


def test_the_watcher_remedy_deep_links_into_the_client_guide():
    """The host remedy lives in the client guide, at a stable section anchor."""
    assert docs_links.WATCHER_LIMITS.startswith(
        "https://github.com/albertsdk/hsync-client/blob/main/docs/troubleshooting.md#"
    )
    assert docs_links.WATCHER_LIMITS != docs_links.TROUBLESHOOTING


def test_docs_index_is_the_documentation_landing_page():
    """Help → Documentation must open the docs index, not a guide page."""
    assert docs_links.DOCS_INDEX.endswith("/docs/README.md")
    assert docs_links.DOCS_INDEX != docs_links.CONNECTION_MODES


def test_a_release_tag_page_is_built_from_the_version():
    """The tag page is the landing that lists every asset of one release.

    The releases index renders only the first ten assets behind a "Show all N
    assets" toggle, so a `.deb`/`.rpm`/`.snap` looks missing there.
    """
    url = docs_links.release_tag_url("1.0.19")

    assert url == "https://github.com/albertsdk/hsync-desktop/releases/tag/v1.0.19"
    assert docs_links.is_allowed_docs_url(url)


@pytest.mark.parametrize(
    "version", ["", "nightly", "1", "1.0", "v1.0.19", "1.0.19-rc1", "1.0.19+build", "1.0.19/../.."]
)
def test_an_unusable_version_falls_back_to_the_releases_index(version):
    """Nothing unvalidated reaches a URL: the index is the safe landing."""
    assert docs_links.release_tag_url(version) == docs_links.RELEASES
    assert (
        docs_links.release_download_url(version, "hsync-desktop-amd64.deb") == docs_links.RELEASES
    )


def test_a_direct_asset_url_is_built_from_the_alias():
    """The fixed-name alias keeps the file name stable while the version is pinned."""
    url = docs_links.release_download_url("1.0.19", "hsync-desktop-x86_64.rpm")

    assert url == (
        "https://github.com/albertsdk/hsync-desktop/releases/download/v1.0.19/"
        "hsync-desktop-x86_64.rpm"
    )
    assert docs_links.is_allowed_docs_url(url)


@pytest.mark.parametrize(
    "asset", ["", "..", "../../etc/passwd", "a b.deb", "sub/dir.deb", ".hidden"]
)
def test_an_asset_name_that_is_a_path_is_rejected(asset):
    """A file name, never a path: a traversal cannot leave the release."""
    assert docs_links.release_download_url("1.0.19", asset) == docs_links.RELEASES


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/albertsdk/hsync-server",
        "https://example.com/albertsdk/hsync-server",
        "https://github.com/other/hsync-server",
        "https://github.com/albertsdk/other",
        "not-a-url",
    ],
)
def test_off_allowlist_targets_are_rejected(url):
    with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
        assert docs_links.open_docs_link(url) is False
    open_url.assert_not_called()


def test_an_allowed_target_is_opened():
    with patch.object(docs_links.QDesktopServices, "openUrl") as open_url:
        assert docs_links.open_docs_link(docs_links.SERVER_SETUP) is True
    open_url.assert_called_once()
