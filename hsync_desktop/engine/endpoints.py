# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Server/rendezvous-server endpoint grammar and probe TLS context for the desktop GUI.

The endpoint grammar itself lives in ``hsync_common.endpoint`` (SSOT). This
module fixes only the GUI's server default port and the probe's SSL policy, so
the Settings dialog and the setup wizard interpret the "server address" and
"rendezvous server" fields identically.
"""

from __future__ import annotations

import ssl
from pathlib import Path

from hsync_common.constants import SERVER_DEFAULT_PORT
from hsync_common.endpoint import (
    build_https_url,
    normalize_endpoint_list,
    parse_host_port,
    parse_https_url,
)

__all__ = [
    "SERVER_DEFAULT_PORT",
    "build_probe_ssl_context",
    "normalize_rendezvous_server_endpoints",
    "normalize_server_endpoint",
    "unverified_ssl_context",
]

# The client's server-mode default port (hsync_common SSOT): the server field
# carries only the address, so a bare host implies this port.

# Trust policies that trust the fingerprint rather than the chain. A probe
# cannot answer the client's terminal prompt, so it connects without chain
# validation in these modes (the real client still enforces the pin).
_FINGERPRINT_POLICIES = frozenset({"ask", "accept-new", "strict"})


def normalize_server_endpoint(raw: str) -> str | None:
    """Canonicalize the server field; raise ``ValueError`` on invalid input.

    Accepts the same forms as ``HSYNC_SERVER_URL`` (bare ``host``/``host:port``/
    ``[IPv6]``/``[IPv6]:port`` or a full ``https://…`` URL) and returns the
    canonical HTTPS URL so ``urlsplit``-based trust handling keeps working.
    Empty input yields ``None``.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if value.lower().startswith("https://"):
        return parse_https_url(value)
    return build_https_url(parse_host_port(value), SERVER_DEFAULT_PORT)


def normalize_rendezvous_server_endpoints(raw: str) -> str | None:
    """Canonicalize the rendezvous-server field; raise ``ValueError`` on invalid input.

    Returns the ordered comma-separated list of ``host``/``host:port``/
    ``[IPv6]:port`` endpoints; empty input yields ``None``. Delegates to the
    shared rule (``hsync_common.endpoint.normalize_endpoint_list``, strict) so
    the GUI field and the client's ``HSYNC_RENDEZVOUS_SERVER_ENDPOINTS`` cannot
    normalize differently, and a typo is reported instead of silently dropped.
    """
    return normalize_endpoint_list(raw, strict=True)


def unverified_ssl_context() -> ssl.SSLContext:
    """An SSLContext that skips chain/hostname verification (fingerprint mode)."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def build_probe_ssl_context(
    *,
    insecure: bool,
    trust_policy: str | None,
    ca_cert: str = "",
) -> ssl.SSLContext:
    """SSL context for a reachability probe, honouring the TLS settings.

    The probe must agree with how the client will connect: ``insecure`` /
    ``none`` skip verification, a ``--ca-cert`` file anchors it, a pinning
    policy (``ask``/``accept-new``/``strict``) trusts the fingerprint rather
    than the chain, and ``chain`` uses the default CA.
    """
    if insecure or trust_policy == "none":
        return unverified_ssl_context()
    if ca_cert and Path(ca_cert).exists():
        return ssl.create_default_context(cafile=ca_cert)
    if trust_policy in _FINGERPRINT_POLICIES:
        return unverified_ssl_context()
    return ssl.create_default_context()
