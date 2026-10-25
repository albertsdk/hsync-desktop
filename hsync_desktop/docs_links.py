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
CONNECTION_MODES = "https://github.com/albertsdk/hsync-desktop/blob/main/docs/usage.md"
# Help → Documentation opens the docs landing page, not the runtime guide the
# wizard's mode step and its "Not sure?" dialog deep-link through CONNECTION_MODES.
DOCS_INDEX = "https://github.com/albertsdk/hsync-desktop/blob/main/docs/README.md"
GITHUB_REPO = "https://github.com/albertsdk/hsync-desktop"

__all__ = [
    "BOOTNODE_SETUP",
    "CONNECTION_MODES",
    "DOCS_INDEX",
    "GITHUB_REPO",
    "SERVER_SETUP",
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
