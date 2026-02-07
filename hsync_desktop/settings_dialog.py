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
"""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT

SETTINGS_ORG = "HSYNC"
SETTINGS_APP = "HSYNCDesktop"

# Default values
DEFAULT_BUCKET = "my-bucket"
DEFAULT_GROUP = "my-group"


def _spin(min_v: int, max_v: int, default: int, suffix: str = "") -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(min_v, max_v)
    sb.setValue(default)
    if suffix:
        sb.setSuffix(f" {suffix}")
    return sb


def _maybe_tip(widget: QWidget, key: str, enabled: bool) -> None:
    """Set tooltip on *widget* from i18n *key* only when *enabled*."""
    widget.setToolTip(tr(key) if enabled else "")


class SettingsDialog(QDialog):
    """Modal settings dialog with tabbed sections."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(520)
        self._advanced = False  # Start in default mode
        self._advanced_widgets: list[tuple[QWidget, QWidget | None]] = []
        self._build_ui()
        self.load()
        self._apply_mode()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Mode toggle row
        mode_row = QHBoxLayout()
        mode_row.addStretch()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([tr("settings.mode_default"), tr("settings.mode_advanced")])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(QLabel("Mode:"))
        mode_row.addWidget(self._mode_combo)
        layout.addLayout(mode_row)

        self._tabs = QTabWidget()

        self._tabs.addTab(self._tab_connection(), icon("network-wired"), tr("settings.connection"))
        self._tabs.addTab(self._tab_sync(), icon("emblem-synchronizing"), tr("settings.sync"))
        self._tabs.addTab(self._tab_lan(), icon("network-workgroup"), tr("settings.lan"))
        self._tabs.addTab(self._tab_log(), icon("utilities-log-viewer"), tr("settings.log"))
        self._tabs.addTab(self._tab_appearance(), icon("preferences-desktop-theme"), tr("settings.appearance"))

        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Mode toggle ─────────────────────────────────────────────────────

    def _on_mode_changed(self, index: int) -> None:
        self._advanced = index == 1
        self._apply_mode()

    def _apply_mode(self) -> None:
        for widget, label in self._advanced_widgets:
            widget.setVisible(self._advanced)
            if label is not None:
                label.setVisible(self._advanced)

    def _mark_advanced(self, form: QFormLayout, widget: QWidget) -> None:
        """Mark the last row added to *form* as advanced-only."""
        row = form.rowCount() - 1
        label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        label_w = label_item.widget() if label_item else None
        self._advanced_widgets.append((widget, label_w))

    # ── Tab: Connection ──────────────────────────────────────────────────

    def _tab_connection(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        tips = self._tips_enabled()

        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("https://server.example.com")
        form.addRow(tr("settings.server_url"), self.server_url)
        _maybe_tip(self.server_url, "tip.server_url", tips)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("(optional)")
        form.addRow(tr("settings.api_key"), self.api_key)
        _maybe_tip(self.api_key, "tip.api_key", tips)

        self.insecure = QCheckBox(tr("settings.insecure"))
        form.addRow("", self.insecure)
        _maybe_tip(self.insecure, "tip.insecure", tips)
        self._mark_advanced(form, self.insecure)

        self.ca_cert = QLineEdit()
        self.ca_cert.setPlaceholderText("/path/to/ca.pem")
        form.addRow(tr("settings.ca_cert"), self.ca_cert)
        _maybe_tip(self.ca_cert, "tip.ca_cert", tips)
        self._mark_advanced(form, self.ca_cert)

        self.http_timeout = _spin(1, 300, 30, "s")
        form.addRow(tr("settings.http_timeout"), self.http_timeout)
        _maybe_tip(self.http_timeout, "tip.http_timeout", tips)
        self._mark_advanced(form, self.http_timeout)
        return w

    # ── Tab: Sync ────────────────────────────────────────────────────────

    def _tab_sync(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        tips = self._tips_enabled()

        self.bucket = QLineEdit()
        self.bucket.setPlaceholderText(DEFAULT_BUCKET)
        form.addRow(tr("settings.bucket"), self.bucket)
        _maybe_tip(self.bucket, "tip.bucket", tips)

        self.continuous = QCheckBox(tr("settings.watch"))
        form.addRow("", self.continuous)
        _maybe_tip(self.continuous, "tip.watch", tips)

        self.ignore_delete = QCheckBox(tr("settings.ignore_delete"))
        self.ignore_delete.toggled.connect(self._on_ignore_delete_toggled)
        form.addRow("", self.ignore_delete)
        _maybe_tip(self.ignore_delete, "tip.ignore_delete", tips)

        self.resync = _spin(0, 3600, 0, "s")
        self.resync.setSpecialValueText("Disabled")
        form.addRow(tr("settings.resync"), self.resync)
        _maybe_tip(self.resync, "tip.resync", tips)
        self._mark_advanced(form, self.resync)

        self.retry_delay = _spin(1, 60, 5, "s")
        form.addRow(tr("settings.retry_delay"), self.retry_delay)
        _maybe_tip(self.retry_delay, "tip.retry_delay", tips)
        self._mark_advanced(form, self.retry_delay)

        self.stability_delay = _spin(0, 60, 0, "s")
        self.stability_delay.setSpecialValueText("Auto")
        form.addRow(tr("settings.stability_delay"), self.stability_delay)
        _maybe_tip(self.stability_delay, "tip.stability_delay", tips)
        self._mark_advanced(form, self.stability_delay)

        self.max_wait = _spin(10, 3600, 120, "s")
        form.addRow(tr("settings.max_wait"), self.max_wait)
        _maybe_tip(self.max_wait, "tip.max_wait", tips)
        self._mark_advanced(form, self.max_wait)

        self.filter_path = QLineEdit()
        self.filter_path.setPlaceholderText("(optional)")
        form.addRow(tr("settings.filter_path"), self.filter_path)
        _maybe_tip(self.filter_path, "tip.filter_path", tips)
        self._mark_advanced(form, self.filter_path)

        self.no_compression = QCheckBox(tr("settings.no_compression"))
        form.addRow("", self.no_compression)
        _maybe_tip(self.no_compression, "tip.no_compression", tips)
        self._mark_advanced(form, self.no_compression)

        self.dry_run = QCheckBox(tr("settings.dry_run"))
        form.addRow("", self.dry_run)
        _maybe_tip(self.dry_run, "tip.dry_run", tips)
        self._mark_advanced(form, self.dry_run)
        return w

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

    # ── Tab: LAN Mode ────────────────────────────────────────────────────

    def _tab_lan(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        tips = self._tips_enabled()

        self.lan_mode = QCheckBox(tr("settings.lan_mode"))
        form.addRow("", self.lan_mode)
        _maybe_tip(self.lan_mode, "tip.lan_mode", tips)

        self.lan_group = QLineEdit()
        self.lan_group.setPlaceholderText(DEFAULT_GROUP)
        form.addRow(tr("settings.lan_group"), self.lan_group)
        _maybe_tip(self.lan_group, "tip.lan_group", tips)

        self.lan_key = QLineEdit()
        self.lan_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.lan_key.setPlaceholderText("(optional)")
        form.addRow(tr("settings.lan_key"), self.lan_key)
        _maybe_tip(self.lan_key, "tip.lan_key", tips)

        self.lan_port = _spin(0, 65535, 0)
        self.lan_port.setSpecialValueText("Auto")
        form.addRow(tr("settings.lan_port"), self.lan_port)
        _maybe_tip(self.lan_port, "tip.lan_port", tips)
        self._mark_advanced(form, self.lan_port)

        self.discovery_timeout = _spin(1, 120, 10, "s")
        form.addRow(tr("settings.discovery_timeout"), self.discovery_timeout)
        _maybe_tip(self.discovery_timeout, "tip.discovery_timeout", tips)
        self._mark_advanced(form, self.discovery_timeout)

        self.lan_https = QCheckBox(tr("settings.lan_https"))
        self.lan_https.setChecked(True)
        form.addRow("", self.lan_https)
        _maybe_tip(self.lan_https, "tip.lan_https", tips)
        self._mark_advanced(form, self.lan_https)

        self.lan_persistent = QCheckBox(tr("settings.lan_persistent"))
        self.lan_persistent.setChecked(True)
        form.addRow("", self.lan_persistent)
        _maybe_tip(self.lan_persistent, "tip.lan_persistent", tips)
        self._mark_advanced(form, self.lan_persistent)
        return w

    # ── Tab: Log (formerly Output) ───────────────────────────────────────

    def _tab_log(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        tips = self._tips_enabled()

        self.verbose = QCheckBox(tr("settings.verbose"))
        form.addRow("", self.verbose)
        _maybe_tip(self.verbose, "tip.verbose", tips)

        self.quiet = QCheckBox(tr("settings.quiet"))
        form.addRow("", self.quiet)
        _maybe_tip(self.quiet, "tip.quiet", tips)
        self._mark_advanced(form, self.quiet)

        self.logfile = QLineEdit()
        self.logfile.setPlaceholderText("/path/to/logfile.log")
        form.addRow(tr("settings.logfile"), self.logfile)
        _maybe_tip(self.logfile, "tip.logfile", tips)
        self._mark_advanced(form, self.logfile)
        return w

    # ── Tab: Appearance ──────────────────────────────────────────────────

    def _tab_appearance(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        tips = self._tips_enabled()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems([tr("settings.theme_light"), tr("settings.theme_dark")])
        form.addRow(tr("settings.theme"), self.theme_combo)
        _maybe_tip(self.theme_combo, "tip.theme", tips)

        self.lang_combo = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        form.addRow(tr("settings.language"), self.lang_combo)
        _maybe_tip(self.lang_combo, "tip.language", tips)

        self.notifications_enabled = QCheckBox(tr("settings.notifications"))
        self.notifications_enabled.setChecked(True)
        form.addRow("", self.notifications_enabled)
        _maybe_tip(self.notifications_enabled, "tip.notifications", tips)

        self.tooltips_enabled = QCheckBox(tr("settings.tooltips"))
        self.tooltips_enabled.setChecked(True)
        form.addRow("", self.tooltips_enabled)
        _maybe_tip(self.tooltips_enabled, "tip.tooltips", tips)
        return w

    # ── Helpers ───────────────────────────────────────────────────────────

    def _tips_enabled(self) -> bool:
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        return s.value("appearance/tooltips", True, bool)

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
        s.setValue("settings/mode_advanced", self._mode_combo.currentIndex() == 1)

    def load(self) -> None:
        """Restore settings from QSettings."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.server_url.setText(s.value("connection/server_url", "", str))
        self.api_key.setText(s.value("connection/api_key", "", str))
        self.insecure.setChecked(s.value("connection/insecure", False, bool))
        self.ca_cert.setText(s.value("connection/ca_cert", "", str))
        self.http_timeout.setValue(s.value("connection/http_timeout", 30, int))
        self.bucket.setText(s.value("sync/bucket", DEFAULT_BUCKET, str))
        self.continuous.setChecked(s.value("sync/continuous", True, bool))  # default ON
        self.resync.setValue(s.value("sync/resync", 0, int))
        self.retry_delay.setValue(s.value("sync/retry_delay", 5, int))
        self.stability_delay.setValue(s.value("sync/stability_delay", 0, int))
        self.max_wait.setValue(s.value("sync/max_wait", 120, int))
        self.ignore_delete.setChecked(s.value("sync/ignore_delete", True, bool))  # default ON
        self.filter_path.setText(s.value("sync/filter_path", "", str))
        self.no_compression.setChecked(s.value("sync/no_compression", False, bool))
        self.dry_run.setChecked(s.value("sync/dry_run", False, bool))
        self.lan_mode.setChecked(s.value("lan/enabled", False, bool))
        self.lan_group.setText(s.value("lan/group", DEFAULT_GROUP, str))
        self.lan_key.setText(s.value("lan/key", "", str))
        self.lan_port.setValue(s.value("lan/port", 0, int))
        self.discovery_timeout.setValue(s.value("lan/discovery_timeout", 10, int))
        self.lan_https.setChecked(s.value("lan/https", True, bool))
        self.lan_persistent.setChecked(s.value("lan/persistent", True, bool))
        self.verbose.setChecked(s.value("output/verbose", False, bool))
        self.quiet.setChecked(s.value("output/quiet", False, bool))
        self.logfile.setText(s.value("output/logfile", "", str))
        theme = s.value("appearance/theme", THEME_LIGHT, str)
        self.theme_combo.setCurrentIndex(1 if theme == THEME_DARK else 0)
        self.notifications_enabled.setChecked(
            s.value("appearance/notifications", True, bool)
        )
        # Language
        saved_lang = s.value("appearance/language", get_language(), str)
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == saved_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        # Tooltips
        self.tooltips_enabled.setChecked(s.value("appearance/tooltips", True, bool))
        # Mode
        advanced = s.value("settings/mode_advanced", False, bool)
        self._mode_combo.setCurrentIndex(1 if advanced else 0)
        self._advanced = advanced


# ─── Utility: build CLI args from QSettings ─────────────────────────────────

def build_hsync_args(local_path: str) -> list[str]:
    """Read persisted settings and return hsync CLI argument list."""
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
    resync = s.value("sync/resync", 0, int)
    if resync > 0:
        args += ["-i", str(resync)]
    args += ["--retry-delay", str(s.value("sync/retry_delay", 5, int))]
    sd = s.value("sync/stability_delay", 0, int)
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
    if s.value("sync/dry_run", False, bool):
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
