# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Trusted-keys management dialog for HSYNC Desktop.

Lists and edits the three SSH-style trust stores through the hsync-client CLI
(no terminal required): the bootnode and sync-server known-hosts stores and the
P2P known-peers store. Every action is a subprocess helper from
:mod:`hsync_desktop.engine`, so the GUI and the CLI share a single source of
truth per store.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from hsync_common.endpoint import format_authority, parse_host_port
from hsync_common.protocol.pairing import parse_fingerprint
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.config import DEFAULT_P2P_ENABLED, SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.engine import (
    add_bootnode_trust,
    add_peer_pin,
    add_server_trust,
    fetch_bootnode_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    list_bootnode_trust,
    list_peer_pins,
    list_server_trust,
    remove_bootnode_trust,
    remove_peer_pin,
    remove_server_trust,
    supports_peer_trust,
)
from hsync_desktop.file_panel.utils import format_mtime
from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon, style_ok_cancel_button_box

# A host trust helper: ``(binary, host, fingerprint, port) -> bool`` (add) or
# ``(binary, host, port) -> str | None`` (fingerprint probe).
_AddTrust = Callable[..., bool]

# Known-hosts ``source`` values (hsync-client ``known_hosts.py::TRUST_SOURCES``)
# mapped to a user-facing label. An unknown value passes through unchanged.
_SOURCE_KEYS = {
    "cli": "trusted_keys.source_cli",
    "tofu": "trusted_keys.source_tofu",
    "prompt": "trusted_keys.source_prompt",
    "flag": "trusted_keys.source_flag",
}


def _source_label(source: str) -> str:
    """Humanize a known-hosts ``source`` value; unknown values pass through."""
    key = _SOURCE_KEYS.get(source)
    return tr(key) if key else source


def _format_local_time(iso: str) -> str:
    """Render a stored UTC ISO-8601 timestamp in the user's local time.

    The trust stores persist UTC (``...Z``), so showing it verbatim would
    mislead the user. Convert to the local timezone and format it like the file
    panel's modification times (today / yesterday / absolute date). An empty or
    unparsable value is returned unchanged.
    """
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return iso
    return format_mtime(dt.timestamp())


class _HostAddDialog(QDialog):
    """Collect a ``host:port`` + fingerprint (optionally read from the node).

    Shared by the bootnode and sync-server tabs: both stores have the same shape
    and the same probe/add helper signature, so only the placeholder differs.
    """

    def __init__(
        self,
        *,
        fetch_fingerprint: Callable[..., str | None],
        add_trust: _AddTrust,
        placeholder: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("trusted_keys.add"))
        self._binary = find_hsync_binary()
        self._fetch_fingerprint = fetch_fingerprint
        self._add_trust = add_trust

        self.host_edit = QLineEdit(self)
        self.host_edit.setPlaceholderText(placeholder)
        self.fingerprint_edit = QLineEdit(self)
        self.fingerprint_edit.setPlaceholderText("sha256:...")

        form = QFormLayout()
        form.addRow(tr("trusted_keys.host"), self.host_edit)
        form.addRow(tr("trusted_keys.fingerprint"), self.fingerprint_edit)

        self.fetch_btn = QPushButton(tr("trusted_keys.read_from_node"), self)
        self.fetch_btn.clicked.connect(self._read_from_node)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        style_ok_cancel_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.fetch_btn)
        layout.addWidget(buttons)

    def _read_from_node(self) -> None:
        host = self.host_edit.text().strip()
        endpoint = parse_host_port(host) if host else None
        if endpoint is None or not self._binary:
            return
        fingerprint = self._fetch_fingerprint(self._binary, endpoint.host, endpoint.port)
        if fingerprint:
            self.fingerprint_edit.setText(fingerprint)
        else:
            QMessageBox.warning(self, tr("trusted_keys.add"), tr("trusted_keys.failed"))

    def _on_accept(self) -> None:
        host = self.host_edit.text().strip()
        endpoint = parse_host_port(host) if host else None
        fingerprint = parse_fingerprint(self.fingerprint_edit.text())
        if endpoint is None or fingerprint is None or not self._binary:
            QMessageBox.warning(self, tr("trusted_keys.add"), tr("trusted_keys.failed"))
            return
        if self._add_trust(self._binary, endpoint.host, fingerprint, endpoint.port):
            self.accept()
        else:
            QMessageBox.warning(self, tr("trusted_keys.add"), tr("trusted_keys.failed"))


