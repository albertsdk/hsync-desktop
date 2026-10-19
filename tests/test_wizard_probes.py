# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Server probe tests: status mapping without touching the network."""

from __future__ import annotations

import ssl
import urllib.error

import hsync_desktop.engine.probes as probes
from hsync_desktop.engine.probes import probe_server_bucket, probe_server_health


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


class TestHealthProbe:
    def test_200_is_ok(self, monkeypatch):
        monkeypatch.setattr(probes, "urlopen", lambda *a, **k: _Response(200))
        result = probe_server_health("https://host:9753", ssl_context=_ssl_context())
        assert result.ok is True and result.status == 200 and result.authenticated is False

    def test_http_error_keeps_status(self, monkeypatch):
        def raise_http(*_a, **_k):
            raise urllib.error.HTTPError("u", 503, "boom", {}, None)

        monkeypatch.setattr(probes, "urlopen", raise_http)
        result = probe_server_health("https://host:9753", ssl_context=_ssl_context())
        assert result.ok is False and result.status == 503

    def test_unreachable(self, monkeypatch):
        def raise_url(*_a, **_k):
            raise urllib.error.URLError("no route")

        monkeypatch.setattr(probes, "urlopen", raise_url)
        result = probe_server_health("https://host:9753", ssl_context=_ssl_context())
        assert result.ok is False and result.status is None
        assert result.reason == probes.REASON_UNREACHABLE


class TestBucketProbe:
    def test_sends_bearer_and_hits_bucket_path(self, monkeypatch):
        seen: dict = {}

        def capture(request, **_k):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            return _Response(200)

        monkeypatch.setattr(probes, "urlopen", capture)
        result = probe_server_bucket(
            "https://host:9753/", "data", "sekret", ssl_context=_ssl_context()
        )
        assert result.ok is True and result.authenticated is True
        assert seen["url"] == "https://host:9753/api/v1/buckets/data"
        assert seen["auth"] == "Bearer sekret"

    def test_404_is_reported_as_missing(self, monkeypatch):
        def raise_http(*_a, **_k):
            raise urllib.error.HTTPError("u", 404, "nope", {}, None)

        monkeypatch.setattr(probes, "urlopen", raise_http)
        result = probe_server_bucket("https://host:9753", "data", "k", ssl_context=_ssl_context())
        assert result.ok is False and result.status == 404
