# mypy: disable-error-code="attr-defined"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Widget builders for the SettingsDialog tabs.

Split out of ``SettingsDialog._load_ui`` (which only orchestrates them); each
builder operates on the dialog instance and sets its widget attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.config import (
    BANDWIDTH_MAX_MBPS,
    FONT_SCALE_COMPACT,
    FONT_SCALE_STANDARD,
    MAX_INBOUND_SIZE_MB_MAX,
    MAX_INBOUND_SIZE_MB_MIN,
    MIN_FREE_DISK_SPACE_MB_MAX,
    MIN_FREE_DISK_SPACE_MB_MIN,
    NOTIFICATION_CATEGORIES,
)
from hsync_desktop.i18n import AUTO_LANGUAGE, SUPPORTED_LANGUAGES, tr
from hsync_desktop.icons import icon
from hsync_desktop.settings.form_helpers import (
    _action_row,
    _insert_row_after,
    _replace_checkbox_with_toggle,
    switch_row,
)
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
)
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT, THEME_SYSTEM
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.widgets.toggle_switch import ToggleSwitch

if TYPE_CHECKING:
    from hsync_desktop.settings.dialog import SettingsDialog


def build_connection_banner(dlg: SettingsDialog) -> None:
    """Create the warning banner shown at the top while a sync is active."""

    # Create info banner for when connection is active (hidden by default)
    dlg._connection_banner = QFrame(dlg)
    dlg._connection_banner.setObjectName("connectionBanner")
    dlg._connection_banner.setStyleSheet(
        "QFrame#connectionBanner { "
        "background-color: #fff3cd; "
        "border: 1px solid #ffc107; "
        "border-radius: 4px; "
        "padding: 8px; "
        "}"
    )
    banner_layout = QHBoxLayout(dlg._connection_banner)
    banner_layout.setContentsMargins(8, 4, 8, 4)
    dlg._banner_icon = QLabel("⚠️")
    dlg._banner_text = QLabel()
    dlg._banner_text.setWordWrap(True)
    dlg._banner_text.setStyleSheet("color: #856404;")
    banner_layout.addWidget(dlg._banner_icon)
    banner_layout.addWidget(dlg._banner_text, 1)
    dlg._connection_banner.hide()

    # Insert banner at the top of the main layout
    main_layout = dlg.findChild(QVBoxLayout, "mainLayout")
    if main_layout:
        main_layout.insertWidget(0, dlg._connection_banner)


