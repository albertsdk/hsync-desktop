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
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.wizard.model import (
    ChoiceAnswers,
    ChoiceAudience,
    WizardDraft,
    WizardMode,
    resolve_mode,
)
from hsync_desktop.wizard.pages.base import WizardPage
from hsync_desktop.wizard.widgets import PrimaryButton, RadioCard

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
    otherwise "only a copy, or edits?" picks the server backup, and the network
    question then separates the two p2p sync modes. Follow-ups that do not apply
    stay visible but are disabled, with a short explanation. Every button is
    labelled through :func:`tr`, so it is translated in all locales regardless of
    Qt's own (not bundled) standard-button translations.
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

        # Only a copy, or edits from both sides? (personal use only)
        self._need_box = QWidget()
        need_layout = QVBoxLayout(self._need_box)
        need_layout.setContentsMargins(0, 0, 0, 0)
        self._q_copy_edits = QLabel(tr("wizard.help.q_copy_edits"))
        self._q_copy_edits.setWordWrap(True)
        need_layout.addWidget(self._q_copy_edits)
        self._copy_only = QRadioButton(tr("wizard.help.copy_only"))
        self._edits_both = QRadioButton(tr("wizard.help.edits_both"))
        self._need_group = QButtonGroup(self)
        self._need_group.addButton(self._copy_only)
        self._need_group.addButton(self._edits_both)
        need_layout.addLayout(self._choice_row(self._copy_only, self._edits_both))
        layout.addWidget(self._need_box)

        # Same network? (only relevant when syncing, i.e. edits from both sides)
        self._same_box = QWidget()
        same_layout = QVBoxLayout(self._same_box)
        same_layout.setContentsMargins(0, 0, 0, 0)
        self._q_network = QLabel(tr("wizard.help.q_network"))
        self._q_network.setWordWrap(True)
        same_layout.addWidget(self._q_network)
        self._same_yes = QRadioButton(tr("action.yes"))
        self._same_no = QRadioButton(tr("action.no"))
        self._same_group = QButtonGroup(self)
        self._same_group.addButton(self._same_yes)
        self._same_group.addButton(self._same_no)
        same_layout.addLayout(self._choice_row(self._same_yes, self._same_no))
        layout.addWidget(self._same_box)

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
        elif current == WizardMode.BACKUP:
            self._personal.setChecked(True)
            self._copy_only.setChecked(True)
        elif current == WizardMode.LAN_SYNC:
            self._personal.setChecked(True)
            self._edits_both.setChecked(True)
            self._same_yes.setChecked(True)
        elif current == WizardMode.REMOTE_SYNC:
            self._personal.setChecked(True)
            self._edits_both.setChecked(True)
            self._same_no.setChecked(True)

    def _answers(self) -> ChoiceAnswers:
        audience: ChoiceAudience | None = None
        if self._team.isChecked():
            audience = ChoiceAudience.TEAM
        elif self._personal.isChecked():
            audience = ChoiceAudience.PERSONAL
        copy_only: bool | None = None
        if self._copy_only.isChecked():
            copy_only = True
        elif self._edits_both.isChecked():
            copy_only = False
        same_network: bool | None = None
        if self._same_yes.isChecked():
            same_network = True
        elif self._same_no.isChecked():
            same_network = False
        return ChoiceAnswers(audience=audience, copy_only=copy_only, same_network=same_network)

    def _on_answer_changed(self, *_args) -> None:
        # Nothing disappears: a follow-up that does not apply is disabled and
        # accompanied by an explanation.
        personal = self._personal.isChecked()
        self._need_box.setEnabled(personal)
        self._same_box.setEnabled(personal and self._edits_both.isChecked())
        # The note and Confirm share the single mapping in resolve_mode, so they
        # can never disagree with the mode the answers select.
        mode = resolve_mode(self._answers())
        if mode is WizardMode.TEAM_SHARE:
            self._note.setText(tr("wizard.help.note_team"))
            self._note.setVisible(True)
        elif mode is WizardMode.BACKUP:
            self._note.setText(tr("wizard.help.note_backup"))
            self._note.setVisible(True)
        else:
            self._note.setVisible(False)
        self._ok.setEnabled(mode is not None)

    def mode(self) -> WizardMode | None:
        """The mode for the current answers, or ``None`` while incomplete."""
        return resolve_mode(self._answers())


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
            mode = dialog.mode()
            if mode is None:  # unreachable: Confirm is gated on a full answer
                return
            self._cards[mode].set_selected(True)
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
