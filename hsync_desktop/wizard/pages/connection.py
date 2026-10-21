# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Step 3 — connection and behaviour (fields depend on the mode)."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop import autostart
from hsync_desktop.config import DEFAULT_HTTP_TIMEOUT
from hsync_desktop.engine import (
    build_probe_ssl_context,
    fetch_bootnode_fingerprint,
    find_hsync_binary,
    normalize_bootnode_endpoint,
    normalize_server_endpoint,
    probe_server_bucket,
    probe_server_health,
)
from hsync_desktop.i18n import tr
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.widgets.text import escape_mnemonics
from hsync_desktop.widgets.toggle_switch import ToggleSwitch
from hsync_desktop.wizard.defaults import generate_group_name, generate_password
from hsync_desktop.wizard.model import WizardDraft, WizardMode, profile_for
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.probes import AsyncProbe, ProbeOutcome
from hsync_desktop.wizard.widgets import (
    InlineError,
    SecretField,
    ToggleRow,
    char_class_validator,
    set_field_error,
)

__all__ = ["ConnectionPage"]

_DIRECTIONS = ("bidirectional", "upload-only", "download-only")

_STATUS_OBJECT_NAMES = {"working": "mutedHint", "ok": "statusOk", "error": "statusError"}

# Shared form-label width: keeps the share-name field aligned with the
# mode-specific fields; longer translations wrap instead of squeezing the field.
_MAX_LABEL_WIDTH = 200

# Tooltips explain the jargon without changing the visible labels.
_TOOLTIP_KEYS = {
    "server_url": "wizard.tip.server_url",
    "api_key": "wizard.tip.api_key",
    "bucket": "wizard.tip.share_name",
    "p2p_group": "wizard.tip.group",
    "p2p_key": "wizard.tip.password",
    "discovery_server": "wizard.tip.discovery_server",
    "receive_only": "wizard.tip.receive_only",
    "cert": "wizard.tip.cert",
}

_AUTOMATION_TIP_KEYS = {
    "continuous": "wizard.tip.continuous",
    "auto_sync": "wizard.tip.auto_sync",
    "start_at_login": "wizard.tip.start_at_login",
}


