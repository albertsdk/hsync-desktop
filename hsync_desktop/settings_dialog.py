# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Settings dialog for HSYNC Desktop.

Organized into sections matching hsync-client CLI option groups:
Connection, Sync, LAN Mode, Output, Appearance, Notifications.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.themes import THEME_DARK, THEME_LIGHT

SETTINGS_ORG = "HSYNC"
SETTINGS_APP = "HSYNCDesktop"


def _spin(min_v: int, max_v: int, default: int, suffix: str = "") -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(min_v, max_v)
    sb.setValue(default)
    if suffix:
        sb.setSuffix(f" {suffix}")
    return sb


class SettingsDialog(QDialog):
    """Modal settings dialog with tabbed sections."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._build_ui()
        self.load()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._tab_connection(), "Connection")
        tabs.addTab(self._tab_sync(), "Sync")
        tabs.addTab(self._tab_lan(), "LAN Mode")
        tabs.addTab(self._tab_output(), "Output")
        tabs.addTab(self._tab_appearance(), "Appearance")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Tab: Connection ──────────────────────────────────────────────────

    def _tab_connection(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("https://server.example.com")
        form.addRow("Server URL:", self.server_url)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("(optional)")
        form.addRow("API Key:", self.api_key)
        self.insecure = QCheckBox("Skip SSL verification")
        form.addRow("", self.insecure)
        self.ca_cert = QLineEdit()
        self.ca_cert.setPlaceholderText("/path/to/ca.pem")
        form.addRow("CA Certificate:", self.ca_cert)
        self.http_timeout = _spin(1, 300, 30, "s")
        form.addRow("HTTP Timeout:", self.http_timeout)
        return w

    # ── Tab: Sync ────────────────────────────────────────────────────────

    def _tab_sync(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.bucket = QLineEdit()
        self.bucket.setPlaceholderText("my-bucket")
        form.addRow("Bucket:", self.bucket)
        self.continuous = QCheckBox("Watch for changes (continuous)")
        form.addRow("", self.continuous)
        self.compare_by = QComboBox()
        self.compare_by.addItems(["mtime", "ctime"])
        form.addRow("Compare by:", self.compare_by)
        self.resync = _spin(0, 3600, 0, "s")
        self.resync.setSpecialValueText("Disabled")
        form.addRow("Re-sync interval:", self.resync)
        self.retry_delay = _spin(1, 60, 5, "s")
        form.addRow("Retry delay:", self.retry_delay)
        self.stability_delay = _spin(0, 60, 0, "s")
        self.stability_delay.setSpecialValueText("Auto")
        form.addRow("Stability delay:", self.stability_delay)
        self.max_wait = _spin(10, 3600, 120, "s")
        form.addRow("Max wait timeout:", self.max_wait)
        self.ignore_delete = QCheckBox("Ignore deletions (backup mode)")
        form.addRow("", self.ignore_delete)
        self.no_compression = QCheckBox("Disable compression")
        form.addRow("", self.no_compression)
        self.dry_run = QCheckBox("Dry run (no changes)")
        form.addRow("", self.dry_run)
        return w

    # ── Tab: LAN Mode ────────────────────────────────────────────────────

    def _tab_lan(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.lan_mode = QCheckBox("Enable LAN P2P mode")
        form.addRow("", self.lan_mode)
        self.lan_group = QLineEdit()
        self.lan_group.setPlaceholderText("(optional)")
        form.addRow("Group:", self.lan_group)
        self.lan_key = QLineEdit()
        self.lan_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.lan_key.setPlaceholderText("(optional)")
        form.addRow("Shared Secret:", self.lan_key)
        self.lan_port = _spin(0, 65535, 0)
        self.lan_port.setSpecialValueText("Auto")
        form.addRow("Port:", self.lan_port)
        self.discovery_timeout = _spin(1, 120, 10, "s")
        form.addRow("Discovery timeout:", self.discovery_timeout)
        self.lan_https = QCheckBox("Use HTTPS")
        self.lan_https.setChecked(True)
        form.addRow("", self.lan_https)
        self.lan_persistent = QCheckBox("Persistent mode")
        self.lan_persistent.setChecked(True)
        form.addRow("", self.lan_persistent)
        return w

    # ── Tab: Output ──────────────────────────────────────────────────────

    def _tab_output(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.verbose = QCheckBox("Verbose (debug) output")
        form.addRow("", self.verbose)
        self.quiet = QCheckBox("Quiet (suppress output)")
        form.addRow("", self.quiet)
        self.logfile = QLineEdit()
        self.logfile.setPlaceholderText("/path/to/logfile.log")
        form.addRow("Log file:", self.logfile)
        return w

    # ── Tab: Appearance ──────────────────────────────────────────────────

    def _tab_appearance(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        form.addRow("Theme:", self.theme_combo)
        self.notifications_enabled = QCheckBox("Enable desktop notifications")
        self.notifications_enabled.setChecked(True)
        form.addRow("", self.notifications_enabled)
        return w

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
        s.setValue("sync/compare_by", self.compare_by.currentText())
        s.setValue("sync/resync", self.resync.value())
        s.setValue("sync/retry_delay", self.retry_delay.value())
        s.setValue("sync/stability_delay", self.stability_delay.value())
        s.setValue("sync/max_wait", self.max_wait.value())
        s.setValue("sync/ignore_delete", self.ignore_delete.isChecked())
        s.setValue("sync/no_compression", self.no_compression.isChecked())
        s.setValue("sync/dry_run", self.dry_run.isChecked())
        s.setValue("lan/enabled", self.lan_mode.isChecked())
        s.setValue("lan/group", self.lan_group.text())
        s.setValue("lan/key", self.lan_key.text())
        s.setValue("lan/port", self.lan_port.value())
        s.setValue("lan/discovery_timeout", self.discovery_timeout.value())
        s.setValue("lan/https", self.lan_https.isChecked())
        s.setValue("lan/persistent", self.lan_persistent.isChecked())
        s.setValue("output/verbose", self.verbose.isChecked())
        s.setValue("output/quiet", self.quiet.isChecked())
        s.setValue("output/logfile", self.logfile.text())
        s.setValue("appearance/theme", self.theme_combo.currentText().lower())
        s.setValue("appearance/notifications", self.notifications_enabled.isChecked())

    def load(self) -> None:
        """Restore settings from QSettings."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.server_url.setText(s.value("connection/server_url", "", str))
        self.api_key.setText(s.value("connection/api_key", "", str))
        self.insecure.setChecked(s.value("connection/insecure", False, bool))
        self.ca_cert.setText(s.value("connection/ca_cert", "", str))
        self.http_timeout.setValue(s.value("connection/http_timeout", 30, int))
        self.bucket.setText(s.value("sync/bucket", "", str))
        self.continuous.setChecked(s.value("sync/continuous", False, bool))
        idx = self.compare_by.findText(s.value("sync/compare_by", "mtime", str))
        if idx >= 0:
            self.compare_by.setCurrentIndex(idx)
        self.resync.setValue(s.value("sync/resync", 0, int))
        self.retry_delay.setValue(s.value("sync/retry_delay", 5, int))
        self.stability_delay.setValue(s.value("sync/stability_delay", 0, int))
        self.max_wait.setValue(s.value("sync/max_wait", 120, int))
        self.ignore_delete.setChecked(s.value("sync/ignore_delete", False, bool))
        self.no_compression.setChecked(s.value("sync/no_compression", False, bool))
        self.dry_run.setChecked(s.value("sync/dry_run", False, bool))
        self.lan_mode.setChecked(s.value("lan/enabled", False, bool))
        self.lan_group.setText(s.value("lan/group", "", str))
        self.lan_key.setText(s.value("lan/key", "", str))
        self.lan_port.setValue(s.value("lan/port", 0, int))
        self.discovery_timeout.setValue(s.value("lan/discovery_timeout", 10, int))
        self.lan_https.setChecked(s.value("lan/https", True, bool))
        self.lan_persistent.setChecked(s.value("lan/persistent", True, bool))
        self.verbose.setChecked(s.value("output/verbose", False, bool))
        self.quiet.setChecked(s.value("output/quiet", False, bool))
        self.logfile.setText(s.value("output/logfile", "", str))
        theme = s.value("appearance/theme", THEME_LIGHT, str)
        idx = 1 if theme == THEME_DARK else 0
        self.theme_combo.setCurrentIndex(idx)
        self.notifications_enabled.setChecked(
            s.value("appearance/notifications", True, bool)
        )


