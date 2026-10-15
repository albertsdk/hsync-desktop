# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""HSYNC engine package: synchronous CLI helpers and the subprocess bridge.

Re-exports the public surface previously provided by ``engine.py`` so existing
``from hsync_desktop.engine import ...`` imports keep working.
"""

from hsync_desktop.engine.cli import (
    _CAPABILITIES_CACHE_KEY,
    _EXPECTED_VERSION,
    _VERSION_CACHE_KEY,
    BinaryVersionProbe,
    add_bootnode_trust,
    add_peer_pin,
    add_server_trust,
    fetch_bootnode_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    get_binary_capabilities,
    get_binary_capabilities_cached,
    get_binary_version,
    get_binary_version_cached,
    is_binary_version_compatible,
    list_bootnode_trust,
    list_peer_pins,
    list_server_trust,
    remove_bootnode_trust,
    remove_peer_pin,
    remove_server_trust,
    supports_peer_trust,
)
from hsync_desktop.engine.process import (
    _HSYNCKEEP,
    HsyncEngine,
    TransferStats,
    apply_settings_env,
    write_secret_pipe,
)

__all__ = [
    "BinaryVersionProbe",
    "HsyncEngine",
    "TransferStats",
    "add_bootnode_trust",
    "add_peer_pin",
    "add_server_trust",
    "apply_settings_env",
    "fetch_bootnode_fingerprint",
    "fetch_server_fingerprint",
    "find_hsync_binary",
    "get_binary_capabilities",
    "get_binary_capabilities_cached",
    "get_binary_version",
    "get_binary_version_cached",
    "is_binary_version_compatible",
    "list_bootnode_trust",
    "list_peer_pins",
    "list_server_trust",
    "remove_bootnode_trust",
    "remove_peer_pin",
    "remove_server_trust",
    "supports_peer_trust",
    "write_secret_pipe",
]
