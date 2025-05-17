# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.utils module."""

import pytest

from hsync_desktop.utils import format_bytes


class TestFormatBytes:
    """Tests for format_bytes() function."""

    def test_bytes(self):
        """Test byte values."""
        assert format_bytes(0) == "0 B"
        assert format_bytes(1) == "1 B"
        assert format_bytes(500) == "500 B"

    def test_kilobytes(self):
        """Test kilobyte values."""
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(10240) == "10.0 KB"

    def test_megabytes(self):
        """Test megabyte values."""
        assert format_bytes(1048576) == "1.0 MB"
        assert format_bytes(1572864) == "1.5 MB"
        assert format_bytes(10485760) == "10.0 MB"

    def test_gigabytes(self):
        """Test gigabyte values."""
        assert format_bytes(1073741824) == "1.0 GB"
        assert format_bytes(1610612736) == "1.5 GB"
        assert format_bytes(10737418240) == "10.0 GB"

    def test_terabytes(self):
        """Test terabyte values."""
        assert format_bytes(1099511627776) == "1.0 TB"
        assert format_bytes(1649267441664) == "1.5 TB"

    def test_negative_values(self):
        """Test negative values."""
        assert format_bytes(-1) == "-1 B"
        assert format_bytes(-1024) == "-1.0 KB"
