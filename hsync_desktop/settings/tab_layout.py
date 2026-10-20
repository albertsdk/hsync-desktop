# mypy: disable-error-code="attr-defined"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Regroup the Sync and p2p settings tabs into ``QGroupBox`` sections.

Split out of ``SettingsDialog`` (the methods are pure UI construction on the
dialog instance); ``SettingsDialog`` keeps thin wrappers calling these.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
)

if TYPE_CHECKING:
    from hsync_desktop.settings.dialog import SettingsDialog


def reorganize_sync_tab(dlg: SettingsDialog) -> None:
    """Reorganize the Sync tab into grouped sections using QGroupBox."""
    sync_tab = dlg._tabs.widget(_SYNC_TAB_INDEX)
    if not sync_tab:
        return

    # ── Collect label references from .ui ──────────────────
    lbl_shared: QLabel = dlg.findChild(QLabel, "lblSharedPath")  # type: ignore[assignment]
    lbl_bucket: QLabel = dlg.findChild(QLabel, "lblBucket")  # type: ignore[assignment]
    lbl_resync: QLabel = dlg.findChild(QLabel, "lblResync")  # type: ignore[assignment]
    lbl_retry: QLabel = dlg.findChild(QLabel, "lblRetryDelay")  # type: ignore[assignment]
    lbl_stability: QLabel = dlg.findChild(QLabel, "lblStabilityDelay")  # type: ignore[assignment]
    lbl_max_wait: QLabel = dlg.findChild(QLabel, "lblMaxWait")  # type: ignore[assignment]
    lbl_filter: QLabel = dlg.findChild(QLabel, "lblFilterPath")  # type: ignore[assignment]

    # Toggle switch containers (toggle.parent() == container QWidget)
    cont_continuous: QWidget = dlg.continuous.parent()  # type: ignore[assignment]
    cont_ignore: QWidget = dlg.ignore_delete.parent()  # type: ignore[assignment]
    cont_no_comp: QWidget = dlg.compression_enabled.parent()  # type: ignore[assignment]
    cont_dry_run: QWidget = dlg.dry_run.parent()  # type: ignore[assignment]
    cont_auto_sync: QWidget = dlg.auto_sync.parent()  # type: ignore[assignment]

    # ── Detach old layout ──────────────────────────────────
    old = sync_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    # ── Build new grouped layout (no scroll) ──────────────
    vbox = QVBoxLayout(sync_tab)
    vbox.setContentsMargins(4, 4, 4, 4)
    vbox.setSpacing(8)

    # Group 1: Path & Bucket
    dlg._grp_path = QGroupBox(tr("settings.group.path_bucket"))
    f1 = QFormLayout(dlg._grp_path)
    path_row = QHBoxLayout()
    path_row.addWidget(dlg.shared_path)
    path_row.addWidget(dlg.btn_browse_shared)
    f1.addRow(lbl_bucket, dlg.bucket)
    f1.addRow(lbl_shared, path_row)
    vbox.addWidget(dlg._grp_path)

    # Group 2: Sync Mode
    dlg._grp_sync = QGroupBox(tr("settings.group.sync_mode"))
    f2 = QFormLayout(dlg._grp_sync)
    f2.addRow(dlg._lbl_sync_direction, dlg.sync_direction_combo)
    f2.addRow("", cont_ignore)
    f2.addRow("", cont_continuous)
    f2.addRow("", cont_auto_sync)
    vbox.addWidget(dlg._grp_sync)

    # Group 3: Timing & Intervals
    dlg._grp_timing = QGroupBox(tr("settings.group.timing"))
    f3 = QFormLayout(dlg._grp_timing)
    f3.addRow(lbl_resync, dlg.resync)
    f3.addRow(lbl_retry, dlg.retry_delay)
    f3.addRow(lbl_stability, dlg.stability_delay)
    f3.addRow(lbl_max_wait, dlg.max_wait)
    vbox.addWidget(dlg._grp_timing)

    # Group 4: Advanced Options
    dlg._grp_advanced = QGroupBox(tr("settings.group.advanced"))
    f4 = QFormLayout(dlg._grp_advanced)
    dlg._lbl_min_free_disk_space = QLabel(tr("settings.min_free_disk_space"))
    f4.addRow(dlg._lbl_min_free_disk_space, dlg.min_free_disk_space)
    dlg._lbl_max_inbound_size = QLabel(tr("settings.max_inbound_size"))
    f4.addRow(dlg._lbl_max_inbound_size, dlg.max_inbound_size)
    f4.addRow(lbl_filter, dlg.filter_path)
    f4.addRow("", cont_no_comp)
    f4.addRow("", cont_dry_run)

    # Extra ignore patterns
    f4.addRow(dlg._lbl_ignore_patterns, dlg.ignore_patterns)

    # Edit .hsyncignore button (no left label, like a regular action)
    f4.addRow("", dlg.btn_edit_hsyncignore)

    # Maintenance: forget the folder's sync history (client-side state DB).
    f4.addRow("", dlg.btn_reset_state)
    vbox.addWidget(dlg._grp_advanced)

    vbox.addStretch()


