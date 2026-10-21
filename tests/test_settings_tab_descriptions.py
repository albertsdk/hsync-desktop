# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the purpose line at the top of the Sync / p2p / Server tabs."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from hsync_desktop import i18n
from hsync_desktop.locales import de, en, es, fr, it, ja, nl, pl, pt, ru, zh
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
    _TAB_DESCRIPTION_KEYS,
)

_MODE_TABS = (_SYNC_TAB_INDEX, _P2P_TAB_INDEX, _SERVER_TAB_INDEX)

_TRANSLATIONS_BY_CODE = {
    "en": en.translations,
    "it": it.translations,
    "de": de.translations,
    "fr": fr.translations,
    "es": es.translations,
    "pt": pt.translations,
    "zh": zh.translations,
    "ru": ru.translations,
    "nl": nl.translations,
    "pl": pl.translations,
    "ja": ja.translations,
}


class TestTabDescriptions:
    """Each mode tab opens with one muted sentence saying what it is for."""

    def test_every_mode_tab_opens_with_its_description(self, dialog):
        for tab_index in _MODE_TABS:
            label = dialog._tab_descriptions[tab_index]
            layout = dialog._tabs.widget(tab_index).layout()
            assert layout.itemAt(0).widget() is label
            assert isinstance(label, QLabel)
            assert label.objectName() == "mutedHint"
            assert label.wordWrap()
            assert label.isEnabled()

    def test_description_text_matches_the_active_language(self, dialog):
        expected = _TRANSLATIONS_BY_CODE[i18n.get_language()]
        for tab_index, key in _TAB_DESCRIPTION_KEYS.items():
            assert dialog._tab_descriptions[tab_index].text() == expected[key]

    def test_general_and_advanced_have_no_description(self, dialog):
        assert _GENERAL_TAB_INDEX not in dialog._tab_descriptions
        assert _ADVANCED_TAB_INDEX not in dialog._tab_descriptions

    def test_description_width_is_capped(self, dialog):
        # A wrapped label reports its unwrapped width as sizeHint; the cap keeps
        # a long translation from widening the fixed-size dialog.
        for label in dialog._tab_descriptions.values():
            assert label.maximumWidth() < dialog.minimumWidth()

    def test_description_has_breathing_room(self, dialog):
        """The purpose line is inset from the tab edge and the first group."""
        for tab_index in _MODE_TABS:
            margins = dialog._tab_descriptions[tab_index].contentsMargins()
            assert margins.left() > 0
            assert margins.right() > 0
            assert margins.bottom() > 0

    def test_descriptions_follow_a_language_change(self, dialog):
        previous = i18n.get_language()
        try:
            for code in ("it", "de"):
                i18n.set_language(code)
                dialog._apply_translations()
                texts = _TRANSLATIONS_BY_CODE[code]
                for tab_index, key in _TAB_DESCRIPTION_KEYS.items():
                    assert dialog._tab_descriptions[tab_index].text() == texts[key]
        finally:
            i18n.set_language(previous)
            dialog._apply_translations()

    def test_server_description_stays_readable_while_p2p_mode_is_on(self, dialog):
        dialog.p2p_mode.setChecked(True)
        try:
            assert not dialog.server_url.isEnabled()
            assert dialog._tab_descriptions[_SERVER_TAB_INDEX].isEnabled()
        finally:
            dialog.p2p_mode.setChecked(False)

    def test_descriptions_stay_readable_during_a_sync(self, dialog):
        dialog.set_connection_active(True)
        try:
            assert not dialog.shared_path.isEnabled()
            for tab_index in _MODE_TABS:
                assert dialog._tab_descriptions[tab_index].isEnabled()
        finally:
            dialog.set_connection_active(False)
