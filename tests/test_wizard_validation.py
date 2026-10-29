# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Wizard validation + derived-default tests."""

from __future__ import annotations

from hsync_desktop.wizard.defaults import (
    default_share_name,
    generate_group_name,
    generate_password,
)
from hsync_desktop.wizard.model import WizardDraft, WizardMode
from hsync_desktop.wizard.validation import (
    STEP_CONNECTION,
    STEP_FOLDER,
    STEP_PURPOSE,
    first_error,
    validate_connection,
    validate_folder,
    validate_purpose,
)


class TestDefaults:
    def test_share_name_from_messy_folder(self):
        assert default_share_name("/home/u/My Documents") == "my-documents"

    def test_share_name_strips_accents(self):
        # Non-ASCII folds to a valid ASCII slug.
        assert default_share_name("/home/u/Caffè") == "caffe"

    def test_share_name_fallback_is_valid(self):
        from hsync_common.path_validation import is_valid_bucket_name

        name = default_share_name("/")
        assert is_valid_bucket_name(name)

    def test_share_name_rejects_leading_dash(self):
        # "..." folds to an empty slug -> random fallback, never a bare "-".
        assert default_share_name("/home/u/...") != "-"

    def test_group_name_is_builtin_safe_and_unique(self):
        first = generate_group_name("/data/My Folder")
        second = generate_group_name("/data/My Folder")
        assert first.startswith("my-folder-")
        assert first != second

    def test_password_length_and_alphabet(self):
        pwd = generate_password()
        assert len(pwd) == 24
        assert not set(pwd) & set("0O1lI")


class TestPurposeValidation:
    def test_requires_mode(self):
        assert validate_purpose(WizardDraft())[0].code == "mode_required"
        assert validate_purpose(WizardDraft(mode=WizardMode.BACKUP)) == []


