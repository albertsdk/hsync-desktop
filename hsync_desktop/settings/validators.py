# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Input validation functions for settings.

Contains validators for paths, URLs, bucket names, and group names.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


def _validate_path(path: str, allow_absolute: bool = True) -> str | None:
    """Validate a file path to prevent path traversal attacks.

    Args:
        path: The path to validate.
        allow_absolute: If False, only relative paths are allowed.

    Returns:
        The validated path if safe, None otherwise.
    """
    if not path:
        return None

    # Remove null bytes
    path = path.replace("\x00", "")

    # Resolve the path and check it's within expected bounds
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return None

    # If absolute paths not allowed, ensure it's relative
    if not allow_absolute and resolved.is_absolute():
        return None

    return str(resolved)


def _validate_bucket(bucket: str) -> str | None:
    """Validate a bucket name.

    Bucket names should only contain alphanumeric characters,
    dashes, underscores, and periods.
    """
    if not bucket:
        return None

    # Remove null bytes
    bucket = bucket.replace("\x00", "")

    # Bucket name pattern: lowercase alphanumeric, dashes, underscores, periods
    # Must start and end with alphanumeric
    if re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", bucket):
        return bucket

    return None


def _validate_url(url: str) -> str | None:
    """Validate a URL for server connection."""
    if not url:
        return None

    # Remove null bytes
    url = url.replace("\x00", "")

    try:
        parsed = urlparse(url)
        # Must have scheme and netloc
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return url
    except Exception:
        pass

    return None


def _validate_group_name(group: str) -> str | None:
    """Validate a LAN group name.

    Group names should be alphanumeric with limited special characters.
    """
    if not group:
        return None

    # Remove null bytes
    group = group.replace("\x00", "")

    # Allow alphanumeric, dashes, underscores, and limited punctuation
    if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", group):
        return group

    return None