class ConnectionPage(WizardPage):
    def __init__(self) -> None:
        super().__init__()
        self._mode: WizardMode | None = None
        self._server_fingerprint = ""
        self._discovery_server_fingerprint = ""
        self._server_verified = False
        self._server_verified_at = ""
        self._discovery_server_verified = False
        self._discovery_server_verified_at = ""
        self._share_missing = False
        self._probing = False
        self._active_target = ""
        self._probe = AsyncProbe(self)
        self._probe.done.connect(self._on_probe_done)

        layout = QVBoxLayout(self)
        self._rows: dict[str, tuple[QWidget, QWidget, InlineError, QLabel]] = {}

        # Shared across every mode: the share name identifies the dataset.
        common_form = QFormLayout()
        layout.addLayout(common_form)
        self.bucket = QLineEdit()
        self.bucket.setValidator(char_class_validator("A-Za-z0-9_-"))
        self.bucket.setPlaceholderText("my-share")
        self.bucket.textChanged.connect(self._on_edit)
        self.bucket.textChanged.connect(self._on_server_edited)
        common_form.addRow(*self._row("bucket", "wizard.connection.share", self.bucket))

        # Mode-specific sections: one clean form per topology.
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._server_page = QWidget()
        server_form = QFormLayout(self._server_page)
        server_form.setContentsMargins(0, 0, 0, 0)

        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("https://hsync.example.com:9753")
        self.server_url.textChanged.connect(self._on_edit)
        self.server_url.textChanged.connect(self._on_server_edited)
        server_form.addRow(
            *self._row("server_url", "wizard.connection.server_url", self.server_url)
        )

        self.api_key = SecretField()
        self.api_key.edit.setPlaceholderText("access-key")
        self.api_key.edit.textChanged.connect(self._on_edit)
        self.api_key.edit.textChanged.connect(self._on_server_edited)
        server_form.addRow(*self._row("api_key", "wizard.connection.api_key", self.api_key))

        self.test_server = QPushButton()
        self.test_server.clicked.connect(self._on_test_server)
        self.server_status = self._make_status()
        server_form.addRow(*self._action_row("test_server", self.test_server))
        # Its own row: a long error can never overlap the button.
        server_form.addRow("", self.server_status)

        self.cert_switch = ToggleSwitch()
        self.cert_switch.toggled.connect(self._on_edit)
        server_form.addRow(
            *self._row("cert", "wizard.connection.server_cert_check", self.cert_switch)
        )

        # Team direction (server mode only, hidden for backup).
        self.direction = QComboBox()
        for value in _DIRECTIONS:
            self.direction.addItem("", value)
        self.direction.currentIndexChanged.connect(self._on_edit)
        server_form.addRow(*self._row("direction", "wizard.connection.direction", self.direction))

        self._network_page = QWidget()
        network_form = QFormLayout(self._network_page)
        network_form.setContentsMargins(0, 0, 0, 0)

        self.group = QLineEdit()
        self.group.setValidator(char_class_validator("A-Za-z0-9._-"))
        self.group.setPlaceholderText("my-devices")
        self.group.textChanged.connect(self._on_edit)
        network_form.addRow(*self._row("p2p_group", "wizard.connection.group", self.group))

        self.password = SecretField(allow_regenerate=True)
        self.password.edit.textChanged.connect(self._on_edit)
        if self.password.regenerate is not None:
            self.password.regenerate.clicked.connect(self._on_regenerate)
        network_form.addRow(*self._row("p2p_key", "wizard.connection.password", self.password))

        self.discovery_server = QLineEdit()
        self.discovery_server.setPlaceholderText("boot.example.net")
        self.discovery_server.textChanged.connect(self._on_edit)
        self.discovery_server.textChanged.connect(self._on_discovery_server_edited)
        network_form.addRow(
            *self._row(
                "discovery_server", "wizard.connection.discovery_server", self.discovery_server
            )
        )

        self.test_discovery_server = QPushButton()
        self.test_discovery_server.clicked.connect(self._on_test_discovery_server)
        self.discovery_server_status = self._make_status()
        network_form.addRow(*self._action_row("test_discovery_server", self.test_discovery_server))
        # Its own row: a long error can never overlap the button.
        network_form.addRow("", self.discovery_server_status)

        # Discovery-server trust buttons, shown under the result after a good check.
        self.discovery_server_trust_box = QWidget()
        trust_layout = QHBoxLayout(self.discovery_server_trust_box)
        trust_layout.setContentsMargins(0, 0, 0, 0)
        self.trust_save = QPushButton()
        self.trust_save.setCheckable(True)
        self.trust_ask = QPushButton()
        self.trust_ask.setCheckable(True)
        self.trust_save.clicked.connect(lambda: self._set_discovery_server_pin(True))
        self.trust_ask.clicked.connect(lambda: self._set_discovery_server_pin(False))
        trust_layout.addWidget(self.trust_save)
        trust_layout.addWidget(self.trust_ask)
        trust_layout.addStretch(1)
        self.discovery_server_trust_box.setVisible(False)
        network_form.addRow("", self.discovery_server_trust_box)

        self.receive_only = ToggleSwitch()
        self.receive_only.toggled.connect(self._on_edit)
        network_form.addRow(
            *self._row("receive_only", "wizard.connection.receive_only", self.receive_only)
        )

        self._stack.addWidget(self._server_page)
        self._stack.addWidget(self._network_page)

        # Optional automation block (all modes).
        self._automation = QGroupBox()
        automation_layout = QVBoxLayout(self._automation)
        self._automation_rows: list[ToggleRow] = []
        self.continuous: ToggleSwitch
        self.auto_sync: ToggleSwitch
        self.start_at_login: ToggleSwitch
        for attr, key in (
            ("continuous", "wizard.automation.continuous"),
            ("auto_sync", "wizard.automation.auto_sync"),
            ("start_at_login", "wizard.automation.start_at_login"),
        ):
            row = ToggleRow(key)
            switch = row.switch
            switch.toggled.connect(self._on_edit)
            setattr(self, attr, switch)
            self._automation_rows.append(row)
            automation_layout.addWidget(row)
        if not autostart.is_supported():
            self.start_at_login.setEnabled(False)
        layout.addWidget(self._automation)

        self.hints = muted_label()
        layout.addWidget(self.hints)
        layout.addStretch(1)
        self.apply_translations()

    # ── construction helpers ─────────────────────────────────────────────
    def _row(self, name: str, label_key: str, field: QWidget) -> tuple[QLabel, QWidget]:
        label = QLabel(tr(label_key))
        label.setProperty("wizardLabelKey", label_key)
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(field)
        error = InlineError()
        box.addWidget(error)
        self._rows[name] = (container, field, error, label)
        return label, container

    def _action_row(self, name: str, button: QPushButton) -> tuple[QLabel, QWidget]:
        """A form row whose field is a left-aligned action button."""
        label = QLabel("")
        container = QWidget()
        box = QHBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(button)
        box.addStretch(1)
        error = InlineError()
        box.addWidget(error)
        self._rows[name] = (container, button, error, label)
        return label, container

    @staticmethod
    def _make_status() -> QLabel:
        label = QLabel()
        label.setWordWrap(True)
        label.setObjectName("mutedHint")
        label.setVisible(False)
        return label

    @staticmethod
    def _set_status(label: QLabel, kind: str, text: str) -> None:
        label.setObjectName(_STATUS_OBJECT_NAMES[kind])
        label.setText(text)
        label.setVisible(bool(text))
        label.setAccessibleName(text)
        label.style().unpolish(label)
        label.style().polish(label)

    def _clear_status(self, label: QLabel) -> None:
        self._set_status(label, "working", "")

    def _set_visible(self, name: str, visible: bool) -> None:
        container, _field, _error, label = self._rows[name]
        container.setVisible(visible)
        label.setVisible(visible)

    # ── behaviour ────────────────────────────────────────────────────────
    def _on_edit(self, *_args) -> None:
        self._share_missing = False
        self._update_test_enabled()
        self.changed.emit()

    def _on_server_edited(self, *_args) -> None:
        """A server-section edit invalidates its result and captured fingerprint."""
        self._server_fingerprint = ""
        self._server_verified = False
        self._server_verified_at = ""
        self._clear_status(self.server_status)

    def _on_discovery_server_edited(self, *_args) -> None:
        """A discovery-server edit invalidates its result, fingerprint and trust choice."""
        self._discovery_server_fingerprint = ""
        self._discovery_server_verified = False
        self._discovery_server_verified_at = ""
        self.discovery_server_trust_box.setVisible(False)
        self.trust_save.setChecked(False)
        self.trust_ask.setChecked(False)
        self._clear_status(self.discovery_server_status)

    def _on_regenerate(self) -> None:
        self.password.setText(generate_password())

    def _update_test_enabled(self) -> None:
        """Test buttons stay disabled until their required inputs are present."""
        server_ready = bool(self.server_url.text().strip() and self.api_key.text().strip())
        self.test_server.setEnabled(not self._probing and server_ready)
        self.test_discovery_server.setEnabled(
            not self._probing and bool(self.discovery_server.text().strip())
        )

    def _set_discovery_server_pin(self, pinned: bool) -> None:
        self.trust_save.setChecked(pinned)
        self.trust_ask.setChecked(not pinned)
        self.changed.emit()

    def set_mode(self, mode: WizardMode | None) -> None:
        self._mode = mode
        profile = profile_for(mode) if mode else None
        server = profile is not None and not profile.p2p_enabled
        p2p = profile is not None and profile.p2p_enabled
        # One clean form per topology instead of interleaved show/hide rows.
        current = self._server_page if (profile is None or server) else self._network_page
        self._stack.setCurrentWidget(current)
        self._set_visible("direction", mode == WizardMode.TEAM_SHARE)
        for name in ("discovery_server", "test_discovery_server"):
            self._set_visible(name, bool(profile and profile.requires_discovery_server))
        self._set_visible("receive_only", p2p)
        self.discovery_server_trust_box.setVisible(False)
        self._clear_status(self.server_status)
        self._clear_status(self.discovery_server_status)
        self._update_test_enabled()

    def _current_direction(self) -> str:
        if self._mode == WizardMode.BACKUP:
            return "upload-only"
        if self._mode == WizardMode.TEAM_SHARE:
            return str(self.direction.currentData())
        if self.receive_only.isChecked():
            return "download-only"
        return "bidirectional"

    def _timeout(self) -> float:
        return float(max(5, DEFAULT_HTTP_TIMEOUT))

    def _on_test_server(self) -> None:
        raw = self.server_url.text().strip()
        try:
            base = normalize_server_endpoint(raw)
            if base is None:
                raise ValueError
        except ValueError:
            set_field_error(
                self.server_url, self._rows["server_url"][2], tr("wizard.error.server_invalid")
            )
            return
        set_field_error(self.server_url, self._rows["server_url"][2], "")
        bucket = self.bucket.text().strip()
        api_key = self.api_key.text().strip()
        check_bucket = bool(bucket and api_key)
        ssl_context = build_probe_ssl_context(
            insecure=False,
            trust_policy="ask" if self.cert_switch.isChecked() else "chain",
        )
        timeout = self._timeout()
        mode = self._mode
        set_field_error(self.bucket, self._rows["bucket"][2], "")
        self._share_missing = False
        self._server_verified = False
        self._server_verified_at = ""
        self._active_target = "server"
        self._set_status(self.server_status, "working", tr("wizard.connection.testing"))
        self._probing = True
        self._update_test_enabled()

        def job() -> ProbeOutcome:
            health = probe_server_health(base, ssl_context=ssl_context, timeout=timeout)
            if not health.ok:
                return _health_failure(health)
            if not check_bucket:
                return ProbeOutcome(True, health.status)
            result = probe_server_bucket(
                base, bucket, api_key, ssl_context=ssl_context, timeout=timeout
            )
            if result.ok:
                return ProbeOutcome(True, result.status)
            if result.status == 404:
                return ProbeOutcome(mode != WizardMode.TEAM_SHARE, 404, reason="share_missing")
            if result.status == 400:
                return ProbeOutcome(False, 400, reason="bad_share")
            if result.status in (401, 403):
                return ProbeOutcome(False, result.status, reason="unauthorized")
            if result.status is not None and result.status >= 500:
                return ProbeOutcome(False, result.status, reason="server_error")
            return ProbeOutcome(False, result.status, reason="unreachable")

        self._probe.start(job)

    def _on_test_discovery_server(self) -> None:
        raw = self.discovery_server.text().strip()
        try:
            normalized = normalize_bootnode_endpoint(raw)
            if normalized is None:
                raise ValueError
        except ValueError:
            set_field_error(
                self.discovery_server,
                self._rows["discovery_server"][2],
                tr("wizard.error.discovery_server_invalid"),
            )
            return
        set_field_error(self.discovery_server, self._rows["discovery_server"][2], "")
        self._discovery_server_fingerprint = ""
        self._discovery_server_verified = False
        self._discovery_server_verified_at = ""
        self.discovery_server_trust_box.setVisible(False)
        self.trust_save.setChecked(False)
        self.trust_ask.setChecked(False)
        binary = find_hsync_binary()
        if not binary:
            self._set_status(
                self.discovery_server_status, "error", tr("wizard.error.pin_no_binary")
            )
            return
        self._active_target = "discovery_server"
        self._set_status(self.discovery_server_status, "working", tr("wizard.connection.testing"))
        self._probing = True
        self._update_test_enabled()
        from hsync_common.endpoint import parse_host_port

        endpoint = parse_host_port(raw)

        def job() -> ProbeOutcome:
            fingerprint = fetch_bootnode_fingerprint(binary, endpoint.host, endpoint.port)
            return ProbeOutcome(
                bool(fingerprint),
                fingerprint=fingerprint or "",
                reason="" if fingerprint else "unreachable",
            )

        self._probe.start(job)

    def _on_probe_done(self, outcome: object) -> None:
        self._probing = False
        self._update_test_enabled()
        if not isinstance(outcome, ProbeOutcome):
            return
        target = self._active_target
        # Ignore a result whose topology no longer matches (mode changed).
        if target == "server":
            if self._mode not in (WizardMode.BACKUP, WizardMode.TEAM_SHARE):
                return
        elif target == "discovery_server":
            if self._mode != WizardMode.REMOTE_SYNC:
                return
        else:
            return
        if target == "discovery_server":
            if outcome.fingerprint:
                self._discovery_server_fingerprint = outcome.fingerprint
                self._discovery_server_verified = True
                self._discovery_server_verified_at = datetime.now(UTC).isoformat()
                self._set_status(
                    self.discovery_server_status,
                    "ok",
                    tr("wizard.connection.test_discovery_server_ok").format(
                        fingerprint=outcome.fingerprint
                    ),
                )
                self.discovery_server_trust_box.setVisible(True)
                self._set_discovery_server_pin(True)
            else:
                self._set_status(
                    self.discovery_server_status,
                    "error",
                    tr("wizard.connection.discovery_server_unreachable"),
                )
            self.changed.emit()
            return
        if outcome.ok:
            self._server_verified = True
            self._server_verified_at = datetime.now(UTC).isoformat()
            self._set_status(self.server_status, "ok", tr("settings.test_connection_success"))
            self._share_missing = False
            self.changed.emit()
            return
        self._share_missing = outcome.reason == "share_missing"
        self._set_status(self.server_status, "error", _probe_message(outcome.reason))
        if self._share_missing:
            set_field_error(self.bucket, self._rows["bucket"][2], tr("wizard.probe.404_team"))
        self.changed.emit()

    # ── page contract ────────────────────────────────────────────────────
    def apply_translations(self) -> None:
        for _container, field, _error, label in self._rows.values():
            key = label.property("wizardLabelKey")
            if key:
                text = tr(str(key))
                label.setText(text)
                if isinstance(field, ToggleSwitch):
                    field.setAccessibleName(text)
        self.test_server.setText(tr("settings.test_connection"))
        self.test_discovery_server.setText(tr("settings.test_connection"))
        self.trust_save.setText(tr("wizard.connection.trust_save"))
        self.trust_ask.setText(tr("wizard.connection.trust_ask"))
        self.direction.setItemText(0, tr("settings.sync_direction.bidirectional"))
        self.direction.setItemText(1, tr("settings.sync_direction.upload_only"))
        self.direction.setItemText(2, tr("settings.sync_direction.download_only"))
        self._automation.setTitle(escape_mnemonics(tr("wizard.automation.title")))
        for row in self._automation_rows:
            row.apply_translations()
        self.password.apply_translations()
        self.hints.setText(self._hint())
        self._align_labels()
        for name, key in _TOOLTIP_KEYS.items():
            field = self._rows[name][1]
            target = field.edit if isinstance(field, SecretField) else field
            target.setToolTip(tr(key))
        for attr, key in _AUTOMATION_TIP_KEYS.items():
            getattr(self, attr).setToolTip(tr(key))

    def _align_labels(self) -> None:
        """Give every form label a common width so all fields share a column.

        The share-name field lives in its own common form above the
        mode-specific forms; without this its column (and therefore its width)
        would differ from the other fields. Long translations wrap instead of
        squeezing the fields.
        """
        labels = [label for (_container, _field, _error, label) in self._rows.values()]
        if not labels:
            return
        natural = max(label.fontMetrics().horizontalAdvance(label.text()) for label in labels)
        width = min(natural + 6, _MAX_LABEL_WIDTH)
        for label in labels:
            label.setWordWrap(True)
            label.setFixedWidth(width)

    def _hint(self) -> str:
        if self._mode == WizardMode.BACKUP:
            return tr("wizard.connection.backup_share_hint")
        if self._mode in (WizardMode.LAN_SYNC, WizardMode.REMOTE_SYNC):
            return tr("wizard.connection.lan_no_test")
        return ""

    def load(self, draft: WizardDraft) -> None:
        self.server_url.setText(draft.server_url)
        self.api_key.setText(draft.api_key)
        self.bucket.setText(draft.bucket)
        self.cert_switch.setChecked(draft.accept_server_cert)
        self.group.setText(draft.p2p_group)
        self.password.setText(draft.p2p_key)
        self.receive_only.setChecked(draft.direction == "download-only")
        self.discovery_server.setText(draft.discovery_server)
        index = _DIRECTIONS.index(draft.direction) if draft.direction in _DIRECTIONS else 0
        self.direction.setCurrentIndex(index)
        self.continuous.setChecked(draft.continuous)
        self.auto_sync.setChecked(draft.auto_sync)
        self.start_at_login.setChecked(draft.start_at_login)
        self._server_fingerprint = draft.server_fingerprint
        self._discovery_server_fingerprint = draft.discovery_server_fingerprint
        self._server_verified = draft.server_verified
        self._server_verified_at = draft.server_verified_at
        self._discovery_server_verified = draft.discovery_server_verified
        self._discovery_server_verified_at = draft.discovery_server_verified_at
        if draft.p2p_group == "" and draft.mode in (WizardMode.LAN_SYNC, WizardMode.REMOTE_SYNC):
            self.group.setText(generate_group_name(draft.local_path))
        self._update_test_enabled()

    def store(self, draft: WizardDraft) -> None:
        draft.server_url = self.server_url.text().strip()
        draft.api_key = self.api_key.text().strip()
        draft.bucket = self.bucket.text().strip()
        draft.accept_server_cert = self.cert_switch.isChecked()
        draft.p2p_group = self.group.text().strip()
        draft.p2p_key = self.password.text().strip()
        draft.discovery_server = self.discovery_server.text().strip()
        draft.direction = self._current_direction()
        draft.continuous = self.continuous.isChecked()
        draft.auto_sync = self.auto_sync.isChecked()
        draft.start_at_login = self.start_at_login.isChecked()
        draft.server_pin = self.cert_switch.isChecked()
        draft.discovery_server_pin = self.trust_save.isChecked() and bool(
            self._discovery_server_fingerprint
        )
        draft.server_fingerprint = self._server_fingerprint
        draft.discovery_server_fingerprint = self._discovery_server_fingerprint
        draft.server_verified = self._server_verified
        draft.server_verified_at = self._server_verified_at
        draft.discovery_server_verified = self._discovery_server_verified
        draft.discovery_server_verified_at = self._discovery_server_verified_at

    def field_error_targets(self) -> dict[str, tuple[QWidget, InlineError]]:
        return {name: (field, error) for name, (_c, field, error, _l) in self._rows.items()}

    def blocks_progress(self) -> bool:
        """A team-share 404 must block Finish (no private-empty-share surprise)."""
        return self._share_missing and self._mode == WizardMode.TEAM_SHARE

    def focus_first(self) -> None:
        name = "server_url" if self._stack.currentWidget() is self._server_page else "p2p_group"
        self._rows[name][1].setFocus()


def _health_failure(health) -> ProbeOutcome:
    if health.status in (401, 403):
        return ProbeOutcome(False, health.status, reason="unauthorized")
    if health.status is not None and health.status >= 500:
        return ProbeOutcome(False, health.status, reason="server_error")
    return ProbeOutcome(False, health.status, reason="unreachable")


def _probe_message(reason: str) -> str:
    return {
        "share_missing": tr("wizard.probe.404_backup"),
        "unauthorized": tr("wizard.probe.401"),
        "bad_share": tr("wizard.probe.400"),
        "server_error": tr("wizard.probe.5xx"),
    }.get(reason, tr("wizard.probe.unreachable"))
