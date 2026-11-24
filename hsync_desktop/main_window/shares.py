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

from collections.abc import Callable
from typing import NamedTuple

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QMenu,
    QMessageBox,
    QToolButton,
)

from hsync_desktop.config import (
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_P2P_ENABLED,
    DEFAULT_SERVER_TRUST,
    DEFAULT_SYNC_DIRECTION,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.engine import (
    AsyncProbe,
    ProbeOutcome,
    ShareTrust,
    check_share_access,
    find_hsync_binary,
    normalize_server_endpoint,
    provision_share_bucket,
)
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon
from hsync_desktop.probe_messages import probe_reason_text
from hsync_desktop.shares import Share, ShareStore
from hsync_desktop.widgets.dialogs import (
    build_choice_box,
    confirm,
    dialog_parent,
    show_warning,
)
from hsync_desktop.widgets.name_dialog import ask_name

_DIRECTION_KEYS = {
    "bidirectional": "settings.sync_direction.bidirectional",
    "upload-only": "settings.sync_direction.upload_only",
    "download-only": "settings.sync_direction.download_only",
}


class _ShareTarget(NamedTuple):
    """What a share creation must confirm on the server before the record exists."""

    base_url: str
    bucket: str
    api_key: str
    trust: ShareTrust
    timeout: float


_PendingShare = tuple[str, str, str | None, Callable[[bool], None] | None, _ShareTarget]


class SharesMixin:
    # Declared so the composed MainWindow shares the types (see window.py).
    _share_store: ShareStore
    _shares_button: QToolButton
    _shares_menu: QMenu
    _local_path: str
    _bucket: str
    _log_active_share: str
    _share_probe: AsyncProbe
    _pending_share: _PendingShare | None

    # ── setup ──────────────────────────────────────────────────────────────
    def _init_shares_ui(self) -> None:
        """Wire the header selector (the button itself is built by UiBuildMixin)."""
        self._shares_menu = QMenu(self._shares_button)
        self._shares_menu.aboutToShow.connect(self._rebuild_shares_menu)
        self._shares_button.setMenu(self._shares_menu)
        self._log_active_share = self._share_store.active_id()
        # One probe for the create/duplicate check: the record is written only
        # once the server confirmed the bucket it will sync into.
        self._pending_share = None
        self._share_probe = AsyncProbe(self)
        self._share_probe.done.connect(self._on_share_access_outcome)
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
        for share in store.shares_sorted():
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
            dialog_parent(self),
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
        QMessageBox.warning(dialog_parent(self), tr("shares.manage.title"), message)

    def _create_share(
        self, name: str, folder: str, *, on_done: Callable[[bool], None] | None = None
    ) -> bool:
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
        active = store.active()
        return self._create_with_access_check(
            name, folder, dict(active.values) if active is not None else {}, None, on_done
        )

    def _duplicate_share(
        self,
        share_id: str,
        name: str,
        folder: str,
        *,
        on_done: Callable[[bool], None] | None = None,
    ) -> bool:
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
        source = store.get(share_id)
        return self._create_with_access_check(
            name, folder, dict(source.values) if source is not None else {}, share_id, on_done
        )

    # ── creation with the share-access check ───────────────────────────────
    def _create_with_access_check(
        self,
        name: str,
        folder: str,
        values: dict,
        source_id: str | None,
        on_done: Callable[[bool], None] | None,
    ) -> bool:
        """Create the share now, or once the server confirmed its new bucket.

        A share created in server mode gets a bucket name the server has never
        seen (``ShareStore.bucket_for``) — the situation the setup wizard's
        connection step already handles with "create the share on the server".
        Asking *before* the record exists is what keeps a refused prompt from
        leaving a share that can never sync. Returns False only when the request
        was refused; True means created now or deferred to the check.
        """
        target = self._share_target(values, ShareStore.bucket_for(name, folder))
        if target is None:
            return self._finish_share_creation(name, folder, source_id, on_done)
        self._pending_share = (name, folder, source_id, on_done, target)
        self._start_share_probe(provision=False)
        return True

    def _share_target(self, values: dict, bucket: str) -> _ShareTarget | None:
        """What a server-mode share must confirm, or ``None`` in direct mode.

        ``None`` also covers a share with no server or no key: there is nothing
        to confirm, so the creation stays offline and the first sync reports it.
        """
        if bool(values.get("p2p/enabled", DEFAULT_P2P_ENABLED)):
            return None
        base = normalize_server_endpoint(str(values.get("connection/server_url", "")).strip())
        api_key = decrypt_value(str(values.get("connection/api_key", ""))).strip()
        if base is None or not api_key:
            return None
        trust = ShareTrust(
            policy=str(values.get("connection/server_trust", DEFAULT_SERVER_TRUST)),
            insecure=bool(values.get("connection/insecure", False)),
            ca_cert=str(values.get("connection/ca_cert", "")),
            binary=find_hsync_binary(),
        )
        timeout = float(max(5, int(values.get("connection/http_timeout", DEFAULT_HTTP_TIMEOUT))))
        return _ShareTarget(base, bucket, api_key, trust, timeout)

    def _start_share_probe(self, *, provision: bool) -> None:
        """Run the share check (or the bucket creation) off the UI thread."""
        pending = self._pending_share
        if pending is None:
            return
        target = pending[4]
        operation = provision_share_bucket if provision else check_share_access
        self._share_probe.start(
            lambda: operation(
                target.base_url,
                target.bucket,
                target.api_key,
                trust=target.trust,
                timeout=target.timeout,
            )
        )

    def _on_share_access_outcome(self, outcome: object) -> None:
        """Finish, offer to create, or drop a share creation the server answered."""
        pending = self._pending_share
        if pending is None or not isinstance(outcome, ProbeOutcome):
            return
        if outcome.ok:
            self._finish_share_creation(*pending[:4])
            return
        if outcome.reason == "share_missing":
            self._ask_create_missing_bucket()
            return
        if outcome.reason in ("unreachable", "server_error"):
            # Offline work must stay possible: the bucket may be fine, and a
            # missing share only shows up on the first sync anyway.
            if confirm(
                dialog_parent(self),
                title=tr("settings.bucket_probe.title"),
                text=tr("settings.bucket_probe.offline"),
                with_icons=True,
            ):
                self._finish_share_creation(*pending[:4])
            else:
                self._drop_pending_share()
            return
        if outcome.reason == "create_quota":
            show_warning(
                dialog_parent(self),
                title=tr("settings.bucket_probe.title"),
                text=tr("settings.bucket_probe.quota").replace("{max}", str(outcome.limit or "")),
            )
        elif outcome.reason == "create_failed":
            show_warning(
                dialog_parent(self),
                title=tr("settings.bucket_probe.title"),
                text=tr("settings.bucket_probe.create_failed"),
            )
        else:
            show_warning(
                dialog_parent(self),
                title=tr("shares.manage.title"),
                text=probe_reason_text(outcome.reason),
            )
        self._drop_pending_share()

    def _ask_create_missing_bucket(self) -> None:
        """404 means "missing" or "no membership": creating it is the way forward."""
        box, buttons = build_choice_box(
            dialog_parent(self),
            title=tr("settings.bucket_probe.title"),
            text=tr("settings.bucket_probe.missing"),
            choices=[
                (tr("settings.bucket_probe.create"), "list-add"),
                (tr("settings.bucket_probe.save_anyway"), "dialog-ok"),
                (tr("action.cancel"), "dialog-cancel"),
            ],
            default_index=0,
        )
        box.exec()
        clicked = box.clickedButton()
        if clicked is buttons[0]:
            self._start_share_probe(provision=True)
            return
        pending = self._pending_share
        if clicked is buttons[1] and pending is not None:
            self._finish_share_creation(*pending[:4])
            return
        self._drop_pending_share()

    def _finish_share_creation(
        self,
        name: str,
        folder: str,
        source_id: str | None,
        on_done: Callable[[bool], None] | None,
    ) -> bool:
        """Write the record, activate the share and report the outcome."""
        self._pending_share = None
        store = self._share_store
        share = (
            store.duplicate(source_id, name, folder)
            if source_id is not None
            else store.create_from_active(name, folder)
        )
        self._switch_to_share(share.id)
        self._sync_shares_button()
        if on_done is not None:
            on_done(True)
        return True

    def _drop_pending_share(self) -> None:
        """Forget a creation the user (or the server) refused."""
        pending = self._pending_share
        self._pending_share = None
        if pending is not None and pending[3] is not None:
            pending[3](False)

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

    def _delete_share(self, share_id: str, clear_state: bool, next_active: str = "") -> bool:
        """Delete a share; *next_active* is the neighbour the caller wants next.

        The client-state reset runs before the record is removed: a failed reset
        (unreadable state, missing client) would otherwise leave the user without
        the share that could be retried.
        """
        store = self._share_store
        if len(store.shares()) <= 1:
            self._warn(tr("shares.error.last"))
            return False
        share = store.get(share_id)
        folder = str(share.values.get("path/local", "")) if share else ""
        was_active = share_id == store.active_id()
        # Clearing the client state needs the engine stopped: its reset is
        # refused while any sync runs.
        if self._engine.is_running and (was_active or clear_state):
            if not self._confirm_stop_for_switch():
                return False
        if clear_state and folder:
            self._reset_sync_state(folder)
        new_active = store.delete(share_id, next_active=next_active)
        self._log_buffers.pop(share_id, None)
        if was_active and new_active:
            store.apply(new_active)
            self._reset_for_share_switch()
        self._sync_shares_button()
        return True

    # ── header actions ─────────────────────────────────────────────────────
    def _on_new_share(self) -> None:
        """Create a share from the active one, then open Settings to refine it."""
        name = ask_name(
            self,
            title=tr("shares.new.title"),
            label=tr("shares.new.name"),
            accept_text_key="shares.manage.new",
        )
        if not name:
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
