# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""EventsMixin: engine signals, status, file events and role indicator."""

from __future__ import annotations

import os
import time
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

from hsync_desktop import debug_events
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
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
)
from hsync_desktop.system_tray import SystemTray
from hsync_desktop.themes import (
    COLOR_CONNECTED,
    COLOR_DISCONNECTED,
    COLOR_SYNCING,
    COLOR_WAITING,
    apply_theme,
)
from hsync_desktop.ui.loader import load_ui_widget

# Minimum spacing between scan-triggered previews: a burst of missed events
# (many renames in a row) coalesces into at most one extra full scan per window.
_SCAN_PREVIEW_COOLDOWN_S = 15.0


class EventsMixin:
    # p2p role state (unknown until the election event). Declared here so the
    # mixin typing agrees with MainWindow.__init__/ActionsMixin.
    _role_known: bool
    _is_master: bool | None
    _connected: bool

    @Slot(str)
    def _on_bucket_detected(self, bucket: str) -> None:
        """Record the active share name and show it next to the folder icon.

        The share name is the user-facing identity, so it labels the local
        folder in the action bar (the local path is a tooltip/click target); the
        window title stays the app name.
        """
        self._bucket = bucket
        self._update_window_title()
        self._update_path_display()

    def _set_status_label(self, status: str) -> None:
        """Update the status dot/label/tray without the connection-loss effects."""
        i18n_map = {
            "connected": ("status.connected", COLOR_CONNECTED),
            "disconnected": ("status.disconnected", COLOR_DISCONNECTED),
            "connecting": ("status.connecting", COLOR_WAITING),
            "waiting": ("status.waiting", COLOR_WAITING),
            "syncing": ("status.syncing", COLOR_SYNCING),
            "error": ("status.error", COLOR_DISCONNECTED),
        }
        key, color = i18n_map.get(status, ("status.unknown", COLOR_DISCONNECTED))
        self._status_dot.setStyleSheet(f"color: {color.name()}; font-size: 14px;")
        self._status_label.setText(tr(key))
        if self._tray:
            self._tray.update_status(status)

    @Slot(str)
    def _on_status(self, status: str) -> None:
        self._set_status_label(status)
        # "Local" rows are grey only while a link can compare them, so the idle
        # list keeps the default text colour instead of looking disabled.
        self._file_panel.set_connected(status == "connected")
        # The role text appears only once connected (icon is always shown in p2p).
        self._connected = status == "connected"
        self._apply_role_visibility()

        if status in ("disconnected", "waiting"):
            # The peer count is only meaningful while connected: clear it so a
            # stale "N/M" does not outlive the link. Per-file statuses keep their
            # last known value: losing the link makes the comparison stale, it
            # does not make a synced file local.
            self._peers_label.setText("–")
            self._set_sync_state("offline" if self._ever_connected else "idle")
            # "Connection lost" only makes sense after a real connection: a
            # one-shot that never linked must not claim a lost connection.
            if status == "disconnected" and self._ever_connected and not self._user_stopped:
                self._notify_warning(tr("notif.connection_lost"), tr("notif.connection_lost_msg"))
        elif status == "connected":
            self._ever_connected = True
            # The dry-run preview phase is over: the client is linked and no
            # further SYNC retry is needed (see _show_preview_summary).
            self._is_dry_run_preview = False
            self._awaiting_preview_for_sync = False
            # A new link carries no file-set answer yet: the refresh below asks
            # for one, so the label reads "checking" until the preview answers.
            self._set_sync_state("checking")
            # Refresh path display (server_ip now available)
            self._update_path_display()
            # A scoped Send/Receive owns its banner; only the normal flow hides
            # it and auto-runs the preview on connect.
            if not self._selection_sync_active:
                if self._info_banner_kind == "progress":
                    self._hide_info_banner()
                if self._engine.is_running:
                    self._on_connected_refresh()
        if debug_events.enabled():
            debug_events.log(
                "status_applied",
                status=status,
                connected=self._connected,
                rows=len(self._file_panel.table._transfers),
            )

    def _on_connected_refresh(self) -> None:
        """Refresh the file list after a connect, with a one-off catch-up.

        The realtime channel is opened only after the initial sync, so peer
        changes made meanwhile (e.g. a remote delete) were not delivered. On the
        first connect of a p2p run, mark them with a preview and run one real
        cycle now instead of waiting for the periodic resync. Later reconnects
        only refresh the preview.

        The catch-up is credited only when the preview answers
        (``_on_preview_ended``): a command the client never consumed (e.g. a
        master whose role has no stdin reader) must not burn the one-shot.
        """
        if self._p2p_enabled and not self._initial_reconcile_done:
            self._pending_initial_reconcile = True
            self._engine.preview()
            self._engine.sync()
        else:
            self._engine.preview()

    # ── Sync state (link status ≠ file-set state) ────────────────────────

    def _set_sync_state(
        self, state: str, downloads: int = 0, uploads: int = 0, others: int = 0
    ) -> None:
        """Remember the file-set state and render it in the bottom bar.

        States: ``idle`` (no run/no link), ``checking`` (a preview is running),
        ``no_devices`` (nothing to compare against), ``in_sync``, ``pending``
        (downloads/uploads) and ``pending_other`` (only deletes/renames).
        """
        self._sync_state = (state, downloads, uploads, others)
        self._render_sync_state()

    def _render_sync_state(self) -> None:
        """Render the remembered sync state with the active language."""
        label = getattr(self, "_sync_state_label", None)
        if label is None:
            return
        state, downloads, uploads, others = self._sync_state
        if state == "pending":
            text = (
                tr("sync.state.pending")
                .replace("{download}", str(downloads))
                .replace("{upload}", str(uploads))
            )
        elif state == "pending_other":
            text = tr("sync.state.pending_other").replace("{count}", str(others))
        else:
            text = tr(f"sync.state.{state}")
        label.setText(text)

    def _on_sync_state_settled(self) -> None:
        """Render the summary after a marker-less ``file_status`` burst."""
        self._set_sync_state(*self._sync_state_after_preview())

    def _sync_state_after_preview(self) -> tuple[str, int, int, int]:
        """Derive the file-set state from the preview counters just collected.

        A preview that classified nothing while the table has rows is not "in
        sync": the other device has not published what it holds yet (the
        serving device answers ``preview_start``/``preview_end`` only), so the
        answer is still pending.
        """
        stats = self._preview_stats
        downloads = stats.to_download
        uploads = stats.to_upload
        others = stats.to_delete + stats.to_rename
        if downloads or uploads:
            return "pending", downloads, uploads, others
        if others:
            return "pending_other", 0, 0, others
        if stats.synced or self._file_panel.table.model().rowCount() == 0:
            return "in_sync", 0, 0, 0
        if self._sync_state[0] in ("no_devices", "waiting_inventory", "offline"):
            # Keep the honest waiting/stale state: a burst that classified
            # nothing is not evidence of being in sync.
            return self._sync_state
        return "checking", 0, 0, 0

    # ── Info banner ──────────────────────────────────────────────────────

    @Slot(int, int)
    def _on_folder_size(self, local_bytes: int, total_bytes: int) -> None:
        """Show the client-provided local/sync-set totals while the engine runs."""
        self._share_local_bytes = local_bytes
        self._share_total_bytes = total_bytes
        self._render_share_size()

    @Slot(int, int)
    def _on_peers(self, connected: int, total: int) -> None:
        self._peers_label.setText(f"{connected}/{total}")
        if self._p2p_enabled:
            if total <= 1:
                # Alone in the group: there is no file set to compare against.
                self._set_sync_state("no_devices")
            elif self._sync_state[0] == "no_devices":
                # A device joined: wait for its inventory before claiming one.
                self._set_sync_state("checking")
        if self._notifier:
            self._notifier.peer_joined(connected, total)
        # Scoped op in progress: surface how many other devices are in reach.
        if self._selection_sync_active and total > 1:
            self._show_info_banner(
                tr("sync.sel_peers_fmt").replace("{count}", str(total - 1)),
                auto_hide_ms=0,
                kind="progress",
            )

    @Slot(bool)
    def _on_master(self, is_master: bool) -> None:
        self._role_known = True
        self._is_master = is_master
        self._retranslate_role()
        if is_master and self._notifier:
            self._notifier.became_master()

    @Slot(str)
    def _on_group_detected(self, group: str) -> None:
        """Update the group label in the bottom bar and the p2p label in the top bar."""
        self._group_label.setText(group)
        # Also update the remote label if p2p mode is active
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)):
            self._remote_label.setText(f"p2p ({group})" if group else "p2p")
            self._group_label.hide()

    def _refresh_transfer_labels(self) -> None:
        """Render the session sent/received counters (distinct files + bytes)."""
        st = self._engine.stats
        self._sent_label.setText(f"{st.files_sent} ({format_bytes(st.bytes_sent)})")
        self._recv_label.setText(f"{st.files_received} ({format_bytes(st.bytes_received)})")

    def _rel_path(self, path: str) -> str:
        """Map a client-reported absolute path onto the table's relative key."""
        base = self._local_path
        if base and path.startswith(base):
            return path[len(base) :].lstrip("/\\")
        return path

    @Slot(str, str, int)
    def _on_file_transferred(self, direction: str, filename: str, size: int) -> None:
        # Count real transfers of a scoped one-shot for its result summary.
        if (
            self._selection_sync_active
            and self._selection_sync_phase == "run"
            and direction in ("↓", "↑")
        ):
            self._selection_result_count += 1
        self._refresh_transfer_labels()
        rel_path = self._rel_path(filename)
        # Read the current mtime (and the size, when the event omits it) from disk.
        mtime = 0.0
        if direction in ("↓", "↑") and self._local_path:
            try:
                st = os.stat(os.path.join(self._local_path, rel_path))
                mtime = st.st_mtime
                if size <= 0:
                    size = st.st_size
            except OSError:
                pass
        # Gather CID and server IP for detail panel
        client_cid = self._engine.cid
        client_ip = self._engine.server_ip
        # Update file panel with actual transfer
        if direction == "↓":
            if self._notifier:
                self._notifier.download_complete(filename)
            self._file_panel.update_file_status(
                rel_path,
                "synced",
                size=size,
                mtime=mtime,
                client_cid=client_cid,
                client_ip=client_ip,
            )
        elif direction == "↑":
            self._file_panel.update_file_status(
                rel_path,
                "synced",
                size=size,
                mtime=mtime,
                client_cid=client_cid,
                client_ip=client_ip,
            )
        elif direction == "✕":
            # File was deleted - show briefly then remove
            self._file_panel.mark_deleted(rel_path)
        if debug_events.enabled():
            row = self._file_panel.table._transfers.get(rel_path)
            stats = self._engine.stats
            debug_events.log(
                "transfer_applied",
                file=rel_path,
                direction=direction,
                size=size,
                row_status=row.status.value if row else None,
                bytes_received=stats.bytes_received,
                bytes_sent=stats.bytes_sent,
            )

    @Slot(str, int, int, str)
    def _on_file_progress(
        self, filepath: str, bytes_transferred: int, total_bytes: int, op: str
    ) -> None:
        """Handle real-time file transfer progress updates."""
        rel = self._rel_path(filepath)
        self._file_panel.update_transfer_progress(rel, bytes_transferred, total_bytes, op)
        if debug_events.enabled():
            row = self._file_panel.table._transfers.get(rel)
            debug_events.log(
                "progress_applied",
                file=rel,
                op=op,
                transferred=bytes_transferred,
                total=total_bytes,
                row_status=row.status.value if row else None,
            )

    @Slot(str, str)
    def _on_file_renamed(self, old_path: str, new_path: str) -> None:
        """Handle a file rename event from the engine."""
        base_path = self._local_path
        old_rel = old_path
        new_rel = new_path
        if base_path:
            if old_path.startswith(base_path):
                old_rel = old_path[len(base_path) :].lstrip("/\\")
            if new_path.startswith(base_path):
                new_rel = new_path[len(base_path) :].lstrip("/\\")
        # Read the mtime from the filesystem: the destination once the rename
        # has landed, otherwise the source (the event can arrive just before the
        # local rename is applied).
        mtime = 0.0
        if base_path:
            for candidate in (new_rel, old_rel):
                try:
                    mtime = os.stat(os.path.join(base_path, candidate)).st_mtime
                    break
                except OSError:
                    continue
        # Gather CID and server IP
        client_cid = self._engine.cid
        client_ip = self._engine.server_ip
        self._file_panel.rename_file(
            old_rel,
            new_rel,
            mtime=mtime,
            client_cid=client_cid,
            client_ip=client_ip,
        )
        if debug_events.enabled():
            row = self._file_panel.table._transfers.get(new_rel)
            debug_events.log(
                "file_renamed_applied",
                old=old_rel,
                new=new_rel,
                row_status=row.status.value if row else None,
            )
        # A rename can merge two tracked paths into one, changing the distinct
        # file count even though no bytes moved.
        self._refresh_transfer_labels()

    @Slot(str)
    def _on_directory_created(self, dirpath: str) -> None:
        """Handle a directory creation event from the engine."""
        base_path = self._local_path
        rel_path = dirpath
        if base_path and dirpath.startswith(base_path):
            rel_path = dirpath[len(base_path) :].lstrip("/\\")
        # Read directory metadata from filesystem
        mtime = 0.0
        if base_path:
            try:
                full = os.path.join(base_path, rel_path)
                mtime = os.stat(full).st_mtime
            except OSError:
                pass
        # Gather CID and server IP
        client_cid = self._engine.cid
        client_ip = self._engine.server_ip
        # Folder entries use a trailing slash as their key; normalize so the
        # sync status updates the same row instead of creating a file-like key.
        dir_key = rel_path.strip("/\\").replace("\\", "/")
        if dir_key:
            self._file_panel.update_file_status(
                dir_key + "/",
                "synced",
                size=0,
                mtime=mtime,
                client_cid=client_cid,
                client_ip=client_ip,
            )

    @Slot(str, str, str)
    def _on_master_conflict(self, conflict_type: str, peer_cid: str, peer_address: str) -> None:
        """Handle a prefer_master conflict or takeover notification.

        A ``takeover`` means the peer is configured to prefer the primary role
        and this device is not, so the handover is the expected election
        outcome: it is logged but does not raise a warning (the new role is
        shown in the status bar). Only a genuine two-prefer_master conflict
        (``conflict_lost`` / ``conflict_won``) is surfaced as a warning.
        """
        if conflict_type == "conflict_lost":
            msg = (
                tr("notif.master_conflict_lost")
                .replace("{cid}", peer_cid)
                .replace("{ip}", peer_address)
            )
        elif conflict_type == "conflict_won":
            msg = (
                tr("notif.master_conflict_won")
                .replace("{cid}", peer_cid)
                .replace("{ip}", peer_address)
            )
        else:  # takeover by a peer that prefers the primary role
            msg = (
                tr("notif.master_takeover").replace("{cid}", peer_cid).replace("{ip}", peer_address)
            )
            self._append_desktop_log("INFO", msg)
            return
        self._notify_warning(tr("notif.master_conflict_title"), msg)
        self._append_desktop_log("WARNING", msg)

    @Slot(str, str, str)
    def _on_transfer_failed(self, op: str, filepath: str, message: str) -> None:
        """Surface a per-file transfer that gave up after retries."""
        arrow = "↑" if op == "upload" else "↓"
        self._append_desktop_log("ERROR", f"{arrow} {filepath}: {message}")
        # The row would otherwise keep showing an in-flight progress bar.
        self._file_panel.mark_failed(self._rel_path(filepath))
        # Per-file failures are aggregated into one in-app error toast (updated
        # in place, so a burst cannot flood the window); the OS notification
        # stays per file. Continuous runs never reach _on_process_finished, so
        # surfacing it here is what makes the failure visible in the window.
        self._transfer_failure_count += 1
        if not self._selection_sync_active:
            self._show_info_banner(
                tr("notif.transfers_failed").replace("{count}", str(self._transfer_failure_count)),
                kind="error",
                title=tr("notif.error"),
            )
        if self._notifier:
            self._notifier.error(tr("notif.error"), message)

    @Slot(str, int, int)
    def _on_sync_paused(self, reason: str, deletes: int, _local: int) -> None:
        """Surface the mass-deletion guard pausing the delete phase."""
        msg = (
            tr("notif.sync_paused_msg")
            .replace("{deletes}", str(deletes))
            .replace("{reason}", reason)
        )
        self._notify_warning(tr("notif.sync_paused_title"), msg)
        self._append_desktop_log("WARNING", msg)

    @Slot(str, str, str)
    def _on_security_rejected(self, op: str, path: str, message: str) -> None:
        """Surface an unsafe remote path refused by the client's inbound guards."""
        msg = tr("notif.security_rejected_msg").replace("{path}", path or "?")
        self._notify_warning(tr("notif.security_rejected_title"), msg)
        detail = f" ({op}: {message})" if message else f" ({op})"
        self._append_desktop_log("WARNING", f"{msg}{detail}")

    @Slot(str)
    def _on_no_master_warning(self, _detail: str) -> None:
        """Handle the [NO MASTER] warning (no node will serve files)."""
        msg = tr("notif.no_master_msg")
        self._notify_warning(tr("notif.no_master_title"), msg)
        self._append_desktop_log("WARNING", msg)

    @Slot(str)
    @Slot(str)
    def _on_sync_pending(self, reason: str) -> None:
        """The master cannot classify the share yet: show a waiting state.

        ``reason`` is ``awaiting_inventory`` (a device is connected but has not
        published what it holds) or ``no_device`` (nothing to compare against).
        Neither is a verdict on the files: never "all synced", and never "no
        device found" while a device is connected.
        """
        if reason == "awaiting_inventory":
            self._set_sync_state("waiting_inventory")
            return
        self._set_sync_state("no_devices")
        if self._selection_sync_active:
            self._finish_selection_sync("no_devices")

    def _on_no_peers(self, _message: str) -> None:
        """A p2p one-shot aborted with no peer: the scoped op has no target."""
        self._set_sync_state("no_devices")
        if self._selection_sync_active:
            self._finish_selection_sync("no_devices")

    @Slot()
    def _on_sync_completed(self) -> None:
        """Finish a scoped Send/Receive once the one-shot cycle completes."""
        was_scoped = self._selection_sync_active
        if was_scoped and self._selection_sync_phase == "run":
            outcome = "done" if self._selection_result_count > 0 else "already_synced"
            self._finish_selection_sync(outcome)
        # The cycle just moved files: recompute the local size instead of keeping
        # the value the client reported before its transfers.
        self._file_panel.refresh_share_size()
        if not was_scoped and self._engine.is_running:
            # The cycle may have reconciled a path whose live rename/add event
            # was missed while the link was down (the scan then shows a stale
            # "Local"). Refresh the statuses so a file now present on both sides
            # reads "Synced" again instead of waiting for the next connect/manual
            # preview.
            self._engine.preview()

    @Slot()
    def _on_files_added_on_disk(self) -> None:
        """Refresh the statuses when the scan finds paths outside the event flow.

        A remote rename/add event lost while the link was down leaves the new
        path created by the consistency scan as a stale "Local"; a preview
        classifies it (typically "Synced") within the scan interval instead of
        waiting for the periodic sync.

        The scan reports the whole batch, so a burst of missed renames is one
        call, not one per file. The cooldown caps the extra full scans too: a
        continuous stream of external renames cannot trigger one every 5 s.
        """
        if not (
            self._engine.is_running
            and self._connected
            and self._p2p_enabled
            and not self._selection_sync_active
        ):
            return
        now = time.monotonic()
        if now - self._last_scan_preview_at < _SCAN_PREVIEW_COOLDOWN_S:
            return
        self._last_scan_preview_at = now
        self._engine.preview()

    @Slot(str, str)
    def _on_duplicate_identity(self, peer_cid: str, peer_address: str) -> None:
        """Handle a duplicated device identity (cloned HSYNC_DEVICE_DIR)."""
        peer = peer_address or "?"
        msg = tr("notif.duplicate_identity_msg").replace("{cid}", peer_cid).replace("{ip}", peer)
        self._notify_warning(tr("notif.duplicate_identity_title"), msg)
        self._append_desktop_log("WARNING", msg)

    @Slot(str, str)
    def _on_conflict_resolved(self, filepath: str, conflict_copy: str) -> None:
        """Handle a file conflict resolved by keeping the remote version."""
        msg = (
            tr("notif.conflict_resolved_msg")
            .replace("{file}", filepath)
            .replace("{conflict_copy}", conflict_copy)
        )
        if self._notifier:
            self._notifier.info(tr("notif.conflict_resolved_title"), msg)
        self._append_desktop_log("INFO", msg)

    # ── Trust refusal dialogs (SSH-style, no terminal) ──────────────────────

    @Slot()
    def _on_preview_started(self) -> None:
        """Handle preview scan started."""
        self._append_log("--- Updating file status... ---")
        # Reset preview statistics
        self._preview_stats.reset()
        self._set_sync_state("checking")

    @Slot()
    def _on_preview_ended(self) -> None:
        """Handle preview scan ended."""
        self._append_log("--- File status updated ---")
        self._set_sync_state(*self._sync_state_after_preview())
        # A serving device answers this window's own PREVIEW with a
        # classification, which is not the preview cycle it is waiting for: the
        # dry-run preview only runs once the node is a slave. Consuming the
        # confirmation here showed a summary with the wrong counters and left the
        # dry run parked (no SYNC ever reached it).
        if self._p2p_enabled and self._is_master:
            return
        # The preview answered: it is now safe to credit the one-shot catch-up.
        if self._pending_initial_reconcile:
            self._pending_initial_reconcile = False
            self._initial_reconcile_done = True
        # Show summary dialog if awaiting sync confirmation
        if self._awaiting_preview_for_sync:
            self._awaiting_preview_for_sync = False
            self._show_preview_summary()

    @Slot(str, str, int)
    def _on_file_status(self, status: str, filepath: str, size: int) -> None:
        """Handle file status from preview."""
        # Convert absolute path to relative path for table lookup
        base_path = self._local_path
        rel_path = filepath
        if base_path and filepath.startswith(base_path):
            rel_path = filepath[len(base_path) :].lstrip("/\\")
        self._file_panel.update_file_status(rel_path, status, size, preview=True)
        # A serving device re-classifies without a preview cycle: settle the
        # summary once its file_status burst goes quiet.
        self._sync_state_timer.start()
        if debug_events.enabled():
            row = self._file_panel.table._transfers.get(rel_path)
            debug_events.log(
                "preview_file_status",
                file=rel_path,
                raw=filepath,
                base=base_path,
                status=status,
                size=size,
                row_status=row.status.value if row else None,
            )
        # Accumulate preview statistics
        if status == "to_download":
            self._preview_stats.to_download += 1
            self._preview_stats.download_size += size
        elif status == "to_upload":
            self._preview_stats.to_upload += 1
            self._preview_stats.upload_size += size
        elif status == "to_delete":
            self._preview_stats.to_delete += 1
        elif status == "synced":
            self._preview_stats.synced += 1

    @Slot(str, int)
    def _on_file_rename_status(self, old_path: str, size: int) -> None:
        """Handle file rename status from preview."""
        base_path = self._local_path
        rel_old = old_path
        if base_path and old_path.startswith(base_path):
            rel_old = old_path[len(base_path) :].lstrip("/\\")
        self._file_panel.update_file_status(rel_old, "to_rename", size, preview=True)
        self._preview_stats.to_rename += 1

    @Slot(int, str)
    def _on_startup_failed(self, code: int, tail: str) -> None:
        """Present an engine that exited before it reported readiness.

        The structured-reason path arrives as ``error(reason="startup")``; this
        is the safety net for older clients, crashes, and failures that happened
        before the client could emit the event.
        """
        self._startup_failure_tail = tail
        self._present_startup_failure(code)

    def _present_startup_failure(self, code: int) -> None:
        """Report a startup failure once per run (manual modal / automatic tray)."""
        if self._startup_failure_surfaced:
            return
        self._startup_failure_surfaced = True
        detail = (self._startup_error_message or self._startup_failure_tail).strip()
        # The structured path already mirrored its message into the log; the
        # safety-net tail is only in the engine's transient buffer, so record it.
        if detail and not self._startup_error_message:
            self._append_desktop_log("ERROR", detail.replace("\n", " "))
        self._report_engine_start_failure(
            code=code,
            detail=detail,
            automatic=self._start_is_automatic,
        )

    @Slot(int, str)
    def _on_process_finished(self, code: int, desc: str) -> None:
        # A run that never reached readiness and reported a structured startup
        # error is presented here, where the exit code is known. The exit-time
        # safety net (``_on_startup_failed``) handles the no-event case first.
        if self._startup_error_message and not self._startup_failure_surfaced:
            self._present_startup_failure(code)
        # A scoped Send/Receive that ended without a typed outcome (crash, user
        # stop) is finalized here; while the confirmation dialog is open
        # (phase "confirm") the op is still in flight and must not be closed.
        was_scoped = self._selection_sync_active
        if self._selection_sync_active and self._selection_sync_phase != "confirm":
            if self._user_stopped:
                self._finish_selection_sync("cancelled")
            else:
                outcome = "done" if self._selection_result_count > 0 else "failed"
                self._finish_selection_sync(outcome)
        self._ever_connected = False
        # Reset the p2p role too: the next process runs a fresh election.
        self._role_known = False
        self._is_master = None
        self._connected = False
        # The sync-set total belongs to the engine session; keep the scan local.
        self._share_total_bytes = -1
        self._retranslate_role()
        self._render_share_size()
        # The run moved files: rescan so the local size is post-sync, not the
        # value the client reported at the start of its last cycle.
        self._file_panel.refresh_share_size()
        # No engine process means no live connection: drop the status out of
        # "connecting"/"connected" (the client cannot report the final state)
        # and clear the now-meaningless peer count.
        self._set_status_label("disconnected")
        # Interrupted transfers never report an outcome: clear their rows.
        self._file_panel.clear_transient_progress(self._local_path or "")
        self._file_panel.set_connected(False)
        self._peers_label.setText("–")
        self._btn_start.setEnabled(bool(self._local_path))
        self._btn_stop.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        if self._tray:
            self._tray.set_running(False)
        # Keep result/error toasts visible after the process exits; clear only
        # run-scoped progress/info toasts.
        self._clear_run_toast()
        self._apply_button_styles()
        self._update_menu_state()
        self._append_log(f"--- Process finished ({desc}, exit code {code}) ---")

        # Notify only for truly unexpected crashes (not user stop, auth error,
        # force sync, app quit, etc.). A startup failure already has its own
        # report, so it must not also raise the generic crash toast.
        if desc == "crashed" and not self._user_stopped and not self._startup_failure_surfaced:
            self._notify_error(
                tr("notif.error"),
                tr("notif.process_crashed").replace("{code}", str(code)),
            )
        elif not was_scoped and not self._user_stopped and self._transfer_failure_count > 0:
            # Consolidate per-file failures into one toast at the end of a run.
            self._show_info_banner(
                tr("notif.transfers_failed").replace("{count}", str(self._transfer_failure_count)),
                kind="error",
                title=tr("notif.error"),
            )
        self._transfer_failure_count = 0

    @Slot(str)
    def _on_path_not_found(self, path: str) -> None:
        """Handle shared path not found error."""
        self._engine.stop()
        self._reset_ui_stopped()
        self._append_desktop_log("WARNING", tr("notif.path_not_found_msg").replace("{path}", path))
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("notif.error"))
        msg.setText(tr("notif.path_not_found_msg").replace("{path}", path))
        msg.setStandardButtons(QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close)
        open_btn = msg.button(QMessageBox.StandardButton.Open)
        open_btn.setText(tr("menu.settings"))
        close_btn = msg.button(QMessageBox.StandardButton.Close)
        close_btn.setText(tr("action.close"))
        msg.setDefaultButton(QMessageBox.StandardButton.Open)
        if msg.exec() == QMessageBox.StandardButton.Open:
            self._open_settings(initial_tab=0)
