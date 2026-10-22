# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.file_panel module."""

from time import time

import pytest
from hsync_common.format import format_bytes as _format_size
from hsync_common.format import format_duration
from hsync_common.ignore import IgnoreMatcher

from hsync_desktop.file_panel import (
    _FILE_TYPE_MAP,
    _NO_PROGRESS_STATUSES,
    STATUS_COLORS,
    STATUS_COLORS_DARK,
    FileTransfer,
    TransferStatus,
    _classify_file,
)


def _format_eta(seconds):
    """Adapter: file panel ETA uses the compact duration style."""
    return format_duration(seconds, style="compact")


class TestTransferStatus:
    """Test TransferStatus enum."""

    def test_all_status_values_exist(self):
        """All expected status values should exist."""
        assert TransferStatus.LOCAL.value == "local"
        assert TransferStatus.SYNCED.value == "synced"
        assert TransferStatus.TO_DOWNLOAD.value == "to_download"
        assert TransferStatus.TO_UPLOAD.value == "to_upload"
        assert TransferStatus.TO_DELETE.value == "to_delete"
        assert TransferStatus.DOWNLOADING.value == "downloading"
        assert TransferStatus.UPLOADING.value == "uploading"
        assert TransferStatus.TO_RENAME.value == "to_rename"
        assert TransferStatus.DELETED.value == "deleted"
        assert TransferStatus.QUEUED.value == "queued"
        assert TransferStatus.TRANSFERRING.value == "transferring"
        assert TransferStatus.COMPLETED.value == "completed"
        assert TransferStatus.ERROR.value == "error"


class TestFileTransfer:
    """Test FileTransfer dataclass."""

    def test_create_transfer(self):
        """Test creating a FileTransfer."""
        transfer = FileTransfer(
            filepath="test.txt",
            direction="↓",
            size=1024,
            bytes_transferred=512,
        )
        assert transfer.filepath == "test.txt"
        assert transfer.direction == "↓"
        assert transfer.size == 1024
        assert transfer.bytes_transferred == 512
        assert transfer.status == TransferStatus.QUEUED  # default

    def test_filename_property(self):
        """Test filename property."""
        transfer = FileTransfer(filepath="path/to/file.txt", direction="↓")
        assert transfer.filename == "file.txt"

    def test_filename_property_no_extension(self):
        """Test filename property with no extension."""
        transfer = FileTransfer(filepath="path/to/README", direction="↓")
        assert transfer.filename == "README"

    def test_path_property(self):
        """Test path property (parent directory)."""
        transfer = FileTransfer(filepath="path/to/file.txt", direction="↓")
        assert transfer.path == "path/to"

    def test_path_property_root_file(self):
        """Test path property for file at root."""
        transfer = FileTransfer(filepath="file.txt", direction="↓")
        assert transfer.path == ""

    def test_remaining_property(self):
        """Test remaining bytes calculation."""
        transfer = FileTransfer(
            filepath="test.txt",
            direction="↓",
            size=1000,
            bytes_transferred=300,
        )
        assert transfer.remaining == 700

    def test_remaining_property_complete(self):
        """Test remaining when complete."""
        transfer = FileTransfer(
            filepath="test.txt",
            direction="↓",
            size=1000,
            bytes_transferred=1000,
        )
        assert transfer.remaining == 0

    def test_eta_seconds_active_download(self):
        """ETA follows the sampled rate while a download is in progress."""
        transfer = FileTransfer(filepath="test.txt", direction="↓", size=1000)
        transfer.start_transfer("↓", now=100.0)
        transfer.note_progress(0, now=100.0)
        transfer.note_progress(50, now=110.0)  # 50 B over 10 s → 5 B/s

        eta = transfer.eta_seconds
        assert eta is not None
        assert 150 <= eta <= 250  # 950 B left at 5 B/s

    def test_eta_seconds_none_when_inactive_or_no_progress(self):
        """ETA is None for a non-active status or before any progress."""
        queued = FileTransfer(
            filepath="test.txt",
            direction="↓",
            size=1000,
            bytes_transferred=500,
            status=TransferStatus.QUEUED,
        )
        assert queued.eta_seconds is None
        uploading = FileTransfer(
            filepath="test.txt",
            direction="↑",
            size=1000,
            status=TransferStatus.UPLOADING,
        )
        assert uploading.eta_seconds is None


class TestFormatSize:
    """Test _format_size function."""

    def test_bytes(self):
        """Test bytes formatting."""
        assert _format_size(0) == "0B"
        assert _format_size(100) == "100B"
        assert _format_size(512) == "512B"

    def test_kilobytes(self):
        """Test kilobytes formatting."""
        assert _format_size(1024) == "1.0KB"
        assert _format_size(1536) == "1.5KB"
        assert _format_size(10240) == "10.0KB"

    def test_megabytes(self):
        """Test megabytes formatting."""
        assert _format_size(1048576) == "1.0MB"
        assert _format_size(1572864) == "1.5MB"

    def test_gigabytes(self):
        """Test gigabytes formatting."""
        assert _format_size(1073741824) == "1.0GB"

    def test_terabytes(self):
        """Test terabytes formatting."""
        assert _format_size(1099511627776) == "1.0TB"


class TestFormatEta:
    """Test _format_eta function."""

    def test_none_input(self):
        """Test None input returns empty string."""
        assert _format_eta(None) == ""

    def test_seconds_only(self):
        """Test seconds only."""
        assert _format_eta(30) == "30s"
        assert _format_eta(59) == "59s"

    def test_minutes_and_seconds(self):
        """Test minutes and seconds."""
        assert _format_eta(60) == "1m 0s"
        assert _format_eta(90) == "1m 30s"
        assert _format_eta(125) == "2m 5s"

    def test_hours_and_minutes(self):
        """Test hours and minutes."""
        assert _format_eta(3600) == "1h 0m"
        assert _format_eta(3660) == "1h 1m"
        assert _format_eta(7200) == "2h 0m"


