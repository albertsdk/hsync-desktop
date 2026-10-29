# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""HSYNC engine package: synchronous CLI helpers and the subprocess bridge.

Re-exports the public surface previously provided by ``engine.py`` so existing
``from hsync_desktop.engine import ...`` imports keep working.
"""

from hsync_desktop.engine.async_probe import AsyncProbe, ProbeOutcome
from hsync_desktop.engine.cli import (
    _CAPABILITIES_CACHE_KEY,
    _EXPECTED_VERSION,
    _VERSION_CACHE_KEY,
    BinaryVersionProbe,
    ResetStateResult,
    add_peer_pin,
    add_rendezvous_trust,
    add_server_trust,
    fetch_rendezvous_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    get_binary_capabilities,
    get_binary_capabilities_cached,
    get_binary_version,
    get_binary_version_cached,
    is_binary_version_compatible,
    list_peer_pins,
    list_rendezvous_trust,
    list_server_trust,
    remove_peer_pin,
    remove_rendezvous_trust,
    remove_server_trust,
    reset_sync_state,
    supports_peer_trust,
)
from hsync_desktop.engine.endpoints import (
    SERVER_DEFAULT_PORT,
    build_probe_ssl_context,
    normalize_rendezvous_server_endpoints,
    normalize_server_endpoint,
    unverified_ssl_context,
)
from hsync_desktop.engine.probes import (
    ServerProbeResult,
    probe_server_bucket,
    probe_server_health,
)
from hsync_desktop.engine.process import (
    _HSYNCKEEP,
    HsyncEngine,
    TransferStats,
    apply_settings_env,
    p2p_secret_mode,
    p2p_secret_option,
    write_secret_pipe,
)

__all__ = [
    "AsyncProbe",
    "BinaryVersionProbe",
    "HsyncEngine",
    "ProbeOutcome",
    "ResetStateResult",
    "ServerProbeResult",
    "SERVER_DEFAULT_PORT",
    "TransferStats",
    "add_rendezvous_trust",
    "add_peer_pin",
    "add_server_trust",
    "apply_settings_env",
    "build_probe_ssl_context",
    "fetch_rendezvous_fingerprint",
    "fetch_server_fingerprint",
    "find_hsync_binary",
    "get_binary_capabilities",
    "get_binary_capabilities_cached",
    "get_binary_version",
    "get_binary_version_cached",
    "is_binary_version_compatible",
    "list_rendezvous_trust",
    "list_peer_pins",
    "list_server_trust",
    "normalize_rendezvous_server_endpoints",
    "normalize_server_endpoint",
    "p2p_secret_mode",
    "p2p_secret_option",
    "probe_server_bucket",
    "probe_server_health",
    "remove_rendezvous_trust",
    "remove_peer_pin",
    "remove_server_trust",
    "reset_sync_state",
    "supports_peer_trust",
    "unverified_ssl_context",
    "write_secret_pipe",
]