def build_sync_tab(dlg: SettingsDialog) -> None:
    """Build the Sync-tab widgets and their dynamic rows."""

    # Sync tab widgets (now first tab, index 0)
    dlg.shared_path = dlg.findChild(QLineEdit, "sharedPath")
    dlg.btn_browse_shared = dlg.findChild(QToolButton, "btnBrowseShared")
    dlg.bucket = dlg.findChild(QLineEdit, "bucket")
    dlg.continuous, dlg._lbl_continuous = _replace_checkbox_with_toggle(dlg, "continuous")
    dlg.ignore_delete, dlg._lbl_ignore_delete = _replace_checkbox_with_toggle(dlg, "ignoreDelete")

    # Sync direction combo – inject BEFORE ignore_delete row (so direction comes first)
    dlg.sync_direction_combo = QComboBox(dlg)
    dlg.sync_direction_combo.addItem("", "bidirectional")
    dlg.sync_direction_combo.addItem("", "upload-only")
    dlg.sync_direction_combo.addItem("", "download-only")
    dlg._lbl_sync_direction = QLabel(dlg)
    # Find the Sync tab form layout and inject before ignore_delete row
    sync_tab = dlg._tabs.widget(_SYNC_TAB_INDEX)
    if sync_tab:
        for child in sync_tab.findChildren(QFormLayout):
            form: QFormLayout = child
            # Find the ignore_delete row and insert before it
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() and item.widget() is dlg.ignore_delete.parent():
                    form.insertRow(row, dlg._lbl_sync_direction, dlg.sync_direction_combo)
                    break
            break
    dlg.resync = dlg.findChild(QSpinBox, "resync")
    dlg.retry_delay = dlg.findChild(QSpinBox, "retryDelay")
    dlg.stability_delay = dlg.findChild(QSpinBox, "stabilityDelay")
    dlg.max_wait = dlg.findChild(QSpinBox, "maxWait")
    dlg.filter_path = dlg.findChild(QLineEdit, "filterPath")
    dlg.min_free_disk_space = QSpinBox()
    dlg.min_free_disk_space.setObjectName("minFreeDiskSpace")
    dlg.min_free_disk_space.setRange(MIN_FREE_DISK_SPACE_MB_MIN, MIN_FREE_DISK_SPACE_MB_MAX)
    dlg.min_free_disk_space.setSuffix(" MB")
    dlg.min_free_disk_space.setSpecialValueText(tr("settings.disabled"))
    dlg.max_inbound_size = QSpinBox()
    dlg.max_inbound_size.setObjectName("maxInboundSize")
    dlg.max_inbound_size.setRange(MAX_INBOUND_SIZE_MB_MIN, MAX_INBOUND_SIZE_MB_MAX)
    dlg.max_inbound_size.setSuffix(" MB")
    dlg.max_inbound_size.setSpecialValueText(tr("settings.disabled"))
    dlg.compression_enabled, dlg._lbl_compression_enabled = _replace_checkbox_with_toggle(
        dlg, "noCompression"
    )
    dlg.dry_run, dlg._lbl_dry_run = _replace_checkbox_with_toggle(dlg, "dryRun")
    dlg.auto_sync, dlg._lbl_auto_sync = _replace_checkbox_with_toggle(dlg, "autoSync")

    # Hidden-file / .hsyncignore controls (dynamic, no .ui counterpart)
    dlg.ignore_patterns = QLineEdit(dlg)
    dlg.ignore_patterns.setObjectName("ignorePatterns")
    dlg.ignore_patterns.setPlaceholderText("*.log, /build/, /dist/")
    dlg._lbl_ignore_patterns = QLabel(dlg)
    dlg.btn_edit_hsyncignore = QPushButton(dlg)
    dlg.btn_edit_hsyncignore.setObjectName("btnEditHsyncignore")
    # Client-side sync-state reset (merge bases + deletion markers). Lives in the
    # client because only it can take the per-directory instance lock.
    dlg.btn_reset_state = QPushButton(dlg)
    dlg.btn_reset_state.setObjectName("btnResetState")

    # Reorganize sync tab into grouped sections
    dlg._reorganize_sync_tab()


def build_server_tab(dlg: SettingsDialog) -> None:
    """Build the Server Mode-tab widgets, its banner and action row."""

    # Connection tab widgets (now second tab, index 1 — "Server Mode")
    dlg.server_url = dlg.findChild(QLineEdit, "serverUrl")
    # A bare host (or host:port) is enough: https:// and the default port are implied.
    dlg.server_url.setPlaceholderText("hsync.example.com")
    dlg.api_key = dlg.findChild(QLineEdit, "apiKey")
    dlg.insecure, dlg._lbl_insecure = _replace_checkbox_with_toggle(dlg, "insecure")
    dlg.ca_cert = dlg.findChild(QLineEdit, "caCert")
    dlg.http_timeout = dlg.findChild(QSpinBox, "httpTimeout")

    # Server TLS trust policy combo (ADR-0036), inserted after http_timeout.
    dlg.server_trust = QComboBox(dlg)
    dlg.server_trust.setObjectName("serverTrust")
    dlg._lbl_server_trust = QLabel(dlg)
    # Create info banner for Server Mode tab when p2p is active (hidden by default)
    dlg._p2p_banner = QFrame(dlg)
    dlg._p2p_banner.setObjectName("p2pBanner")
    dlg._p2p_banner.setStyleSheet(
        "QFrame#p2pBanner { "
        "background-color: #fff3cd; "
        "border: 1px solid #ffc107; "
        "border-radius: 4px; "
        "padding: 8px; "
        "}"
    )
    p2p_banner_layout = QHBoxLayout(dlg._p2p_banner)
    p2p_banner_layout.setContentsMargins(8, 4, 8, 4)
    dlg._p2p_banner_icon = QLabel("⚠️")
    dlg._p2p_banner_text = QLabel()
    dlg._p2p_banner_text.setWordWrap(True)
    dlg._p2p_banner_text.setStyleSheet("color: #856404;")
    p2p_banner_layout.addWidget(dlg._p2p_banner_icon)
    p2p_banner_layout.addWidget(dlg._p2p_banner_text, 1)
    dlg._p2p_banner.hide()

    # Insert p2p banner at the top of the Server Mode (tabConnection) layout
    # Also insert the server trust-policy controls and Test Connection button
    dlg.btn_test_connection = QPushButton()
    dlg.btn_test_connection.setObjectName("btnTestConnection")

    # Server-panel twin of the p2p "Manage trusted keys" button, opening the
    # dialog on the Servers tab. Two buttons keep the two panels gated
    # independently (server fields disabled in p2p mode, and vice versa).
    dlg.btn_manage_trusted_keys_server = QPushButton()
    dlg.btn_manage_trusted_keys_server.setObjectName("btnManageTrustedKeysServer")
    dlg.btn_manage_trusted_keys_server.clicked.connect(dlg._open_server_trusted_keys)

    conn_tab = dlg._tabs.widget(_SERVER_TAB_INDEX)
    if conn_tab:
        conn_layout = conn_tab.layout()
        if isinstance(conn_layout, QFormLayout):
            conn_layout.insertRow(0, dlg._p2p_banner)
            # Insert the server trust-policy combo after the http_timeout
            # row, then the trusted-keys + Test Connection buttons below it.
            for row in range(conn_layout.rowCount()):
                item = conn_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() == dlg.http_timeout:
                    conn_layout.insertRow(row + 1, dlg._lbl_server_trust, dlg.server_trust)
                    conn_layout.insertRow(
                        row + 2,
                        "",
                        _action_row(
                            dlg.btn_manage_trusted_keys_server,
                            dlg.btn_test_connection,
                        ),
                    )
                    break

    # Regroup the tab into sections, matching the other settings tabs.
    dlg._reorganize_server_tab()


