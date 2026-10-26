# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Step 4 — review before applying."""

from __future__ import annotations

from PySide6.QtCore import QDateTime, QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.wizard.model import WizardDraft, WizardMode, profile_for
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.widgets import section_title

__all__ = ["ReviewPage"]

_STEP_FOR_SECTION = {
    "mode": 0,
    "folder": 1,
    "connection": 2,
    "behaviour": 2,
    "checks": 2,
}

_TITLE_KEYS = {
    "mode": "wizard.step.mode",
    "folder": "wizard.step.folder",
    "connection": "wizard.step.connection",
    "behaviour": "wizard.review.behaviour",
    "checks": "wizard.review.checks",
}

# Uniform width so the per-section "Edit" buttons align in one column.
_EDIT_MIN_WIDTH = 96


def _mask(secret: str) -> str:
    if not secret:
        return "—"
    if len(secret) <= 4:
        return "•" * len(secret)
    return "•" * 6 + secret[-4:]


def _format_verified_at(iso: str) -> str:
    """Render an ISO-8601 UTC timestamp as a localised local time."""
    moment = QDateTime.fromString(iso, Qt.DateFormat.ISODate)
    if not moment.isValid():
        return iso
    return QLocale().toString(moment.toLocalTime(), QLocale.FormatType.ShortFormat)


def _checks_text(draft: WizardDraft) -> str:
    """Describe the last real verification (never claim more than was checked)."""
    mode = draft.mode
    profile = profile_for(mode) if mode else None
    if mode == WizardMode.LAN_SYNC:
        return tr("wizard.connection.lan_no_test")
    if profile is not None and not profile.p2p_enabled:
        if draft.server_verified and draft.server_verified_at:
            return tr("wizard.review.verified_at").format(
                time=_format_verified_at(draft.server_verified_at)
            )
        return tr("wizard.review.not_verified")
    if profile is not None and profile.requires_discovery_server:
        if draft.discovery_server_verified and draft.discovery_server_fingerprint:
            return tr("wizard.connection.test_discovery_server_ok").format(
                fingerprint=draft.discovery_server_fingerprint
            )
        return tr("wizard.review.not_verified")
    return tr("wizard.review.not_verified")


class ReviewPage(WizardPage):
    edit_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scrollable so long bodies (behaviour/checks) are never clipped.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        self._sections: dict[str, tuple[QWidget, QLabel, QPushButton, QLabel]] = {}
        for section in ("mode", "folder", "connection", "behaviour", "checks"):
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 8)
            header = QGridLayout()
            title = section_title("")
            header.addWidget(title, 0, 0)
            edit = QPushButton()
            edit.setFlat(True)
            edit.setMinimumWidth(_EDIT_MIN_WIDTH)
            edit.clicked.connect(
                lambda _=False, s=section: self.edit_requested.emit(_STEP_FOR_SECTION[s])
            )
            header.addWidget(
                edit, 0, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            header.setColumnStretch(0, 1)
            body = muted_label("")
            box_layout.addLayout(header)
            box_layout.addWidget(body)
            layout.addWidget(box)
            if section != "checks":
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                layout.addWidget(separator)
            self._sections[section] = (box, body, edit, title)
        self._note = muted_label()
        layout.addWidget(self._note)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.apply_translations()

    def apply_translations(self) -> None:
        for key, (_box, _body, edit, title) in self._sections.items():
            title.setText(tr(_TITLE_KEYS[key]))
            edit.setText(tr("wizard.action.edit"))
        self._note.setText(tr("wizard.review.apply_note"))

    def load(self, draft: WizardDraft) -> None:
        mode = draft.mode
        profile = profile_for(mode) if mode else None

        self._set(
            "mode",
            f"{tr(f'wizard.mode.{mode.value}.title')}\n{tr(f'wizard.mode.{mode.value}.desc')}"
            if mode
            else "",
        )
        self._set("folder", draft.local_path or "—")

        lines = [f"{tr('wizard.connection.share')}: {draft.bucket or '—'}"]
        if profile is not None and not profile.p2p_enabled:
            lines.append(f"{tr('wizard.connection.server_url')}: {draft.server_url or '—'}")
            lines.append(f"{tr('wizard.connection.api_key')}: {_mask(draft.api_key)}")
        else:
            lines.append(f"{tr('wizard.connection.group')}: {draft.p2p_group or '—'}")
            lines.append(f"{tr('wizard.connection.password')}: {_mask(draft.p2p_key)}")
            if profile is not None and profile.requires_discovery_server:
                lines.append(
                    f"{tr('wizard.connection.discovery_server')}: {draft.discovery_server or '—'}"
                )
        self._set("connection", "\n".join(lines))

        direction_label = {
            "bidirectional": tr("settings.sync_direction.bidirectional"),
            "upload-only": tr("settings.sync_direction.upload_only"),
            "download-only": tr("settings.sync_direction.download_only"),
        }.get(draft.direction, draft.direction)
        behaviour = [
            f"{tr('settings.sync_direction')}: {direction_label}",
            f"{tr('wizard.review.keep_deleted')}: {_on_off(draft.ignore_delete)}",
            f"{tr('wizard.automation.continuous')}: {_on_off(draft.continuous)}",
            f"{tr('wizard.automation.auto_sync')}: {_on_off(draft.auto_sync)}",
            f"{tr('wizard.automation.start_at_login')}: {_on_off(draft.start_at_login)}",
        ]
        self._set("behaviour", "\n".join(behaviour))
        self._set("checks", _checks_text(draft))

    def _set(self, section: str, text: str) -> None:
        self._sections[section][1].setText(text)

    def focus_first(self) -> None:
        self._sections["mode"][2].setFocus()


def _on_off(value: bool) -> str:
    return tr("wizard.review.value_on") if value else tr("wizard.review.value_off")
