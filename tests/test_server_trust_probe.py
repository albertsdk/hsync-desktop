# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""The authenticated probe must never send the API key unverified."""

from __future__ import annotations

import ssl

from hsync_desktop.engine import server_trust_probe as stp
from hsync_desktop.engine.probes import ServerProbeResult

FP = "aa" * 32
CHANGED = "bb" * 32


def _trusted(*_args, **_kwargs) -> ServerProbeResult:
    return ServerProbeResult(True, 200, 1, False)


def _untrusted(*_args, **_kwargs) -> ServerProbeResult:
    return ServerProbeResult(False, None, 1, False, "unreachable")


def _resolve(policy: str, *, insecure: bool = False) -> stp.BucketTrust:
    return stp.resolve_bucket_trust(
        base_url="https://host:9753",
        policy=policy,
        insecure=insecure,
        ca_cert="",
        binary="hsync",
        timeout=5.0,
    )


def test_insecure_and_none_use_an_unverified_context():
    for trust in (_resolve("none"), _resolve("auto", insecure=True)):
        assert trust.reason == ""
        assert trust.ssl_context is not None
        assert trust.ssl_context.verify_mode == ssl.CERT_NONE


def test_a_trusted_chain_needs_no_pin_for_auto(monkeypatch):
    monkeypatch.setattr(stp, "probe_server_health", _trusted)
    monkeypatch.setattr(stp, "list_server_trust", lambda _binary: [])

    trust = _resolve("auto")

    assert trust.reason == ""
    assert trust.pinned is False
    assert trust.ssl_context is not None
    assert trust.ssl_context.verify_mode == ssl.CERT_REQUIRED


def test_auto_pins_a_first_sighting_and_uses_the_certificate(monkeypatch):
    added: list[str] = []
    sentinel = ssl.create_default_context()
    monkeypatch.setattr(stp, "probe_server_health", _untrusted)
    monkeypatch.setattr(stp, "list_server_trust", lambda _binary: [])
    monkeypatch.setattr(stp, "fetch_server_certificate", lambda *_a, **_k: (FP, "PEM"))
    monkeypatch.setattr(stp, "certificate_ssl_context", lambda _pem: sentinel)
    monkeypatch.setattr(
        stp, "add_server_trust", lambda _b, _h, fingerprint, _p: added.append(fingerprint) or True
    )

    trust = _resolve("auto")

    assert trust.reason == ""
    assert trust.pinned is True
    assert trust.ssl_context is sentinel
    assert added == [FP]


def test_strict_without_a_pin_refuses(monkeypatch):
    monkeypatch.setattr(stp, "probe_server_health", _untrusted)
    monkeypatch.setattr(stp, "list_server_trust", lambda _binary: [])
    monkeypatch.setattr(stp, "fetch_server_certificate", lambda *_a, **_k: (FP, "PEM"))

    trust = _resolve("strict")

    assert trust.ssl_context is None
    assert trust.reason == stp.REASON_TRUST_MISSING


def test_ask_without_a_pin_does_not_send_the_key(monkeypatch):
    monkeypatch.setattr(stp, "probe_server_health", _untrusted)
    monkeypatch.setattr(stp, "list_server_trust", lambda _binary: [])
    monkeypatch.setattr(stp, "fetch_server_certificate", lambda *_a, **_k: (FP, "PEM"))

    trust = _resolve("ask")

    assert trust.ssl_context is None
    assert trust.reason == stp.REASON_TRUST_MISSING


def test_a_changed_pin_is_refused(monkeypatch):
    monkeypatch.setattr(stp, "probe_server_health", _untrusted)
    monkeypatch.setattr(
        stp,
        "list_server_trust",
        lambda _binary: [{"host": "host", "port": 9753, "fingerprint": CHANGED}],
    )
    monkeypatch.setattr(stp, "fetch_server_certificate", lambda *_a, **_k: (FP, "PEM"))

    trust = _resolve("auto")

    assert trust.ssl_context is None
    assert trust.reason == stp.REASON_TRUST_CHANGED


def test_a_matching_pin_proceeds(monkeypatch):
    sentinel = ssl.create_default_context()
    monkeypatch.setattr(stp, "probe_server_health", _untrusted)
    monkeypatch.setattr(
        stp,
        "list_server_trust",
        lambda _binary: [{"host": "host", "port": 9753, "fingerprint": FP}],
    )
    monkeypatch.setattr(stp, "fetch_server_certificate", lambda *_a, **_k: (FP, "PEM"))
    monkeypatch.setattr(stp, "certificate_ssl_context", lambda _pem: sentinel)

    trust = _resolve("strict")

    assert trust.reason == ""
    assert trust.ssl_context is sentinel
    assert trust.pinned is False
