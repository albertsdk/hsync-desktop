# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The startup disclaimer: explicit labels, app icons, and versioned acceptance."""

from __future__ import annotations

from hsync_desktop.i18n import tr
from hsync_desktop.main_window.start import (
    _DISCLAIMER_VERSION_KEY,
    _LEGACY_DISCLAIMER_KEY,
    DISCLAIMER_VERSION,
    _accepted_disclaimer_version,
)
from tests._helpers import _resolve_dialog


def _build(window):
    return window._build_disclaimer_dialog()


def test_disclaimer_offers_explicit_labels_and_app_icons(window):
    msg, acknowledge, not_now, dont_show = _build(window)
    try:
        assert acknowledge.text() == tr("disclaimer.acknowledge")
        assert not_now.text() == tr("disclaimer.not_now")
        assert dont_show.text() == tr("disclaimer.dont_show")
        assert not acknowledge.icon().isNull()
        assert not not_now.icon().isNull()
        assert msg.defaultButton() is acknowledge
        assert msg.escapeButton() is not_now
    finally:
        msg.deleteLater()


def test_acknowledge_with_dont_show_persists_the_version(window, settings, monkeypatch):
    prompt = _build(window)
    prompt[3].setChecked(True)
    monkeypatch.setattr(window, "_build_disclaimer_dialog", lambda: prompt)
    _resolve_dialog(monkeypatch, tr("disclaimer.acknowledge"))

    try:
        assert window._show_disclaimer() is True
        assert settings.value(_DISCLAIMER_VERSION_KEY, 0, int) == DISCLAIMER_VERSION
    finally:
        prompt[0].deleteLater()


def test_defer_does_not_persist_an_acknowledgement(window, settings, monkeypatch):
    prompt = _build(window)
    prompt[3].setChecked(True)
    monkeypatch.setattr(window, "_build_disclaimer_dialog", lambda: prompt)
    _resolve_dialog(monkeypatch, tr("disclaimer.not_now"))

    try:
        assert window._show_disclaimer() is False
        assert not settings.contains(_DISCLAIMER_VERSION_KEY)
    finally:
        prompt[0].deleteLater()


def test_closing_without_a_click_does_not_acknowledge(window, settings, monkeypatch):
    prompt = _build(window)
    prompt[3].setChecked(True)
    monkeypatch.setattr(window, "_build_disclaimer_dialog", lambda: prompt)
    _resolve_dialog(monkeypatch, None)

    try:
        assert window._show_disclaimer() is False
        assert not settings.contains(_DISCLAIMER_VERSION_KEY)
    finally:
        prompt[0].deleteLater()


def test_an_accepted_version_skips_the_dialog(window, settings, monkeypatch):
    settings.setValue(_DISCLAIMER_VERSION_KEY, DISCLAIMER_VERSION)
    built: list[int] = []
    monkeypatch.setattr(window, "_build_disclaimer_dialog", lambda: built.append(1))

    assert window._show_disclaimer() is True
    assert built == []


def test_legacy_boolean_counts_as_version_one(window, settings):
    settings.setValue(_LEGACY_DISCLAIMER_KEY, True)

    assert _accepted_disclaimer_version(settings) == 1
