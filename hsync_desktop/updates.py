# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Release update check for HSYNC Desktop.

The GUI only *discovers* whether a newer release exists: it never downloads or
executes an artifact. Two reasons:

- every distribution channel already has a safe upgrade path — Snap refreshes
  itself, the Windows installer upgrades in place, and ``.deb``/``.rpm`` belong
  to the system package manager;
- the release assets are not signed, so executing a downloaded file would be
  the only code path in the app that runs code with no shared trust anchor (see
  ADR-0048).

Consequently the check is opt-in, the only URL consulted is the project's own
``releases/latest`` redirect (pinned as :data:`docs_links.LATEST_RELEASE` and
allowlisted by :func:`docs_links.is_allowed_docs_url`), it uses no API token and
no credentials, and every failure is silent so an offline machine never sees a
warning.

The redirect is used instead of the GitHub API on purpose: it resolves the
newest tag without the unauthenticated rate limit (60 requests/hour per IP),
the same technique ``install.sh`` already relies on.
"""

from __future__ import annotations

import time
from http.client import HTTPException
from urllib.request import Request, urlopen

from PySide6.QtCore import QSettings

from hsync_desktop.config import DEFAULT_UPDATE_CHECK, SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.docs_links import LATEST_RELEASE, is_allowed_docs_url

__all__ = [
    "CHECK_INTERVAL_SECONDS",
    "TIMEOUT_SECONDS",
    "cached_latest_version",
    "check_now",
    "dismissed_version",
    "fetch_latest_version",
    "is_dismissed",
    "is_enabled",
    "is_newer",
    "last_check_epoch",
    "parse_version",
    "record_check",
    "set_dismissed_version",
    "set_enabled",
    "should_check",
]

#: Request budget: the check must never delay the UI.
TIMEOUT_SECONDS = 5.0
#: At most one request per day, per installation.
CHECK_INTERVAL_SECONDS = 24 * 60 * 60

_KEY_ENABLED = "updates/check_enabled"
_KEY_LAST_CHECK = "updates/last_check"
_KEY_LATEST = "updates/latest_version"
_KEY_DISMISSED = "updates/dismissed_version"

_RELEASES_TAG_MARKER = "/releases/tag/"


def parse_version(text: str) -> tuple[int, ...] | None:
    """Parse ``v1.2.3`` (or ``1.2.3-rc1``) into a comparable tuple, or None.

    Build metadata and pre-release suffixes are dropped: the check only answers
    "is there a newer release than mine?", so ``v1.0.12-rc1`` compares as
    ``1.0.12``. Anything that is not a dotted integer sequence is rejected
    instead of guessed.
    """
    base = text.strip().lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    parts = base.split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def is_newer(current: str, latest: str) -> bool:
    """True when *latest* is a strictly newer release than *current*.

    Unparseable input is never reported as an update: a malformed tag must not
    produce a "new version available" dialog.
    """
    current_parts = parse_version(current)
    latest_parts = parse_version(latest)
    if current_parts is None or latest_parts is None:
        return False
    width = max(len(current_parts), len(latest_parts))
    current_padded = current_parts + (0,) * (width - len(current_parts))
    latest_padded = latest_parts + (0,) * (width - len(latest_parts))
    return latest_padded > current_padded


def _tag_from_final_url(url: str) -> str | None:
    """Return the release tag from a ``…/releases/tag/<tag>`` URL, or None."""
    index = url.find(_RELEASES_TAG_MARKER)
    if index < 0:
        return None
    tag = url[index + len(_RELEASES_TAG_MARKER) :].split("/", 1)[0]
    tag = tag.split("?", 1)[0].split("#", 1)[0]
    return tag or None


def fetch_latest_version(timeout: float = TIMEOUT_SECONDS) -> str | None:
    """Return the newest published version (``1.2.3``), or None.

    Blocking: callers must run it off the UI thread (``engine/async_probe.py``).
    Returns None on any failure — offline, timeout, proxy error, no release, or
    a redirect that does not end on a release tag page — so the caller can stay
    silent instead of reporting a spurious error.
    """
    if not is_allowed_docs_url(LATEST_RELEASE):  # invariant: pinned target
        return None
    try:
        request = Request(LATEST_RELEASE, method="HEAD")
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - pinned https URL
            final_url = response.geturl()
    except (OSError, ValueError, HTTPException):
        return None
    tag = _tag_from_final_url(final_url)
    if tag is None:
        return None
    parsed = parse_version(tag)
    if parsed is None:
        return None
    return ".".join(str(part) for part in parsed)


# ─── Persisted state ────────────────────────────────────────────────────────


def _settings() -> QSettings:
    """Return the QSettings used for the update state (patchable in tests)."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def is_enabled() -> bool:
    """True when the operator opted into the automatic startup check."""
    return bool(_settings().value(_KEY_ENABLED, DEFAULT_UPDATE_CHECK, bool))


def set_enabled(enabled: bool) -> None:
    """Persist the opt-in flag for the automatic startup check."""
    settings = _settings()
    settings.setValue(_KEY_ENABLED, bool(enabled))
    settings.sync()


def last_check_epoch() -> int | None:
    """Return when the last check completed (Unix time), or None."""
    raw = _settings().value(_KEY_LAST_CHECK, "")
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value or None


def cached_latest_version() -> str | None:
    """Return the version discovered by the last successful check, or None."""
    raw = _settings().value(_KEY_LATEST, "")
    version = str(raw).strip()
    return version or None


def record_check(latest: str | None, now: float | None = None) -> None:
    """Store the moment of the check and, when known, the version it found.

    The timestamp is recorded even when the request failed, so an offline
    machine retries tomorrow instead of on every launch.
    """
    settings = _settings()
    timestamp = int(time.time() if now is None else now)
    settings.setValue(_KEY_LAST_CHECK, timestamp)
    settings.setValue(_KEY_LATEST, latest or "")
    settings.sync()


def should_check(now: float | None = None) -> bool:
    """True when the opt-in check is due.

    The interval also guards against a clock that jumped far into the past: in
    that case the check runs instead of waiting for the timestamp to catch up.
    """
    if not is_enabled():
        return False
    last = last_check_epoch()
    if last is None:
        return True
    elapsed = int(time.time() if now is None else now) - last
    return elapsed >= CHECK_INTERVAL_SECONDS or elapsed < -CHECK_INTERVAL_SECONDS


def dismissed_version() -> str | None:
    """Return the release the operator asked not to be reminded about."""
    raw = _settings().value(_KEY_DISMISSED, "")
    version = str(raw).strip()
    return version or None


def set_dismissed_version(version: str) -> None:
    """Remember (or clear, with an empty string) a dismissed release."""
    settings = _settings()
    settings.setValue(_KEY_DISMISSED, version)
    settings.sync()


def is_dismissed(version: str) -> bool:
    """True when *version* is the release the operator dismissed."""
    return bool(version) and dismissed_version() == version


def check_now(timeout: float = TIMEOUT_SECONDS, now: float | None = None) -> str | None:
    """Look the newest release up, record the attempt, and return its version."""
    latest = fetch_latest_version(timeout)
    record_check(latest, now)
    return latest
