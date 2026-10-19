# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Input validation functions for settings.

Contains validators for paths, URLs, bucket names, and group names.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from hsync_common.path_validation import is_valid_bucket_name, safe_resolve_path

# POSIX system directories that must never be the sync root; a broad warning is
# raised for them (and for the user's home) so the wizard can require an explicit
# confirmation before syncing a whole system tree.
_SYSTEM_DIRS = frozenset(
    {
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/lib",
        "/lib64",
        "/opt",
        "/proc",
        "/root",
        "/run",
        "/sbin",
        "/srv",
        "/sys",
        "/usr",
        "/var",
    }
)


@dataclass(frozen=True, slots=True)
class FolderCheck:
    """Outcome of :func:`validate_sync_folder`.

    ``level`` is ``"ok"``, ``"warning"`` or ``"error"``; ``code`` is a stable
    machine code the caller maps to a localized message. ``free_mb`` is the free
    space of the containing filesystem in MB (``None`` when it could not be
    read); ``free_bytes`` is the same value in bytes for human-readable display.
    """

    level: str
    code: str
    free_mb: int | None = None
    free_bytes: int | None = None


def validate_sync_folder(path: str, *, min_free_mb: int = 0) -> FolderCheck:
    """Validate a candidate sync folder.

    Mirrors the checks the setup wizard performs: existence, type, permissions
    and the filesystem-root hard block are errors; the user's home and POSIX
    system directories are warnings (a whole-tree sync needs explicit consent);
    low free space is a warning when ``min_free_mb`` is configured.
    """
    raw = (path or "").strip()
    if not raw:
        return FolderCheck("error", "empty")
    try:
        resolved = Path(raw).expanduser().resolve()
    except (OSError, ValueError):
        return FolderCheck("error", "invalid")
    if not resolved.exists():
        return FolderCheck("error", "missing")
    if not resolved.is_dir():
        return FolderCheck("error", "not_dir")
    # The filesystem root is never syncable (checked before the access probe:
    # a non-root user cannot write "/" but the reason is the root, not perms).
    if resolved.parent == resolved:
        return FolderCheck("error", "root")
    if not os.access(resolved, os.R_OK | os.W_OK):
        return FolderCheck("error", "no_access")

    try:
        free_bytes: int | None = shutil.disk_usage(resolved).free
    except OSError:
        free_bytes = None
    free_mb = free_bytes // (1024 * 1024) if free_bytes is not None else None

    if resolved == Path.home():
        return FolderCheck("warning", "home", free_mb, free_bytes)
    if str(resolved) in _SYSTEM_DIRS:
        return FolderCheck("warning", "system", free_mb, free_bytes)
    if min_free_mb and free_mb is not None and free_mb < min_free_mb:
        return FolderCheck("warning", "low_space", free_mb, free_bytes)
    return FolderCheck("ok", "ok", free_mb, free_bytes)


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
