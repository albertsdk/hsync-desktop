# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Field validation for the setup wizard.

Validators return an :class:`Issue` with a stable machine ``code``; the UI maps
it to a localized message (``wizard.error.<code>`` / ``wizard.warn.<code>``).
Kept Qt-free and pure so the rules can be unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from hsync_common.protocol.rdv_tokens import (
    WeakGroupPassphrase,
    passphrase_warning,
    validate_group_passphrase,
)

from hsync_desktop.engine import normalize_rendezvous_server_endpoints, normalize_server_endpoint
from hsync_desktop.settings.validators import (
    _validate_bucket,
    _validate_group_name,
    validate_sync_folder,
)
from hsync_desktop.wizard.model import WizardDraft, profile_for

__all__ = [
    "STEP_CONNECTION",
    "STEP_COUNT",
    "STEP_FOLDER",
    "STEP_PURPOSE",
    "STEP_REVIEW",
    "Issue",
    "first_error",
    "validate_connection",
    "validate_folder",
    "validate_purpose",
    "validate_step",
]

# Wizard steps, in order.
STEP_PURPOSE = 0
STEP_FOLDER = 1
STEP_CONNECTION = 2
STEP_REVIEW = 3
STEP_COUNT = 4


@dataclass(frozen=True, slots=True)
class Issue:
    """A validation issue tied to a field, addressed by a machine code."""

    level: str  # "error" | "warning"
    code: str
    field: str


def validate_purpose(draft: WizardDraft) -> list[Issue]:
    """Step 1: a mode must be chosen."""
    if draft.mode is None:
        return [Issue("error", "mode_required", "mode")]
    return []


def validate_folder(draft: WizardDraft, *, min_free_mb: int = 0) -> list[Issue]:
    """Step 2: the folder must exist, be writable and not be a system root."""
    check = validate_sync_folder(draft.local_path, min_free_mb=min_free_mb)
    if check.level == "ok":
        return []
    level = "error" if check.level == "error" else "warning"
    return [Issue(level, check.code, "local_path")]


def _check_share(draft: WizardDraft) -> Issue | None:
    name = draft.bucket.strip()
    if not name:
        return Issue("error", "share_required", "bucket")
    if _validate_bucket(name) is None:
        return Issue("error", "share_invalid", "bucket")
    return None


def _check_server(draft: WizardDraft) -> list[Issue]:
    issues: list[Issue] = []
    if not draft.server_url.strip():
        issues.append(Issue("error", "server_required", "server_url"))
    else:
        try:
            normalize_server_endpoint(draft.server_url)
        except ValueError:
            issues.append(Issue("error", "server_invalid", "server_url"))
    if not draft.api_key.strip():
        issues.append(Issue("error", "api_key_required", "api_key"))
    return issues


def _check_p2p(draft: WizardDraft, requires_rendezvous_server: bool) -> list[Issue]:
    issues: list[Issue] = []
    if _validate_group_name(draft.p2p_group.strip()) is None:
        issues.append(Issue("error", "group_invalid", "p2p_group"))
    password = draft.p2p_key.strip()
    if not password:
        issues.append(Issue("error", "password_required", "p2p_key"))
    else:
        try:
            validate_group_passphrase(password)
        except WeakGroupPassphrase as exc:
            issues.append(Issue("error", f"password_{exc.code}", "p2p_key"))
        else:
            if passphrase_warning(password) == "short":
                issues.append(Issue("warning", "password_short", "p2p_key"))
    if requires_rendezvous_server:
        rendezvous_server = draft.rendezvous_server.strip()
        if not rendezvous_server:
            issues.append(Issue("error", "rendezvous_server_required", "rendezvous_server"))
        else:
            try:
                normalize_rendezvous_server_endpoints(rendezvous_server)
            except ValueError:
                issues.append(Issue("error", "rendezvous_server_invalid", "rendezvous_server"))
    return issues


def validate_connection(draft: WizardDraft) -> list[Issue]:
    """Step 3: validate the mode-specific connection fields."""
    if draft.mode is None:
        return []
    profile = profile_for(draft.mode)
    if profile.p2p_enabled:
        issues = _check_p2p(draft, profile.requires_rendezvous_server)
    else:
        issues = _check_server(draft)
    share = _check_share(draft)
    if share is not None:
        issues.append(share)
    return issues


def validate_step(draft: WizardDraft, step: int, *, min_free_mb: int = 0) -> list[Issue]:
    """Validate all fields owned by *step* (review owns none)."""
    if step == STEP_PURPOSE:
        return validate_purpose(draft)
    if step == STEP_FOLDER:
        return validate_folder(draft, min_free_mb=min_free_mb)
    if step == STEP_CONNECTION:
        return validate_connection(draft)
    return []


def first_error(draft: WizardDraft, step: int, *, min_free_mb: int = 0) -> Issue | None:
    """Return the first blocking issue for *step*, if any."""
    for issue in validate_step(draft, step, min_free_mb=min_free_mb):
        if issue.level == "error":
            return issue
    return None
