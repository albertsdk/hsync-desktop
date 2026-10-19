# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Setup wizard model: modes, profiles, draft and inference.

No Qt widgets here: the mode/profile tables, the settings inference and the
draft persistence (QSettings + ``crypto``) are pure enough to unit-test without
a running application.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import cast

from PySide6.QtCore import QSettings

from hsync_desktop.config import (
    DEFAULT_P2P_BOOTNODE,
    DEFAULT_P2P_ENABLED,
    DEFAULT_SYNC_DIRECTION,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.crypto import decrypt_value, encrypt_value

__all__ = [
    "DRAFT_VERSION",
    "WizardDraft",
    "WizardMode",
    "WizardProfile",
    "clear_draft",
    "infer_mode_from_settings",
    "load_draft",
    "mark_auto_shown",
    "mark_completed",
    "profile_for",
    "save_draft",
    "should_auto_open",
]

# Bumped when the draft layout changes: a draft with another version is
# discarded instead of being partially restored.
DRAFT_VERSION = 2

_DRAFT_PREFIX = "wizard/draft"


class WizardMode(StrEnum):
    """The four use cases the wizard can configure."""

    BACKUP = "backup"
    LAN_SYNC = "lan_sync"
    REMOTE_SYNC = "remote_sync"
    TEAM_SHARE = "team_share"


@dataclass(frozen=True, slots=True)
class WizardProfile:
    """Derived defaults for a mode (see the plan's smart-default table)."""

    mode: WizardMode
    p2p_enabled: bool
    direction: str  # "bidirectional" | "upload-only" | "download-only"
    ignore_delete: bool
    start_at_login: bool
    requires_relay: bool
    server_trust: str | None  # None = mode has no server field


_PROFILES: dict[WizardMode, WizardProfile] = {
    WizardMode.BACKUP: WizardProfile(
        WizardMode.BACKUP,
        p2p_enabled=False,
        direction="upload-only",
        ignore_delete=True,
        start_at_login=True,
        requires_relay=False,
        server_trust="chain",
    ),
    WizardMode.LAN_SYNC: WizardProfile(
        WizardMode.LAN_SYNC,
        p2p_enabled=True,
        direction="bidirectional",
        ignore_delete=False,
        start_at_login=False,
        requires_relay=False,
        server_trust=None,
    ),
    WizardMode.REMOTE_SYNC: WizardProfile(
        WizardMode.REMOTE_SYNC,
        p2p_enabled=True,
        direction="bidirectional",
        ignore_delete=False,
        start_at_login=False,
        requires_relay=True,
        server_trust=None,
    ),
    WizardMode.TEAM_SHARE: WizardProfile(
        WizardMode.TEAM_SHARE,
        p2p_enabled=False,
        direction="bidirectional",
        ignore_delete=False,
        start_at_login=False,
        requires_relay=False,
        server_trust="chain",
    ),
}


def profile_for(mode: WizardMode) -> WizardProfile:
    """Return the derived defaults for *mode*."""
    return _PROFILES[mode]


@dataclass
class WizardDraft:
    """All editable wizard state (secrets in clear here, encrypted at rest)."""

    mode: WizardMode | None = None
    local_path: str = ""
    bucket: str = ""
    server_url: str = ""
    api_key: str = ""
    p2p_group: str = ""
    p2p_key: str = ""
    relay: str = ""
    direction: str = "bidirectional"
    ignore_delete: bool = False
    continuous: bool = True
    auto_sync: bool = True
    start_at_login: bool = False
    # Trust choices; fingerprints are captured by the probe and pinned on apply.
    accept_server_cert: bool = False
    server_fingerprint: str = ""
    server_pin: bool = False
    relay_fingerprint: str = ""
    relay_pin: bool = False
    # Last successful reachability check (ISO 8601 UTC); cleared on edit.
    server_verified: bool = False
    server_verified_at: str = ""
    relay_verified: bool = False
    relay_verified_at: str = ""


def _settings() -> QSettings:
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def infer_mode_from_settings(settings: QSettings | None = None) -> WizardMode | None:
    """Preselect a mode from the current configuration (re-run prefill)."""
    s = settings or _settings()
    if not str(s.value("path/local", "", str)).strip():
        return None
    p2p = bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool))
    direction = str(s.value("sync/direction", DEFAULT_SYNC_DIRECTION, str))
    if p2p:
        relay = str(s.value("p2p/bootnode", DEFAULT_P2P_BOOTNODE, str)).strip()
        return WizardMode.REMOTE_SYNC if relay else WizardMode.LAN_SYNC
    if direction == "upload-only":
        return WizardMode.BACKUP
    return WizardMode.TEAM_SHARE


