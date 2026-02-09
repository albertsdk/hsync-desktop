# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Settings dialog for HSYNC Desktop.

Organized into sections matching hsync-client CLI option groups:
Connection, Sync, LAN Mode, Log, Appearance.
Supports Default (minimal) and Advanced (all options) modes.

UI is loaded from ui/settings_dialog.ui (Qt Designer).
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import (
    SUPPORTED_LANGUAGES,
    get_language,
    set_language,
    tr,
)
from hsync_desktop.icons import icon
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT, detect_system_theme
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.toggle_switch import ToggleSwitch

SETTINGS_ORG = "HSYNC"
SETTINGS_APP = "HSYNCDesktop"

# Default values
DEFAULT_BUCKET = "my-bucket"
DEFAULT_GROUP = "my-group"


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

    # List of advanced-only widgets: (widget_name, label_name or None)
    _ADVANCED_WIDGETS = [
        # Connection tab
        ("insecure", None),
        ("caCert", "lblCaCert"),
        ("httpTimeout", "lblHttpTimeout"),
        # Sync tab
        ("resync", "lblResync"),
        ("retryDelay", "lblRetryDelay"),
        ("stabilityDelay", "lblStabilityDelay"),
        ("maxWait", "lblMaxWait"),
        ("filterPath", "lblFilterPath"),
        ("noCompression", None),
        ("dryRun", None),
        # LAN tab
        ("lanPort", "lblLanPort"),
        ("discoveryTimeout", "lblDiscoveryTimeout"),
        ("lanHttps", None),
        ("lanPersistent", None),
        # Log tab
        ("quiet", None),
        ("logfile", "lblLogfile"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._advanced = False  # Start in default mode
        self._connection_active = False  # Track if sync is running

        self._load_ui()
        self.load()  # Load saved values BEFORE connecting signals
        self._connect_signals()  # Connect signals AFTER loading to avoid spurious events
        self._apply_mode()

    # ── UI loading from .ui file ─────────────────────────────────────────

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("settings_dialog", self)

        # Replace the QCheckBox placeholder with ToggleSwitch
        # Find the modeLayout (QHBoxLayout) that contains the checkbox
        mode_layout: QHBoxLayout | None = self.findChild(QHBoxLayout, "modeLayout")  # type: ignore[assignment]
        checkbox_placeholder = self.findChild(QCheckBox, "advancedMode")

        if mode_layout and checkbox_placeholder:
            index = mode_layout.indexOf(checkbox_placeholder)
            mode_layout.removeWidget(checkbox_placeholder)
            checkbox_placeholder.deleteLater()
            self._advanced_mode = ToggleSwitch(self)
            mode_layout.insertWidget(index, self._advanced_mode)
        else:
            # Fallback
            self._advanced_mode = ToggleSwitch(self)

        # Get widget references from .ui file
        self._lbl_advanced: QLabel = self.findChild(QLabel, "lblAdvanced")  # type: ignore[assignment]
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

        # Connection tab widgets
        self.server_url: QLineEdit = self.findChild(QLineEdit, "serverUrl")  # type: ignore[assignment]
        self.api_key: QLineEdit = self.findChild(QLineEdit, "apiKey")  # type: ignore[assignment]
        self.insecure, self._lbl_insecure = _replace_checkbox_with_toggle(self, "insecure")
        self.ca_cert: QLineEdit = self.findChild(QLineEdit, "caCert")  # type: ignore[assignment]
        self.http_timeout: QSpinBox = self.findChild(QSpinBox, "httpTimeout")  # type: ignore[assignment]

        # Sync tab widgets
        self.bucket: QLineEdit = self.findChild(QLineEdit, "bucket")  # type: ignore[assignment]
        self.continuous, self._lbl_continuous = _replace_checkbox_with_toggle(self, "continuous")
        self.ignore_delete, self._lbl_ignore_delete = _replace_checkbox_with_toggle(self, "ignoreDelete")
        self.resync: QSpinBox = self.findChild(QSpinBox, "resync")  # type: ignore[assignment]
        self.retry_delay: QSpinBox = self.findChild(QSpinBox, "retryDelay")  # type: ignore[assignment]
        self.stability_delay: QSpinBox = self.findChild(QSpinBox, "stabilityDelay")  # type: ignore[assignment]
        self.max_wait: QSpinBox = self.findChild(QSpinBox, "maxWait")  # type: ignore[assignment]
        self.filter_path: QLineEdit = self.findChild(QLineEdit, "filterPath")  # type: ignore[assignment]
        self.no_compression, self._lbl_no_compression = _replace_checkbox_with_toggle(self, "noCompression")
        self.dry_run, self._lbl_dry_run = _replace_checkbox_with_toggle(self, "dryRun")

        # LAN tab widgets
        self.lan_mode, self._lbl_lan_mode = _replace_checkbox_with_toggle(self, "lanMode")
        self.lan_group: QLineEdit = self.findChild(QLineEdit, "lanGroup")  # type: ignore[assignment]
        self.lan_key: QLineEdit = self.findChild(QLineEdit, "lanKey")  # type: ignore[assignment]
        self.lan_port: QSpinBox = self.findChild(QSpinBox, "lanPort")  # type: ignore[assignment]
        self.discovery_timeout: QSpinBox = self.findChild(QSpinBox, "discoveryTimeout")  # type: ignore[assignment]
        self.lan_https, self._lbl_lan_https = _replace_checkbox_with_toggle(self, "lanHttps")
        self.lan_persistent, self._lbl_lan_persistent = _replace_checkbox_with_toggle(self, "lanPersistent")
        self.force_master, self._lbl_force_master = _replace_checkbox_with_toggle(self, "forceMaster")

        # Log tab widgets
        self.verbose, self._lbl_verbose = _replace_checkbox_with_toggle(self, "verbose")
        self.quiet, self._lbl_quiet = _replace_checkbox_with_toggle(self, "quiet")
        self.logfile: QLineEdit = self.findChild(QLineEdit, "logfile")  # type: ignore[assignment]
        self.show_log_panel, self._lbl_show_log = _replace_checkbox_with_toggle(self, "showLogPanel")

        # Appearance tab widgets
        self.theme_combo: QComboBox = self.findChild(QComboBox, "themeCombo")  # type: ignore[assignment]
        self.lang_combo: QComboBox = self.findChild(QComboBox, "langCombo")  # type: ignore[assignment]
        self.notifications_enabled, self._lbl_notifications = _replace_checkbox_with_toggle(self, "notificationsEnabled")
        self.tooltips_enabled, self._lbl_tooltips = _replace_checkbox_with_toggle(self, "tooltipsEnabled")

        # Set tab icons programmatically (theme icons don't work cross-platform)
        self._tabs.setTabIcon(0, icon("network-wired"))
        self._tabs.setTabIcon(1, icon("emblem-synchronizing"))
        self._tabs.setTabIcon(2, icon("network-workgroup"))
        self._tabs.setTabIcon(3, icon("utilities-log-viewer"))
        self._tabs.setTabIcon(4, icon("preferences-desktop-theme"))

        # Setup language combo with proper data
        self.lang_combo.clear()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(name, code)

        # Apply translations
        self._apply_translations()
        self._apply_tooltips()

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self.setWindowTitle(tr("settings.title"))

        # Advanced mode toggle label
        if self._lbl_advanced:
            self._lbl_advanced.setText(tr("settings.mode_advanced"))

        # Tab titles
        self._tabs.setTabText(0, tr("settings.connection"))
        self._tabs.setTabText(1, tr("settings.sync"))
        self._tabs.setTabText(2, tr("settings.lan"))
        self._tabs.setTabText(3, tr("settings.log"))
        self._tabs.setTabText(4, tr("settings.appearance"))

        # Connection tab labels
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

        # Sync tab labels
        lbl = self.findChild(QLabel, "lblBucket")  # type: ignore[assignment]
        if lbl:
            lbl.setText(tr("settings.bucket"))
        self._lbl_continuous.setText(tr("settings.watch"))
        self._lbl_ignore_delete.setText(tr("settings.ignore_delete"))
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
        self._lbl_no_compression.setText(tr("settings.no_compression"))
        self._lbl_dry_run.setText(tr("settings.dry_run"))

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

    def _apply_tooltips(self) -> None:
        """Apply tooltips to widgets if enabled."""
        tips = self._tips_enabled()

        # Connection tab
        _maybe_tip(self.server_url, "tip.server_url", tips)
        _maybe_tip(self.api_key, "tip.api_key", tips)
        _maybe_tip(self.insecure, "tip.insecure", tips)
        _maybe_tip(self.ca_cert, "tip.ca_cert", tips)
        _maybe_tip(self.http_timeout, "tip.http_timeout", tips)

        # Sync tab
        _maybe_tip(self.bucket, "tip.bucket", tips)
        _maybe_tip(self.continuous, "tip.watch", tips)
        _maybe_tip(self.ignore_delete, "tip.ignore_delete", tips)
        _maybe_tip(self.resync, "tip.resync", tips)
        _maybe_tip(self.retry_delay, "tip.retry_delay", tips)
        _maybe_tip(self.stability_delay, "tip.stability_delay", tips)
        _maybe_tip(self.max_wait, "tip.max_wait", tips)
        _maybe_tip(self.filter_path, "tip.filter_path", tips)
        _maybe_tip(self.no_compression, "tip.no_compression", tips)
        _maybe_tip(self.dry_run, "tip.dry_run", tips)

        # LAN tab
        _maybe_tip(self.lan_mode, "tip.lan_mode", tips)
        _maybe_tip(self.lan_group, "tip.lan_group", tips)
        _maybe_tip(self.lan_key, "tip.lan_key", tips)
        _maybe_tip(self.lan_port, "tip.lan_port", tips)
        _maybe_tip(self.discovery_timeout, "tip.discovery_timeout", tips)
        _maybe_tip(self.lan_https, "tip.lan_https", tips)
        _maybe_tip(self.lan_persistent, "tip.lan_persistent", tips)
        _maybe_tip(self.force_master, "tip.force_master", tips)

        # Log tab
        _maybe_tip(self.verbose, "tip.verbose", tips)
        _maybe_tip(self.quiet, "tip.quiet", tips)
        _maybe_tip(self.logfile, "tip.logfile", tips)

        # Appearance tab
        _maybe_tip(self.theme_combo, "tip.theme", tips)
        _maybe_tip(self.lang_combo, "tip.language", tips)
        _maybe_tip(self.notifications_enabled, "tip.notifications", tips)
        _maybe_tip(self.tooltips_enabled, "tip.tooltips", tips)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._advanced_mode.toggled.connect(self._on_mode_changed)
        self.ignore_delete.toggled.connect(self._on_ignore_delete_toggled)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

    # ── Mode toggle ─────────────────────────────────────────────────────

    def _on_mode_changed(self, checked: bool) -> None:
        self._advanced = checked
        self._apply_mode()

    def _apply_mode(self) -> None:
        """Show/hide advanced widgets based on mode."""
        for widget_name, label_name in self._ADVANCED_WIDGETS:
            widget = self.findChild(QWidget, widget_name)
            if widget:
                widget.setVisible(self._advanced)
            if label_name:
                label = self.findChild(QLabel, label_name)
                if label:
                    label.setVisible(self._advanced)

    def _on_ignore_delete_toggled(self, checked: bool) -> None:
        """Show a warning when the user disables ignore-delete."""
        if not checked:
            result = QMessageBox.warning(
                self,
                tr("warn.ignore_delete_title"),
                tr("warn.ignore_delete_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                self.ignore_delete.blockSignals(True)
                self.ignore_delete.setChecked(True)
                self.ignore_delete.blockSignals(False)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _tips_enabled(self) -> bool:
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        return bool(s.value("appearance/tooltips", True, bool))

    # ── Save / Load ──────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        self.save()
        self.accept()

    def save(self) -> None:
        """Persist all settings to QSettings."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        s.setValue("connection/server_url", self.server_url.text())
        s.setValue("connection/api_key", self.api_key.text())
        s.setValue("connection/insecure", self.insecure.isChecked())
        s.setValue("connection/ca_cert", self.ca_cert.text())
        s.setValue("connection/http_timeout", self.http_timeout.value())
        s.setValue("sync/bucket", self.bucket.text())
        s.setValue("sync/continuous", self.continuous.isChecked())
        s.setValue("sync/resync", self.resync.value())
        s.setValue("sync/retry_delay", self.retry_delay.value())
        s.setValue("sync/stability_delay", self.stability_delay.value())
        s.setValue("sync/max_wait", self.max_wait.value())
        s.setValue("sync/ignore_delete", self.ignore_delete.isChecked())
        s.setValue("sync/filter_path", self.filter_path.text())
        s.setValue("sync/no_compression", self.no_compression.isChecked())
        s.setValue("sync/dry_run", self.dry_run.isChecked())
        s.setValue("lan/enabled", self.lan_mode.isChecked())
        s.setValue("lan/group", self.lan_group.text())
        s.setValue("lan/key", self.lan_key.text())
        s.setValue("lan/port", self.lan_port.value())
        s.setValue("lan/discovery_timeout", self.discovery_timeout.value())
        s.setValue("lan/https", self.lan_https.isChecked())
        s.setValue("lan/persistent", self.lan_persistent.isChecked())
        s.setValue("lan/force_master", self.force_master.isChecked())
        s.setValue("output/verbose", self.verbose.isChecked())
        s.setValue("output/quiet", self.quiet.isChecked())
        s.setValue("output/logfile", self.logfile.text())
        # Map translated theme names back to internal keys
        s.setValue("appearance/theme", THEME_DARK if self.theme_combo.currentIndex() == 1 else THEME_LIGHT)
        s.setValue("appearance/notifications", self.notifications_enabled.isChecked())
        # New fields
        lang_code = self.lang_combo.currentData()
        if lang_code:
            s.setValue("appearance/language", lang_code)
            set_language(lang_code)
        s.setValue("appearance/tooltips", self.tooltips_enabled.isChecked())
        s.setValue("appearance/show_log", self.show_log_panel.isChecked())
        s.setValue("settings/mode_advanced", self._advanced_mode.isChecked())

    def load(self) -> None:
        """Restore settings from QSettings."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.server_url.setText(str(s.value("connection/server_url", "", str)))
        self.api_key.setText(str(s.value("connection/api_key", "", str)))
        self.insecure.setChecked(bool(s.value("connection/insecure", False, bool)))
        self.ca_cert.setText(str(s.value("connection/ca_cert", "", str)))
        self.http_timeout.setValue(cast(int, s.value("connection/http_timeout", 30, int)))
        self.bucket.setText(str(s.value("sync/bucket", DEFAULT_BUCKET, str)))
        self.continuous.setChecked(bool(s.value("sync/continuous", True, bool)))  # default ON
        self.resync.setValue(cast(int, s.value("sync/resync", 0, int)))
        self.retry_delay.setValue(cast(int, s.value("sync/retry_delay", 5, int)))
        self.stability_delay.setValue(cast(int, s.value("sync/stability_delay", 0, int)))
        self.max_wait.setValue(cast(int, s.value("sync/max_wait", 120, int)))
        self.ignore_delete.setChecked(bool(s.value("sync/ignore_delete", True, bool)))  # default ON
        self.filter_path.setText(str(s.value("sync/filter_path", "", str)))
        self.no_compression.setChecked(bool(s.value("sync/no_compression", False, bool)))
        self.dry_run.setChecked(bool(s.value("sync/dry_run", False, bool)))
        self.lan_mode.setChecked(bool(s.value("lan/enabled", False, bool)))
        self.lan_group.setText(str(s.value("lan/group", DEFAULT_GROUP, str)))
        self.lan_key.setText(str(s.value("lan/key", "", str)))
        self.lan_port.setValue(cast(int, s.value("lan/port", 0, int)))
        self.discovery_timeout.setValue(cast(int, s.value("lan/discovery_timeout", 10, int)))
        self.lan_https.setChecked(bool(s.value("lan/https", True, bool)))
        self.lan_persistent.setChecked(bool(s.value("lan/persistent", True, bool)))
        self.force_master.setChecked(bool(s.value("lan/force_master", False, bool)))
        self.verbose.setChecked(bool(s.value("output/verbose", False, bool)))
        self.quiet.setChecked(bool(s.value("output/quiet", False, bool)))
        self.logfile.setText(str(s.value("output/logfile", "", str)))
        theme = s.value("appearance/theme", detect_system_theme(), str)
        self.theme_combo.setCurrentIndex(1 if theme == THEME_DARK else 0)
        self.notifications_enabled.setChecked(
            bool(s.value("appearance/notifications", True, bool))
        )
        # Language
        saved_lang = s.value("appearance/language", get_language(), str)
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == saved_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        # Tooltips
        self.tooltips_enabled.setChecked(bool(s.value("appearance/tooltips", True, bool)))
        # Show log panel (default: hidden)
        self.show_log_panel.setChecked(bool(s.value("appearance/show_log", False, bool)))
        # Mode
        advanced = s.value("settings/mode_advanced", False, bool)
        self._advanced_mode.setChecked(bool(advanced))
        self._advanced = bool(advanced)

    # ── Connection-active state management ────────────────────────────────

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
            self.bucket,
            self.continuous,
            self.ignore_delete,
            self.resync,
            self.retry_delay,
            self.stability_delay,
            self.max_wait,
            self.filter_path,
            self.no_compression,
            self.dry_run,
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
        ]

        # Combine all widgets that should be disabled
        all_disabled_widgets = connection_widgets + sync_widgets + lan_widgets

        for widget in all_disabled_widgets:
            widget.setEnabled(not active)
            # Set tooltip explaining why it's disabled
            if active:
                widget.setToolTip(disabled_tip)

        # Re-apply normal tooltips when connection is not active
        if not active:
            self._apply_tooltips()


# ─── Utility: build CLI args from QSettings ─────────────────────────────────

def build_hsync_args(local_path: str, force_dry_run: bool = False) -> list[str]:
    """Read persisted settings and return hsync CLI argument list.

    Args:
        local_path: The local directory path to sync.
        force_dry_run: If True, always add --dry-run flag regardless of settings.
    """
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    args: list[str] = []

    # Bucket – use default if not set
    bucket = s.value("sync/bucket", DEFAULT_BUCKET, str) or DEFAULT_BUCKET
    args += ["-b", bucket]

    # Path
    if local_path:
        args += ["-p", local_path]

    # Connection
    url = s.value("connection/server_url", "", str)
    if url:
        args += ["-s", url]
    if s.value("connection/insecure", False, bool):
        args.append("--insecure")
    ca = s.value("connection/ca_cert", "", str)
    if ca:
        args += ["--ca-cert", ca]
    args += ["--timeout", str(s.value("connection/http_timeout", 30, int))]

    # Sync
    if s.value("sync/continuous", True, bool):
        args.append("-w")
    resync = cast(int, s.value("sync/resync", 0, int))
    if resync > 0:
        args += ["-i", str(resync)]
    args += ["--retry-delay", str(s.value("sync/retry_delay", 5, int))]
    sd = cast(int, s.value("sync/stability_delay", 0, int))
    if sd > 0:
        args += ["--stability-delay", str(sd)]
    args += ["--max-wait-timeout", str(s.value("sync/max_wait", 120, int))]
    if s.value("sync/ignore_delete", True, bool):
        args.append("--ignore-delete")
    filter_path = s.value("sync/filter_path", "", str)
    if filter_path:
        args += ["--filter-path", filter_path]
    if s.value("sync/no_compression", False, bool):
        args.append("--no-compression")
    if force_dry_run or s.value("sync/dry_run", False, bool):
        args.append("-n")

    # LAN
    if s.value("lan/enabled", False, bool):
        args.append("--lan-mode")
        port = s.value("lan/port", 0, int)
        if port:
            args += ["--lan-port", str(port)]
        args += ["--discovery-timeout", str(s.value("lan/discovery_timeout", 10, int))]
        grp = s.value("lan/group", DEFAULT_GROUP, str) or DEFAULT_GROUP
        args += ["--lan-group", grp]
        if not s.value("lan/https", True, bool):
            args.append("--no-lan-https")
        if not s.value("lan/persistent", True, bool):
            args.append("--no-lan-persistent")
        if s.value("lan/force_master", False, bool):
            args.append("--force-master")

    # Output – always use --no-color for machine-friendly parsing
    args.append("--no-color")
    if s.value("output/verbose", False, bool):
        args.append("-v")
    if s.value("output/quiet", False, bool):
        args.append("-q")
    logfile = s.value("output/logfile", "", str)
    if logfile:
        args += ["-o", logfile]

    return args


def get_saved_theme() -> str:
    """Return the persisted theme name, defaulting to system theme."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    # Use system theme as default if no theme has been saved
    default_theme = detect_system_theme()
    return str(s.value("appearance/theme", default_theme, str))


def are_notifications_enabled() -> bool:
    """Return whether notifications are enabled."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("appearance/notifications", True, bool))


def is_log_panel_visible() -> bool:
    """Return whether the log panel should be visible (default: hidden)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return bool(s.value("appearance/show_log", False, bool))
