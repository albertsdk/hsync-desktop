# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Contextual documentation links.

A link is a muted, word-wrapped ``QLabel`` whose rich-text anchor opens a fixed
documentation URL through :func:`hsync_desktop.docs_links.open_docs_link`.
``LinksAccessibleByKeyboard`` keeps it reachable with Tab/Enter, and the URL is
stored on the label so a language change can rebuild the text without losing
the target.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from hsync_desktop.docs_links import open_docs_link
from hsync_desktop.i18n import tr

__all__ = ["help_link", "set_help_link_text"]

_HELP_URL_PROPERTY = "docsUrl"
_EXTERNAL_ARROW = "\u2197"


def _rich_text(text: str, url: str) -> str:
    """Compose the anchor, escaping the translated text and the URL."""
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)} {_EXTERNAL_ARROW}</a>'


def set_help_link_text(label: QLabel, text_key: str) -> None:
    """Rebuild the link text after a language change, keeping its URL."""
    url = str(label.property(_HELP_URL_PROPERTY) or "")
    if not url:
        return
    label.setText(_rich_text(tr(text_key), url))
    label.setToolTip(url)
    label.setAccessibleName(tr(text_key))


def help_link(text_key: str, url: str) -> QLabel:
    """A word-wrapped, keyboard-accessible link to a documentation page."""
    label = QLabel()
    label.setObjectName("helpLink")
    label.setProperty(_HELP_URL_PROPERTY, url)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextBrowserInteraction
        | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
    )
    label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    label.setWordWrap(True)
    label.setCursor(Qt.CursorShape.PointingHandCursor)
    label.setOpenExternalLinks(False)
    label.linkActivated.connect(open_docs_link)
    set_help_link_text(label, text_key)
    return label
