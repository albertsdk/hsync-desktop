# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.fonts (host font resolution)."""

from __future__ import annotations

import subprocess

import pytest
from PySide6.QtGui import QFont, QFontDatabase

import hsync_desktop.fonts as fonts


class TestParsePangoFont:
    def test_family_and_size(self):
        assert fonts.parse_pango_font("'Ubuntu 11'") == ("Ubuntu", 11.0)

    def test_family_with_spaces(self):
        assert fonts.parse_pango_font("'Ubuntu Sans 11'") == ("Ubuntu Sans", 11.0)

    def test_fractional_size_with_comma(self):
        assert fonts.parse_pango_font("'Noto Sans 10,5'") == ("Noto Sans", 10.5)

    def test_style_word_is_stripped_from_the_family(self):
        assert fonts.parse_pango_font("'Noto Sans Bold 11'") == ("Noto Sans", 11.0)

    def test_family_without_a_size(self):
        assert fonts.parse_pango_font("'Cantarell'") == ("Cantarell", None)

    def test_empty_values(self):
        assert fonts.parse_pango_font("") is None
        assert fonts.parse_pango_font("''") is None


class TestParseKdeFont:
    def test_family_and_point_size(self):
        assert fonts.parse_kde_font("Noto Sans,10,-1,5,50,0,0,0,0,0") == ("Noto Sans", 10.0)

    def test_family_only(self):
        assert fonts.parse_kde_font("Hack") == ("Hack", None)

    def test_invalid_size_is_ignored(self):
        assert fonts.parse_kde_font("Hack,abc,-1") == ("Hack", None)

    def test_empty_values(self):
        assert fonts.parse_kde_font("") is None
        assert fonts.parse_kde_font(",10,-1") is None


class TestHostEnv:
    def test_bundled_library_overrides_are_removed(self, monkeypatch):
        for key in fonts._LIBRARY_ENV_KEYS:
            monkeypatch.setenv(key, "/bundled")
        monkeypatch.setenv("HOME", "/home/probe")

        env = fonts._host_env()

        for key in fonts._LIBRARY_ENV_KEYS:
            assert key not in env
        assert env["HOME"] == "/home/probe"


class TestGsettingsValues:
    def test_reads_the_values_with_a_sanitized_environment(self, monkeypatch):
        captured: dict[str, object] = {}
        stdout = (
            "org.gnome.desktop.interface font-name 'Ubuntu 11'\n"
            "org.gnome.desktop.interface monospace-font-name 'Ubuntu Mono 13'\n"
            "org.gnome.desktop.interface text-scaling-factor 1.25\n"
        )

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

        monkeypatch.setattr(fonts.shutil, "which", lambda name: "/usr/bin/gsettings")
        monkeypatch.setattr(fonts.subprocess, "run", fake_run)
        monkeypatch.setenv("LD_LIBRARY_PATH", "/bundled")

        values = fonts._gsettings_values(
            ("font-name", "monospace-font-name", "text-scaling-factor")
        )

        assert values == {
            "font-name": "'Ubuntu 11'",
            "monospace-font-name": "'Ubuntu Mono 13'",
            "text-scaling-factor": "1.25",
        }
        assert captured["args"] == ["gsettings", "list-recursively", fonts._GSETTINGS_SCHEMA]
        env = captured["env"]
        assert isinstance(env, dict)
        assert "LD_LIBRARY_PATH" not in env

    def test_non_zero_exit_is_empty(self, monkeypatch):
        monkeypatch.setattr(fonts.shutil, "which", lambda name: "/usr/bin/gsettings")
        monkeypatch.setattr(
            fonts.subprocess,
            "run",
            lambda args, **kwargs: subprocess.CompletedProcess(args, 1, stdout="", stderr="err"),
        )
        assert fonts._gsettings_values(("font-name",)) == {}

    def test_timeout_is_empty(self, monkeypatch):
        monkeypatch.setattr(fonts.shutil, "which", lambda name: "/usr/bin/gsettings")

        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="gsettings", timeout=1.0)

        monkeypatch.setattr(fonts.subprocess, "run", fake_run)
        assert fonts._gsettings_values(("font-name",)) == {}

    def test_missing_binary_is_empty(self, monkeypatch):
        monkeypatch.setattr(fonts.shutil, "which", lambda name: None)
        assert fonts._gsettings_values(("font-name",)) == {}