class TestClassifyFile:
    """Test _classify_file function."""

    def test_image_files(self):
        """Test image file classification."""
        icon, key = _classify_file("photo.jpg")
        assert icon == "image-x-generic"
        assert key == "ftype.image"

        icon, key = _classify_file("photo.png")
        assert icon == "image-x-generic"

        icon, key = _classify_file("photo.jpeg")
        assert icon == "image-x-generic"

    def test_audio_files(self):
        """Test audio file classification."""
        icon, key = _classify_file("song.mp3")
        assert icon == "audio-x-generic"
        assert key == "ftype.audio"

    def test_video_files(self):
        """Test video file classification."""
        icon, key = _classify_file("video.mp4")
        assert icon == "video-x-generic"
        assert key == "ftype.video"

    def test_document_files(self):
        """Test document file classification."""
        icon, key = _classify_file("doc.pdf")
        assert icon == "x-office-document"
        assert key == "ftype.document"

    def test_spreadsheet_files(self):
        """Test spreadsheet file classification."""
        icon, key = _classify_file("data.xlsx")
        assert icon == "x-office-spreadsheet"
        assert key == "ftype.spreadsheet"

    def test_presentation_files(self):
        """Test presentation file classification."""
        icon, key = _classify_file("presentation.pptx")
        assert icon == "x-office-presentation"
        assert key == "ftype.presentation"

    def test_archive_files(self):
        """Test archive file classification."""
        icon, key = _classify_file("archive.zip")
        assert icon == "package-x-generic"
        assert key == "ftype.archive"

    def test_code_files(self):
        """Test code file classification."""
        icon, key = _classify_file("script.py")
        assert icon == "text-x-script"
        assert key == "ftype.code"

        icon, key = _classify_file("app.js")
        assert icon == "text-x-script"

    def test_executable_files(self):
        """Test executable file classification."""
        icon, key = _classify_file("program.exe")
        assert icon == "application-x-executable"
        assert key == "ftype.executable"

    def test_certificate_files(self):
        """Test certificate/key file classification."""
        icon, key = _classify_file("key.pem")
        assert icon == "application-certificate"
        assert key == "ftype.key"

    def test_font_files(self):
        """Test font file classification."""
        icon, key = _classify_file("font.ttf")
        assert icon == "font-x-generic"
        assert key == "ftype.font"

    def test_directory(self):
        """Test directory classification."""
        icon, key = _classify_file("folder/")
        assert icon == "folder"
        assert key == "ftype.folder"

    def test_unknown_extension(self):
        """Test unknown extension defaults to generic."""
        icon, key = _classify_file("file.xyz123")
        assert icon == "text-x-generic"
        assert key == "ftype.other"

    def test_no_extension(self):
        """Test file without extension."""
        icon, key = _classify_file("Makefile")
        assert icon == "text-x-generic"


class TestStatusColors:
    """Test STATUS_COLORS dictionary."""

    def test_all_statuses_have_colors(self):
        """All transfer statuses should have colors defined."""
        for status in TransferStatus:
            assert status in STATUS_COLORS, f"Missing color for {status}"

    def test_colors_are_qcolor(self):
        """All status colors should be QColor objects."""
        from PySide6.QtGui import QColor

        for _status, color in STATUS_COLORS.items():
            assert isinstance(color, QColor)

    def test_dark_palette_covers_the_same_statuses(self):
        """The dark-theme palette defines exactly the light-theme statuses."""
        from hsync_desktop.file_panel import STATUS_COLORS_DARK

        assert set(STATUS_COLORS_DARK) == set(STATUS_COLORS)


class TestNoProgressStatuses:
    """Test _NO_PROGRESS_STATUSES set."""

    def test_is_set(self):
        """Should be a set."""
        assert isinstance(_NO_PROGRESS_STATUSES, set)

    def test_contains_expected_statuses(self):
        """Should contain statuses that don't show progress."""
        assert TransferStatus.LOCAL in _NO_PROGRESS_STATUSES
        assert TransferStatus.SYNCED in _NO_PROGRESS_STATUSES
        assert TransferStatus.TO_DELETE in _NO_PROGRESS_STATUSES
        assert TransferStatus.TO_RENAME in _NO_PROGRESS_STATUSES
        assert TransferStatus.DELETED in _NO_PROGRESS_STATUSES
        assert TransferStatus.ERROR in _NO_PROGRESS_STATUSES


class TestFileTypeMap:
    """Test _FILE_TYPE_MAP dictionary."""

    def test_map_not_empty(self):
        """Map should contain entries."""
        assert len(_FILE_TYPE_MAP) > 0

    def test_extensions_lowercase(self):
        """All extensions in map should be lowercase."""
        for ext in _FILE_TYPE_MAP.keys():
            assert ext == ext.lower(), f"Extension {ext} is not lowercase"

    def test_values_are_tuples(self):
        """All values should be tuples of (icon_name, translation_key)."""
        for ext, value in _FILE_TYPE_MAP.items():
            assert isinstance(value, tuple), f"Value for {ext} is not a tuple"
            assert len(value) == 2, f"Value for {ext} is not a pair"
            assert isinstance(value[0], str), f"Icon name for {ext} is not a string"
            assert isinstance(value[1], str), f"Translation key for {ext} is not a string"


