# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Text helpers for widgets that read ``&`` as a keyboard mnemonic.

``QGroupBox``, ``QAbstractButton`` and the tab bar consume an ampersand as a
shortcut marker and underline the character after it, so a translated label such
as "Share & Path" would render as "Share_Path" (the space gets underlined).
Menus are the opposite case: there the single ``&`` *is* the Alt shortcut and
must stay untouched.

Consumers: ``settings/tab_layout.py``, ``settings/tab_translations.py``,
``settings/credential_dialogs.py`` and ``wizard/pages/connection.py``.
"""

from __future__ import annotations

__all__ = ["escape_mnemonics"]


def escape_mnemonics(text: str) -> str:
    """Return *text* with every ``&`` doubled, so Qt renders it literally.

    Apply it only at the sinks that parse mnemonics (group-box titles, button
    text, tab labels). A ``QLabel`` without a buddy, the combo-box items and the
    message boxes already display the ampersand and must receive the raw string.
    """

    return text.replace("&", "&&")
