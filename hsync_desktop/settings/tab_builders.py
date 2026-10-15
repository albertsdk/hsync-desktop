# mypy: disable-error-code="attr-defined"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Widget builders for the SettingsDialog tabs.

Split out of ``SettingsDialog._load_ui`` (which only orchestrates them); each
builder operates on the dialog instance and sets its widget attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import SUPPORTED_LANGUAGES, tr
from hsync_desktop.icons import icon
from hsync_desktop.settings.form_helpers import (
    _action_row,
    _insert_row_after,
    _replace_checkbox_with_toggle,
)
from hsync_desktop.settings.tab_indices import _SERVER_TAB_INDEX, _SYNC_TAB_INDEX
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
    dlg.min_free_disk_space.setRange(0, 100_000)
    dlg.min_free_disk_space.setSuffix(" MB")
    dlg.min_free_disk_space.setSpecialValueText(tr("settings.disabled"))
    dlg.max_inbound_size = QSpinBox()
    dlg.max_inbound_size.setObjectName("maxInboundSize")
    dlg.max_inbound_size.setRange(0, 10_000_000)
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

    # Reorganize sync tab into grouped sections
    dlg._reorganize_sync_tab()


def build_server_tab(dlg: SettingsDialog) -> None:
    """Build the Server Mode-tab widgets, its banner and action row."""

    # Connection tab widgets (now second tab, index 1 — "Server Mode")
    dlg.server_url = dlg.findChild(QLineEdit, "serverUrl")
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
    upnp_container = QWidget(dlg)
    hl_upnp = QHBoxLayout(upnp_container)
    hl_upnp.setContentsMargins(0, 0, 0, 0)
    hl_upnp.addWidget(dlg.p2p_upnp)
    hl_upnp.addWidget(dlg._lbl_p2p_upnp)
    hl_upnp.addStretch()
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

    dlg.force_master, dlg._lbl_force_master = _replace_checkbox_with_toggle(dlg, "forceMaster")

    # Never Master toggle (dynamic, no .ui counterpart) – mutually
    # exclusive with Force Master. Inserted right after the force_master row.
    dlg.never_master = ToggleSwitch(dlg)
    dlg.never_master.setObjectName("neverMaster")
    dlg._lbl_never_master = QLabel(dlg)
    cont_never_master = QWidget(dlg)
    hl_never_master = QHBoxLayout(cont_never_master)
    hl_never_master.setContentsMargins(0, 0, 0, 0)
    hl_never_master.addWidget(dlg.never_master)
    hl_never_master.addWidget(dlg._lbl_never_master)
    hl_never_master.addStretch()
    fm_container = dlg.force_master.parent()
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
    cont_require_pairing = QWidget(dlg)
    hl_require_pairing = QHBoxLayout(cont_require_pairing)
    hl_require_pairing.setContentsMargins(0, 0, 0, 0)
    hl_require_pairing.addWidget(dlg.require_pairing)
    hl_require_pairing.addWidget(dlg._lbl_require_pairing)
    hl_require_pairing.addStretch()
    nm_container = cont_never_master.parent()
    if isinstance(nm_container, QWidget):
        nm_layout = nm_container.layout()
        if isinstance(nm_layout, QFormLayout):
            for row in range(nm_layout.rowCount()):
                item = nm_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() is cont_never_master:
                    nm_layout.insertRow(row + 1, "", cont_require_pairing)
                    break

    # Reorganize p2p tab into grouped sections
    dlg._reorganize_p2p_tab()


def build_log_tab(dlg: SettingsDialog) -> None:
    """Build the Log-tab widgets (Quiet mode is hidden)."""

    # Log tab widgets
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
    dlg.show_log_panel, dlg._lbl_show_log_panel = _replace_checkbox_with_toggle(dlg, "showLogPanel")


def build_appearance_tab(dlg: SettingsDialog) -> None:
    """Build the Appearance-tab widgets."""

    # Appearance tab widgets
    dlg.theme_combo = dlg.findChild(QComboBox, "themeCombo")
    dlg.lang_combo = dlg.findChild(QComboBox, "langCombo")
    dlg.notifications_enabled, dlg._lbl_notifications = _replace_checkbox_with_toggle(
        dlg, "notificationsEnabled"
    )
    dlg.tooltips_enabled, dlg._lbl_tooltips = _replace_checkbox_with_toggle(dlg, "tooltipsEnabled")


def set_tab_icons(dlg: SettingsDialog) -> None:
    """Set the tab icons programmatically (theme icons are not portable)."""

    # Set tab icons programmatically (theme icons don't work cross-platform)
    dlg._tabs.setTabIcon(0, icon("emblem-synchronizing"))  # Sync (first)
    dlg._tabs.setTabIcon(1, icon("network-p2p"))  # p2p Mode (second)
    dlg._tabs.setTabIcon(2, icon("network-cloud"))  # Server Mode (third)
    dlg._tabs.setTabIcon(3, icon("utilities-log-viewer"))
    dlg._tabs.setTabIcon(4, icon("preferences-desktop-theme"))


def setup_language_combo(dlg: SettingsDialog) -> None:
    """Populate the language combo with the supported languages."""

    # Setup language combo with proper data
    dlg.lang_combo.clear()
    for code, name in SUPPORTED_LANGUAGES.items():
        dlg.lang_combo.addItem(name, code)


def finalize_size(dlg: SettingsDialog) -> None:
    """Auto-size the dialog to fit all content after translation."""

    # Auto-size to fit all content (especially the grouped Sync tab)
    dlg.setMinimumSize(0, 0)  # Override .ui minimumSize
    dlg.setMinimumWidth(640)  # Keep a reasonable minimum width
    dlg.adjustSize()  # Resize to sizeHint
    hint = dlg.sizeHint()
    dlg.setFixedSize(max(hint.width(), 640), hint.height())