class TestFileContextMenu:
    """Right-click actions: ``Open`` navigates into folders (instead of launching
    the OS file manager); a containing-folder entry reveals the entry."""

    @staticmethod
    def _entry(filepath: str) -> FileTransfer:
        return FileTransfer(filepath=filepath, direction="—", size=0, status=TransferStatus.LOCAL)

    @staticmethod
    def _table(qtbot, monkeypatch, opened):
        from hsync_desktop.file_panel import transfer_table as tt

        class _FakeQDS:
            @staticmethod
            def openUrl(url):
                opened.append(url.toLocalFile())
                return True

        monkeypatch.setattr(tt, "QDesktopServices", _FakeQDS)
        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        return table

    def test_open_folder_navigates_into_it(self, qtbot, monkeypatch):
        opened: list[str] = []
        table = self._table(qtbot, monkeypatch, opened)
        navigated: list[str] = []
        monkeypatch.setattr(table, "navigate_to", lambda path: navigated.append(path))

        table._ctx_open(self._entry("sub/"))

        assert navigated == ["sub/"]
        assert opened == []

    def test_open_file_uses_the_default_app(self, qtbot, monkeypatch):
        opened: list[str] = []
        table = self._table(qtbot, monkeypatch, opened)

        table._ctx_open(self._entry("sub/f.txt"))

        assert opened == ["/base/sub/f.txt"]

    def test_open_containing_reveals_the_parent_directory(self, qtbot, monkeypatch):
        opened: list[str] = []
        table = self._table(qtbot, monkeypatch, opened)

        table._ctx_open_containing(self._entry("sub/"))
        table._ctx_open_containing(self._entry("sub/f.txt"))

        assert opened == ["/base", "/base/sub"]


class TestColumnHeaderRetranslation:
    """Column headers follow the language: they are re-applied on change."""

    def test_retranslate_reapplies_localized_headers(self, qtbot, monkeypatch):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        monkeypatch.setattr(tt, "tr", lambda key: f"IT:{key}")

        table.retranslate()

        expected = [f"IT:{key}" if key else "" for key in tt._COLUMN_KEYS]
        actual = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        assert actual == expected


class TestRenameKeepsTheMtime:
    """Renaming a row must not drop its modification date."""

    @staticmethod
    def _table_with(qtbot, filepath: str, mtime: float):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.add_transfer(
            FileTransfer(
                filepath=filepath,
                direction="⇄",
                size=10,
                status=TransferStatus.SYNCED,
                mtime=mtime,
            )
        )
        return table

    def test_keeps_the_previous_mtime_when_the_read_is_empty(self, qtbot):
        table = self._table_with(qtbot, "old.txt", 1234.0)

        table.rename_file("old.txt", "new.txt", mtime=0.0)

        assert "old.txt" not in table._transfers
        assert table._transfers["new.txt"].mtime == 1234.0

    def test_uses_the_provided_mtime_when_given(self, qtbot):
        table = self._table_with(qtbot, "old.txt", 1.0)

        table.rename_file("old.txt", "new.txt", mtime=999.0)

        assert table._transfers["new.txt"].mtime == 999.0

    def test_the_renamed_row_is_synced(self, qtbot):
        """A rename is a synced path, not a fresh local file."""
        table = self._table_with(qtbot, "old.txt", 1.0)

        table.rename_file("old.txt", "new.txt", mtime=1.0)

        assert table._transfers["new.txt"].status is TransferStatus.SYNCED


