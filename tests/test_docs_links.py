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
        docs_links.BOOTNODE_SETUP,
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
