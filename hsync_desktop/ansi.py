# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""ANSI SGR parsing for the log panel.

The client colorizes its stdout with loguru, which emits SGR escape sequences
(``\\x1b[33m`` yellow, ``\\x1b[1m`` bold, ``\\x1b[0m`` reset, ...). The Desktop
launches it with ``--color=always``, so the raw log feed carries those
sequences and the panel can reproduce the client's own palette instead of
inventing a second one.

Only the attributes the shared log palette can express are tracked (foreground
color, bold, dim); everything else is stripped. Consumers:
``hsync_desktop/log_style.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["AnsiRun", "parse_sgr", "strip_sgr"]

#: Complete SGR sequence: ESC [ params m (params may be empty: reset).
_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# SGR parameters understood by the palette.
_RESET = 0
_BOLD = 1
_DIM = 2
_NORMAL_INTENSITY = 22
_DEFAULT_FOREGROUND = 39
_FG_STANDARD = range(30, 38)
_FG_BRIGHT = range(90, 98)


@dataclass(frozen=True)
class AnsiRun:
    """A piece of a log line with the SGR state that applies to it."""

    text: str
    color: int | None = None  # SGR foreground parameter (30-37, 90-97)
    bold: bool = False
    dim: bool = False


def parse_sgr(line: str) -> list[AnsiRun]:
    """Split *line* into runs, tracking the SGR state in effect for each."""

    runs: list[AnsiRun] = []
    color: int | None = None
    bold = False
    dim = False
    position = 0
    for match in _SGR_RE.finditer(line):
        text = line[position : match.start()]
        if text:
            runs.append(AnsiRun(text, color, bold, dim))
        position = match.end()
        for code in _parameters(match.group(1)):
            if code == _RESET:
                color, bold, dim = None, False, False
            elif code == _BOLD:
                bold = True
            elif code == _DIM:
                dim = True
            elif code == _NORMAL_INTENSITY:
                bold = dim = False
            elif code == _DEFAULT_FOREGROUND:
                color = None
            elif code in _FG_STANDARD or code in _FG_BRIGHT:
                color = code
    tail = line[position:]
    if tail:
        runs.append(AnsiRun(tail, color, bold, dim))
    return runs


def strip_sgr(line: str) -> str:
    """Return *line* without its SGR sequences."""

    return _SGR_RE.sub("", line)


def _parameters(raw: str) -> list[int]:
    """Parse an SGR parameter list; an empty list means reset."""

    if not raw:
        return [_RESET]
    codes: list[int] = []
    for part in raw.split(";"):
        try:
            codes.append(int(part))
        except ValueError:
            continue
    return codes or [_RESET]
