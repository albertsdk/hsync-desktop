# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Apply a wizard draft to QSettings (plus the trust-store / autostart side effects).

Writes only the keys the wizard owns; every other setting is left untouched.
Trust pinning happens here because the pin lives in the client known-hosts store,
not in QSettings: ``apply_draft`` returns whether a requested pin succeeded so the
UI can block Finish and offer the "skip pinning" escape.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from hsync_common.constants import SERVER_DEFAULT_PORT
from hsync_common.endpoint import parse_host_port
from PySide6.QtCore import QSettings

from hsync_desktop import autostart
from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.crypto import encrypt_value
from hsync_desktop.engine import (
    add_rendezvous_trust,
    add_server_trust,
    fetch_rendezvous_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    normalize_rendezvous_server_endpoints,
    normalize_server_endpoint,
)
from hsync_desktop.wizard.model import WizardDraft, profile_for

__all__ = ["ApplyResult", "apply_draft"]

# Trust port when the endpoint carries none: mirrors the client/GUI pre-flight
# (``TrustMixin._ensure_trust`` uses 443 for https, the shared server
# default otherwise; the rendezvous-server pre-flight uses 443).
_HTTPS_PORT = 443


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """Outcome of :func:`apply_draft`.

    ``pin_error`` is ``""`` on success, ``"no_binary"`` when the client binary
    is missing, or ``"failed"`` when the trust-store write failed. When set, the
    caller must block Finish (or re-apply with ``pin=False`` after the explicit
    skip).
    """

    pin_error: str = ""


def _server_host_port(url: str) -> tuple[str, int] | None:
    parts = urlsplit(url)
    if not parts.hostname:
        return None
    port = parts.port or (_HTTPS_PORT if parts.scheme == "https" else SERVER_DEFAULT_PORT)
    return parts.hostname, port


def _rendezvous_server_host_port(rendezvous_server: str) -> tuple[str, int] | None:
    try:
        endpoint = parse_host_port(rendezvous_server)
    except ValueError:
        return None
    return endpoint.host, endpoint.port or _HTTPS_PORT


def _pin_endpoint(
    binary: str,
    target: tuple[str, int] | None,
    fingerprint: str,
    *,
    fetch: Callable[[str, str, int | None], str | None],
    add: Callable[[str, str, str, int | None], bool],
) -> str:
    """Pin one endpoint, reading its fingerprint first when none was supplied.

    Returns ``""`` on success and ``"failed"`` otherwise; the wizard maps that to
    its per-endpoint status label. Single implementation for the server and
    rendezvous-server pins, which differ only in how the endpoint is resolved and
    which ``hsync trust`` subcommand is used.
    """
    if target is None:
        return "failed"
    host, port = target
    fingerprint = fingerprint or fetch(binary, host, port) or ""
    if not fingerprint:
        return "failed"
    return "" if add(binary, host, fingerprint, port) else "failed"


def _pin_server(binary: str, url: str, fingerprint: str) -> str:
    return _pin_endpoint(
        binary,
        _server_host_port(url),
        fingerprint,
        fetch=fetch_server_fingerprint,
        add=add_server_trust,
    )


def _pin_rendezvous_server(binary: str, rendezvous_server: str, fingerprint: str) -> str:
    return _pin_endpoint(
        binary,
        _rendezvous_server_host_port(rendezvous_server),
        fingerprint,
        fetch=fetch_rendezvous_fingerprint,
        add=add_rendezvous_trust,
    )


def _pin_requested(draft: WizardDraft, *, server_mode: bool) -> list[tuple[str, str, str]]:
    """Return ``(kind, endpoint, fingerprint)`` for each requested pin."""
    requests: list[tuple[str, str, str]] = []
    if server_mode and draft.server_pin and draft.server_url.strip():
        requests.append(("server", draft.server_url.strip(), draft.server_fingerprint))
    if draft.rendezvous_server_pin and draft.rendezvous_server.strip():
        requests.append(
            (
                "rendezvous_server",
                draft.rendezvous_server.strip(),
                draft.rendezvous_server_fingerprint,
            )
        )
    return requests


def apply_draft(
    settings: QSettings | None,
    draft: WizardDraft,
    *,
    pin: bool = True,
) -> ApplyResult:
    """Persist the draft; pin the confirmed certificates unless *pin* is False."""
    s = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
    profile = profile_for(draft.mode) if draft.mode else None

    s.setValue("path/local", draft.local_path.strip())
    s.setValue("sync/bucket", draft.bucket.strip())
    s.setValue("sync/direction", draft.direction)
    s.setValue("sync/deletion_policy", draft.deletion_policy)
    s.setValue("sync/continuous", draft.continuous)
    s.setValue("sync/auto_sync", draft.auto_sync)

    server_mode = profile is not None and not profile.p2p_enabled
    if server_mode:
        s.setValue("p2p/enabled", False)
        # Clear a stale discovery servers so it cannot leak HSYNC_RENDEZVOUS_SERVER_ENDPOINTS into a server run.
        s.setValue("p2p/rendezvous_server_endpoints", "")
        s.setValue("connection/server_url", normalize_server_endpoint(draft.server_url) or "")
        s.setValue("connection/api_key", encrypt_value(draft.api_key) if draft.api_key else "")
        if draft.accept_server_cert:
            s.setValue("connection/server_trust", "ask")
    else:
        s.setValue("p2p/enabled", True)
        s.setValue("p2p/group", draft.p2p_group.strip())
        s.setValue("p2p/key", encrypt_value(draft.p2p_key) if draft.p2p_key else "")
        s.setValue("p2p/key_mode", "passphrase")
        s.setValue("p2p/rendezvous_server_trust", "ask")
        rendezvous_server = (
            normalize_rendezvous_server_endpoints(draft.rendezvous_server)
            if profile and profile.requires_rendezvous_server
            else ""
        )
        s.setValue("p2p/rendezvous_server_endpoints", rendezvous_server or "")

    s.setValue("appearance/start_at_login", draft.start_at_login)
    if autostart.is_supported():
        try:
            autostart.set_enabled(draft.start_at_login)
        except OSError:
            # The preference is stored; the OS entry is reconciled by Settings.
            pass

    if not pin:
        return ApplyResult()
    requests = _pin_requested(draft, server_mode=server_mode)
    if not requests:
        return ApplyResult()
    binary = find_hsync_binary()
    if not binary:
        return ApplyResult(pin_error="no_binary")
    for kind, endpoint, fingerprint in requests:
        error = (
            _pin_server(binary, endpoint, fingerprint)
            if kind == "server"
            else _pin_rendezvous_server(binary, endpoint, fingerprint)
        )
        if error:
            return ApplyResult(pin_error=error)
    return ApplyResult()