def build_p2p_tab(dlg: SettingsDialog) -> None:
    """Build the p2p-tab widgets and their dynamic rows."""

    # p2p tab widgets
    dlg.p2p_mode, dlg._lbl_p2p_mode = _replace_checkbox_with_toggle(dlg, "p2pMode")
    dlg.p2p_group = dlg.findChild(QLineEdit, "p2pGroup")
    dlg.p2p_key = dlg.findChild(QLineEdit, "p2pKey")
    dlg.p2p_port = dlg.findChild(QSpinBox, "p2pPort")
    dlg.discovery_timeout = dlg.findChild(QSpinBox, "discoveryTimeout")

    # Bootnode (optional) – cross-network discovery through a boot/1 node.
    # Dynamic, no .ui counterpart; inserted right after the group row.
    dlg.p2p_bootnode = QLineEdit(dlg)
    dlg.p2p_bootnode.setObjectName("p2pBootnode")
    dlg.p2p_bootnode.setPlaceholderText("boot.example.net")
    dlg._lbl_p2p_bootnode = QLabel(dlg)
    _insert_row_after(dlg.p2p_group, dlg._lbl_p2p_bootnode, dlg.p2p_bootnode)

    # Trust policy (ADR-0035): how the client authenticates the bootnode.
    # Own form row so the label aligns under "Bootnode (optional)".
    dlg.p2p_bootnode_trust = QComboBox(dlg)
    dlg.p2p_bootnode_trust.setObjectName("p2pBootnodeTrust")
    dlg._lbl_p2p_bootnode_trust = QLabel(dlg)
    trust_container = QWidget(dlg)
    hl_trust = QHBoxLayout(trust_container)
    hl_trust.setContentsMargins(0, 0, 0, 0)
    hl_trust.addWidget(dlg.p2p_bootnode_trust)
    hl_trust.addStretch()
    dlg._populate_bootnode_trust()
    _insert_row_after(dlg.p2p_bootnode, dlg._lbl_p2p_bootnode_trust, trust_container)

    # Manage trusted keys (ADR-0035): opens the known-hosts / known-peers
    # dialog that edits the shared stores via the hsync CLI.
    dlg.btn_manage_trusted_keys = QPushButton(dlg)
    dlg.btn_manage_trusted_keys.setObjectName("btnManageTrustedKeys")
    dlg.btn_manage_trusted_keys.clicked.connect(dlg._open_trusted_keys)

    # Verify the configured bootnode answers (probes its certificate via the
    # client; mirrors the server panel's Test Connection button).
    dlg.btn_test_bootnode = QPushButton(dlg)
    dlg.btn_test_bootnode.setObjectName("btnTestBootnode")
    dlg.btn_test_bootnode.clicked.connect(dlg._on_test_bootnode)

    manage_container = _action_row(dlg.btn_manage_trusted_keys, dlg.btn_test_bootnode)
    _insert_row_after(trust_container, QLabel(""), manage_container)

    # UPnP toggle for the master TCP port (only effective with a bootnode).
    dlg.p2p_upnp = ToggleSwitch(dlg)
    dlg.p2p_upnp.setObjectName("p2pUpnp")
    dlg._lbl_p2p_upnp = QLabel(dlg)
    upnp_container = switch_row(dlg.p2p_upnp, dlg._lbl_p2p_upnp, dlg)
    _insert_row_after(manage_container, QLabel(""), upnp_container)

    # NTP hosts (ADR-0023) – comma-separated SNTP servers passed to
    # hsync-client via the HSYNC_NTP_HOSTS environment variable. Dynamic,
    # no .ui counterpart; inserted right after the discovery_timeout row.
    dlg.ntp_hosts = QLineEdit(dlg)
    dlg.ntp_hosts.setObjectName("ntpHosts")
    dlg.ntp_hosts.setPlaceholderText("pool.ntp.org, time.cloudflare.com, time.google.com")
    dlg._lbl_ntp_hosts = QLabel(dlg)
    disc_container = dlg.discovery_timeout.parent()
    if isinstance(disc_container, QWidget):
        disc_layout = disc_container.layout()
        if isinstance(disc_layout, QFormLayout):
            for row in range(disc_layout.rowCount()):
                item = disc_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() is dlg.discovery_timeout:
                    disc_layout.insertRow(row + 1, dlg._lbl_ntp_hosts, dlg.ntp_hosts)
                    break

    dlg.prefer_master, dlg._lbl_prefer_master = _replace_checkbox_with_toggle(dlg, "preferMaster")

    # Never Master toggle (dynamic, no .ui counterpart) – mutually
    # exclusive with Prefer Master. Inserted right after the prefer_master row.
    dlg.never_master = ToggleSwitch(dlg)
    dlg.never_master.setObjectName("neverMaster")
    dlg._lbl_never_master = QLabel(dlg)
    cont_never_master = switch_row(dlg.never_master, dlg._lbl_never_master, dlg)
    fm_container = dlg.prefer_master.parent()
    if isinstance(fm_container, QWidget):
        fm_parent = fm_container.parent()
        fm_layout = fm_parent.layout() if isinstance(fm_parent, QWidget) else None
        if isinstance(fm_layout, QFormLayout):
            for row in range(fm_layout.rowCount()):
                item = fm_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() is fm_container:
                    fm_layout.insertRow(row + 1, "", cont_never_master)
                    break

    # Require Pairing toggle (dynamic, no .ui counterpart) – strict TOFU:
    # refuse a first-seen master certificate until confirmed out of band.
    # Inserted right after the never_master row.
    dlg.require_pairing = ToggleSwitch(dlg)
    dlg.require_pairing.setObjectName("requirePairing")
    dlg._lbl_require_pairing = QLabel(dlg)
    cont_require_pairing = switch_row(dlg.require_pairing, dlg._lbl_require_pairing, dlg)
    nm_container = cont_never_master.parent()
    if isinstance(nm_container, QWidget):
        nm_layout = nm_container.layout()
        if isinstance(nm_layout, QFormLayout):
            for row in range(nm_layout.rowCount()):
                item = nm_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() is cont_never_master:
                    nm_layout.insertRow(row + 1, "", cont_require_pairing)
                    break

    # Peer download (p2p only): download file blocks from other devices, not
    # only the primary. The caps are env-only (HSYNC_P2P_PEER_READ_CAP,
    # HSYNC_P2P_PEER_SOURCES_MAX); the on/off is --no-peer-download.
    dlg.peer_download = ToggleSwitch(dlg)
    dlg.peer_download.setObjectName("peerDownload")
    dlg._lbl_peer_download = QLabel(dlg)
    cont_peer = switch_row(dlg.peer_download, dlg._lbl_peer_download, dlg)
    dlg.peer_read_cap = QSpinBox(dlg)
    dlg.peer_read_cap.setObjectName("peerReadCap")
    dlg.peer_read_cap.setRange(1, 32)
    dlg._lbl_peer_read_cap = QLabel(dlg)
    dlg.peer_sources_max = QSpinBox(dlg)
    dlg.peer_sources_max.setObjectName("peerSourcesMax")
    dlg.peer_sources_max.setRange(1, 8)
    dlg._lbl_peer_sources_max = QLabel(dlg)

    # Reorganize p2p tab into grouped sections
    dlg._reorganize_p2p_tab()


