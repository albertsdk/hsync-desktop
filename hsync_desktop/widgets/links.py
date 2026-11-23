# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Contextual documentation links.

A link is a muted, word-wrapped ``QLabel`` whose rich-text anchor opens a fixed
documentation URL through :func:`hsync_desktop.docs_links.open_docs_link`.
``LinksAccessibleByKeyboard`` keeps it reachable with Tab/Enter, and the URL is
stored on the label so a language change can rebuild the text without losing the
target.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QBoxLayout, QDialogButtonBox, QLabel, QSizePolicy

from hsync_desktop.docs_links import open_docs_link
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon

__all__ = [
    "help_link",
    "insert_help_link_above",
    "set_help_link_text",
    "set_help_link_url",
]

_HELP_URL_PROPERTY = "docsUrl"
_HELP_COLOR_PROPERTY = "docsColor"
_EXTERNAL_ARROW = "\u2197"
# Rendered size of the optional leading icon and the gap that separates it from
# the text; together they become the label's left inset.
_LEADING_ICON_PX = 16
_LEADING_ICON_GAP = 6


class _HelpLinkLabel(QLabel):
    """A link label sized to the height it actually needs.

    A word-wrapped rich-text ``QLabel`` reports the height its *text document*
    needs at the document's ideal (very narrow) width as ``sizeHint``: a
    one-line link claims three lines, and the form row around it keeps that
    dead space. Answer the hint with the wrapped height at the width the label
    really has.

    An optional leading icon is painted into the left inset the label reserves,
    so the affordance stays a single ``QLabel`` (text, link signal and
    ``docsUrl`` property unchanged) and the icon follows the theme.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._leading_icon_name: str | None = None

    def set_leading_icon(self, name: str | None) -> None:
        """Reserve room for *name*'s glyph on the left and repaint."""
        self._leading_icon_name = name
        left = _LEADING_ICON_PX + _LEADING_ICON_GAP if name else 0
        self.setContentsMargins(left, 0, 0, 0)
        self.updateGeometry()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().paintEvent(event)
        name = self._leading_icon_name
        if not name:
            return
        pixmap = icon(name).pixmap(
            QSize(_LEADING_ICON_PX, _LEADING_ICON_PX), self.devicePixelRatioF()
        )
        if pixmap.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(0, (self.height() - _LEADING_ICON_PX) // 2, pixmap)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        hint = super().sizeHint()
        width = self.width() if self.width() > 0 else hint.width()
        return QSize(hint.width(), self.heightForWidth(width))


def _rich_text(text: str, url: str, color: str | None = None) -> str:
    """Compose the anchor, escaping the translated text and the URL.

    The anchor is always underlined: a link identified by colour alone fails
    WCAG 1.4.1, and a label's QSS ``color`` does not reach a rich-text anchor.
    ``color`` overrides the underline colour for surfaces whose background makes
    the theme's link colour unreadable (inline, because QSS cannot reach it).
    """
    style = "text-decoration: underline;"
    if color:
        style = f"color: {html.escape(color, quote=True)}; {style}"
    return (
        f'<a style="{style}" href="{html.escape(url, quote=True)}">'
        f"{html.escape(text)} {_EXTERNAL_ARROW}</a>"
    )


def set_help_link_text(label: QLabel, text_key: str) -> None:
    """Rebuild the link text after a language change, keeping its URL and color."""
    url = str(label.property(_HELP_URL_PROPERTY) or "")
    if not url:
        return
    color = str(label.property(_HELP_COLOR_PROPERTY) or "") or None
    label.setText(_rich_text(tr(text_key), url, color))
    label.setToolTip(url)
    label.setAccessibleName(tr(text_key))


def set_help_link_url(label: QLabel, text_key: str, url: str) -> None:
    """Retarget an existing link label to *url* and rebuild its text.

    Lets a reused link (the toast's guide affordance) follow the context that
    showed it instead of being recreated per message.
    """
    label.setProperty(_HELP_URL_PROPERTY, url)
    set_help_link_text(label, text_key)


def help_link(
    text_key: str, url: str, *, color: str | None = None, icon: str | None = None
) -> QLabel:
    """A word-wrapped, keyboard-accessible link to a documentation page.

    ``color`` is an optional explicit anchor color for a coloured surface (the
    overlay toast), where the theme's link color would not contrast; language
    changes keep it through the stored property. ``icon`` names a bundled icon
    drawn before the text (the settings' contextual help affordance), which keeps
    the link recognisable without relying on the label alone.
    """
    label = _HelpLinkLabel()
    label.setObjectName("helpLink")
    label.setProperty(_HELP_URL_PROPERTY, url)
    label.setProperty(_HELP_COLOR_PROPERTY, color or "")
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextBrowserInteraction
        | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
    )
    label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    label.setWordWrap(True)
    # A help link is one row: never let a tall layout hand it the spare vertical
    # space (it would read as an empty gap between the content and the buttons).
    # ``Maximum`` keeps the wrapped height ``sizeHint`` reports at the real width.
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    label.setCursor(Qt.CursorShape.PointingHandCursor)
    label.setOpenExternalLinks(False)
    label.linkActivated.connect(open_docs_link)
    label.set_leading_icon(icon)
    set_help_link_text(label, text_key)
    return label


def insert_help_link_above(button_box: QDialogButtonBox, text_key: str, url: str) -> QLabel:
    """Add a help link as the row just above *button_box*'s row.

    The convention of the dialogs that own a procedure: one link, next to the
    action it explains, to the page that documents that dialog — never a link per
    field. It carries the same ``help-about`` glyph as the settings tabs, so the
    affordance is identical across the app.
    """
    link = help_link(text_key, url, icon="help-about")
    parent = button_box.parentWidget()
    layout = parent.layout() if parent is not None else None
    if isinstance(layout, QBoxLayout):
        index = layout.indexOf(button_box)
        layout.insertWidget(index if index >= 0 else layout.count(), link)
    return link
