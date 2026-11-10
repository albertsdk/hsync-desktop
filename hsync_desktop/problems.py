# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The problems that currently hold, as the window reports them.

A notification is a moment; a problem is a state. A transfer that gave up, a
watcher degraded to polling, a share with no primary device are states: they
have an identity (so the user can tell *which* one) and a lifetime (so they
disappear when the condition heals). The window keeps them here and renders them
in the status bar, while the log stays the durable record of everything that
happened.

Keyed by identity, so a repeat updates the entry in place instead of stacking:
failures by bucket-relative path, warnings by the subsystem that reported them.

Consumers: ``main_window/ui.py`` (the status-bar badge and the notification
policy) and ``main_window/events.py`` (the engine events that record and resolve
them).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

__all__ = ["FAILURE", "WARNING", "Problem", "ProblemRegistry"]

#: A transfer that gave up: keyed by path, resolved when that path transfers.
FAILURE = "failure"
#: A non-fatal condition a subsystem reported: keyed by source, resolved when
#: that subsystem reports it cleared.
WARNING = "warning"


@dataclass(frozen=True)
class Problem:
    """One active problem: what it is, which one it is, and how to act on it."""

    kind: str
    key: str  # the identity: a bucket-relative path, or a warning source
    title: str  # the headline the badge lists (the path for a failure)
    detail: str
    help_url: str | None = None
    # warning: the client's stable sub-reason (e.g. rendezvous "unreachable" vs
    # "token_required"), so a consumer can localize a precise message.
    reason: str = ""


class ProblemRegistry(QObject):
    """The active problems; ``changed`` fires whenever the set changes."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._failures: dict[str, Problem] = {}
        self._warnings: dict[str, Problem] = {}

    # ── Failures ─────────────────────────────────────────────────────────

    def record_failure(self, path: str, detail: str) -> None:
        """Record a transfer that gave up; a repeat replaces its message.

        A permanently failing download is re-reported every cycle: an unchanged
        entry is a no-op, so the badge is not rebuilt for nothing.
        """
        if not path:
            return
        problem = Problem(FAILURE, path, path, detail)
        if self._failures.get(path) == problem:
            return
        self._failures[path] = problem
        self.changed.emit()

    def resolve_failure(self, path: str) -> None:
        """The path transferred: whatever failed on it no longer holds."""
        if self._failures.pop(path, None) is not None:
            self.changed.emit()

    def clear_failures(self) -> None:
        """Drop every failure (the cycle reported nothing left to transfer)."""
        if self._failures:
            self._failures.clear()
            self.changed.emit()

    # ── Warnings ─────────────────────────────────────────────────────────

    def record_warning(
        self, source: str, title: str, detail: str, help_url: str | None = None, reason: str = ""
    ) -> None:
        """Record a condition *source* reports; a repeat replaces the entry.

        An unchanged entry is a no-op, so a condition the client re-asserts on
        every cycle does not rebuild the badge for nothing.
        """
        if not source:
            return
        problem = Problem(WARNING, source, title, detail, help_url, reason)
        if self._warnings.get(source) == problem:
            return
        self._warnings[source] = problem
        self.changed.emit()

    def clear_warning(self, source: str) -> None:
        """The condition *source* reported no longer holds."""
        if self._warnings.pop(source, None) is not None:
            self.changed.emit()

    def clear_all(self) -> None:
        """Drop everything: the session the problems described is over."""
        if self._failures or self._warnings:
            self._failures.clear()
            self._warnings.clear()
            self.changed.emit()

    # ── Reads ────────────────────────────────────────────────────────────

    @property
    def failures(self) -> list[Problem]:
        """The failing transfers, in the order they were recorded."""
        return list(self._failures.values())

    @property
    def warnings(self) -> list[Problem]:
        """The active warnings, in the order they were recorded."""
        return list(self._warnings.values())

    @property
    def problems(self) -> list[Problem]:
        """Every active problem, failures first."""
        return self.failures + self.warnings

    @property
    def failure_count(self) -> int:
        return len(self._failures)

    @property
    def warning_count(self) -> int:
        return len(self._warnings)

    @property
    def has_problems(self) -> bool:
        return bool(self._failures or self._warnings)
