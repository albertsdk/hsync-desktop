# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Centralised documentation URLs and safe external-link opening.

The URLs are fixed constants (never built from user input). ``open_docs_link``
accepts only HTTPS links to the project GitHub organisation, so a mistranslated
label or a future call site cannot turn a help link into an arbitrary
navigation.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

_GITHUB_ORG_PATH = "/albertsdk/hsync-"

SERVER_SETUP = "https://github.com/albertsdk/hsync-server/blob/main/docs/getting-started.md"
RENDEZVOUS_SETUP = "https://github.com/albertsdk/hsync-rendezvous/blob/main/docs/getting-started.md"
CONNECTION_MODES = "https://github.com/albertsdk/hsync-desktop/blob/main/docs/choose-connection.md"
# Linked from every persistent warning banner as the generic symptom guide
# (docs/troubleshooting.md). A warning whose remedy needs host commands links to
# WATCHER_LIMITS instead, so the copy-paste steps stay one click away.
TROUBLESHOOTING = "https://github.com/albertsdk/hsync-desktop/blob/main/docs/troubleshooting.md"
# Client troubleshooting section carrying the per-platform commands for the
# file-watcher/inotify and descriptor limits. The heading is a stable link target:
# renaming it here, in the desktop troubleshooting page or in the client page
# breaks the deep link silently.
WATCHER_LIMITS = (
    "https://github.com/albertsdk/hsync-client/blob/main/docs/"
    "troubleshooting.md#the-file-watcher-degrades-to-polling-inotify-limits"
)
# Help → Documentation opens the docs landing page, not the mode chooser the
# wizard's mode step and its "Not sure?" dialog deep-link through CONNECTION_MODES.
DOCS_INDEX = "https://github.com/albertsdk/hsync-desktop/blob/main/docs/README.md"
GITHUB_REPO = "https://github.com/albertsdk/hsync-desktop"
RELEASES = "https://github.com/albertsdk/hsync-desktop/releases"
# Redirect that resolves the newest release tag without the GitHub API rate
# limit; ``updates.py`` reads the tag from the final URL.
LATEST_RELEASE = "https://github.com/albertsdk/hsync-desktop/releases/latest"
# Per-version release pages. The releases *index* (``RELEASES``) renders only the
# first ten assets behind a "Show all N assets" toggle, so a `.deb`/`.rpm`/`.snap`
# looks missing there; the **tag** page lists every asset of the release and the
# **download** path serves one asset directly. Both are built from a version that
# passed :func:`_is_release_version`, so a URL never carries unvalidated input.
RELEASES_TAG_PREFIX = "https://github.com/albertsdk/hsync-desktop/releases/tag/"
RELEASES_DOWNLOAD_PREFIX = "https://github.com/albertsdk/hsync-desktop/releases/download/"

# The ``X.Y.Z`` version a stable release tag carries; a pre-release suffix cannot
# appear here because the check reads GitHub's *latest stable* redirect, and
# RELEASES.md §7 forbids ``+build`` in tags.
_RELEASE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# One file name, never a path: the leading character rules out ``..``.
_ASSET_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

__all__ = [
    "RENDEZVOUS_SETUP",
    "CONNECTION_MODES",
    "DOCS_INDEX",
    "GITHUB_REPO",
    "LATEST_RELEASE",
    "RELEASES",
    "RELEASES_DOWNLOAD_PREFIX",
    "RELEASES_TAG_PREFIX",
    "SERVER_SETUP",
    "TROUBLESHOOTING",
    "WATCHER_LIMITS",
    "is_allowed_docs_url",
    "open_docs_link",
    "release_download_url",
    "release_tag_url",
]


def _is_release_version(version: str) -> bool:
    """True for the ``X.Y.Z`` version a stable release tag carries."""
    return bool(_RELEASE_VERSION_RE.match(version))


def release_tag_url(version: str) -> str:
    """Return the release page of *version*, or the releases index when unusable.

    The tag page is what an operator needs to pick a package: unlike the
    releases index it lists **every** asset of that release.
    """
    if not _is_release_version(version):
        return RELEASES
    return f"{RELEASES_TAG_PREFIX}v{version}"


def release_download_url(version: str, asset: str) -> str:
    """Return the direct download URL of one asset of *version*.

    *asset* is one of the fixed-name aliases every release publishes
    (``RELEASES.md`` §5.8). A version or file name that fails validation returns
    the releases index instead of being pasted into a URL.
    """
    if not _is_release_version(version) or not _ASSET_NAME_RE.match(asset):
        return RELEASES
    return f"{RELEASES_DOWNLOAD_PREFIX}v{version}/{asset}"


def is_allowed_docs_url(url: str) -> bool:
    """True for the fixed HTTPS documentation targets on the project GitHub."""
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.netloc == "github.com"
        and parts.path.startswith(_GITHUB_ORG_PATH)
    )


def open_docs_link(url: str) -> bool:
    """Open a documentation link in the browser; reject anything off-allowlist."""
    if not is_allowed_docs_url(url):
        return False
    QDesktopServices.openUrl(QUrl(url))
    return True
