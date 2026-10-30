# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the log panel colors (client palette + shared level/label fallback)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextFormat

from hsync_desktop.log_style import LOG_COLORS, styled_runs
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT

_LIGHT = LOG_COLORS[THEME_LIGHT]
_DARK = LOG_COLORS[THEME_DARK]


def _hex(value: str) -> str:
    """Normalise a palette hex the way QColor reports it (lowercase)."""

    return QColor(value).name()


def _color(fmt) -> str | None:
    if not fmt.hasProperty(QTextFormat.Property.ForegroundBrush):
        return None
    return fmt.foreground().color().name()


def _colored(line: str, theme: str = THEME_LIGHT) -> dict[str, str | None]:
    """Map each non-empty run's text to its foreground color (None = default)."""

    return {run.text: _color(run.fmt) for run in styled_runs(line, theme) if run.text}


class TestClientPalette:
    """Lines carrying the client's SGR keep its own classification."""

    def test_warning_and_transfer_label(self):
        line = (
            "\x1b[2m2026-10-21T14:48:07Z\x1b[0m - [1] [N/A] \x1b[33mWARNING\x1b[0m: "
            "\x1b[36m[DOWNLOAD]\x1b[0m a.txt"
        )

        colors = _colored(line)

        assert colors["WARNING"] == _hex(_LIGHT["yellow"])
        assert colors["[DOWNLOAD]"] == _hex(_LIGHT["cyan"])
        assert colors["2026-10-21T14:48:07Z"] == _hex(_LIGHT["dim"])

    def test_critical_is_bold_red(self):
        runs = styled_runs("\x1b[1m\x1b[31mCRITICAL\x1b[0m: boom")

        assert _color(runs[0].fmt) == _hex(_LIGHT["red"])
        assert runs[0].fmt.fontWeight() > 400

    def test_the_palette_follows_the_theme(self):
        line = "\x1b[33mWARNING\x1b[0m: x"

        assert _colored(line, THEME_LIGHT)["WARNING"] == _hex(_LIGHT["yellow"])
        assert _colored(line, THEME_DARK)["WARNING"] == _hex(_DARK["yellow"])
        assert _hex(_LIGHT["yellow"]) != _hex(_DARK["yellow"])

    def test_text_never_keeps_the_escape_sequences(self):
        runs = styled_runs("\x1b[31mERROR\x1b[0m: boom")

        assert "".join(run.text for run in runs) == "ERROR: boom"


class TestLevelAndLabelFallback:
    """Lines without SGR (desktop markers, plain logs) use the shared mapping."""

    def test_desktop_error_level_is_colored(self):
        colors = _colored("2026-10-21T14:48:08Z - [41234] [desktop] ERROR: [EVENT ERROR] boom")

        assert colors["ERROR"] == _hex(_LIGHT["red"])

    def test_client_and_desktop_lines_share_the_level_category(self):
        # One panel, one palette: only the identity field differs.
        client = _colored("2026-10-21T14:48:08.123Z - [1] [cid] WARNING: x")
        desktop = _colored("2026-10-21T14:48:08.123Z - [41234] [desktop] WARNING: x")

        assert client["WARNING"] == desktop["WARNING"] == _hex(_LIGHT["yellow"])

    def test_desktop_timestamp_is_dimmed_like_the_client(self):
        """A SGR-free desktop line dims its timestamp like the engine's lines.

        The client wraps the timestamp in ``<dim>``; without the same treatment
        the desktop's own lines showed the same column in the default text color,
        so one panel looked like two.
        """
        colors = _colored("2026-10-21T14:48:08.123Z - [41234] [desktop] INFO: x")

        assert colors["2026-10-21T14:48:08.123Z"] == _hex(_LIGHT["dim"])

    def test_label_category_is_applied(self):
        colors = _colored("2026-10-21T14:48:08Z - [1] [cid] INFO: [DELETE] gone.txt")

        assert colors["[DELETE]"] == _hex(_LIGHT["red"])

    def test_longest_label_wins(self):
        colors = _colored("2026-10-21T14:48:08Z - [1] [cid] INFO: [REMOTE DOWNLOAD] a.bin")

        assert "[REMOTE DOWNLOAD]" in colors
        assert "[DOWNLOAD]" not in colors

    def test_plain_line_has_a_single_default_run(self):
        runs = styled_runs("just a message")

        assert len(runs) == 1
        assert runs[0].text == "just a message"
        assert _color(runs[0].fmt) is None

    def test_phase_marker_is_bold(self):
        runs = styled_runs("2026-10-21T14:48:08Z - [1] [cid] INFO: [INITIAL SYNC] start")
        marker = next(run for run in runs if run.text == "[INITIAL SYNC]")

        assert marker.fmt.fontWeight() > 400

    def test_error_color_is_readable_in_both_themes(self):
        assert QColor(_hex(_LIGHT["red"])).lightness() < QColor(_hex(_DARK["red"])).lightness()