def build_advanced_tab(dlg: SettingsDialog) -> None:
    """Build the Advanced-tab widgets (engine tuning + logging)."""

    dlg.autotune, dlg._lbl_autotune = _replace_checkbox_with_toggle(dlg, "autotuneEnabled")
    dlg.delta_enabled, dlg._lbl_delta_enabled = _replace_checkbox_with_toggle(dlg, "deltaEnabled")
    dlg.mass_delete_guard, dlg._lbl_mass_delete_guard = _replace_checkbox_with_toggle(
        dlg, "massDeleteGuard"
    )

    dlg.verbose, dlg._lbl_verbose = _replace_checkbox_with_toggle(dlg, "verbose")
    # NOTE: Quiet mode is hidden because hsync-desktop depends on parsing
    # stdout for status updates, file transfers, auth errors, etc.
    dlg.quiet, dlg._lbl_quiet = _replace_checkbox_with_toggle(dlg, "quiet")
    dlg.quiet.hide()
    dlg._lbl_quiet.hide()
    # Hide the parent container if it exists
    parent = dlg.quiet.parent()
    if isinstance(parent, QWidget):
        parent.hide()
    dlg.logfile = dlg.findChild(QLineEdit, "logfile")

    dlg.max_concurrent_transfers = QSpinBox()
    dlg.max_concurrent_transfers.setObjectName("maxConcurrentTransfers")
    dlg.max_concurrent_transfers.setRange(0, 20)
    dlg.max_concurrent_transfers.setSpecialValueText(tr("settings.auto"))

    dlg.delta_min_file_size = QSpinBox()
    dlg.delta_min_file_size.setObjectName("deltaMinFileSize")
    dlg.delta_min_file_size.setRange(0, 10_000_000)
    dlg.delta_min_file_size.setSuffix(" KB")

    dlg.delta_min_file_size_p2p = QSpinBox()
    dlg.delta_min_file_size_p2p.setObjectName("deltaMinFileSizeP2p")
    dlg.delta_min_file_size_p2p.setRange(0, 10_000_000)
    dlg.delta_min_file_size_p2p.setSuffix(" KB")

    dlg.mass_delete_threshold = QSpinBox()
    dlg.mass_delete_threshold.setObjectName("massDeleteThreshold")
    dlg.mass_delete_threshold.setRange(0, 1_000_000)
    dlg.mass_delete_threshold.setSpecialValueText(tr("settings.disabled"))

    dlg.mass_delete_percent = QSpinBox()
    dlg.mass_delete_percent.setObjectName("massDeletePercent")
    dlg.mass_delete_percent.setRange(0, 100)
    dlg.mass_delete_percent.setSuffix(" %")
    dlg.mass_delete_percent.setSpecialValueText(tr("settings.disabled"))

    dlg.bandwidth_upload = QDoubleSpinBox()
    dlg.bandwidth_upload.setObjectName("bandwidthUpload")
    dlg.bandwidth_upload.setRange(0.0, BANDWIDTH_MAX_MBPS)
    dlg.bandwidth_upload.setDecimals(2)
    dlg.bandwidth_upload.setSuffix(" MB/s")
    dlg.bandwidth_upload.setSpecialValueText(tr("settings.unlimited"))

    dlg.bandwidth_download = QDoubleSpinBox()
    dlg.bandwidth_download.setObjectName("bandwidthDownload")
    dlg.bandwidth_download.setRange(0.0, BANDWIDTH_MAX_MBPS)
    dlg.bandwidth_download.setDecimals(2)
    dlg.bandwidth_download.setSuffix(" MB/s")
    dlg.bandwidth_download.setSpecialValueText(tr("settings.unlimited"))

    dlg._reorganize_advanced_tab()


