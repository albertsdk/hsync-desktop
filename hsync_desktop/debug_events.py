# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Temporary diagnostics for the file-panel event flow.

Enabled only when ``HSYNC_DESKTOP_DEBUG_EVENTS`` names a writable file: every
engine event the desktop receives and the resulting panel row / session counter
are appended as one JSON object per line. With the variable unset this module is
a no-op (one ``os.environ`` lookup at import). It changes no behaviour and is
meant to be removed once the file-panel progress investigation is closed.

Usage::

    HSYNC_DESKTOP_DEBUG_EVENTS=/tmp/hsync-desktop-events.jsonl ./hsync-desktop
"""

from __future__ import annotations

import json
import os
from typing import Any, TextIO

from hsync_common.time_utils import utc_now_iso

_PATH = os.environ.get("HSYNC_DESKTOP_DEBUG_EVENTS", "").strip()
_fh: TextIO | None = None


def enabled() -> bool:
    """True when a debug output path was configured."""
    return bool(_PATH)


def output_path() -> str:
    """The configured debug output path (empty when disabled)."""
    return _PATH


def log(kind: str, **fields: Any) -> None:
    """Append one JSONL diagnostic record; never raises."""
    global _fh
    if not _PATH:
        return
    try:
        if _fh is None:
            _fh = open(_PATH, "a", encoding="utf-8")
        payload = {"ts": utc_now_iso(), "kind": kind, **fields}
        _fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        _fh.flush()
    except (OSError, ValueError, TypeError):
        pass
