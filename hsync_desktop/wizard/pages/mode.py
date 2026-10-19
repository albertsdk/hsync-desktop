# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Step 1 — pick the use case."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.wizard.model import WizardDraft, WizardMode
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.widgets import PrimaryButton, RadioCard, muted_label

__all__ = ["HelpChoiceDialog", "ModePage"]

_ORDER = (
    WizardMode.BACKUP,
    WizardMode.LAN_SYNC,
    WizardMode.REMOTE_SYNC,
    WizardMode.TEAM_SHARE,
)

_MODE_ICONS = {
    WizardMode.BACKUP: "backup",
    WizardMode.LAN_SYNC: "network-p2p",
    WizardMode.REMOTE_SYNC: "network-cloud",
    WizardMode.TEAM_SHARE: "people",
}


class HelpChoiceDialog(QDialog):
    """Explicit chooser covering all four use cases.

    Three short questions, always visible: "sharing with a team?" → done;
    otherwise "same network?" → done or "copy vs edits". Follow-ups that do not
    apply stay visible but are disabled, with a short explanation. Every button
    is labelled through :func:`tr`, so it is translated in all locales
    regardless of Qt's own (not bundled) standard-button translations.
    """

    def __init__(self, current: WizardMode | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("wizard.help.not_sure"))
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        # Who is it for?
        self._q_share = QLabel(tr("wizard.help.q_share"))
        self._q_share.setWordWrap(True)
        layout.addWidget(self._q_share)
        self._team = QRadioButton(tr("wizard.help.team"))
        self._personal = QRadioButton(tr("wizard.help.personal"))
        self._share_group = QButtonGroup(self)
        self._share_group.addButton(self._team)
        self._share_group.addButton(self._personal)
        layout.addLayout(self._choice_row(self._team, self._personal))

        # Same network? (personal use only)
        self._same_box = QWidget()
        same_layout = QVBoxLayout(self._same_box)
        same_layout.setContentsMargins(0, 0, 0, 0)
        self._q1 = QLabel(tr("wizard.help.q1"))
        self._q1.setWordWrap(True)
        same_layout.addWidget(self._q1)
        self._same_yes = QRadioButton(tr("action.yes"))
        self._same_no = QRadioButton(tr("action.no"))
        self._same_group = QButtonGroup(self)
        self._same_group.addButton(self._same_yes)
        self._same_group.addButton(self._same_no)
        same_layout.addLayout(self._choice_row(self._same_yes, self._same_no))
        layout.addWidget(self._same_box)

        # Only a copy, or edits from both sides? (different networks only)
        self._need_box = QWidget()
        need_layout = QVBoxLayout(self._need_box)
        need_layout.setContentsMargins(0, 0, 0, 0)
        self._q2 = QLabel(tr("wizard.help.q2"))
        self._q2.setWordWrap(True)
        need_layout.addWidget(self._q2)
        self._copy_only = QRadioButton(tr("wizard.help.copy_only"))
        self._edits_both = QRadioButton(tr("wizard.help.edits_both"))
        self._need_group = QButtonGroup(self)
        self._need_group.addButton(self._copy_only)
        self._need_group.addButton(self._edits_both)
        need_layout.addLayout(self._choice_row(self._copy_only, self._edits_both))
        layout.addWidget(self._need_box)

        # Explains why a follow-up question is disabled (nothing is hidden).
        self._note = muted_label()
        self._note.setVisible(False)
        layout.addWidget(self._note)

        self._prefill(current)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel = QPushButton(tr("action.cancel"))
        self._cancel.clicked.connect(self.reject)
        buttons.addWidget(self._cancel)
        self._ok = PrimaryButton(tr("wizard.action.continue"))
        self._ok.clicked.connect(self.accept)
        buttons.addWidget(self._ok)
        layout.addLayout(buttons)

        for radio in (
            self._team,
            self._personal,
            self._same_yes,
            self._same_no,
            self._copy_only,
            self._edits_both,
        ):
            radio.toggled.connect(self._on_answer_changed)
        self._on_answer_changed()

    @staticmethod
    def _choice_row(*radios: QRadioButton) -> QHBoxLayout:
        row = QHBoxLayout()
        for radio in radios:
            row.addWidget(radio)
        row.addStretch(1)
        return row

    def _prefill(self, current: WizardMode | None) -> None:
        if current == WizardMode.TEAM_SHARE:
            self._team.setChecked(True)
        elif current == WizardMode.LAN_SYNC:
            self._personal.setChecked(True)
            self._same_yes.setChecked(True)
        elif current == WizardMode.REMOTE_SYNC:
            self._personal.setChecked(True)
            self._same_no.setChecked(True)
            self._edits_both.setChecked(True)
        elif current == WizardMode.BACKUP:
            self._personal.setChecked(True)
            self._same_no.setChecked(True)
            self._copy_only.setChecked(True)

    def _on_answer_changed(self, *_args) -> None:
        # Nothing disappears: a follow-up that does not apply is disabled and
        # accompanied by an explanation.
        personal = self._personal.isChecked()
        self._same_box.setEnabled(personal)
        self._need_box.setEnabled(personal and self._same_no.isChecked())
        if self._team.isChecked():
            self._note.setText(tr("wizard.help.note_team"))
            self._note.setVisible(True)
        elif personal and self._same_yes.isChecked():
            self._note.setText(tr("wizard.help.note_same_network"))
            self._note.setVisible(True)
        else:
            self._note.setVisible(False)
        self._update_ok()

    def _update_ok(self) -> None:
        """Confirm is enabled only when the answers on the active path suffice."""
        if self._team.isChecked():
            enabled = True
        elif not self._personal.isChecked():
            enabled = False
        elif self._same_yes.isChecked():
            enabled = True
        else:
            enabled = self._same_no.isChecked() and (
                self._copy_only.isChecked() or self._edits_both.isChecked()
            )
        self._ok.setEnabled(enabled)

    def mode(self) -> WizardMode:
        """Map the explicit answers to a mode (all four are reachable)."""
        if self._team.isChecked():
            return WizardMode.TEAM_SHARE
        if self._same_yes.isChecked():
            return WizardMode.LAN_SYNC
        if self._copy_only.isChecked():
            return WizardMode.BACKUP
        return WizardMode.REMOTE_SYNC


