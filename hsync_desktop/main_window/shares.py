# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""SharesMixin: the header share selector and the switch/manage flows.

The store keeps every saved share and writes the active one into the flat
``QSettings`` keys. This mixin owns the header selector, the switch flow
(confirm → stop → snapshot → apply → stay stopped) and the manage operations the
``SharesDialog`` delegates back to (so the engine is only ever touched here).
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QToolButton,
)

from hsync_desktop.config import DEFAULT_SYNC_DIRECTION
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon
from hsync_desktop.shares import Share, ShareStore
from hsync_desktop.widgets.dialogs import confirm

_DIRECTION_KEYS = {
    "bidirectional": "menu.sync.direction.bidirectional",
    "upload-only": "menu.sync.direction.upload_only",
    "download-only": "menu.sync.direction.download_only",
}


class SharesMixin:
    # Declared so the composed MainWindow shares the types (see window.py).
    _share_store: ShareStore
    _shares_button: QToolButton
    _shares_menu: QMenu
    _local_path: str
    _bucket: str
    _log_active_share: str

    # ── setup ──────────────────────────────────────────────────────────────
    def _init_shares_ui(self) -> None:
        """Wire the header selector (the button itself is built by UiBuildMixin)."""
        self._shares_menu = QMenu(self._shares_button)
        self._shares_menu.aboutToShow.connect(self._rebuild_shares_menu)
        self._shares_button.setMenu(self._shares_menu)
        self._log_active_share = self._share_store.active_id()
        self._sync_shares_button()

    def _sync_shares_button(self) -> None:
        """Show the selector only when at least one share exists."""
        self._shares_button.setVisible(self._share_store.has_shares())

    @staticmethod
    def _share_is_p2p(share: Share) -> bool:
        return bool(share.values.get("p2p/enabled", True))

    def _share_tooltip(self, share: Share) -> str:
        lines: list[str] = []
        folder = str(share.values.get("path/local", ""))
        if folder:
            lines.append(f"{tr('shares.tip.folder')}: {folder}")
        bucket = str(share.values.get("sync/bucket", ""))
        if bucket:
            lines.append(f"{tr('shares.tip.bucket')}: {bucket}")
        direction = str(share.values.get("sync/direction", DEFAULT_SYNC_DIRECTION))
        key = _DIRECTION_KEYS.get(direction)
        if key:
            lines.append(tr(key))
        if self._share_is_p2p(share):
            group = str(share.values.get("p2p/group", "")).strip()
            lines.append(tr("shares.tip.mode_p2p") + (f": {group}" if group else ""))
        else:
            server = str(share.values.get("connection/server_url", "")).strip()
            lines.append(tr("shares.tip.mode_server") + (f": {server}" if server else ""))
        return "\n".join(lines)

    def _active_header_tooltip(self) -> str:
        """Tooltip for the header name: folder + bucket + direction + target."""
        share = self._share_store.active()
        return self._share_tooltip(share) if share is not None else self._local_path

    def _rebuild_shares_menu(self) -> None:
        """Rebuild the selector menu from the store (sorted by name)."""
        self._shares_menu.clear()
        store = self._share_store
        active = store.active_id()
        for share in sorted(store.shares(), key=lambda s: s.name.casefold()):
            action = QAction(self._shares_menu)
            action.setText(share.name or tr("shares.untitled"))
            action.setCheckable(True)
            action.setChecked(share.id == active)
            action.setIcon(icon("network-p2p" if self._share_is_p2p(share) else "network-cloud"))
            action.setToolTip(self._share_tooltip(share))
            action.triggered.connect(
                lambda _checked=False, sid=share.id: self._switch_to_share(sid)
            )
            self._shares_menu.addAction(action)
        self._shares_menu.addSeparator()
        new_action = self._shares_menu.addAction(tr("shares.menu.new"))
        new_action.triggered.connect(self._on_new_share)
        open_action = self._shares_menu.addAction(tr("shares.menu.open_folder"))
        open_action.triggered.connect(self._open_active_folder)
        manage_action = self._shares_menu.addAction(tr("shares.menu.manage"))
        manage_action.triggered.connect(self._on_manage_shares)

    # ── switch ─────────────────────────────────────────────────────────────
    def _confirm_stop_for_switch(self) -> bool:
        """Stop a running sync before a switch; False when the user declines."""
        if not self._engine.is_running:
            return True
        if not confirm(
            self,
            title=tr("shares.switch.confirm_title"),
            text=tr("shares.switch.confirm_stop"),
        ):
            return False
        self._engine.stop_and_wait()
        return True

    def _switch_to_share(self, share_id: str) -> None:
        """Make *share_id* the active projection, stopping a live sync first."""
        store = self._share_store
        if share_id == store.active_id() or store.get(share_id) is None:
            return
        if not self._confirm_stop_for_switch():
            return
        store.snapshot_active()
        store.apply(share_id)
        self._reset_for_share_switch()

    def _reset_for_share_switch(self) -> None:
        """Clear the run-scoped UI state and reload everything for the new share."""
        self._reset_ui_stopped()
        self._bucket = ""
        self._conn_state = "stopped"
        self._conn_reason = ""
        self._conn_badge_replaces_icon = False
        self._link_status = ""
        self._ever_connected = False
        self._user_stopped = False
        self._problems.clear_all()
        self._file_panel.clear()
        self._set_log_share(self._share_store.active_id())
        self._apply_settings_changes()
        self._sync_shares_button()

    def _adopt_log_share(self) -> None:
        """Bind the log identity to the active share when it is not set yet.

        A fresh install creates share #1 from Settings/the wizard, a path that
        never goes through ``_set_log_share``; without this its history is never
        buffered. Already-displayed lines are kept.
        """
        share_id = self._share_store.active_id()
        if not share_id or share_id == self._log_active_share:
            return
        if not self._log_active_share:
            self._seed_log_buffer_from_view(share_id)
        self._log_active_share = share_id

    # ── folder / name ──────────────────────────────────────────────────────
    def _open_active_folder(self) -> None:
        """Open the active share's folder (or the wizard when unconfigured)."""
        if self._local_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._local_path))
        else:
            self._open_setup_wizard()

    def _on_share_name_clicked(self) -> None:
        """Header name click: the shares menu, else the configure affordance."""
        if self._share_store.has_shares():
            self._shares_button.showMenu()
        elif self._local_path:
            self._open_settings(initial_tab=0)
        else:
            self._open_setup_wizard()

    # ── create / manage (also called by SharesDialog) ──────────────────────
    def _folder_is_taken(self, folder: str) -> bool:
        """True when another share already uses *folder* (Settings validator)."""
        active = self._share_store.active()
        return (
            self._share_store.folder_in_use(
                folder, exclude_id=active.id if active is not None else None
            )
            is not None
        )

    def _bucket_is_taken(self, bucket: str) -> bool:
        """True when another share already uses *bucket* (p2p same-device warning)."""
        target = bucket.strip()
        if not target:
            return False
        active = self._share_store.active()
        for share in self._share_store.shares():
            if active is not None and share.id == active.id:
                continue
            if str(share.values.get("sync/bucket", "")).strip() == target:
                return True
        return False

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, tr("shares.manage.title"), message)

    def _create_share(self, name: str, folder: str) -> bool:
        store = self._share_store
        name = name.strip()
        if not name:
            self._warn(tr("shares.error.name_required"))
            return False
        if store.name_in_use(name):
            self._warn(tr("shares.error.name_duplicate"))
            return False
        if not folder:
            self._warn(tr("shares.error.folder_required"))
            return False
        if store.folder_in_use(folder):
            self._warn(tr("shares.error.folder_duplicate"))
            return False
        # Stop a running sync before mutating the book, so a declined prompt
        # never leaves a share that was created but never activated.
        if not self._confirm_stop_for_switch():
            return False
        share = store.create_from_active(name, folder)
        self._switch_to_share(share.id)
        self._sync_shares_button()
        return True

    def _duplicate_share(self, share_id: str, name: str, folder: str) -> bool:
        store = self._share_store
        name = name.strip()
        if not name:
            self._warn(tr("shares.error.name_required"))
            return False
        if store.name_in_use(name):
            self._warn(tr("shares.error.name_duplicate"))
            return False
        if not folder:
            self._warn(tr("shares.error.folder_required"))
            return False
        if store.folder_in_use(folder):
            self._warn(tr("shares.error.folder_duplicate"))
            return False
        if not self._confirm_stop_for_switch():
            return False
        share = store.duplicate(share_id, name, folder)
        self._switch_to_share(share.id)
        self._sync_shares_button()
        return True

    def _rename_share(self, share_id: str, name: str) -> bool:
        store = self._share_store
        name = name.strip()
        if not name:
            self._warn(tr("shares.error.name_required"))
            return False
        if store.name_in_use(name, exclude_id=share_id):
            self._warn(tr("shares.error.name_duplicate"))
            return False
        store.rename(share_id, name)
        if share_id == store.active_id():
            self._update_path_display()
        return True

    def _delete_share(self, share_id: str, clear_state: bool) -> bool:
        store = self._share_store
        if len(store.shares()) <= 1:
            self._warn(tr("shares.error.last"))
            return False
        share = store.get(share_id)
        folder = str(share.values.get("path/local", "")) if share else ""
        was_active = share_id == store.active_id()
        # Clearing the client state needs the engine stopped: its reset is
        # refused while any sync runs, and afterwards the share is already gone.
        if self._engine.is_running and (was_active or clear_state):
            if not self._confirm_stop_for_switch():
                return False
        new_active = store.delete(share_id)
        self._log_buffers.pop(share_id, None)
        if clear_state and folder:
            self._reset_sync_state(folder)
        if was_active and new_active:
            store.apply(new_active)
            self._reset_for_share_switch()
        self._sync_shares_button()
        return True

    # ── header actions ─────────────────────────────────────────────────────
    def _on_new_share(self) -> None:
        """Create a share from the active one, then open Settings to refine it."""
        name, ok = QInputDialog.getText(self, tr("shares.new.title"), tr("shares.new.name"))
        if not ok or not name.strip():
            return
        folder = QFileDialog.getExistingDirectory(self, tr("shares.new.folder"))
        if not folder:
            return
        if self._create_share(name, folder):
            self._open_settings(initial_tab=0)

    def _on_manage_shares(self) -> None:
        from hsync_desktop.shares.dialog import SharesDialog

        SharesDialog(self, self).exec()
        self._sync_shares_button()
