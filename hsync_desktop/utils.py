# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Common utility functions for HSYNC Desktop.
"""

from __future__ import annotations


def format_bytes(n: int) -> str:
    """Format bytes into human-readable string.

    Args:
        n: Number of bytes

    Returns:
        Formatted string like "1.5 MB" or "500 B"
    """
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"
