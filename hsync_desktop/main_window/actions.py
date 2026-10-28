# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""ActionsMixin: action bar, sync controls, preview and direction menu."""

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
    supports_peer_trust,
)
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.i18n import register_language_callback, tr
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
    build_selection_args,
    get_bandwidth_limits,
    get_deletion_policy,
    get_saved_theme,
    get_sync_direction,
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


class ActionsMixin:
    # Scoped Send/Receive target ``(subdir, direction)``; None when idle. Declared
    # here so the composed ``MainWindow`` shares the optional type.
    _pending_selection_sync: tuple[str, str] | None
    # Folder/row captured before the scoped op reloads the file panel.
    _selection_sync_view: tuple[str, str | None] | None
    # p2p role state (unknown until the election event). Declared here so the
    # composed ``MainWindow`` shares the optional type.
    _role_known: bool
    _is_master: bool | None
    _connected: bool

    @Slot(QAction)
    def _on_direction_changed(self, action: QAction) -> None:
        """Handle sync direction change from the menu."""
        direction = action.data()
        if not direction:
            return
        # Persist to QSettings
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("sync/direction", direction)
        # If the engine is running, send the command dynamically
        if self._engine.is_running:
            self._engine.set_sync_direction(direction)
        # Refresh path display to update sync direction icon
        self._update_path_display()

    @Slot(object)
    def _on_file_selection_changed(self, transfer) -> None:
        """Handle file selection change from the file panel table."""
        has_selection = transfer is not None
        self._set_file_menu_enabled(has_selection)
        # Hide "Open With" for folders
        if has_selection and hasattr(transfer, "filepath"):
            is_dir = transfer.filepath.endswith("/")
            self._act_file_open_with.setEnabled(not is_dir)

    # ── File menu action wrappers ─────────────────────────────────────────

    def _get_selected_transfer(self):
        """Return the currently selected transfer from the file panel, or None."""
        table = self._file_panel._table
        row = table._last_selected_row
        if row < 0 or row >= table.model().rowCount():
            return None
        transfer = table._get_transfer_at_row(row)
        if not transfer:
            # Synthesized folder — create a virtual transfer
            from hsync_desktop.file_panel import FileTransfer, TransferStatus

            display_name = table.model().display_name(row)
            if display_name is None:
                return None
            folder_path = (
                f"{table._current_path}/{display_name}/"
                if table._current_path
                else f"{display_name}/"
            )
            transfer = FileTransfer(
                filepath=folder_path,
                direction="—",
                size=0,
                status=TransferStatus.LOCAL,
            )
        return transfer

    def _menu_file_open(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_open(t)

    def _menu_file_open_with(self) -> None:
        t = self._get_selected_transfer()
        if t and not t.filepath.endswith("/"):
            self._file_panel._table._ctx_open_with(t)

    def _menu_file_copy_to(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_copy_to(t)

    def _menu_file_open_containing(self) -> None:
        """Reveal the selected entry in the OS file manager."""
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_open_containing(t)

    def _menu_file_copy_path(self) -> None:
        """Copy the selected entry's absolute path (host-native form)."""
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table.copy_path(t)

    def _menu_file_copy_path_relative(self) -> None:
        """Copy the selected entry's path inside the shared folder."""
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table.copy_path(t, relative=True)

    def _menu_file_rename(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_rename(t)

    def _menu_file_trash(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_trash(t)

    def _menu_file_properties(self) -> None:
        t = self._get_selected_transfer()
        if t:
            self._file_panel._table._ctx_properties(t)

    def _has_file_selection(self) -> bool:
        """Return whether a file/folder row is selected in the file panel."""
        return self._get_selected_transfer() is not None

    def _menu_file_send(self) -> None:
        transfer = self._get_selected_transfer()
        if transfer:
            self._sync_selection(transfer.filepath, "upload-only")

    def _menu_file_receive(self) -> None:
        transfer = self._get_selected_transfer()
        if transfer:
            self._sync_selection(transfer.filepath, "download-only")

    @staticmethod
    def _selection_subdir(filepath: str) -> str:
        """Bucket-relative subdirectory a selection sync is scoped to.

        A folder maps to itself; a file maps to its containing folder (per-file
        sync is not supported by the engine). A root-level entry yields "".
        """
        path = filepath.strip("/")
        if filepath.endswith("/"):
            return path
        return os.path.dirname(path)

    @staticmethod
    def _selection_display_name(filepath: str, current_path: str) -> str | None:
        """Row name of the acted-on entry at the folder currently shown.

        The list shows one path segment per row, so a nested target maps to the
        first segment below ``current_path``; this keeps the highlight on the
        row the user acted on after the panel reloads.
        """
        target = filepath.strip("/")
        base = current_path.strip("/")
        if base:
            if target == base:
                return None
            if target.startswith(base + "/"):
                target = target[len(base) + 1 :]
        return target.split("/", 1)[0] if target else None

    def _enter_running_ui(self) -> None:
        """Reflect a started engine in the buttons, tray and menus."""
        self._on_status("connecting")
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        # A running engine can always compare the share: the command is queued on
        # its stdin and both roles answer it (see StartMixin._on_check_changes).
        self._btn_check_changes.setEnabled(True)
        if self._tray:
            self._tray.set_running(True)
        self._apply_button_styles()
        self._update_menu_state()

    def _prepare_engine_run(
        self,
        local_path: str,
        *,
        restore_view: tuple[str, str | None] | None = None,
    ) -> None:
        """Common pre-start bookkeeping shared by every engine (re)start."""
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("path/local", local_path)
        self._log_view.clear()
        # A new run clears stale run-scoped toasts but keeps persistent
        # error/warning toasts the user has not dismissed yet.
        self._clear_run_toast(across_runs=True)
        self._file_panel.load_local_files(local_path, restore_view=restore_view)
        self._user_stopped = False
        self._ever_connected = False  # reset per engine process
        self._transfer_failure_count = 0  # reset per engine process
        self._p2p_enabled = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", False, bool)
        )
        self._initial_reconcile_done = False
        self._pending_initial_reconcile = False
        self._dry_run_preview_reported = False
        self._last_scan_preview_at = 0.0
        # A fresh process runs a fresh p2p election: back to the neutral role.
        self._role_known = False
        self._is_master = None
        self._connected = False
        self._share_total_bytes = -1
        self._retranslate_role()
        self._render_share_size()
        if self._notifier:
            self._notifier.user_stopped = False
        if is_simulation_mode():
            self._append_desktop_log("INFO", tr("simulation.log_start"))

    def _sync_selection(self, filepath: str, direction: str) -> None:
        """Confirm and run a one-shot Send (upload-only) / Receive (download-only)
        of a selected subtree.

        Only available while stopped (the actions are disabled otherwise). A
        dry-run preview scoped to the selection runs first, so the preview
        summary dialog shows the actions that would be taken; the real one-shot
        starts only on accept. Send is a non-destructive push; Receive is a pull
        and keeps the deletion-risk confirmation.
        """
        if self._engine.is_running:
            self._append_desktop_log("WARNING", tr("sync.selection_busy"))
            self._show_info_banner(tr("sync.selection_busy"), auto_hide_ms=5000, kind="info")
            return
        local_path = self._local_path
        if not local_path:
            self._append_desktop_log("WARNING", "Please select a local directory first.")
            return

        # Same pre-flight prompts as a normal start.
        if direction == "download-only" and not self._check_deletion_risk():
            return
        if not self._check_keyless_p2p():
            return
        if not self._check_disk_space():
            return
        # Same trust pre-flight as a normal start; the fingerprint probe runs off
        # the UI thread, so the scoped run begins from its callback.
        self._ensure_trust(lambda: self._begin_selection_run(filepath, direction))

    def _begin_selection_run(self, filepath: str, direction: str) -> None:
        """Arm and preview the confirmed scoped Send/Receive."""
        local_path = self._local_path
        if not local_path:
            return
        subdir = self._selection_subdir(filepath)
        label = tr("action.send_now") if direction == "upload-only" else tr("action.receive_now")
        self._append_log(f"--- {label}: {subdir or '.'} ---")
        view_path = self._file_panel.current_path
        self._selection_sync_view = (
            view_path,
            self._selection_display_name(filepath, view_path),
        )
        self._prepare_engine_run(local_path, restore_view=self._selection_sync_view)
        self._begin_selection_sync(subdir, direction)

        # Preview first (one-shot dry-run scoped to the selection); the real run
        # starts from _show_preview_summary() once the dialog is accepted.
        self._awaiting_preview_for_sync = True
        self._is_dry_run_preview = False
        args = build_selection_args(local_path, subdir, direction, dry_run=True)
        if not self._start_engine(args):
            self._awaiting_preview_for_sync = False
            self._finish_selection_sync("cancelled")
            return
        self._enter_running_ui()

    # ── Scoped Send/Receive outcome helpers ──────────────────────────────

    def _is_window_foreground(self) -> bool:
        """True when the main window is visible and focused."""
        return self.isVisible() and self.isActiveWindow()

    def _selection_phase_text(self) -> str:
        """Progress-banner text at the start of a scoped operation."""
        p2p_enabled = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        )
        return tr("sync.sel_search") if p2p_enabled else tr("sync.sel_server")

    def _begin_selection_sync(self, subdir: str, direction: str) -> None:
        """Arm the scoped-op state and show a persistent progress banner."""
        self._selection_sync_active = True
        self._selection_sync_phase = "preview"
        self._pending_selection_sync = (subdir, direction)
        self._show_info_banner(self._selection_phase_text(), auto_hide_ms=0, kind="progress")

    def _finish_selection_sync(self, outcome: str, *, applied: int = 0) -> bool:
        """Finalize a scoped Send/Receive and surface its outcome (idempotent).

        ``applied`` is the action count the engine reported for the run (transfers,
        renames and deletes), never a count of UI events: a rename moves no bytes
        and would otherwise read as "nothing to do". Returns True when it actually
        finalized, so a later engine event (``process_finished``) does not
        re-surface the same result.
        """
        if not self._selection_sync_active:
            return False
        args = self._pending_selection_sync
        direction = args[1] if args else ""
        count = applied
        self._selection_sync_active = False
        self._selection_sync_phase = ""
        self._pending_selection_sync = None
        self._selection_sync_view = None
        self._reset_ui_stopped()  # hides the banner, resets buttons/menus
        self._surface_selection_outcome(outcome, direction=direction, count=count)
        return True

    def _surface_selection_outcome(self, outcome: str, *, direction: str, count: int) -> None:
        """Show the scoped-op result (dialog in the foreground, else a notification)."""
        if outcome == "no_devices":
            self._important_selection_outcome(
                tr("sync.sel_no_devices_title"), tr("sync.sel_no_devices_msg")
            )
        elif outcome == "server_unreachable":
            self._important_selection_outcome(
                tr("sync.sel_server_unreachable_title"), tr("sync.sel_server_unreachable_msg")
            )
        elif outcome == "failed":
            self._important_selection_outcome(
                tr("sync.sel_failed_title"), tr("sync.sel_failed_msg")
            )
        elif outcome == "already_synced":
            self._info_selection_outcome(tr("sync.sel_already_synced"), success=False)
        elif outcome == "done":
            key = "sync.sel_sent_fmt" if direction == "upload-only" else "sync.sel_received_fmt"
            self._info_selection_outcome(tr(key).replace("{count}", str(count)))
        # "cancelled" / "stopped": nothing to show.

    def _important_selection_outcome(self, title: str, message: str) -> None:
        """A modal dialog when the window is focused, otherwise a notification."""
        if self._is_window_foreground():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(title)
            box.setText(title)
            box.setInformativeText(message)
            box.exec()
        elif self._notifier:
            self._notifier.warning(title, message, category="sync")
        else:
            self._show_info_banner(message, kind="error", title=title)

    def _info_selection_outcome(self, message: str, *, success: bool = True) -> None:
        """Non-critical scoped result: a toast now, plus an OS notification when
        the window is out of focus (the manager suppresses it in the foreground,
        so exactly one surface shows)."""
        if success:
            self._show_info_banner(message, kind="success", title=tr("notif.success"))
        else:
            self._show_info_banner(message, kind="info")
        if self._notifier:
            self._notifier.info(tr("app.name"), message, category="sync")

    def _start_selection_run(self, subdir: str, direction: str) -> None:
        """Start the real one-shot Send/Receive after the preview is confirmed."""
        local_path = self._local_path
        if not local_path:
            self._finish_selection_sync("failed")
            return
        self._selection_sync_phase = "run"
        self._prepare_engine_run(local_path, restore_view=self._selection_sync_view)
        args = build_selection_args(local_path, subdir, direction)
        if not self._start_engine(args):
            self._finish_selection_sync("failed")
            return
        self._enter_running_ui()

    def _open_documentation(self) -> None:
        """Open the documentation index in the default browser."""
        from hsync_desktop.docs_links import DOCS_INDEX, open_docs_link

        open_docs_link(DOCS_INDEX)

    def _open_github(self) -> None:
        """Open the project page on GitHub in the default browser."""
        from hsync_desktop.docs_links import GITHUB_REPO, open_docs_link

        open_docs_link(GITHUB_REPO)

    def _show_about(self) -> None:
        """Show the splash screen as an About dialog."""
        from hsync_desktop.splash_screen import SplashScreen

        about = SplashScreen(self)
        about.show_as_about()

    def _show_license(self) -> None:
        """Show the project license in a scrollable, read-only dialog."""
        from hsync_desktop.license_dialog import LicenseDialog

        LicenseDialog(self).exec()

    # ── Signal wiring ────────────────────────────────────────────────────

    def _show_preview_summary(self) -> None:
        """Show the preview summary dialog and start sync if confirmed."""
        s = self._preview_stats
        selection = self._selection_sync_active
        # Simulation Mode never applies the preview: the client exits after its
        # one-shot dry-run, so no SYNC command is ever sent.
        simulation = is_simulation_mode()

        if not s.has_work():
            # Skip the dialog entirely.
            self._append_desktop_log("INFO", tr("preview.no_actions"))
            if selection:
                # Scoped op with nothing to transfer: report it instead of silence.
                self._finish_selection_sync("already_synced")
                return
            if self._is_dry_run_preview and not simulation:
                # Send SYNC to switch from dry-run to real sync. The dry-run
                # phase stays armed: the client may be serving as master when
                # the command is written (its stdin is only read by the slave
                # role), so the next preview it runs in this phase must send it
                # again. The phase ends when the link comes up (_on_status).
                self._engine.sync()
                self._awaiting_preview_for_sync = True
                if not self._dry_run_preview_reported:
                    self._dry_run_preview_reported = True
                    # Surface the result without needing the log panel.
                    self._info_selection_outcome(tr("preview.no_actions"), success=False)
                return
            self._is_dry_run_preview = False
            # Non-scoped: surface the result without needing the log panel.
            self._info_selection_outcome(tr("preview.no_actions"), success=False)
            return

        if selection:
            # The preview process has already exited (or will): keep the scoped
            # op active, but mark the confirmation phase so a process-finished
            # event does not finalize while this modal dialog is open.
            self._selection_sync_phase = "confirm"

        download_bps, upload_bps = get_bandwidth_limits()
        scope = ""
        if selection and self._pending_selection_sync:
            scope = self._preview_path(self._pending_selection_sync[0])
        dlg = PreviewSummaryDialog(
            self._preview_stats,
            parent=self,
            simulation=simulation,
            download_bps=download_bps,
            upload_bps=upload_bps,
            direction=get_sync_direction(),
            deletions_kept=get_deletion_policy() != "propagate",
            scope=scope,
        )
        if dlg.exec() == PreviewSummaryDialog.DialogCode.Accepted:
            if selection:
                # Scoped Send/Receive: start the confirmed one-shot for real.
                args = self._pending_selection_sync
                if args:
                    self._start_selection_run(*args)
                else:
                    self._finish_selection_sync("failed")
            elif simulation:
                # Preview-only run: report it and let the one-shot process exit.
                self._append_desktop_log("INFO", tr("preview.simulation_no_changes"))
                self._info_selection_outcome(tr("preview.simulation_no_changes"), success=False)
            else:
                # Send SYNC command — the running process will perform
                # the actual sync without needing a restart.
                self._engine.sync()
            self._is_dry_run_preview = False
        else:
            if selection:
                self._finish_selection_sync("cancelled")
            elif self._is_dry_run_preview:
                # User cancelled - stop the dry-run process
                self._engine.stop_and_wait()
                # Reset UI state
                self._btn_start.setEnabled(bool(self._local_path))
                self._btn_stop.setEnabled(False)
                if self._tray:
                    self._tray.set_running(False)
                self._apply_button_styles()
                self._update_menu_state()
            # If stdin preview, just close dialog - process keeps running
            self._is_dry_run_preview = False

    def _show_bandwidth_dialog(self) -> None:
        """Show the bandwidth settings dialog."""
        # Check if sync is active
        sync_active = self._engine.is_running

        # Show bandwidth dialog
        dlg = BandwidthDialog(self, sync_active=sync_active)
        if dlg.exec() == BandwidthDialog.DialogCode.Accepted:
            upload_mbps, download_mbps = dlg.get_bandwidth_values()

            # Convert MB/s to bytes/s
            upload_bps = int(upload_mbps * 1024 * 1024) if upload_mbps else None
            download_bps = int(download_mbps * 1024 * 1024) if download_mbps else None

            # Format human-readable values for log
            upload_display = f"{upload_mbps}" if upload_mbps else "∞"
            download_display = f"{download_mbps}" if download_mbps else "∞"

            # If sync is running, send the new limits via stdin command
            if self._engine.is_running:
                self._engine.set_bandwidth(upload_bps, download_bps)
                self._append_desktop_log(
                    "INFO",
                    tr("bandwidth.applied").format(
                        upload=upload_display, download=download_display
                    ),
                )
            else:
                # If sync is not running, just save settings for next start
                self._append_desktop_log(
                    "INFO",
                    tr("bandwidth.saved").format(upload=upload_display, download=download_display),
                )
