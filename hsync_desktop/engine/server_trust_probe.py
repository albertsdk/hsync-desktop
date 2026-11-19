# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Secure TLS resolution for the authenticated bucket probe.

The Settings dialog and the setup wizard send the API key to ``/api/v1``
resources, so the connection must be CA-verified or pinned to the server's
certificate: an unverified context would leak the key to a man-in-the-middle.

``resolve_bucket_trust`` mirrors the client's ADR-0051 resolution using the
shared policy (:mod:`hsync_common.protocol.tls_trust`) and the client trust
store (``hsync trust server``). ``auto`` pins the first sighting (TOFU) with a
notice; ``ask``/``strict`` require an explicit pin and fail closed otherwise; a
changed fingerprint is always refused.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from hsync_common.protocol.pairing import parse_fingerprint
from hsync_common.protocol.tls_trust import (
    TrustAction,
    TrustPolicy,
    evaluate_tls_trust,
    resolve_auto_policy,
)

from hsync_desktop.engine.cli import add_server_trust, list_server_trust
from hsync_desktop.engine.endpoints import unverified_ssl_context
from hsync_desktop.engine.probes import (
    REASON_UNREACHABLE,
    certificate_ssl_context,
    fetch_server_certificate,
    probe_server_health,
)

__all__ = [
    "REASON_TRUST_CHANGED",
    "REASON_TRUST_MISSING",
    "REASON_TRUST_PIN_FAILED",
    "BucketTrust",
    "resolve_bucket_trust",
]

REASON_TRUST_MISSING = "trust_missing"
REASON_TRUST_CHANGED = "trust_changed"
REASON_TRUST_PIN_FAILED = "trust_pin_failed"


@dataclass(frozen=True, slots=True)
class BucketTrust:
    """The resolved TLS context for an authenticated probe.

    ``ssl_context`` is ``None`` only when ``reason`` explains why the request
    must not be sent. ``fingerprint`` is the observed server certificate (for the
    UI notice) and ``pinned`` says a TOFU pin was stored by this resolution.
    """

    ssl_context: ssl.SSLContext | None
    reason: str = ""
    fingerprint: str = ""
    pinned: bool = False


def resolve_bucket_trust(
    *,
    base_url: str,
    policy: str | None,
    insecure: bool,
    ca_cert: str,
    binary: str | None,
    timeout: float,
) -> BucketTrust:
    """Resolve the TLS context for the authenticated bucket probe.

    ``none``/``insecure`` return an unverified context only because the user
    explicitly asked for it; every pinning policy returns a verified context or
    one anchored to the server's certificate, never an unverified one.
    """
    selected = policy or TrustPolicy.auto.value
    if insecure or selected == TrustPolicy.none.value:
        return BucketTrust(unverified_ssl_context())

    verified = _verified_context(ca_cert)
    if selected == TrustPolicy.chain.value:
        return BucketTrust(verified)

    host, port = _host_port(base_url)
    chain_trusted = probe_server_health(base_url, ssl_context=verified, timeout=timeout).ok
    stored = _stored_fingerprint(binary, host, port)
    if selected == TrustPolicy.auto.value and chain_trusted and not stored:
        return BucketTrust(verified)

    certificate = fetch_server_certificate(host, port, timeout)
    if certificate is None:
        return BucketTrust(None, reason=REASON_UNREACHABLE)
    observed, pem = certificate
    stored = _stored_fingerprint(binary, host, port)

    if selected == TrustPolicy.auto.value:
        resolved = resolve_auto_policy(TrustPolicy.auto, stored, chain_trusted=chain_trusted)
    else:
        try:
            resolved = TrustPolicy(selected)
        except ValueError:
            return BucketTrust(None, reason=REASON_TRUST_MISSING, fingerprint=observed)

    action = evaluate_tls_trust(resolved, stored, observed)

    if action is TrustAction.proceed:
        context = verified if chain_trusted else certificate_ssl_context(pem)
        return BucketTrust(context, fingerprint=observed)
    if action is TrustAction.pin_and_proceed:
        if not _pin(binary, host, port, observed):
            return BucketTrust(None, reason=REASON_TRUST_PIN_FAILED, fingerprint=observed)
        return BucketTrust(certificate_ssl_context(pem), fingerprint=observed, pinned=True)
    if action is TrustAction.prompt:
        return BucketTrust(None, reason=REASON_TRUST_MISSING, fingerprint=observed)
    reason = REASON_TRUST_CHANGED if stored else REASON_TRUST_MISSING
    return BucketTrust(None, reason=reason, fingerprint=observed)


def _host_port(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url)
    return parsed.hostname or "", parsed.port or 443


def _verified_context(ca_cert: str) -> ssl.SSLContext:
    if ca_cert and Path(ca_cert).exists():
        return ssl.create_default_context(cafile=ca_cert)
    return ssl.create_default_context()


def _stored_fingerprint(binary: str | None, host: str, port: int) -> str | None:
    if not binary or not host:
        return None
    for entry in list_server_trust(binary) or []:
        if str(entry.get("host", "")).lower() != host.lower():
            continue
        raw_port = entry.get("port")
        if not isinstance(raw_port, (int, str)):
            continue
        try:
            entry_port = int(raw_port)
        except (TypeError, ValueError):
            continue
        if entry_port != port:
            continue
        return parse_fingerprint(str(entry.get("fingerprint", "")))
    return None


def _pin(binary: str | None, host: str, port: int, fingerprint: str) -> bool:
    if not binary or not host:
        return False
    return add_server_trust(binary, host, fingerprint, port)
