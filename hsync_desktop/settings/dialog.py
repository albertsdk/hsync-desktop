# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Dialog classes for HSYNC Desktop settings.

Contains SettingsDialog, ApiKeyDialog, and P2PKeyDialog.
"""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import cast

from hsync_common.constants import HSYNCIGNORE_FILENAME
from hsync_common.endpoint import (
    build_https_url,
    format_authority,
    parse_host_port,
    parse_https_url,
)
from hsync_common.protocol.capabilities import supports_cli_option, supports_subcommand
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.config import (
    DEFAULT_AUTO_SYNC,
    DEFAULT_BUCKET,
    DEFAULT_CA_CERT,
    DEFAULT_COMPRESSION_ENABLED,
    DEFAULT_CONTINUOUS,
    DEFAULT_DISCOVERY_TIMEOUT,
    DEFAULT_DRY_RUN,
    DEFAULT_FILTER_PATH,
    DEFAULT_FORCE_MASTER,
    DEFAULT_GROUP,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_IGNORE_DELETE,
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_INSECURE,
    DEFAULT_LOGFILE,
    DEFAULT_MAX_INBOUND_SIZE,
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_FREE_DISK_SPACE,
    DEFAULT_NEVER_MASTER,
    DEFAULT_NO_COMPRESSION,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_NTP_HOSTS,
    DEFAULT_P2P_BOOTNODE,
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_P2P_ENABLED,
    DEFAULT_P2P_KEY,
    DEFAULT_P2P_PORT,
    DEFAULT_P2P_REQUIRE_PAIRING,
    DEFAULT_P2P_UPNP_ENABLED,
    DEFAULT_QUIET,
    DEFAULT_RESYNC_INTERVAL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SERVER_TRUST,
    DEFAULT_SHOW_LOG_PANEL,
    DEFAULT_STABILITY_DELAY,
    DEFAULT_SYNC_DIRECTION,
    DEFAULT_TOOLTIPS,
    DEFAULT_VERBOSE,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.crypto import decrypt_value, encrypt_value
from hsync_desktop.engine import get_binary_capabilities_cached
from hsync_desktop.i18n import (
    SUPPORTED_LANGUAGES,
    get_language,
    set_language,
    tr,
)
from hsync_desktop.icons import icon
from hsync_desktop.settings.cli_args import secure_config_file
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT, detect_system_theme
from hsync_desktop.trusted_keys import TrustedKeysDialog
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.toggle_switch import ToggleSwitch

# The client's server-mode default port (mirrors hsync_client.constants).
_SERVER_DEFAULT_PORT = 9753


def _maybe_tip(widget: QWidget, key: str, enabled: bool) -> None:
    """Set tooltip on *widget* from i18n *key* only when *enabled*."""
    widget.setToolTip(tr(key) if enabled else "")


def _insert_row_after(anchor: QWidget, label: QWidget, field: QWidget) -> bool:
    """Insert a QFormLayout row right after the row holding ``anchor``."""
    container = anchor.parent()
    layout = container.layout() if isinstance(container, QWidget) else None
    if not isinstance(layout, QFormLayout):
        return False
    for row in range(layout.rowCount()):
        item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
        if item and item.widget() is anchor:
            layout.insertRow(row + 1, label, field)
            return True
    return False


def _replace_checkbox_with_toggle(
    parent: QWidget, checkbox_name: str
) -> tuple[ToggleSwitch, QLabel]:
    """Replace a QCheckBox with a ToggleSwitch in a QFormLayout.

    Finds the checkbox by name, creates a ToggleSwitch with the same text,
    and replaces it in the parent layout.

    Args:
        parent: The parent widget containing the checkbox.
        checkbox_name: The object name of the checkbox to replace.

    Returns:
        A tuple of (ToggleSwitch, QLabel) for the new widgets.
    """
    checkbox: QCheckBox | None = parent.findChild(QCheckBox, checkbox_name)  # type: ignore[assignment]
    if checkbox is None:
        # Fallback: return a new toggle switch with empty label
        return ToggleSwitch(parent), QLabel(parent)

    # Get the checkbox text for the label
    text = checkbox.text()

    # Find the parent layout
    parent_layout = checkbox.parentWidget()
    if parent_layout is None:
        checkbox.deleteLater()
        return ToggleSwitch(parent), QLabel(parent)

    # Find the form layout containing this checkbox
    layout = parent_layout.layout()
    if isinstance(layout, QFormLayout):
        # Find the row containing the checkbox
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() == checkbox:
                # Create toggle switch with label
                toggle = ToggleSwitch(parent)
                label = QLabel(text, parent)
                # Create a horizontal layout with toggle + label (switch on left)
                h_layout = QHBoxLayout()
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.addWidget(toggle)
                h_layout.addWidget(label)
                h_layout.addStretch()
                # Create container widget
                container = QWidget(parent)
                container.setLayout(h_layout)
                # Replace in form layout
                layout.removeRow(row)
                layout.insertRow(row, "", container)
                return toggle, label

    # Fallback: just delete and return new toggle
    checkbox.deleteLater()
    return ToggleSwitch(parent), QLabel(parent)


class SettingsDialog(QDialog):
    """Modal settings dialog with tabbed sections."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Controls gated off by the binary's capabilities; never re-enabled
        # by the p2p-mode or connection-active state machines.
        self._unsupported_widgets: set[QWidget] = set()
        self._unsupported_labels: set[QLabel] = set()

        self._load_ui()
        self.load()  # Load saved values BEFORE connecting signals
        self._connect_signals()  # Connect signals AFTER loading to avoid spurious events
        self._apply_capabilities()  # Gate controls the binary does not support

    # ── UI loading from .ui file ─────────────────────────────────────────

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("settings_dialog", self)

        # Get widget references from .ui file
        self._tabs: QTabWidget = self.findChild(QTabWidget, "tabWidget")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

        # Create info banner for when connection is active (hidden by default)
        self._connection_banner = QFrame(self)
        self._connection_banner.setObjectName("connectionBanner")
        self._connection_banner.setStyleSheet(
            "QFrame#connectionBanner { "
            "background-color: #fff3cd; "
            "border: 1px solid #ffc107; "
            "border-radius: 4px; "
            "padding: 8px; "
            "}"
        )
        banner_layout = QHBoxLayout(self._connection_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self._banner_icon = QLabel("⚠️")
        self._banner_text = QLabel()
        self._banner_text.setWordWrap(True)
        self._banner_text.setStyleSheet("color: #856404;")
        banner_layout.addWidget(self._banner_icon)
        banner_layout.addWidget(self._banner_text, 1)
        self._connection_banner.hide()

        # Insert banner at the top of the main layout
        main_layout: QVBoxLayout = self.findChild(QVBoxLayout, "mainLayout")  # type: ignore[assignment]
        if main_layout:
            main_layout.insertWidget(0, self._connection_banner)

        # Sync tab widgets (now first tab, index 0)
        self.shared_path: QLineEdit = self.findChild(QLineEdit, "sharedPath")  # type: ignore[assignment]
        self.btn_browse_shared: QToolButton = self.findChild(QToolButton, "btnBrowseShared")  # type: ignore[assignment]
        self.bucket: QLineEdit = self.findChild(QLineEdit, "bucket")  # type: ignore[assignment]
        self.continuous, self._lbl_continuous = _replace_checkbox_with_toggle(self, "continuous")
        self.ignore_delete, self._lbl_ignore_delete = _replace_checkbox_with_toggle(
            self, "ignoreDelete"
        )

        # Sync direction combo – inject BEFORE ignore_delete row (so direction comes first)
        self.sync_direction_combo = QComboBox(self)
        self.sync_direction_combo.addItem("", "bidirectional")
        self.sync_direction_combo.addItem("", "upload-only")
        self.sync_direction_combo.addItem("", "download-only")
        self._lbl_sync_direction = QLabel(self)
        # Find the Sync tab form layout and inject before ignore_delete row
        sync_tab = self._tabs.widget(0)  # Sync is the first tab (index 0)
        if sync_tab:
            for child in sync_tab.findChildren(QFormLayout):
                form: QFormLayout = child
                # Find the ignore_delete row and insert before it
                for row in range(form.rowCount()):
                    item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    if item and item.widget() and item.widget() is self.ignore_delete.parent():
                        form.insertRow(row, self._lbl_sync_direction, self.sync_direction_combo)
                        break
                break

        # Connection tab widgets (now second tab, index 1 — "Server Mode")
        self.server_url: QLineEdit = self.findChild(QLineEdit, "serverUrl")  # type: ignore[assignment]
        self.api_key: QLineEdit = self.findChild(QLineEdit, "apiKey")  # type: ignore[assignment]
        self.insecure, self._lbl_insecure = _replace_checkbox_with_toggle(self, "insecure")
        self.ca_cert: QLineEdit = self.findChild(QLineEdit, "caCert")  # type: ignore[assignment]
        self.http_timeout: QSpinBox = self.findChild(QSpinBox, "httpTimeout")  # type: ignore[assignment]

        # Server TLS trust policy combo (ADR-0036), inserted after http_timeout.
        self.server_trust = QComboBox(self)
        self.server_trust.setObjectName("serverTrust")
        self._lbl_server_trust = QLabel(self)

        self.resync: QSpinBox = self.findChild(QSpinBox, "resync")  # type: ignore[assignment]
        self.retry_delay: QSpinBox = self.findChild(QSpinBox, "retryDelay")  # type: ignore[assignment]
        self.stability_delay: QSpinBox = self.findChild(QSpinBox, "stabilityDelay")  # type: ignore[assignment]
        self.max_wait: QSpinBox = self.findChild(QSpinBox, "maxWait")  # type: ignore[assignment]
        self.filter_path: QLineEdit = self.findChild(QLineEdit, "filterPath")  # type: ignore[assignment]
        self.min_free_disk_space = QSpinBox()
        self.min_free_disk_space.setObjectName("minFreeDiskSpace")
        self.min_free_disk_space.setRange(0, 100_000)
        self.min_free_disk_space.setSuffix(" MB")
        self.min_free_disk_space.setSpecialValueText(tr("settings.disabled"))
        self.max_inbound_size = QSpinBox()
        self.max_inbound_size.setObjectName("maxInboundSize")
        self.max_inbound_size.setRange(0, 10_000_000)
        self.max_inbound_size.setSuffix(" MB")
        self.max_inbound_size.setSpecialValueText(tr("settings.disabled"))
        self.compression_enabled, self._lbl_compression_enabled = _replace_checkbox_with_toggle(
            self, "noCompression"
        )
        self.dry_run, self._lbl_dry_run = _replace_checkbox_with_toggle(self, "dryRun")
        self.auto_sync, self._lbl_auto_sync = _replace_checkbox_with_toggle(self, "autoSync")

        # Hidden-file / .hsyncignore controls (dynamic, no .ui counterpart)
        self.ignore_patterns = QLineEdit(self)
        self.ignore_patterns.setObjectName("ignorePatterns")
        self.ignore_patterns.setPlaceholderText("*.log, /build/, /dist/")
        self._lbl_ignore_patterns = QLabel(self)
        self.btn_edit_hsyncignore = QPushButton(self)
        self.btn_edit_hsyncignore.setObjectName("btnEditHsyncignore")

        # Reorganize sync tab into grouped sections
        self._reorganize_sync_tab()

        # p2p tab widgets
        self.p2p_mode, self._lbl_p2p_mode = _replace_checkbox_with_toggle(self, "p2pMode")
        self.p2p_group: QLineEdit = self.findChild(QLineEdit, "p2pGroup")  # type: ignore[assignment]
        self.p2p_key: QLineEdit = self.findChild(QLineEdit, "p2pKey")  # type: ignore[assignment]
        self.p2p_port: QSpinBox = self.findChild(QSpinBox, "p2pPort")  # type: ignore[assignment]
        self.discovery_timeout: QSpinBox = self.findChild(QSpinBox, "discoveryTimeout")  # type: ignore[assignment]

        # Bootnode (optional) – cross-network discovery through a boot/1 node.
        # Dynamic, no .ui counterpart; inserted right after the group row.
        self.p2p_bootnode = QLineEdit(self)
        self.p2p_bootnode.setObjectName("p2pBootnode")
        self.p2p_bootnode.setPlaceholderText("boot.example.net")
        self._lbl_p2p_bootnode = QLabel(self)
        _insert_row_after(self.p2p_group, self._lbl_p2p_bootnode, self.p2p_bootnode)

        # Trust policy (ADR-0035): how the client authenticates the bootnode.
        self.p2p_bootnode_trust = QComboBox(self)
        self.p2p_bootnode_trust.setObjectName("p2pBootnodeTrust")
        self._lbl_p2p_bootnode_trust = QLabel(self)
        trust_container = QWidget(self)
        hl_trust = QHBoxLayout(trust_container)
        hl_trust.setContentsMargins(0, 0, 0, 0)
        hl_trust.addWidget(self.p2p_bootnode_trust)
        hl_trust.addWidget(self._lbl_p2p_bootnode_trust)
        hl_trust.addStretch()
        self._populate_bootnode_trust()
        _insert_row_after(self.p2p_bootnode, QLabel(""), trust_container)

        # Manage trusted keys (ADR-0035): opens the known-hosts / known-peers
        # dialog that edits the shared stores via the hsync CLI.
        self.btn_manage_trusted_keys = QPushButton(self)
        self.btn_manage_trusted_keys.setObjectName("btnManageTrustedKeys")
        self.btn_manage_trusted_keys.clicked.connect(self._open_trusted_keys)
        manage_container = QWidget(self)
        hl_manage = QHBoxLayout(manage_container)
        hl_manage.setContentsMargins(0, 0, 0, 0)
        hl_manage.addWidget(self.btn_manage_trusted_keys)
        hl_manage.addStretch()
        _insert_row_after(trust_container, QLabel(""), manage_container)

        # UPnP toggle for the master TCP port (only effective with a bootnode).
        self.p2p_upnp = ToggleSwitch(self)
        self.p2p_upnp.setObjectName("p2pUpnp")
        self._lbl_p2p_upnp = QLabel(self)
        upnp_container = QWidget(self)
        hl_upnp = QHBoxLayout(upnp_container)
        hl_upnp.setContentsMargins(0, 0, 0, 0)
        hl_upnp.addWidget(self.p2p_upnp)
        hl_upnp.addWidget(self._lbl_p2p_upnp)
        hl_upnp.addStretch()
        _insert_row_after(manage_container, QLabel(""), upnp_container)

        # NTP hosts (ADR-0023) – comma-separated SNTP servers passed to
        # hsync-client via the HSYNC_NTP_HOSTS environment variable. Dynamic,
        # no .ui counterpart; inserted right after the discovery_timeout row.
        self.ntp_hosts = QLineEdit(self)
        self.ntp_hosts.setObjectName("ntpHosts")
        self.ntp_hosts.setPlaceholderText("pool.ntp.org, time.cloudflare.com, time.google.com")
        self._lbl_ntp_hosts = QLabel(self)
        disc_container = self.discovery_timeout.parent()
        if isinstance(disc_container, QWidget):
            disc_layout = disc_container.layout()
            if isinstance(disc_layout, QFormLayout):
                for row in range(disc_layout.rowCount()):
                    item = disc_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    if item and item.widget() is self.discovery_timeout:
                        disc_layout.insertRow(row + 1, self._lbl_ntp_hosts, self.ntp_hosts)
                        break

        self.force_master, self._lbl_force_master = _replace_checkbox_with_toggle(
            self, "forceMaster"
        )

        # Never Master toggle (dynamic, no .ui counterpart) – mutually
        # exclusive with Force Master. Inserted right after the force_master row.
        self.never_master = ToggleSwitch(self)
        self.never_master.setObjectName("neverMaster")
        self._lbl_never_master = QLabel(self)
        cont_never_master = QWidget(self)
        hl_never_master = QHBoxLayout(cont_never_master)
        hl_never_master.setContentsMargins(0, 0, 0, 0)
        hl_never_master.addWidget(self.never_master)
        hl_never_master.addWidget(self._lbl_never_master)
        hl_never_master.addStretch()
        fm_container = self.force_master.parent()
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
        self.require_pairing = ToggleSwitch(self)
        self.require_pairing.setObjectName("requirePairing")
        self._lbl_require_pairing = QLabel(self)
        cont_require_pairing = QWidget(self)
        hl_require_pairing = QHBoxLayout(cont_require_pairing)
        hl_require_pairing.setContentsMargins(0, 0, 0, 0)
        hl_require_pairing.addWidget(self.require_pairing)
        hl_require_pairing.addWidget(self._lbl_require_pairing)
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

        # Log tab widgets
        self.verbose, self._lbl_verbose = _replace_checkbox_with_toggle(self, "verbose")
        # NOTE: Quiet mode is hidden because hsync-desktop depends on parsing
        # stdout for status updates, file transfers, auth errors, etc.
        self.quiet, self._lbl_quiet = _replace_checkbox_with_toggle(self, "quiet")
        self.quiet.hide()
        self._lbl_quiet.hide()
        # Hide the parent container if it exists
        parent = self.quiet.parent()
        if isinstance(parent, QWidget):
            parent.hide()
        self.logfile: QLineEdit = self.findChild(QLineEdit, "logfile")  # type: ignore[assignment]
        self.show_log_panel, _ = _replace_checkbox_with_toggle(self, "showLogPanel")

        # Appearance tab widgets
        self.theme_combo: QComboBox = self.findChild(QComboBox, "themeCombo")  # type: ignore[assignment]
        self.lang_combo: QComboBox = self.findChild(QComboBox, "langCombo")  # type: ignore[assignment]
        self.notifications_enabled, self._lbl_notifications = _replace_checkbox_with_toggle(
            self, "notificationsEnabled"
        )
        self.tooltips_enabled, self._lbl_tooltips = _replace_checkbox_with_toggle(
            self, "tooltipsEnabled"
        )

        # Set tab icons programmatically (theme icons don't work cross-platform)
        self._tabs.setTabIcon(0, icon("emblem-synchronizing"))  # Sync (first)
        self._tabs.setTabIcon(1, icon("network-cloud"))  # Server Mode (second)
        self._tabs.setTabIcon(2, icon("network-p2p"))
        self._tabs.setTabIcon(3, icon("utilities-log-viewer"))
        self._tabs.setTabIcon(4, icon("preferences-desktop-theme"))

        # Create info banner for Server Mode tab when p2p is active (hidden by default)
        self._p2p_banner = QFrame(self)
        self._p2p_banner.setObjectName("p2pBanner")
        self._p2p_banner.setStyleSheet(
            "QFrame#p2pBanner { "
            "background-color: #fff3cd; "
            "border: 1px solid #ffc107; "
            "border-radius: 4px; "
            "padding: 8px; "
            "}"
        )
        p2p_banner_layout = QHBoxLayout(self._p2p_banner)
        p2p_banner_layout.setContentsMargins(8, 4, 8, 4)
        self._p2p_banner_icon = QLabel("⚠️")
        self._p2p_banner_text = QLabel()
        self._p2p_banner_text.setWordWrap(True)
        self._p2p_banner_text.setStyleSheet("color: #856404;")
        p2p_banner_layout.addWidget(self._p2p_banner_icon)
        p2p_banner_layout.addWidget(self._p2p_banner_text, 1)
        self._p2p_banner.hide()

        # Insert p2p banner at the top of the Server Mode (tabConnection) layout
        # Also insert server_cert_fingerprint field and Test Connection button
        self.btn_test_connection = QPushButton()
        self.btn_test_connection.setObjectName("btnTestConnection")

        conn_tab = self._tabs.widget(1)
        if conn_tab:
            conn_layout = conn_tab.layout()
            if isinstance(conn_layout, QFormLayout):
                conn_layout.insertRow(0, self._p2p_banner)
                # Insert the server trust-policy combo after the http_timeout
                # row, then the Test Connection button below it.
                for row in range(conn_layout.rowCount()):
                    item = conn_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    if item and item.widget() == self.http_timeout:
                        conn_layout.insertRow(row + 1, self._lbl_server_trust, self.server_trust)
                        conn_layout.insertRow(row + 2, "", self.btn_test_connection)
                        break

        # Setup language combo with proper data
        self.lang_combo.clear()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(name, code)

        # Apply translations
        self._apply_translations()
        self._apply_tooltips()

        # Auto-size to fit all content (especially the grouped Sync tab)
        self.setMinimumSize(0, 0)  # Override .ui minimumSize
        self.setMinimumWidth(640)  # Keep a reasonable minimum width
        self.adjustSize()  # Resize to sizeHint
        hint = self.sizeHint()
        self.setFixedSize(max(hint.width(), 640), hint.height())

    # ── Sync tab grouping ─────────────────────────────────────────

    def _populate_bootnode_trust(self) -> None:
        """Fill the bootnode trust-policy combo (ADR-0035), preserving selection."""
        current = self.p2p_bootnode_trust.currentData()
        self.p2p_bootnode_trust.clear()
        for value, key in (
            ("ask", "settings.p2p_bootnode_trust_ask"),
            ("accept-new", "settings.p2p_bootnode_trust_accept_new"),
            ("strict", "settings.p2p_bootnode_trust_strict"),
            ("none", "settings.p2p_bootnode_trust_none"),
        ):
            self.p2p_bootnode_trust.addItem(tr(key), value)
        index = self.p2p_bootnode_trust.findData(current)
        self.p2p_bootnode_trust.setCurrentIndex(index if index >= 0 else 0)

    def _open_trusted_keys(self) -> None:
        """Open the known-hosts / known-peers management dialog."""
        TrustedKeysDialog(self).exec()

    def _populate_server_trust(self) -> None:
        """Fill the server trust-policy combo (ADR-0036), preserving selection."""
        current = self.server_trust.currentData()
        self.server_trust.clear()
        for value, key in (
            ("chain", "settings.server_trust_chain"),
            ("ask", "settings.server_trust_ask"),
            ("accept-new", "settings.server_trust_accept_new"),
            ("strict", "settings.server_trust_strict"),
            ("none", "settings.server_trust_none"),
        ):
            self.server_trust.addItem(tr(key), value)
        index = self.server_trust.findData(current)
        self.server_trust.setCurrentIndex(index if index >= 0 else 0)

    def _reorganize_sync_tab(self) -> None:
        """Reorganize the Sync tab into grouped sections using QGroupBox."""
        sync_tab = self._tabs.widget(0)
        if not sync_tab:
            return

        # ── Collect label references from .ui ──────────────────
        lbl_shared: QLabel = self.findChild(QLabel, "lblSharedPath")  # type: ignore[assignment]
        lbl_bucket: QLabel = self.findChild(QLabel, "lblBucket")  # type: ignore[assignment]
        lbl_resync: QLabel = self.findChild(QLabel, "lblResync")  # type: ignore[assignment]
        lbl_retry: QLabel = self.findChild(QLabel, "lblRetryDelay")  # type: ignore[assignment]
        lbl_stability: QLabel = self.findChild(QLabel, "lblStabilityDelay")  # type: ignore[assignment]
        lbl_max_wait: QLabel = self.findChild(QLabel, "lblMaxWait")  # type: ignore[assignment]
        lbl_filter: QLabel = self.findChild(QLabel, "lblFilterPath")  # type: ignore[assignment]

        # Toggle switch containers (toggle.parent() == container QWidget)
        cont_continuous: QWidget = self.continuous.parent()  # type: ignore[assignment]
        cont_ignore: QWidget = self.ignore_delete.parent()  # type: ignore[assignment]
        cont_no_comp: QWidget = self.compression_enabled.parent()  # type: ignore[assignment]
        cont_dry_run: QWidget = self.dry_run.parent()  # type: ignore[assignment]
        cont_auto_sync: QWidget = self.auto_sync.parent()  # type: ignore[assignment]

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
        self._grp_path = QGroupBox(tr("settings.group.path_bucket"))
        f1 = QFormLayout(self._grp_path)
        path_row = QHBoxLayout()
        path_row.addWidget(self.shared_path)
        path_row.addWidget(self.btn_browse_shared)
        f1.addRow(lbl_shared, path_row)
        f1.addRow(lbl_bucket, self.bucket)
        vbox.addWidget(self._grp_path)

        # Group 2: Sync Mode
        self._grp_sync = QGroupBox(tr("settings.group.sync_mode"))
        f2 = QFormLayout(self._grp_sync)
        f2.addRow(self._lbl_sync_direction, self.sync_direction_combo)
        f2.addRow("", cont_ignore)
        f2.addRow("", cont_continuous)
        f2.addRow("", cont_auto_sync)
        vbox.addWidget(self._grp_sync)

        # Group 3: Timing & Intervals
        self._grp_timing = QGroupBox(tr("settings.group.timing"))
        f3 = QFormLayout(self._grp_timing)
        f3.addRow(lbl_resync, self.resync)
        f3.addRow(lbl_retry, self.retry_delay)
        f3.addRow(lbl_stability, self.stability_delay)
        f3.addRow(lbl_max_wait, self.max_wait)
        vbox.addWidget(self._grp_timing)

        # Group 4: Advanced Options
        self._grp_advanced = QGroupBox(tr("settings.group.advanced"))
        f4 = QFormLayout(self._grp_advanced)
        self._lbl_min_free_disk_space = QLabel(tr("settings.min_free_disk_space"))
        f4.addRow(self._lbl_min_free_disk_space, self.min_free_disk_space)
        self._lbl_max_inbound_size = QLabel(tr("settings.max_inbound_size"))
        f4.addRow(self._lbl_max_inbound_size, self.max_inbound_size)
        f4.addRow(lbl_filter, self.filter_path)
        f4.addRow("", cont_no_comp)
        f4.addRow("", cont_dry_run)

        # Extra ignore patterns
        f4.addRow(self._lbl_ignore_patterns, self.ignore_patterns)

        # Edit .hsyncignore button (no left label, like a regular action)
        f4.addRow("", self.btn_edit_hsyncignore)
        vbox.addWidget(self._grp_advanced)

        vbox.addStretch()

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self.setWindowTitle(tr("settings.title"))

        # Tab titles
        self._tabs.setTabText(0, tr("settings.sync"))
        self._tabs.setTabText(1, tr("settings.server_mode"))
        self._tabs.setTabText(2, tr("settings.p2p"))
        self._tabs.setTabText(3, tr("settings.log"))
        self._tabs.setTabText(4, tr("settings.appearance"))

        # Sync tab - shared path label
        lbl_shared: QLabel = self.findChild(QLabel, "lblSharedPath")  # type: ignore[assignment]
        if lbl_shared:
            lbl_shared.setText(tr("settings.shared_path"))

        # Server Mode tab labels
        lbl: QLabel = self.findChild(QLabel, "lblServerUrl")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.server_url"))
        lbl = self.findChild(QLabel, "lblApiKey")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.api_key"))
        self._lbl_insecure.setText(tr("settings.insecure"))
        lbl = self.findChild(QLabel, "lblCaCert")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.ca_cert"))
        lbl = self.findChild(QLabel, "lblHttpTimeout")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.http_timeout"))
        self._lbl_server_trust.setText(tr("settings.server_trust"))
        self._populate_server_trust()
        self.btn_test_connection.setText(tr("settings.test_connection"))

        # Sync tab labels
        lbl = self.findChild(QLabel, "lblBucket")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.bucket"))
        self._lbl_continuous.setText(tr("settings.watch"))
        self._lbl_ignore_delete.setText(tr("settings.ignore_delete"))
        self._lbl_sync_direction.setText(tr("settings.sync_direction"))
        self.sync_direction_combo.setItemText(0, tr("settings.sync_direction.bidirectional"))
        self.sync_direction_combo.setItemText(1, tr("settings.sync_direction.upload_only"))
        self.sync_direction_combo.setItemText(2, tr("settings.sync_direction.download_only"))
        lbl = self.findChild(QLabel, "lblResync")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.resync"))
        lbl = self.findChild(QLabel, "lblRetryDelay")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.retry_delay"))
        lbl = self.findChild(QLabel, "lblStabilityDelay")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.stability_delay"))
        lbl = self.findChild(QLabel, "lblMaxWait")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.max_wait"))
        lbl = self.findChild(QLabel, "lblFilterPath")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.filter_path"))
        self._lbl_min_free_disk_space.setText(tr("settings.min_free_disk_space"))
        self.min_free_disk_space.setSpecialValueText(tr("settings.disabled"))
        self._lbl_max_inbound_size.setText(tr("settings.max_inbound_size"))
        self.max_inbound_size.setSpecialValueText(tr("settings.disabled"))
        self._lbl_compression_enabled.setText(tr("settings.compression_enabled"))
        self._lbl_dry_run.setText(tr("settings.dry_run"))
        self._lbl_auto_sync.setText(tr("settings.auto_sync"))
        self._lbl_ignore_patterns.setText(tr("settings.ignore_patterns"))
        self.btn_edit_hsyncignore.setText(tr("settings.edit_hsyncignore"))

        # Sync tab group box titles
        self._grp_path.setTitle(tr("settings.group.path_bucket"))
        self._grp_sync.setTitle(tr("settings.group.sync_mode"))
        self._grp_timing.setTitle(tr("settings.group.timing"))
        self._grp_advanced.setTitle(tr("settings.group.advanced"))

        # p2p tab labels
        self._lbl_p2p_mode.setText(tr("settings.p2p_mode"))
        lbl = self.findChild(QLabel, "lblP2pGroup")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.p2p_group"))
        lbl = self.findChild(QLabel, "lblP2pKey")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.p2p_key"))
        lbl = self.findChild(QLabel, "lblP2pPort")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.p2p_port"))
        self._lbl_p2p_bootnode.setText(tr("settings.p2p_bootnode"))
        self._lbl_p2p_bootnode_trust.setText(tr("settings.p2p_bootnode_trust"))
        self._populate_bootnode_trust()
        self.btn_manage_trusted_keys.setText(tr("settings.manage_trusted_keys"))
        self._lbl_p2p_upnp.setText(tr("settings.p2p_upnp"))
        lbl = self.findChild(QLabel, "lblDiscoveryTimeout")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.discovery_timeout"))
        self._lbl_ntp_hosts.setText(tr("settings.ntp_hosts"))
        self._lbl_force_master.setText(tr("settings.force_master"))
        self._lbl_never_master.setText(tr("settings.never_master"))
        self._lbl_require_pairing.setText(tr("settings.require_pairing"))

        # Log tab labels
        self._lbl_verbose.setText(tr("settings.verbose"))
        self._lbl_quiet.setText(tr("settings.quiet"))
        lbl = self.findChild(QLabel, "lblLogfile")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.logfile"))

        # Appearance tab labels
        lbl = self.findChild(QLabel, "lblTheme")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.theme"))
        self.theme_combo.setItemText(0, tr("settings.theme_light"))
        self.theme_combo.setItemText(1, tr("settings.theme_dark"))
        lbl = self.findChild(QLabel, "lblLanguage")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.p2pguage"))
        self._lbl_notifications.setText(tr("settings.notifications"))
        self._lbl_tooltips.setText(tr("settings.tooltips"))

        # Button box
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(tr("settings.save"))
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(tr("settings.cancel"))

    def _apply_tooltips(self) -> None:
        """Apply tooltips to widgets if enabled."""
        tips = self._tips_enabled()

        # Sync tab
        _maybe_tip(self.shared_path, "tip.shared_path", tips)
        _maybe_tip(self.bucket, "tip.bucket", tips)
        _maybe_tip(self.continuous, "tip.watch", tips)
        _maybe_tip(self.ignore_delete, "tip.ignore_delete", tips)
        _maybe_tip(self.sync_direction_combo, "tip.sync_direction", tips)
        _maybe_tip(self.resync, "tip.resync", tips)
        _maybe_tip(self.retry_delay, "tip.retry_delay", tips)
        _maybe_tip(self.stability_delay, "tip.stability_delay", tips)
        _maybe_tip(self.max_wait, "tip.max_wait", tips)
        _maybe_tip(self.min_free_disk_space, "tip.min_free_disk_space", tips)
        _maybe_tip(self.max_inbound_size, "tip.max_inbound_size", tips)
        _maybe_tip(self.filter_path, "tip.filter_path", tips)
        _maybe_tip(self.compression_enabled, "tip.compression_enabled", tips)
        _maybe_tip(self.dry_run, "tip.dry_run", tips)
        _maybe_tip(self.auto_sync, "tip.auto_sync", tips)
        _maybe_tip(self.ignore_patterns, "tip.ignore_patterns", tips)
        _maybe_tip(self.btn_edit_hsyncignore, "tip.edit_hsyncignore", tips)

        # Server Mode tab
        _maybe_tip(self.server_url, "tip.server_url", tips)
        _maybe_tip(self.api_key, "tip.api_key", tips)
        _maybe_tip(self.insecure, "tip.insecure", tips)
        _maybe_tip(self.ca_cert, "tip.ca_cert", tips)
        _maybe_tip(self.server_trust, "tip.server_trust", tips)
        _maybe_tip(self.http_timeout, "tip.http_timeout", tips)

        # p2p tab
        _maybe_tip(self.p2p_mode, "tip.p2p_mode", tips)
        _maybe_tip(self.p2p_group, "tip.p2p_group", tips)
        _maybe_tip(self.p2p_key, "tip.p2p_key", tips)
        _maybe_tip(self.p2p_port, "tip.p2p_port", tips)
        _maybe_tip(self.discovery_timeout, "tip.discovery_timeout", tips)
        _maybe_tip(self.ntp_hosts, "tip.ntp_hosts", tips)
        _maybe_tip(self.force_master, "tip.force_master", tips)
        _maybe_tip(self.never_master, "tip.never_master", tips)
        _maybe_tip(self.require_pairing, "tip.require_pairing", tips)

        # Log tab
        _maybe_tip(self.verbose, "tip.verbose", tips)
        _maybe_tip(self.quiet, "tip.quiet", tips)
        _maybe_tip(self.logfile, "tip.logfile", tips)

        # Appearance tab
        _maybe_tip(self.lang_combo, "tip.language", tips)
        _maybe_tip(self.theme_combo, "tip.theme", tips)
        _maybe_tip(self.notifications_enabled, "tip.notifications", tips)
        _maybe_tip(self.tooltips_enabled, "tip.tooltips", tips)

        # Capability-gated controls always explain why they are unavailable,
        # overriding any normal tooltip cleared above.
        for widget in self._unsupported_widgets:
            widget.setToolTip(tr("tip.capability_unsupported"))

    def _apply_capabilities(self) -> None:
        """Gate p2p controls by the binary's advertised capabilities.

        Reads the capabilities document from the configured hsync binary and
        disables any p2p toggle the binary does not support — the ``p2p``
        subcommand gates the whole block, and each remaining toggle is gated by
        the flag the ``p2p`` subcommand advertises. The UI can never offer a
        control the client cannot honour. An unknown document (missing binary
        or parse failure) conservatively leaves every control enabled.
        """
        doc = get_binary_capabilities_cached()
        if doc is None:
            return
        p2p_supported = supports_subcommand(doc, "p2p")
        gated: list[tuple[str, ToggleSwitch, QLabel]] = [
            ("--force-master", self.force_master, self._lbl_force_master),
            ("--never-master", self.never_master, self._lbl_never_master),
            ("--require-pairing", self.require_pairing, self._lbl_require_pairing),
            ("--no-upnp", self.p2p_upnp, self._lbl_p2p_upnp),
        ]
        for flag, widget, label in gated:
            if p2p_supported and supports_cli_option(doc, flag, subcommand="p2p"):
                continue
            self._unsupported_widgets.add(widget)
            self._unsupported_labels.add(label)
            if widget.isChecked():
                widget.blockSignals(True)
                widget.setChecked(False)
                widget.blockSignals(False)
            widget.setEnabled(False)
            label.setEnabled(False)
            widget.setToolTip(tr("tip.capability_unsupported"))
        # The bootnode host field belongs to the bootnode discovery plan: gate it
        # on its ``--port`` flag (the positional is not in cli_options).
        if not (p2p_supported and supports_cli_option(doc, "--port", subcommand="p2p")):
            self._unsupported_widgets.add(self.p2p_bootnode)
            self._unsupported_labels.add(self._lbl_p2p_bootnode)
            self.p2p_bootnode.setEnabled(False)
            self._lbl_p2p_bootnode.setEnabled(False)
            self.p2p_bootnode.setToolTip(tr("tip.capability_unsupported"))
        if not p2p_supported:
            # The p2p subcommand itself is the master gate for the p2p tab.
            self._unsupported_widgets.add(self.p2p_mode)
            self._unsupported_labels.add(self._lbl_p2p_mode)
            if self.p2p_mode.isChecked():
                self.p2p_mode.blockSignals(True)
                self.p2p_mode.setChecked(False)
                self.p2p_mode.blockSignals(False)
            self.p2p_mode.setEnabled(False)
            self._lbl_p2p_mode.setEnabled(False)
            self.p2p_mode.setToolTip(tr("tip.capability_unsupported"))
        # Refresh dependent enable-state with the new gates in effect.
        self._on_p2p_mode_toggled(self.p2p_mode.isChecked())

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.ignore_delete.toggled.connect(self._on_ignore_delete_toggled)
        self.btn_browse_shared.clicked.connect(self._on_browse_shared)
        self.p2p_mode.toggled.connect(self._on_p2p_mode_toggled)
        self.force_master.toggled.connect(self._on_force_master_toggled)
        self.never_master.toggled.connect(self._on_never_master_toggled)
        self.btn_test_connection.clicked.connect(self._on_test_connection)
        self.btn_edit_hsyncignore.clicked.connect(self._on_edit_hsyncignore)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

    def _on_edit_hsyncignore(self) -> None:
        """Open the .hsyncignore editor for the currently configured shared folder."""
        shared = self.shared_path.text().strip()
        if not shared:
            QMessageBox.warning(
                self,
                tr("hsyncignore.title"),
                tr("hsyncignore.no_path_warning"),
            )
            return
        dlg = HsyncIgnoreEditorDialog(Path(shared), self)
        dlg.exec()

    def _on_ignore_delete_toggled(self, checked: bool) -> None:
        """Show a warning when the user disables ignore-delete."""
        if not checked:
            msg = QMessageBox(
                QMessageBox.Icon.Warning,
                tr("warn.ignore_delete_title"),
                tr("warn.ignore_delete_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                self,
            )
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            yes_btn = msg.button(QMessageBox.StandardButton.Yes)
            no_btn = msg.button(QMessageBox.StandardButton.No)
            if yes_btn:
                yes_btn.setText(tr("action.yes"))
            if no_btn:
                no_btn.setText(tr("action.no"))
            if msg.exec() != QMessageBox.StandardButton.Yes:
                self.ignore_delete.blockSignals(True)
                self.ignore_delete.setChecked(True)
                self.ignore_delete.blockSignals(False)

    def _on_browse_shared(self) -> None:
        """Open a folder browser to select the shared path."""
        current = self.shared_path.text() or ""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.shared_path_browse"),
            current,
        )
        if folder:
            self.shared_path.setText(folder)

    def _on_p2p_mode_toggled(self, checked: bool) -> None:
        """Enable/disable Server Mode tab widgets when p2p mode changes,
        and enable/disable p2p tab widgets based on p2p mode state."""
        # Show/hide the p2p banner on Server Mode tab
        self._p2p_banner.setVisible(checked)
        if checked:
            self._p2p_banner_text.setText(tr("settings.p2p_disables_server"))

        # Disable/enable all Server Mode tab widgets
        server_widgets: list[QWidget] = [
            self.server_url,
            self.api_key,
            self.insecure,
            self.ca_cert,
            self.http_timeout,
            self.btn_test_connection,
        ]
        for widget in server_widgets:
            widget.setEnabled(not checked)

        # Also disable the labels in the Server Mode tab
        conn_tab = self._tabs.widget(1)
        if conn_tab:
            for lbl in conn_tab.findChildren(QLabel):
                if lbl not in (self._p2p_banner_icon, self._p2p_banner_text):
                    lbl.setEnabled(not checked)

        # Enable/disable p2p tab widgets (except the p2p_mode toggle itself)
        p2p_sub_widgets: list[QWidget] = [
            self.p2p_group,
            self.p2p_bootnode,
            self.p2p_upnp,
            self.p2p_key,
            self.p2p_port,
            self.discovery_timeout,
            self.ntp_hosts,
            self.force_master,
            self.never_master,
            self.require_pairing,
        ]
        for widget in p2p_sub_widgets:
            widget.setEnabled(checked and widget not in self._unsupported_widgets)

        # Also enable/disable the labels in the p2p tab (except p2p_mode label)
        p2p_tab = self._tabs.widget(2)
        if p2p_tab:
            for lbl in p2p_tab.findChildren(QLabel):
                if lbl is not self._lbl_p2p_mode:
                    lbl.setEnabled(checked and lbl not in self._unsupported_labels)

    def _on_force_master_toggled(self, checked: bool) -> None:
        """Force-master and never-master are mutually exclusive."""
        if checked and self.never_master.isChecked():
            self.never_master.blockSignals(True)
            self.never_master.setChecked(False)
            self.never_master.blockSignals(False)

    def _on_never_master_toggled(self, checked: bool) -> None:
        """Force-master and never-master are mutually exclusive."""
        if checked and self.force_master.isChecked():
            self.force_master.blockSignals(True)
            self.force_master.setChecked(False)
            self.force_master.blockSignals(False)

    def _normalize_server_endpoint(self) -> str | None:
        """Canonicalize the server field, or raise ``ValueError``.

        Accepts the same forms as ``HSYNC_SERVER`` (bare ``host``/``host:port``/
        ``[IPv6]``/``[IPv6]:port`` or a full ``https://…`` URL) and returns the
        canonical HTTPS URL so ``_ensure_server_trust``/``urlsplit`` keep working.
        """
        raw = self.server_url.text().strip()
        if not raw:
            return None
        if raw.lower().startswith("https://"):
            return parse_https_url(raw)
        return build_https_url(parse_host_port(raw), _SERVER_DEFAULT_PORT)

    def _normalize_bootnode_endpoint(self) -> str | None:
        """Canonicalize the bootnode field, or raise ``ValueError``."""
        raw = self.p2p_bootnode.text().strip()
        if not raw:
            return None
        endpoint = parse_host_port(raw)
        if endpoint.port is None:
            return endpoint.host
        return format_authority(endpoint.host, endpoint.port)

    def _on_test_connection(self) -> None:
        """Test the server connection by calling the /health endpoint."""
        url = self.server_url.text().strip()
        if not url:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_connection_no_url"),
            )
            return

        # Validate + normalize through the shared endpoint grammar to prevent
        # SSRF via file://, localhost probes, or other unexpected schemes.
        try:
            normalized = self._normalize_server_endpoint()
            assert normalized is not None  # url was non-empty above
            base = normalized.rstrip("/")
        except ValueError:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.invalid_server_endpoint"),
            )
            return
        health_url = f"{base}/health"

        self.btn_test_connection.setEnabled(False)
        self.btn_test_connection.setText("…")

        def _restore() -> None:
            self.btn_test_connection.setEnabled(True)
            self.btn_test_connection.setText(tr("settings.test_connection"))

        try:
            timeout = max(5, self.http_timeout.value())
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(
                req, timeout=timeout, context=self._test_connection_ssl_context()
            ) as resp:
                success = resp.status == 200
        except urllib.error.HTTPError as exc:
            success = exc.code == 200
        except Exception:
            success = False

        _restore()

        if success:
            QMessageBox.information(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_connection_success"),
            )
        else:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_connection_failure"),
            )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _test_connection_ssl_context(self) -> ssl.SSLContext:
        """SSL context for the Test Connection probe, honouring TLS settings.

        The probe must agree with how the client will connect: ``--insecure`` /
        ``none`` skip verification, ``--ca-cert`` anchors it, a pinning policy
        (``ask``/``accept-new``/``strict``) trusts the fingerprint rather than the
        chain (the button cannot prompt, so it probes without chain validation —
        the real client still enforces the pin), and ``chain`` uses the default CA.
        """
        policy = self.server_trust.currentData()
        if self.insecure.isChecked() or policy == "none":
            return self._unverified_ssl_context()
        ca_cert = self.ca_cert.text().strip()
        if ca_cert and Path(ca_cert).exists():
            return ssl.create_default_context(cafile=ca_cert)
        if policy in ("ask", "accept-new", "strict"):
            return self._unverified_ssl_context()
        return ssl.create_default_context()

    @staticmethod
    def _unverified_ssl_context() -> ssl.SSLContext:
        """An SSLContext that skips chain/hostname verification (fingerprint mode)."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _tips_enabled(self) -> bool:
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        return bool(s.value("appearance/tooltips", True, bool))

    # ── Save / Load ──────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        # Validate: force-master is incompatible with directional sync
        if self.force_master.isChecked():
            direction = self.sync_direction_combo.currentData() or "bidirectional"
            if direction != "bidirectional":
                msg = QMessageBox(
                    QMessageBox.Icon.Warning,
                    tr("warn.force_master_title"),
                    tr("warn.force_master_msg"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    self,
                )
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)
                yes_btn = msg.button(QMessageBox.StandardButton.Yes)
                no_btn = msg.button(QMessageBox.StandardButton.No)
                if yes_btn:
                    yes_btn.setText(tr("action.yes"))
                if no_btn:
                    no_btn.setText(tr("action.no"))
                if msg.exec() == QMessageBox.StandardButton.Yes:
                    # Reset to bidirectional and continue saving
                    self.sync_direction_combo.setCurrentIndex(0)
                else:
                    return  # Go back to dialog
        # Validate: the API key is never sent over an unencrypted channel.
        if not self._confirm_insecure_api_key():
            return  # Go back to dialog
        # Validate + normalize the server and bootnode endpoints (shared grammar).
        try:
            normalized_server = self._normalize_server_endpoint()
        except ValueError:
            QMessageBox.warning(self, tr("settings.title"), tr("settings.invalid_server_endpoint"))
            return
        try:
            normalized_bootnode = self._normalize_bootnode_endpoint()
        except ValueError:
            QMessageBox.warning(
                self, tr("settings.title"), tr("settings.invalid_bootnode_endpoint")
            )
            return
        if normalized_server is not None:
            self.server_url.setText(normalized_server)
        if normalized_bootnode is not None:
            self.p2p_bootnode.setText(normalized_bootnode)
        self.save()
        self.accept()

    def _confirm_insecure_api_key(self) -> bool:
        """Warn when the API key would travel over an insecure channel.

        Mirrors the client gate that aborts when an API key is paired with
        an ``http://`` URL or with SSL verification disabled. Returns True
        to proceed with saving, False to return to the dialog.
        """
        if self.p2p_mode.isChecked():
            return True  # Server-mode settings are unused in p2p mode
        if not self.api_key.text().strip():
            return True
        url = self.server_url.text().strip().lower()
        insecure_url = url.startswith("http://")
        if not (insecure_url or self.insecure.isChecked()):
            return True
        msg = QMessageBox(
            QMessageBox.Icon.Warning,
            tr("warn.api_key_insecure_title"),
            tr("warn.api_key_insecure_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        yes_btn = msg.button(QMessageBox.StandardButton.Yes)
        no_btn = msg.button(QMessageBox.StandardButton.No)
        if yes_btn:
            yes_btn.setText(tr("action.yes"))
        if no_btn:
            no_btn.setText(tr("action.no"))
        return msg.exec() == QMessageBox.StandardButton.Yes

    def save(self) -> None:
        """Persist all settings to QSettings."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        s.setValue("path/local", self.shared_path.text())
        s.setValue("connection/server_url", self.server_url.text())
        s.setValue("connection/api_key", encrypt_value(self.api_key.text()))
        s.setValue("connection/insecure", self.insecure.isChecked())
        s.setValue("connection/ca_cert", self.ca_cert.text())
        s.setValue("connection/server_trust", self.server_trust.currentData())
        s.setValue("connection/http_timeout", self.http_timeout.value())
        s.setValue("sync/bucket", self.bucket.text())
        s.setValue("sync/continuous", self.continuous.isChecked())
        s.setValue("sync/resync", self.resync.value())
        s.setValue("sync/retry_delay", self.retry_delay.value())
        s.setValue("sync/stability_delay", self.stability_delay.value())
        s.setValue("sync/max_wait", self.max_wait.value())
        s.setValue("sync/ignore_delete", self.ignore_delete.isChecked())
        s.setValue("sync/direction", self.sync_direction_combo.currentData() or "bidirectional")
        s.setValue("sync/min_free_disk_space", self.min_free_disk_space.value())
        s.setValue("sync/max_inbound_size", self.max_inbound_size.value())
        s.setValue("sync/filter_path", self.filter_path.text())
        s.setValue("sync/compression_enabled", self.compression_enabled.isChecked())
        s.setValue("sync/dry_run", self.dry_run.isChecked())
        s.setValue("sync/auto_sync", self.auto_sync.isChecked())
        s.setValue("sync/ignore_patterns", self.ignore_patterns.text())
        s.setValue("p2p/enabled", self.p2p_mode.isChecked())
        s.setValue("p2p/group", self.p2p_group.text())
        s.setValue("p2p/bootnode", self.p2p_bootnode.text().strip())
        s.setValue(
            "p2p/bootnode_trust",
            self.p2p_bootnode_trust.currentData() or DEFAULT_P2P_BOOTNODE_TRUST,
        )
        s.setValue("p2p/upnp_enabled", self.p2p_upnp.isChecked())
        s.setValue("p2p/key", encrypt_value(self.p2p_key.text()))
        s.setValue("p2p/port", self.p2p_port.value())
        s.setValue("p2p/discovery_timeout", self.discovery_timeout.value())
        s.setValue("p2p/ntp_hosts", self.ntp_hosts.text())
        s.setValue("p2p/force_master", self.force_master.isChecked())
        s.setValue("p2p/never_master", self.never_master.isChecked())
        s.setValue("p2p/require_pairing", self.require_pairing.isChecked())
        s.setValue("output/verbose", self.verbose.isChecked())
        s.setValue("output/quiet", self.quiet.isChecked())
        s.setValue("output/logfile", self.logfile.text())
        # Map translated theme names back to internal keys
        s.setValue(
            "appearance/theme", THEME_DARK if self.theme_combo.currentIndex() == 1 else THEME_LIGHT
        )
        s.setValue("appearance/notifications", self.notifications_enabled.isChecked())
        # New fields
        lang_code = self.lang_combo.currentData()
        if lang_code:
            s.setValue("appearance/language", lang_code)
            set_language(lang_code)
        s.setValue("appearance/tooltips", self.tooltips_enabled.isChecked())
        s.setValue("appearance/show_log", self.show_log_panel.isChecked())
        # Flush to disk and tighten file permissions (config may be created here
        # on first run, before the startup hardening runs).
        s.sync()
        secure_config_file()

    def load(self) -> None:
        """Restore settings from QSettings."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.shared_path.setText(str(s.value("path/local", "", str)))
        self.server_url.setText(str(s.value("connection/server_url", "", str)))
        self.api_key.setText(decrypt_value(str(s.value("connection/api_key", "", str))))
        self.insecure.setChecked(bool(s.value("connection/insecure", DEFAULT_INSECURE, bool)))
        self.ca_cert.setText(str(s.value("connection/ca_cert", DEFAULT_CA_CERT, str)))
        trust_index = self.server_trust.findData(
            s.value("connection/server_trust", DEFAULT_SERVER_TRUST, str)
        )
        self.server_trust.setCurrentIndex(trust_index if trust_index >= 0 else 0)
        self.http_timeout.setValue(
            cast(int, s.value("connection/http_timeout", DEFAULT_HTTP_TIMEOUT, int))
        )
        self.bucket.setText(str(s.value("sync/bucket", DEFAULT_BUCKET, str)))
        self.continuous.setChecked(bool(s.value("sync/continuous", DEFAULT_CONTINUOUS, bool)))
        self.resync.setValue(cast(int, s.value("sync/resync", DEFAULT_RESYNC_INTERVAL, int)))
        self.retry_delay.setValue(cast(int, s.value("sync/retry_delay", DEFAULT_RETRY_DELAY, int)))
        self.stability_delay.setValue(
            cast(int, s.value("sync/stability_delay", DEFAULT_STABILITY_DELAY, int))
        )
        self.max_wait.setValue(cast(int, s.value("sync/max_wait", DEFAULT_MAX_WAIT, int)))
        self.ignore_delete.setChecked(
            bool(s.value("sync/ignore_delete", DEFAULT_IGNORE_DELETE, bool))
        )
        saved_dir = s.value("sync/direction", DEFAULT_SYNC_DIRECTION, str)
        for i in range(self.sync_direction_combo.count()):
            if self.sync_direction_combo.itemData(i) == saved_dir:
                self.sync_direction_combo.setCurrentIndex(i)
                break
        self.min_free_disk_space.setValue(
            cast(int, s.value("sync/min_free_disk_space", DEFAULT_MIN_FREE_DISK_SPACE, int))
        )
        self.max_inbound_size.setValue(
            cast(int, s.value("sync/max_inbound_size", DEFAULT_MAX_INBOUND_SIZE, int))
        )
        self.filter_path.setText(str(s.value("sync/filter_path", DEFAULT_FILTER_PATH, str)))
        # Read new key; fall back to inverted legacy key for migration
        if s.contains("sync/compression_enabled"):
            self.compression_enabled.setChecked(
                bool(s.value("sync/compression_enabled", DEFAULT_COMPRESSION_ENABLED, bool))
            )
        else:
            # Migrate from legacy no_compression (inverted logic)
            legacy = bool(s.value("sync/no_compression", DEFAULT_NO_COMPRESSION, bool))
            self.compression_enabled.setChecked(not legacy)
        self.dry_run.setChecked(bool(s.value("sync/dry_run", DEFAULT_DRY_RUN, bool)))
        self.auto_sync.setChecked(bool(s.value("sync/auto_sync", DEFAULT_AUTO_SYNC, bool)))
        self.ignore_patterns.setText(
            str(s.value("sync/ignore_patterns", DEFAULT_IGNORE_PATTERNS, str))
        )
        self.p2p_mode.setChecked(bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)))
        self.p2p_group.setText(str(s.value("p2p/group", DEFAULT_GROUP, str)))
        self.p2p_bootnode.setText(str(s.value("p2p/bootnode", DEFAULT_P2P_BOOTNODE, str)))
        index = self.p2p_bootnode_trust.findData(
            str(s.value("p2p/bootnode_trust", DEFAULT_P2P_BOOTNODE_TRUST, str))
        )
        self.p2p_bootnode_trust.setCurrentIndex(index if index >= 0 else 0)
        self.p2p_upnp.setChecked(bool(s.value("p2p/upnp_enabled", DEFAULT_P2P_UPNP_ENABLED, bool)))
        self.p2p_key.setText(decrypt_value(str(s.value("p2p/key", DEFAULT_P2P_KEY, str))))
        self.p2p_port.setValue(cast(int, s.value("p2p/port", DEFAULT_P2P_PORT, int)))
        self.discovery_timeout.setValue(
            cast(int, s.value("p2p/discovery_timeout", DEFAULT_DISCOVERY_TIMEOUT, int))
        )
        self.ntp_hosts.setText(str(s.value("p2p/ntp_hosts", DEFAULT_NTP_HOSTS, str)))
        self.force_master.setChecked(bool(s.value("p2p/force_master", DEFAULT_FORCE_MASTER, bool)))
        self.never_master.setChecked(bool(s.value("p2p/never_master", DEFAULT_NEVER_MASTER, bool)))
        self.require_pairing.setChecked(
            bool(s.value("p2p/require_pairing", DEFAULT_P2P_REQUIRE_PAIRING, bool))
        )
        self.verbose.setChecked(bool(s.value("output/verbose", DEFAULT_VERBOSE, bool)))
        self.quiet.setChecked(bool(s.value("output/quiet", DEFAULT_QUIET, bool)))
        self.logfile.setText(str(s.value("output/logfile", DEFAULT_LOGFILE, str)))
        theme = s.value("appearance/theme", detect_system_theme(), str)
        self.theme_combo.setCurrentIndex(1 if theme == THEME_DARK else 0)
        self.notifications_enabled.setChecked(
            bool(s.value("appearance/notifications", DEFAULT_NOTIFICATIONS, bool))
        )
        # Language
        saved_lang = s.value("appearance/language", get_language(), str)
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == saved_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        # Tooltips
        self.tooltips_enabled.setChecked(
            bool(s.value("appearance/tooltips", DEFAULT_TOOLTIPS, bool))
        )
        # Show log panel (default: hidden)
        self.show_log_panel.setChecked(
            bool(s.value("appearance/show_log", DEFAULT_SHOW_LOG_PANEL, bool))
        )
        # Apply p2p mode state to Server Mode tab
        self._on_p2p_mode_toggled(self.p2p_mode.isChecked())

    # ── Connection-active state management ────────────────────────────────

    def set_current_tab(self, index: int) -> None:
        """Switch the tab widget to the given index."""
        if self._tabs and 0 <= index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def set_connection_active(self, active: bool) -> None:
        """Enable or disable settings that cannot be changed during sync.

        When sync is running, connection-critical settings are disabled
        (grayed out) to prevent confusing the user with changes that
        won't take effect until the next sync.

        Args:
            active: True if sync is running, False otherwise.
        """

        # Show/hide the info banner
        self._connection_banner.setVisible(active)
        if active:
            self._banner_text.setText(tr("settings.connection_active_warning"))

        # Tooltip to show on disabled widgets
        disabled_tip = tr("tip.disabled_during_sync") if active else ""

        # List of widgets to disable during active connection
        # Connection tab - all settings affect how we connect
        connection_widgets: list[QWidget] = [
            self.server_url,
            self.api_key,
            self.insecure,
            self.ca_cert,
            self.http_timeout,
        ]

        # Sync tab - all settings affect sync behavior
        sync_widgets: list[QWidget] = [
            self.shared_path,
            self.btn_browse_shared,
            self.bucket,
            self.continuous,
            self.ignore_delete,
            self.sync_direction_combo,
            self.resync,
            self.retry_delay,
            self.stability_delay,
            self.max_wait,
            self.min_free_disk_space,
            self.max_inbound_size,
            self.filter_path,
            self.compression_enabled,
            self.dry_run,
            self.ignore_patterns,
            self.btn_edit_hsyncignore,
        ]

        # p2p tab - all settings affect p2p mode behavior
        p2p_widgets: list[QWidget] = [
            self.p2p_mode,
            self.p2p_group,
            self.p2p_bootnode,
            self.p2p_upnp,
            self.p2p_key,
            self.p2p_port,
            self.discovery_timeout,
            self.ntp_hosts,
            self.force_master,
            self.never_master,
            self.require_pairing,
        ]

        # Combine all widgets that should be disabled
        all_disabled_widgets = connection_widgets + sync_widgets + p2p_widgets

        for widget in all_disabled_widgets:
            widget.setEnabled(not active and widget not in self._unsupported_widgets)
            # Set tooltip explaining why it's disabled
            if active:
                widget.setToolTip(disabled_tip)

        # Re-apply normal tooltips and p2p-mode state when connection is not active
        if not active:
            self._apply_tooltips()
            # Re-apply p2p mode state so sub-widgets stay disabled if p2p is off
            self._on_p2p_mode_toggled(self.p2p_mode.isChecked())


# ─── API Key Dialog ─────────────────────────────────────────────────────────


class ApiKeyDialog(QDialog):
    """Dialog to prompt for API key when authentication fails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("api_key_dialog", self)

        self.setWindowTitle(tr("apikey.title"))

        # Get widget references from .ui
        self._lbl_error: QLabel = self.findChild(QLabel, "lblError")  # type: ignore[assignment]
        self._lbl_prompt: QLabel = self.findChild(QLabel, "lblPrompt")  # type: ignore[assignment]
        self._lbl_key_label: QLabel = self.findChild(QLabel, "lblKeyLabel")  # type: ignore[assignment]
        self._api_key_edit: QLineEdit = self.findChild(QLineEdit, "editApiKey")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

    def _populate(self) -> None:
        """Populate labels with translated text and load current values."""
        self._lbl_error.setText(tr("apikey.error_message"))
        self._lbl_prompt.setText(tr("apikey.prompt"))
        self._lbl_key_label.setText(tr("apikey.label"))
        self._api_key_edit.setPlaceholderText(tr("apikey.label"))

        # Load current API key if any
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        current_key = decrypt_value(str(s.value("connection/api_key", "", str)))
        self._api_key_edit.setText(current_key)

        # Buttons
        self._button_box.addButton(tr("apikey.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        self._cancel_btn = self._button_box.addButton(
            tr("apikey.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)

        # Focus on input
        self._api_key_edit.setFocus()

    def _on_save(self) -> None:
        """Save the API key and accept the dialog."""
        api_key = self._api_key_edit.text().strip()
        if api_key:
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            s.setValue("connection/api_key", encrypt_value(api_key))
            self.accept()
        else:
            # Show warning if empty
            QMessageBox.warning(
                self,
                tr("apikey.title"),
                tr("apikey.prompt"),
            )


# ─── p2p Key Dialog ─────────────────────────────────────────────────────────


class P2PKeyDialog(QDialog):
    """Dialog to prompt for p2p key when p2p authentication fails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("p2p_key_dialog", self)

        self.setWindowTitle(tr("p2pauth.title"))

        # Get widget references from .ui
        self._lbl_error: QLabel = self.findChild(QLabel, "lblError")  # type: ignore[assignment]
        self._lbl_prompt: QLabel = self.findChild(QLabel, "lblPrompt")  # type: ignore[assignment]
        self._lbl_key_label: QLabel = self.findChild(QLabel, "lblKeyLabel")  # type: ignore[assignment]
        self._p2p_key_edit: QLineEdit = self.findChild(QLineEdit, "editP2PKey")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

    def _populate(self) -> None:
        """Populate labels with translated text and load current values."""
        self._lbl_error.setText(tr("p2pauth.error_message"))
        self._lbl_prompt.setText(tr("p2pauth.prompt"))
        self._lbl_key_label.setText(tr("p2pauth.label"))
        self._p2p_key_edit.setPlaceholderText(tr("p2pauth.label"))

        # Load current p2p key if any
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        current_key = decrypt_value(str(s.value("p2p/key", "", str)))
        self._p2p_key_edit.setText(current_key)

        # Buttons
        self._button_box.addButton(tr("p2pauth.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        self._cancel_btn = self._button_box.addButton(
            tr("p2pauth.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)

        # Focus on input
        self._p2p_key_edit.setFocus()

    def _on_save(self) -> None:
        """Save the p2p key and accept the dialog."""
        p2p_key = self._p2p_key_edit.text().strip()
        if p2p_key:
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            s.setValue("p2p/key", encrypt_value(p2p_key))
            self.accept()
        else:
            QMessageBox.warning(
                self,
                tr("p2pauth.title"),
                tr("p2pauth.prompt"),
            )


# ─── .hsyncignore Editor Dialog ─────────────────────────────────────────────


class HsyncIgnoreEditorDialog(QDialog):
    """Simple text editor for the `.hsyncignore` file at the bucket root."""

    def __init__(self, bucket_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bucket_root = bucket_root
        self._target = bucket_root / HSYNCIGNORE_FILENAME

        self.setWindowTitle(tr("hsyncignore.title"))
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        self._lbl_desc = QLabel(tr("hsyncignore.description"), self)
        self._lbl_desc.setWordWrap(True)
        layout.addWidget(self._lbl_desc)

        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText("# Example:\n# /build/\n# *.log\n# !important.log\n")
        layout.addWidget(self._editor, 1)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText(tr("hsyncignore.save"))
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(tr("hsyncignore.cancel"))
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._load_file()

    def _load_file(self) -> None:
        """Load the existing .hsyncignore content, if any."""
        if not self._target.exists():
            return
        try:
            self._editor.setPlainText(self._target.read_text(encoding="utf-8"))
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("hsyncignore.title"),
                tr("hsyncignore.read_error").format(error=exc),
            )

    def _on_save(self) -> None:
        """Write the editor content to the .hsyncignore file."""
        try:
            self._bucket_root.mkdir(parents=True, exist_ok=True)
            self._target.write_text(self._editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("hsyncignore.title"),
                tr("hsyncignore.write_error").format(error=exc),
            )
            return
        self.accept()
