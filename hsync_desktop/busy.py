# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Delayed "work in progress" feedback shared by every long task.

Showing a busy indicator the instant a task starts is wrong twice: a fast task
flashes something that appears and disappears, and a slow one leaves the user
wondering whether anything is happening at all. The rule here is the standard
one — do nothing for :data:`BUSY_DELAY_MS`, show the indicator only if the task
is still running after that — and it is implemented once so every surface uses
the same threshold and the same glyph.

The glyph is a single-cell braille spinner, so replacing the last character of a
label (or prefixing it) never changes the label's width and the layout cannot
jump. Consumers: the sync-state label (a comparison is running) and the file
panel's loading overlay (a folder scan is running).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

__all__ = [
    "BUSY_DELAY_MS",
    "BUSY_FRAME_MS",
    "SPINNER_FRAMES",
    "BusyText",
    "busy_text",
]

# How long a task may run before its indicator appears. Below this a task is
# effectively instantaneous, and any animation would only flicker.
BUSY_DELAY_MS = 2000
# One animation step. Fast enough to read as motion, slow enough to stay calm.
BUSY_FRAME_MS = 125

# Braille spinner frames: every frame is a single cell, so a label that swaps its
# trailing ellipsis for one of these keeps the exact same width.
SPINNER_FRAMES = "⣾⣽⣻⢿⡿⣟⣯⣷"


def busy_text(base: str, frame: str) -> str:
    """Return *base* with the busy glyph worked in without changing its width.

    A label that ends with an ellipsis ("Checking…") swaps that ellipsis for the
    frame; anything else gets the frame and a space in front. The ellipsis form is
    the one every busy label in the app uses, so the common case never reflows.
    """
    if not base:
        return frame
    if base.endswith("…"):
        return base[:-1] + frame
    return f"{frame} {base}"


class BusyText(QObject):
    """Animate a ``QLabel`` with the busy glyph, after a delay.

    ``start()`` arms the delay; nothing changes until it elapses. Past the delay
    the label shows ``busy_text(base, frame)`` and the frame advances every
    :data:`BUSY_FRAME_MS`. Calling ``start()`` again while the indicator is
    pending or running is a no-op on the timers — the busy labels are re-rendered
    on every state change, and re-arming there would postpone the delay forever.
    ``stop()`` clears both timers and restores the plain text immediately.

    The accessible name stays the plain text, so a screen reader announces
    "Checking…" once instead of a glyph that changes eight times a second.
    """

    def __init__(
        self,
        label,
        *,
        delay_ms: int | None = None,
    ) -> None:
        super().__init__(label)
        self._label = label
        self._delay_ms = delay_ms
        self._base = ""
        self._index = 0
        self._pending = False
        self._animating = False
        # Timers are parented to this QObject, so they die with the label.
        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._begin)
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(BUSY_FRAME_MS)
        self._frame_timer.timeout.connect(self._advance)

    @property
    def is_animating(self) -> bool:
        """True while the glyph is on screen (the delay has elapsed)."""
        return self._animating

    def set_text(self, text: str) -> None:
        """Set the plain text, keeping the current animation state.

        While the delay is still pending the label shows the new base text (a
        language change must not wait for the glyph), and while animating it keeps
        the glyph.
        """
        self._base = text
        self._label.setAccessibleName(text)
        if self._animating:
            self._label.setText(busy_text(text, SPINNER_FRAMES[self._index]))
        else:
            self._label.setText(text)

    def start(self, delay_ms: int | None = None) -> None:
        """Arm the delay; a no-op when already pending or animating.

        ``delay_ms`` overrides the configured delay for this call (``0`` starts
        the animation at once). It exists for a surface that owns the visibility
        timing itself and only needs the glyph when its own timer fires.
        """
        if self._pending or self._animating:
            return
        self._pending = True
        self._label.setText(self._base)
        if delay_ms is None:
            delay_ms = self._delay_ms if self._delay_ms is not None else BUSY_DELAY_MS
        self._delay_timer.start(delay_ms)

    def stop(self) -> None:
        """Cancel the delay, stop the animation and restore the plain text."""
        self._delay_timer.stop()
        self._frame_timer.stop()
        self._pending = False
        self._animating = False
        self._index = 0
        self._label.setText(self._base)

    def _begin(self) -> None:
        self._pending = False
        self._animating = True
        self._index = 0
        self._label.setText(busy_text(self._base, SPINNER_FRAMES[0]))
        self._frame_timer.start()

    def _advance(self) -> None:
        self._index = (self._index + 1) % len(SPINNER_FRAMES)
        self._label.setText(busy_text(self._base, SPINNER_FRAMES[self._index]))
