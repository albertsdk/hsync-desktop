# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Typed registry of the per-share ``QSettings`` keys.

A saved share stores the values of exactly these keys. The type is required
because ``QSettings``' INI backend returns strings unless a type is requested:
``"false"`` re-read as a bool would be truthy, so a snapshot without the type
would corrupt booleans and integers. ``settings/dialog.py::SettingsDialog.save``
is the reference for which keys exist and what they hold.
"""

from __future__ import annotations

from hsync_desktop.config import (
    DEFAULT_AUTO_APPLY,
    DEFAULT_AUTO_SYNC,
    DEFAULT_AUTOTUNE,
    DEFAULT_BUCKET,
    DEFAULT_CA_CERT,
    DEFAULT_COMPRESSION_ENABLED,
    DEFAULT_CONTINUOUS,
    DEFAULT_DELETION_POLICY,
    DEFAULT_DELTA_ENABLED,
    DEFAULT_DELTA_MIN_FILE_SIZE_KB,
    DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB,
    DEFAULT_DRY_RUN,
    DEFAULT_FILTER_PATH,
    DEFAULT_GROUP,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_INSECURE,
    DEFAULT_LOGFILE,
    DEFAULT_MASS_DELETE_GUARD,
    DEFAULT_MASS_DELETE_PERCENT,
    DEFAULT_MASS_DELETE_THRESHOLD,
    DEFAULT_MAX_CONCURRENT_TRANSFERS,
    DEFAULT_MAX_INBOUND_SIZE,
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_FREE_DISK_SPACE,
    DEFAULT_NEVER_MASTER,
    DEFAULT_NO_COMPRESSION,
    DEFAULT_NTP_HOSTS,
    DEFAULT_P2P_ENABLED,
    DEFAULT_P2P_KEY,
    DEFAULT_P2P_NO_MDNS,
    DEFAULT_P2P_PEER_DOWNLOAD,
    DEFAULT_P2P_PEER_READ_CAP,
    DEFAULT_P2P_PEER_SOURCES_MAX,
    DEFAULT_P2P_PORT,
    DEFAULT_P2P_RENDEZVOUS,
    DEFAULT_P2P_RENDEZVOUS_TRANSPORT,
    DEFAULT_P2P_RENDEZVOUS_TRUST,
    DEFAULT_P2P_TRUST,
    DEFAULT_P2P_UPNP_ENABLED,
    DEFAULT_PREFER_MASTER,
    DEFAULT_RENDEZVOUS_TIMEOUT,
    DEFAULT_RESYNC_INTERVAL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SERVER_TRUST,
    DEFAULT_STABILITY_DELAY,
    DEFAULT_SYNC_DIRECTION,
)

#: Per-share settings: ``key -> (default, type)``. Snapshot reads every key with
#: its type; apply writes the stored values back.
SHARE_KEYS: dict[str, tuple[object, type]] = {
    "path/local": ("", str),
    "sync/bucket": (DEFAULT_BUCKET, str),
    "sync/direction": (DEFAULT_SYNC_DIRECTION, str),
    "sync/continuous": (DEFAULT_CONTINUOUS, bool),
    "sync/resync": (DEFAULT_RESYNC_INTERVAL, int),
    "sync/retry_delay": (DEFAULT_RETRY_DELAY, int),
    "sync/stability_delay": (DEFAULT_STABILITY_DELAY, int),
    "sync/max_wait": (DEFAULT_MAX_WAIT, int),
    "sync/min_free_disk_space": (DEFAULT_MIN_FREE_DISK_SPACE, int),
    "sync/max_inbound_size": (DEFAULT_MAX_INBOUND_SIZE, int),
    "sync/filter_path": (DEFAULT_FILTER_PATH, str),
    "sync/ignore_patterns": (DEFAULT_IGNORE_PATTERNS, str),
    "sync/compression_enabled": (DEFAULT_COMPRESSION_ENABLED, bool),
    "sync/no_compression": (DEFAULT_NO_COMPRESSION, bool),
    "sync/deletion_policy": (DEFAULT_DELETION_POLICY, str),
    "sync/dry_run": (DEFAULT_DRY_RUN, bool),
    "sync/auto_sync": (DEFAULT_AUTO_SYNC, bool),
    "sync/auto_apply": (DEFAULT_AUTO_APPLY, bool),
    "sync/bandwidth_upload": (0.0, float),
    "sync/bandwidth_download": (0.0, float),
    "p2p/enabled": (DEFAULT_P2P_ENABLED, bool),
    "p2p/group": (DEFAULT_GROUP, str),
    "p2p/key": (DEFAULT_P2P_KEY, str),
    "p2p/key_mode": ("raw", str),
    "p2p/port": (DEFAULT_P2P_PORT, int),
    "p2p/rendezvous_timeout": (DEFAULT_RENDEZVOUS_TIMEOUT, int),
    "p2p/prefer_master": (DEFAULT_PREFER_MASTER, bool),
    "p2p/never_master": (DEFAULT_NEVER_MASTER, bool),
    "p2p/trust": (DEFAULT_P2P_TRUST, str),
    "p2p/peer_download": (DEFAULT_P2P_PEER_DOWNLOAD, bool),
    "p2p/peer_read_cap": (DEFAULT_P2P_PEER_READ_CAP, int),
    "p2p/peer_sources_max": (DEFAULT_P2P_PEER_SOURCES_MAX, int),
    "p2p/rendezvous_server_endpoints": (DEFAULT_P2P_RENDEZVOUS, str),
    "p2p/rendezvous_server_trust": (DEFAULT_P2P_RENDEZVOUS_TRUST, str),
    "p2p/rendezvous_transport": (DEFAULT_P2P_RENDEZVOUS_TRANSPORT, str),
    "p2p/upnp_enabled": (DEFAULT_P2P_UPNP_ENABLED, bool),
    "p2p/no_mdns": (DEFAULT_P2P_NO_MDNS, bool),
    "p2p/ntp_hosts": (DEFAULT_NTP_HOSTS, str),
    "connection/server_url": ("", str),
    "connection/api_key": ("", str),
    "connection/insecure": (DEFAULT_INSECURE, bool),
    "connection/ca_cert": (DEFAULT_CA_CERT, str),
    "connection/server_trust": (DEFAULT_SERVER_TRUST, str),
    "connection/http_timeout": (DEFAULT_HTTP_TIMEOUT, int),
    "advanced/autotune": (DEFAULT_AUTOTUNE, bool),
    "advanced/max_concurrent_transfers": (DEFAULT_MAX_CONCURRENT_TRANSFERS, int),
    "advanced/delta_enabled": (DEFAULT_DELTA_ENABLED, bool),
    "advanced/delta_min_file_size_kb": (DEFAULT_DELTA_MIN_FILE_SIZE_KB, int),
    "advanced/delta_min_file_size_p2p_kb": (DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB, int),
    "advanced/mass_delete_guard": (DEFAULT_MASS_DELETE_GUARD, bool),
    "advanced/mass_delete_threshold": (DEFAULT_MASS_DELETE_THRESHOLD, int),
    "advanced/mass_delete_percent": (DEFAULT_MASS_DELETE_PERCENT, int),
    "output/logfile": (DEFAULT_LOGFILE, str),
}

#: Prefixes a share may write on apply. A hand-edited or future blob can never
#: clobber a global setting (``appearance/*``, ``ui/*``…).
SHARE_PREFIXES = ("path/", "sync/", "p2p/", "connection/", "advanced/")

# ``connection/api_key`` and ``p2p/key`` hold Fernet-encrypted strings
# (`hsync_desktop/settings/crypto.py`): the store copies them verbatim and never
# decrypts or logs them.
