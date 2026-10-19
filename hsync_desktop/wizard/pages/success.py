# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Success screen shown after the wizard applies the configuration."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from hsync_desktop.i18n import tr
from hsync_desktop.icons import icon
from hsync_desktop.wizard.model import WizardDraft, profile_for
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.widgets import PrimaryButton, muted_label

__all__ = ["SuccessPage"]


class SuccessPage(WizardPage):
    start_requested = Signal()
    dashboard_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        self._icon = QLabel()
        self._icon.setPixmap(icon("dialog-ok").pixmap(48, 48))
        self._icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._icon)

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        font = self._title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 6)
        self._title.setFont(font)
        layout.addWidget(self._title)

        self._desc = muted_label()
        layout.addWidget(self._desc)

        self._invite_title = QLabel()
        layout.addWidget(self._invite_title)
        # Read-only selectable field so the group/password can be selected too.
        self._invite_text = QPlainTextEdit()
        self._invite_text.setReadOnly(True)
        self._invite_text.setFixedHeight(56)
        self._invite_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._invite_text)
        self._copy = QPushButton()
        self._copy.clicked.connect(self._on_copy)
        layout.addWidget(self._copy)

        self._what_next = muted_label()
        layout.addWidget(self._what_next)
        # Action bar anchored at the bottom, separated from the content.
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.start = PrimaryButton()
        self.start.clicked.connect(self.start_requested.emit)
        self.dashboard = QPushButton()
        self.dashboard.clicked.connect(self.dashboard_requested.emit)
        buttons.addWidget(self.start)
        buttons.addWidget(self.dashboard)
        layout.addLayout(buttons)
        self.apply_translations()

    def apply_translations(self) -> None:
        self._title.setText(tr("wizard.success.title"))
        self._desc.setText(tr("wizard.success.desc"))
        self._invite_title.setText(tr("wizard.success.invite"))
        self._copy.setText(tr("wizard.action.copy_invite"))
        self._what_next.setText(tr("wizard.success.what_next"))
        self.start.setText(tr("wizard.action.start_syncing"))
        self.dashboard.setText(tr("wizard.action.go_dashboard"))

    def load(self, draft: WizardDraft) -> None:
        profile = profile_for(draft.mode) if draft.mode else None
        is_p2p = profile is not None and profile.p2p_enabled
        self._invite_title.setVisible(is_p2p)
        self._invite_text.setVisible(is_p2p)
        self._copy.setVisible(is_p2p)
        if is_p2p:
            self._invite_text.setPlainText(
                tr("wizard.success.invite_text").format(
                    group=draft.p2p_group, password=draft.p2p_key
                )
            )

    def _on_copy(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._invite_text.toPlainText())
