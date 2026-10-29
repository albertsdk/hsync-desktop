# mypy: disable-error-code="attr-defined"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Apply the i18n strings to every SettingsDialog widget.

Split out of ``SettingsDialog`` (pure presentation on the dialog instance);
``SettingsDialog`` keeps a thin wrapper calling this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel

from hsync_desktop.i18n import SUPPORTED_LANGUAGES, tr
from hsync_desktop.icons import style_ok_cancel_button_box
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
    _TAB_DESCRIPTION_KEYS,
)
from hsync_desktop.settings.tab_layout import equalize_tab_descriptions
from hsync_desktop.widgets.links import set_help_link_text
from hsync_desktop.widgets.text import escape_mnemonics

if TYPE_CHECKING:
    from hsync_desktop.settings.dialog import SettingsDialog


def apply_translations(dlg: SettingsDialog) -> None:
    """Apply i18n translations to UI elements."""
    dlg.setWindowTitle(tr("settings.title"))

    # Tab titles
    dlg._tabs.setTabText(_SYNC_TAB_INDEX, escape_mnemonics(tr("settings.sync")))
    dlg._tabs.setTabText(_P2P_TAB_INDEX, escape_mnemonics(tr("settings.p2p")))
    dlg._tabs.setTabText(_SERVER_TAB_INDEX, escape_mnemonics(tr("settings.server_mode")))
    dlg._tabs.setTabText(_GENERAL_TAB_INDEX, escape_mnemonics(tr("settings.general")))
    dlg._tabs.setTabText(_ADVANCED_TAB_INDEX, escape_mnemonics(tr("settings.advanced")))

    # Tab descriptions (mode tabs only, see _TAB_DESCRIPTION_KEYS)
    for tab_index, key in _TAB_DESCRIPTION_KEYS.items():
        hint = dlg._tab_descriptions.get(tab_index)
        if hint is not None:
            hint.setText(tr(key))

    # Sync tab - shared path label
    lbl_shared: QLabel = dlg.findChild(QLabel, "lblSharedPath")  # type: ignore[assignment]
    if lbl_shared:
        lbl_shared.setText(tr("settings.shared_path"))

    # Server Mode tab labels
    lbl: QLabel = dlg.findChild(QLabel, "lblServerUrl")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.server_url"))
    lbl = dlg.findChild(QLabel, "lblApiKey")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.api_key"))
    dlg._lbl_insecure.setText(tr("settings.insecure"))
    lbl = dlg.findChild(QLabel, "lblCaCert")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.ca_cert"))
    lbl = dlg.findChild(QLabel, "lblHttpTimeout")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.http_timeout"))
    dlg._lbl_server_trust.setText(tr("settings.server_trust"))
    dlg._populate_server_trust()
    dlg.btn_test_connection.setText(
        escape_mnemonics(
            tr("common.checking")
            if getattr(dlg, "_probe_target", None) == "server"
            else tr("settings.test_connection")
        )
    )

    # Sync tab labels
    lbl = dlg.findChild(QLabel, "lblBucket")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.bucket"))
    dlg._lbl_continuous.setText(tr("settings.watch"))
    dlg._lbl_deletion_policy.setText(tr("settings.deletion_policy"))
    dlg._populate_deletion_policy()
    dlg._lbl_sync_direction.setText(tr("settings.sync_direction"))
    dlg.sync_direction_combo.setItemText(0, tr("settings.sync_direction.bidirectional"))
    dlg.sync_direction_combo.setItemText(1, tr("settings.sync_direction.upload_only"))
    dlg.sync_direction_combo.setItemText(2, tr("settings.sync_direction.download_only"))
    lbl = dlg.findChild(QLabel, "lblResync")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.resync"))
    dlg.resync.setSpecialValueText(tr("settings.disabled"))
    lbl = dlg.findChild(QLabel, "lblRetryDelay")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.retry_delay"))
    lbl = dlg.findChild(QLabel, "lblStabilityDelay")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.stability_delay"))
    dlg.stability_delay.setSpecialValueText(tr("settings.auto"))
    lbl = dlg.findChild(QLabel, "lblMaxWait")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.max_wait"))
    lbl = dlg.findChild(QLabel, "lblFilterPath")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.filter_path"))
    dlg._lbl_min_free_disk_space.setText(tr("settings.min_free_disk_space"))
    dlg.min_free_disk_space.setSpecialValueText(tr("settings.disabled"))
    dlg._lbl_max_inbound_size.setText(tr("settings.max_inbound_size"))
    dlg.max_inbound_size.setSpecialValueText(tr("settings.disabled"))
    dlg._lbl_compression_enabled.setText(tr("settings.compression_enabled"))
    dlg._lbl_dry_run.setText(tr("settings.dry_run"))
    dlg._lbl_auto_sync.setText(tr("settings.auto_sync"))
    dlg._lbl_ignore_patterns.setText(tr("settings.ignore_patterns"))
    dlg.btn_edit_hsyncignore.setText(escape_mnemonics(tr("settings.edit_hsyncignore")))
    dlg.btn_reset_state.setText(escape_mnemonics(tr("settings.reset_state.button")))

    # Sync tab group box titles
    dlg._grp_path.setTitle(escape_mnemonics(tr("settings.group.path_bucket")))
    dlg._grp_sync.setTitle(escape_mnemonics(tr("settings.group.sync_mode")))
    dlg._grp_timing.setTitle(escape_mnemonics(tr("settings.group.timing")))
    dlg._grp_advanced.setTitle(escape_mnemonics(tr("settings.group.advanced")))
    dlg._grp_p2p_mode.setTitle(escape_mnemonics(tr("settings.group.p2p_mode")))
    dlg._grp_p2p_discovery.setTitle(escape_mnemonics(tr("settings.group.p2p_discovery")))
    dlg._grp_p2p_role.setTitle(escape_mnemonics(tr("settings.group.p2p_role")))
    dlg._grp_p2p_advanced.setTitle(escape_mnemonics(tr("settings.group.advanced")))
    dlg._grp_server.setTitle(escape_mnemonics(tr("settings.group.server")))
    dlg._grp_server_certificates.setTitle(
        escape_mnemonics(tr("settings.group.server_certificates"))
    )
    dlg._grp_server_advanced.setTitle(escape_mnemonics(tr("settings.group.advanced")))

    # Advanced tab group box titles
    dlg._grp_advanced_perf.setTitle(escape_mnemonics(tr("settings.group.performance")))
    dlg._grp_advanced_delta.setTitle(escape_mnemonics(tr("settings.group.delta")))
    dlg._grp_advanced_guard.setTitle(escape_mnemonics(tr("settings.group.deletion_protection")))
    dlg._lbl_deletion_risk_reset.setText(tr("settings.deletion_risk_reset_hint"))
    dlg.btn_deletion_risk_reset.setText(escape_mnemonics(tr("settings.deletion_risk_reset")))
    dlg._grp_advanced_network.setTitle(escape_mnemonics(tr("settings.group.network")))
    dlg._grp_advanced_logging.setTitle(escape_mnemonics(tr("settings.group.logging")))

    # p2p tab labels
    dlg._lbl_p2p_mode.setText(tr("settings.p2p_mode"))
    lbl = dlg.findChild(QLabel, "lblP2pGroup")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.p2p_group"))
    lbl = dlg.findChild(QLabel, "lblP2pKey")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.p2p_key"))
    lbl = dlg.findChild(QLabel, "lblP2pPort")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.p2p_port"))
    dlg._lbl_p2p_bootnode.setText(tr("settings.p2p_bootnode"))
    dlg._lbl_p2p_bootnode_trust.setText(tr("settings.p2p_bootnode_trust"))
    dlg._populate_bootnode_trust()
    dlg.btn_manage_trusted_keys.setText(escape_mnemonics(tr("settings.manage_trusted_keys")))
    dlg.btn_manage_trusted_keys_server.setText(escape_mnemonics(tr("settings.manage_trusted_keys")))
    dlg.btn_test_bootnode.setText(
        escape_mnemonics(
            tr("common.checking")
            if getattr(dlg, "_probe_target", None) == "bootnode"
            else tr("settings.test_connection")
        )
    )
    dlg._lbl_p2p_upnp.setText(tr("settings.p2p_upnp"))
    lbl = dlg.findChild(QLabel, "lblDiscoveryTimeout")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.discovery_timeout"))
    dlg._lbl_ntp_hosts.setText(tr("settings.ntp_hosts"))
    dlg._lbl_prefer_master.setText(tr("settings.prefer_master"))
    dlg._lbl_never_master.setText(tr("settings.never_master"))
    dlg._lbl_p2p_trust.setText(tr("settings.p2p_trust"))
    dlg._populate_p2p_trust()
    dlg._lbl_peer_download.setText(tr("settings.peer_download"))
    dlg._lbl_peer_read_cap.setText(tr("settings.peer_read_cap"))
    dlg._lbl_peer_sources_max.setText(tr("settings.peer_sources_max"))

    # Advanced tab labels (engine tuning + logging)
    dlg._lbl_autotune.setText(tr("settings.autotune"))
    dlg._lbl_max_concurrent.setText(tr("settings.max_concurrent_transfers"))
    dlg._lbl_delta_enabled.setText(tr("settings.delta_enabled"))
    dlg._lbl_delta_min.setText(tr("settings.delta_min_file_size"))
    dlg._lbl_delta_min_p2p.setText(tr("settings.delta_min_file_size_p2p"))
    dlg._lbl_mass_delete_guard.setText(tr("settings.mass_delete_guard"))
    dlg._lbl_guard_threshold.setText(tr("settings.mass_delete_threshold"))
    dlg._lbl_guard_percent.setText(tr("settings.mass_delete_percent"))
    dlg._lbl_bandwidth_upload.setText(tr("settings.bandwidth_upload"))
    dlg._lbl_bandwidth_download.setText(tr("settings.bandwidth_download"))
    dlg._lbl_verbose.setText(tr("settings.verbose"))
    dlg._lbl_quiet.setText(tr("settings.quiet"))
    lbl = dlg.findChild(QLabel, "lblLogfile")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.logfile"))
    dlg.max_concurrent_transfers.setSpecialValueText(tr("settings.auto"))
    dlg.mass_delete_threshold.setSpecialValueText(tr("settings.disabled"))
    dlg.mass_delete_percent.setSpecialValueText(tr("settings.disabled"))
    dlg.bandwidth_upload.setSpecialValueText(tr("settings.unlimited"))
    dlg.bandwidth_download.setSpecialValueText(tr("settings.unlimited"))

    # General tab labels (interface + startup)
    lbl = dlg.findChild(QLabel, "lblTheme")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.theme"))
    dlg.theme_combo.setItemText(0, tr("settings.theme_light"))
    dlg.theme_combo.setItemText(1, tr("settings.theme_dark"))
    dlg.theme_combo.setItemText(2, tr("settings.theme_system"))
    dlg._lbl_font_scale.setText(tr("settings.font_size"))
    dlg.font_scale_combo.setItemText(0, tr("settings.font_size_standard"))
    dlg.font_scale_combo.setItemText(1, tr("settings.font_size_compact"))
    lbl = dlg.findChild(QLabel, "lblLanguage")  # type: ignore[assignment]
    if lbl:
        lbl.setText(tr("settings.language"))
    # The first language entry ("System default") is localized; the endonyms are not.
    if dlg.lang_combo.count():
        dlg.lang_combo.setItemText(0, tr("settings.language_system"))
    dlg._grp_general_appearance.setTitle(escape_mnemonics(tr("settings.group.appearance")))
    dlg._grp_general_notifications.setTitle(escape_mnemonics(tr("settings.group.notifications")))
    dlg._grp_general_window.setTitle(escape_mnemonics(tr("settings.group.window")))
    dlg._lbl_notifications.setText(tr("settings.notifications"))
    dlg._lbl_notifications_categories.setText(tr("settings.notifications_categories"))
    for category, (_toggle, label) in dlg.notification_toggles.items():
        label.setText(tr(f"settings.notifications_{category}"))
    dlg._lbl_tooltips.setText(tr("settings.tooltips"))
    dlg._lbl_show_log_panel.setText(tr("settings.show_log_panel"))
    dlg._lbl_start_at_login.setText(tr("settings.start_at_login"))
    dlg._lbl_show_advanced.setText(tr("settings.show_advanced"))

    # Contextual documentation links (fixed URLs; only the text is localized).
    set_help_link_text(dlg._lbl_help_server, "help.server_setup")
    set_help_link_text(dlg._lbl_help_bootnode, "help.bootnode_setup")

    # Button box
    style_ok_cancel_button_box(dlg._button_box)