class TestParseScale:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("1.25", 1.25), ("2.9", 2.9), ("5.0", 1.0), ("abc", 1.0), (None, 1.0)],
    )
    def test_values_are_parsed_and_clamped(self, raw, expected):
        assert fonts._parse_scale(raw) == expected


class TestResolveFont:
    def _fallback(self) -> QFont:
        font = QFont("Fallback")
        font.setPointSizeF(10.0)
        return font

    def test_family_and_size(self):
        result = fonts._resolve_font(("Probe UI", 11.0), self._fallback(), 1.0)
        assert result.family() == "Probe UI"
        assert result.pointSizeF() == pytest.approx(11.0)

    def test_scaling_is_applied(self):
        result = fonts._resolve_font(("Probe UI", 11.0), self._fallback(), 1.25)
        assert result.pointSizeF() == pytest.approx(13.75)

    def test_an_unknown_family_keeps_the_configured_size(self):
        """A family fontconfig must substitute still keeps the desktop's size."""
        result = fonts._resolve_font(("Cantarell", 11.0), self._fallback(), 1.0)
        assert result.family() == "Cantarell"
        assert result.pointSizeF() == pytest.approx(11.0)

    def test_no_size_uses_the_fallback_size(self):
        result = fonts._resolve_font(("Probe UI", None), self._fallback(), 1.0)
        assert result.pointSizeF() == pytest.approx(10.0)