def build_general_tab(dlg: SettingsDialog) -> None:
    """Build the General-tab widgets (interface + startup)."""

    dlg.theme_combo = dlg.findChild(QComboBox, "themeCombo")
    dlg.lang_combo = dlg.findChild(QComboBox, "langCombo")
    # Theme items: Light (0) and Dark (1) keep their indices; append "System
    # default" (2) with stable item data.
    dlg.theme_combo.setItemData(0, THEME_LIGHT)
    dlg.theme_combo.setItemData(1, THEME_DARK)
    dlg.theme_combo.addItem("", THEME_SYSTEM)
    dlg.notifications_enabled, dlg._lbl_notifications = _replace_checkbox_with_toggle(
        dlg, "notificationsEnabled"
    )
    dlg.tooltips_enabled, dlg._lbl_tooltips = _replace_checkbox_with_toggle(dlg, "tooltipsEnabled")
    dlg.show_log_panel, dlg._lbl_show_log_panel = _replace_checkbox_with_toggle(dlg, "showLogPanel")
    dlg.start_at_login, dlg._lbl_start_at_login = _replace_checkbox_with_toggle(dlg, "startAtLogin")

    # "Notifications for": one row per category, in the same shape as every
    # other switch (``switch_row``) and hosted in a frame-less container placed
    # in the field column — a QGroupBox was laid out as a spanning row, which
    # left its toggles ~117 px left of the form's own switches.
    dlg.notification_group = QWidget(dlg)
    notification_lines = QVBoxLayout(dlg.notification_group)
    notification_lines.setContentsMargins(0, 0, 0, 0)
    notification_lines.setSpacing(6)
    dlg._lbl_notifications_categories = muted_label(tr("settings.notifications_categories"))
    notification_lines.addWidget(dlg._lbl_notifications_categories)
    dlg.notification_toggles = {}
    for category in NOTIFICATION_CATEGORIES:
        toggle = ToggleSwitch(dlg.notification_group)
        label = QLabel(dlg.notification_group)
        notification_lines.addWidget(switch_row(toggle, label, dlg.notification_group))
        dlg.notification_toggles[category] = (toggle, label)
    dlg.notification_group.setEnabled(dlg.notifications_enabled.isChecked())
    dlg.notifications_enabled.toggled.connect(dlg.notification_group.setEnabled)

    dlg.font_scale_combo = QComboBox(dlg)
    dlg.font_scale_combo.setObjectName("fontScaleCombo")
    dlg.font_scale_combo.addItem("", FONT_SCALE_STANDARD)
    dlg.font_scale_combo.addItem("", FONT_SCALE_COMPACT)
    dlg._lbl_font_scale = QLabel(dlg)

    # "Show advanced options" toggle (no .ui counterpart): hides the Advanced tab
    # and the advanced sections in the Sync/p2p/Server tabs.
    dlg.show_advanced = ToggleSwitch(dlg)
    dlg.show_advanced.setObjectName("showAdvanced")
    dlg._lbl_show_advanced = QLabel(dlg)
    cont_show_advanced = switch_row(dlg.show_advanced, dlg._lbl_show_advanced, dlg)
    # The page is rebuilt into grouped sections (``tab_layout.py::
    # reorganize_general_tab``): this builder only creates the widgets.
    dlg._cont_show_advanced = cont_show_advanced
    dlg._reorganize_general_tab()


