# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Derived defaults for the setup wizard (names, passwords, suggestions).

Derived names are sanitized so they always satisfy the client's canonical
bucket/group grammars instead of surfacing a validation error for an ordinary
folder name (``My Documents``, ``Caffè``…).
"""

from __future__ import annotations

import os
import re
import secrets
import unicodedata

from hsync_common.path_validation import is_valid_bucket_name
from PySide6.QtCore import QStandardPaths

__all__ = [
    "default_share_name",
    "generate_group_name",
    "generate_password",
    "suggested_folders",
]

# Unambiguous alphabet for the generated shared password: no 0/O, 1/l/I.
_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_PASSWORD_LENGTH = 24

_MAX_NAME = 63  # matches MAX_BUCKET_NAME_LENGTH


def _slug(text: str) -> str:
    """Fold *text* into ``[a-z0-9]`` words separated by single hyphens."""
    base = os.path.basename(text.rstrip("/\\"))
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-_").lower()
    return base[:_MAX_NAME].strip("-_")


def default_share_name(folder: str) -> str:
    """Derive a valid share name from a folder path (random fallback)."""
    slug = _slug(folder)
    if slug and is_valid_bucket_name(slug):
        return slug
    return f"hsync-{secrets.token_hex(3)}"


def generate_group_name(folder: str) -> str:
    """Derive a group name from a folder path, suffixed for uniqueness."""
    base = _slug(folder) or "hsync"
    suffix = secrets.token_hex(2)
    name = f"{base}-{suffix}"[:_MAX_NAME].strip("-_")
    return name or f"hsync-{suffix}"


def generate_password() -> str:
    """A readable, unguessable shared password (p2p group key)."""
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def suggested_folders() -> list[tuple[str, str | None]]:
    """Quick folder suggestions as ``(label-key, path | None)`` pairs.

    Documents/Pictures come from the desktop's localized user directories
    (XDG user-dirs and their Windows/macOS equivalents), so the suggested path
    exists even on non-English systems; ``None`` marks an unconfigured location.
    """
    home = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
    if not home:
        home = os.path.expanduser("~")
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    return [
        ("wizard.folder.suggest_documents", documents or None),
        ("wizard.folder.suggest_pictures", pictures or None),
        ("wizard.folder.suggest_home", os.path.join(home, "HSYNC")),
    ]