def should_auto_open(settings: QSettings | None = None) -> bool:
    """True on the first run only: never auto-shown and no folder configured."""
    s = settings or _settings()
    if bool(s.value("wizard/auto_shown", False, bool)):
        return False
    return not str(s.value("path/local", "", str)).strip()


def _save_secret(s: QSettings, key: str, value: str) -> None:
    s.setValue(key, encrypt_value(value) if value else "")


def _load_secret(s: QSettings, key: str) -> str:
    raw = str(s.value(key, "", str))
    return decrypt_value(raw) if raw else ""


def save_draft(settings: QSettings | None, draft: WizardDraft, step: int) -> None:
    """Persist the draft and the last visited step."""
    s = settings or _settings()
    s.setValue("wizard/in_progress", True)
    s.setValue("wizard/version", DRAFT_VERSION)
    s.setValue("wizard/last_step", int(step))
    s.setValue("wizard/mode", draft.mode.value if draft.mode else "")
    for field in fields(WizardDraft):
        if field.name in ("api_key", "p2p_key"):
            continue
        value = getattr(draft, field.name)
        s.setValue(f"{_DRAFT_PREFIX}/{field.name}", value)
    _save_secret(s, f"{_DRAFT_PREFIX}/api_key", draft.api_key)
    _save_secret(s, f"{_DRAFT_PREFIX}/p2p_key", draft.p2p_key)


def load_draft(settings: QSettings | None = None) -> tuple[WizardDraft, int] | None:
    """Return the saved draft and step, or ``None`` when absent/stale."""
    s = settings or _settings()
    if not bool(s.value("wizard/in_progress", False, bool)):
        return None
    if int(cast(int, s.value("wizard/version", 0, int))) != DRAFT_VERSION:
        clear_draft(s)
        return None
    draft = WizardDraft()
    raw_mode = str(s.value("wizard/mode", "", str))
    try:
        draft.mode = WizardMode(raw_mode) if raw_mode else None
    except ValueError:
        draft.mode = None
    for field in fields(WizardDraft):
        if field.name == "mode":
            continue
        key = f"{_DRAFT_PREFIX}/{field.name}"
        if field.name in ("api_key", "p2p_key"):
            setattr(draft, field.name, _load_secret(s, key))
        elif field.type == "bool":
            setattr(draft, field.name, bool(s.value(key, False, bool)))
        else:
            setattr(draft, field.name, str(s.value(key, "", str)))
    step = int(cast(int, s.value("wizard/last_step", 0, int)))
    return draft, step


def mark_auto_shown(settings: QSettings | None = None) -> None:
    """Record that the wizard has been auto-opened once."""
    s = settings or _settings()
    s.setValue("wizard/auto_shown", True)


def clear_draft(settings: QSettings | None = None) -> None:
    """Clear all draft values and the in-progress flag."""
    s = settings or _settings()
    for field in fields(WizardDraft):
        s.remove(f"{_DRAFT_PREFIX}/{field.name}")
    s.setValue("wizard/in_progress", False)
    s.remove("wizard/last_step")
    s.remove("wizard/mode")


def mark_completed(settings: QSettings | None = None) -> None:
    """Mark the wizard as completed and drop the draft."""
    s = settings or _settings()
    s.setValue("wizard/completed", True)
    s.setValue("wizard/version", DRAFT_VERSION)
    clear_draft(s)