def set_tab_icons(dlg: SettingsDialog) -> None:
    """Set the tab icons programmatically (theme icons are not portable)."""

    # Set tab icons programmatically (theme icons don't work cross-platform)
    dlg._tabs.setTabIcon(_SYNC_TAB_INDEX, icon("emblem-synchronizing"))
    dlg._tabs.setTabIcon(_P2P_TAB_INDEX, icon("network-p2p"))
    dlg._tabs.setTabIcon(_SERVER_TAB_INDEX, icon("network-cloud"))
    dlg._tabs.setTabIcon(_GENERAL_TAB_INDEX, icon("preferences-system"))
    dlg._tabs.setTabIcon(_ADVANCED_TAB_INDEX, icon("preferences-other"))


def setup_language_combo(dlg: SettingsDialog) -> None:
    """Populate the language combo: the automatic entry, then the endonyms."""

    # Setup language combo with proper data. The first entry follows the system
    # locale (the default); the rest are the language endonyms, never translated.
    dlg.lang_combo.clear()
    dlg.lang_combo.addItem(tr("settings.language_system"), AUTO_LANGUAGE)
    for code, name in SUPPORTED_LANGUAGES.items():
        dlg.lang_combo.addItem(name, code)


_SCREEN_SIZE_FRACTION = 0.9