def reorganize_p2p_tab(dlg: SettingsDialog) -> None:
    """Reorganize the p2p tab into grouped sections using QGroupBox."""
    p2p_tab = dlg._tabs.widget(_P2P_TAB_INDEX)
    if not p2p_tab:
        return

    lbl_group: QLabel = dlg.findChild(QLabel, "lblP2pGroup")  # type: ignore[assignment]
    lbl_key: QLabel = dlg.findChild(QLabel, "lblP2pKey")  # type: ignore[assignment]
    lbl_port: QLabel = dlg.findChild(QLabel, "lblP2pPort")  # type: ignore[assignment]
    lbl_discovery: QLabel = dlg.findChild(QLabel, "lblDiscoveryTimeout")  # type: ignore[assignment]

    # Toggle/trust containers (toggle.parent() == the container QWidget).
    cont_mode: QWidget = dlg.p2p_mode.parent()  # type: ignore[assignment]
    cont_upnp: QWidget = dlg.p2p_upnp.parent()  # type: ignore[assignment]
    cont_force: QWidget = dlg.prefer_master.parent()  # type: ignore[assignment]
    cont_never: QWidget = dlg.never_master.parent()  # type: ignore[assignment]
    cont_pairing: QWidget = dlg.require_pairing.parent()  # type: ignore[assignment]
    cont_peer: QWidget = dlg.peer_download.parent()  # type: ignore[assignment]
    trust_container: QWidget = dlg.p2p_bootnode_trust.parent()  # type: ignore[assignment]
    manage_container: QWidget = dlg.btn_manage_trusted_keys.parent()  # type: ignore[assignment]

    # Detach the original form layout.
    old = p2p_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    vbox = QVBoxLayout(p2p_tab)
    vbox.setContentsMargins(4, 4, 4, 4)
    vbox.setSpacing(8)

    # Group 1: mode + group identity
    dlg._grp_p2p_mode = QGroupBox(tr("settings.group.p2p_mode"))
    g1 = QFormLayout(dlg._grp_p2p_mode)
    g1.addRow("", cont_mode)
    g1.addRow(lbl_group, dlg.p2p_group)
    g1.addRow(lbl_key, dlg.p2p_key)
    vbox.addWidget(dlg._grp_p2p_mode)

    # Group 2: cross-network discovery through a bootnode
    dlg._grp_p2p_discovery = QGroupBox(tr("settings.group.p2p_discovery"))
    g2 = QFormLayout(dlg._grp_p2p_discovery)
    g2.addRow(dlg._lbl_p2p_bootnode, dlg.p2p_bootnode)
    g2.addRow(dlg._lbl_p2p_bootnode_trust, trust_container)
    g2.addRow("", manage_container)
    g2.addRow("", cont_upnp)
    vbox.addWidget(dlg._grp_p2p_discovery)

    # Group 3: role election + pairing
    dlg._grp_p2p_role = QGroupBox(tr("settings.group.p2p_role"))
    g3 = QFormLayout(dlg._grp_p2p_role)
    g3.addRow("", cont_force)
    g3.addRow("", cont_never)
    g3.addRow("", cont_pairing)
    vbox.addWidget(dlg._grp_p2p_role)

    # Group 4: advanced tuning
    dlg._grp_p2p_advanced = QGroupBox(tr("settings.group.advanced"))
    g4 = QFormLayout(dlg._grp_p2p_advanced)
    g4.addRow(lbl_port, dlg.p2p_port)
    g4.addRow(lbl_discovery, dlg.discovery_timeout)
    g4.addRow(dlg._lbl_ntp_hosts, dlg.ntp_hosts)
    g4.addRow("", cont_peer)
    g4.addRow(dlg._lbl_peer_read_cap, dlg.peer_read_cap)
    g4.addRow(dlg._lbl_peer_sources_max, dlg.peer_sources_max)
    vbox.addWidget(dlg._grp_p2p_advanced)

    vbox.addStretch()


