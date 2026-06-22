# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Dialog classes for HSYNC Desktop settings.

Contains SettingsDialog, ApiKeyDialog, and LanKeyDialog.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import cast

from hsync_common.constants import HSYNCIGNORE_FILENAME
from PySide6.QtCore import QSettings, QThread, QTimer
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
    DEFAULT_LAN_ENABLED,
    DEFAULT_LAN_HTTPS,
    DEFAULT_LAN_KEY,
    DEFAULT_LAN_PERSISTENT,
    DEFAULT_LAN_PORT,
    DEFAULT_LAN_REQUIRE_PAIRING,
    DEFAULT_LOGFILE,
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_FREE_DISK_SPACE,
    DEFAULT_NEVER_MASTER,
    DEFAULT_NO_COMPRESSION,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_QUIET,
    DEFAULT_RESYNC_INTERVAL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SERVER_CERT_FINGERPRINT,
    DEFAULT_SHOW_LOG_PANEL,
    DEFAULT_STABILITY_DELAY,
    DEFAULT_SYNC_DIRECTION,
    DEFAULT_SYNC_HIDDEN,
    DEFAULT_TOOLTIPS,
    DEFAULT_VERBOSE,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.crypto import decrypt_value, encrypt_value
from hsync_desktop.i18n import (
    SUPPORTED_LANGUAGES,
    get_language,
    set_language,
    tr,
)
from hsync_desktop.icons import icon
from hsync_desktop.settings.cli_args import secure_config_file
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT, detect_system_theme
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.toggle_switch import ToggleSwitch


