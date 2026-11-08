# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the shared delayed busy feedback (``hsync_desktop.busy``)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from hsync_desktop.busy import BUSY_DELAY_MS, SPINNER_FRAMES, BusyText, busy_text


class TestBusyTextFormatting:
    def test_frames_are_single_cell(self):
        """Every frame must be one cell, or the label reflows on each step."""
        assert all(len(frame) == 1 for frame in SPINNER_FRAMES)

    def test_ellipsis_is_replaced_keeping_the_width(self):
        base = "Checking…"
        rendered = busy_text(base, SPINNER_FRAMES[0])
        assert rendered == "Checking" + SPINNER_FRAMES[0]
        assert len(rendered) == len(base)

    def test_a_long_ellipsis_form_is_handled(self):
        from hsync_desktop.i18n import tr

        base = tr("sync.state.checking")
        assert len(busy_text(base, SPINNER_FRAMES[0])) == len(base)

    def test_text_without_ellipsis_is_prefixed(self):
        assert busy_text("Working", SPINNER_FRAMES[0]) == f"{SPINNER_FRAMES[0]} Working"

    def test_empty_text_yields_the_frame(self):
        assert busy_text("", SPINNER_FRAMES[0]) == SPINNER_FRAMES[0]


class TestBusyTextAnimation:
    def test_nothing_changes_before_the_delay(self, qtbot):
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=5000)
        busy.set_text("Checking…")

        busy.start()
        assert label.text() == "Checking…"
        assert busy.is_animating is False

    def test_the_glyph_appears_after_the_delay(self, qtbot):
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=50)
        busy.set_text("Checking…")

        busy.start()
        qtbot.wait(200)

        assert busy.is_animating is True
        assert label.text()[-1] in SPINNER_FRAMES
        busy.stop()

    def test_the_frame_advances(self, qtbot):
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=0)
        busy.set_text("Checking…")

        busy.start()
        qtbot.wait(260)
        first = label.text()
        qtbot.wait(260)

        assert first[-1] in SPINNER_FRAMES
        assert label.text()[-1] in SPINNER_FRAMES
        busy.stop()

    def test_start_is_idempotent_while_pending(self, qtbot):
        """Repeated starts (every state re-render) must not postpone the delay."""
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=150)
        busy.set_text("Checking…")

        busy.start()
        for _ in range(20):
            busy.start()
            qtbot.wait(10)
        qtbot.wait(200)

        assert busy.is_animating is True
        busy.stop()

    def test_stop_before_the_delay_leaves_nothing_behind(self, qtbot):
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=200)
        busy.set_text("Checking…")

        busy.start()
        busy.stop()
        qtbot.wait(300)

        assert busy.is_animating is False
        assert label.text() == "Checking…"

    def test_stop_after_the_delay_restores_the_plain_text(self, qtbot):
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=0)
        busy.set_text("Checking…")

        busy.start()
        qtbot.wait(100)
        busy.stop()

        assert busy.is_animating is False
        assert label.text() == "Checking…"

    def test_set_text_while_animating_keeps_the_glyph(self, qtbot):
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=0)
        busy.set_text("Checking…")

        busy.start()
        qtbot.wait(100)
        busy.set_text("Caricamento…")

        assert label.text().startswith("Caricamento")
        assert label.text()[-1] in SPINNER_FRAMES
        busy.stop()

    def test_the_accessible_name_never_carries_the_glyph(self, qtbot):
        """A screen reader announces the plain state, not a changing glyph."""
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label, delay_ms=0)
        busy.set_text("Checking…")

        busy.start()
        qtbot.wait(200)

        assert label.accessibleName() == "Checking…"
        busy.stop()

    def test_the_default_delay_is_the_shared_threshold(self, qtbot, monkeypatch):
        import hsync_desktop.busy as busy_module

        monkeypatch.setattr(busy_module, "BUSY_DELAY_MS", 0)
        label = QLabel()
        qtbot.addWidget(label)
        busy = BusyText(label)
        busy.set_text("Checking…")

        busy.start()
        qtbot.wait(100)

        assert busy.is_animating is True
        busy.stop()
        assert BUSY_DELAY_MS == 2000
