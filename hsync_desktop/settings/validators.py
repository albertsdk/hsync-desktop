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

from hsync_common.path_validation import is_valid_bucket_name, safe_resolve_path


def _validate_path(path: str, allow_absolute: bool = True) -> str | None:
    """Validate a file path to prevent path traversal attacks.

    Args:
        path: The path to validate.
        allow_absolute: If False, only relative paths are allowed.

    Returns:
        The validated path if safe, None otherwise.
    """
    return safe_resolve_path(path, allow_absolute=allow_absolute)


def _validate_bucket(bucket: str) -> str | None:
    """Validate a bucket name against the canonical HSYNC pattern.

    Bucket names must be alphanumeric, may contain hyphens and underscores in
    the middle, and cannot start or end with a hyphen or underscore.
    """
    if not bucket:
        return None

    # Remove null bytes
    bucket = bucket.replace("\x00", "")

    if is_valid_bucket_name(bucket):
        return bucket

    return None


def _validate_group_name(group: str) -> str | None:
    """Validate a p2p group name.

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
