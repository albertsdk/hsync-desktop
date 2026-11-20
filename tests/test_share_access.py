# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The shared share-access check: trust resolution, pinning and provisioning.

The wizard's connection step, the Settings dialog's bucket field and the share
creation flow all go through this module, so the API-key safety and TOFU rules
are proven once here instead of once per caller.
"""

from __future__ import annotations

import ssl

import hsync_desktop.engine.share_access as share_access
from hsync_desktop.engine.probes import REASON_QUOTA, ServerProbeResult
from hsync_desktop.engine.server_trust_probe import (
    REASON_TRUST_PIN_FAILED,
    BucketTrust,
)

TRUST = share_access.ShareTrust(policy="auto", binary="hsync")


def _context() -> ssl.SSLContext:
    return ssl._create_unverified_context()


def _resolves_to(monkeypatch, *, needs_pin: bool = False, fingerprint: str = "fp") -> None:
    monkeypatch.setattr(
        share_access,
        "resolve_bucket_trust",
        lambda **_kwargs: BucketTrust(_context(), fingerprint=fingerprint, needs_pin=needs_pin),
    )


def test_a_refused_trust_never_sends_the_key(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(
        share_access,
        "resolve_bucket_trust",
        lambda **_kwargs: BucketTrust(None, reason="trust_missing"),
    )
    monkeypatch.setattr(
        share_access,
        "probe_server_bucket_access",
        lambda *_a, **_k: sent.append("probe") or (ServerProbeResult(False, None, 0, False), "x"),
    )

    outcome = share_access.check_share_access("https://host", "team", "key", trust=TRUST, timeout=5)

    assert outcome.ok is False
    assert outcome.reason == "trust_missing"
    assert sent == []


def test_a_passing_first_sighting_is_pinned(monkeypatch):
    pinned: list[tuple[str | None, str, str]] = []
    _resolves_to(monkeypatch, needs_pin=True)
    monkeypatch.setattr(
        share_access,
        "probe_server_bucket_access",
        lambda *_a, **_k: (ServerProbeResult(True, 200, 0, True), ""),
    )
    monkeypatch.setattr(
        share_access,
        "pin_observed_fingerprint",
        lambda binary, base, fingerprint: pinned.append((binary, base, fingerprint)) or True,
    )

    outcome = share_access.check_share_access("https://host", "team", "key", trust=TRUST, timeout=5)

    assert outcome.ok is True
    assert outcome.pinned is True
    assert pinned == [("hsync", "https://host", "fp")]


def test_the_wizard_never_writes_the_store(monkeypatch):
    """The connection step leaves pinning to Finish (the draft picks the policy)."""
    pinned: list[str] = []
    _resolves_to(monkeypatch, needs_pin=True)
    monkeypatch.setattr(
        share_access,
        "probe_server_bucket_access",
        lambda *_a, **_k: (ServerProbeResult(True, 200, 0, True), ""),
    )
    monkeypatch.setattr(
        share_access,
        "pin_observed_fingerprint",
        lambda *_a, **_k: pinned.append("pinned") or True,
    )

    outcome = share_access.check_share_access(
        "https://host", "team", "key", trust=TRUST, timeout=5, pin_first_sighting=False
    )

    assert outcome.ok is True
    assert outcome.pinned is False
    assert pinned == []


def test_a_pin_that_cannot_be_stored_blocks_the_check(monkeypatch):
    _resolves_to(monkeypatch, needs_pin=True)
    monkeypatch.setattr(
        share_access,
        "probe_server_bucket_access",
        lambda *_a, **_k: (ServerProbeResult(True, 200, 0, True), ""),
    )
    monkeypatch.setattr(share_access, "pin_observed_fingerprint", lambda *_a, **_k: False)

    outcome = share_access.check_share_access("https://host", "team", "key", trust=TRUST, timeout=5)

    assert outcome.ok is False
    assert outcome.reason == REASON_TRUST_PIN_FAILED


def test_provisioning_creates_then_rechecks(monkeypatch):
    calls: list[str] = []
    _resolves_to(monkeypatch)
    monkeypatch.setattr(
        share_access,
        "create_server_bucket",
        lambda *_a, **_k: calls.append("create") or ServerProbeResult(True, 201, 0, True),
    )
    monkeypatch.setattr(
        share_access,
        "probe_server_bucket_access",
        lambda *_a, **_k: calls.append("check") or (ServerProbeResult(True, 200, 0, True), ""),
    )

    outcome = share_access.provision_share_bucket(
        "https://host", "team", "key", trust=TRUST, timeout=5
    )

    assert outcome.ok is True
    assert calls == ["create", "check"]


def test_a_quota_refusal_keeps_the_limit(monkeypatch):
    _resolves_to(monkeypatch)
    monkeypatch.setattr(
        share_access,
        "create_server_bucket",
        lambda *_a, **_k: ServerProbeResult(False, 403, 0, True, reason=REASON_QUOTA, limit=3),
    )

    outcome = share_access.provision_share_bucket(
        "https://host", "team", "key", trust=TRUST, timeout=5
    )

    assert outcome.ok is False
    assert outcome.reason == "create_quota"
    assert outcome.limit == 3


def test_a_probe_failure_passes_its_reason(monkeypatch):
    _resolves_to(monkeypatch)
    monkeypatch.setattr(
        share_access,
        "probe_server_bucket_access",
        lambda *_a, **_k: (ServerProbeResult(False, 404, 0, True), "share_missing"),
    )

    outcome = share_access.check_share_access("https://host", "team", "key", trust=TRUST, timeout=5)

    assert outcome.ok is False
    assert outcome.reason == "share_missing"
    assert outcome.status == 404
