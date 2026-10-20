# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Filtering rules for the file panel.

The panel must list exactly what the engine synchronises, so the local scan,
the consistency pass and the status-bar size share one predicate based on the
engine's :class:`~hsync_common.ignore.IgnoreMatcher`.

Visibility of dot-prefixed names is a separate, purely visual concern driven by
the "show hidden files" toggle; it never changes what is scanned, counted or
synchronised.
"""

from __future__ import annotations

import os

from hsync_common.constants import HSYNCIGNORE_FILENAME, HSYNCKEEP_FILENAME
from hsync_common.ignore import IgnoreMatcher
from hsync_common.path_validation import basename


def is_synced_entry(matcher: IgnoreMatcher, path: str, *, is_dir: bool) -> bool:
    """Return True when the engine would synchronise *path*.

    Mirrors the client's own scan: ignored/internal names and transfer
    artifacts are excluded by :meth:`IgnoreMatcher.matches`, while the
    ``.hsynckeep`` sentinel is synchronised by the engine but stays internal to
    the UI (the client also excludes it from the folder-size totals).
    """
    if basename(path) == HSYNCKEEP_FILENAME:
        return False
    return not matcher.matches(path, is_dir=is_dir)


def has_dot_segment(rel_path: str) -> bool:
    """Return True when any path segment of *rel_path* starts with a dot."""
    return any(part.startswith(".") for part in rel_path.rstrip("/").split("/"))


def ignore_file_stamp(directory: str) -> tuple[int, int] | None:
    """Return ``(mtime_ns, size)`` of the bucket's ``.hsyncignore``, or None.

    Used to reload the matcher only when the ignore file actually changed.
    """
    try:
        st = os.stat(os.path.join(directory, HSYNCIGNORE_FILENAME))
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)