def _maybe_tip(widget: QWidget, key: str, enabled: bool) -> None:
    """Set tooltip on *widget* from i18n *key* only when *enabled*."""
    widget.setToolTip(tr(key) if enabled else "")


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
        self._connection_active = False  # Track if sync is running

        self._load_ui()
        self.load()  # Load saved values BEFORE connecting signals
        self._connect_signals()  # Connect signals AFTER loading to avoid spurious events

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

        # Add server_cert_fingerprint field dynamically (after ca_cert)
        self.server_cert_fingerprint = QLineEdit(self)
        self.server_cert_fingerprint.setObjectName("serverCertFingerprint")
        self.server_cert_fingerprint.setPlaceholderText("SHA-256 hex fingerprint")
        self._lbl_cert_fingerprint = QLabel(self)

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
        self.compression_enabled, self._lbl_compression_enabled = _replace_checkbox_with_toggle(
            self, "noCompression"
        )
        self.dry_run, self._lbl_dry_run = _replace_checkbox_with_toggle(self, "dryRun")
        self.auto_sync, self._lbl_auto_sync = _replace_checkbox_with_toggle(self, "autoSync")

        # Hidden-file / .hsyncignore controls (dynamic, no .ui counterpart)
        self.sync_hidden = ToggleSwitch(self)
        self.sync_hidden.setObjectName("syncHidden")
        self._lbl_sync_hidden = QLabel(self)
        self.ignore_patterns = QLineEdit(self)
        self.ignore_patterns.setObjectName("ignorePatterns")
        self.ignore_patterns.setPlaceholderText("*.log, /build/, /dist/")
        self._lbl_ignore_patterns = QLabel(self)
        self.btn_edit_hsyncignore = QPushButton(self)
        self.btn_edit_hsyncignore.setObjectName("btnEditHsyncignore")

        # Reorganize sync tab into grouped sections
        self._reorganize_sync_tab()

        # LAN tab widgets
        self.lan_mode, self._lbl_lan_mode = _replace_checkbox_with_toggle(self, "lanMode")
        self.lan_group: QLineEdit = self.findChild(QLineEdit, "lanGroup")  # type: ignore[assignment]
        self.lan_key: QLineEdit = self.findChild(QLineEdit, "lanKey")  # type: ignore[assignment]
        self.lan_port: QSpinBox = self.findChild(QSpinBox, "lanPort")  # type: ignore[assignment]
        self.discovery_timeout: QSpinBox = self.findChild(QSpinBox, "discoveryTimeout")  # type: ignore[assignment]
        self.lan_https, self._lbl_lan_https = _replace_checkbox_with_toggle(self, "lanHttps")
        self.lan_persistent, self._lbl_lan_persistent = _replace_checkbox_with_toggle(
            self, "lanPersistent"
        )
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
            fm_layout = fm_container.parent().layout() if fm_container.parent() else None
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
        self.show_log_panel, self._lbl_show_log = _replace_checkbox_with_toggle(
            self, "showLogPanel"
        )

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
        self._tabs.setTabIcon(2, icon("network-lan"))
        self._tabs.setTabIcon(3, icon("utilities-log-viewer"))
        self._tabs.setTabIcon(4, icon("preferences-desktop-theme"))

        # Create info banner for Server Mode tab when LAN is active (hidden by default)
        self._lan_banner = QFrame(self)
        self._lan_banner.setObjectName("lanBanner")
        self._lan_banner.setStyleSheet(
            "QFrame#lanBanner { "
            "background-color: #fff3cd; "
            "border: 1px solid #ffc107; "
            "border-radius: 4px; "
            "padding: 8px; "
            "}"
        )
        lan_banner_layout = QHBoxLayout(self._lan_banner)
        lan_banner_layout.setContentsMargins(8, 4, 8, 4)
        self._lan_banner_icon = QLabel("⚠️")
        self._lan_banner_text = QLabel()
        self._lan_banner_text.setWordWrap(True)
        self._lan_banner_text.setStyleSheet("color: #856404;")
        lan_banner_layout.addWidget(self._lan_banner_icon)
        lan_banner_layout.addWidget(self._lan_banner_text, 1)
        self._lan_banner.hide()

        # Insert LAN banner at the top of the Server Mode (tabConnection) layout
        # Also insert server_cert_fingerprint field and Test Connection button
        self.btn_test_connection = QPushButton()
        self.btn_test_connection.setObjectName("btnTestConnection")

        conn_tab = self._tabs.widget(1)
        if conn_tab:
            conn_layout = conn_tab.layout()
            if isinstance(conn_layout, QFormLayout):
                conn_layout.insertRow(0, self._lan_banner)
                # Insert server_cert_fingerprint after http_timeout row,
                # then Test Connection button after cert fingerprint
                for row in range(conn_layout.rowCount()):
                    item = conn_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    if item and item.widget() == self.http_timeout:
                        conn_layout.insertRow(
                            row + 1, self._lbl_cert_fingerprint, self.server_cert_fingerprint
                        )
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
        f4.addRow(lbl_filter, self.filter_path)
        f4.addRow("", cont_no_comp)
        f4.addRow("", cont_dry_run)

        # Sync hidden toggle (switch + label container, like other toggles)
        cont_sync_hidden = QWidget(self)
        hl_sync_hidden = QHBoxLayout(cont_sync_hidden)
        hl_sync_hidden.setContentsMargins(0, 0, 0, 0)
        hl_sync_hidden.addWidget(self.sync_hidden)
        hl_sync_hidden.addWidget(self._lbl_sync_hidden)
        hl_sync_hidden.addStretch()
        f4.addRow("", cont_sync_hidden)

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
        self._tabs.setTabText(2, tr("settings.lan"))
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
        self._lbl_compression_enabled.setText(tr("settings.compression_enabled"))
        self._lbl_dry_run.setText(tr("settings.dry_run"))
        self._lbl_auto_sync.setText(tr("settings.auto_sync"))
        self._lbl_sync_hidden.setText(tr("settings.sync_hidden"))
        self._lbl_ignore_patterns.setText(tr("settings.ignore_patterns"))
        self.btn_edit_hsyncignore.setText(tr("settings.edit_hsyncignore"))

        # Sync tab group box titles
        self._grp_path.setTitle(tr("settings.group.path_bucket"))
        self._grp_sync.setTitle(tr("settings.group.sync_mode"))
        self._grp_timing.setTitle(tr("settings.group.timing"))
        self._grp_advanced.setTitle(tr("settings.group.advanced"))

        # LAN tab labels
        self._lbl_lan_mode.setText(tr("settings.lan_mode"))
        lbl = self.findChild(QLabel, "lblLanGroup")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.lan_group"))
        lbl = self.findChild(QLabel, "lblLanKey")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.lan_key"))
        lbl = self.findChild(QLabel, "lblLanPort")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.lan_port"))
        lbl = self.findChild(QLabel, "lblDiscoveryTimeout")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.discovery_timeout"))
        self._lbl_lan_https.setText(tr("settings.lan_https"))
        self._lbl_lan_persistent.setText(tr("settings.lan_persistent"))
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
            lbl.setText(tr("settings.language"))
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
        _maybe_tip(self.filter_path, "tip.filter_path", tips)
        _maybe_tip(self.compression_enabled, "tip.compression_enabled", tips)
        _maybe_tip(self.dry_run, "tip.dry_run", tips)
        _maybe_tip(self.auto_sync, "tip.auto_sync", tips)
        _maybe_tip(self.sync_hidden, "tip.sync_hidden", tips)
        _maybe_tip(self.ignore_patterns, "tip.ignore_patterns", tips)
        _maybe_tip(self.btn_edit_hsyncignore, "tip.edit_hsyncignore", tips)

        # Server Mode tab
        _maybe_tip(self.server_url, "tip.server_url", tips)
        _maybe_tip(self.api_key, "tip.api_key", tips)
        _maybe_tip(self.insecure, "tip.insecure", tips)
        _maybe_tip(self.ca_cert, "tip.ca_cert", tips)
        _maybe_tip(self.http_timeout, "tip.http_timeout", tips)

        # LAN tab
        _maybe_tip(self.lan_mode, "tip.lan_mode", tips)
        _maybe_tip(self.lan_group, "tip.lan_group", tips)
        _maybe_tip(self.lan_key, "tip.lan_key", tips)
        _maybe_tip(self.lan_port, "tip.lan_port", tips)
        _maybe_tip(self.discovery_timeout, "tip.discovery_timeout", tips)
        _maybe_tip(self.lan_https, "tip.lan_https", tips)
        _maybe_tip(self.lan_persistent, "tip.lan_persistent", tips)
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

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.ignore_delete.toggled.connect(self._on_ignore_delete_toggled)
        self.btn_browse_shared.clicked.connect(self._on_browse_shared)
        self.lan_mode.toggled.connect(self._on_lan_mode_toggled)
        self.lan_https.toggled.connect(self._on_lan_https_toggled)
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

    def _on_lan_mode_toggled(self, checked: bool) -> None:
        """Enable/disable Server Mode tab widgets when LAN mode changes,
        and enable/disable LAN tab widgets based on LAN mode state."""
        # Show/hide the LAN banner on Server Mode tab
        self._lan_banner.setVisible(checked)
        if checked:
            self._lan_banner_text.setText(tr("settings.lan_disables_server"))

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
                if lbl not in (self._lan_banner_icon, self._lan_banner_text):
                    lbl.setEnabled(not checked)

        # Enable/disable LAN tab widgets (except the lan_mode toggle itself)
        lan_sub_widgets: list[QWidget] = [
            self.lan_group,
            self.lan_key,
            self.lan_port,
            self.discovery_timeout,
            self.lan_https,
            self.lan_persistent,
            self.force_master,
            self.never_master,
            self.require_pairing,
        ]
        for widget in lan_sub_widgets:
            widget.setEnabled(checked)

        # Also enable/disable the labels in the LAN tab (except lan_mode label)
        lan_tab = self._tabs.widget(2)
        if lan_tab:
            for lbl in lan_tab.findChildren(QLabel):
                if lbl is not self._lbl_lan_mode:
                    lbl.setEnabled(checked)

        # The shared secret is only usable over HTTPS; keep its gate in sync.
        self._apply_lan_key_gate()

    def _on_lan_https_toggled(self, _checked: bool) -> None:
        """Re-apply the shared-secret gate when LAN HTTPS changes."""
        self._apply_lan_key_gate()

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

    def _apply_lan_key_gate(self) -> None:
        """Disable the LAN shared secret unless LAN HTTPS is enabled.

        Mirrors the client config rule that drops ``lan_key`` when HTTPS
        is off: a shared secret must never travel over plain HTTP.
        """
        lan_on = self.lan_mode.isChecked()
        https_on = self.lan_https.isChecked()
        enabled = lan_on and https_on
        self.lan_key.setEnabled(enabled)
        lbl = self.findChild(QLabel, "lblLanKey")
        if lbl:
            lbl.setEnabled(enabled)
        if lan_on and not https_on:
            tip = tr("tip.lan_key_https_required")
            self.lan_key.setToolTip(tip)
            if lbl:
                lbl.setToolTip(tip)
        else:
            restore = tr("tip.lan_key") if self._tips_enabled() else ""
            self.lan_key.setToolTip(restore)
            if lbl:
                lbl.setToolTip("")

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

        # Normalize URL
        base = url.rstrip("/")
        health_url = f"{base}/health"

        self.btn_test_connection.setEnabled(False)
        self.btn_test_connection.setText("…")

        def _restore() -> None:
            self.btn_test_connection.setEnabled(True)
            self.btn_test_connection.setText(tr("settings.test_connection"))

        try:
            timeout = max(5, self.http_timeout.value())
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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
        self.save()
        self.accept()

    def _confirm_insecure_api_key(self) -> bool:
        """Warn when the API key would travel over an insecure channel.

        Mirrors the client gate that aborts when an API key is paired with
        an ``http://`` URL or with SSL verification disabled. Returns True
        to proceed with saving, False to return to the dialog.
        """
        if self.lan_mode.isChecked():
            return True  # Server-mode settings are unused in LAN mode
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
        s.setValue("connection/server_cert_fingerprint", self.server_cert_fingerprint.text())
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
        s.setValue("sync/filter_path", self.filter_path.text())
        s.setValue("sync/compression_enabled", self.compression_enabled.isChecked())
        s.setValue("sync/dry_run", self.dry_run.isChecked())
        s.setValue("sync/auto_sync", self.auto_sync.isChecked())
        s.setValue("sync/sync_hidden", self.sync_hidden.isChecked())
        s.setValue("sync/ignore_patterns", self.ignore_patterns.text())
        s.setValue("lan/enabled", self.lan_mode.isChecked())
        s.setValue("lan/group", self.lan_group.text())
        s.setValue("lan/key", self.lan_key.text())
        s.setValue("lan/port", self.lan_port.value())
        s.setValue("lan/discovery_timeout", self.discovery_timeout.value())
        s.setValue("lan/https", self.lan_https.isChecked())
        s.setValue("lan/persistent", self.lan_persistent.isChecked())
        s.setValue("lan/force_master", self.force_master.isChecked())
        s.setValue("lan/never_master", self.never_master.isChecked())
        s.setValue("lan/require_pairing", self.require_pairing.isChecked())
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
        self.server_cert_fingerprint.setText(
            str(s.value("connection/server_cert_fingerprint", DEFAULT_SERVER_CERT_FINGERPRINT, str))
        )
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
        self.sync_hidden.setChecked(bool(s.value("sync/sync_hidden", DEFAULT_SYNC_HIDDEN, bool)))
        self.ignore_patterns.setText(
            str(s.value("sync/ignore_patterns", DEFAULT_IGNORE_PATTERNS, str))
        )
        self.lan_mode.setChecked(bool(s.value("lan/enabled", DEFAULT_LAN_ENABLED, bool)))
        self.lan_group.setText(str(s.value("lan/group", DEFAULT_GROUP, str)))
        self.lan_key.setText(str(s.value("lan/key", DEFAULT_LAN_KEY, str)))
        self.lan_port.setValue(cast(int, s.value("lan/port", DEFAULT_LAN_PORT, int)))
        self.discovery_timeout.setValue(
            cast(int, s.value("lan/discovery_timeout", DEFAULT_DISCOVERY_TIMEOUT, int))
        )
        self.lan_https.setChecked(bool(s.value("lan/https", DEFAULT_LAN_HTTPS, bool)))
        self.lan_persistent.setChecked(
            bool(s.value("lan/persistent", DEFAULT_LAN_PERSISTENT, bool))
        )
        self.force_master.setChecked(bool(s.value("lan/force_master", DEFAULT_FORCE_MASTER, bool)))
        self.never_master.setChecked(bool(s.value("lan/never_master", DEFAULT_NEVER_MASTER, bool)))
        self.require_pairing.setChecked(
            bool(s.value("lan/require_pairing", DEFAULT_LAN_REQUIRE_PAIRING, bool))
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
        # Apply LAN mode state to Server Mode tab
        self._on_lan_mode_toggled(self.lan_mode.isChecked())

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
        self._connection_active = active

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
            self.filter_path,
            self.compression_enabled,
            self.dry_run,
            self.sync_hidden,
            self.ignore_patterns,
            self.btn_edit_hsyncignore,
        ]

        # LAN tab - all settings affect LAN mode behavior
        lan_widgets: list[QWidget] = [
            self.lan_mode,
            self.lan_group,
            self.lan_key,
            self.lan_port,
            self.discovery_timeout,
            self.lan_https,
            self.lan_persistent,
            self.force_master,
            self.never_master,
            self.require_pairing,
        ]

        # Combine all widgets that should be disabled
        all_disabled_widgets = connection_widgets + sync_widgets + lan_widgets

        for widget in all_disabled_widgets:
            widget.setEnabled(not active)
            # Set tooltip explaining why it's disabled
            if active:
                widget.setToolTip(disabled_tip)

        # Re-apply normal tooltips and LAN-mode state when connection is not active
        if not active:
            self._apply_tooltips()
            # Re-apply LAN mode state so sub-widgets stay disabled if LAN is off
            self._on_lan_mode_toggled(self.lan_mode.isChecked())


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
        self._save_btn = self._button_box.addButton(
            tr("apikey.save"), QDialogButtonBox.ButtonRole.AcceptRole
        )
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

    def get_api_key(self) -> str:
        """Return the entered API key."""
        return self._api_key_edit.text().strip()


