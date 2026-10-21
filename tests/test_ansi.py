# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the ANSI SGR parser behind the log panel colors."""

from __future__ import annotations

from hsync_desktop.ansi import AnsiRun, parse_sgr, strip_sgr


class TestParseSgr:
    def test_plain_text_is_one_run(self):
        assert parse_sgr("plain line") == [AnsiRun("plain line")]

    def test_color_applies_to_the_next_run_only(self):
        runs = parse_sgr("\x1b[33mWARNING\x1b[0m: rest")

        assert runs == [AnsiRun("WARNING", color=33), AnsiRun(": rest")]

    def test_bold_and_dim_are_separate_attributes(self):
        runs = parse_sgr("\x1b[1m\x1b[31mCRITICAL\x1b[0m")

        assert runs == [AnsiRun("CRITICAL", color=31, bold=True)]

        dim = parse_sgr("\x1b[2mtimestamp\x1b[0m")
        assert dim == [AnsiRun("timestamp", dim=True)]

    def test_combined_parameters(self):
        runs = parse_sgr("\x1b[1;36m[WS]\x1b[0m")

        assert runs == [AnsiRun("[WS]", color=36, bold=True)]

    def test_default_foreground_resets_only_the_color(self):
        runs = parse_sgr("\x1b[1m\x1b[32mGREEN\x1b[39m plain")

        assert runs == [AnsiRun("GREEN", color=32, bold=True), AnsiRun(" plain", bold=True)]

    def test_empty_sequence_is_a_reset(self):
        runs = parse_sgr("\x1b[31mred\x1b[mplain")

        assert runs == [AnsiRun("red", color=31), AnsiRun("plain")]

    def test_background_and_unknown_codes_are_ignored(self):
        runs = parse_sgr("\x1b[44;4mtext\x1b[0m")

        assert runs == [AnsiRun("text")]

    def test_strip_removes_every_sequence(self):
        assert strip_sgr("\x1b[2mts\x1b[0m - \x1b[31mERR\x1b[0m") == "ts - ERR"
