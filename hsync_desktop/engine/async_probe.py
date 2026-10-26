# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Async wrapper that runs a blocking probe off the UI thread.

Mirrors ``file_panel/workers.py::DirectoryScanWorker`` (a ``QObject`` with a
``@Slot() run()`` moved onto a ``QThread``) and adds a generation counter so a
result from an abandoned request is never delivered.

Consumers: the setup wizard connection page, the Settings "Test Connection"
actions, the trusted-keys "read from server" action and the MainWindow trust
pre-flight. Every blocking probe (``engine/probes.py`` HTTP calls and the
``engine/cli.py`` fingerprint subprocesses) must run here: on the UI thread it
freezes the window and the desktop environment reports the app as unresponsive.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import QObject, QThread, Signal, Slot

__all__ = ["AsyncProbe", "ProbeOutcome"]

# Probes still in flight, keyed by their thread. Module-level so that a cancelled
# probe whose owner (a dialog or the main window) is destroyed keeps its thread
# and worker referenced until the blocking call returns: destroying a running
# QThread, or a QObject that lives in another thread, aborts the process.
_PENDING: dict[QThread, _Worker] = {}


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
        self.cancelled = False
        self.generation = 0

    def cancel(self) -> None:
        self.cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            outcome = self._job()
        except Exception:  # pragma: no cover - probe jobs must never crash the UI
            outcome = ProbeOutcome(False, reason="error")
        if not self.cancelled:
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
        thread = QThread()
        worker = _Worker(job)
        worker.generation = self._generation
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda retired=thread: _PENDING.pop(retired, None))
        self._thread = thread
        self._worker = worker
        _PENDING[thread] = worker
        thread.start()

    def cancel(self) -> None:
        self._generation += 1
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
        self._thread = None
        self._worker = None

    @Slot(object)
    def _on_worker_finished(self, result: Any) -> None:
        worker = cast(_Worker | None, self.sender())
        if worker is not None and worker.generation == self._generation:
            self.done.emit(result)
