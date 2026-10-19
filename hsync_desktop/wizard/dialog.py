# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The setup wizard dialog: shell, navigation, draft and apply."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.config import (
    DEFAULT_BUCKET,
    DEFAULT_GROUP,
    DEFAULT_IGNORE_DELETE,
    DEFAULT_MIN_FREE_DISK_SPACE,
    DEFAULT_START_AT_LOGIN,
    DEFAULT_SYNC_DIRECTION,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.i18n import register_language_callback, tr, unregister_language_callback
from hsync_desktop.icons import icon, themed_icon
from hsync_desktop.wizard import messages
from hsync_desktop.wizard.apply import apply_draft
from hsync_desktop.wizard.defaults import (
    default_share_name,
    generate_group_name,
    generate_password,
)
from hsync_desktop.wizard.model import (
    WizardDraft,
    WizardMode,
    infer_mode_from_settings,
    load_draft,
    mark_completed,
    profile_for,
    save_draft,
)
from hsync_desktop.wizard.pages import (
    ConnectionPage,
    FolderPage,
    ModePage,
    ReviewPage,
    SuccessPage,
)
from hsync_desktop.wizard.stepper import StepIndicator
from hsync_desktop.wizard.validation import (
    STEP_CONNECTION,
    STEP_REVIEW,
    validate_step,
)
from hsync_desktop.wizard.widgets import InlineError, PrimaryButton, set_field_error

__all__ = ["SetupWizard"]

_SUCCESS_INDEX = 4

_PAGE_TITLE_KEYS = (
    "wizard.step.mode",
    "wizard.step.folder",
    "wizard.step.connection",
    "wizard.step.review",
)


