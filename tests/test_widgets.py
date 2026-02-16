# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.widgets module."""

from pathlib import Path

import pytest


class TestWidgetsModule:
    """Test widgets module imports."""

    def test_toggle_switch_import(self):
        """Test that ToggleSwitch can be imported."""
        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        assert ToggleSwitch is not None

    def test_widgets_init_exists(self):
        """Test that widgets __init__ can be imported."""
        from hsync_desktop.widgets import ToggleSwitch

        assert ToggleSwitch is not None


class TestToggleSwitchConstants:
    """Test that ToggleSwitch class has expected methods."""

    def test_toggle_switch_has_size_hint(self):
        """Test ToggleSwitch has sizeHint method."""
        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        assert hasattr(ToggleSwitch, "sizeHint")
        assert callable(ToggleSwitch.sizeHint)

    def test_toggle_switch_has_minimum_size_hint(self):
        """Test ToggleSwitch has minimumSizeHint method."""
        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        assert hasattr(ToggleSwitch, "minimumSizeHint")
        assert callable(ToggleSwitch.minimumSizeHint)

    def test_toggle_switch_has_paint_event(self):
        """Test ToggleSwitch has paintEvent method."""
        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        assert hasattr(ToggleSwitch, "paintEvent")

    def test_toggle_switch_has_enter_event(self):
        """Test ToggleSwitch has enterEvent method."""
        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        assert hasattr(ToggleSwitch, "enterEvent")

    def test_toggle_switch_inherits_qabstractbutton(self):
        """Test ToggleSwitch inherits from QAbstractButton."""
        from PySide6.QtWidgets import QAbstractButton

        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        assert issubclass(ToggleSwitch, QAbstractButton)

    def test_toggle_switch_has_thumb_position_property(self):
        """Test ToggleSwitch has thumb_position property."""
        from PySide6.QtCore import Property

        from hsync_desktop.widgets.toggle_switch import ToggleSwitch

        # Check that thumb_position is a Property
        assert hasattr(ToggleSwitch, "thumb_position")
        assert isinstance(ToggleSwitch.thumb_position, Property)


class TestWidgetsPackage:
    """Test widgets package structure."""

    def test_widgets_dir_exists(self):
        """Test widgets directory exists."""
        widgets_dir = Path(__file__).parent.parent / "hsync_desktop" / "widgets"
        assert widgets_dir.exists()

    def test_toggle_switch_file_exists(self):
        """Test toggle_switch.py file exists."""
        toggle_file = (
            Path(__file__).parent.parent / "hsync_desktop" / "widgets" / "toggle_switch.py"
        )
        assert toggle_file.exists()

    def test_toggle_switch_file_not_empty(self):
        """Test toggle_switch.py is not empty."""
        toggle_file = (
            Path(__file__).parent.parent / "hsync_desktop" / "widgets" / "toggle_switch.py"
        )
        assert toggle_file.stat().st_size > 0
