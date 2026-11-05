# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The deletion-risk notice and the acknowledgement that silences it.

Only *Receive only* removes a local file at the initial sync: a bidirectional
run (server or p2p) uploads the files that exist only here, *Send only* never
deletes on this device, the keep policy cannot delete and Simulation Mode only
previews. The notice therefore guards that single posture, and every other
combination returns before asking.

An acknowledgement is scoped to the folder and the settings it was given for
(``_ACK_KEY`` stores the notice version, the reason and a digest of both), so
another folder, a different sync direction, deletion policy or p2p posture asks
again, and a reworded notice bumps ``DELETION_RISK_NOTICE_VERSION``. Silencing
the notice never disables protection: a run still stops at the plan it computed
before applying a deletion, and the mass-deletion guard keeps pausing the cycles
that would remove too many files.
"""

from __future__ import annotations

import hashlib
import os

from hsync_common.listing import folder_has_user_content as _folder_has_user_content
from PySide6.QtCore import QSettings

from hsync_desktop.config import (
    DEFAULT_DELETION_POLICY,
    DEFAULT_P2P_ENABLED,
    DEFAULT_SYNC_DIRECTION,
)

# Bumped when the wording changes, so an acknowledgement never covers a text the
# user did not read.
DELETION_RISK_NOTICE_VERSION = 1
_ACK_KEY = "ui/deletion_risk_ack"
REASON_DOWNLOAD_ONLY = "download-only"


def folder_has_user_content(local_path: str) -> bool:
    """True when the folder holds user data a deletion could remove.

    Delegates to the shared rule
    (``hsync_common.listing.folder_has_user_content``), so the window and the
    client's deletion guard cannot drift on what "the folder is not empty" means.
    """
    return _folder_has_user_content(local_path)


def acknowledgement(settings: QSettings, local_path: str, reason: str) -> str:
    """The value that acknowledges the notice for this folder and posture.

    The digest covers the folder and every setting that decides which files a
    run may remove, so an acknowledgement given for one share never covers
    another one, and changing the posture asks again.
    """
    posture = "|".join(
        (
            os.path.normcase(os.path.abspath(local_path)),
            str(settings.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)),
            str(settings.value("p2p/prefer_master", False, bool)),
            str(settings.value("sync/direction", DEFAULT_SYNC_DIRECTION, str)),
            str(settings.value("sync/deletion_policy", DEFAULT_DELETION_POLICY, str)),
        )
    )
    digest = hashlib.sha256(posture.encode("utf-8")).hexdigest()[:16]
    return f"{DELETION_RISK_NOTICE_VERSION}|{reason}|{digest}"


def is_acknowledged(settings: QSettings, local_path: str, reason: str) -> bool:
    """True when the notice was silenced for this folder and these settings."""
    return str(settings.value(_ACK_KEY, "", str)) == acknowledgement(settings, local_path, reason)


def acknowledge(settings: QSettings, local_path: str, reason: str) -> None:
    """Silence the notice for this folder and these settings only."""
    settings.setValue(_ACK_KEY, acknowledgement(settings, local_path, reason))


def forget_acknowledgement(settings: QSettings) -> None:
    """Make the notice appear again at the next start."""
    settings.remove(_ACK_KEY)
