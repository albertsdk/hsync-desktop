# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Async wrapper that runs a blocking probe off the UI thread.

Mirrors ``file_panel/workers.py::DirectoryScanWorker`` (a ``QObject`` with a
``@Slot() run()`` moved onto a ``QThread``) and adds a generation counter so a
result from an abandoned request is never delivered.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

__all__ = ["AsyncProbe", "ProbeOutcome"]


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    """The result of a probe job, ready for the UI to render."""

    ok: bool
    status: int | None = None
    fingerprint: str = ""
    reason: str = ""


class _Worker(QObject):
    finished = Signal(object)

    def __init__(self, job: Callable[[], ProbeOutcome]) -> None:
        super().__init__()
        self._job = job
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            outcome = self._job()
        except Exception:  # pragma: no cover - probe jobs must never crash the UI
            outcome = ProbeOutcome(False, reason="error")
        if not self._cancelled:
            self.finished.emit(outcome)


class AsyncProbe(QObject):
    """Runs one probe at a time; a new ``start`` (or ``cancel``) drops the old result."""

    done = Signal(object)  # ProbeOutcome

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _Worker | None = None
        self._generation = 0

    def start(self, job: Callable[[], ProbeOutcome]) -> None:
        self.cancel()
        self._generation += 1
        generation = self._generation
        thread = QThread()
        worker = _Worker(job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result, g=generation: self._deliver(g, result))
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def cancel(self) -> None:
        self._generation += 1
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
        self._thread = None
        self._worker = None

    def _deliver(self, generation: int, result: Any) -> None:
        if generation == self._generation:
            self.done.emit(result)