class TestFolderValidation:
    def test_existing_dir_ok(self, tmp_path):
        draft = WizardDraft(mode=WizardMode.BACKUP, local_path=str(tmp_path))
        assert validate_folder(draft) == []

    def test_missing_dir(self, tmp_path):
        draft = WizardDraft(mode=WizardMode.BACKUP, local_path=str(tmp_path / "nope"))
        issues = validate_folder(draft)
        assert [i.code for i in issues] == ["missing"]
        assert issues[0].level == "error"

    def test_file_not_dir(self, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("x")
        draft = WizardDraft(mode=WizardMode.BACKUP, local_path=str(target))
        assert validate_folder(draft)[0].code == "not_dir"

    def test_root_blocked(self):
        draft = WizardDraft(mode=WizardMode.BACKUP, local_path="/")
        assert validate_folder(draft)[0].code == "root"

    def test_empty(self):
        assert validate_folder(WizardDraft(local_path=""))[0].code == "empty"

    def test_home_is_warning(self):
        import os

        draft = WizardDraft(mode=WizardMode.BACKUP, local_path=os.path.expanduser("~"))
        issues = validate_folder(draft)
        assert issues and issues[0].level == "warning"


class TestConnectionValidation:
    def test_backup_needs_server_key_and_share(self):
        draft = WizardDraft(mode=WizardMode.BACKUP)
        codes = {i.code for i in validate_connection(draft)}
        assert {"server_required", "api_key_required", "share_required"} <= codes

    def test_backup_valid(self):
        draft = WizardDraft(
            mode=WizardMode.BACKUP,
            server_url="host.example.com",
            api_key="k",
            bucket="data",
        )
        assert validate_connection(draft) == []

    def test_backup_rejects_http(self):
        draft = WizardDraft(
            mode=WizardMode.BACKUP,
            server_url="http://host",
            api_key="k",
            bucket="data",
        )
        assert [i.code for i in validate_connection(draft)] == ["server_invalid"]

    def test_remote_requires_rendezvous_server(self):
        draft = WizardDraft(
            mode=WizardMode.REMOTE_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="abcdwxyz12345678",
        )
        assert [i.code for i in validate_connection(draft)] == ["rendezvous_server_required"]

    def test_lan_needs_no_server(self):
        draft = WizardDraft(
            mode=WizardMode.LAN_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="abcdwxyz12345678",
        )
        assert validate_connection(draft) == []

    def test_lan_rejects_a_short_password(self):
        draft = WizardDraft(mode=WizardMode.LAN_SYNC, bucket="data", p2p_group="grp", p2p_key="pw")
        assert [i.code for i in validate_connection(draft)] == ["password_too_short"]

    def test_lan_rejects_a_weak_password(self):
        draft = WizardDraft(
            mode=WizardMode.LAN_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="password1234",
        )
        assert [i.code for i in validate_connection(draft)] == ["password_too_weak"]

    def test_lan_warns_on_a_12_char_password(self):
        draft = WizardDraft(
            mode=WizardMode.LAN_SYNC,
            bucket="data",
            p2p_group="grp",
            p2p_key="abcdwxyz1234",
        )
        issues = validate_connection(draft)
        assert [i.code for i in issues] == ["password_short"]
        assert issues[0].level == "warning"

    def test_team_needs_server(self):
        draft = WizardDraft(mode=WizardMode.TEAM_SHARE, bucket="data")
        codes = {i.code for i in validate_connection(draft)}
        assert "server_required" in codes and "api_key_required" in codes

    def test_first_error_skips_warnings(self):
        import os

        draft = WizardDraft(mode=WizardMode.BACKUP, local_path=os.path.expanduser("~"))
        # home only raises a warning, so the folder step is not blocked
        assert first_error(draft, STEP_FOLDER) is None
        # the connection step has real errors (no server/key/share)
        assert first_error(draft, STEP_CONNECTION) is not None
        # a mode is already selected
        assert first_error(draft, STEP_PURPOSE) is None


class TestSuggestedFolders:
    def test_uses_localized_standard_dirs(self, monkeypatch):
        from PySide6.QtCore import QStandardPaths

        import hsync_desktop.wizard.defaults as defaults

        mapping = {
            QStandardPaths.StandardLocation.HomeLocation: "/home/u",
            QStandardPaths.StandardLocation.DocumentsLocation: "/home/u/Documenti",
            QStandardPaths.StandardLocation.PicturesLocation: "/home/u/Immagini",
            QStandardPaths.StandardLocation.MusicLocation: "/home/u/Musica",
            QStandardPaths.StandardLocation.MoviesLocation: "/home/u/Video",
        }
        monkeypatch.setattr(
            defaults.QStandardPaths,
            "writableLocation",
            staticmethod(lambda location: mapping.get(location, "")),
        )
        folders = dict(defaults.suggested_folders())
        assert folders["wizard.folder.suggest_documents"] == "/home/u/Documenti"
        assert folders["wizard.folder.suggest_pictures"] == "/home/u/Immagini"
        assert folders["wizard.folder.suggest_music"] == "/home/u/Musica"
        assert folders["wizard.folder.suggest_videos"] == "/home/u/Video"
        assert folders["wizard.folder.suggest_home"] == "/home/u/HSYNC"

    def test_unset_standard_dir_is_none(self, monkeypatch):
        from PySide6.QtCore import QStandardPaths

        import hsync_desktop.wizard.defaults as defaults

        monkeypatch.setattr(
            defaults.QStandardPaths,
            "writableLocation",
            staticmethod(lambda location: "" if "Document" in str(location) else "/x"),
        )
        folders = dict(defaults.suggested_folders())
        assert folders["wizard.folder.suggest_documents"] is None


class TestFolderCheckFreeBytes:
    def test_free_bytes_and_mb_agree(self, tmp_path):
        from hsync_desktop.settings.validators import validate_sync_folder

        check = validate_sync_folder(str(tmp_path))
        assert check.free_bytes is not None and check.free_bytes > 0
        assert check.free_mb == check.free_bytes // (1024 * 1024)

    def test_missing_path_has_no_free_space(self, tmp_path):
        from hsync_desktop.settings.validators import validate_sync_folder

        check = validate_sync_folder(str(tmp_path / "nope"))
        assert check.free_bytes is None and check.free_mb is None
