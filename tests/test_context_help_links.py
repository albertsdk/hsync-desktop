# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""One contextual documentation link per dialog that owns a procedure.

The link goes to the page that documents *that* dialog, so a window never sends
the user to the docs index or to a generic guide. These tests pin the target of
each entry point (the mapping is otherwise only visible in the source).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from hsync_desktop import docs_links
from hsync_desktop.i18n import tr


@pytest.fixture(autouse=True)
def _qt_application(qapp):
    """Every dialog below needs the session ``QApplication`` to exist."""
    return qapp


def _help_link(dialog) -> QLabel:
    """The dialog's single help link (exactly one per window)."""
    labels = dialog.findChildren(QLabel, "helpLink")
    assert len(labels) == 1, f"expected one help link, found {len(labels)}"
    return labels[0]


def _assert_link(dialog, url: str, text_key: str = "help.open_guide") -> None:
    label = _help_link(dialog)
    assert label.property("docsUrl") == url
    assert url in label.text()
    assert tr(text_key) in label.text()
    assert label.accessibleName() == tr(text_key)
    # The same affordance everywhere: the glyph owns a reserved left inset.
    assert label.contentsMargins().left() > 0


def test_the_reset_state_dialog_links_to_its_guide():
    from hsync_desktop.settings.reset_state_dialog import ResetStateDialog

    _assert_link(ResetStateDialog(), docs_links.RESET_SYNC_STATE)


def test_the_ignore_rules_editor_links_to_the_pattern_guide(tmp_path):
    from hsync_desktop.settings.hsyncignore_dialog import HsyncIgnoreEditorDialog

    _assert_link(HsyncIgnoreEditorDialog(tmp_path), docs_links.IGNORE_RULES)


def test_the_bandwidth_dialog_links_to_the_network_section():
    from hsync_desktop.bandwidth_dialog import BandwidthDialog

    _assert_link(BandwidthDialog(), docs_links.BANDWIDTH_LIMITS)


def test_the_compare_summary_links_to_the_compare_guide():
    from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog

    _assert_link(PreviewSummaryDialog(PreviewStats()), docs_links.COMPARE_PREVIEW)


def test_the_api_key_dialog_links_to_the_secrets_guide():
    from hsync_desktop.settings.credential_dialogs import ApiKeyDialog

    _assert_link(ApiKeyDialog(), docs_links.SECRETS)


def test_the_shared_password_dialog_links_to_the_secrets_guide():
    from hsync_desktop.settings.credential_dialogs import P2PKeyDialog

    _assert_link(P2PKeyDialog(), docs_links.SECRETS)


def test_the_group_key_dialog_links_to_the_search_server_password_section():
    from hsync_desktop.settings.credential_dialogs import GroupKeyDialog

    _assert_link(GroupKeyDialog("k" * 32, "my-share"), docs_links.GROUP_KEY)


def test_the_wizard_connection_step_links_to_the_connection_guide():
    from hsync_desktop.wizard.pages.connection import ConnectionPage

    _assert_link(ConnectionPage(), docs_links.SETTINGS_CONNECTION_GUIDE, "help.settings_connection")


class _FakeStore:
    """The two reads ``SharesDialog`` needs to build its list."""

    def shares_sorted(self):
        return []

    def active_id(self) -> str:
        return ""


class _FakeHost:
    _share_store = _FakeStore()


def test_the_shares_dialog_links_to_the_shares_guide():
    from hsync_desktop.shares.dialog import SharesDialog

    _assert_link(SharesDialog(_FakeHost()), docs_links.SHARES)


@pytest.mark.parametrize(
    "url",
    [
        docs_links.TRUST_STORE,
        docs_links.RESET_SYNC_STATE,
        docs_links.IGNORE_RULES,
        docs_links.SECRETS,
        docs_links.GROUP_KEY,
        docs_links.BANDWIDTH_LIMITS,
        docs_links.COMPARE_PREVIEW,
        docs_links.SHARES,
    ],
)
def test_every_context_help_target_is_an_allowlisted_published_page(url):
    """The allowlist is what stops a help link from navigating off-project."""
    assert docs_links.is_allowed_docs_url(url)
    assert url.startswith("https://github.com/albertsdk/hsync-desktop/blob/main/docs/")
