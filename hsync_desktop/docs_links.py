# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Centralised documentation URLs and safe external-link opening.

The URLs are fixed constants (never built from user input). ``open_docs_link``
accepts only HTTPS links to the project GitHub organisation, so a mistranslated
label or a future call site cannot turn a help link into an arbitrary
navigation.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

_GITHUB_ORG_PATH = "/albertsdk/hsync-"

SERVER_SETUP = "https://github.com/albertsdk/hsync-server/blob/main/docs/getting-started.md"
BOOTNODE_SETUP = "https://github.com/albertsdk/hsync-bootnode/blob/main/docs/getting-started.md"
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

__all__ = [
    "BOOTNODE_SETUP",
    "CONNECTION_MODES",
    "DOCS_INDEX",
    "GITHUB_REPO",
    "SERVER_SETUP",
    "TROUBLESHOOTING",
    "WATCHER_LIMITS",
    "is_allowed_docs_url",
    "open_docs_link",
]


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
