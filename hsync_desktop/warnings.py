# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Actionable remediation text for the engine warnings that need one.

A warning that only states *what broke* leaves the user stuck: a degraded file
watcher keeps synchronising (in polling mode) but the cause — a host-wide kernel
limit — outlives the run and will hit again on the next start. The client
reports the cause as a stable ``reason`` plus, where it measured them, the
numbers (``needed``/``limit``); this module turns that into localized text.

Keys are the ``reason`` values emitted by the client
(``hsync_client.watcher.WatcherLimit`` members, plus ``"polling_fallback"`` for a
downgrade whose cause could not be classified): they are host facts, so only the
ones a user can act on carry a remedy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hsync_desktop.i18n import tr

_WATCHER_REMEDY_KEYS: dict[str, str] = {
    "inotify_watches": "notif.remedy_inotify_watches",
    "inotify_instances": "notif.remedy_inotify_instances",
    "fd_exhaustion": "notif.remedy_fd_exhaustion",
}


def remedy_text(source: str, details: Mapping[str, Any] | None) -> str:
    """Return the localized remedy for a warning, or ``""`` when there is none.

    ``details`` carries the ``reason`` (case class) and the optional measured
    numbers. The numbers are appended only when both are present: a remedy with
    a wrong or partial figure is worse than one without.
    """
    if source != "watcher":
        return ""
    reason = str((details or {}).get("reason") or "")
    key = _WATCHER_REMEDY_KEYS.get(reason)
    if key is None:
        return ""
    remedy = tr(key)
    needed = (details or {}).get("needed")
    limit = (details or {}).get("limit")
    if isinstance(needed, int) and isinstance(limit, int):
        remedy = f"{remedy} {tr('notif.remedy_numbers').format(needed=needed, limit=limit)}"
    return remedy
