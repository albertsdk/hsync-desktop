# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Localized text for a server-probe reason code.

The probe layer reports machine codes (``hsync_desktop/engine/probes.py``); this
module turns them into the sentence the user reads, so the setup wizard and the
Settings dialog phrase the same server answer identically.
"""

from __future__ import annotations

from hsync_desktop.i18n import tr

__all__ = ["probe_reason_text"]

_REASON_KEYS = {
    "unauthorized": "wizard.probe.401",
    "bad_share": "wizard.probe.400",
    "server_error": "wizard.probe.5xx",
    "share_missing": "wizard.probe.404_team",
}


def probe_reason_text(reason: str) -> str:
    """The localized sentence for *reason* (unreachable when the code is unknown)."""
    return tr(_REASON_KEYS.get(reason, "wizard.probe.unreachable"))
