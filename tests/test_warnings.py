# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the remediation text attached to actionable engine warnings."""

from __future__ import annotations

import pytest

from hsync_desktop.i18n import set_language, tr
from hsync_desktop.warnings import remedy_text


class TestRemedyText:
    """``remedy_text`` maps a warning's cause to localized, concrete advice."""

    @pytest.mark.parametrize(
        ("reason", "key"),
        [
            ("inotify_watches", "notif.remedy_inotify_watches"),
            ("inotify_instances", "notif.remedy_inotify_instances"),
            ("fd_exhaustion", "notif.remedy_fd_exhaustion"),
        ],
    )
    def test_each_known_watcher_cause_has_a_remedy(self, reason, key):
        assert remedy_text("watcher", {"reason": reason}) == tr(key)

    def test_the_numbers_are_appended_when_measured(self):
        text = remedy_text(
            "watcher",
            {"reason": "inotify_watches", "needed": 12000, "limit": 8192},
        )

        assert text == (
            f"{tr('notif.remedy_inotify_watches')} "
            f"{tr('notif.remedy_numbers').format(needed=12000, limit=8192)}"
        )

    def test_a_partial_measurement_is_never_quoted(self):
        """One number alone would read as a wrong figure: omit the sentence."""
        text = remedy_text("watcher", {"reason": "inotify_watches", "needed": 12000})

        assert text == tr("notif.remedy_inotify_watches")

    def test_an_unclassified_fallback_has_no_remedy(self):
        assert remedy_text("watcher", {"reason": "polling_fallback"}) == ""

    def test_a_transient_condition_has_no_remedy(self):
        assert remedy_text("watcher", {"reason": "transient"}) == ""

    def test_another_subsystem_has_no_remedy(self):
        assert remedy_text("rendezvous", {"reason": "inotify_watches"}) == ""

    def test_missing_details_are_tolerated(self):
        assert remedy_text("watcher", None) == ""

    def test_another_language_is_honoured(self):
        set_language("it")
        try:
            assert remedy_text("watcher", {"reason": "inotify_watches"}) == tr(
                "notif.remedy_inotify_watches"
            )
        finally:
            set_language("en")
