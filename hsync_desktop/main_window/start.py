# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""StartMixin: engine lifecycle, sync orchestration and settings application."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast
from urllib.parse import urlsplit

from hsync_common.endpoint import parse_host_port
from hsync_common.format import format_bytes
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.bandwidth_dialog import BandwidthDialog
from hsync_desktop.config import (
    DEFAULT_P2P_BOOTNODE_TRUST,
    DEFAULT_P2P_ENABLED,
    DEFAULT_SERVER_TRUST,
    DEFAULT_SYNC_DIRECTION,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.engine import (
    HsyncEngine,
    add_bootnode_trust,
    add_peer_pin,
    add_server_trust,
    fetch_bootnode_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    list_bootnode_trust,
    list_server_trust,
    remove_bootnode_trust,
    remove_peer_pin,
    remove_server_trust,
    reset_sync_state,
    supports_peer_trust,
)
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.fonts import (
    apply_system_fonts,
    log_monospace_font,
    reset_widget_fonts,
    ui_font,
)
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.icons import icon
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog
from hsync_desktop.settings import (
    SETTINGS_APP,
    SETTINGS_ORG,
    ApiKeyDialog,
    P2PKeyDialog,
    SettingsDialog,
    are_notifications_enabled,
    build_hsync_args,
    get_deletion_policy,
    get_enabled_notification_categories,
    get_saved_font_scale,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
    is_simulation_mode,
)
from hsync_desktop.system_tray import SystemTray
from hsync_desktop.themes import (
    COLOR_CONNECTED,
    COLOR_DISCONNECTED,
    COLOR_WAITING,
    apply_theme,
)
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.widgets.dialogs import build_confirm_box, confirm
from hsync_desktop.wizard import SetupWizard
from hsync_desktop.wizard.model import mark_auto_shown, should_auto_open

# ── Startup disclaimer ───────────────────────────────────────────────────────
# Bumped when the wording changes, so an earlier acknowledgement does not cover
# a text the user never saw. The legacy boolean from previous releases counts as
# acceptance of version 1 only.
DISCLAIMER_VERSION = 1
_DISCLAIMER_VERSION_KEY = "ui/disclaimer_version"
_LEGACY_DISCLAIMER_KEY = "ui/disclaimer_accepted"
_LEGACY_DISCLAIMER_VERSION = 1


def _accepted_disclaimer_version(settings: QSettings) -> int:
    """Highest disclaimer version the user acknowledged."""
    version = int(settings.value(_DISCLAIMER_VERSION_KEY, 0) or 0)
    if version == 0 and settings.value(_LEGACY_DISCLAIMER_KEY, False, bool):
        version = _LEGACY_DISCLAIMER_VERSION
    return version


class StartMixin:
    # Open settings dialog, if any (re-declared here so the mixin typing agrees
    # with MainWindow.__init__).
    _settings_dialog: SettingsDialog | None
    # Open setup wizard, if any (re-declared so the mixin typing agrees with
    # MainWindow.__init__).
    _setup_wizard: SetupWizard | None
    # Scoped Send/Receive target, cleared by a normal start (re-declared so the
    # mixin typing agrees with MainWindow.__init__).
    _pending_selection_sync: tuple[str, str] | None

    def _reset_ui_stopped(self) -> None:
        """Reset UI buttons to the stopped state."""
        self._stop_requested = False
        self._btn_start.setEnabled(bool(self._local_path))
        self._btn_stop.setEnabled(False)
        if self._tray:
            self._tray.set_running(False)
        # Keep result/error toasts visible; only run-scoped toasts are cleared.
        self._clear_run_toast()
        self._apply_button_styles()
        self._update_menu_state()

    def _set_path(self, path: str) -> None:
        """Set the local path and update the display."""
        self._local_path = path.strip()
        # Feed the engine's distinct-file identity keys, so an absolute transfer
        # path and its bucket-relative form collapse to one key.
        self._engine.local_root = self._local_path
        self._update_path_display()
        self._update_menu_state()

    def _share_display_name(self) -> str:
        """User-facing share name shown next to the folder icon.

        Prefers the engine-detected bucket, then the saved share name, then the
        local folder's own name as a last resort.
        """
        if self._bucket:
            return self._bucket
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        bucket = str(s.value("sync/bucket", "", str)).strip()
        if bucket:
            return bucket
        from pathlib import Path as _Path

        return _Path(self._local_path).name or self._local_path

    def _update_path_display(self) -> None:
        """Update the path label, sync direction icon, and remote endpoint."""
        from hsync_desktop.icons import icon as get_icon

        # Primary/secondary is a p2p concept; Server Mode has no such role, so
        # hide the label and its icon there instead of a permanent "Secondary".
        p2p_enabled = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        )
        self._apply_role_visibility()

        if self._local_path:
            # ── Folder icon + share name (local path in the tooltip) ──────
            self._path_icon_label.setPixmap(get_icon("folder-open").pixmap(24, 24))
            self._path_icon_label.show()
            share_name = self._share_display_name()
            # Elide the name if it's too long (max ~300px)
            max_name_px = 300
            fm = QFontMetrics(self._path_label.font())
            elided = fm.elidedText(share_name, Qt.TextElideMode.ElideMiddle, max_name_px)
            text_color = (
                self._path_label.palette()
                .color(self._path_label.palette().ColorRole.WindowText)
                .name()
            )
            self._path_label.setText(
                f'<a href="open" style="color:{text_color}; text-decoration:underline;">{elided}</a>'
            )
            # The full local path is always reachable here: this tooltip is
            # intentionally exempt from the "Show tooltips" preference, which
            # only governs the settings fields.
            self._path_label.setToolTip(self._local_path)
            self._path_label.setCursor(Qt.CursorShape.PointingHandCursor)

            # ── Sync direction icon ───────────────────────────────────
            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            direction = str(s.value("sync/direction", DEFAULT_SYNC_DIRECTION, str))
            dir_icon_map = {
                "bidirectional": "sync-bidirectional",
                "upload-only": "sync-upload",
                "download-only": "sync-download",
            }
            dir_tip_map = {
                "bidirectional": tr("menu.sync.direction.bidirectional"),
                "upload-only": tr("menu.sync.direction.upload_only"),
                "download-only": tr("menu.sync.direction.download_only"),
            }
            icon_name = dir_icon_map.get(direction, "sync-bidirectional")
            self._sync_dir_icon.setPixmap(get_icon(icon_name).pixmap(24, 24))
            self._sync_dir_icon.setToolTip(dir_tip_map.get(direction, ""))
            self._sync_dir_icon.show()

            # ── Remote endpoint icon + label ──────────────────────────
            if p2p_enabled:
                self._remote_icon.setPixmap(get_icon("network-p2p").pixmap(24, 24))
                group = str(s.value("p2p/group", "", str))
                self._remote_label.setText(f"p2p ({group})" if group else "p2p")
                self._remote_icon.setToolTip(tr("label.remote_p2p_tip"))
                self._remote_label.setToolTip(tr("label.remote_p2p_tip"))
                # Group name shown next to the p2p label — hide from bottom bar
                self._group_label.hide()
            else:
                self._remote_icon.setPixmap(get_icon("network-cloud").pixmap(24, 24))
                server_ip = self._engine.server_ip if self._engine.server_ip else ""
                if not server_ip:
                    server_url = str(s.value("connection/server_url", "", str))
                    if server_url:
                        from urllib.parse import urlparse

                        parsed = urlparse(server_url)
                        server_ip = parsed.hostname or ""
                self._remote_label.setText(server_ip if server_ip else tr("label.remote_server"))
                self._remote_icon.setToolTip(tr("label.remote_server_tip"))
                self._remote_label.setToolTip(tr("label.remote_server_tip"))
                # In server mode, group label stays in bottom bar
                self._group_label.show()
            self._remote_icon.show()
            self._remote_label.show()
        else:
            self._path_icon_label.hide()
            self._sync_dir_icon.hide()
            self._remote_icon.hide()
            self._remote_label.hide()
            text_color = (
                self._path_label.palette()
                .color(self._path_label.palette().ColorRole.WindowText)
                .name()
            )
            self._path_label.setText(
                f'<a href="settings" style="color:{text_color}; text-decoration:underline;">'
                f"{tr('label.path_placeholder')}</a>"
            )
            self._path_label.setToolTip(tr("label.path_placeholder_tip"))
            self._path_label.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_path_clicked(self, link: str) -> None:
        """Handle clicks on the path label link."""
        if link == "settings":
            # Unconfigured folder: send the user to the wizard, not Settings.
            if self._local_path:
                self._open_settings(initial_tab=0)
            else:
                self._open_setup_wizard()
        elif self._local_path and os.path.isdir(self._local_path):
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl.fromLocalFile(self._local_path))

    def _build_disclaimer_dialog(
        self,
    ) -> tuple[QMessageBox, QPushButton, QPushButton, QCheckBox]:
        """Disclaimer with explicit acknowledge/defer labels and the app's icons."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("disclaimer.title"))
        msg.setText(tr("disclaimer.message"))

        acknowledge = msg.addButton(tr("disclaimer.acknowledge"), QMessageBox.ButtonRole.AcceptRole)
        acknowledge.setIcon(icon("dialog-ok"))
        not_now = msg.addButton(tr("disclaimer.not_now"), QMessageBox.ButtonRole.RejectRole)
        not_now.setIcon(icon("dialog-cancel"))
        msg.setDefaultButton(acknowledge)
        # Closing the window or pressing Esc defers; it never acknowledges.
        msg.setEscapeButton(not_now)

        dont_show = QCheckBox(tr("disclaimer.dont_show"))
        msg.setCheckBox(dont_show)
        return msg, acknowledge, not_now, dont_show

    def _show_disclaimer(self, *, interactive: bool = True) -> bool:
        """Show the disclaimer; True only when the user acknowledges it.

        ``interactive=False`` is for a run the user did not trigger: a one-time
        notice must not appear on a window nobody opened (a tray-only
        ``--minimized`` start), so the run is dropped and the caller surfaces it.
        """
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if _accepted_disclaimer_version(s) >= DISCLAIMER_VERSION:
            return True
        if not interactive:
            return False

        msg, acknowledge, _not_now, dont_show = self._build_disclaimer_dialog()
        msg.exec()
        # Window close and Esc leave clickedButton() empty: no acknowledgement.
        if msg.clickedButton() is not acknowledge:
            return False
        if dont_show.isChecked():
            s.setValue(_DISCLAIMER_VERSION_KEY, DISCLAIMER_VERSION)
        return True

    def _check_auto_sync(self) -> None:
        """Auto-start synchronization if a saved path exists."""
        # Do not race the setup wizard: defer until it has closed.
        if self._setup_wizard is not None:
            QTimer.singleShot(500, self._check_auto_sync)
            return
        local_path = self._local_path
        if local_path:
            self._on_auto_start()

    def _on_auto_start(self) -> None:
        """Auto-start from a saved folder or the OS autostart entry.

        Marks the run as automatic so a startup failure is reported through the
        tray/banner instead of a modal dialog that would be invisible while the
        app sits in the tray (``--minimized``), and so the deletion-risk gate
        never turns into a prompt nobody asked for. ``_on_start`` defers the run,
        so the origin is handed over as pending state instead of a scope exit.
        """
        self._pending_start_automatic = True
        self._on_start()

    def _check_deletion_risk(self, *, interactive: bool = True) -> bool:
        """Check if sync settings could cause local file deletion.

        Returns True if safe to proceed (no risk or user confirmed). Simulation
        Mode always proceeds: the client only previews in ``--dry-run``, so a
        run with it enabled can neither delete nor transfer anything.

        ``interactive=False`` is for a run the user did not trigger (auto-sync on
        startup): a confirmation answered by nobody must never start a
        destructive run, so the check reports the risk instead of asking.
        """
        local_path = self._local_path
        if not local_path or not os.path.exists(local_path):
            return True

        # Check if directory has any content
        try:
            entries = os.listdir(local_path)
        except OSError:
            return True
        if not entries:
            return True

        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        # Simulation Mode never applies changes (the run is a preview-only
        # one-shot), so nothing can be deleted and the confirmation would be a
        # false alarm.
        if is_simulation_mode():
            return True
        # Keep deleted files: this device never removes a file, so there is no
        # risk to confirm (and an automatic startup run must not be dropped for
        # a deletion that cannot happen).
        if get_deletion_policy() == "keep":
            return True
        p2p_mode = s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        prefer_master = s.value("p2p/prefer_master", False, bool)
        sync_dir = s.value("sync/direction", DEFAULT_SYNC_DIRECTION, str)

        # upload-only never deletes local files
        if sync_dir == "upload-only":
            return True

        # prefer_master in p2p mode means this client is authoritative
        if p2p_mode and prefer_master:
            return True

        # Determine risk
        if p2p_mode and not prefer_master:
            reason = tr("notif.deletion_risk_p2p")
        elif sync_dir == "download-only":
            reason = tr("notif.deletion_risk_download")
        else:
            # bidirectional server mode – normal behaviour
            return True

        if not interactive:
            return False

        return confirm(
            self,
            title=tr("notif.deletion_risk"),
            text=tr("notif.deletion_risk_msg").replace("{reason}", reason),
            with_icons=True,
        )

    def _report_deletion_risk_needed(self) -> None:
        """Surface a startup run stopped by the deletion-risk gate.

        The run is dropped rather than queued: the user reviews the settings and
        presses Start, which prompts through the normal interactive path.
        """
        message = tr("notif.deletion_risk_manual")
        self._append_desktop_log("WARNING", message)
        self._notify_warning(tr("notif.deletion_risk"), message)

    def _report_disclaimer_needed(self) -> None:
        """Surface a startup run stopped by the unacknowledged disclaimer."""
        message = tr("notif.disclaimer_manual")
        self._append_desktop_log("WARNING", message)
        self._notify_warning(tr("disclaimer.title"), message)

    def _check_keyless_p2p(self) -> bool:
        """Confirm keyless P2P operation before connecting.

        Without a shared key the transport hides traffic but authenticates nobody:
        reads are open and peers cannot be verified. Returns True when a key is
        set or the operator accepts the risk.
        """
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if not s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool):
            return True
        p2p_key = decrypt_value(str(s.value("p2p/key", "", str)))
        if p2p_key:
            return True

        return confirm(
            self,
            title=tr("warn.keyless_p2p_title"),
            text=tr("warn.keyless_p2p_msg"),
            icon_name=QMessageBox.Icon.Question,
            with_icons=True,
        )

    def _check_disk_space(self) -> bool:
        """Check if sufficient disk space is available. Returns False if insufficient."""
        from hsync_common.disk import BYTES_PER_MB, check_free_space

        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        min_free_mb = cast(int, s.value("sync/min_free_disk_space", 500, int))

        if min_free_mb <= 0:
            return True

        # Same rule as the client/server (``check_free_space``); the setting is
        # edited in whole MB, the shared guard is byte-based.
        space = check_free_space(self._local_path, reserve_bytes=min_free_mb * BYTES_PER_MB)
        if space.error is not None:
            self._append_desktop_log("WARNING", f"Could not check disk space: {space.error}")
            return True
        if not space.ok:
            QMessageBox.critical(
                self,
                tr("error.insufficient_disk_space"),
                tr("error.insufficient_disk_space_msg").format(
                    required=min_free_mb,
                    available=space.free_mb,
                ),
            )
            return False
        return True

    def _on_start(self) -> None:
        # Consume the queued origin first: a manual Start clears it, an automatic
        # one keeps it for the whole run (delayed continue + startup failures).
        self._start_is_automatic = self._pending_start_automatic
        self._pending_start_automatic = False
        # A new session may legitimately re-prompt for fingerprints dismissed in
        # the previous one.
        self._trust_prompted.clear()
        automatic = self._start_is_automatic
        # Show the disclaimer first. An automatic start never raises it: the
        # notice is surfaced and the run waits for a manual Start.
        if not self._show_disclaimer(interactive=not automatic):
            if automatic:
                self._report_disclaimer_needed()
            return

        local_path = self._local_path
        if not local_path:
            self._append_desktop_log("WARNING", "Please select a local directory first.")
            return

        # Delay the deletion risk check to prevent accidental double-clicks
        # This gives the user time to read the disclaimer before the next dialog appears
        self._pending_sync_path = local_path
        QTimer.singleShot(500, self._continue_start_after_disclaimer)

    def _continue_start_after_disclaimer(self) -> None:
        """Continue startup after disclaimer delay - check deletion risk and start sync."""
        local_path = self._pending_sync_path
        if not local_path:
            return

        # A normal start supersedes any pending Send/Receive preview.
        self._pending_selection_sync = None

        # Check for file deletion risk. A run started automatically (auto-sync on
        # startup) stops here when the settings could delete files: the warning is
        # surfaced and the user must press Start, which prompts interactively.
        automatic = self._start_is_automatic
        if not self._check_deletion_risk(interactive=not automatic):
            if automatic:
                self._report_deletion_risk_needed()
            return

        # Confirm keyless P2P posture before any connection is made
        if not self._check_keyless_p2p():
            return

        # Check disk space
        if not self._check_disk_space():
            return

        # Resolve bootnode/server trust before the client starts (the client
        # cannot prompt without a terminal). The fingerprint probe runs off the
        # UI thread, so the start continues from its callback.
        self._ensure_trust(lambda: self._start_preview_run(local_path))

    def _start_preview_run(self, local_path: str) -> None:
        """Start the dry-run preview that precedes a full sync."""
        args = build_hsync_args(local_path, force_dry_run=True)

        self._prepare_engine_run(local_path)
        # Set flags to show preview summary when dry-run completes
        self._awaiting_preview_for_sync = True
        self._is_dry_run_preview = True  # We're in dry-run mode for initial preview
        self._pending_sync_path = local_path  # Save path for actual sync
        if not self._start_engine(args):
            self._reset_ui_stopped()
            return
        self._enter_running_ui()

    def _start_engine(self, args: list[str]) -> bool:
        """Start the engine, surfacing a visible dialog when it fails.

        A failed start (missing/incompatible binary, spawn failure) used to
        leave the window unchanged and only raise a desktop notification, so the
        Start click looked like a no-op. Returns the engine result; the caller
        owns the post-success UI state and the failure reset.
        """
        self._last_engine_error = ""
        # Fresh startup-failure state for this run (see ``_on_startup_failed``).
        self._startup_failure_surfaced = False
        self._startup_error_message = ""
        self._startup_failure_tail = ""
        self._engine.local_root = self._local_path
        self._engine_starting = True
        try:
            started = self._engine.start(args)
        finally:
            self._engine_starting = False
        if started:
            return True
        # A scoped Send/Receive that could not launch is ended silently: the
        # start-failure dialog below is its single, more specific report.
        if self._selection_sync_active:
            self._finish_selection_sync("cancelled")
        self._report_engine_start_failure(
            detail=self._last_engine_error, automatic=self._start_is_automatic
        )
        return False

    def _report_engine_start_failure(
        self,
        *,
        code: int = 0,
        detail: str = "",
        automatic: bool = False,
    ) -> None:
        """Show why the engine could not start instead of failing silently.

        A manual start gets a modal dialog; an automatic start gets the
        persistent error banner plus the tray notification (a modal would be
        invisible and blocking while the app runs minimized in the tray).
        """
        detail = (detail or self._last_engine_error).strip()
        text = tr("notif.engine_start_failed")
        if code:
            text = f"{text}\n\n{tr('notif.engine_startup_failed').replace('{code}', str(code))}"
        if automatic:
            message = f"{text}\n{detail}".strip()
            self._append_desktop_log("ERROR", message.replace("\n", " "))
            self._notify_error(tr("notif.error"), message)
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(tr("notif.error"))
        msg.setText(text)
        if detail:
            msg.setInformativeText(detail)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        show_log = msg.addButton(tr("settings.show_log_panel"), QMessageBox.ButtonRole.ActionRole)
        msg.exec()
        if msg.clickedButton() is show_log:
            self._show_log_panel()

    def _mark_user_stopped(self) -> None:
        """Per-run bookkeeping shared by every user-initiated stop.

        Runs even when the engine is not running: the flag also gates the
        "connection lost" and engine-warning suppressions, so callers set it
        before deciding whether there is a process to stop.
        """
        self._user_stopped = True
        self._trust_prompted.clear()
        if self._notifier:
            self._notifier.user_stopped = True

    def _on_stop(self) -> None:
        self._mark_user_stopped()
        # The Stop action is disabled once stopping, so a second request can only
        # come from a click queued before the repaint: ignore it.
        if not self._engine.is_running or self._stop_requested:
            return
        self._enter_stopping_ui()
        # Non-blocking: the window stays responsive while the child unwinds; the
        # engine's grace/safety timers escalate and settle the state.
        self._engine.request_stop()

    def _enter_stopping_ui(self) -> None:
        """Show the stopping state at once, before the child has exited.

        The badge changes immediately, Start/Stop/Check-changes are disabled and a
        progress toast plus a log marker make the click visible. The state is
        cleared by ``EventsMixin._on_process_finished`` or, if the child never
        reports its exit, by the engine's ``stop_timeout``.
        """
        self._stop_requested = True
        self._set_status_label("stopping")
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(False)
        if self._tray:
            self._tray.set_stopping()
        self._apply_button_styles()
        self._update_menu_state()
        self._show_info_banner(tr("status.stopping"), kind="progress")
        self._append_log(f"--- {tr('status.stopping')} ---")

    @Slot()
    def _on_stop_timeout(self) -> None:
        """Settle the UI when the engine could not confirm the child exit.

        ``HsyncEngine.stop_timeout`` means the kill escalation produced no
        ``finished`` and the engine already reset its own state: leaving
        "Stopping…" and telling the user beats waiting forever.
        """
        self._set_status_label("disconnected")
        self._reset_ui_stopped()
        self._append_desktop_log("WARNING", tr("notif.stop_timeout"))
        self._show_info_banner(tr("notif.stop_timeout"), kind="warning", title=tr("notif.warning"))

    def _can_check_changes(self) -> bool:
        """Whether the manual comparison can run in the current state.

        One predicate for the action-bar button, the ``F5`` menu action and the
        tray entry, so the three never disagree. A missing link does **not**
        disable the action: the click then explains that the check waits for a
        connection, instead of writing a ``PREVIEW`` the client can only fail.
        """
        return (
            self._engine.is_running
            and not self._stop_requested
            and not self._comparison_in_flight
            and not self._selection_sync_active
            # Simulation Mode *is* a preview: a second one would race the one-shot.
            and not is_simulation_mode()
        )

    def _on_check_changes(self) -> None:
        """Ask the running engine for a fresh comparison of the share.

        Sends a ``PREVIEW`` command over stdin and lets the role decide the
        answer: a **secondary** node replies with the preview cycle this window
        confirms (``preview_start``/``preview_end``), so the summary dialog can
        offer the sync, while a **primary** node serves the share and replies with
        its own classification pass (``status_pass_start``/``status_pass_end``),
        which re-renders the rows and the file-set state — there is nothing for the
        serving device to pull.

        The guards keep the click honest: no comparison with a dead engine, none
        queued behind a running one, none while Simulation Mode (the whole run is
        already a preview) and none before a link exists — the client's preview
        would fail and still report an end marker, which reads as "everything in
        sync". The app itself compares on every connect, so nothing is lost.
        """
        if not self._engine.is_running:
            self._append_desktop_log("WARNING", "Please start synchronization first.")
            return
        if self._comparison_in_flight:
            # The control is disabled while one runs; this covers a queued click.
            return
        if is_simulation_mode():
            self._append_desktop_log("INFO", tr("simulation.tip"))
            self._show_info_banner(tr("simulation.tip"), kind="info")
            return
        if not self._connected:
            self._append_desktop_log("INFO", tr("tip.check_changes_waiting"))
            self._show_info_banner(tr("tip.check_changes_waiting"), kind="info")
            return
        # The action name is the menu entry: one vocabulary for the tooltip,
        # the menu, the tray and the log line this click writes.
        self._append_log(f"--- {tr('menu.sync.check_changes')} ---")
        # Only the requester-side preview cycle may confirm a sync: a serving
        # device answers with a classification, whose markers own the rendering.
        self._awaiting_preview_for_sync = not (self._p2p_enabled and self._is_master)
        self._is_dry_run_preview = False  # stdin preview, not dry-run mode
        self._engine.preview()

    def _load_local_files(self, path: str) -> None:
        """Load files from the selected directory into the file panel."""
        if path:
            self._file_panel.load_local_files(path)

    def _open_settings(self, initial_tab: int | None = None) -> None:
        if self._settings_dialog is not None:
            if isinstance(initial_tab, int) and not isinstance(initial_tab, bool):
                self._settings_dialog.set_current_tab(initial_tab)
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dlg = SettingsDialog(self)
        self._settings_dialog = dlg
        try:
            # Disable connection-critical settings while sync is running
            dlg.set_connection_active(self._engine.is_running)
            # initial_tab may receive a bool from Qt signal triggered(bool) — ignore that
            if isinstance(initial_tab, int) and not isinstance(initial_tab, bool):
                dlg.set_current_tab(initial_tab)
            accepted = dlg.exec() == SettingsDialog.DialogCode.Accepted
        finally:
            self._settings_dialog = None
        # The dialog only *asks* for the reset; the window owns the engine and
        # performs the call once the modal is gone (the log shows the outcome).
        reset_folder = dlg.reset_state_folder
        if accepted:
            self._apply_settings_changes()
        if reset_folder:
            self._reset_sync_state(reset_folder)

    def _reset_sync_state(self, folder: str) -> None:
        """Forget *folder*'s client-side sync state (Settings → Sync → Advanced).

        The client takes the folder's instance lock, so a running sync makes the
        command refuse; the button is disabled in that state and this guard only
        covers a race.
        """
        if self._engine.is_running:
            QMessageBox.warning(
                self, tr("settings.reset_state.title"), tr("settings.reset_state.stop_first")
            )
            return
        binary = self._engine.binary_path
        if not binary:
            # No bundled client (broken install): report it instead of letting
            # ``subprocess.run([None, ...])`` raise out of this slot.
            QMessageBox.warning(
                self, tr("settings.reset_state.title"), tr("settings.reset_state.failed")
            )
            return
        result = reset_sync_state(binary, folder)
        if not result.ok:
            detail = result.message or tr("settings.reset_state.failed")
            self._append_desktop_log("ERROR", f"[STATE RESET] {detail}")
            QMessageBox.warning(self, tr("settings.reset_state.title"), detail)
            return
        if not result.found:
            message = tr("settings.reset_state.nothing")
        elif result.quarantined:
            message = tr("settings.reset_state.quarantined")
        else:
            message = (
                tr("settings.reset_state.done")
                .replace("{versions}", str(result.versions))
                .replace("{tombstones}", str(result.tombstones))
            )
        self._append_desktop_log("INFO", f"[STATE RESET] {message}")
        QMessageBox.information(self, tr("settings.reset_state.title"), message)

    def _refresh_menu_fonts(self) -> None:
        """Re-apply the resolved app font to the menu bar and its popups.

        QMenu caches the font it was created with, so a live font-size change
        otherwise leaves the menus at the previous scale until the next launch.
        """
        font = ui_font()
        self.menuBar().setFont(font)
        for menu in self.menuBar().findChildren(QMenu):
            menu.setFont(font)

    def _apply_settings_changes(self) -> None:
        """Re-apply settings that changed on disk (Settings dialog or wizard).

        One refresh path so both the Settings dialog and the setup wizard
        converge: theme/icons/notifications/log visibility plus the local path
        reload and the path display.
        """
        theme = get_saved_theme()
        app = QApplication.instance()
        if app:
            apply_theme(app, theme)  # type: ignore[arg-type]
            apply_system_fonts(app, get_saved_font_scale())
            # The stylesheet resolved every widget's font at polish time, so the
            # new application font must be re-inherited explicitly; the widgets
            # that use another font are re-applied right below.
            reset_widget_fonts(self)
            self._refresh_menu_fonts()
            self._refresh_icons_for_theme()
            self._log_view.setFont(log_monospace_font())
            self._file_panel.refresh_fonts()
        if theme != self._log_theme:
            # The log colors are baked into the text formats: recolor on change.
            self._log_theme = theme
            self._rerender_log()
        if self._notifier:
            self._notifier.enabled = are_notifications_enabled()
            self._notifier.categories = get_enabled_notification_categories()
        self._apply_log_visibility()
        # The Simulation Mode badge/title/tray and the backup-policy badge
        # follow the saved settings too.
        self._refresh_simulation_state()
        self._refresh_deletion_badge()
        # Reload path in case it changed in settings
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        new_path = str(s.value("path/local", "", str))
        if new_path != self._local_path:
            self._set_path(new_path)
            if new_path:
                self._load_local_files(new_path)
        # Refresh path display (settings may have changed p2p/server/direction)
        self._update_path_display()
        # The presence title follows the mode (devices vs connected members).
        self._update_peers_label_title()

    def _open_setup_wizard(self) -> None:
        """Open the guided setup wizard (stop a running sync first)."""
        if self._setup_wizard is not None:
            self._setup_wizard.raise_()
            self._setup_wizard.activateWindow()
            return
        if self._engine.is_running:
            if not self._confirm_stop_sync():
                return
            self._mark_user_stopped()
            # The wizard may start the engine right after, so the child must
            # really be gone: this path waits instead of showing "Stopping…".
            self._engine.stop_and_wait()
        dlg = SetupWizard(self)
        self._setup_wizard = dlg
        try:
            dlg.exec()
        finally:
            self._setup_wizard = None
        if dlg.applied:
            self._apply_settings_changes()
            if dlg.start_requested:
                self._on_start()

    def _build_stop_sync_dialog(self) -> QMessageBox:
        """Stop-to-reconfigure confirmation with translated labels and app icons."""
        return build_confirm_box(
            self,
            title=tr("wizard.title"),
            text=tr("wizard.stop_prompt"),
            icon_name=QMessageBox.Icon.Question,
            with_icons=True,
        )

    def _confirm_stop_sync(self) -> bool:
        return self._build_stop_sync_dialog().exec() == QMessageBox.StandardButton.Yes

    def maybe_show_setup_wizard(self) -> None:
        """Auto-open the wizard once on a first run (no folder configured)."""
        if self._setup_wizard is not None:
            return
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if not should_auto_open(s):
            return
        mark_auto_shown(s)
        s.sync()
        self._open_setup_wizard()
