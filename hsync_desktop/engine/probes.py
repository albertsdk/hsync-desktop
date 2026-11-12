# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Blocking server reachability probes for the desktop GUI.

Shared by the Settings dialog "Test connection" action and the setup wizard.
Both must interpret the result identically, so the HTTP call, the REST paths
and the reason codes live here instead of being duplicated.
"""

from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from hsync_common.protocol.rest import (
    REST_BUCKET_PATH_TEMPLATE,
    REST_BUCKETS_PREFIX,
    REST_HEALTH_PATH,
)

__all__ = [
    "REASON_QUOTA",
    "ServerProbeResult",
    "create_server_bucket",
    "probe_server_bucket",
    "probe_server_bucket_access",
    "probe_server_health",
    "server_failure_reason",
]

# Machine reason codes; the UI maps them to localized messages (never shown raw).
REASON_UNREACHABLE = "unreachable"
REASON_SHARE_MISSING = "share_missing"
REASON_BAD_SHARE = "bad_share"
REASON_UNAUTHORIZED = "unauthorized"
REASON_SERVER_ERROR = "server_error"
REASON_QUOTA = "quota"


@dataclass(frozen=True, slots=True)
class ServerProbeResult:
    """Outcome of a server probe.

    ``ok`` is True only on HTTP 200. ``status`` is the HTTP status or ``None``
    when the request never completed (network/TLS error). ``authenticated`` is
    True when an API key was exercised (the bucket probe), so the caller can
    distinguish "reachable but unauthenticated" from "reachable and authorized".
    ``limit`` carries the server's per-account bucket cap when it refused a
    creation for that reason.
    """

    ok: bool
    status: int | None
    latency_ms: int
    authenticated: bool
    reason: str = ""
    limit: int | None = None


def _probe(
    url: str, api_key: str, ssl_context: ssl.SSLContext, timeout: float
) -> ServerProbeResult:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = Request(url, headers=headers, method="GET")
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout, context=ssl_context) as response:
            status = getattr(response, "status", None)
            latency = int((time.monotonic() - started) * 1000)
            return ServerProbeResult(status == 200, status, latency, bool(api_key))
    except HTTPError as exc:
        latency = int((time.monotonic() - started) * 1000)
        return ServerProbeResult(False, exc.code, latency, bool(api_key))
    except (URLError, ssl.SSLError, OSError, ValueError):
        latency = int((time.monotonic() - started) * 1000)
        return ServerProbeResult(False, None, latency, bool(api_key), REASON_UNREACHABLE)


def probe_server_health(
    base_url: str, *, ssl_context: ssl.SSLContext, timeout: float = 5.0
) -> ServerProbeResult:
    """Probe ``GET /health`` for reachability (no authentication)."""
    return _probe(f"{base_url.rstrip('/')}{REST_HEALTH_PATH}", "", ssl_context, timeout)


def probe_server_bucket(
    base_url: str,
    bucket: str,
    api_key: str,
    *,
    ssl_context: ssl.SSLContext,
    timeout: float = 5.0,
) -> ServerProbeResult:
    """Probe ``GET /api/v1/buckets/<bucket>`` for authentication + access.

    This is the only non-admin authenticated call, so it also verifies the API
    key. A 404 means the bucket is missing **or** the account has no access to
    it (the server deliberately does not distinguish the two).
    """
    path = REST_BUCKET_PATH_TEMPLATE.replace("{bucket}", quote(bucket, safe=""))
    return _probe(f"{base_url.rstrip('/')}{path}", api_key, ssl_context, timeout)


def create_server_bucket(
    base_url: str,
    bucket: str,
    api_key: str,
    *,
    ssl_context: ssl.SSLContext,
    timeout: float = 5.0,
) -> ServerProbeResult:
    """Create *bucket* on the server (``POST /api/v1/buckets?bucket=<name>``).

    The name travels as a query parameter (the create route has no path
    placeholder) and the creator becomes the owner. ``ok`` is True on 201 **and**
    on 409: a bucket that already exists is the outcome the caller wanted. A 403
    is the per-account quota when the body names it (``REASON_QUOTA`` with the
    cap in ``limit``), otherwise a rejected key.
    """
    url = f"{base_url.rstrip('/')}{REST_BUCKETS_PREFIX}?bucket={quote(bucket, safe='')}"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = Request(url, headers=headers, method="POST")
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout, context=ssl_context) as response:
            status = getattr(response, "status", None)
            latency = int((time.monotonic() - started) * 1000)
            return ServerProbeResult(status in (200, 201), status, latency, bool(api_key))
    except HTTPError as exc:
        latency = int((time.monotonic() - started) * 1000)
        if exc.code == 409:
            return ServerProbeResult(True, 409, latency, bool(api_key))
        if exc.code == 403:
            limit = _quota_limit(exc)
            if limit is not None:
                return ServerProbeResult(
                    False, 403, latency, bool(api_key), REASON_QUOTA, limit=limit
                )
            return ServerProbeResult(False, 403, latency, bool(api_key), REASON_UNAUTHORIZED)
        return ServerProbeResult(False, exc.code, latency, bool(api_key))
    except (URLError, ssl.SSLError, OSError, ValueError):
        latency = int((time.monotonic() - started) * 1000)
        return ServerProbeResult(False, None, latency, bool(api_key), REASON_UNREACHABLE)


def _quota_limit(exc: HTTPError) -> int | None:
    """The per-account bucket cap from a quota 403 body, or ``None``.

    The server answers ``{"info": "Bucket quota exceeded for account",
    "max_buckets_per_account": N}``; any other 403 (a rejected key) has no such
    field and must not be reported as a quota.
    """
    try:
        payload = json.loads(exc.read() or b"{}")
    except (ValueError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    limit = payload.get("max_buckets_per_account")
    return limit if isinstance(limit, int) and limit > 0 else None


def server_failure_reason(result: ServerProbeResult) -> str:
    """Reason code for a failed probe.

    Per-status, so a rejected key (401/403) is never reported as an unreachable
    server and a server-side fault (5xx) never as a bad name.
    """
    if result.status in (401, 403):
        return REASON_UNAUTHORIZED
    if result.status is not None and result.status >= 500:
        return REASON_SERVER_ERROR
    return REASON_UNREACHABLE


def probe_server_bucket_access(
    base_url: str,
    bucket: str,
    api_key: str,
    *,
    ssl_context: ssl.SSLContext,
    timeout: float = 5.0,
) -> tuple[ServerProbeResult, str]:
    """Reach the server, then check that the account may use *bucket*.

    Health comes first: a dead server must not be reported as a missing share.
    The reason code is empty on HTTP 200; otherwise one of ``unreachable``,
    ``unauthorized``, ``server_error``, ``bad_share`` or ``share_missing``
    (404 — the bucket does not exist **or** the account is not a member; the
    server deliberately does not tell the two apart).

    Shared by the wizard's Test connection and the Settings dialog's
    bucket-change check so both read a server answer identically.
    """
    health = probe_server_health(base_url, ssl_context=ssl_context, timeout=timeout)
    if not health.ok:
        return health, server_failure_reason(health)
    result = probe_server_bucket(
        base_url, bucket, api_key, ssl_context=ssl_context, timeout=timeout
    )
    if result.ok:
        return result, ""
    if result.status == 404:
        return result, REASON_SHARE_MISSING
    if result.status == 400:
        return result, REASON_BAD_SHARE
    return result, server_failure_reason(result)