def reorganize_server_tab(dlg: SettingsDialog) -> None:
    """Reorganize the Server Mode tab into grouped sections using QGroupBox."""
    server_tab = dlg._tabs.widget(_SERVER_TAB_INDEX)
    if not server_tab:
        return

    lbl_server_url: QLabel = dlg.findChild(QLabel, "lblServerUrl")  # type: ignore[assignment]
    lbl_api_key: QLabel = dlg.findChild(QLabel, "lblApiKey")  # type: ignore[assignment]
    lbl_ca_cert: QLabel = dlg.findChild(QLabel, "lblCaCert")  # type: ignore[assignment]
    lbl_timeout: QLabel = dlg.findChild(QLabel, "lblHttpTimeout")  # type: ignore[assignment]

    # Toggle/action containers (the widget's parent is the row container).
    cont_insecure: QWidget = dlg.insecure.parent()  # type: ignore[assignment]
    action_row: QWidget = dlg.btn_manage_trusted_keys_server.parent()  # type: ignore[assignment]

    old = server_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    vbox = QVBoxLayout(server_tab)
    vbox.setContentsMargins(4, 4, 4, 4)
    vbox.setSpacing(8)

    # The p2p-mode warning banner stays at the top, above the groups.
    vbox.addWidget(dlg._p2p_banner)

    # Group 1: server endpoint, credentials, identity and actions.
    dlg._grp_server = QGroupBox(tr("settings.group.server"))
    g1 = QFormLayout(dlg._grp_server)
    g1.addRow(lbl_server_url, dlg.server_url)
    g1.addRow(lbl_api_key, dlg.api_key)
    g1.addRow(dlg._lbl_server_trust, dlg.server_trust)
    g1.addRow("", action_row)
    vbox.addWidget(dlg._grp_server)

    # Group 2: TLS/certificate behaviour.
    dlg._grp_server_certificates = QGroupBox(tr("settings.group.server_certificates"))
    g2 = QFormLayout(dlg._grp_server_certificates)
    g2.addRow("", cont_insecure)
    g2.addRow(lbl_ca_cert, dlg.ca_cert)
    vbox.addWidget(dlg._grp_server_certificates)

    # Group 3: advanced request tuning.
    dlg._grp_server_advanced = QGroupBox(tr("settings.group.advanced"))
    g3 = QFormLayout(dlg._grp_server_advanced)
    g3.addRow(lbl_timeout, dlg.http_timeout)
    vbox.addWidget(dlg._grp_server_advanced)

    vbox.addStretch()


def reorganize_advanced_tab(dlg: SettingsDialog) -> None:
    """Reorganize the Advanced tab into grouped sections using QGroupBox."""
    advanced_tab = dlg._tabs.widget(_ADVANCED_TAB_INDEX)
    if not advanced_tab:
        return

    cont_autotune: QWidget = dlg.autotune.parent()  # type: ignore[assignment]
    cont_delta: QWidget = dlg.delta_enabled.parent()  # type: ignore[assignment]
    cont_guard: QWidget = dlg.mass_delete_guard.parent()  # type: ignore[assignment]
    cont_verbose: QWidget = dlg.verbose.parent()  # type: ignore[assignment]
    lbl_logfile: QLabel = dlg.findChild(QLabel, "lblLogfile")  # type: ignore[assignment]

    old = advanced_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    vbox = QVBoxLayout(advanced_tab)
    vbox.setContentsMargins(4, 4, 4, 4)
    vbox.setSpacing(8)

    # Group 1: performance
    dlg._grp_advanced_perf = QGroupBox(tr("settings.group.performance"))
    f1 = QFormLayout(dlg._grp_advanced_perf)
    f1.addRow("", cont_autotune)
    dlg._lbl_max_concurrent = QLabel(tr("settings.max_concurrent_transfers"))
    f1.addRow(dlg._lbl_max_concurrent, dlg.max_concurrent_transfers)
    vbox.addWidget(dlg._grp_advanced_perf)

    # Group 2: delta transfer
    dlg._grp_advanced_delta = QGroupBox(tr("settings.group.delta"))
    f2 = QFormLayout(dlg._grp_advanced_delta)
    f2.addRow("", cont_delta)
    dlg._lbl_delta_min = QLabel(tr("settings.delta_min_file_size"))
    f2.addRow(dlg._lbl_delta_min, dlg.delta_min_file_size)
    dlg._lbl_delta_min_p2p = QLabel(tr("settings.delta_min_file_size_p2p"))
    f2.addRow(dlg._lbl_delta_min_p2p, dlg.delta_min_file_size_p2p)
    vbox.addWidget(dlg._grp_advanced_delta)

    # Group 3: deletion protection
    dlg._grp_advanced_guard = QGroupBox(tr("settings.group.deletion_protection"))
    f3 = QFormLayout(dlg._grp_advanced_guard)
    f3.addRow("", cont_guard)
    dlg._lbl_guard_threshold = QLabel(tr("settings.mass_delete_threshold"))
    f3.addRow(dlg._lbl_guard_threshold, dlg.mass_delete_threshold)
    dlg._lbl_guard_percent = QLabel(tr("settings.mass_delete_percent"))
    f3.addRow(dlg._lbl_guard_percent, dlg.mass_delete_percent)
    vbox.addWidget(dlg._grp_advanced_guard)

    # Group 4: network
    dlg._grp_advanced_network = QGroupBox(tr("settings.group.network"))
    f4 = QFormLayout(dlg._grp_advanced_network)
    dlg._lbl_bandwidth_upload = QLabel(tr("settings.bandwidth_upload"))
    f4.addRow(dlg._lbl_bandwidth_upload, dlg.bandwidth_upload)
    dlg._lbl_bandwidth_download = QLabel(tr("settings.bandwidth_download"))
    f4.addRow(dlg._lbl_bandwidth_download, dlg.bandwidth_download)
    vbox.addWidget(dlg._grp_advanced_network)

    # Group 5: logging
    dlg._grp_advanced_logging = QGroupBox(tr("settings.group.logging"))
    f5 = QFormLayout(dlg._grp_advanced_logging)
    f5.addRow("", cont_verbose)
    f5.addRow(lbl_logfile, dlg.logfile)
    vbox.addWidget(dlg._grp_advanced_logging)

    vbox.addStretch()
