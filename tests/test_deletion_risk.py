# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The deletion-risk notice: what counts as user content and what an ack covers."""

from __future__ import annotations

import pytest

from hsync_desktop.deletion_risk import (
    _ACK_KEY,
    DELETION_RISK_NOTICE_VERSION,
    REASON_DOWNLOAD_ONLY,
    acknowledge,
    acknowledgement,
    folder_has_user_content,
    forget_acknowledgement,
    is_acknowledged,
)


class TestFolderHasUserContent:
    """Only data a deletion could remove counts: artefacts do not."""

    def test_an_empty_folder_has_none(self, tmp_path):
        assert folder_has_user_content(str(tmp_path)) is False

    def test_a_regular_file_counts(self, tmp_path):
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")

        assert folder_has_user_content(str(tmp_path)) is True

    def test_a_file_in_a_subdirectory_counts(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "report.txt").write_text("x", encoding="utf-8")

        assert folder_has_user_content(str(tmp_path)) is True

    def test_the_entries_the_engine_ignores_do_not_count(self, tmp_path):
        (tmp_path / ".hsynckeep").write_text("", encoding="utf-8")
        (tmp_path / ".hsyncignore").write_text("", encoding="utf-8")
        (tmp_path / "Thumbs.db").write_text("x", encoding="utf-8")
        (tmp_path / "draft.tmp").write_text("x", encoding="utf-8")

        assert folder_has_user_content(str(tmp_path)) is False

    def test_a_dotfile_counts_because_it_is_synchronised(self, tmp_path):
        (tmp_path / ".env").write_text("x", encoding="utf-8")

        assert folder_has_user_content(str(tmp_path)) is True

    def test_a_missing_folder_has_none(self, tmp_path):
        assert folder_has_user_content(str(tmp_path / "absent")) is False


class TestAcknowledgement:
    """An acknowledgement covers one folder and the posture it was given for."""

    def test_a_fresh_store_has_none(self, settings, tmp_path):
        assert is_acknowledged(settings, str(tmp_path), REASON_DOWNLOAD_ONLY) is False
        assert not settings.contains(_ACK_KEY)

    def test_acknowledging_covers_that_folder_and_posture(self, settings, tmp_path):
        acknowledge(settings, str(tmp_path), REASON_DOWNLOAD_ONLY)

        assert is_acknowledged(settings, str(tmp_path), REASON_DOWNLOAD_ONLY) is True

    def test_another_folder_is_not_covered(self, settings, tmp_path):
        acknowledge(settings, str(tmp_path / "a"), REASON_DOWNLOAD_ONLY)

        assert is_acknowledged(settings, str(tmp_path / "b"), REASON_DOWNLOAD_ONLY) is False

    def test_a_relative_and_an_absolute_path_name_the_same_folder(
        self, settings, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        acknowledge(settings, "share", REASON_DOWNLOAD_ONLY)

        assert is_acknowledged(settings, str(tmp_path / "share"), REASON_DOWNLOAD_ONLY) is True

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("p2p/enabled", False),
            ("p2p/prefer_master", True),
            ("sync/direction", "download-only"),
            ("sync/deletion_policy", "keep"),
        ],
    )
    def test_a_changed_setting_is_not_covered(self, settings, tmp_path, key, value):
        acknowledge(settings, str(tmp_path), REASON_DOWNLOAD_ONLY)
        settings.setValue(key, value)

        assert is_acknowledged(settings, str(tmp_path), REASON_DOWNLOAD_ONLY) is False

    def test_a_different_reason_is_not_covered(self, settings, tmp_path):
        acknowledge(settings, str(tmp_path), REASON_DOWNLOAD_ONLY)

        assert is_acknowledged(settings, str(tmp_path), "something-else") is False

    def test_the_value_states_the_notice_version_and_the_reason(self, settings, tmp_path):
        assert acknowledgement(settings, str(tmp_path), REASON_DOWNLOAD_ONLY).startswith(
            f"{DELETION_RISK_NOTICE_VERSION}|{REASON_DOWNLOAD_ONLY}|"
        )

    def test_forgetting_brings_the_notice_back(self, settings, tmp_path):
        acknowledge(settings, str(tmp_path), REASON_DOWNLOAD_ONLY)
        forget_acknowledgement(settings)

        assert is_acknowledged(settings, str(tmp_path), REASON_DOWNLOAD_ONLY) is False
        assert not settings.contains(_ACK_KEY)
