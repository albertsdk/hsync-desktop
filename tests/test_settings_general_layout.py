# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Layout of the General tab: three sections, switches aligned inside each."""

from __future__ import annotations

from hsync_desktop.config import NOTIFICATION_CATEGORIES
from hsync_desktop.i18n import tr
from hsync_desktop.settings.tab_indices import _GENERAL_TAB_INDEX
from hsync_desktop.widgets.text import escape_mnemonics


def _open_general_tab(dialog, qtbot):
    dialog._tabs.setCurrentIndex(_GENERAL_TAB_INDEX)
    dialog.show()
    qtbot.wait(1)
    return dialog


def _x(widget, anchor) -> int:
    return widget.mapTo(anchor, widget.rect().topLeft()).x()


class TestGeneralSections:
    """The page is grouped in the sections every HIG recommends."""

    def test_the_tab_ships_three_sections(self, dialog):
        titles = [
            dialog._grp_general_appearance.title(),
            dialog._grp_general_notifications.title(),
            dialog._grp_general_window.title(),
        ]

        # ``_group_box`` escapes ``&`` so the title renders it literally.
        assert titles == [
            escape_mnemonics(tr("settings.group.appearance")),
            escape_mnemonics(tr("settings.group.notifications")),
            escape_mnemonics(tr("settings.group.window")),
        ]

    def test_the_appearance_section_holds_language_theme_and_font(self, dialog):
        group = dialog._grp_general_appearance

        for widget in (dialog.lang_combo, dialog.theme_combo, dialog.font_scale_combo):
            assert group.isAncestorOf(widget)

    def test_the_notifications_section_holds_the_master_switch_and_categories(self, dialog):
        group = dialog._grp_general_notifications

        assert group.isAncestorOf(dialog.notifications_enabled)
        assert group.isAncestorOf(dialog._lbl_notifications_categories)
        assert set(dialog.notification_toggles) == set(NOTIFICATION_CATEGORIES)
        for toggle, label in dialog.notification_toggles.values():
            assert group.isAncestorOf(toggle)
            assert group.isAncestorOf(label)

    def test_the_window_section_holds_the_switches_and_closes_with_advanced(self, dialog):
        group = dialog._grp_general_window

        for widget in (
            dialog.tooltips_enabled,
            dialog.show_log_panel,
            dialog.start_at_login,
            dialog.show_advanced,
        ):
            assert group.isAncestorOf(widget)

        # The advanced disclosure is the page's last row.
        form = group.layout()
        item = form.itemAt(form.rowCount() - 1, form.ItemRole.FieldRole)
        assert item is not None and item.widget() is dialog.show_advanced


class TestGeneralSwitchAlignment:
    """A switch row is ``caption [toggle]``: captions and controls in one column."""

    def test_the_switches_of_a_section_share_one_column(self, dialog, qtbot):
        _open_general_tab(dialog, qtbot)

        for switches in (
            (dialog.notifications_enabled,),
            tuple(toggle for toggle, _label in dialog.notification_toggles.values()),
            (
                dialog.tooltips_enabled,
                dialog.show_log_panel,
                dialog.start_at_login,
                dialog.show_advanced,
            ),
        ):
            columns = {_x(widget, dialog) for widget in switches}
            assert len(columns) == 1, (switches, columns)

    def test_each_caption_precedes_its_switch(self, dialog, qtbot):
        """Label first, control in the field column (the desktop form order)."""
        _open_general_tab(dialog, qtbot)

        pairs = [(dialog.notifications_enabled, dialog._lbl_notifications)]
        pairs += list(dialog.notification_toggles.values())
        for toggle, label in pairs:
            assert _x(label, dialog) < _x(toggle, dialog)

    def test_category_captions_line_up_with_the_master_caption(self, dialog, qtbot):
        _open_general_tab(dialog, qtbot)
        master_x = _x(dialog._lbl_notifications, dialog)

        for _category, (_toggle, label) in dialog.notification_toggles.items():
            assert _x(label, dialog) == master_x

    def test_the_categories_open_with_a_translated_heading(self, dialog, qtbot):
        _open_general_tab(dialog, qtbot)
        heading = dialog._lbl_notifications_categories

        assert heading.text() == tr("settings.notifications_categories")
        assert heading.objectName() == "mutedHint"
        # The heading introduces the block, so it starts where the captions do.
        assert _x(heading, dialog) == _x(dialog._lbl_notifications, dialog)

    def test_the_master_switch_gates_every_category(self, dialog, qtbot):
        _open_general_tab(dialog, qtbot)

        dialog.notifications_enabled.setChecked(False)
        assert not dialog._lbl_notifications_categories.isEnabled()
        assert all(
            not toggle.isEnabled() and not label.isEnabled()
            for toggle, label in dialog.notification_toggles.values()
        )

        dialog.notifications_enabled.setChecked(True)
        assert all(toggle.isEnabled() for toggle, _label in dialog.notification_toggles.values())


class TestSettingsCaptions:
    """Form captions carry no trailing colon: the columns do the separating."""

    def test_no_form_caption_ends_with_a_colon(self, dialog):
        from PySide6.QtWidgets import QFormLayout, QLabel

        captions: list[str] = []
        for form in dialog.findChildren(QFormLayout):
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                label = item.widget() if item is not None else None
                if isinstance(label, QLabel) and label.text().strip():
                    captions.append(label.text())
        assert captions, "no form captions found"
        offenders = [text for text in captions if text.rstrip().endswith((":", "："))]
        assert not offenders, offenders
