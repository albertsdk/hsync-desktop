# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Semi-transparent loading overlay with a progress bar for the file panel."""

from __future__ import annotations

from hsync_common.format import format_bytes
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.busy import BUSY_DELAY_MS, BusyText
from hsync_desktop.file_panel.import_ops import CopyProgress, ImportPhase
from hsync_desktop.i18n import tr

# The scan bar shows its own figures; the import bar shows a percentage, because
# its counters are bytes and the human-readable pair lives in the detail line.
_SCAN_BAR_FORMAT = "%p% (%v / %m)"

# One label per import phase, so the text names what the worker is really doing.
_IMPORT_LABELS = {
    ImportPhase.SCAN: "loading.import_scan",
    ImportPhase.COPY: "loading.import_copy",
    ImportPhase.MOVE: "loading.import_move",
}


class LoadingOverlay(QWidget):
    """Semi-transparent overlay with progress indicator.

    One widget covers the table in both cases that make it busy: a folder scan
    (``show_loading``/``set_progress``, determinate, not cancellable) and a drag
    & drop import (``show_import``, cancellable, indeterminate while the current
    item is still being counted).
    """

    # Emitted when the user asks to stop the running import.
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None, *, delay_ms: int | None = None) -> None:
        super().__init__(parent)
        # A scan indicator waits before appearing (``BUSY_DELAY_MS`` by default):
        # most folders are scanned in a few milliseconds, and an overlay that
        # flashes over the table is worse than none at all. ``delay_ms`` lets a
        # test drive the behaviour without waiting for the real threshold.
        self._scan_delay_ms = delay_ms
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(True)

        # Semi-transparent background
        palette = self.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        bg_color.setAlpha(200)
        palette.setColor(palette.ColorRole.Window, bg_color)
        self.setPalette(palette)

        # Layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Container for centered content
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.setSpacing(10)

        # Loading label
        self._label = QLabel(tr("loading.files"))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._label.font()
        font.setPointSize(12)
        self._label.setFont(font)
        container_layout.addWidget(self._label)
        self._scan_busy = BusyText(self._label, delay_ms=delay_ms)
        self._scan_busy.set_text(tr("loading.files"))

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._progress.setMinimumWidth(250)
        self._progress.setMaximumWidth(350)
        self._progress.setTextVisible(True)
        self._progress.setFormat(_SCAN_BAR_FORMAT)
        container_layout.addWidget(self._progress)

        # Import counters, under the bar: they carry the figures a percentage
        # alone cannot show (how many files, how many bytes).
        self._detail = QLabel("")
        self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail.hide()
        container_layout.addWidget(self._detail)

        self._cancel_button = QPushButton(tr("btn.cancel"))
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        self._cancel_button.hide()
        container_layout.addWidget(self._cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(container)
        self.hide()

    def set_progress(self, current: int, total: int) -> None:
        """Update progress bar."""
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        # Update label with count; a progress update must not re-arm the delay, so
        # it goes through the busy text (which keeps the animation if running).
        self._scan_busy.set_text(f"{tr('loading.files')} ({current}/{total})")

    def show_loading(self) -> None:
        """Show the scan indicator after the busy delay (determinate, no cancel).

        The widget itself is revealed only once the delay elapses, so a folder
        that scans instantly never flashes an overlay over the table. The caller
        may re-issue this on every resize; the delay is armed only once.
        """
        self._cancel_button.hide()
        self._detail.hide()
        self._progress.setFormat(_SCAN_BAR_FORMAT)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._scan_busy.set_text(tr("loading.files"))
        if self._scan_busy.is_animating:
            # Already past the delay: keep it on screen (this is re-issued on
            # every resize).
            self._show_raised()
            return
        timer = self._reveal_timer()
        if timer.isActive():
            return
        timer.start(self._delay_ms())

    def _delay_ms(self) -> int:
        """The configured delay, falling back to the shared threshold."""
        return BUSY_DELAY_MS if self._scan_delay_ms is None else self._scan_delay_ms

    def _reveal_timer(self) -> QTimer:
        """The one-shot timer that reveals the overlay when the delay elapses."""
        timer = self.__dict__.get("_reveal_timer_obj")
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._reveal)
            self._reveal_timer_obj = timer
        return timer

    def _reveal(self) -> None:
        """Reveal the overlay with its spinner.

        The timer only fires while the scan still owns the overlay:
        ``hide_loading`` cancels it, so a scan that finished during the delay
        never shows anything.
        """
        self._show_raised()
        self._scan_busy.start(0)

    def show_import(self, progress: CopyProgress) -> None:
        """Show, or refresh, the import indicator for ``progress``.

        The bar is determinate only when the total is known — bytes first, then
        files — and stays indeterminate while the current item is being counted
        or after that count gave up: a percentage that cannot be kept would be a
        worse answer than an honest busy bar.
        """
        # An import is an explicit, cancellable action: it appears at once, so it
        # must also own the label without the scan's spinner. The label text goes
        # through ``BusyText`` (after stopping it), or ``stop`` would restore the
        # scan wording over the import one.
        self._scan_busy.stop()
        self._cancel_reveal()
        self._scan_busy.set_text(tr(_IMPORT_LABELS[progress.phase]))
        self._detail.setText(self._import_detail(progress))
        self._detail.show()
        self._cancel_button.show()
        self._progress.setFormat("%p%")
        if progress.bytes_total:
            self._progress.setRange(0, progress.bytes_total)
            self._progress.setValue(min(progress.bytes_done, progress.bytes_total))
        elif progress.files_total:
            self._progress.setRange(0, progress.files_total)
            self._progress.setValue(min(progress.files_done, progress.files_total))
        else:
            self._progress.setRange(0, 0)
        self._show_raised()

    def hide_loading(self) -> None:
        """Hide the overlay immediately and cancel a pending scan indicator."""
        self._scan_busy.stop()
        self._cancel_reveal()
        self.hide()

    def _cancel_reveal(self) -> None:
        """Cancel the pending reveal, if any (never rescheduled by ``start``)."""
        timer = self.__dict__.get("_reveal_timer_obj")
        if timer is not None:
            timer.stop()

    def reset_cancel(self) -> None:
        """Re-arm Cancel for a new import batch.

        A batch disables the button when it is clicked, so the next one has to
        arm it again: the render path must not, or a progress update arriving
        after the click would silently re-offer a cancel that is already asked
        for.
        """
        self._cancel_button.setEnabled(True)

    def _show_raised(self) -> None:
        """Show the overlay above the table it covers."""
        self.show()
        self.raise_()

    def _on_cancel_clicked(self) -> None:
        """Ask to stop the import (the file being written still finishes)."""
        self._cancel_button.setEnabled(False)
        self.cancel_requested.emit()

    @staticmethod
    def _import_detail(progress: CopyProgress) -> str:
        """The counters line: item position, then files and bytes written."""
        parts: list[str] = []
        if progress.items_total > 1:
            parts.append(
                tr("loading.import_items").format(
                    done=progress.items_done, total=progress.items_total
                )
            )
        if progress.files_total is None:
            parts.append(
                tr("loading.import_progress").format(
                    files=progress.files_done, size=format_bytes(progress.bytes_done)
                )
            )
            return " · ".join(parts)
        parts.append(
            tr("loading.import_progress_total").format(
                files=progress.files_done,
                total_files=progress.files_total,
                size=format_bytes(progress.bytes_done),
                total_size=format_bytes(progress.bytes_total or 0),
            )
        )
        return " · ".join(parts)
