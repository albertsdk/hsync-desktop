# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Blocking server reachability probes for the desktop GUI.

Shared by the Settings dialog "Test connection" action and the setup wizard.
Both must interpret the result identically, so the HTTP call, the REST paths
and the reason codes live here instead of being duplicated.
"""

from __future__ import annotations

import ssl
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from hsync_common.protocol.rest import REST_BUCKET_PATH_TEMPLATE, REST_HEALTH_PATH

__all__ = ["ServerProbeResult", "probe_server_bucket", "probe_server_health"]

# Machine reason codes; the UI maps them to localized messages (never shown raw).
REASON_UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class ServerProbeResult:
    """Outcome of a server probe.

    ``ok`` is True only on HTTP 200. ``status`` is the HTTP status or ``None``
    when the request never completed (network/TLS error). ``authenticated`` is
    True when an API key was exercised (the bucket probe), so the caller can
    distinguish "reachable but unauthenticated" from "reachable and authorized".
    """

    ok: bool
    status: int | None
    latency_ms: int
    authenticated: bool
    reason: str = ""


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