# ─── LAN Key Dialog ─────────────────────────────────────────────────────────


class LanKeyDialog(QDialog):
    """Dialog to prompt for LAN key when LAN authentication fails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("lan_key_dialog", self)

        self.setWindowTitle(tr("lanauth.title"))

        # Get widget references from .ui
        self._lbl_error: QLabel = self.findChild(QLabel, "lblError")  # type: ignore[assignment]
        self._lbl_prompt: QLabel = self.findChild(QLabel, "lblPrompt")  # type: ignore[assignment]
        self._lbl_key_label: QLabel = self.findChild(QLabel, "lblKeyLabel")  # type: ignore[assignment]
        self._lan_key_edit: QLineEdit = self.findChild(QLineEdit, "editLanKey")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

    def _populate(self) -> None:
        """Populate labels with translated text and load current values."""
        self._lbl_error.setText(tr("lanauth.error_message"))
        self._lbl_prompt.setText(tr("lanauth.prompt"))
        self._lbl_key_label.setText(tr("lanauth.label"))
        self._lan_key_edit.setPlaceholderText(tr("lanauth.label"))

        # Load current LAN key if any
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        current_key = str(s.value("lan/key", "", str))
        self._lan_key_edit.setText(current_key)

        # Buttons
        self._save_btn = self._button_box.addButton(
            tr("lanauth.save"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_btn = self._button_box.addButton(
            tr("lanauth.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)

        # Focus on input
        self._lan_key_edit.setFocus()

    def _on_save(self) -> None:
        """Save the LAN key and accept the dialog."""
        lan_key = self._lan_key_edit.text().strip()
        if lan_key:
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            s.setValue("lan/key", lan_key)
            self.accept()
        else:
            QMessageBox.warning(
                self,
                tr("lanauth.title"),
                tr("lanauth.prompt"),
            )

    def get_lan_key(self) -> str:
        """Return the entered LAN key."""
        return self._lan_key_edit.text().strip()


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
