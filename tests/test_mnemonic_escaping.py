# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Literal ampersands in widgets that parse ``&`` as a mnemonic.

``QGroupBox``, ``QAbstractButton`` and the tab bar underline the character after
an ampersand, so a translated "Share & Path" used to render as "Share_Path" (the
space was underlined). Every locale is scanned, so a new translation cannot
reintroduce the artefact.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QAbstractButton, QGroupBox

from hsync_desktop import i18n
from hsync_desktop.i18n import SUPPORTED_LANGUAGES
from hsync_desktop.settings.credential_dialogs import ApiKeyDialog, P2PKeyDialog
from hsync_desktop.settings.dialog import SettingsDialog
from hsync_desktop.widgets.text import escape_mnemonics


def has_unescaped_ampersand(text: str) -> bool:
    """True when *text* holds an ``&`` that is not doubled."""

    index = 0
    while index < len(text):
        if text[index] == "&":
            if index + 1 < len(text) and text[index + 1] == "&":
                index += 2
                continue
            return True
        index += 1
    return False


@pytest.fixture(params=sorted(SUPPORTED_LANGUAGES))
def language(request):
    """Run a test once per supported locale, restoring the previous one."""

    previous = i18n.get_language()
    i18n.set_language(request.param)
    try:
        yield request.param
    finally:
        i18n.set_language(previous)


class TestEscapeHelper:
    def test_doubles_a_literal_ampersand(self):
        assert escape_mnemonics("Share & Path") == "Share && Path"

    def test_leaves_other_text_alone(self):
        assert escape_mnemonics("Sync") == "Sync"
        assert escape_mnemonics("") == ""


class TestDetector:
    """The scan itself must not miss a single ampersand."""

    def test_flags_a_single_ampersand(self):
        assert has_unescaped_ampersand("Share & Path")
        assert has_unescaped_ampersand("Save &Retry")

    def test_accepts_a_doubled_ampersand(self):
        assert not has_unescaped_ampersand("Share && Path")
        assert not has_unescaped_ampersand("Sync")
        assert not has_unescaped_ampersand("")


class TestSettingsWidgets:
    """No mnemonic-aware widget in the dialog renders a bare ``&``."""

    def test_group_titles_are_escaped(self, language, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        titles = [group.title() for group in dialog.findChildren(QGroupBox)]
        assert titles
        for title in titles:
            assert not has_unescaped_ampersand(title), f"{language}: {title!r}"

    def test_button_texts_are_escaped(self, language, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        buttons = [button.text() for button in dialog.findChildren(QAbstractButton)]
        assert buttons
        for text in buttons:
            assert not has_unescaped_ampersand(text), f"{language}: {text!r}"

    def test_tab_titles_are_escaped(self, language, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        for index in range(dialog._tabs.count()):
            assert not has_unescaped_ampersand(dialog._tabs.tabText(index)), language


class TestKnownProseTitles:
    """The two locales whose prose uses a real ampersand show it verbatim."""

    @pytest.mark.parametrize(
        ("code", "attribute", "expected"),
        [
            ("en", "_grp_path", "Share && Path"),
            ("en", "_grp_timing", "Timing && Intervals"),
            ("en", "_grp_p2p_mode", "Mode && Group"),
            ("en", "_grp_p2p_role", "Role && security"),
            ("de", "_grp_timing", "Zeiten && Intervalle"),
        ],
    )
    def test_ampersand_is_displayed(self, qtbot, code, attribute, expected):
        previous = i18n.get_language()
        i18n.set_language(code)
        try:
            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            assert getattr(dialog, attribute).title() == expected
        finally:
            i18n.set_language(previous)


class TestCredentialDialogs:
    """The "Save & Retry" button keeps its ampersand in both credential dialogs."""

    @pytest.mark.parametrize("code", ["en", "de"])
    @pytest.mark.parametrize("factory", [ApiKeyDialog, P2PKeyDialog])
    def test_save_button_is_escaped(self, qtbot, code, factory):
        previous = i18n.get_language()
        i18n.set_language(code)
        try:
            dialog = factory()
            qtbot.addWidget(dialog)
            texts = [button.text() for button in dialog.findChildren(QAbstractButton)]
            assert texts
            for text in texts:
                assert not has_unescaped_ampersand(text), text
            assert any("&&" in text for text in texts)
        finally:
            i18n.set_language(previous)
