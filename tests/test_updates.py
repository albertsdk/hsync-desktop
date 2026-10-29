# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Release update check: version parsing, pinned lookup and persisted state."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from hsync_desktop import updates

RELEASE_URL = "https://github.com/albertsdk/hsync-desktop/releases/tag/v1.0.12"


class _Response:
    """Minimal urlopen() stand-in exposing the final URL of the redirect."""

    def __init__(self, url: str) -> None:
        self._url = url

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """Redirect the persisted update state to a throwaway INI file."""
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(updates, "_settings", lambda: store)
    return store


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.0.11", (1, 0, 11)),
        ("v1.2.3", (1, 2, 3)),
        ("V1.2.3", (1, 2, 3)),
        (" 1.0.12 ", (1, 0, 12)),
        ("1.0.12-rc1", (1, 0, 12)),
        ("1.0.12+build.7", (1, 0, 12)),
        ("1.2.3.4", (1, 2, 3, 4)),
        ("", None),
        ("v", None),
        ("1..2", None),
        ("1.0.x", None),
        ("latest", None),
    ],
)
def test_parse_version_accepts_tags_and_rejects_garbage(text, expected):
    assert updates.parse_version(text) == expected


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        ("1.0.11", "1.0.12", True),
        ("1.0.11", "1.1.0", True),
        ("1.0.11", "2.0.0", True),
        ("1.0.11", "1.0.11", False),
        ("1.0.12", "1.0.11", False),
        ("1.0", "1.0.0", False),
        ("1.0.9", "1.0.10", True),
        ("1.0.11", "v1.0.12", True),
        ("1.0.11", "1.0.12-rc1", True),
        # A malformed tag must never be reported as an update.
        ("1.0.11", "", False),
        ("1.0.11", "latest", False),
        ("", "1.0.12", False),
    ],
)
def test_is_newer_compares_numerically(current, latest, expected):
    assert updates.is_newer(current, latest) is expected


def test_fetch_reads_the_tag_from_the_redirect_target(monkeypatch):
    monkeypatch.setattr(updates, "urlopen", lambda *_a, **_k: _Response(RELEASE_URL))
    assert updates.fetch_latest_version() == "1.0.12"


@pytest.mark.parametrize(
    "final_url",
    [
        "https://github.com/albertsdk/hsync-desktop/releases",  # no release yet
        "https://github.com/albertsdk/hsync-desktop",  # unexpected redirect
        "https://github.com/albertsdk/hsync-desktop/releases/tag/",  # empty tag
        "https://github.com/albertsdk/hsync-desktop/releases/tag/nightly",  # unparseable
    ],
)
def test_fetch_returns_none_without_a_parseable_release_tag(monkeypatch, final_url):
    monkeypatch.setattr(updates, "urlopen", lambda *_a, **_k: _Response(final_url))
    assert updates.fetch_latest_version() is None


@pytest.mark.parametrize("error", [OSError("offline"), TimeoutError(), ValueError("bad url")])
def test_fetch_returns_none_on_network_failures(monkeypatch, error):
    def boom(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(updates, "urlopen", boom)
    assert updates.fetch_latest_version() is None


def test_the_lookup_target_is_pinned_to_the_project_releases(monkeypatch):
    """The request URL is a fixed constant, never built from remote data."""
    seen: list[str] = []

    def fake_urlopen(request, *_a, **_k):
        seen.append(request.full_url)
        return _Response(RELEASE_URL)

    monkeypatch.setattr(updates, "urlopen", fake_urlopen)
    updates.fetch_latest_version()
    assert seen == ["https://github.com/albertsdk/hsync-desktop/releases/latest"]


def test_automatic_checks_are_opt_in_by_default(settings):
    assert updates.is_enabled() is False
    assert updates.should_check() is False


def test_should_check_respects_the_interval_and_the_opt_in(settings, monkeypatch):
    monkeypatch.setattr(updates.time, "time", lambda: 1_000_000)
    updates.set_enabled(True)
    assert updates.should_check() is True  # never checked before

    updates.record_check("1.0.12")
    assert updates.should_check() is False  # just checked
    assert updates.should_check(now=1_000_000 + updates.CHECK_INTERVAL_SECONDS) is True
    # A clock that jumped far into the past must not postpone the check.
    assert updates.should_check(now=1_000_000 - 2 * updates.CHECK_INTERVAL_SECONDS) is True


def test_record_check_keeps_the_version_and_the_attempt_time(settings):
    updates.record_check("1.0.12", now=42)
    assert updates.cached_latest_version() == "1.0.12"
    assert updates.last_check_epoch() == 42

    # A failed attempt keeps the timestamp but clears the discovered version.
    updates.record_check(None, now=84)
    assert updates.cached_latest_version() is None
    assert updates.last_check_epoch() == 84


def test_check_now_records_the_attempt_when_offline(settings, monkeypatch):
    monkeypatch.setattr(updates, "fetch_latest_version", lambda *_a, **_k: None)
    monkeypatch.setattr(updates.time, "time", lambda: 7)
    assert updates.check_now() is None
    assert updates.last_check_epoch() == 7
    assert updates.cached_latest_version() is None


def test_dismissed_version_is_per_release(settings):
    assert updates.is_dismissed("1.0.12") is False
    updates.set_dismissed_version("1.0.12")
    assert updates.is_dismissed("1.0.12") is True
    assert updates.is_dismissed("1.0.13") is False
    assert updates.is_dismissed("") is False
