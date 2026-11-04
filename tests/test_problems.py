# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the window's registry of active problems."""

from __future__ import annotations

import pytest

from hsync_desktop.problems import FAILURE, WARNING, ProblemRegistry


@pytest.fixture
def registry(qtbot):
    """A registry with the application pytest-qt provides for the signals."""
    return ProblemRegistry()


class TestProblemRegistry:
    """The problems that hold, keyed so a repeat updates and a heal clears."""

    def test_starts_empty(self, registry):
        assert registry.problems == []
        assert registry.failure_count == 0
        assert registry.warning_count == 0
        assert registry.has_problems is False

    def test_a_failure_is_keyed_by_path(self, registry):
        registry.record_failure("a/b.bin", "boom")
        registry.record_failure("a/b.bin", "again")

        assert registry.failure_count == 1
        problem = registry.failures[0]
        assert problem.kind == FAILURE
        assert problem.key == "a/b.bin"
        assert problem.title == "a/b.bin"
        assert problem.detail == "again"

    def test_a_success_resolves_the_failure(self, registry):
        registry.record_failure("a/b.bin", "boom")

        registry.resolve_failure("a/b.bin")

        assert registry.problems == []

    def test_a_warning_is_keyed_by_source(self, registry):
        registry.record_warning("watcher", "degraded", "")
        registry.record_warning("watcher", "still degraded", "")

        assert registry.warning_count == 1
        problem = registry.warnings[0]
        assert problem.kind == WARNING
        assert problem.key == "watcher"
        assert problem.title == "still degraded"

    def test_clearing_a_warning_removes_it(self, registry):
        registry.record_warning("watcher", "degraded", "")

        registry.clear_warning("watcher")

        assert registry.problems == []

    def test_failures_are_listed_before_warnings(self, registry):
        registry.record_warning("watcher", "degraded", "")
        registry.record_failure("a.bin", "boom")

        assert [problem.kind for problem in registry.problems] == [FAILURE, WARNING]

    def test_clear_all_drops_everything(self, registry):
        registry.record_failure("a.bin", "boom")
        registry.record_warning("watcher", "degraded", "")

        registry.clear_all()

        assert registry.problems == []

    def test_an_empty_identity_is_ignored(self, registry):
        registry.record_failure("", "boom")
        registry.record_warning("", "degraded", "")

        assert registry.problems == []

    def test_changed_fires_once_per_real_change(self, registry):
        changes: list[int] = []
        registry.changed.connect(lambda: changes.append(1))

        registry.record_failure("a.bin", "boom")
        registry.record_failure("a.bin", "boom")  # unchanged: nothing to repaint
        registry.clear_failures()
        registry.clear_failures()  # already empty: nothing changed
        registry.resolve_failure("never/seen.bin")  # unknown: nothing changed

        assert len(changes) == 2

    def test_a_changed_detail_repaints(self, registry):
        changes: list[int] = []
        registry.changed.connect(lambda: changes.append(1))

        registry.record_failure("a.bin", "boom")
        registry.record_failure("a.bin", "a different reason")

        assert len(changes) == 2
        assert registry.failures[0].detail == "a different reason"