class ModePage(WizardPage):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._why = muted_label()
        layout.addWidget(self._why)
        self._cards: dict[WizardMode, RadioCard] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for mode in _ORDER:
            card = RadioCard(mode, "", "", _MODE_ICONS[mode])
            card.selected.connect(self._on_selected)
            self._group.addButton(card.radio)
            self._cards[mode] = card
            layout.addWidget(card)
        self._help = QPushButton()
        self._help.clicked.connect(self._on_help)
        layout.addWidget(self._help)
        layout.addStretch(1)
        self.apply_translations()

    def _on_selected(self, _value: object) -> None:
        self.changed.emit()

    def _current_mode(self) -> WizardMode | None:
        return next((mode for mode, card in self._cards.items() if card.is_selected()), None)

    def _on_help(self) -> None:
        dialog = HelpChoiceDialog(self._current_mode(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._cards[dialog.mode()].set_selected(True)
            self.changed.emit()

    def apply_translations(self) -> None:
        self._why.setText(tr("wizard.why.mode"))
        for mode, card in self._cards.items():
            card.retranslate(
                tr(f"wizard.mode.{mode.value}.title"), tr(f"wizard.mode.{mode.value}.desc")
            )
        self._help.setText(tr("wizard.help.not_sure"))

    def load(self, draft: WizardDraft) -> None:
        for mode, card in self._cards.items():
            card.set_selected(draft.mode == mode)

    def store(self, draft: WizardDraft) -> None:
        draft.mode = self._current_mode()

    def focus_first(self) -> None:
        self._cards[_ORDER[0]].radio.setFocus()