class TestKdeFontFile:
    def test_reads_general_fonts(self, tmp_path, monkeypatch):
        (tmp_path / "kdeglobals").write_text(
            "[General]\nfont=Noto Sans,10,-1,5,50,0,0,0,0,0\nfixed=Hack,12,-1,5,50,0,0,0,0,0\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert fonts._kde_font("font") == "Noto Sans,10,-1,5,50,0,0,0,0,0"
        assert fonts._kde_font("fixed") == "Hack,12,-1,5,50,0,0,0,0,0"

    def test_missing_file_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert fonts._kde_font("font") is None

    def test_invalid_file_is_none(self, tmp_path, monkeypatch):
        (tmp_path / "kdeglobals").write_text("not an ini file\n", encoding="utf-8")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert fonts._kde_font("font") is None


class TestResolveSystemFonts:
    def test_gnome_uses_the_configured_fonts(self, qapp, monkeypatch):
        values = {
            "font-name": "'Probe UI 11'",
            "monospace-font-name": "'Probe Mono 12'",
            "text-scaling-factor": "1.0",
        }
        monkeypatch.setattr(fonts, "_desktop", lambda: "gnome")
        monkeypatch.setattr(fonts, "_gsettings_values", lambda keys: values)

        result = fonts.resolve_system_fonts()

        assert result.ui.family() == "Probe UI"
        assert result.ui.pointSizeF() == pytest.approx(11.0)
        assert result.mono.family() == "Probe Mono"
        assert result.mono.pointSizeF() == pytest.approx(12.0)

    def test_gnome_text_scaling_is_applied(self, qapp, monkeypatch):
        values = {
            "font-name": "'Probe UI 10'",
            "monospace-font-name": "'Probe Mono 10'",
            "text-scaling-factor": "1.5",
        }
        monkeypatch.setattr(fonts, "_desktop", lambda: "gnome")
        monkeypatch.setattr(fonts, "_gsettings_values", lambda keys: values)

        result = fonts.resolve_system_fonts()

        assert result.ui.pointSizeF() == pytest.approx(15.0)
        assert result.mono.pointSizeF() == pytest.approx(15.0)

    def test_an_uninstalled_family_keeps_the_configured_name_and_size(self, qapp, monkeypatch):
        monkeypatch.setattr(fonts, "_desktop", lambda: "gnome")
        monkeypatch.setattr(
            fonts, "_gsettings_values", lambda keys: {"font-name": "'Missing Font 11'"}
        )

        result = fonts.resolve_system_fonts()

        # The family is kept for Qt/fontconfig to substitute; the size is the
        # desktop's, not Qt's default (the visible difference on Ubuntu).
        assert result.ui.family() == "Missing Font"
        assert result.ui.pointSizeF() == pytest.approx(11.0)

    def test_kde_reads_kdeglobals(self, qapp, monkeypatch):
        values = {
            "font": "Probe KDE,10,-1,5,50,0,0,0,0,0",
            "fixed": "Probe KDE Mono,11,-1,5,50,0,0,0,0,0",
        }
        monkeypatch.setattr(fonts, "_desktop", lambda: "kde")
        monkeypatch.setattr(fonts, "_kde_font", lambda key: values.get(key))

        result = fonts.resolve_system_fonts()

        assert result.ui.family() == "Probe KDE"
        assert result.ui.pointSizeF() == pytest.approx(10.0)
        assert result.mono.family() == "Probe KDE Mono"
        assert result.mono.pointSizeF() == pytest.approx(11.0)

    def test_an_unknown_desktop_uses_the_system_fonts(self, qapp, monkeypatch):
        monkeypatch.setattr(fonts, "_desktop", lambda: "")

        result = fonts.resolve_system_fonts()

        base = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        assert result.ui.family() == base.family()


class TestApplySystemFonts:
    def test_sets_the_app_font_and_caches_both_fonts(self, qapp, monkeypatch):
        monkeypatch.setattr(fonts, "_mono_font", None)
        monkeypatch.setattr(fonts, "_ui_font", None)
        probe = QFont("Probe UI")
        probe.setPointSizeF(11.0)
        mono = QFont("Probe Mono")
        mono.setPointSizeF(12.0)
        monkeypatch.setattr(
            fonts,
            "resolve_system_fonts",
            lambda _font_scale=fonts.FONT_SCALE_STANDARD: fonts.SystemFonts(probe, mono),
        )
        previous = QFont(qapp.font())
        try:
            fonts.apply_system_fonts(qapp)

            assert qapp.font().family() == "Probe UI"
            assert fonts.ui_font().family() == "Probe UI"
            assert fonts.monospace_font().family() == "Probe Mono"
        finally:
            qapp.setFont(previous)
            monkeypatch.setattr(fonts, "_ui_font", None)

    def test_without_resolution_the_fixed_font_is_used(self, qapp, monkeypatch):
        monkeypatch.setattr(fonts, "_mono_font", None)

        expected = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        assert fonts.monospace_font().family() == expected.family()

    def test_without_resolution_the_general_font_is_used(self, qapp, monkeypatch):
        monkeypatch.setattr(fonts, "_ui_font", None)

        expected = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        assert fonts.ui_font().family() == expected.family()


class TestSmallMonospaceFont:
    """Dense text (log, license) is one point smaller, never below 8 pt."""

    def test_one_point_smaller(self, qapp, monkeypatch):
        base = QFont("Probe Mono")
        base.setPointSizeF(11.0)
        monkeypatch.setattr(fonts, "_mono_font", base)

        assert fonts.small_monospace_font().pointSizeF() == pytest.approx(10.0)

    def test_floor_at_eight(self, qapp, monkeypatch):
        base = QFont("Probe Mono")
        base.setPointSizeF(8.0)
        monkeypatch.setattr(fonts, "_mono_font", base)

        assert fonts.small_monospace_font().pointSizeF() == pytest.approx(8.0)

    def test_pixel_sized_font_is_unchanged(self, qapp, monkeypatch):
        base = QFont("Probe Mono")
        base.setPixelSize(12)
        monkeypatch.setattr(fonts, "_mono_font", base)

        assert fonts.small_monospace_font().pointSizeF() <= 0


class TestLogMonospaceFont:
    """The log viewer is two points smaller than the desktop monospace."""

    def test_two_points_smaller(self, qapp, monkeypatch):
        base = QFont("Probe Mono")
        base.setPointSizeF(11.0)
        monkeypatch.setattr(fonts, "_mono_font", base)

        assert fonts.log_monospace_font().pointSizeF() == pytest.approx(9.0)

    def test_floor_at_seven(self, qapp, monkeypatch):
        for size in (8.0, 7.0, 6.0):
            base = QFont("Probe Mono")
            base.setPointSizeF(size)
            monkeypatch.setattr(fonts, "_mono_font", base)

            assert fonts.log_monospace_font().pointSizeF() == pytest.approx(7.0)

    def test_smaller_than_the_license_font(self, qapp, monkeypatch):
        base = QFont("Probe Mono")
        base.setPointSizeF(12.0)
        monkeypatch.setattr(fonts, "_mono_font", base)

        assert fonts.log_monospace_font().pointSizeF() < fonts.small_monospace_font().pointSizeF()

    def test_pixel_sized_font_is_unchanged(self, qapp, monkeypatch):
        base = QFont("Probe Mono")
        base.setPixelSize(12)
        monkeypatch.setattr(fonts, "_mono_font", base)

        assert fonts.log_monospace_font().pointSizeF() <= 0


class TestTableFont:
    """The file table follows the global UI font scale (no extra delta)."""

    def test_follows_the_ui_font(self, qapp, monkeypatch):
        base = QFont("Probe UI")
        base.setPointSizeF(12.0)
        monkeypatch.setattr(fonts, "_ui_font", base)

        assert fonts.table_font().pointSizeF() == pytest.approx(12.0)

    def test_pixel_sized_font_is_unchanged(self, qapp, monkeypatch):
        base = QFont("Probe UI")
        base.setPixelSize(14)
        monkeypatch.setattr(fonts, "_ui_font", base)

        assert fonts.table_font().pointSizeF() <= 0

    def test_row_height_keeps_a_comfortable_target(self, qapp, monkeypatch):
        base = QFont("Probe UI")
        base.setPointSizeF(9.0)
        monkeypatch.setattr(fonts, "_ui_font", base)

        assert fonts.table_row_height() >= fonts._MIN_TABLE_ROW_HEIGHT


class TestCompactScale:
    """Compact shifts the UI and monospace bases one point down (floor 8 pt)."""

    def test_offset_reduces_and_floors(self, qapp):
        base = QFont("Probe")
        base.setPointSizeF(11.0)
        assert fonts._offset_font(base, -1.0, 8.0).pointSizeF() == pytest.approx(10.0)

        base.setPointSizeF(8.5)
        assert fonts._offset_font(base, -1.0, 8.0).pointSizeF() == pytest.approx(8.0)

    def test_resolve_compact_reduces_both_bases(self, qapp, monkeypatch):
        def system_font(kind):
            font = QFont("Probe")
            font.setPointSizeF(12.0 if kind == QFontDatabase.SystemFont.FixedFont else 11.0)
            return font

        monkeypatch.setattr(fonts.QFontDatabase, "systemFont", lambda kind: system_font(kind))
        monkeypatch.setattr(fonts, "_desktop", lambda: "")

        standard = fonts.resolve_system_fonts()
        compact = fonts.resolve_system_fonts(fonts.FONT_SCALE_COMPACT)

        assert standard.ui.pointSizeF() == pytest.approx(11.0)
        assert compact.ui.pointSizeF() == pytest.approx(10.0)
        assert standard.mono.pointSizeF() == pytest.approx(12.0)
        assert compact.mono.pointSizeF() == pytest.approx(11.0)
