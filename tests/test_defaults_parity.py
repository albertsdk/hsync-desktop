# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Contract test: the GUI re-exports the shared defaults instead of copying them.

The desktop shells out to ``hsync`` and cannot import the client package, so
both sides read ``hsync_common.defaults``. These assertions fail as soon as a
value is written back as a literal in ``config.py`` — the copy that used to
drift from the engine.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from hsync_common import defaults
from hsync_common.constants import DELTA_MIN_FILE_SIZE, DELTA_MIN_FILE_SIZE_P2P
from hsync_common.disk import BYTES_PER_MB

import hsync_desktop
from hsync_desktop import config


class TestSharedDefaultsAreAliases:
    def test_connection_and_timing_defaults(self):
        assert config.DEFAULT_HTTP_TIMEOUT is defaults.HTTP_TIMEOUT_DEFAULT
        assert config.DEFAULT_SYNC_DIRECTION is defaults.SYNC_DIRECTION_DEFAULT
        assert config.DEFAULT_RETRY_DELAY is defaults.RECONNECT_DELAY_DEFAULT
        assert config.DEFAULT_STABILITY_DELAY is defaults.STABILITY_DELAY_DEFAULT
        assert config.DEFAULT_MAX_WAIT is defaults.MAX_WAIT_TIMEOUT_DEFAULT

    def test_limits_and_guard_defaults(self):
        assert config.DEFAULT_MIN_FREE_DISK_SPACE == (
            defaults.MIN_FREE_DISK_SPACE_DEFAULT // BYTES_PER_MB
        )
        assert config.DEFAULT_MAX_INBOUND_SIZE is defaults.MAX_INBOUND_SIZE_MB_DEFAULT
        assert config.DEFAULT_MASS_DELETE_GUARD is defaults.MASS_DELETE_GUARD_DEFAULT
        assert config.DEFAULT_MASS_DELETE_THRESHOLD is defaults.MASS_DELETE_THRESHOLD_DEFAULT
        assert config.DEFAULT_MASS_DELETE_PERCENT is defaults.MASS_DELETE_PERCENT_DEFAULT

    def test_bandwidth_bounds(self):
        assert config.BANDWIDTH_MIN_BPS is defaults.BANDWIDTH_MIN_BPS
        assert config.BANDWIDTH_MAX_BPS is defaults.BANDWIDTH_MAX_BPS
        assert config.BANDWIDTH_MAX_MBPS == defaults.BANDWIDTH_MAX_BPS / (1024 * 1024)

    def test_p2p_peer_defaults(self):
        assert config.DEFAULT_P2P_PEER_DOWNLOAD is defaults.P2P_PEER_DOWNLOAD_DEFAULT
        assert config.DEFAULT_P2P_PEER_READ_CAP is defaults.P2P_PEER_READ_CAP_DEFAULT
        assert config.DEFAULT_P2P_PEER_SOURCES_MAX is defaults.P2P_PEER_SOURCES_MAX_DEFAULT

    def test_delta_floors_are_derived_from_the_client_byte_constants(self):
        """The dialog works in KB; the engine's constants are bytes."""
        assert config.DEFAULT_DELTA_MIN_FILE_SIZE_KB * 1024 == DELTA_MIN_FILE_SIZE
        assert config.DEFAULT_DELTA_MIN_FILE_SIZE_P2P_KB * 1024 == DELTA_MIN_FILE_SIZE_P2P

    def test_validation_bounds_are_the_shared_ones(self):
        """The GUI clamps to the same ranges the CLI validates against."""
        assert config.RETRY_DELAY_MIN is defaults.RECONNECT_DELAY_MIN
        assert config.RETRY_DELAY_MAX is defaults.RECONNECT_DELAY_MAX
        assert config.STABILITY_DELAY_MAX is defaults.STABILITY_DELAY_MAX
        assert config.MAX_WAIT_MIN is defaults.MAX_WAIT_TIMEOUT_MIN
        assert config.MAX_WAIT_MAX is defaults.MAX_WAIT_TIMEOUT_MAX
        assert config.RESYNC_MAX is defaults.RESYNC_MAX
        # The GUI bounds are the byte SSOT expressed in whole MB.
        assert config.MIN_FREE_DISK_SPACE_MB_MIN == defaults.MIN_FREE_DISK_SPACE_MIN // BYTES_PER_MB
        assert config.MIN_FREE_DISK_SPACE_MB_MAX == defaults.MIN_FREE_DISK_SPACE_MAX // BYTES_PER_MB
        assert config.MAX_INBOUND_SIZE_MB_MIN is defaults.MAX_INBOUND_SIZE_MB_MIN
        assert config.MAX_INBOUND_SIZE_MB_MAX is defaults.MAX_INBOUND_SIZE_MB_MAX


class TestUiResourceDefaults:
    """The Qt Designer file must not carry a stale copy of a shared default."""

    _TIMING_SPINBOXES = {
        "maxWait": (config.GUI_MAX_WAIT_MIN, defaults.MAX_WAIT_TIMEOUT_MAX),
        "retryDelay": (config.GUI_RETRY_DELAY_MIN, defaults.RECONNECT_DELAY_MAX),
        "stabilityDelay": (0, defaults.STABILITY_DELAY_MAX),
    }

    def _spinbox(self, name: str) -> ET.Element:
        ui = Path(hsync_desktop.__file__).parent / "ui" / "settings_dialog.ui"
        for widget in ET.parse(ui).iter("widget"):
            if widget.get("name") == name:
                return widget
        raise AssertionError(f"{name} widget not found in settings_dialog.ui")

    def _number(self, widget: ET.Element, prop: str) -> int:
        node = widget.find(f"./property[@name='{prop}']/number")
        assert node is not None, f"missing {prop} on {widget.get('name')}"
        return int(node.text or 0)

    def test_max_wait_spinbox_uses_the_shared_default(self):
        assert self._number(self._spinbox("maxWait"), "value") == defaults.MAX_WAIT_TIMEOUT_DEFAULT

    def test_max_wait_spinbox_is_in_seconds(self):
        suffix = self._spinbox("maxWait").find("./property[@name='suffix']/string")
        assert suffix is not None
        assert (suffix.text or "").strip() == "s"

    @pytest.mark.parametrize(
        "name,expected",
        _TIMING_SPINBOXES.items(),
        ids=list(_TIMING_SPINBOXES),
    )
    def test_timing_spinbox_range_matches_the_shared_bounds(self, name, expected):
        widget = self._spinbox(name)
        assert (self._number(widget, "minimum"), self._number(widget, "maximum")) == expected