def _available_screen_size(dlg: SettingsDialog) -> QSize | None:
    """The dialog screen's usable size, or ``None`` when the platform reports none."""

    screen = dlg.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        return None
    geometry = screen.availableGeometry()
    if geometry.width() <= 0 or geometry.height() <= 0:
        return None
    return geometry.size()


# Scroll frame + vertical bar + page/dialog margins: the content width must
# leave room for them or the no-horizontal-scroll pages clip the last control.
_CONTENT_WIDTH_MARGIN = 40


def _content_width(dlg: SettingsDialog) -> int:
    """Widest tab content plus the scroll chrome, or 0 when not measurable."""
    widest = 0
    for index in range(dlg._tabs.count()):
        page = dlg._tabs.widget(index)
        if page is None:
            continue
        layout = page.layout()
        if layout is not None:
            layout.activate()
        scroll = page.findChild(QScrollArea)
        content = scroll.widget() if scroll is not None else None
        if content is None:
            continue
        widest = max(widest, content.sizeHint().width())
    return widest + _CONTENT_WIDTH_MARGIN if widest else 0


def finalize_size(dlg: SettingsDialog, *, allow_shrink: bool = True) -> None:
    """Fit the dialog to its content, clamped to the screen so it stays usable.

    Each tab page scrolls (see ``tab_layout``), so a tall page no longer forces a
    tall, fixed window: the dialog is resizable and never larger than the screen.
    Pass ``allow_shrink=False`` when re-fitting after a change (the advanced
    toggle) so a size the user chose is never reduced or de-maximized.
    """

    hint = dlg.sizeHint()
    content_width = _content_width(dlg)
    available = _available_screen_size(dlg)
    if available is None:
        width = max(hint.width(), 640, content_width)
        height = hint.height()
    else:
        width = max(640, hint.width(), content_width)
        width = min(width, int(available.width() * _SCREEN_SIZE_FRACTION))
        height = min(hint.height(), int(available.height() * _SCREEN_SIZE_FRACTION))
    dlg.setMinimumWidth(width)
    dlg.setMinimumHeight(min(480, height))
    # Never disturb a maximized window; when re-fitting, never shrink a size the
    # user chose (only grow a too-small dialog) and skip no-op resizes.
    if dlg.isMaximized():
        return
    if not allow_shrink and dlg.width() >= width and dlg.height() >= height:
        return
    if dlg.width() == width and dlg.height() == height:
        return
    dlg.resize(width, height)


def fit_current_tab(dlg: SettingsDialog) -> None:
    """Grow the dialog for the current tab when its content fits on screen.

    The scroll area shows its vertical bar as soon as the client area is a few
    pixels shorter than the page (wrapped description, frame). Re-measure after
    the layout settles and grow once, bounded by the same screen fraction as
    ``finalize_size``. Never shrink or disturb a maximized window.
    """
    if not dlg.isVisible() or dlg.isMaximized():
        return
    page = dlg._tabs.currentWidget()
    scroll = page.findChild(QScrollArea) if page is not None else None
    content = scroll.widget() if scroll is not None else None
    if scroll is None or content is None:
        return
    layout = dlg.layout()
    if layout is not None:
        layout.activate()
    available = _available_screen_size(dlg)
    limit_w = int(available.width() * _SCREEN_SIZE_FRACTION) if available is not None else None
    limit_h = int(available.height() * _SCREEN_SIZE_FRACTION) if available is not None else None

    # Width first: a wider viewport can change the wrapped height.
    needed_w = content.sizeHint().width() + _CONTENT_WIDTH_MARGIN
    target_w = min(needed_w, limit_w) if limit_w is not None else needed_w
    if target_w > dlg.width():
        dlg.resize(target_w, dlg.height())
    dlg.setMinimumWidth(max(dlg.minimumWidth(), target_w))
    if layout is not None:
        layout.activate()

    overflow = scroll.verticalScrollBar().maximum()
    if overflow <= 0:
        return
    frame = max(0, dlg.frameGeometry().height() - dlg.geometry().height())
    target_h = dlg.height() + overflow + frame + 4
    if limit_h is not None:
        target_h = min(target_h, limit_h)
    if target_h > dlg.height():
        dlg.resize(dlg.width(), target_h)
