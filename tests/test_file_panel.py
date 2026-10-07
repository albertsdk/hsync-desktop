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
