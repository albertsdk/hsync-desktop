# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the async probe runner (``engine/async_probe.py``).

The runner is what keeps a blocking probe (an HTTPS call or a client CLI
subprocess) from freezing the window: these tests pin the delivery, the
cancellation and the superseding behaviour the UI relies on.
"""

from __future__ import annotations

import time

from hsync_desktop.engine.async_probe import _PENDING, AsyncProbe, ProbeOutcome


def _probe_with_recorder() -> tuple[AsyncProbe, list]:
    probe = AsyncProbe()
    results: list = []
    probe.done.connect(results.append)
    return probe, results


def _slow(outcome: ProbeOutcome, delay: float = 0.2):
    """A job that blocks for *delay*, like a probe waiting on the network."""

    def job() -> ProbeOutcome:
        time.sleep(delay)
        return outcome

    return job


class TestAsyncProbe:
    def test_delivers_the_job_result(self, qtbot):
        probe, results = _probe_with_recorder()
        probe.start(lambda: ProbeOutcome(True, 200))
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
        assert results == [ProbeOutcome(True, 200)]

    def test_a_raising_job_becomes_an_error_outcome(self, qtbot):
        probe, results = _probe_with_recorder()

        def boom() -> ProbeOutcome:
            raise RuntimeError("probe crashed")

        probe.start(boom)
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
        assert results == [ProbeOutcome(False, reason="error")]

    def test_cancel_drops_a_pending_result(self, qtbot):
        probe, results = _probe_with_recorder()
        probe.start(_slow(ProbeOutcome(True)))
        probe.cancel()
        # The cancelled job keeps blocking in its thread: the thread and its
        # worker must stay referenced until it finishes (a running QThread, or a
        # QObject destroyed from another thread, aborts the process).
        assert _PENDING
        qtbot.waitUntil(lambda: not _PENDING, timeout=5000)
        qtbot.wait(50)
        assert results == []

    def test_a_new_start_supersedes_the_pending_probe(self, qtbot):
        probe, results = _probe_with_recorder()
        probe.start(_slow(ProbeOutcome(False)))
        probe.start(lambda: ProbeOutcome(True))
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
        qtbot.waitUntil(lambda: not _PENDING, timeout=5000)
        assert results == [ProbeOutcome(True)]