class _PeerAddDialog(QDialog):
    """Collect a peer device ID + fingerprint (bucket prefilled from settings)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("trusted_keys.add"))
        self._binary = find_hsync_binary()

        self.cid_edit = QLineEdit(self)
        self.cid_edit.setPlaceholderText("ABCDEFGH-…")
        self.fingerprint_edit = QLineEdit(self)
        self.fingerprint_edit.setPlaceholderText("sha256:...")
        self.bucket_edit = QLineEdit(self)
        self.bucket_edit.setText(
            str(QSettings(SETTINGS_ORG, SETTINGS_APP).value("sync/bucket", "", str))
        )

        form = QFormLayout()
        form.addRow(tr("trusted_keys.device_id"), self.cid_edit)
        form.addRow(tr("trusted_keys.bucket"), self.bucket_edit)
        form.addRow(tr("trusted_keys.fingerprint"), self.fingerprint_edit)

        warning = QLabel(tr("trusted_keys.manual_warning"), self)
        warning.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        style_ok_cancel_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(warning)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        cid = self.cid_edit.text().strip()
        bucket = self.bucket_edit.text().strip()
        fingerprint = parse_fingerprint(self.fingerprint_edit.text())
        if not cid or not bucket or fingerprint is None or not self._binary:
            QMessageBox.warning(self, tr("trusted_keys.add"), tr("trusted_keys.failed"))
            return
        if add_peer_pin(self._binary, cid, bucket, fingerprint):
            self.accept()
        else:
            QMessageBox.warning(self, tr("trusted_keys.add"), tr("trusted_keys.failed"))


class TrustedKeysDialog(QDialog):
    """Manage the bootnode/server known-hosts stores and the P2P known-peers store."""

    # ``initial_tab`` values → index in ``self._tabs``.
    _TAB_INDEX = {"bootnodes": 0, "servers": 1, "peers": 2}

    def __init__(self, parent: QWidget | None = None, *, initial_tab: str = "bootnodes") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("trusted_keys.title"))
        self.resize(680, 380)
        self._binary = find_hsync_binary()

        self._tabs = QTabWidget(self)
        self._bootnode_table = QTableWidget(0, 4, self)
        self._server_table = QTableWidget(0, 4, self)
        self._peer_table = QTableWidget(0, 3, self)
        self._tabs.addTab(
            self._build_host_tab(self._bootnode_table, self._add_bootnode, self._remove_bootnode),
            tr("trusted_keys.tabs_bootnodes"),
        )
        self._tabs.addTab(
            self._build_host_tab(self._server_table, self._add_server, self._remove_server),
            tr("trusted_keys.tabs_servers"),
        )
        self._tabs.addTab(self._build_peer_tab(), tr("trusted_keys.tabs_peers"))
        self._apply_mode_tab_visibility(initial_tab)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText(tr("action.close"))
            close_btn.setIcon(icon("window-close"))
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

        self._refresh()

    # ── Construction ───────────────────────────────────────────────────────

    def _apply_mode_tab_visibility(self, initial_tab: str) -> None:
        """Show only the trust stores the active sync mode can use.

        The relay-server and device stores belong to p2p mode; the sync-server
        store belongs to Server Mode. Hiding the irrelevant ones keeps the
        dialog focused (each mode's settings panel opens its own tab).
        """
        p2p_enabled = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        )
        visible = {"bootnodes": p2p_enabled, "servers": not p2p_enabled, "peers": p2p_enabled}
        for name, index in self._TAB_INDEX.items():
            self._tabs.setTabVisible(index, visible[name])
        # Never select a hidden page: fall back to the first visible one.
        index = self._TAB_INDEX.get(initial_tab, 0)
        if not visible.get(initial_tab, True):
            index = next(self._TAB_INDEX[name] for name, shown in visible.items() if shown)
        self._tabs.setCurrentIndex(index)

    def _build_host_tab(self, table: QTableWidget, on_add, on_remove) -> QWidget:
        """Build a bootnode/server-style tab: a ``host:port`` table + buttons."""
        table.setHorizontalHeaderLabels(
            [
                tr("trusted_keys.host"),
                tr("trusted_keys.fingerprint"),
                tr("trusted_keys.source"),
                tr("trusted_keys.first_seen"),
            ]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)

        add_btn = QPushButton(tr("trusted_keys.add"), self)
        add_btn.clicked.connect(on_add)
        remove_btn = QPushButton(tr("trusted_keys.remove"), self)
        remove_btn.clicked.connect(on_remove)
        refresh_btn = QPushButton(tr("trusted_keys.refresh"), self)
        refresh_btn.clicked.connect(self._refresh)

        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addWidget(refresh_btn)
        row.addStretch()

        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.addWidget(table)
        layout.addLayout(row)
        return widget

    def _build_peer_tab(self) -> QWidget:
        table = self._peer_table
        table.setHorizontalHeaderLabels(
            [
                tr("trusted_keys.peer"),
                tr("trusted_keys.fingerprint"),
                tr("trusted_keys.first_seen"),
            ]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)

        add_btn = QPushButton(tr("trusted_keys.add"), self)
        add_btn.clicked.connect(self._add_peer)
        remove_btn = QPushButton(tr("trusted_keys.remove"), self)
        remove_btn.clicked.connect(self._remove_peer)
        refresh_btn = QPushButton(tr("trusted_keys.refresh"), self)
        refresh_btn.clicked.connect(self._refresh)

        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addWidget(refresh_btn)
        row.addStretch()

        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.addWidget(table)
        layout.addLayout(row)
        return widget

    # ── Population ─────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        self._reload_hosts(self._bootnode_table)
        self._reload_hosts(self._server_table)
        self._load_peers()

    def _reload_hosts(self, table: QTableWidget) -> None:
        """Reload the bootnode or server table from its store."""
        if self._binary is None:
            return
        lister = list_server_trust if table is self._server_table else list_bootnode_trust
        self._load_hosts(table, lister(self._binary))

    def _load_hosts(self, table: QTableWidget, entries: list[dict[str, Any]] | None) -> None:
        table.setRowCount(0)
        if not self._binary:
            self._set_empty(table, tr("trusted_keys.empty"))
            return
        if entries is None:
            self._set_empty(table, tr("trusted_keys.failed"))
            return
        for entry in entries:
            host = str(entry.get("host", ""))
            port = int(entry.get("port", 443))
            self._append_row(
                table,
                [
                    format_authority(host, port),
                    str(entry.get("fingerprint", "")),
                    _source_label(str(entry.get("source", ""))),
                    _format_local_time(str(entry.get("first_seen", ""))),
                ],
            )
            # Keep the structured (host, port) pair for a lossless remove, so an
            # IPv6 composite ("[::1]:443") is never re-parsed from its text.
            item = table.item(table.rowCount() - 1, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, (host, port))

    def _load_peers(self) -> None:
        table = self._peer_table
        table.setRowCount(0)
        if not self._binary:
            self._set_empty(table, tr("trusted_keys.empty"))
            return
        if not supports_peer_trust(self._binary):
            self._set_empty(table, tr("trusted_keys.capability_missing"))
            return
        entries = list_peer_pins(self._binary)
        if entries is None:
            self._set_empty(table, tr("trusted_keys.failed"))
            return
        for entry in entries:
            self._append_row(
                table,
                [
                    f"{entry.get('cid', '')}|{entry.get('bucket', '')}",
                    str(entry.get("fingerprint", "")),
                    _format_local_time(str(entry.get("first_seen", ""))),
                ],
            )

    @staticmethod
    def _set_empty(table: QTableWidget, message: str) -> None:
        table.setRowCount(1)
        table.setItem(0, 0, QTableWidgetItem(message))

    @staticmethod
    def _append_row(table: QTableWidget, values: list[str]) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, col, item)

    # ── Actions ────────────────────────────────────────────────────────────

    def _add_bootnode(self) -> None:
        dialog = _HostAddDialog(
            fetch_fingerprint=fetch_bootnode_fingerprint,
            add_trust=add_bootnode_trust,
            placeholder="boot.example.net",
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_hosts(self._bootnode_table)

    def _add_server(self) -> None:
        dialog = _HostAddDialog(
            fetch_fingerprint=fetch_server_fingerprint,
            add_trust=add_server_trust,
            placeholder="server.example.com:9753",
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_hosts(self._server_table)

    def _add_peer(self) -> None:
        if not self._binary or not supports_peer_trust(self._binary):
            QMessageBox.warning(
                self, tr("trusted_keys.title"), tr("trusted_keys.capability_missing")
            )
            return
        if _PeerAddDialog(self).exec() == QDialog.DialogCode.Accepted:
            self._load_peers()

    def _remove_bootnode(self) -> None:
        self._remove_host(self._bootnode_table, remove_bootnode_trust)

    def _remove_server(self) -> None:
        self._remove_host(self._server_table, remove_server_trust)

    def _remove_host(self, table: QTableWidget, remove_trust: Callable[..., bool]) -> None:
        row = table.currentRow()
        if row < 0 or self._binary is None:
            return
        item = table.item(row, 0)
        stored = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(stored, tuple) and len(stored) == 2:
            host, port = stored
            authority = format_authority(host, port)
        else:
            authority = item.text() if item else ""
            endpoint = parse_host_port(authority)
            if endpoint is None:
                return
            host, port = endpoint.host, endpoint.port
        if not self._confirm_remove(authority):
            return
        if remove_trust(self._binary, host, port):
            self._reload_hosts(table)
        else:
            QMessageBox.warning(self, tr("trusted_keys.title"), tr("trusted_keys.failed"))

    def _remove_peer(self) -> None:
        row = self._peer_table.currentRow()
        if row < 0 or self._binary is None:
            return
        item = self._peer_table.item(row, 0)
        peer = item.text() if item else ""
        cid, _, bucket = peer.partition("|")
        if not cid or not bucket or not self._confirm_remove(peer):
            return
        if remove_peer_pin(self._binary, cid, bucket):
            self._load_peers()
        else:
            QMessageBox.warning(self, tr("trusted_keys.title"), tr("trusted_keys.failed"))

    def _confirm_remove(self, peer: str) -> bool:
        answer = QMessageBox.question(
            self,
            tr("trusted_keys.remove"),
            tr("trusted_keys.remove_confirm").format(peer=peer),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
