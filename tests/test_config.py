# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.config module."""

import hsync_desktop.config as config


class TestAppInfo:
    """Test application info constants."""


class TestDefaultSyncSettings:
    """Test default sync settings."""

    def test_default_bucket(self):
        assert config.DEFAULT_BUCKET == "my-bucket"

    def test_default_group(self):
        assert config.DEFAULT_GROUP == "my-group"


class TestConnectionDefaults:
    """Test connection default values."""

    def test_default_insecure(self):
        assert config.DEFAULT_INSECURE is False

    def test_default_ca_cert(self):
        assert config.DEFAULT_CA_CERT == ""

    def test_default_http_timeout(self):
        assert config.DEFAULT_HTTP_TIMEOUT == 30


class TestSyncDefaults:
    """Test sync default values."""

    def test_default_continuous(self):
        assert config.DEFAULT_CONTINUOUS is True

    def test_default_ignore_delete(self):
        assert config.DEFAULT_IGNORE_DELETE is False

    def test_default_sync_direction(self):
        assert config.DEFAULT_SYNC_DIRECTION == "bidirectional"

    def test_default_resync_interval(self):
        assert config.DEFAULT_RESYNC_INTERVAL == 0

    def test_default_retry_delay(self):
        assert config.DEFAULT_RETRY_DELAY == 5

    def test_default_stability_delay(self):
        assert config.DEFAULT_STABILITY_DELAY == 5

    def test_default_max_wait(self):
        assert config.DEFAULT_MAX_WAIT == 120

    def test_default_filter_path(self):
        assert config.DEFAULT_FILTER_PATH == ""

    def test_default_no_compression(self):
        assert config.DEFAULT_NO_COMPRESSION is False

    def test_default_dry_run(self):
        assert config.DEFAULT_DRY_RUN is False

    def test_default_auto_sync(self):
        assert config.DEFAULT_AUTO_SYNC is False


class TestLanDefaults:
    """Test LAN mode default values."""

    def test_default_lan_enabled(self):
        assert config.DEFAULT_LAN_ENABLED is False

    def test_default_lan_key(self):
        assert config.DEFAULT_LAN_KEY == ""

    def test_default_lan_port(self):
        assert config.DEFAULT_LAN_PORT == 0

    def test_default_discovery_timeout(self):
        assert config.DEFAULT_DISCOVERY_TIMEOUT == 10

    def test_default_force_master(self):
        assert config.DEFAULT_FORCE_MASTER is False


class TestOutputDefaults:
    """Test output/logging default values."""

    def test_default_verbose(self):
        assert config.DEFAULT_VERBOSE is False

    def test_default_quiet(self):
        assert config.DEFAULT_QUIET is False

    def test_default_logfile(self):
        assert config.DEFAULT_LOGFILE == ""

    def test_default_show_log_panel(self):
        assert config.DEFAULT_SHOW_LOG_PANEL is False


class TestAppearanceDefaults:
    """Test appearance default values."""

    def test_default_notifications(self):
        assert config.DEFAULT_NOTIFICATIONS is True

    def test_default_tooltips(self):
        assert config.DEFAULT_TOOLTIPS is True


class TestUIConstants:
    """Test UI-related constants."""

    def test_file_batch_size(self):
        assert config.FILE_BATCH_SIZE == 50

    def test_consistency_check_interval_ms(self):
        assert config.CONSISTENCY_CHECK_INTERVAL_MS == 5000