class TestLocalRowColour:
    """A "Local" row is grey only while a connection can compare it."""

    @staticmethod
    def _table_with_local(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.add_transfer(
            FileTransfer(
                filepath="a.txt",
                direction="—",
                size=1,
                status=TransferStatus.LOCAL,
            )
        )
        table.refresh_view()
        return table

    def test_idle_uses_the_default_text_colour(self, qtbot):
        from PySide6.QtGui import QPalette

        table = self._table_with_local(qtbot)

        colour = table.item(0, 0).foreground().color()

        assert colour == table.palette().color(QPalette.ColorRole.Text)

    def test_connected_uses_the_local_grey(self, qtbot):
        table = self._table_with_local(qtbot)

        table.set_connected(True)

        colour = table.item(0, 0).foreground().color()
        assert colour in (
            STATUS_COLORS[TransferStatus.LOCAL],
            STATUS_COLORS_DARK[TransferStatus.LOCAL],
        )

    def test_disconnecting_restores_the_default_colour(self, qtbot):
        from PySide6.QtGui import QPalette

        table = self._table_with_local(qtbot)
        table.set_connected(True)

        table.set_connected(False)

        colour = table.item(0, 0).foreground().color()
        assert colour == table.palette().color(QPalette.ColorRole.Text)


class TestRestoredView:
    """A scoped Send/Receive reload keeps the user's folder and row."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        for filepath in ("sub/a.txt", "sub/b.txt", "top.txt"):
            table.add_transfer(
                FileTransfer(
                    filepath=filepath,
                    direction="—",
                    size=1,
                    status=TransferStatus.LOCAL,
                )
            )
        return table

    def test_restore_reopens_the_folder_and_selects_the_row(self, qtbot):
        table = self._table(qtbot)

        table.restore_view("sub", "b.txt")

        assert table.current_path == "sub"
        assert table._last_selected_row == table._row_index["b.txt"]

    def test_the_selection_survives_status_refreshes(self, qtbot):
        table = self._table(qtbot)
        table.restore_view("sub", "b.txt")

        table.refresh_view()

        assert table._last_selected_row == table._row_index["b.txt"]

    def test_a_row_that_appears_later_is_selected(self, qtbot):
        table = self._table(qtbot)
        table.restore_view("sub", "later.txt")

        table.add_transfer(
            FileTransfer(
                filepath="sub/later.txt",
                direction="—",
                size=1,
                status=TransferStatus.LOCAL,
            )
        )

        assert table._last_selected_row == table._row_index["later.txt"]

    def test_user_navigation_clears_the_restored_selection(self, qtbot):
        table = self._table(qtbot)
        table.restore_view("sub", "b.txt")

        table.navigate_to("")
        table.refresh_view()

        assert table._last_selected_row == -1


class TestNavigationDuringSync:
    """Folders stay navigable while an active sync rebuilds the table."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        for filepath in ("sub/a.txt", "sub/b.txt", "top.txt"):
            table.add_transfer(
                FileTransfer(
                    filepath=filepath,
                    direction="—",
                    size=1,
                    status=TransferStatus.LOCAL,
                )
            )
        table.refresh_view()
        return table

    def test_enter_opens_the_selected_folder(self, qtbot):
        from PySide6.QtCore import Qt

        table = self._table(qtbot)
        table.setCurrentCell(table._row_index["sub"], 0)

        qtbot.keyClick(table, Qt.Key.Key_Return)

        assert table.current_path == "sub"

    def test_a_pending_click_defers_the_rebuild(self, qtbot):
        """A rebuild between the two clicks of a double-click would break it."""
        table = self._table(qtbot)
        table._click_timer.start()
        table._refresh_pending = True

        table._do_refresh_view()

        assert table._refresh_pending is True

        table._click_timer.stop()
        table._do_refresh_view()
        assert table._refresh_pending is False


class TestTableTypography:
    """The dense file table uses the smaller, still-accessible table font."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        return table

    def test_the_table_uses_the_table_font(self, qtbot, monkeypatch):
        from hsync_desktop import fonts

        probe = fonts.ui_font()
        probe.setPointSizeF(12.0)
        monkeypatch.setattr(fonts, "_ui_font", probe)

        table = self._table(qtbot)

        assert table.font().pointSizeF() == pytest.approx(11.0)
        assert table.horizontalHeader().font().pointSizeF() == pytest.approx(11.0)

    def test_rows_keep_a_comfortable_height(self, qtbot):
        from hsync_desktop.fonts import _MIN_TABLE_ROW_HEIGHT

        table = self._table(qtbot)

        assert table.verticalHeader().defaultSectionSize() >= _MIN_TABLE_ROW_HEIGHT


class TestOptionalColumns:
    """Speed is hidden by default; Direction is visible by default."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        return table

    def test_speed_starts_hidden_and_direction_is_visible(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)
        table = self._table(qtbot)
        header = table.horizontalHeader()

        assert header.isSectionHidden(tt.COL_SPEED)
        assert not header.isSectionHidden(tt.COL_DIRECTION)
        for col in (tt.COL_NAME, tt.COL_SIZE, tt.COL_MODIFIED, tt.COL_STATUS):
            assert not header.isSectionHidden(col)

    def test_headers_include_the_optional_columns(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)

        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        assert len(headers) == len(tt._COLUMN_KEYS)
        assert "Speed" in headers
        assert "Direction" in headers

    def test_a_downloading_row_reports_direction_and_speed(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        transfer = FileTransfer(filepath="a.bin", direction="↓", size=4096)
        transfer.start_transfer("↓", now=100.0)
        transfer.note_progress(0, now=100.0)
        transfer.note_progress(2048, now=101.0)
        table.add_transfer(transfer)

        assert table.item(0, tt.COL_DIRECTION).text() == "↓"
        assert table.item(0, tt.COL_SPEED).text().endswith("/s")

    def test_a_completed_row_has_no_speed(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="a.bin", direction="↓", size=10, status=TransferStatus.COMPLETED)
        )

        assert table.item(0, tt.COL_SPEED).text() == ""

    def test_folder_tooltip_lists_the_planned_operations(self, qtbot):
        """A folder aggregates mixed actions: its tooltip spells them out."""
        from hsync_desktop.file_panel import transfer_table as tt
        from hsync_desktop.i18n import tr

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(
                filepath="dir/a.bin", direction="↑", size=10, status=TransferStatus.TO_UPLOAD
            )
        )
        table.add_transfer(
            FileTransfer(
                filepath="dir/b.bin", direction="↓", size=10, status=TransferStatus.TO_DOWNLOAD
            )
        )
        table.add_transfer(
            FileTransfer(
                filepath="dir/c.bin", direction="↑", size=10, status=TransferStatus.TO_UPLOAD
            )
        )
        table.refresh_view()

        tooltip = table.item(0, tt.COL_NAME).toolTip()
        assert f"{tr('detail.to_upload')}: 2" in tooltip
        assert f"{tr('detail.to_download')}: 1" in tooltip

    def test_folder_shows_the_aggregate_speed_of_its_children(self, qtbot):
        """The Speed column aggregates the in-flight children's rates."""
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        for name, transferred in (("dir/a.bin", 1_000), ("dir/b.bin", 2_000)):
            transfer = FileTransfer(filepath=name, direction="↑", size=10_000)
            transfer.start_transfer("↑", now=0.0)
            transfer.note_progress(0, now=0.0)
            transfer.note_progress(transferred, now=1.0)
            table.add_transfer(transfer)
        table.refresh_view()

        assert table._cached_items is not None
        folder = next(fd for name, _transfer, fd in table._cached_items if name == "dir")
        assert folder["speed"] == pytest.approx(3_000)
        assert table.item(0, tt.COL_SPEED).text().endswith("/s")

    def test_visibility_is_persisted(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)

        table = self._table(qtbot)
        table._toggle_column(tt.COL_SPEED, True)  # show Speed

        assert not table.horizontalHeader().isSectionHidden(tt.COL_SPEED)
        fresh = self._table(qtbot)
        assert not fresh.horizontalHeader().isSectionHidden(tt.COL_SPEED)
        assert not fresh.horizontalHeader().isSectionHidden(tt.COL_DIRECTION)

    def test_showing_both_optional_columns_is_persisted(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)

        table = self._table(qtbot)
        table._toggle_column(tt.COL_SPEED, True)
        table._toggle_column(tt.COL_DIRECTION, True)

        fresh = self._table(qtbot)
        assert not fresh.horizontalHeader().isSectionHidden(tt.COL_SPEED)
        assert not fresh.horizontalHeader().isSectionHidden(tt.COL_DIRECTION)

    def test_restored_selection_is_correct_under_a_column_sort(self, qtbot):
        from PySide6.QtCore import Qt

        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        table.add_transfer(
            FileTransfer(filepath="a.txt", direction="—", size=1, status=TransferStatus.LOCAL)
        )
        table.add_transfer(
            FileTransfer(filepath="m.txt", direction="—", size=99, status=TransferStatus.LOCAL)
        )
        table.sortItems(tt.COL_SIZE, Qt.SortOrder.DescendingOrder)

        table.restore_view("", "a.txt")

        assert table._last_selected_row >= 0
        assert table.item(table._last_selected_row, tt.COL_NAME).text() == "a.txt"


