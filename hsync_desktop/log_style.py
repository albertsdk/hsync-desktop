# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Colors for the log panel.

Two sources, applied in this order:

1. **The client's own palette.** The Desktop launches the engine with
   ``--color=always``, so every line carries the SGR sequences loguru produces
   from ``hsync_common.logger.LEVEL_STYLES`` and
   ``hsync_common.labels.LABEL_STYLES``. Those are rendered 1:1 through the
   theme-aware ANSI palette below, so the panel looks exactly like the terminal.
2. **The shared level/label contract** for lines that arrive without SGR (the
   Desktop's own ``[pid] [desktop] LEVEL:`` lines, plain logs): the same two
   mappings from ``hsync-common`` decide which span is colored — the level is
   located with the canonical ``hsync_common.logger.LOG_LINE_RE`` grammar, so
   the panel reads client and Desktop lines with one parser — and the panel
   translates their tag names to the same Qt colors.

The perceived colors are Desktop-owned on purpose: the terminal palette belongs
to the terminal, while the GUI must stay readable on its own light/dark
backgrounds. Consumers: ``main_window/ui.py`` (log appends and the re-render on
a theme change).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hsync_common.labels import LABEL_STYLES
from hsync_common.logger import LEVEL_STYLES, LOG_LINE_RE
from PySide6.QtGui import QColor, QFont, QTextCharFormat

from hsync_desktop.ansi import AnsiRun, parse_sgr
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT

__all__ = ["LOG_COLORS", "StyledRun", "styled_runs"]

#: Semantic color name -> hex, per theme. ``dim`` is the muted tone used by
#: both the DEBUG level and the no-op labels; the bright* entries exist for SGR
#: codes the client could start emitting. ``black``/``white`` are inverted in
#: the dark theme so an explicit SGR color never turns invisible.
LOG_COLORS: dict[str, dict[str, str]] = {
    THEME_LIGHT: {
        "black": "#1E1E1E",
        "red": "#C62828",
        "green": "#2E7D32",
        "yellow": "#8D6E00",
        "blue": "#1565C0",
        "magenta": "#8E24AA",
        "cyan": "#00707A",
        "white": "#1E1E1E",
        "bright_black": "#5A5A5A",
        "bright_red": "#D32F2F",
        "bright_green": "#388E3C",
        "bright_yellow": "#9A7B00",
        "bright_blue": "#1976D2",
        "bright_magenta": "#AB47BC",
        "bright_cyan": "#00838F",
        "bright_white": "#1E1E1E",
        "dim": "#6A6A6A",
    },
    THEME_DARK: {
        "black": "#D4D4D4",
        "red": "#EF9A9A",
        "green": "#81C784",
        "yellow": "#FFD866",
        "blue": "#64B5F6",
        "magenta": "#F48FB1",
        "cyan": "#4DD0E1",
        "white": "#D4D4D4",
        "bright_black": "#B0B0B0",
        "bright_red": "#FF8A80",
        "bright_green": "#A5D6A7",
        "bright_yellow": "#FFE082",
        "bright_blue": "#90CAF9",
        "bright_magenta": "#F8BBD0",
        "bright_cyan": "#80DEEA",
        "bright_white": "#FFFFFF",
        "dim": "#9A9A9A",
    },
}


_ANSI_NAMES: dict[int, str] = {
    30: "black",
    31: "red",
    32: "green",
    33: "yellow",
    34: "blue",
    35: "magenta",
    36: "cyan",
    37: "white",
    90: "bright_black",
    91: "bright_red",
    92: "bright_green",
    93: "bright_yellow",
    94: "bright_blue",
    95: "bright_magenta",
    96: "bright_cyan",
    97: "bright_white",
}

#: loguru color tag -> semantic name (``<cyan>`` -> ``cyan``).
_TAG_NAMES: dict[str, str] = {
    "black": "black",
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "white": "white",
    "dim": "dim",
}

# The canonical grammar (``hsync_common.logger.LOG_LINE_RE``) locates the level:
# "<ts> - [pid] [cid|desktop] LEVEL: message". Shared with the client and with
# the engine's own ERROR harvest, so no consumer re-encodes the shape.

# Longest-first so "[REMOTE DOWNLOAD]" wins over "[DOWNLOAD]" at the same spot.
_LABEL_RE = re.compile(
    "|".join(re.escape(label) for label in sorted(LABEL_STYLES, key=len, reverse=True))
)


@dataclass(frozen=True)
class StyledRun:
    """A piece of a log line plus the format to render it with."""

    text: str
    fmt: QTextCharFormat


def styled_runs(line: str, theme: str = THEME_LIGHT) -> list[StyledRun]:
    """Return the runs to render *line* with, using *theme*'s palette."""

    colors = LOG_COLORS.get(theme, LOG_COLORS[THEME_LIGHT])
    ansi_runs = parse_sgr(line)
    if any(run.color is not None or run.bold or run.dim for run in ansi_runs):
        return [_run(run, colors) for run in ansi_runs if run.text]
    return _fallback_runs(line, colors)


def _run(run: AnsiRun, colors: dict[str, str]) -> StyledRun:
    name = _ANSI_NAMES.get(run.color) if run.color is not None else None
    if name is None and run.dim:
        name = "dim"
    return StyledRun(run.text, _format(colors, name, bold=run.bold))


def _fallback_runs(line: str, colors: dict[str, str]) -> list[StyledRun]:
    """Color a line without SGR from the shared level/label mappings."""

    spans: list[tuple[int, int, str | None, bool]] = []

    record = LOG_LINE_RE.match(line)
    if record is not None:
        start, end = record.span("level")
        name, bold = _tag_style(LEVEL_STYLES.get(record.group("level"), ("", "")))
        spans.append((start, end, name, bold))

    for match in _LABEL_RE.finditer(line):
        name, bold = _tag_style(LABEL_STYLES[match.group(0)])
        spans.append((match.start(), match.end(), name, bold))

    if not spans:
        return [StyledRun(line, QTextCharFormat())]

    runs: list[StyledRun] = []
    position = 0
    for start, end, name, bold in sorted(spans):
        if start < position:  # overlapping span: keep the first, longest one
            continue
        if start > position:
            runs.append(StyledRun(line[position:start], QTextCharFormat()))
        runs.append(StyledRun(line[start:end], _format(colors, name, bold=bold)))
        position = end
    if position < len(line):
        runs.append(StyledRun(line[position:], QTextCharFormat()))
    return [run for run in runs if run.text]


def _tag_style(tags: tuple[str, str]) -> tuple[str | None, bool]:
    """Translate a loguru tag pair (``<bold><red>``) to (name, bold)."""

    opening = tags[0]
    bold = "<bold>" in opening
    for tag, name in _TAG_NAMES.items():
        if f"<{tag}>" in opening:
            return name, bold
    return None, bold


def _format(colors: dict[str, str], name: str | None, *, bold: bool = False) -> QTextCharFormat:
    """Build the char format for a semantic color name."""

    fmt = QTextCharFormat()
    if name is not None and (hex_color := colors.get(name)):
        fmt.setForeground(QColor(hex_color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    return fmt
