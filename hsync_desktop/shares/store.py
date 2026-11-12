# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Persistence for named shares: the store and its flat-key projection.

The flat ``QSettings`` keys stay the *active projection* (the running config),
so the engine argument builder and every reader are untouched. The store keeps a
list of shares in a single versioned JSON blob and swaps the projection when the
user switches share.

Snapshot points: at startup and right before a switch, so the flat keys remain
the live source of truth and a crash never loses edits. Only the active share is
refreshed from the flat keys; the others are read from the blob.
"""

from __future__ import annotations

import copy
import os
import time
import uuid

from PySide6.QtCore import QSettings

from hsync_desktop.config import DEFAULT_BUCKET, SETTINGS_APP, SETTINGS_ORG
from hsync_desktop.shares.keys import SHARE_KEYS, SHARE_PREFIXES
from hsync_desktop.shares.model import Share, ShareBook
from hsync_desktop.wizard.defaults import default_share_name

BOOK_KEY = "shares/v1"


def _canonical(folder: str) -> str:
    """Case/real-path canonical folder key (``""`` for an empty path)."""
    text = (folder or "").strip()
    if not text:
        return ""
    try:
        return os.path.normcase(os.path.realpath(text))
    except OSError:
        return os.path.normcase(text)


def _is_share_key(key: str) -> bool:
    return key == "output/logfile" or key.startswith(SHARE_PREFIXES)


def sort_key(share: Share) -> str:
    """Display order shared by the selector, the manage dialog and the delete fallback."""
    return (share.name or "").casefold()


class ShareStore:
    """CRUD over the saved shares plus the active-projection swap."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._s = settings if settings is not None else QSettings(SETTINGS_ORG, SETTINGS_APP)

    # ── blob IO ─────────────────────────────────────────────────────────────
    def _read(self) -> ShareBook | None:
        raw = str(self._s.value(BOOK_KEY, "", str))
        if not raw:
            return None
        try:
            return ShareBook.from_json_text(raw)
        except (ValueError, TypeError):
            self._quarantine(raw)
            return None

    def _write(self, book: ShareBook) -> None:
        self._s.setValue(BOOK_KEY, book.to_json_text())
        self._s.sync()

    def _quarantine(self, raw: str) -> None:
        """Move an unreadable blob aside so the next migration can rebuild it."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self._s.setValue(f"{BOOK_KEY}.corrupt-{stamp}", raw)
        self._s.remove(BOOK_KEY)
        self._s.sync()

    def _book(self) -> ShareBook:
        book = self._read() or ShareBook()
        ids = {share.id for share in book.shares}
        if not book.shares:
            book.active = ""
        elif book.active not in ids:
            book.active = book.shares[0].id
        return book

    # ── queries ─────────────────────────────────────────────────────────────
    def shares(self) -> list[Share]:
        return self._book().shares

    def shares_sorted(self) -> list[Share]:
        """The shares in the one order every view shows them (by name)."""
        return sorted(self._book().shares, key=sort_key)

    def has_shares(self) -> bool:
        return bool(self._book().shares)

    def active_id(self) -> str:
        return self._book().active

    def active(self) -> Share | None:
        book = self._book()
        return next((s for s in book.shares if s.id == book.active), None)

    def get(self, share_id: str) -> Share | None:
        return next((s for s in self._book().shares if s.id == share_id), None)

    def name_in_use(self, name: str, *, exclude_id: str | None = None) -> bool:
        target = (name or "").strip().casefold()
        if not target:
            return False
        return any(
            s.id != exclude_id and s.name.strip().casefold() == target for s in self._book().shares
        )

    def folder_in_use(self, folder: str, *, exclude_id: str | None = None) -> Share | None:
        canonical = _canonical(folder)
        if not canonical:
            return None
        for share in self._book().shares:
            if share.id == exclude_id:
                continue
            if _canonical(str(share.values.get("path/local", ""))) == canonical:
                return share
        return None

    # ── snapshot / apply ────────────────────────────────────────────────────
    def _capture(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for key, (default, kind) in SHARE_KEYS.items():
            if self._s.contains(key):
                values[key] = self._s.value(key, default, kind)
        return values

    def snapshot_active(self) -> None:
        """Write the current flat keys into the active share's record."""
        book = self._book()
        share = next((s for s in book.shares if s.id == book.active), None)
        if share is None:
            return
        share.values = self._capture()
        self._write(book)

    def apply(self, share_id: str) -> None:
        """Write *share_id*'s record into the flat keys (the active projection)."""
        book = self._book()
        share = next((s for s in book.shares if s.id == share_id), None)
        if share is None:
            raise KeyError(share_id)
        # Clear every per-share key first so a value the target does not set can
        # never leak from the share that was active.
        for key in SHARE_KEYS:
            self._s.remove(key)
        for key, value in share.values.items():
            if _is_share_key(key):
                self._s.setValue(key, value)
        book.active = share_id
        self._write(book)

    def sync_from_flat(self) -> None:
        """Ensure a share exists for the flat keys and refresh it (Settings/wizard)."""
        self.ensure_first_share()
        self.snapshot_active()

    def enforce_unique_folder(self) -> bool:
        """Revert a flat ``path/local`` owned by another share; True if reverted.

        The Settings dialog blocks the collision up front, but the setup wizard
        writes ``path/local`` directly; re-checking here keeps the
        one-folder-per-share invariant before the record adopts the wizard value.
        """
        book = self._book()
        active = next((s for s in book.shares if s.id == book.active), None)
        if active is None:
            return False
        flat_path = str(self._s.value("path/local", "", str)).strip()
        if self.folder_in_use(flat_path, exclude_id=active.id) is None:
            return False
        self._s.setValue("path/local", str(active.values.get("path/local", "")))
        self._s.sync()
        return True

    # ── migration ───────────────────────────────────────────────────────────
    def _is_configured(self) -> bool:
        return bool(str(self._s.value("path/local", "", str)).strip()) or self._s.contains(
            "sync/bucket"
        )

    def _default_name(self) -> str:
        bucket = str(self._s.value("sync/bucket", "", str)).strip()
        if bucket and bucket != DEFAULT_BUCKET:
            return bucket
        folder = str(self._s.value("path/local", "", str)).strip()
        if folder:
            return default_share_name(folder)
        return bucket or default_share_name("")

    def migrate_if_needed(self) -> None:
        """Turn an existing flat config into share #1; leave a fresh install empty.

        The flat keys are never touched, so every reader behaves as before.
        """
        if self._read() is not None:
            return
        if not self._is_configured():
            return  # fresh install: the first configuration creates the share
        share = Share(id=uuid.uuid4().hex, name=self._default_name(), values=self._capture())
        self._write(ShareBook(active=share.id, shares=[share]))

    def ensure_first_share(self) -> None:
        """Create share #1 from the flat keys when the store is still empty."""
        book = self._book()
        if book.shares or not self._is_configured():
            return
        share = Share(id=uuid.uuid4().hex, name=self._default_name(), values=self._capture())
        book.shares = [share]
        book.active = share.id
        self._write(book)

    # ── CRUD ────────────────────────────────────────────────────────────────
    @staticmethod
    def _bucket_for(name: str, folder: str) -> str:
        return default_share_name(name.strip() or folder or "")

    def create_from_active(self, name: str, folder: str) -> Share:
        """Append a new share copying the active one, with a new name/folder.

        The active share is not changed here: the caller switches explicitly so
        the outgoing share is snapshotted before the projection moves.
        """
        book = self._book()
        source = next((s for s in book.shares if s.id == book.active), None)
        if source is not None:
            # Refresh the active record from the live flat keys first: several
            # paths (direction menu, bandwidth dialog, key re-prompts) write the
            # projection without going through the snapshot points.
            self.snapshot_active()
            book = self._book()
            source = next((s for s in book.shares if s.id == book.active), None)
        values = copy.deepcopy(source.values) if source is not None else self._capture()
        values["path/local"] = folder
        values["sync/bucket"] = self._bucket_for(name, folder)
        share = Share(id=uuid.uuid4().hex, name=name.strip(), values=values)
        book.shares.append(share)
        self._write(book)
        return share

    def duplicate(self, share_id: str, name: str, folder: str) -> Share:
        """Append a copy of *share_id* with a new name/folder (active unchanged)."""
        book = self._book()
        source = next((s for s in book.shares if s.id == share_id), None)
        if source is None:
            raise KeyError(share_id)
        if share_id == book.active:
            self.snapshot_active()
            book = self._book()
            source = next((s for s in book.shares if s.id == share_id), None)
            if source is None:
                raise KeyError(share_id)
        values = copy.deepcopy(source.values)
        values["path/local"] = folder
        values["sync/bucket"] = self._bucket_for(name, folder)
        share = Share(id=uuid.uuid4().hex, name=name.strip(), values=values)
        book.shares.append(share)
        self._write(book)
        return share

    def rename(self, share_id: str, name: str) -> None:
        """Rename the label only; the bucket (the identifier) is untouched."""
        book = self._book()
        share = next((s for s in book.shares if s.id == share_id), None)
        if share is None:
            raise KeyError(share_id)
        share.name = name.strip()
        self._write(book)

    def delete(self, share_id: str, *, next_active: str = "") -> str:
        """Remove a share; returns the new active id (``""`` when none remain).

        *next_active* is the id the caller wants to activate when the removed
        share was the active one — its visible neighbour — so the window lands on
        the row the user is looking at instead of an arbitrary record. The
        caller owns the engine stop and the optional client-state reset; the
        store never touches files.
        """
        book = self._book()
        if len(book.shares) <= 1:
            raise ValueError("cannot delete the last share")
        book.shares = [s for s in book.shares if s.id != share_id]
        if book.active == share_id:
            survivors = {s.id for s in book.shares}
            if next_active in survivors:
                book.active = next_active
            elif book.shares:
                book.active = sorted(book.shares, key=sort_key)[0].id
            else:
                book.active = ""
        self._write(book)
        return book.active