class TestDirectionColumn:
    """Direction is empty at rest and its operative glyphs are bold."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        return table

    def test_a_resting_file_has_no_direction_text(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="idle.bin", direction="—", size=10, status=TransferStatus.LOCAL)
        )

        assert table.item(0, tt.COL_DIRECTION).text() == ""

    def test_a_planned_operation_is_shown_in_bold(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="up.bin", direction="↑", size=10, status=TransferStatus.TO_UPLOAD)
        )

        item = table.item(0, tt.COL_DIRECTION)
        assert item.text() == "↑"
        assert item.font().bold()

    def test_a_folder_has_no_direction(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(
                filepath="dir/a.bin", direction="↑", size=10, status=TransferStatus.TO_UPLOAD
            )
        )

        assert table.item(0, tt.COL_DIRECTION).text() == ""


class TestColumnResizing:
    """Data columns are user-resizable and their widths are persisted."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        return table

    def test_data_columns_are_interactive(self, qtbot):
        from PySide6.QtWidgets import QHeaderView

        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        header = table.horizontalHeader()

        for col in (
            tt.COL_SIZE,
            tt.COL_TYPE,
            tt.COL_MODIFIED,
            tt.COL_PROGRESS,
            tt.COL_ETA,
            tt.COL_STATUS,
            tt.COL_SPEED,
            tt.COL_DIRECTION,
        ):
            assert header.sectionResizeMode(col) is QHeaderView.ResizeMode.Interactive
        assert header.sectionResizeMode(tt.COL_NAME) is QHeaderView.ResizeMode.Stretch
        assert header.sectionResizeMode(tt.COL_ICON) is QHeaderView.ResizeMode.Fixed
        assert header.minimumSectionSize() == tt._MIN_SECTION_WIDTH

    def test_a_user_width_is_persisted_and_restored(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)

        table = self._table(qtbot)
        table.horizontalHeader().resizeSection(tt.COL_SIZE, 222)  # triggers save

        fresh = self._table(qtbot)
        assert fresh.horizontalHeader().sectionSize(tt.COL_SIZE) == 222

    def test_reset_columns_clears_the_saved_widths(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)

        table = self._table(qtbot)
        table.horizontalHeader().resizeSection(tt.COL_SIZE, 222)
        assert store.value(table._COLUMN_WIDTH_SETTINGS_KEY)

        table._reset_columns()

        assert not store.value(table._COLUMN_WIDTH_SETTINGS_KEY)

    def test_setup_does_not_persist_widths(self, qtbot, tmp_path, monkeypatch):
        """Constructing the table must not save unfitted widths."""
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)

        table = self._table(qtbot)

        assert not store.value(table._COLUMN_WIDTH_SETTINGS_KEY)
        assert not table._columns_sized

    def test_columns_are_fitted_once_from_the_content(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)

        table = self._table(qtbot)
        assert not table._columns_sized
        table.add_transfer(
            FileTransfer(filepath="a.bin", direction="—", size=10, status=TransferStatus.LOCAL)
        )

        assert table._columns_sized
        header = table.horizontalHeader()
        assert header.sectionSize(tt.COL_SIZE) >= tt._MIN_COLUMN_WIDTH
        # The fitted pass touches only data columns.
        assert header.sectionSize(tt.COL_ICON) == 32
        assert header.sectionSize(tt.COL_PROGRESS) == 130