# ─── Utility: build CLI args from QSettings ─────────────────────────────────

def build_hsync_args(local_path: str) -> list[str]:
    """Read persisted settings and return hsync CLI argument list."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    args: list[str] = []

    bucket = s.value("sync/bucket", "", str)
    if not bucket:
        return args  # nothing to do without a bucket
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
    if s.value("sync/continuous", False, bool):
        args.append("-w")
    args += ["--compare-by", s.value("sync/compare_by", "mtime", str)]
    resync = s.value("sync/resync", 0, int)
    if resync > 0:
        args += ["-i", str(resync)]
    args += ["--retry-delay", str(s.value("sync/retry_delay", 5, int))]
    sd = s.value("sync/stability_delay", 0, int)
    if sd > 0:
        args += ["--stability-delay", str(sd)]
    args += ["--max-wait-timeout", str(s.value("sync/max_wait", 120, int))]
    if s.value("sync/ignore_delete", False, bool):
        args.append("--ignore-delete")
    if s.value("sync/no_compression", False, bool):
        args.append("--no-compression")
    if s.value("sync/dry_run", False, bool):
        args.append("-n")

    # LAN
    if s.value("lan/enabled", False, bool):
        args.append("--lan-mode")
        port = s.value("lan/port", 0, int)
        if port:
            args += ["--lan-port", str(port)]
        args += ["--discovery-timeout", str(s.value("lan/discovery_timeout", 10, int))]
        grp = s.value("lan/group", "", str)
        if grp:
            args += ["--lan-group", grp]
        if not s.value("lan/https", True, bool):
            args.append("--no-lan-https")
        if not s.value("lan/persistent", True, bool):
            args.append("--no-lan-persistent")

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
    """Return the persisted theme name."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return s.value("appearance/theme", THEME_LIGHT, str)


def are_notifications_enabled() -> bool:
    """Return whether notifications are enabled."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return s.value("appearance/notifications", True, bool)
