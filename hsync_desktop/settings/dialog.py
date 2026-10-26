# mypy: disable-error-code="attr-defined"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
SettingsDialog for HSYNC Desktop.

The API-key / p2p-key prompts live in credential_dialogs.py and the
.hsyncignore editor in hsyncignore_dialog.py.
"""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import cast

from hsync_common.constants import HSYNCIGNORE_FILENAME
from hsync_common.endpoint import parse_host_port
from hsync_common.protocol.boot_tokens import (
    WeakGroupPassphrase,
    validate_group_passphrase,
)
from hsync_common.protocol.capabilities import supports_cli_option, supports_subcommand
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QShowEvent
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

from hsync_desktop import autostart
from hsync_desktop.config import (
    DEFAULT_AUTO_SYNC,
    DEFAULT_AUTOTUNE,
    DEFAULT_BUCKET,
    DEFAULT_CA_CERT,
    DEFAULT_COMPRESSION_ENABLED,
    DEFAULT_CONTINUOUS,
    DEFAULT_DELTA_ENABLED,
    DEFAULT_DELTA_MIN_FILE_SIZE_KB,
    DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB,
    DEFAULT_DISCOVERY_TIMEOUT,
    DEFAULT_DRY_RUN,
    DEFAULT_FILTER_PATH,
    DEFAULT_FONT_SCALE,
    DEFAULT_GROUP,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_IGNORE_DELETE,
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
    DEFAULT_NOTIFICATIONS,
    DEFAULT_NTP_HOSTS,
    DEFAULT_P2P_BOOTNODE,
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_P2P_ENABLED,
    DEFAULT_P2P_KEY,
    DEFAULT_P2P_PEER_DOWNLOAD,
    DEFAULT_P2P_PEER_READ_CAP,
    DEFAULT_P2P_PEER_SOURCES_MAX,
    DEFAULT_P2P_PORT,
    DEFAULT_P2P_REQUIRE_PAIRING,
    DEFAULT_P2P_UPNP_ENABLED,
    DEFAULT_PREFER_MASTER,
    DEFAULT_QUIET,
    DEFAULT_RESYNC_INTERVAL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SERVER_TRUST,
    DEFAULT_SHOW_LOG_PANEL,
    DEFAULT_STABILITY_DELAY,
    DEFAULT_START_AT_LOGIN,
    DEFAULT_SYNC_DIRECTION,
    DEFAULT_TOOLTIPS,
    DEFAULT_VERBOSE,
    MIN_RESYNC_INTERVAL,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.crypto import decrypt_value, encrypt_value
from hsync_desktop.engine import (
    build_probe_ssl_context,
    fetch_bootnode_fingerprint,
    find_hsync_binary,
    get_binary_capabilities_cached,
    normalize_bootnode_endpoint,
    normalize_server_endpoint,
    p2p_secret_mode,
    probe_server_health,
)
from hsync_desktop.i18n import (
    AUTO_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_language,
    set_language,
    tr,
)
from hsync_desktop.icons import icon, style_ok_cancel_button_box
from hsync_desktop.settings.cli_args import (
    get_bandwidth_limits,
    save_bandwidth_limits,
    secure_config_file,
)
from hsync_desktop.settings.form_helpers import (
    _action_row,
    _insert_row_after,
    _maybe_tip,
    _paired_label,
    _replace_checkbox_with_toggle,
    _set_field_tooltip,
)
from hsync_desktop.settings.hsyncignore_dialog import HsyncIgnoreEditorDialog
from hsync_desktop.settings.reset_state_dialog import ResetStateDialog
from hsync_desktop.settings.tab_builders import (
    build_advanced_tab,
    build_connection_banner,
    build_general_tab,
    build_p2p_tab,
    build_server_tab,
    build_sync_tab,
    finalize_size,
    fit_current_tab,
    set_tab_icons,
    setup_language_combo,
)
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
)
from hsync_desktop.settings.tab_layout import (
    reorganize_advanced_tab,
    reorganize_general_tab,
    reorganize_p2p_tab,
    reorganize_server_tab,
    reorganize_sync_tab,
)
from hsync_desktop.settings.tab_translations import apply_translations
from hsync_desktop.themes import THEME_DARK, THEME_LIGHT, THEME_SYSTEM
from hsync_desktop.trusted_keys import TrustedKeysDialog
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.dialogs import confirm
from hsync_desktop.widgets.toggle_switch import ToggleSwitch


class SettingsDialog(QDialog):
    """Modal settings dialog with tabbed sections."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Controls gated off by the binary's capabilities; never re-enabled
        # by the p2p-mode or connection-active state machines.
        self._unsupported_widgets: set[QWidget] = set()
        self._unsupported_labels: set[QLabel] = set()
        # Per-tab purpose labels; exempt from the label-greying state machines so
        # a disabled tab still says what it is for.
        self._tab_descriptions: dict[int, QLabel] = {}
        # Folder whose sync state the user asked to reset ("" = no request).
        self._reset_state_folder = ""
        # Snapshot of the stored p2p secret + its input mode, so save() can tell
        # an edited user password from an untouched legacy raw key.
        self._p2p_key_loaded = ""
        self._p2p_key_mode_loaded = "raw"

        self._load_ui()
        self.load()  # Load saved values BEFORE connecting signals
        self._connect_signals()  # Connect signals AFTER loading to avoid spurious events
        self._apply_capabilities()  # Gate controls the binary does not support

    # ── UI loading from .ui file ─────────────────────────────────────────

    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        load_ui_widget("settings_dialog", self)

        self._tabs: QTabWidget = self.findChild(QTabWidget, "tabWidget")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

        build_connection_banner(self)
        build_sync_tab(self)
        build_server_tab(self)
        build_p2p_tab(self)
        build_advanced_tab(self)
        build_general_tab(self)
        set_tab_icons(self)
        setup_language_combo(self)

        self._apply_translations()
        self._apply_tooltips()

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
        """Open the trust dialog on the bootnode tab (p2p panel button)."""
        TrustedKeysDialog(self, initial_tab="bootnodes").exec()

    def _open_server_trusted_keys(self) -> None:
        """Open the trust dialog on the server tab (server panel button)."""
        TrustedKeysDialog(self, initial_tab="servers").exec()

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

    def _reorganize_general_tab(self) -> None:
        """Regroup the General tab (implementation in ``tab_layout.py``)."""
        reorganize_general_tab(self)

    def _reorganize_sync_tab(self) -> None:
        """Regroup the Sync tab (implementation in ``tab_layout.py``)."""
        reorganize_sync_tab(self)

    def _reorganize_p2p_tab(self) -> None:
        """Regroup the p2p tab (implementation in ``tab_layout.py``)."""
        reorganize_p2p_tab(self)

    def _reorganize_server_tab(self) -> None:
        """Regroup the Server Mode tab (implementation in ``tab_layout.py``)."""
        reorganize_server_tab(self)

    def _reorganize_advanced_tab(self) -> None:
        """Regroup the Advanced tab (implementation in ``tab_layout.py``)."""
        reorganize_advanced_tab(self)

    def _apply_translations(self) -> None:
        """Apply i18n strings (implementation in ``tab_translations.py``)."""
        apply_translations(self)

    def _apply_tooltips(self) -> None:
        """Apply tooltips to widgets if enabled."""
        tips = self._tips_enabled()

        for widget, key in (
            (self.shared_path, "tip.shared_path"),
            (self.bucket, "tip.bucket"),
            (self.continuous, "tip.watch"),
            (self.ignore_delete, "tip.ignore_delete"),
            (self.sync_direction_combo, "tip.sync_direction"),
            (self.resync, "tip.resync"),
            (self.retry_delay, "tip.retry_delay"),
            (self.stability_delay, "tip.stability_delay"),
            (self.max_wait, "tip.max_wait"),
            (self.min_free_disk_space, "tip.min_free_disk_space"),
            (self.max_inbound_size, "tip.max_inbound_size"),
            (self.filter_path, "tip.filter_path"),
            (self.compression_enabled, "tip.compression_enabled"),
            (self.dry_run, "tip.dry_run"),
            (self.auto_sync, "tip.auto_sync"),
            (self.ignore_patterns, "tip.ignore_patterns"),
            (self.btn_edit_hsyncignore, "tip.edit_hsyncignore"),
            (self.btn_reset_state, "tip.reset_state"),
            (self.server_url, "tip.server_url"),
            (self.api_key, "tip.api_key"),
            (self.insecure, "tip.insecure"),
            (self.ca_cert, "tip.ca_cert"),
            (self.server_trust, "tip.server_trust"),
            (self.http_timeout, "tip.http_timeout"),
            (self.btn_manage_trusted_keys_server, "tip.manage_trusted_keys"),
            (self.p2p_mode, "tip.p2p_mode"),
            (self.p2p_group, "tip.p2p_group"),
            (self.p2p_bootnode, "tip.p2p_bootnode"),
            (self.p2p_bootnode_trust, "tip.p2p_bootnode_trust"),
            (self.btn_manage_trusted_keys, "tip.manage_trusted_keys"),
            (self.btn_test_bootnode, "tip.test_bootnode"),
            (self.p2p_upnp, "tip.p2p_upnp"),
            (self.p2p_key, "tip.p2p_key"),
            (self.p2p_port, "tip.p2p_port"),
            (self.discovery_timeout, "tip.discovery_timeout"),
            (self.ntp_hosts, "tip.ntp_hosts"),
            (self.prefer_master, "tip.prefer_master"),
            (self.never_master, "tip.never_master"),
            (self.require_pairing, "tip.require_pairing"),
            (self.peer_download, "tip.peer_download"),
            (self.peer_read_cap, "tip.peer_read_cap"),
            (self.peer_sources_max, "tip.peer_sources_max"),
            (self.autotune, "tip.autotune"),
            (self.max_concurrent_transfers, "tip.max_concurrent_transfers"),
            (self.delta_enabled, "tip.delta_enabled"),
            (self.delta_min_file_size, "tip.delta_min_file_size"),
            (self.delta_min_file_size_p2p, "tip.delta_min_file_size_p2p"),
            (self.mass_delete_guard, "tip.mass_delete_guard"),
            (self.mass_delete_threshold, "tip.mass_delete_threshold"),
            (self.mass_delete_percent, "tip.mass_delete_percent"),
            (self.bandwidth_upload, "tip.bandwidth_upload"),
            (self.bandwidth_download, "tip.bandwidth_download"),
            (self.verbose, "tip.verbose"),
            (self.quiet, "tip.quiet"),
            (self.logfile, "tip.logfile"),
            (self.lang_combo, "tip.language"),
            (self.theme_combo, "tip.theme"),
            (self.font_scale_combo, "tip.font_size"),
            (self.notifications_enabled, "tip.notifications"),
            (self._lbl_notifications_categories, "tip.notifications_categories"),
            (self.tooltips_enabled, "tip.tooltips"),
            (self.show_log_panel, "tip.show_log_panel"),
            (self.start_at_login, "tip.start_at_login"),
        ):
            _maybe_tip(widget, key, tips)
        # A disabled toggle on a platform without an autostart mechanism still
        # explains itself, overriding the normal tooltip cleared above.
        if not autostart.is_supported():
            _set_field_tooltip(self.start_at_login, tr("tip.start_at_login_unsupported"))

        # Capability-gated controls always explain why they are unavailable,
        # overriding any normal tooltip cleared above.
        for widget in self._unsupported_widgets:
            _set_field_tooltip(widget, tr("tip.capability_unsupported"))

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
            ("--prefer-master", self.prefer_master, self._lbl_prefer_master),
            ("--never-master", self.never_master, self._lbl_never_master),
            ("--require-pairing", self.require_pairing, self._lbl_require_pairing),
            ("--upnp", self.p2p_upnp, self._lbl_p2p_upnp),
        ]
        for flag, widget, label in gated:
            if p2p_supported and supports_cli_option(doc, flag, subcommand="p2p"):
                continue
            self._unsupported_widgets.add(widget)
            self._unsupported_labels.add(label)
            if widget.isChecked():
                widget.setChecked(False)
            widget.setEnabled(False)
            label.setEnabled(False)
            _set_field_tooltip(widget, tr("tip.capability_unsupported"))
        # The bootnode host field belongs to the bootnode discovery plan: gate it
        # on its ``--port`` flag (the positional is not in cli_options).
        if not (p2p_supported and supports_cli_option(doc, "--port", subcommand="p2p")):
            self._unsupported_widgets.add(self.p2p_bootnode)
            self._unsupported_labels.add(self._lbl_p2p_bootnode)
            self.p2p_bootnode.setEnabled(False)
            self._lbl_p2p_bootnode.setEnabled(False)
            _set_field_tooltip(self.p2p_bootnode, tr("tip.capability_unsupported"))
        if not p2p_supported:
            # The p2p subcommand itself is the master gate for the p2p tab.
            self._unsupported_widgets.add(self.p2p_mode)
            self._unsupported_labels.add(self._lbl_p2p_mode)
            if self.p2p_mode.isChecked():
                self.p2p_mode.setChecked(False)
            self.p2p_mode.setEnabled(False)
            self._lbl_p2p_mode.setEnabled(False)
            _set_field_tooltip(self.p2p_mode, tr("tip.capability_unsupported"))
        # Refresh dependent enable-state with the new gates in effect.
        self._on_p2p_mode_toggled(self.p2p_mode.isChecked())

        # Peer download is p2p-only: gate it (and its env-only caps) on the
        # --no-peer-download flag the p2p subcommand advertises.
        if not (p2p_supported and supports_cli_option(doc, "--no-peer-download", subcommand="p2p")):
            for peer_widget, peer_label in (
                (self.peer_download, self._lbl_peer_download),
                (self.peer_read_cap, self._lbl_peer_read_cap),
                (self.peer_sources_max, self._lbl_peer_sources_max),
            ):
                self._unsupported_widgets.add(peer_widget)
                self._unsupported_labels.add(peer_label)
                peer_widget.setEnabled(False)
                peer_label.setEnabled(False)
                _set_field_tooltip(peer_widget, tr("tip.capability_unsupported"))

        # Advanced tab: engine-wide knobs are advertised by both subcommands
        # (union check, subcommand=None). Disable a control the binary cannot
        # honour rather than emitting a flag it would reject.
        advanced_gated: list[tuple[str, QWidget, QLabel]] = [
            ("--no-autotune", self.autotune, self._lbl_autotune),
            (
                "--max-concurrent-transfers",
                self.max_concurrent_transfers,
                self._lbl_max_concurrent,
            ),
            ("--no-delta", self.delta_enabled, self._lbl_delta_enabled),
            ("--delta-min-file-size", self.delta_min_file_size, self._lbl_delta_min),
            (
                "--delta-min-file-size-p2p",
                self.delta_min_file_size_p2p,
                self._lbl_delta_min_p2p,
            ),
            ("--mass-delete-guard", self.mass_delete_guard, self._lbl_mass_delete_guard),
            ("--mass-delete-threshold", self.mass_delete_threshold, self._lbl_guard_threshold),
            ("--mass-delete-percent", self.mass_delete_percent, self._lbl_guard_percent),
            ("--limit-upload", self.bandwidth_upload, self._lbl_bandwidth_upload),
            ("--limit-download", self.bandwidth_download, self._lbl_bandwidth_download),
        ]
        for adv_flag, adv_widget, adv_label in advanced_gated:
            if supports_cli_option(doc, adv_flag):
                continue
            self._unsupported_widgets.add(adv_widget)
            self._unsupported_labels.add(adv_label)
            adv_widget.setEnabled(False)
            adv_label.setEnabled(False)
            _set_field_tooltip(adv_widget, tr("tip.capability_unsupported"))

        # Sync-state reset: the maintenance ``state`` subcommand is the gate (it
        # is introspected into the capabilities document, so an older bundled
        # binary simply hides the button).
        if not supports_subcommand(doc, "state"):
            self._unsupported_widgets.add(self.btn_reset_state)
            self.btn_reset_state.setEnabled(False)
            _set_field_tooltip(self.btn_reset_state, tr("tip.capability_unsupported"))

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.ignore_delete.toggled.connect(self._on_ignore_delete_toggled)
        self.btn_browse_shared.clicked.connect(self._on_browse_shared)
        self.p2p_mode.toggled.connect(self._on_p2p_mode_toggled)
        self.prefer_master.toggled.connect(self._on_prefer_master_toggled)
        self.never_master.toggled.connect(self._on_never_master_toggled)
        self.verbose.toggled.connect(self._on_verbose_toggled)
        self.show_advanced.toggled.connect(self._on_show_advanced_toggled)
        self.sync_direction_combo.currentIndexChanged.connect(self._on_sync_direction_changed)
        self.btn_test_connection.clicked.connect(self._on_test_connection)
        self.btn_edit_hsyncignore.clicked.connect(self._on_edit_hsyncignore)
        self.btn_reset_state.clicked.connect(self._on_reset_state)
        self.resync.valueChanged.connect(self._normalize_resync)
        self._tabs.currentChanged.connect(self._fit_current_tab)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

    def showEvent(self, event: QShowEvent) -> None:
        """Fit the first visible tab after the initial layout settles."""
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_current_tab)

    def _fit_current_tab(self, _index: int | None = None) -> None:
        """Grow the dialog when the current tab would otherwise scroll."""
        fit_current_tab(self)

    def _normalize_resync(self, _value: int = 0) -> None:
        """Keep the periodic check disabled (0) or at least the client minimum."""
        value = self.resync.value()
        if 0 < value < MIN_RESYNC_INTERVAL:
            self.resync.blockSignals(True)
            self.resync.setValue(MIN_RESYNC_INTERVAL)
            self.resync.blockSignals(False)

    def _on_show_advanced_toggled(self, _checked: bool) -> None:
        """Reflect the advanced toggle immediately, then re-fit the dialog."""
        self._apply_advanced_visibility()
        finalize_size(self, allow_shrink=False)

    def _apply_advanced_visibility(self) -> None:
        """Show the Advanced tab and the advanced sections only when enabled."""
        show = self.show_advanced.isChecked()
        self._tabs.setTabVisible(_ADVANCED_TAB_INDEX, show)
        for group in (
            getattr(self, "_grp_advanced", None),
            getattr(self, "_grp_p2p_advanced", None),
            getattr(self, "_grp_server_certificates", None),
            getattr(self, "_grp_server_advanced", None),
        ):
            if group is not None:
                group.setVisible(show)
        if not show and self._tabs.currentIndex() == _ADVANCED_TAB_INDEX:
            self._tabs.setCurrentIndex(_GENERAL_TAB_INDEX)

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

    def _on_reset_state(self) -> None:
        """Confirm a sync-state reset and hand the request to the main window.

        The dialog never touches the state DB: the window owns the engine (so it
        knows whether a sync is running) and calls the client, which takes the
        folder's instance lock. Accepting closes the dialog so the window can
        report the outcome in the log.
        """
        shared = self.shared_path.text().strip()
        if not shared:
            QMessageBox.warning(
                self,
                tr("settings.reset_state.title"),
                tr("settings.reset_state.no_folder"),
            )
            return
        dialog = ResetStateDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        # Persist through the same validated path as OK, so closing as Accepted
        # never silently drops the session's edits; request the reset only once
        # the settings are really saved.
        if not self._commit():
            return
        self._reset_state_folder = shared
        self.accept()

    @property
    def reset_state_folder(self) -> str:
        """Folder whose sync state the user asked to reset (empty = none)."""
        return self._reset_state_folder

    def _on_ignore_delete_toggled(self, checked: bool) -> None:
        """Show a warning when the user disables ignore-delete."""
        if not checked:
            if not confirm(
                self,
                title=tr("warn.ignore_delete_title"),
                text=tr("warn.ignore_delete_msg"),
                icon_name=QMessageBox.Icon.Warning,
            ):
                self.ignore_delete.setChecked(True)

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
            self.server_trust,
            self.btn_manage_trusted_keys_server,
            self.btn_test_connection,
        ]
        for widget in server_widgets:
            widget.setEnabled(not checked)

        # Also disable the labels in the Server Mode tab
        self._set_tab_labels_enabled(
            _SERVER_TAB_INDEX,
            not checked,
            exclude=(self._p2p_banner_icon, self._p2p_banner_text),
        )

        # Enable/disable p2p tab widgets (except the p2p_mode toggle itself)
        p2p_sub_widgets: list[QWidget] = [
            self.p2p_group,
            self.p2p_bootnode,
            self.p2p_bootnode_trust,
            self.btn_manage_trusted_keys,
            self.btn_test_bootnode,
            self.p2p_upnp,
            self.p2p_key,
            self.p2p_port,
            self.discovery_timeout,
            self.ntp_hosts,
            self.prefer_master,
            self.never_master,
            self.require_pairing,
            self.peer_download,
            self.peer_read_cap,
            self.peer_sources_max,
        ]
        for widget in p2p_sub_widgets:
            widget.setEnabled(checked and widget not in self._unsupported_widgets)

        # Also enable/disable the labels in the p2p tab (except p2p_mode label)
        self._set_tab_labels_enabled(_P2P_TAB_INDEX, checked, exclude=(self._lbl_p2p_mode,))
        # The toggle's own label follows the toggle's availability, not the mode.
        self._lbl_p2p_mode.setEnabled(self._lbl_p2p_mode not in self._unsupported_labels)

    def _set_tab_labels_enabled(
        self, tab_index: int, enabled: bool, exclude: tuple[QWidget, ...] = ()
    ) -> None:
        """Gray/restore a tab's field labels so a disabled panel reads as disabled.

        Mirrors the widget enable state: the Server Mode tab grays its labels
        when p2p mode is active, so the Sync and p2p tabs gray theirs while a
        sync is running. Banner labels, the tab's purpose description and labels
        unavailable in this build are left untouched.
        """
        tab = self._tabs.widget(tab_index)
        if not tab:
            return
        description = self._tab_descriptions.get(tab_index)
        for label in tab.findChildren(QLabel):
            if label in exclude or label in self._unsupported_labels or label is description:
                continue
            label.setEnabled(enabled)

    def _on_prefer_master_toggled(self, checked: bool) -> None:
        """Prefer-master and never-master are mutually exclusive.

        Enabling prefer-master also meets the live incompatibility gate: with a
        non-bidirectional direction active, "Yes" returns the sync to
        bidirectional and jumps to the sync tab to review it.
        """
        if checked and self.never_master.isChecked():
            self.never_master.setChecked(False)
        if checked and self._prefer_master_conflict():
            proposed = self._maybe_warn_prefer_master(
                "warn.prefer_master_sync_msg",
                direction=self.sync_direction_combo.currentText(),
            )
            if proposed:
                self.sync_direction_combo.setCurrentIndex(0)
                self.set_current_tab(_SYNC_TAB_INDEX)
            else:
                # Keep the direction: prefer-master stays incompatible, so the
                # toggle must go back off (the invariant prefer-master =>
                # bidirectional must hold).
                self.prefer_master.setChecked(False)

    def _on_never_master_toggled(self, checked: bool) -> None:
        """Prefer-master and never-master are mutually exclusive."""
        if checked and self.prefer_master.isChecked():
            self.prefer_master.setChecked(False)

    def _set_notification_categories_enabled(self, enabled: bool) -> None:
        """Gate the per-event notification rows on the master switch.

        The category rows are plain form rows, so the master switch enables each
        caption and control instead of a container widget.
        """
        self._lbl_notifications_categories.setEnabled(enabled)
        for toggle, label in self.notification_toggles.values():
            label.setEnabled(enabled)
            toggle.setEnabled(enabled)

    def _on_verbose_toggled(self, checked: bool) -> None:
        """Offer to show the log panel when detailed logging would be invisible.

        Verbose output has nowhere to go while the log panel is hidden and no
        log file is configured. We do not block the option (file-only logging is
        legitimate) but offer to reveal the panel.
        """
        if not checked:
            return
        if self.show_log_panel.isChecked() or self.logfile.text().strip():
            return
        if confirm(
            self,
            title=tr("warn.verbose_no_log_title"),
            text=tr("warn.verbose_no_log_msg"),
            icon_name=QMessageBox.Icon.Question,
            default_yes=True,
        ):
            self.show_log_panel.setChecked(True)

    def _on_sync_direction_changed(self, _index: int) -> None:
        """Warn live when the picked direction conflicts with prefer-master.

        The fix here is disabling prefer-master (the user just chose the
        direction), so "Yes" turns the toggle off and jumps to the p2p tab.
        """
        if not self._prefer_master_conflict():
            return
        if self._maybe_warn_prefer_master("warn.prefer_master_disable_msg"):
            # Do not blockSignals here: ToggleSwitch paints from the thumb
            # animation driven by `toggled`, so swallowing it leaves the
            # switch drawn as ON while checked is False and the user's click
            # re-enables it, re-triggering this prompt in a loop.
            self.prefer_master.setChecked(False)
            self.set_current_tab(_P2P_TAB_INDEX)
        else:
            # Keep prefer-master: the primary device always syncs both ways, so
            # the incompatible direction must not stay selected.
            self.sync_direction_combo.setCurrentIndex(0)

    def _normalize_server_endpoint(self) -> str | None:
        """Canonicalize the server field, or raise ``ValueError``.

        Accepts the same forms as ``HSYNC_SERVER`` (bare ``host``/``host:port``/
        ``[IPv6]``/``[IPv6]:port`` or a full ``https://…`` URL) and returns the
        canonical HTTPS URL so ``_ensure_server_trust``/``urlsplit`` keep working.
        """
        return normalize_server_endpoint(self.server_url.text())

    def _normalize_bootnode_endpoint(self) -> str | None:
        """Canonicalize the bootnode field, or raise ``ValueError``."""
        return normalize_bootnode_endpoint(self.p2p_bootnode.text())

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
        self.btn_test_connection.setEnabled(False)
        self.btn_test_connection.setText("…")

        def _restore() -> None:
            self.btn_test_connection.setEnabled(True)

        self.btn_test_connection.setText(tr("settings.test_connection"))
        self.btn_test_bootnode.setText(tr("settings.test_connection"))

        result = probe_server_health(
            base,
            ssl_context=self._test_connection_ssl_context(),
            timeout=max(5, self.http_timeout.value()),
        )
        success = result.ok

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

    def _on_test_bootnode(self) -> None:
        """Verify the configured bootnode is reachable (probes its certificate)."""
        raw = self.p2p_bootnode.text().strip()
        if not raw:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_bootnode_no_host"),
            )
            return
        try:
            endpoint = parse_host_port(raw)
        except ValueError:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.invalid_bootnode_endpoint"),
            )
            return

        binary = find_hsync_binary()
        if not binary:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_bootnode_no_binary"),
            )
            return

        self.btn_test_bootnode.setEnabled(False)
        self.btn_test_bootnode.setText("…")

        def _restore() -> None:
            self.btn_test_bootnode.setEnabled(True)
            self.btn_test_bootnode.setText(tr("settings.test_connection"))

        # Contacting the bootnode reads its certificate fingerprint (no pin is
        # written); a value means the node answered, None means unreachable.
        fingerprint = fetch_bootnode_fingerprint(binary, endpoint.host, endpoint.port)
        _restore()

        if fingerprint:
            QMessageBox.information(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_bootnode_success").replace("{fingerprint}", fingerprint),
            )
        else:
            QMessageBox.warning(
                self,
                tr("settings.test_connection_title"),
                tr("settings.test_bootnode_failure"),
            )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _test_connection_ssl_context(self) -> ssl.SSLContext:
        """SSL context for the Test Connection probe, honouring TLS settings.

        Delegates to the shared policy helper so the Settings probe and the setup
        wizard agree on the certificate handling.
        """
        return build_probe_ssl_context(
            insecure=self.insecure.isChecked(),
            trust_policy=self.server_trust.currentData(),
            ca_cert=self.ca_cert.text().strip(),
        )

    def _tips_enabled(self) -> bool:
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        return bool(s.value("appearance/tooltips", True, bool))

    # ── Save / Load ──────────────────────────────────────────────────────

    def _prefer_master_conflict(self) -> bool:
        """True when an active prefer-master meets a non-bidirectional direction.

        `--prefer-master` is only emitted in p2p mode, so the conflict exists
        only while the p2p toggle is on (consumed by `_on_accept` and by the
        live direction check).
        """
        direction = self.sync_direction_combo.currentData() or DEFAULT_SYNC_DIRECTION
        return (
            self.p2p_mode.isChecked()
            and self.prefer_master.isChecked()
            and direction != "bidirectional"
        )

    def _maybe_warn_prefer_master(self, msg_key: str, **fmt: str) -> bool:
        """Show the prefer-master/directional-sync warning for ``msg_key``.

        The message differs by trigger (direction changed vs prefer-master
        enabled) but the outcome is the same: True when the user accepts the
        proposed fix. ``fmt`` fills the placeholders of the localized message
        (e.g. the active direction label). Shared by the save gate and both
        live checks.
        """
        text = tr(msg_key).format(**fmt) if fmt else tr(msg_key)
        return confirm(
            self,
            title=tr("warn.prefer_master_title"),
            text=text,
            default_yes=True,
        )

    def _on_accept(self) -> None:
        """Validate and persist the dialog, then close it as Accepted."""
        if not self._commit():
            return  # Go back to dialog
        self.accept()

    def _effective_p2p_key_mode(self) -> str:
        """Persist the input mode the current field value needs.

        An edited field is a user password (the existing contract). An untouched
        one keeps its stored mode, normalised by
        `engine.process.p2p_secret_mode`: a secret below the client's raw-key
        floor cannot be a group key, so it is a shared password. That also
        repairs legacy installs whose short secret was stored as ``raw`` before
        passphrases existed, instead of leaving them to the engine's startup
        error.
        """
        secret = self.p2p_key.text().strip()
        if not secret:
            return self._p2p_key_mode_loaded
        stored = "passphrase" if secret != self._p2p_key_loaded else self._p2p_key_mode_loaded
        return p2p_secret_mode(secret, stored)

    def _commit(self) -> bool:
        """Validate every field and persist; False when a check vetoes.

        Shared by the OK button and the sync-state reset, so both leave the
        dialog through the same validated path: neither may close as Accepted
        (which makes the window re-apply the settings) without saving.
        """
        # Validate: prefer-master is incompatible with directional sync
        if self._prefer_master_conflict():
            if not self._maybe_warn_prefer_master("warn.prefer_master_msg"):
                return False  # Go back to dialog
            # Reset to bidirectional and continue saving
            self.sync_direction_combo.setCurrentIndex(0)
        # Validate: the API key is never sent over an unencrypted channel.
        if not self._confirm_insecure_api_key():
            return False  # Go back to dialog
        # Validate + normalize the server and bootnode endpoints (shared grammar).
        try:
            normalized_server = self._normalize_server_endpoint()
        except ValueError:
            QMessageBox.warning(self, tr("settings.title"), tr("settings.invalid_server_endpoint"))
            return False
        try:
            normalized_bootnode = self._normalize_bootnode_endpoint()
        except ValueError:
            QMessageBox.warning(
                self, tr("settings.title"), tr("settings.invalid_bootnode_endpoint")
            )
            return False
        if normalized_server is not None:
            self.server_url.setText(normalized_server)
        if normalized_bootnode is not None:
            self.p2p_bootnode.setText(normalized_bootnode)
        # Validate: the OS login item must match the toggle before persisting.
        if not self._apply_start_at_login():
            return False  # Go back to dialog
        # Validate a user-typed p2p password (the raw-key path is enforced by
        # the engine's 32-char floor and stays untouched for legacy installs).
        if self.p2p_mode.isChecked():
            password = self.p2p_key.text().strip()
            if password and self._effective_p2p_key_mode() == "passphrase":
                try:
                    validate_group_passphrase(password)
                except WeakGroupPassphrase as exc:
                    QMessageBox.warning(
                        self,
                        tr("settings.title"),
                        tr(f"p2pauth.error.{exc.code}"),
                    )
                    return False
        self.save()
        return True

    def _apply_start_at_login(self) -> bool:
        """Register/unregister the OS login item to match the toggle.

        Returns True when the requested state is applied (or the platform has
        no autostart mechanism). On failure shows a warning, restores the
        toggle to the real state, and returns False so the dialog stays open
        and nothing is persisted.
        """
        if not autostart.is_supported():
            return True
        desired = self.start_at_login.isChecked()
        try:
            autostart.set_enabled(desired)
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("settings.title"),
                tr("warn.start_at_login_failed").format(error=exc),
            )
            self.start_at_login.setChecked(autostart.is_enabled())
            return False
        return True

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
        return confirm(
            self,
            title=tr("warn.api_key_insecure_title"),
            text=tr("warn.api_key_insecure_msg"),
        )

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
        self._normalize_resync()
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
        # Advanced tab (engine tuning)
        s.setValue("advanced/autotune", self.autotune.isChecked())
        s.setValue("advanced/max_concurrent_transfers", self.max_concurrent_transfers.value())
        s.setValue("advanced/delta_enabled", self.delta_enabled.isChecked())
        s.setValue("advanced/delta_min_file_size_kb", self.delta_min_file_size.value())
        s.setValue("advanced/delta_min_file_size_p2p_kb", self.delta_min_file_size_p2p.value())
        s.setValue("advanced/mass_delete_guard", self.mass_delete_guard.isChecked())
        s.setValue("advanced/mass_delete_threshold", self.mass_delete_threshold.value())
        s.setValue("advanced/mass_delete_percent", self.mass_delete_percent.value())
        save_bandwidth_limits(
            self.bandwidth_upload.value() or None,
            self.bandwidth_download.value() or None,
        )
        s.setValue("p2p/enabled", self.p2p_mode.isChecked())
        s.setValue("p2p/group", self.p2p_group.text().strip())
        s.setValue("p2p/bootnode", self.p2p_bootnode.text().strip())
        s.setValue(
            "p2p/bootnode_trust",
            self.p2p_bootnode_trust.currentData() or DEFAULT_P2P_BOOTNODE_TRUST,
        )
        s.setValue("p2p/upnp_enabled", self.p2p_upnp.isChecked())
        s.setValue("p2p/key", encrypt_value(self.p2p_key.text().strip()))
        s.setValue("p2p/key_mode", self._effective_p2p_key_mode())
        s.setValue("p2p/port", self.p2p_port.value())
        s.setValue("p2p/discovery_timeout", self.discovery_timeout.value())
        s.setValue("p2p/ntp_hosts", self.ntp_hosts.text())
        s.setValue("p2p/prefer_master", self.prefer_master.isChecked())
        s.setValue("p2p/never_master", self.never_master.isChecked())
        s.setValue("p2p/require_pairing", self.require_pairing.isChecked())
        s.setValue("p2p/peer_download", self.peer_download.isChecked())
        s.setValue("p2p/peer_read_cap", self.peer_read_cap.value())
        s.setValue("p2p/peer_sources_max", self.peer_sources_max.value())
        s.setValue("output/verbose", self.verbose.isChecked())
        s.setValue("output/quiet", self.quiet.isChecked())
        s.setValue("output/logfile", self.logfile.text())
        # Theme preference: "light"/"dark"/"system" (item data).
        theme_value = self.theme_combo.currentData()
        if not isinstance(theme_value, str) or not theme_value:
            theme_value = THEME_DARK if self.theme_combo.currentIndex() == 1 else THEME_LIGHT
        s.setValue("appearance/theme", theme_value)
        s.setValue("appearance/font_scale", self.font_scale_combo.currentData())
        s.setValue("ui/show_advanced", self.show_advanced.isChecked())
        s.setValue("appearance/notifications", self.notifications_enabled.isChecked())
        for category, (toggle, _label) in self.notification_toggles.items():
            s.setValue(f"appearance/notifications/{category}", toggle.isChecked())
        # New fields
        lang_code = self.lang_combo.currentData()
        if lang_code:
            s.setValue("appearance/language", lang_code)
            set_language(lang_code)
        s.setValue("appearance/tooltips", self.tooltips_enabled.isChecked())
        s.setValue("appearance/start_at_login", self.start_at_login.isChecked())
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
        # Advanced tab (engine tuning)
        self.autotune.setChecked(bool(s.value("advanced/autotune", DEFAULT_AUTOTUNE, bool)))
        self.max_concurrent_transfers.setValue(
            cast(
                int,
                s.value("advanced/max_concurrent_transfers", DEFAULT_MAX_CONCURRENT_TRANSFERS, int),
            )
        )
        self.delta_enabled.setChecked(
            bool(s.value("advanced/delta_enabled", DEFAULT_DELTA_ENABLED, bool))
        )
        self.delta_min_file_size.setValue(
            cast(
                int,
                s.value("advanced/delta_min_file_size_kb", DEFAULT_DELTA_MIN_FILE_SIZE_KB, int),
            )
        )
        self.delta_min_file_size_p2p.setValue(
            cast(
                int,
                s.value(
                    "advanced/delta_min_file_size_p2p_kb",
                    DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB,
                    int,
                ),
            )
        )
        self.mass_delete_guard.setChecked(
            bool(s.value("advanced/mass_delete_guard", DEFAULT_MASS_DELETE_GUARD, bool))
        )
        self.mass_delete_threshold.setValue(
            cast(
                int,
                s.value("advanced/mass_delete_threshold", DEFAULT_MASS_DELETE_THRESHOLD, int),
            )
        )
        self.mass_delete_percent.setValue(
            cast(int, s.value("advanced/mass_delete_percent", DEFAULT_MASS_DELETE_PERCENT, int))
        )
        upload_bps, download_bps = get_bandwidth_limits()
        self.bandwidth_upload.setValue((upload_bps or 0) / (1024 * 1024))
        self.bandwidth_download.setValue((download_bps or 0) / (1024 * 1024))
        self.p2p_mode.setChecked(bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)))
        self.p2p_group.setText(str(s.value("p2p/group", DEFAULT_GROUP, str)))
        self.p2p_bootnode.setText(str(s.value("p2p/bootnode", DEFAULT_P2P_BOOTNODE, str)))
        index = self.p2p_bootnode_trust.findData(
            str(s.value("p2p/bootnode_trust", DEFAULT_P2P_BOOTNODE_TRUST, str))
        )
        self.p2p_bootnode_trust.setCurrentIndex(index if index >= 0 else 0)
        self.p2p_upnp.setChecked(bool(s.value("p2p/upnp_enabled", DEFAULT_P2P_UPNP_ENABLED, bool)))
        self.p2p_key.setText(decrypt_value(str(s.value("p2p/key", DEFAULT_P2P_KEY, str))))
        self._p2p_key_loaded = self.p2p_key.text().strip()
        self._p2p_key_mode_loaded = str(s.value("p2p/key_mode", "raw", str)) or "raw"
        self.p2p_port.setValue(cast(int, s.value("p2p/port", DEFAULT_P2P_PORT, int)))
        self.discovery_timeout.setValue(
            cast(int, s.value("p2p/discovery_timeout", DEFAULT_DISCOVERY_TIMEOUT, int))
        )
        self.ntp_hosts.setText(str(s.value("p2p/ntp_hosts", DEFAULT_NTP_HOSTS, str)))
        self.prefer_master.setChecked(
            bool(s.value("p2p/prefer_master", DEFAULT_PREFER_MASTER, bool))
        )
        self.never_master.setChecked(bool(s.value("p2p/never_master", DEFAULT_NEVER_MASTER, bool)))
        self.require_pairing.setChecked(
            bool(s.value("p2p/require_pairing", DEFAULT_P2P_REQUIRE_PAIRING, bool))
        )
        self.peer_download.setChecked(
            bool(s.value("p2p/peer_download", DEFAULT_P2P_PEER_DOWNLOAD, bool))
        )
        self.peer_read_cap.setValue(
            cast(int, s.value("p2p/peer_read_cap", DEFAULT_P2P_PEER_READ_CAP, int))
        )
        self.peer_sources_max.setValue(
            cast(int, s.value("p2p/peer_sources_max", DEFAULT_P2P_PEER_SOURCES_MAX, int))
        )
        self.verbose.setChecked(bool(s.value("output/verbose", DEFAULT_VERBOSE, bool)))
        self.quiet.setChecked(bool(s.value("output/quiet", DEFAULT_QUIET, bool)))
        self.logfile.setText(str(s.value("output/logfile", DEFAULT_LOGFILE, str)))
        theme_setting = str(s.value("appearance/theme", THEME_SYSTEM, str))
        theme_index = self.theme_combo.findData(theme_setting)
        if theme_index < 0:
            # Legacy values without item data: Light=0, Dark=1.
            theme_index = 1 if theme_setting == THEME_DARK else 0
        self.theme_combo.setCurrentIndex(theme_index)
        saved_font_scale = str(s.value("appearance/font_scale", DEFAULT_FONT_SCALE, str))
        font_index = self.font_scale_combo.findData(saved_font_scale)
        self.font_scale_combo.setCurrentIndex(font_index if font_index >= 0 else 0)
        self.show_advanced.setChecked(bool(s.value("ui/show_advanced", False, bool)))
        self._apply_advanced_visibility()
        self.notifications_enabled.setChecked(
            bool(s.value("appearance/notifications", DEFAULT_NOTIFICATIONS, bool))
        )
        for category, (toggle, _label) in self.notification_toggles.items():
            toggle.setChecked(bool(s.value(f"appearance/notifications/{category}", True, bool)))
        self._set_notification_categories_enabled(self.notifications_enabled.isChecked())
        # Language
        saved_lang = str(s.value("appearance/language", AUTO_LANGUAGE, str))
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == saved_lang:
                self.lang_combo.setCurrentIndex(i)
                break
                break
        # Tooltips
        self.tooltips_enabled.setChecked(
            bool(s.value("appearance/tooltips", DEFAULT_TOOLTIPS, bool))
        )
        # Start at OS login (minimized to the tray). On a supported platform the
        # on-disk autostart entry is the source of truth (the QSettings value is
        # only a mirror); where unsupported, disable and explain.
        if autostart.is_supported():
            self.start_at_login.setChecked(autostart.is_enabled())
        else:
            self.start_at_login.setChecked(
                bool(s.value("appearance/start_at_login", DEFAULT_START_AT_LOGIN, bool))
            )
            self.start_at_login.setEnabled(False)
            self._lbl_start_at_login.setEnabled(False)
            _set_field_tooltip(self.start_at_login, tr("tip.start_at_login_unsupported"))
        # Show log panel (default: hidden)
        self.show_log_panel.setChecked(
            bool(s.value("appearance/show_log", DEFAULT_SHOW_LOG_PANEL, bool))
        )
        # Apply p2p mode state to Server Mode tab
        self._on_p2p_mode_toggled(self.p2p_mode.isChecked())

        # Size last: the advanced visibility and the p2p-mode gate above change
        # which rows are shown, and the size must clamp to the screen.
        finalize_size(self)

    # ── Connection-active state management ────────────────────────────────

    def set_current_tab(self, index: int) -> None:
        """Switch the tab widget to the given index (first visible if hidden)."""
        if self._tabs and 0 <= index < self._tabs.count():
            if not self._tabs.isTabVisible(index):
                index = next(
                    (i for i in range(self._tabs.count()) if self._tabs.isTabVisible(i)),
                    index,
                )
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
            self.server_trust,
            self.btn_manage_trusted_keys_server,
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
            self.btn_reset_state,
        ]

        # p2p tab - all settings affect p2p mode behavior
        p2p_widgets: list[QWidget] = [
            self.p2p_mode,
            self.p2p_group,
            self.p2p_bootnode,
            self.p2p_bootnode_trust,
            self.btn_manage_trusted_keys,
            self.btn_test_bootnode,
            self.p2p_upnp,
            self.p2p_key,
            self.p2p_port,
            self.discovery_timeout,
            self.ntp_hosts,
            self.prefer_master,
            self.never_master,
            self.require_pairing,
            self.peer_download,
            self.peer_read_cap,
            self.peer_sources_max,
        ]

        # Advanced tab - engine tuning and logging need a restart
        advanced_widgets: list[QWidget] = [
            self.autotune,
            self.max_concurrent_transfers,
            self.delta_enabled,
            self.delta_min_file_size,
            self.delta_min_file_size_p2p,
            self.mass_delete_guard,
            self.mass_delete_threshold,
            self.mass_delete_percent,
            self.bandwidth_upload,
            self.bandwidth_download,
            self.verbose,
            self.logfile,
        ]

        # Combine all widgets that should be disabled
        all_disabled_widgets = connection_widgets + sync_widgets + p2p_widgets + advanced_widgets

        for widget in all_disabled_widgets:
            widget.setEnabled(not active and widget not in self._unsupported_widgets)
            # Set tooltip explaining why it's disabled
            if active:
                _set_field_tooltip(widget, disabled_tip)

        # Gray the field labels too, so a disabled panel reads as disabled (the
        # same visual the Server Mode tab uses when p2p mode is active). The
        # General tab stays live: theme/language/startup change without a restart.
        if active:
            self._set_tab_labels_enabled(_SYNC_TAB_INDEX, False)
            self._set_tab_labels_enabled(_P2P_TAB_INDEX, False)
            self._set_tab_labels_enabled(_ADVANCED_TAB_INDEX, False)
            self._set_tab_labels_enabled(
                _SERVER_TAB_INDEX,
                False,
                exclude=(self._p2p_banner_icon, self._p2p_banner_text),
            )
        else:
            # Sync labels are managed only here; the p2p/Server labels are
            # restored by _on_p2p_mode_toggled below.
            self._set_tab_labels_enabled(_SYNC_TAB_INDEX, True)
            self._set_tab_labels_enabled(_ADVANCED_TAB_INDEX, True)
            self._apply_tooltips()
            # Re-apply p2p mode state so sub-widgets stay disabled if p2p is off
            self._on_p2p_mode_toggled(self.p2p_mode.isChecked())
