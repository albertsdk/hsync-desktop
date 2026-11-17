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
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from hsync_common.disk import BYTES_PER_MB, check_free_space
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

# The macOS counterpart: the canonical system trees.
_MACOS_SYSTEM_DIRS = ("/System", "/Library", "/Applications")

# Windows roots come from the environment so a system on a non-``C:`` drive is
# handled without hard-coding a letter.
_WINDOWS_SYSTEM_ENV = (
    "SystemRoot",
    "windir",
    "ProgramFiles",
    "ProgramFiles(x86)",
    "ProgramData",
)


def protected_system_roots(
    *, platform: str | None = None, environ: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Return the system trees that need a warning before syncing them.

    Linux uses the fixed POSIX list (exact match), macOS the three system trees,
    Windows the roots named by the environment. ``platform``/``environ`` are
    injectable so the Linux CI can exercise every branch.
    """
    plat = sys.platform if platform is None else platform
    if plat == "win32":
        env = os.environ if environ is None else environ
        roots = (env.get(name, "") for name in _WINDOWS_SYSTEM_ENV)
        return tuple(dict.fromkeys(root for root in roots if root))
    if plat == "darwin":
        return _MACOS_SYSTEM_DIRS
    return tuple(sorted(_SYSTEM_DIRS))


def _is_protected_system_dir(
    path: str, *, platform: str | None = None, environ: Mapping[str, str] | None = None
) -> bool:
    """Whether *path* is a platform system tree or a directory inside one.

    Separators are folded to ``/`` so a Windows path matches whichever form the
    OS reports. Windows and macOS match a root **or a directory inside it**,
    case-insensitively (macOS defaults to a case-insensitive filesystem); Linux
    matches a root exactly, so a data folder such as ``/var/www`` is not flagged.
    """
    plat = sys.platform if platform is None else platform
    nested = plat in ("win32", "darwin")
    target = path.replace("\\", "/").rstrip("/")
    if nested:
        target = target.casefold()
    for root in protected_system_roots(platform=plat, environ=environ):
        candidate = root.replace("\\", "/").rstrip("/")
        if not candidate:
            continue
        if nested:
            candidate = candidate.casefold()
        if target == candidate or (nested and target.startswith(candidate + "/")):
            return True
    return False


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
    if _is_protected_system_dir(str(resolved)):
        return FolderCheck("warning", "system", free_mb, free_bytes)
    # Same free-space rule as the client/server (`hsync_common.disk`); the GUI
    # setting is edited in whole MB.
    space = check_free_space(str(resolved), reserve_bytes=min_free_mb * BYTES_PER_MB)
    if not space.ok:
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