class TestEmptyFolderStatus:
    """An empty folder shows its own status; a remote-created dir is SYNCED."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        return table

    def test_synced_empty_folder_is_synced_and_green(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt
        from hsync_desktop.i18n import tr

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="newdir/", direction="—", size=0, status=TransferStatus.SYNCED)
        )
        table.refresh_view()

        item = table.item(0, tt.COL_STATUS)
        assert item.text() == tr("folder.status.synced")
        assert item.foreground().color() in (
            STATUS_COLORS[TransferStatus.SYNCED],
            STATUS_COLORS_DARK[TransferStatus.SYNCED],
        )

    def test_local_empty_folder_stays_local(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt
        from hsync_desktop.i18n import tr

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="newdir/", direction="—", size=0, status=TransferStatus.LOCAL)
        )
        table.refresh_view()

        assert table.item(0, tt.COL_STATUS).text() == tr("folder.status.local")

    def test_a_local_child_wins_over_the_folder_status(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt
        from hsync_desktop.i18n import tr

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="dir/", direction="—", size=0, status=TransferStatus.SYNCED)
        )
        table.add_transfer(
            FileTransfer(filepath="dir/f.txt", direction="—", size=1, status=TransferStatus.LOCAL)
        )
        table.refresh_view()

        assert table.item(0, tt.COL_STATUS).text() == tr("folder.status.local")


class TestShareSize:
    """The existing scan exposes the local folder size without a second walk."""

    def test_scan_reports_the_total_size(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        (tmp_path / "a.bin").write_bytes(b"x" * 10)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.bin").write_bytes(b"y" * 20)
        worker = DirectoryScanWorker(str(tmp_path), IgnoreMatcher(str(tmp_path)))
        sizes: list[int] = []
        worker.size_progress.connect(sizes.append)

        worker.run()

        assert sizes[-1] == 30

    def test_an_empty_share_reports_zero(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        worker = DirectoryScanWorker(str(tmp_path), IgnoreMatcher(str(tmp_path)))
        sizes: list[int] = []
        worker.size_progress.connect(sizes.append)

        worker.run()

        assert sizes == [0]

    def test_panel_forwards_the_scan_size(self, qtbot):
        from hsync_desktop.file_panel import FilePanel

        panel = FilePanel()
        qtbot.addWidget(panel)
        seen: list[int] = []
        panel.share_size_changed.connect(seen.append)

        panel._on_scan_size(42)

        assert panel._share_size_bytes == 42
        assert seen[-1] == 42


class TestEntryFiltering:
    """The sync-set predicate mirrors the engine, not a dot-name heuristic."""

    def test_dotfiles_are_synced_entries(self, tmp_path):
        from hsync_desktop.file_panel.filter import is_synced_entry

        matcher = IgnoreMatcher(str(tmp_path))

        assert is_synced_entry(matcher, str(tmp_path / ".env"), is_dir=False)
        assert is_synced_entry(matcher, str(tmp_path / ".git"), is_dir=True)

    def test_internal_and_cache_names_are_not_synced_entries(self, tmp_path):
        from hsync_desktop.file_panel.filter import is_synced_entry

        matcher = IgnoreMatcher(str(tmp_path))

        for name, is_dir in (
            (".hsynckeep", False),
            (".hsyncignore", False),
            (".DS_Store", False),
            ("Thumbs.db", False),
            ("a.bin.part", False),
        ):
            assert not is_synced_entry(matcher, str(tmp_path / name), is_dir=is_dir), name

    def test_hsyncignore_patterns_apply(self, tmp_path):
        from hsync_desktop.file_panel.filter import is_synced_entry

        (tmp_path / ".hsyncignore").write_text("data/\n")
        matcher = IgnoreMatcher(str(tmp_path))

        assert not is_synced_entry(matcher, str(tmp_path / "data"), is_dir=True)
        assert is_synced_entry(matcher, str(tmp_path / "docs"), is_dir=True)

    def test_has_dot_segment(self):
        from hsync_desktop.file_panel.filter import has_dot_segment

        assert has_dot_segment(".env")
        assert has_dot_segment("sub/.env")
        assert has_dot_segment(".git/config")
        assert not has_dot_segment("sub/file.txt")
        assert not has_dot_segment("a.b/c.txt")


class TestScanFiltering:
    """DirectoryScanWorker lists and counts exactly what the engine syncs."""

    def test_scan_includes_dotfiles_and_excludes_internal_entries(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        (tmp_path / "visible.bin").write_bytes(b"a" * 10)
        (tmp_path / ".env").write_bytes(b"b" * 7)
        (tmp_path / ".hsynckeep").write_bytes(b"")
        (tmp_path / ".DS_Store").write_bytes(b"c" * 3)
        (tmp_path / ".hsyncignore").write_text("*.log\n")
        (tmp_path / "debug.log").write_text("ignored")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.bin").write_bytes(b"d" * 5)

        worker = DirectoryScanWorker(str(tmp_path), IgnoreMatcher(str(tmp_path)))
        found: list[tuple[str, int, float]] = []
        sizes: list[int] = []
        worker.files_found.connect(found.extend)
        worker.size_progress.connect(sizes.append)

        worker.run()

        paths = {path for path, _size, _mtime in found}
        assert "visible.bin" in paths
        assert ".env" in paths
        assert "sub/b.bin" in paths
        assert ".hsynckeep" not in paths
        assert ".DS_Store" not in paths
        assert ".hsyncignore" not in paths
        assert "debug.log" not in paths
        assert sizes[-1] == 22  # 10 + 7 + 5; .hsynckeep and ignored files excluded

    def test_a_dot_only_directory_is_not_reported_as_empty(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        dotonly = tmp_path / "dotonly"
        dotonly.mkdir()
        (dotonly / ".env").write_bytes(b"x" * 4)

        worker = DirectoryScanWorker(str(tmp_path), IgnoreMatcher(str(tmp_path)))
        found: list[tuple[str, int, float]] = []
        worker.files_found.connect(found.extend)

        worker.run()

        paths = {path for path, _size, _mtime in found}
        assert "dotonly/.env" in paths
        assert "dotonly/" not in paths

    def test_a_directory_with_only_ignored_files_is_an_empty_dir_entry(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        (tmp_path / ".hsyncignore").write_text("*.log\n")
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "debug.log").write_text("x")

        worker = DirectoryScanWorker(str(tmp_path), IgnoreMatcher(str(tmp_path)))
        found: list[tuple[str, int, float]] = []
        worker.files_found.connect(found.extend)

        worker.run()

        paths = {path for path, _size, _mtime in found}
        assert "cache/" in paths

    def test_size_only_scan_reports_the_total_without_rows(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        (tmp_path / "a.bin").write_bytes(b"x" * 10)
        (tmp_path / ".env").write_bytes(b"y" * 7)
        (tmp_path / ".hsynckeep").write_bytes(b"")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.bin").write_bytes(b"z" * 5)

        worker = DirectoryScanWorker(str(tmp_path), IgnoreMatcher(str(tmp_path)), emit_rows=False)
        rows: list[tuple[str, int, float]] = []
        sizes: list[int] = []
        worker.files_found.connect(rows.extend)
        worker.size_progress.connect(sizes.append)

        worker.run()

        assert rows == []
        assert sizes[-1] == 22  # 10 + 7 + 5; .hsynckeep excluded


class TestShareSizeRefresh:
    """``refresh_share_size`` recomputes the total without reloading the table."""

    def test_is_skipped_without_a_folder(self, qtbot):
        from hsync_desktop.file_panel import FilePanel

        panel = FilePanel()
        qtbot.addWidget(panel)

        panel.refresh_share_size()

        assert panel._scan_worker is None

    def test_reports_the_current_total(self, qtbot, tmp_path):
        from hsync_desktop.file_panel import FilePanel

        (tmp_path / "a.bin").write_bytes(b"x" * 10)
        panel = FilePanel()
        qtbot.addWidget(panel)
        panel._current_directory = str(tmp_path)
        panel._matcher = IgnoreMatcher(str(tmp_path))
        seen: list[int] = []
        panel.share_size_changed.connect(seen.append)

        panel.refresh_share_size()
        qtbot.waitUntil(lambda: bool(seen), timeout=5000)

        assert seen[-1] == 10


class TestShowHiddenToggle:
    """Dot-prefixed names are a persisted view option (default: hidden)."""

    @staticmethod
    def _settings(tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)
        return store

    @staticmethod
    def _table(qtbot, files):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        table.set_base_directory("/base")
        table.add_transfers_batch(
            [
                FileTransfer(
                    filepath=path,
                    direction="—",
                    size=1,
                    status=TransferStatus.LOCAL,
                )
                for path in files
            ]
        )
        table.refresh_view()
        return table

    def test_dot_entries_are_hidden_by_default(self, qtbot, tmp_path, monkeypatch):
        self._settings(tmp_path, monkeypatch)
        table = self._table(
            qtbot, ["visible.txt", ".env", ".git/config", "sub/.hidden", "sub/a.txt"]
        )

        assert "visible.txt" in table._row_index
        assert "sub" in table._row_index
        assert ".env" not in table._row_index
        assert ".git" not in table._row_index

    def test_enabling_shows_dot_entries(self, qtbot, tmp_path, monkeypatch):
        self._settings(tmp_path, monkeypatch)
        table = self._table(qtbot, ["visible.txt", ".env", ".git/config"])

        table.set_show_hidden(True)

        assert ".env" in table._row_index
        assert ".git" in table._row_index

    def test_the_choice_is_persisted(self, qtbot, tmp_path, monkeypatch):
        self._settings(tmp_path, monkeypatch)
        table = self._table(qtbot, ["a.txt"])
        table.set_show_hidden(True)

        fresh = self._table(qtbot, ["a.txt"])

        assert fresh._show_hidden is True

    def test_folder_counts_ignore_view_hidden_children(self, qtbot, tmp_path, monkeypatch):
        self._settings(tmp_path, monkeypatch)
        table = self._table(qtbot, ["sub/a.txt", "sub/.hidden"])

        assert table._cached_items is not None
        data = next(fd for name, _transfer, fd in table._cached_items if name == "sub")
        assert data["count"] == 1

    def test_a_folder_with_only_hidden_children_stays_listed(self, qtbot, tmp_path, monkeypatch):
        self._settings(tmp_path, monkeypatch)
        table = self._table(qtbot, ["onlyhidden/.env"])

        assert "onlyhidden" in table._row_index


class TestConsistencyFiltering:
    """The periodic consistency pass uses the same engine predicate."""

    def test_a_dot_only_directory_is_not_emptied(self, qtbot, tmp_path):
        from hsync_desktop.file_panel import FilePanel

        dotonly = tmp_path / "dotonly"
        dotonly.mkdir()
        (dotonly / ".env").write_text("x")

        panel = FilePanel()
        qtbot.addWidget(panel)
        panel._current_directory = str(tmp_path)
        panel._matcher = IgnoreMatcher(str(tmp_path))
        panel._table.set_base_directory(str(tmp_path))

        panel._check_directory_consistency()

        assert "dotonly/.env" in panel._table._transfers
        assert "dotonly/" not in panel._table._transfers

    def test_a_locally_deleted_synced_row_is_reconciled(self, qtbot, tmp_path):
        """A synced file deleted on disk must disappear from the view.

        The structured delete event normally arrives first (red marker); this
        scan is the safety net for a missed event, so it must not keep a stale
        SYNCED row just because it is not LOCAL.
        """
        from hsync_desktop.file_panel import FilePanel

        panel = FilePanel()
        qtbot.addWidget(panel)
        panel._current_directory = str(tmp_path)
        panel._matcher = IgnoreMatcher(str(tmp_path))
        panel._table.set_base_directory(str(tmp_path))
        panel._table.add_transfer(
            FileTransfer(
                filepath="gone.bin",
                direction="—",
                size=10,
                status=TransferStatus.SYNCED,
            )
        )

        panel._check_directory_consistency()

        row = panel._table._transfers["gone.bin"]
        assert row.status is TransferStatus.DELETED

    def test_a_download_in_flight_is_not_removed_by_the_scan(self, qtbot, tmp_path):
        """The scan must not drop the row of a file not yet on disk."""
        from hsync_desktop.file_panel import FilePanel

        panel = FilePanel()
        qtbot.addWidget(panel)
        panel._current_directory = str(tmp_path)
        panel._matcher = IgnoreMatcher(str(tmp_path))
        panel._table.set_base_directory(str(tmp_path))
        panel._table.update_transfer_progress("incoming.bin", 5, 10, "download")

        panel._check_directory_consistency()

        assert panel._table._transfers["incoming.bin"].status is TransferStatus.DOWNLOADING

    def test_new_on_disk_paths_ask_for_a_status_refresh(self, qtbot, tmp_path):
        """A missed event leaves a stale Local; the scan asks for a preview."""
        from hsync_desktop.file_panel import FilePanel

        (tmp_path / "new.txt").write_text("x", encoding="utf-8")
        panel = FilePanel()
        qtbot.addWidget(panel)
        panel._current_directory = str(tmp_path)
        panel._matcher = IgnoreMatcher(str(tmp_path))
        panel._table.set_base_directory(str(tmp_path))

        with qtbot.waitSignal(panel.scan_found_new_files, timeout=1000):
            panel._check_directory_consistency()


class TestTransferRate:
    """The displayed rate comes from progress samples, not from the start time."""

    def test_rate_uses_the_sample_window(self):
        transfer = FileTransfer(filepath="a.bin", direction="↓", size=10_000_000)
        transfer.start_transfer("↓", now=1000.0)
        transfer.note_progress(0, now=1000.0)
        transfer.note_progress(1_048_576, now=1001.0)

        assert transfer.speed_bps is not None
        assert abs(transfer.speed_bps - 1_048_576) < 1024
        expected_eta = (10_000_000 - 1_048_576) / 1_048_576
        assert transfer.eta_seconds is not None
        assert abs(transfer.eta_seconds - expected_eta) < 1.0

    def test_a_burst_settles_on_the_sustained_rate(self):
        """The window reports the last second, so a burst stops dominating it."""
        transfer = FileTransfer(filepath="a.bin", direction="↑", size=100_000_000)
        transfer.start_transfer("↑", now=0.0)
        transfer.note_progress(0, now=0.0)

        # 2 MiB in 1 s: 512 KiB every 0.25 s.
        for step in range(1, 5):
            transfer.note_progress(step * 524_288, now=step * 0.25)
        assert transfer.speed_bps == pytest.approx(2_097_152)

        # 1 MiB/s sustained afterwards: 256 KiB every 0.25 s.
        sent = 2_097_152
        for step in range(1, 9):
            sent += 262_144
            transfer.note_progress(sent, now=1.0 + step * 0.25)
        assert transfer.speed_bps == pytest.approx(1_048_576, rel=0.01)

    def test_a_backwards_sample_restarts_the_measurement(self):
        transfer = FileTransfer(filepath="a.bin", direction="↓", size=1000)
        transfer.start_transfer("↓", now=10.0)
        transfer.note_progress(0, now=10.0)
        transfer.note_progress(500, now=11.0)
        transfer.note_progress(100, now=11.5)  # resume restarted the counter

        assert transfer.speed_bps is None

    def test_stop_transfer_returns_the_row_to_rest(self):
        transfer = FileTransfer(filepath="a.bin", direction="↓", size=1000)
        transfer.start_transfer("↓", now=1.0)
        transfer.note_progress(0, now=1.0)
        transfer.note_progress(500, now=2.0)

        transfer.stop_transfer()

        assert transfer.status is TransferStatus.LOCAL
        assert transfer.direction == "—"
        assert transfer.bytes_transferred == 0
        assert transfer.speed_bps is None


class TestLiveTransferProgress:
    """A progress event creates the row of a file that is not on disk yet."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        return table

    def test_progress_creates_the_row_of_a_received_file(self, qtbot):
        from PySide6.QtCore import Qt

        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.update_transfer_progress("incoming.bin", 512_000, 1_024_000, "download")
        table.refresh_view()  # flush the debounce

        assert table.rowCount() == 1
        assert table.item(0, tt.COL_DIRECTION).text() == "↓"
        assert table.item(0, tt.COL_SIZE).text() == _format_size(1_024_000)
        pct = table.item(0, tt.COL_PROGRESS).data(Qt.ItemDataRole.UserRole)
        assert pct == 50

    def test_progress_keeps_the_on_disk_size_of_a_compressed_upload(self, qtbot):
        from PySide6.QtCore import Qt

        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(
                filepath="big.bin",
                direction="↑",
                size=1_000_000,
                status=TransferStatus.TO_UPLOAD,
            )
        )
        table.update_transfer_progress("big.bin", 400_000, 400_000, "upload")
        table.refresh_view()

        assert table._transfers["big.bin"].size == 1_000_000  # the file
        assert table._transfers["big.bin"].total_bytes == 400_000  # the wire
        assert table.item(0, tt.COL_DIRECTION).text() == "↑"
        assert table.item(0, tt.COL_PROGRESS).data(Qt.ItemDataRole.UserRole) == 100

    def test_a_completed_download_shows_the_final_size(self, qtbot):
        from PySide6.QtCore import Qt

        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.update_transfer_progress("incoming.bin", 512, 1024, "download")
        table.update_file_status("incoming.bin", "synced", size=1024, mtime=1.0)

        assert table.item(0, tt.COL_SIZE).text() == _format_size(1024)
        assert table.item(0, tt.COL_PROGRESS).data(Qt.ItemDataRole.UserRole) == -1
        assert table.item(0, tt.COL_SPEED).text() == ""

    def test_a_failed_transfer_flags_the_row_as_error(self, qtbot):
        from PySide6.QtCore import Qt

        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.update_transfer_progress("incoming.bin", 512, 1024, "download")
        table.mark_failed("incoming.bin")

        assert table._transfers["incoming.bin"].status is TransferStatus.ERROR
        assert table.item(0, tt.COL_PROGRESS).data(Qt.ItemDataRole.UserRole) == -1
        assert table.item(0, tt.COL_SPEED).text() == ""

    def test_stop_clears_in_flight_rows(self, qtbot, tmp_path):
        table = self._table(qtbot)
        (tmp_path / "kept.bin").write_bytes(b"abcd")
        table.update_transfer_progress("kept.bin", 2, 4, "download")
        table.update_transfer_progress("gone.bin", 2, 4, "download")

        table.clear_transient_progress(str(tmp_path))

        assert "gone.bin" not in table._transfers
        assert table._transfers["kept.bin"].status is TransferStatus.LOCAL

    def test_reset_keeps_in_flight_and_deleted_rows(self, qtbot):
        """A link flap must not erase live progress nor an unacknowledged delete."""
        table = self._table(qtbot)
        table.update_transfer_progress("up.bin", 1, 10, "upload")
        table.add_transfer(
            FileTransfer(filepath="gone.bin", direction="✕", size=0, status=TransferStatus.DELETED)
        )
        table.add_transfer(
            FileTransfer(filepath="idle.bin", direction="—", size=5, status=TransferStatus.SYNCED)
        )

        table.reset_all_to_local()

        assert table._transfers["up.bin"].status is TransferStatus.UPLOADING
        assert table._transfers["gone.bin"].status is TransferStatus.DELETED
        assert table._transfers["idle.bin"].status is TransferStatus.LOCAL

    def test_preview_status_does_not_downgrade_an_in_flight_row(self, qtbot):
        """A preview must not hide the progress of an active transfer, while a
        real completion still applies."""
        table = self._table(qtbot)
        table.update_transfer_progress("up.bin", 1, 10, "upload")

        table.update_file_status("up.bin", "synced", size=10, preview=True)
        assert table._transfers["up.bin"].status is TransferStatus.UPLOADING

        table.update_file_status("up.bin", "synced", size=10)
        assert table._transfers["up.bin"].status is TransferStatus.SYNCED