class SetupWizard(QDialog):
    """Guided, re-runnable configuration assistant."""

    def __init__(self, parent: QWidget | None = None, settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("wizard.title"))
        self.setModal(True)
        self._settings = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._draft = WizardDraft()
        self._step = 0
        self.applied = False
        self.start_requested = False
        self._min_free_mb = int(
            cast(
                int,
                self._settings.value("sync/min_free_disk_space", DEFAULT_MIN_FREE_DISK_SPACE, int),
            )
        )

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_draft)

        self._build_ui()
        register_language_callback(self._retranslate)
        self._restore()

    # ── construction ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        self._subtitle = QLabel()
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._subtitle)
        self._stepper = StepIndicator(4)
        layout.addWidget(self._stepper)
        self._resume = QLabel()
        self._resume.setObjectName("mutedHint")
        self._resume.setVisible(False)
        layout.addWidget(self._resume)

        self._page_title = QLabel()
        title_font = self._page_title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        self._page_title.setFont(title_font)
        layout.addWidget(self._page_title)

        self._stack = QStackedWidget()
        self.mode_page = ModePage()
        self.folder_page = FolderPage()
        self.connection_page = ConnectionPage()
        self.review_page = ReviewPage()
        self.success_page = SuccessPage()
        self._pages = [self.mode_page, self.folder_page, self.connection_page, self.review_page]
        for page in self._pages:
            page.changed.connect(self._schedule_save)
            self._stack.addWidget(page)
        self._stack.addWidget(self.success_page)
        layout.addWidget(self._stack, 1)

        self._general_error = QLabel()
        self._general_error.setObjectName("inlineError")
        self._general_error.setWordWrap(True)
        self._general_error.setVisible(False)
        layout.addWidget(self._general_error)

        footer = QHBoxLayout()
        self._later = QPushButton()
        self._later.clicked.connect(self.reject)
        footer.addWidget(self._later)
        self._skip_defaults = QPushButton()
        self._skip_defaults.clicked.connect(self._on_skip_defaults)
        footer.addWidget(self._skip_defaults)
        footer.addStretch(1)
        self._back = QPushButton()
        self._back.setIcon(icon("go-previous"))
        self._back.clicked.connect(self._on_back)
        footer.addWidget(self._back)
        self._primary = PrimaryButton()
        self._primary.clicked.connect(self._on_primary)
        self._primary.setDefault(True)
        footer.addWidget(self._primary)
        layout.addLayout(footer)

        self.review_page.edit_requested.connect(self._set_step)
        self.success_page.start_requested.connect(self._on_start_syncing)
        self.success_page.dashboard_requested.connect(self.accept)

        self._retranslate()
        self._update_footer()
        self.setMinimumSize(560, 480)
        self.resize(680, 620)

    # ── draft lifecycle ──────────────────────────────────────────────────
    def _prefill_from_settings(self) -> None:
        d = self._draft
        s = self._settings
        d.local_path = str(s.value("path/local", "", str))
        d.bucket = str(s.value("sync/bucket", DEFAULT_BUCKET, str))
        d.server_url = str(s.value("connection/server_url", "", str))
        d.api_key = decrypt_value(str(s.value("connection/api_key", "", str)))
        d.p2p_group = str(s.value("p2p/group", DEFAULT_GROUP, str))
        d.p2p_key = decrypt_value(str(s.value("p2p/key", "", str)))
        d.relay = str(s.value("p2p/bootnode", "", str))
        d.direction = str(s.value("sync/direction", DEFAULT_SYNC_DIRECTION, str))
        d.ignore_delete = bool(s.value("sync/ignore_delete", DEFAULT_IGNORE_DELETE, bool))
        d.auto_sync = bool(s.value("sync/auto_sync", False, bool))
        d.start_at_login = bool(s.value("appearance/start_at_login", DEFAULT_START_AT_LOGIN, bool))

    def _restore(self) -> None:
        resumed = load_draft(self._settings)
        self._prefill_from_settings()
        if resumed is not None:
            draft, step = resumed
            self._draft = draft
            self._step = min(step, STEP_REVIEW)
            self._resume.setText(tr("wizard.resume.banner").format(step=self._step + 1))
            self._resume.setVisible(True)
        else:
            self._draft.mode = infer_mode_from_settings(self._settings)
            if self._draft.mode is not None:
                self._apply_mode_defaults(self._draft.mode)
        self._sync_pages()
        self._set_step(self._step)

    def _apply_mode_defaults(self, mode: WizardMode) -> None:
        profile = profile_for(mode)
        d = self._draft
        d.direction = profile.direction
        d.ignore_delete = profile.ignore_delete
        d.start_at_login = profile.start_at_login
        d.continuous = True
        d.auto_sync = True
        if profile.p2p_enabled:
            if not d.p2p_group:
                d.p2p_group = generate_group_name(d.local_path)
            if not d.p2p_key:
                d.p2p_key = generate_password()

    def _sync_pages(self) -> None:
        self.mode_page.load(self._draft)
        self.folder_page.load(self._draft)
        self.connection_page.set_mode(self._draft.mode)
        self.connection_page.load(self._draft)
        self.review_page.load(self._draft)

    def _store_pages(self) -> None:
        for page in self._pages:
            page.store(self._draft)

    def _save_draft(self) -> None:
        if self.applied or self._step >= len(self._pages):
            return
        save_draft(self._settings, self._draft, self._step)

    def _schedule_save(self) -> None:
        self._save_timer.start(300)

    # ── navigation ───────────────────────────────────────────────────────
    def _set_step(self, step: int) -> None:
        self._step = max(0, min(step, len(self._pages)))
        self._stack.setCurrentIndex(self._step)
        self._stepper.set_current(self._step)
        success = self._step == _SUCCESS_INDEX
        # The final screen is a destination, not another step: drop the
        # progress header (subtitle, step index, resume banner).
        self._subtitle.setVisible(not success)
        self._stepper.setVisible(not success)
        self._resume.setVisible(not success and bool(self._resume.text()))
        if self._step < len(_PAGE_TITLE_KEYS):
            self._page_title.setText(tr(_PAGE_TITLE_KEYS[self._step]))
            self._page_title.setVisible(True)
        else:
            self._page_title.setVisible(False)
        self._update_footer()
        if self._step < len(self._pages):
            self._pages[self._step].focus_first()

    def _update_footer(self) -> None:
        success = self._step == _SUCCESS_INDEX
        self._later.setVisible(self._step == 0)
        self._skip_defaults.setVisible(self._step == STEP_CONNECTION)
        self._back.setVisible(0 < self._step < _SUCCESS_INDEX)
        self._primary.setVisible(not success)
        if self._step == STEP_REVIEW:
            self._primary.setText(tr("wizard.action.finish"))
            # Completion action: no directional arrow.
            self._primary.setIcon(QIcon())
        else:
            self._primary.setText(tr("wizard.action.continue"))
            self._primary.setIcon(themed_icon("go-next", "#FFFFFF"))

    def _on_back(self) -> None:
        self._store_pages()
        self._set_step(self._step - 1)

    def _on_skip_defaults(self) -> None:
        self._store_pages()
        profile = profile_for(self._draft.mode) if self._draft.mode else None
        if profile is not None:
            self._draft.continuous = True
            self._draft.auto_sync = True
            self.connection_page.load(self._draft)
        if self._validate_current():
            self._set_step(self._step + 1)

    def _on_primary(self) -> None:
        self._store_pages()
        if self._step == STEP_REVIEW:
            self._finish()
            return
        if not self._validate_current():
            return
        if self._step == 0 and self._draft.mode is not None:
            self._apply_mode_defaults(self._draft.mode)
            self._sync_pages()
        elif self._step == 1:
            self._derive_bucket_if_default()
            self.connection_page.load(self._draft)
        self._set_step(self._step + 1)

    def _derive_bucket_if_default(self) -> None:
        d = self._draft
        if d.local_path and d.bucket in ("", DEFAULT_BUCKET):
            d.bucket = default_share_name(d.local_path)

    def _validate_current(self) -> bool:
        self._general_error.setVisible(False)
        error_map: dict[str, tuple[QWidget, InlineError]] = {}
        for page in self._pages:
            error_map.update(page.field_error_targets())
        for field, error in error_map.values():
            set_field_error(field, error, "")
        issues = validate_step(self._draft, self._step, min_free_mb=self._min_free_mb)
        blocked = self._step == STEP_CONNECTION and self.connection_page.blocks_progress()
        first_field = None
        general = ""
        for issue in issues:
            if issue.level != "error":
                continue
            target = error_map.get(issue.field)
            if target is not None:
                set_field_error(target[0], target[1], messages.issue_message(issue))
                first_field = first_field or target[0]
            else:
                general = general or messages.issue_message(issue)
        if general:
            self._general_error.setText(general)
            self._general_error.setVisible(True)
        if first_field is not None:
            first_field.setFocus()
        return not general and not any(i.level == "error" for i in issues) and not blocked

    def _finish(self) -> None:
        self._store_pages()
        if not self._validate_current():
            self._set_step(STEP_CONNECTION)
            return
        result = apply_draft(self._settings, self._draft)
        if result.pin_error:
            message = (
                tr("wizard.error.pin_no_binary")
                if result.pin_error == "no_binary"
                else tr("wizard.error.pin_failed")
            )
            answer = QMessageBox.question(
                self,
                tr("wizard.title"),
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                apply_draft(self._settings, self._draft, pin=False)
            else:
                return
        mark_completed(self._settings)
        self._settings.sync()
        self.applied = True
        self.success_page.load(self._draft)
        self._set_step(_SUCCESS_INDEX)

    def _on_start_syncing(self) -> None:
        self.start_requested = True
        self.accept()

    # ── i18n / teardown ──────────────────────────────────────────────────
    def _retranslate(self) -> None:
        self.setWindowTitle(tr("wizard.title"))
        self._subtitle.setText(tr("wizard.subtitle"))
        self._later.setText(tr("wizard.action.later"))
        self._skip_defaults.setText(tr("wizard.action.skip_defaults"))
        self._back.setText(tr("wizard.action.back"))
        self._stepper.apply_translations()
        for page in (*self._pages, self.success_page):
            page.apply_translations()
        if self._step < len(_PAGE_TITLE_KEYS):
            self._page_title.setText(tr(_PAGE_TITLE_KEYS[self._step]))
        self._update_footer()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._save_draft()
        if self.applied:
            mark_completed(self._settings)
        self._settings.sync()
        unregister_language_callback(self._retranslate)
        super().closeEvent(event)
