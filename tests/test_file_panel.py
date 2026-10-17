# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for hsync_desktop.file_panel module."""

from time import time

from hsync_common.format import format_bytes as _format_size
from hsync_common.format import format_duration

from hsync_desktop.file_panel import (
    _FILE_TYPE_MAP,
    _NO_PROGRESS_STATUSES,
    STATUS_COLORS,
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
        """ETA is computed while a download is in progress."""
        transfer = FileTransfer(
            filepath="test.txt",
            direction="↓",
            size=1000,
            bytes_transferred=500,
            status=TransferStatus.DOWNLOADING,
            start_time=time() - 10,
        )
        eta = transfer.eta_seconds
        assert eta is not None
        assert 5 <= eta <= 15

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
        assert colour == STATUS_COLORS[TransferStatus.LOCAL]

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


class TestOptionalColumns:
    """Speed and Direction are available but hidden by default."""

    @staticmethod
    def _table(qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = tt.FileTransferTable()
        qtbot.addWidget(table)
        return table

    def test_speed_and_direction_start_hidden(self, qtbot, tmp_path, monkeypatch):
        from PySide6.QtCore import QSettings

        from hsync_desktop.file_panel import transfer_table as tt

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(tt, "QSettings", lambda *a, **k: store)
        table = self._table(qtbot)
        header = table.horizontalHeader()

        assert header.isSectionHidden(tt.COL_SPEED)
        assert header.isSectionHidden(tt.COL_DIRECTION)
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
        table.add_transfer(
            FileTransfer(
                filepath="a.bin",
                direction="↓",
                size=4096,
                bytes_transferred=2048,
                start_time=time() - 2.0,
                status=TransferStatus.DOWNLOADING,
            )
        )

        assert table.item(0, tt.COL_DIRECTION).text() == "↓"
        assert table.item(0, tt.COL_SPEED).text().endswith("/s")

    def test_a_completed_row_has_no_speed(self, qtbot):
        from hsync_desktop.file_panel import transfer_table as tt

        table = self._table(qtbot)
        table.add_transfer(
            FileTransfer(filepath="a.bin", direction="↓", size=10, status=TransferStatus.COMPLETED)
        )

        assert table.item(0, tt.COL_SPEED).text() == ""

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
        assert fresh.horizontalHeader().isSectionHidden(tt.COL_DIRECTION)

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
        assert item.foreground().color() == STATUS_COLORS[TransferStatus.SYNCED]

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
        worker = DirectoryScanWorker(str(tmp_path))
        sizes: list[int] = []
        worker.size_progress.connect(sizes.append)

        worker.run()

        assert sizes[-1] == 30

    def test_an_empty_share_reports_zero(self, tmp_path):
        from hsync_desktop.file_panel.workers import DirectoryScanWorker

        worker = DirectoryScanWorker(str(tmp_path))
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
