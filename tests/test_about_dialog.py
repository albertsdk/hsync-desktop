# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the Help -> About window (information, credits, license)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QLabel

from hsync_desktop import about_dialog
from hsync_desktop.about_dialog import (
    TAB_CREDITS,
    TAB_INFO,
    TAB_LICENSE,
    AboutDialog,
    license_text,
)
from hsync_desktop.credits import CREDIT_SECTIONS
from hsync_desktop.i18n import tr


@pytest.fixture(autouse=True)
def _no_bundled_binary(monkeypatch):
    """Keep the engine-version probe off the real bundled binary.

    ``AboutDialog`` starts a ``BinaryVersionProbe`` on construction; without this
    the tests would spawn the real ``hsync`` executable and touch the host's
    QSettings cache. The probe degrades to an empty version instead.
    """
    from hsync_desktop.engine import cli as engine_cli

    monkeypatch.setattr(engine_cli, "find_hsync_binary", lambda: None)


def _make(qtbot, **kwargs) -> AboutDialog:
    dialog = AboutDialog(**kwargs)
    qtbot.addWidget(dialog)
    return dialog


class TestLicenseText:
    def test_reads_the_project_license(self) -> None:
        text = license_text()
        assert "BSD 3-Clause License" in text
        assert "Redistribution and use in source and binary forms" in text


class TestTabs:
    def test_has_the_three_sections(self, qtbot) -> None:
        dialog = _make(qtbot)
        tabs = dialog._tabs
        assert tabs.count() == 3
        assert [tabs.tabText(index) for index in range(3)] == [
            tr("about.tab.info"),
            tr("about.tab.credits"),
            tr("about.tab.license"),
        ]

    def test_opens_on_the_information_tab(self, qtbot) -> None:
        assert _make(qtbot)._tabs.currentIndex() == TAB_INFO

    def test_can_open_on_the_credits_tab(self, qtbot) -> None:
        assert _make(qtbot, initial_tab=TAB_CREDITS)._tabs.currentIndex() == TAB_CREDITS

    def test_can_open_on_the_license_tab(self, qtbot) -> None:
        assert _make(qtbot, initial_tab=TAB_LICENSE)._tabs.currentIndex() == TAB_LICENSE


class TestInformationTab:
    def test_shows_the_app_identity(self, qtbot) -> None:
        from hsync_desktop import __version__

        dialog = _make(qtbot)
        assert dialog._lbl_app_name.text() == tr("app.name")
        assert dialog._lbl_tagline.text() == tr("app.tagline")
        assert dialog._lbl_copyright.text() == tr("about.copyright")
        assert dialog._lbl_author.text() == "Alberto Basso"
        expected = tr("about.version").replace("{version}", __version__).replace("{engine}", "—")
        assert dialog._lbl_version.text() == expected

    def test_window_title_is_the_short_about_label(self, qtbot) -> None:
        dialog = _make(qtbot)
        assert dialog.windowTitle() == tr("menu.help.about")

    def test_can_be_resized_down_to_its_floor(self, qtbot) -> None:
        dialog = _make(qtbot)
        assert dialog.minimumSize().width() == 640
        assert dialog.minimumSize().height() == 480

    @pytest.mark.parametrize(
        ("widget_name", "expected"),
        [
            ("_btn_github", "GITHUB_REPO"),
            ("_btn_docs", "DOCS_INDEX"),
            ("_btn_full_list", "CONTRIBUTORS"),
        ],
    )
    def test_links_open_the_project_pages(self, qtbot, monkeypatch, widget_name, expected):
        opened: list[str] = []
        monkeypatch.setattr(about_dialog, "open_docs_link", opened.append)

        dialog = _make(qtbot)
        getattr(dialog, widget_name).click()

        from hsync_desktop import docs_links

        assert opened == [getattr(docs_links, expected)]


class TestCreditsTab:
    def test_lists_a_title_and_every_person(self, qtbot) -> None:
        dialog = _make(qtbot)
        labels = [label.text() for label in dialog._credits_container.findChildren(QLabel)]
        for section in CREDIT_SECTIONS:
            assert tr(section.title_key) in labels
            for person in section.people:
                assert f"{person.name} (@{person.handle})" in labels
        # ``tr`` returns the key itself when a translation is missing, so a raw
        # ``about.*`` string here means the locale keys drifted from this data.
        assert not [text for text in labels if text.startswith("about.")]

    def test_section_titles_are_bold(self, qtbot) -> None:
        dialog = _make(qtbot)
        titles = {tr(section.title_key) for section in CREDIT_SECTIONS}
        labelled = [
            label
            for label in dialog._credits_container.findChildren(QLabel)
            if label.text() in titles
        ]
        assert len(labelled) == len(titles)
        assert all(label.font().bold() for label in labelled)


class TestLicenseTab:
    def test_shows_the_readonly_license(self, qtbot) -> None:
        dialog = _make(qtbot)
        assert dialog._txt_license.isReadOnly()
        assert dialog._txt_license.toPlainText() == license_text()

    def test_uses_the_small_monospace_font(self, qtbot, monkeypatch) -> None:
        from PySide6.QtGui import QFont

        monkeypatch.setattr(about_dialog, "small_monospace_font", lambda: QFont("Probe Small"))

        dialog = _make(qtbot)

        assert dialog._txt_license.font().family() == "Probe Small"

    def test_falls_back_when_the_text_is_unavailable(self, qtbot, monkeypatch) -> None:
        monkeypatch.setattr(about_dialog, "license_text", lambda: "")

        dialog = _make(qtbot)

        assert dialog._txt_license.toPlainText() == tr("license.unavailable")


class TestClose:
    def test_close_button_is_localised(self, qtbot) -> None:
        dialog = _make(qtbot)
        close_btn = dialog._button_box.button(QDialogButtonBox.StandardButton.Close)
        assert close_btn is not None
        assert close_btn.text() == tr("action.close")
