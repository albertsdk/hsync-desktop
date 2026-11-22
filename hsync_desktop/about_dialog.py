# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Structured About window: information, credits and license.

Help → About opens it on the Information tab. The license text lives on its own
tab of this window, and the credits come from ``hsync_desktop/credits.py``; the
welcome splash (``hsync_desktop/splash_screen.py``) keeps its own separate
layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop import __version__
from hsync_desktop.about_text import version_text
from hsync_desktop.branding import LOGO_PATH, LOGO_WIDTH
from hsync_desktop.credits import CREDIT_SECTIONS, person_label
from hsync_desktop.docs_links import CONTRIBUTORS, DOCS_INDEX, GITHUB_REPO, open_docs_link
from hsync_desktop.engine import BinaryVersionProbe
from hsync_desktop.fonts import small_monospace_font
from hsync_desktop.i18n import tr
from hsync_desktop.ui.loader import load_ui_widget

TAB_INFO = 0
TAB_CREDITS = 1
TAB_LICENSE = 2


def _license_path() -> Path | None:
    """Locate the ``LICENSE`` file in the frozen bundle or the source tree."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        candidates.append(Path(meipass) / "hsync_desktop" / "LICENSE")
    # ``hsync_desktop/about_dialog.py`` -> repo root is two levels up.
    candidates.append(Path(__file__).resolve().parent.parent / "LICENSE")
    for path in candidates:
        if path.is_file():
            return path
    return None


def license_text() -> str:
    """Return the project license text (empty when the file is unavailable)."""
    path = _license_path()
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


class AboutDialog(QDialog):
    """Application information, credits and license in one tabbed window."""

    def __init__(self, parent: QWidget | None = None, initial_tab: int = TAB_INFO) -> None:
        super().__init__(parent)
        self._load_ui()
        self._apply_translations()
        self._populate_credits()
        self._apply_license()
        self._tabs.setCurrentIndex(initial_tab)
        self._start_engine_version_probe()

    def _load_ui(self) -> None:
        """Load the layout, resolve its widgets and wire the links."""
        load_ui_widget("about_dialog", self)

        self.setWindowTitle(tr("menu.help.about"))
        self._lbl_logo: QLabel = self.findChild(QLabel, "lblLogo")  # type: ignore[assignment]
        self._lbl_app_name: QLabel = self.findChild(QLabel, "lblAppName")  # type: ignore[assignment]
        self._lbl_version: QLabel = self.findChild(QLabel, "lblVersion")  # type: ignore[assignment]
        self._lbl_tagline: QLabel = self.findChild(QLabel, "lblTagline")  # type: ignore[assignment]
        self._lbl_copyright: QLabel = self.findChild(QLabel, "lblCopyright")  # type: ignore[assignment]
        self._lbl_author: QLabel = self.findChild(QLabel, "lblAuthor")  # type: ignore[assignment]
        self._tabs: QTabWidget = self.findChild(QTabWidget, "tabWidget")  # type: ignore[assignment]
        self._txt_license: QPlainTextEdit = self.findChild(QPlainTextEdit, "txtLicense")  # type: ignore[assignment]
        self._btn_github: QPushButton = self.findChild(QPushButton, "btnGithub")  # type: ignore[assignment]
        self._btn_docs: QPushButton = self.findChild(QPushButton, "btnDocs")  # type: ignore[assignment]
        self._btn_full_list: QPushButton = self.findChild(QPushButton, "btnFullList")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

        credits: QWidget | None = self.findChild(QWidget, "creditsContents")
        credits_layout = credits.layout() if credits is not None else None
        if credits is None or not isinstance(credits_layout, QVBoxLayout):
            raise RuntimeError("about_dialog.ui: creditsContents has no QVBoxLayout")
        self._credits_container = credits
        self._credits_layout = credits_layout

        self._btn_github.clicked.connect(self._open_github)
        self._btn_docs.clicked.connect(self._open_documentation)
        self._btn_full_list.clicked.connect(self._open_contributors)
        self._button_box.rejected.connect(self.reject)

        if LOGO_PATH.is_file():
            self._lbl_logo.setPixmap(QIcon(str(LOGO_PATH)).pixmap(QSize(LOGO_WIDTH, LOGO_WIDTH)))

    def _apply_translations(self) -> None:
        """Apply i18n translations to labels, tabs and buttons."""
        self._lbl_app_name.setText(tr("app.name"))
        self._lbl_version.setText(version_text(__version__, "…"))
        self._lbl_tagline.setText(tr("app.tagline"))
        self._lbl_copyright.setText(tr("about.copyright"))
        self._lbl_author.setText(tr("about.author"))
        self._tabs.setTabText(TAB_INFO, tr("about.tab.info"))
        self._tabs.setTabText(TAB_CREDITS, tr("about.tab.credits"))
        self._tabs.setTabText(TAB_LICENSE, tr("about.tab.license"))
        self._btn_github.setText(tr("menu.help.github"))
        self._btn_docs.setText(tr("menu.help.docs"))
        self._btn_full_list.setText(tr("about.credits.full_list"))
        close_btn = self._button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText(tr("action.close"))

    def _populate_credits(self) -> None:
        """Render one titled group of names per credit section, in order."""
        for section in CREDIT_SECTIONS:
            title = QLabel(tr(section.title_key), self._credits_container)
            title_font = title.font()
            title_font.setBold(True)
            title.setFont(title_font)
            self._credits_layout.addWidget(title)
            for person in section.people:
                self._credits_layout.addWidget(
                    QLabel(person_label(person), self._credits_container)
                )
        self._credits_layout.addStretch(1)

    def _apply_license(self) -> None:
        """Fill the license tab with the bundled text and the dense font."""
        self._txt_license.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._txt_license.setFont(small_monospace_font())
        self._txt_license.setPlainText(license_text() or tr("license.unavailable"))

    def _start_engine_version_probe(self) -> None:
        """Resolve the bundled engine version off the UI thread."""
        self._engine_probe = BinaryVersionProbe(None, self)
        self._engine_probe.finished.connect(self._apply_engine_version)
        self._engine_probe.start()

    @Slot(str)
    def _apply_engine_version(self, version: str) -> None:
        """Fill the engine part of the version line, or an em dash when unknown."""
        self._lbl_version.setText(version_text(__version__, version or "—"))

    def _open_github(self) -> None:
        """Open the project page on GitHub."""
        open_docs_link(GITHUB_REPO)

    def _open_documentation(self) -> None:
        """Open the documentation index."""
        open_docs_link(DOCS_INDEX)

    def _open_contributors(self) -> None:
        """Open the published contributors list on GitHub."""
        open_docs_link(CONTRIBUTORS)
