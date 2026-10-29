# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""TrustMixin: pin/trust dialogs and trust command handlers."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit

from hsync_common.constants import SERVER_DEFAULT_PORT
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
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.engine import (
    AsyncProbe,
    HsyncEngine,
    ProbeOutcome,
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
    COLOR_WAITING,
    apply_theme,
)
from hsync_desktop.ui.loader import load_ui_widget


@dataclass(frozen=True, slots=True)
class _TrustCheck:
    """One unknown ``host:port`` the pre-flight must authenticate before a run.

    ``fetch_fn`` is the blocking fingerprint probe (a client CLI call): it only
    ever runs on the ``AsyncProbe`` thread; ``add_fn`` writes the confirmed pin.
    ``kind`` is the host class (``"bootnode"`` or ``"server"``): only the sync
    server is mandatory for a run, so an unreachable discovery server degrades
    the run instead of cancelling it.
    """

    host: str
    port: int
    add_fn: Callable[..., bool]
    fetch_fn: Callable[..., str | None]
    label: str
    binary: str
    kind: str


class TrustMixin:
    def _trust_identity_key(self, scope: str, cid: str, address: str) -> tuple[str, str]:
        """Dedupe key for a trust prompt: the scope plus the device/endpoint id."""
        return (scope, cid or address or "")

    def _should_prompt_trust(self, scope: str, cid: str, address: str, fingerprint: str) -> bool:
        """Whether a trust refusal should open a dialog (dedupe per identity).

        Returns False when the same fingerprint was already prompted for this
        identity, so the client's continuous retries do not reopen a dialog the
        user already dismissed; records the fingerprint otherwise.
        """
        key = self._trust_identity_key(scope, cid, address)
        if self._trust_prompted.get(key) == fingerprint:
            return False
        self._trust_prompted[key] = fingerprint
        return True

    def _trust_identity(self, scope: str, cid: str, address: str) -> str:
        """Human-readable identity for a trust prompt (device ID or host:port)."""
        if scope == "master":
            return cid
        endpoint = parse_host_port(address) if address else None
        if endpoint is None:
            return address or "?"
        return f"{endpoint.authority}:{endpoint.port}" if endpoint.port else endpoint.authority

    def _host_port_from_address(self, address: str) -> tuple[str, int | None]:
        """Split a bootnode/server ``peer_address`` into (host, port) for the CLI."""
        endpoint = parse_host_port(address) if address else None
        if endpoint is None:
            return address or "", None
        return endpoint.host, endpoint.port

    @staticmethod
    def _host_trust_actions(
        scope: str,
    ) -> tuple[Callable[..., bool], Callable[..., bool], str] | None:
        """(add, remove, label) for a host:port trust scope (bootnode/server).

        Resolved at call time (not captured at import) so tests can monkeypatch
        the engine helpers; ``master`` pins a P2P peer and is handled separately.
        """
        if scope == "bootnode":
            return add_bootnode_trust, remove_bootnode_trust, "Discovery server"
        if scope == "server":
            return add_server_trust, remove_server_trust, "Server"
        return None

    def _maybe_offer_restart(self) -> None:
        """Offer to restart a stopped sync after a bootnode pin change."""
        if self._engine.is_running or not self._local_path:
            return
        answer = QMessageBox.question(
            self,
            tr("dialogs.restart_title"),
            tr("dialogs.restart_body"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._on_start()

    def _accept_peer_pin(self, cid: str, fingerprint: str) -> None:
        """Pin a P2P master fingerprint through the known-peers store."""
        binary = find_hsync_binary()
        if not binary:
            return
        if not supports_peer_trust(binary):
            QMessageBox.warning(
                self, tr("dialogs.pairing_needed_title"), tr("dialogs.trust_failed")
            )
            return
        bucket = str(QSettings(SETTINGS_ORG, SETTINGS_APP).value("sync/bucket", "", str))
        if add_peer_pin(binary, cid, bucket, fingerprint):
            self._append_desktop_log("INFO", f"Peer {cid} pinned.")
        else:
            QMessageBox.warning(
                self, tr("dialogs.pairing_needed_title"), tr("dialogs.trust_failed")
            )

    def _trust_prompt(
        self,
        title_key: str,
        body_key: str,
        peer: str,
        fingerprint: str,
        buttons: list[tuple[str, QMessageBox.ButtonRole]],
    ) -> QMessageBox.ButtonRole | None:
        """Show a modal trust prompt; return the role of the clicked button.

        Both trust dialogs (first-seen pairing and fingerprint change) share this
        construction: warning icon, translated title/body with the peer and the
        fingerprint, and the reject button as the default, so dismissing the
        dialog (Esc / window close, which yields ``None``) never pins or forgets
        anything.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr(title_key))
        box.setText(tr(body_key).format(peer=peer, fingerprint=fingerprint))
        added: list[tuple[QPushButton, QMessageBox.ButtonRole]] = []
        for label_key, role in buttons:
            added.append((box.addButton(tr(label_key), role), role))
        for button, role in added:
            if role == QMessageBox.ButtonRole.RejectRole:
                box.setDefaultButton(button)
        box.exec()
        clicked = box.clickedButton()
        for button, role in added:
            if clicked is button:
                return role
        return None

    @Slot(str, str, str, str)
    def _on_pairing_needed(self, scope: str, cid: str, address: str, fingerprint: str) -> None:
        """Prompt for a first-seen fingerprint that strict pairing refuses."""
        if not self._should_prompt_trust(scope, cid, address, fingerprint):
            return
        peer = self._trust_identity(scope, cid, address)
        choice = self._trust_prompt(
            "dialogs.pairing_needed_title",
            "dialogs.pairing_needed_body",
            peer,
            fingerprint,
            [
                ("dialogs.trust_accept", QMessageBox.ButtonRole.AcceptRole),
                ("dialogs.trust_ignore", QMessageBox.ButtonRole.RejectRole),
            ],
        )
        if choice is not QMessageBox.ButtonRole.AcceptRole:
            self._append_desktop_log("WARNING", "Peer not trusted.")
            return
        if scope == "master":
            self._accept_peer_pin(cid, fingerprint)
            return
        action = self._host_trust_actions(scope)
        if action is None:
            return
        add_fn, _remove_fn, label = action
        host, port = self._host_port_from_address(address)
        binary = find_hsync_binary()
        if not binary or not add_fn(binary, host, fingerprint, port):
            QMessageBox.warning(
                self, tr("dialogs.pairing_needed_title"), tr("dialogs.trust_failed")
            )
            return
        self._append_desktop_log("INFO", f"{label} {peer} trusted.")
        self._maybe_offer_restart()

    @Slot(str, str, str, str)
    def _on_fingerprint_changed(self, scope: str, cid: str, address: str, fingerprint: str) -> None:
        """Prompt when a pinned fingerprint no longer matches (possible MITM)."""
        if not self._should_prompt_trust(scope, cid, address, fingerprint):
            return
        peer = self._trust_identity(scope, cid, address)
        choice = self._trust_prompt(
            "dialogs.peer_changed_title",
            "dialogs.peer_changed_body",
            peer,
            fingerprint,
            [
                ("dialogs.trust_accept", QMessageBox.ButtonRole.AcceptRole),
                ("dialogs.trust_forget", QMessageBox.ButtonRole.DestructiveRole),
                ("dialogs.trust_ignore", QMessageBox.ButtonRole.RejectRole),
            ],
        )
        if choice in (None, QMessageBox.ButtonRole.RejectRole):
            # Ignored or dismissed (Esc / window closed): never touch the pin.
            return
        binary = find_hsync_binary()
        if not binary:
            return
        if scope == "master":
            bucket = str(QSettings(SETTINGS_ORG, SETTINGS_APP).value("sync/bucket", "", str))
            if choice is QMessageBox.ButtonRole.AcceptRole:
                add_peer_pin(binary, cid, bucket, fingerprint)
            else:
                remove_peer_pin(binary, cid, bucket)
            return
        action = self._host_trust_actions(scope)
        if action is None:
            return
        add_fn, remove_fn, _label = action
        host, port = self._host_port_from_address(address)
        if choice is QMessageBox.ButtonRole.AcceptRole:
            ok = add_fn(binary, host, fingerprint, port)
        else:
            ok = remove_fn(binary, host, port)
        if not ok:
            QMessageBox.warning(self, tr("dialogs.peer_changed_title"), tr("dialogs.trust_failed"))
            return
        self._maybe_offer_restart()

    @Slot(str)
    def _on_auth_error(self, _error_msg: str) -> None:
        """Re-prompt for credentials after an authentication failure.

        The client reports a missing or incorrect key through the ``auth_error``
        and ``auth_required`` events. The GUI always re-prompts (it never only
        announces that the password is wrong) so the operator can enter a correct
        value and retry; a retry that fails again reopens this prompt. Events
        arriving while a prompt is already open — the modal ``exec()`` runs a
        nested event loop — are ignored.
        """
        if self._auth_prompt_active:
            return
        self._auth_prompt_active = True
        try:
            # An authentication failure aborts a scoped Send/Receive: close its
            # state silently before the re-prompt so the retry does not fight it.
            if self._selection_sync_active:
                self._finish_selection_sync("cancelled")
            self._engine.stop_and_wait()

            s = QSettings(SETTINGS_ORG, SETTINGS_APP)
            p2p_enabled = bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool))

            if p2p_enabled:
                # p2p mode: prompt for the shared password (pre-filled with the
                # current one so a mistyped value is easy to correct).
                self._append_desktop_log("WARNING", tr("p2pauth.error_message"))
                p2p_dlg = P2PKeyDialog(self)
                accepted = p2p_dlg.exec() == P2PKeyDialog.DialogCode.Accepted
            else:
                # Server mode: prompt for the API key.
                self._append_desktop_log("WARNING", tr("apikey.error_message"))
                api_dlg = ApiKeyDialog(self)
                accepted = api_dlg.exec() == ApiKeyDialog.DialogCode.Accepted

            if accepted:
                self._append_desktop_log("INFO", f"--- {tr('p2pauth.retrying')} ---")
                self._retry_after_auth_fix()
            else:
                self._reset_ui_stopped()
        finally:
            self._auth_prompt_active = False

    def _retry_after_auth_fix(self) -> None:
        """Restart sync in dry-run mode after credentials have been updated."""
        # Immediately update status bar to show "connecting" state
        self._on_status("connecting")
        # Show info banner for extra visibility
        self._show_info_banner(f"🔄 {tr('banner.reconnecting')}", kind="progress")
        local_path = self._local_path
        if local_path:
            args = build_hsync_args(local_path, force_dry_run=True)
            self._log_view.clear()
            self._file_panel.load_local_files(local_path)
            self._awaiting_preview_for_sync = True
            self._is_dry_run_preview = True
            # The credential prompt just put the user in front of the window: the
            # plan of this dry-run is theirs to confirm, even when the run itself
            # started automatically.
            self._dry_run_unattended = False
            self._pending_sync_path = local_path
            if self._start_engine(args):
                self._btn_start.setEnabled(False)
                self._btn_stop.setEnabled(True)
                if self._tray:
                    self._tray.set_running(True)
                self._apply_button_styles()
                self._update_menu_state()
                # The restarted dry-run is preparing a plan again: without this
                # the wait would have no progress state at all.
                self._enter_preparing_plan_ui()
                return
        self._hide_info_banner()
        self._reset_ui_stopped()

    # ── Trust pre-flight (ADR-0035 / ADR-0036) ────────────────────────────

    def _init_trust_preflight(self) -> None:
        """Create the async probe that authenticates unknown hosts before a run."""
        self._trust_probe = AsyncProbe(self)
        self._trust_probe.done.connect(self._on_trust_probe_done)
        self._trust_checks: list[_TrustCheck] = []
        self._trust_check_active: _TrustCheck | None = None
        self._trust_on_ready: Callable[[], None] | None = None

    def _ensure_trust(self, on_ready: Callable[[], None]) -> None:
        """Authenticate the configured hosts before a run starts.

        The store lookups are local and run inline; an unknown host needs a
        network round-trip, so the fingerprint probe runs on ``AsyncProbe`` and
        ``on_ready`` is called only once every host is trusted. A host the
        operator refuses (or that never answers) abandons the run: ``on_ready``
        is never called, mirroring a ``False`` pre-flight result.
        """
        if self._trust_on_ready is not None:
            return  # a pre-flight is already running
        self._trust_on_ready = on_ready
        self._trust_checks = self._pending_trust_checks()
        self._run_next_trust_check()

    def _pending_trust_checks(self) -> list[_TrustCheck]:
        """The hosts that still need an operator decision, bootnode first."""
        binary = find_hsync_binary()
        if not binary:
            return []  # the engine reports the missing binary
        checks: list[_TrustCheck] = []
        for check in (self._bootnode_trust_check(binary), self._server_trust_check(binary)):
            if check is not None:
                checks.append(check)
        return checks

    def _bootnode_trust_check(self, binary: str) -> _TrustCheck | None:
        """Bootnode pre-flight (ADR-0035), or ``None`` when nothing to ask."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if not bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)):
            return None
        host = str(s.value("p2p/discovery_server_endpoints", "", str)).strip()
        if not host:
            return None
        if str(s.value("p2p/discovery_server_trust", DEFAULT_P2P_BOOTNODE_TRUST, str)) != "ask":
            return None
        # The bootnode setting may carry a port ("[IPv6]:port"): normalize it to
        # its unbracketed host and use the real port for the trust store/fetch.
        try:
            endpoint = parse_host_port(host)
        except ValueError:
            return None
        return self._trust_check(
            binary,
            endpoint.host,
            endpoint.port or 443,
            list_fn=list_bootnode_trust,
            fetch_fn=fetch_bootnode_fingerprint,
            add_fn=add_bootnode_trust,
            label="Bootnode",
            kind="bootnode",
        )

    def _server_trust_check(self, binary: str) -> _TrustCheck | None:
        """Sync-server pre-flight (ADR-0036), or ``None`` in p2p mode."""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)):
            return None  # server trust applies to server mode only
        if str(s.value("connection/server_trust", DEFAULT_SERVER_TRUST, str)) != "ask":
            return None
        url = str(s.value("connection/server_url", "", str)).strip()
        endpoint = urlsplit(url) if url else None
        host = (endpoint.hostname or "") if endpoint else ""
        if not host:
            return None
        port = (endpoint.port if endpoint else None) or (
            443 if endpoint and endpoint.scheme == "https" else SERVER_DEFAULT_PORT
        )
        return self._trust_check(
            binary,
            host,
            port,
            list_fn=list_server_trust,
            fetch_fn=fetch_server_fingerprint,
            add_fn=add_server_trust,
            label="Server",
            kind="server",
        )

    @staticmethod
    def _trust_check(
        binary: str,
        host: str,
        port: int,
        *,
        list_fn: Callable[..., list[dict] | None],
        fetch_fn: Callable[..., str | None],
        add_fn: Callable[..., bool],
        label: str,
        kind: str,
    ) -> _TrustCheck | None:
        """Build the check for an unpinned ``host:port`` (``None`` when pinned).

        A store hit needs no network call, so the run proceeds without a prompt.
        """
        entries = list_fn(binary)
        if entries is not None and any(
            entry.get("host") == host and entry.get("port") == port for entry in entries
        ):
            return None
        return _TrustCheck(host, port, add_fn, fetch_fn, label, binary, kind)

    def _run_next_trust_check(self) -> None:
        """Probe the next unknown host, or hand control back to the caller."""
        if not self._trust_checks:
            on_ready = self._finish_trust_preflight()
            if on_ready is not None:
                on_ready()
            return
        check = self._trust_checks.pop(0)
        self._trust_check_active = check
        self._show_info_banner(tr("common.checking"), auto_hide_ms=0, kind="progress")
        self._trust_probe.start(
            lambda: ProbeOutcome(
                bool(fingerprint := check.fetch_fn(check.binary, check.host, check.port)),
                fingerprint=fingerprint or "",
            )
        )

    def _finish_trust_preflight(self) -> Callable[[], None] | None:
        """Clear the pre-flight state and return the continuation (once)."""
        on_ready = self._trust_on_ready
        self._trust_on_ready = None
        self._trust_checks = []
        self._trust_check_active = None
        self._hide_info_banner()
        return on_ready

    @Slot(object)
    def _on_trust_probe_done(self, outcome: object) -> None:
        """Confirm an unknown host's fingerprint, then continue or abandon."""
        check = self._trust_check_active
        if check is None or self._trust_on_ready is None:
            return  # cancelled: the run was abandoned or the window closed
        self._trust_check_active = None
        self._hide_info_banner()
        fingerprint = outcome.fingerprint if isinstance(outcome, ProbeOutcome) else ""
        if not fingerprint:
            if check.kind == "bootnode":
                # The discovery server is an optional cross-network source: an
                # unreachable node degrades the run to local-network discovery
                # instead of cancelling it. The client retries the node on its
                # own and, once it answers, reports the unpinned identity through
                # ``pairing_needed`` (scope ``bootnode``), which re-prompts here.
                self._append_desktop_log(
                    "WARNING",
                    f"Discovery server {check.host}:{check.port} is not reachable: "
                    "devices are discovered on the local network only. Pin its "
                    "fingerprint (Manage trusted servers & devices) to use it.",
                )
                self._run_next_trust_check()
                return
            self._finish_trust_preflight()
            QMessageBox.warning(
                self,
                tr("dialogs.bootnode_trust_title"),
                tr("dialogs.bootnode_unreachable").format(host=check.host),
            )
            return
        answer = QMessageBox.question(
            self,
            tr("dialogs.bootnode_trust_title"),
            tr("dialogs.bootnode_trust_body").format(host=check.host, fingerprint=fingerprint),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._append_desktop_log(
                "WARNING", f"{check.label} certificate not accepted; start cancelled."
            )
            self._finish_trust_preflight()
            return
        if not check.add_fn(check.binary, check.host, fingerprint, check.port):
            self._finish_trust_preflight()
            QMessageBox.warning(
                self, tr("dialogs.bootnode_trust_title"), tr("dialogs.trust_failed")
            )
            return
        self._run_next_trust_check()
