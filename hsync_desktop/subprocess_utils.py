# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Alberto Basso

"""Spawn helpers that keep console children from opening their own window.

A ``--windowed`` (console-less) Windows parent does not give its console
children a console: each one opens a new console window unless the process is
created with ``CREATE_NO_WINDOW``. The flag is meaningless elsewhere, so these
helpers are no-ops off Windows and callers can always splat the kwargs.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TypedDict

_IS_WINDOWS = sys.platform == "win32"


class NoConsoleKwargs(TypedDict, total=False):
    """Keyword arguments accepted by ``subprocess`` spawn functions."""

    creationflags: int


def create_no_window() -> int:
    """Return ``CREATE_NO_WINDOW`` on Windows, ``0`` elsewhere."""
    if not _IS_WINDOWS:
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def no_console_kwargs() -> NoConsoleKwargs:
    """``subprocess`` kwargs that suppress a child console window.

    Empty off Windows, so a call site can pass ``**no_console_kwargs()``
    unconditionally without changing non-Windows behavior.
    """
    flag = create_no_window()
    return {"creationflags": flag} if flag else {}
