# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Unit tests for the share store (persistence, migration, projection)."""

from __future__ import annotations

import pytest

from hsync_desktop.shares import BOOK_KEY, ShareStore
from hsync_desktop.shares.model import SCHEMA_VERSION, ShareBook
from tests._helpers import _settings


def _configured(tmp_path):
    s = _settings(tmp_path)
    s.setValue("path/local", str(tmp_path / "Team"))
    s.setValue("sync/bucket", "team")
    return s


def _store_with_one_share(tmp_path):
    s = _configured(tmp_path)
    store = ShareStore(s)
    store.migrate_if_needed()
    return s, store


class TestMigration:
    def test_migration_records_the_existing_config(self, tmp_path):
        s = _configured(tmp_path)
        s.setValue("sync/continuous", False)
        store = ShareStore(s)

        store.migrate_if_needed()

        shares = store.shares()
        assert len(shares) == 1
        assert shares[0].name == "team"
        assert shares[0].values["path/local"] == str(tmp_path / "Team")
        assert shares[0].values["sync/continuous"] is False
        # The flat keys (the live projection) are never touched.
        assert s.value("path/local") == str(tmp_path / "Team")
        assert s.value("sync/bucket") == "team"

    def test_fresh_install_stays_empty_until_configured(self, tmp_path):
        s = _settings(tmp_path)
        store = ShareStore(s)

        store.migrate_if_needed()
        assert not store.has_shares()

        s.setValue("path/local", str(tmp_path / "Team"))
        s.setValue("sync/bucket", "team")
        store.sync_from_flat()
        assert len(store.shares()) == 1

    def test_migration_names_from_the_folder_when_bucket_is_default(self, tmp_path):
        s = _settings(tmp_path)
        s.setValue("path/local", str(tmp_path / "Team Photos"))
        store = ShareStore(s)

        store.migrate_if_needed()

        assert store.shares()[0].name == "team-photos"

    def test_a_corrupt_blob_is_quarantined_and_migration_reruns(self, tmp_path):
        s = _configured(tmp_path)
        s.setValue(BOOK_KEY, "{not json")
        store = ShareStore(s)

        store.migrate_if_needed()

        assert len(store.shares()) == 1
        assert [k for k in s.allKeys() if k.startswith(f"{BOOK_KEY}.corrupt-")]

    def test_an_unknown_version_is_treated_as_corrupt(self, tmp_path):
        s = _configured(tmp_path)
        s.setValue(BOOK_KEY, ShareBook(version=SCHEMA_VERSION + 1).to_json_text())
        store = ShareStore(s)

        assert store.shares() == []
        assert [k for k in s.allKeys() if k.startswith(f"{BOOK_KEY}.corrupt-")]


class TestCaptureAndApply:
    def test_snapshot_keeps_types(self, tmp_path):
        s = _configured(tmp_path)
        s.setValue("sync/continuous", False)
        s.setValue("sync/resync", 42)
        store = ShareStore(s)
        store.migrate_if_needed()

        values = store.active().values
        assert values["sync/continuous"] is False
        assert values["sync/resync"] == 42
        assert values["p2p/enabled"] is True

    def test_apply_removes_a_key_the_target_does_not_set(self, tmp_path):
        s, store = _store_with_one_share(tmp_path)
        s.setValue("sync/filter_path", "sub")  # present only in the live keys

        store.apply(store.active_id())

        assert not s.contains("sync/filter_path")

    def test_apply_writes_the_target_values(self, tmp_path):
        s = _configured(tmp_path)
        store = ShareStore(s)
        store.migrate_if_needed()
        second = store.create_from_active("Other", str(tmp_path / "Other"))

        store.apply(store.shares()[0].id)

        assert s.value("path/local") == str(tmp_path / "Team")
        assert store.active_id() == store.shares()[0].id
        assert store.get(second.id) is not None


class TestCrud:
    def test_rename_keeps_the_bucket(self, tmp_path):
        _, store = _store_with_one_share(tmp_path)
        share = store.active()

        store.rename(share.id, "Renamed")

        renamed = store.get(share.id)
        assert renamed.name == "Renamed"
        assert renamed.values["sync/bucket"] == "team"

    def test_create_seeds_the_sanitized_bucket_and_folder(self, tmp_path):
        _, store = _store_with_one_share(tmp_path)
        first = store.active()

        share = store.create_from_active("Backup casa", str(tmp_path / "Backup"))

        assert share.name == "Backup casa"
        assert share.values["sync/bucket"] == "backup-casa"
        assert share.values["path/local"] == str(tmp_path / "Backup")
        # The active share is unchanged: the caller switches explicitly.
        assert store.active_id() == first.id

    def test_name_and_folder_uniqueness(self, tmp_path):
        _, store = _store_with_one_share(tmp_path)
        first = store.active()

        assert store.name_in_use("team")
        assert not store.name_in_use("team", exclude_id=first.id)
        found = store.folder_in_use(str(tmp_path / "Team"))
        assert found is not None and found.id == first.id
        assert store.folder_in_use(str(tmp_path / "Team"), exclude_id=first.id) is None

    def test_secrets_are_copied_verbatim(self, tmp_path):
        s, store = _store_with_one_share(tmp_path)
        store.snapshot_active()
        s.setValue("connection/api_key", "enc:secret")
        store.snapshot_active()

        copied = store.create_from_active("B", str(tmp_path / "B"))

        assert copied.values["connection/api_key"] == "enc:secret"

    def test_delete_refuses_the_last_share(self, tmp_path):
        _, store = _store_with_one_share(tmp_path)

        with pytest.raises(ValueError):
            store.delete(store.active_id())

    def test_deleting_the_active_share_selects_the_first_remaining(self, tmp_path):
        _, store = _store_with_one_share(tmp_path)
        first = store.active()
        second = store.create_from_active("B", str(tmp_path / "B"))

        new_active = store.delete(second.id)

        assert new_active == first.id
        assert store.active_id() == first.id
        assert store.get(second.id) is None


class TestModel:
    def test_share_book_round_trip(self):
        text = ShareBook(active="x", shares=[]).to_json_text()
        book = ShareBook.from_json_text(text)
        assert book.version == SCHEMA_VERSION
        assert book.active == "x"

    def test_unsupported_version_raises(self):
        with pytest.raises(ValueError):
            ShareBook.from_json_text('{"version": 999, "active": "", "shares": []}')
