# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The bucket-change check: a server-mode bucket edit is verified before saving.

Renaming a share keeps the bucket (``ShareStore.rename``), so only an edit of the
bucket field reaches the probe. A 404 is ambiguous on the server side (missing or
no membership) and the first upload creates a missing bucket, so the check asks
instead of saving silently.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox

import hsync_desktop.settings.dialog as settings_dialog
from hsync_desktop.engine import ProbeOutcome, ServerProbeResult
from hsync_desktop.i18n import tr


@pytest.fixture
def server_dialog(dialog):
    """A dialog in server mode pointed at a host with a key."""
    dialog.p2p_mode.setChecked(False)
    dialog.server_url.setText("https://host")
    dialog.api_key.setText("key")
    dialog.http_timeout.setValue(5)
    return dialog


def _persisted(settings) -> str:
    return str(settings.value("sync/bucket", "", str))


def _choice_box(monkeypatch, choice: int) -> list[str]:
    """Patch the three-choice box so it answers with *choice* (0-based)."""
    buttons = [object(), object(), object()]
    labels: list[str] = []

    class _Box:
        def exec(self) -> int:
            return 0

        def clickedButton(self):  # noqa: N802 - Qt spelling
            return buttons[choice]

    def fake_build(_parent, *, title, text, choices, default_index=0):
        labels.extend(label for label, _icon in choices)
        return _Box(), buttons

    monkeypatch.setattr(settings_dialog, "build_choice_box", fake_build)
    return labels


class TestWhenTheCheckRuns:
    def test_an_unchanged_bucket_needs_no_check(self, server_dialog, settings):
        settings.setValue("sync/bucket", "team")
        server_dialog.bucket.setText("team")

        assert server_dialog._bucket_probe_job("https://host") is None

    def test_p2p_mode_never_checks(self, server_dialog, settings):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        server_dialog.p2p_mode.setChecked(True)

        assert server_dialog._bucket_probe_job("https://host") is None

    def test_a_missing_key_skips_the_check(self, server_dialog, settings):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        server_dialog.api_key.setText("")

        assert server_dialog._bucket_probe_job("https://host") is None

    def test_an_unset_server_skips_the_check(self, server_dialog, settings):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")

        assert server_dialog._bucket_probe_job(None) is None

    def test_a_changed_bucket_probes_the_new_name(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        seen: dict[str, object] = {}

        def fake_probe(base_url, bucket, api_key, *, ssl_context, timeout):
            seen.update(base=base_url, bucket=bucket, key=api_key)
            return ServerProbeResult(True, 200, 1, True), ""

        monkeypatch.setattr(settings_dialog, "probe_server_bucket_access", fake_probe)
        job = server_dialog._bucket_probe_job("https://host/")

        assert job is not None
        assert job() == ProbeOutcome(True, 200)
        assert seen == {"base": "https://host", "bucket": "new", "key": "key"}


class TestOutcome:
    def test_a_reachable_bucket_saves_and_runs_the_continuation(self, server_dialog, settings):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        done: list[str] = []
        server_dialog._commit_continuation = lambda: done.append("accepted")

        server_dialog._on_bucket_probe_done(ProbeOutcome(True, 200))

        assert _persisted(settings) == "new"
        assert done == ["accepted"]
        assert server_dialog._commit_continuation is None

    def test_404_offers_to_create_the_share(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        labels = _choice_box(monkeypatch, 0)
        created: list[str] = []
        monkeypatch.setattr(
            server_dialog, "_create_bucket_then_commit", lambda: created.append("create")
        )

        server_dialog._on_bucket_probe_done(ProbeOutcome(False, 404, reason="share_missing"))

        assert labels == [
            tr("settings.bucket_probe.create"),
            tr("settings.bucket_probe.save_anyway"),
            tr("action.cancel"),
        ]
        assert created == ["create"]
        # Nothing is saved until the re-check after the creation passes.
        assert _persisted(settings) == "old"

    def test_404_save_anyway_keeps_the_old_behaviour(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        _choice_box(monkeypatch, 1)

        server_dialog._on_bucket_probe_done(ProbeOutcome(False, 404, reason="share_missing"))

        assert _persisted(settings) == "new"

    def test_404_declined_keeps_the_old_bucket(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        done: list[str] = []
        server_dialog._commit_continuation = lambda: done.append("accepted")
        _choice_box(monkeypatch, 2)

        server_dialog._on_bucket_probe_done(ProbeOutcome(False, 404, reason="share_missing"))

        assert _persisted(settings) == "old"
        assert done == []
        assert server_dialog._commit_continuation is None

    def test_a_failed_creation_warns_and_saves_nothing(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        warned: list[str] = []

        class _Box:
            @staticmethod
            def warning(*_args, **_kwargs):
                warned.append("warning")

        monkeypatch.setattr(settings_dialog, "QMessageBox", _Box)

        server_dialog._on_bucket_probe_done(ProbeOutcome(False, 403, reason="create_failed"))

        assert warned == ["warning"]
        assert _persisted(settings) == "old"

    def test_create_then_commit_creates_and_rechecks(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        server_dialog._bucket_probe_args = ("https://host", "new", "key", object(), 5.0)
        calls: list[str] = []
        monkeypatch.setattr(
            settings_dialog,
            "create_server_bucket",
            lambda *_a, **_k: calls.append("create") or ServerProbeResult(True, 201, 1, True),
        )
        monkeypatch.setattr(
            settings_dialog,
            "probe_server_bucket_access",
            lambda *_a, **_k: (ServerProbeResult(True, 200, 1, True), ""),
        )
        started: list = []
        monkeypatch.setattr(server_dialog, "_start_bucket_probe", lambda job: started.append(job))

        server_dialog._create_bucket_then_commit()

        assert started
        assert started[0]() == ProbeOutcome(True, 200)
        assert calls == ["create"]

    def test_an_offline_server_asks_before_saving(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        monkeypatch.setattr(settings_dialog, "confirm", lambda *_a, **_k: True)

        server_dialog._on_bucket_probe_done(ProbeOutcome(False, None, reason="unreachable"))

        assert _persisted(settings) == "new"

    def test_a_rejected_key_never_saves(self, server_dialog, settings, monkeypatch):
        settings.setValue("sync/bucket", "old")
        server_dialog.bucket.setText("new")
        warned: list[str] = []

        class _Box:
            @staticmethod
            def warning(*_args, **_kwargs):
                warned.append("warning")

        monkeypatch.setattr(settings_dialog, "QMessageBox", _Box)

        server_dialog._on_bucket_probe_done(ProbeOutcome(False, 401, reason="unauthorized"))

        assert warned == ["warning"]
        assert _persisted(settings) == "old"


class TestBusyState:
    def test_the_ok_button_reports_the_check_and_is_restored(self, server_dialog):
        box = server_dialog.findChild(QDialogButtonBox)
        ok = box.button(QDialogButtonBox.StandardButton.Ok)
        label = ok.text()

        server_dialog._set_commit_busy(True)
        assert ok.isEnabled() is False
        assert ok.text() == tr("common.checking")

        server_dialog._set_commit_busy(False)
        assert ok.isEnabled() is True
        assert ok.text() == label

    def test_cancel_stays_usable_during_the_check(self, server_dialog):
        box = server_dialog.findChild(QDialogButtonBox)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)

        server_dialog._set_commit_busy(True)

        assert cancel.isEnabled() is True
