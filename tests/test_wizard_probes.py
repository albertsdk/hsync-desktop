# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Server probe tests: status mapping without touching the network."""

from __future__ import annotations

import io
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


class TestCreateBucket:
    """``POST /buckets?bucket=<name>``: 201 and 409 both mean the share is there."""

    def test_201_is_ok_and_posts_the_name_as_a_query_param(self, monkeypatch):
        seen: dict = {}

        def capture(request, **_k):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["auth"] = request.get_header("Authorization")
            return _Response(201)

        monkeypatch.setattr(probes, "urlopen", capture)
        result = probes.create_server_bucket(
            "https://host:9753/", "barbara", "key", ssl_context=_ssl_context()
        )

        assert result.ok is True and result.status == 201
        # The create route has no path placeholder: the name is a query param.
        assert seen["url"] == "https://host:9753/api/v1/buckets?bucket=barbara"
        assert seen["method"] == "POST"
        assert seen["auth"] == "Bearer key"

    def test_409_already_exists_is_ok(self, monkeypatch):
        def raise_http(*_a, **_k):
            raise urllib.error.HTTPError("u", 409, "exists", {}, None)

        monkeypatch.setattr(probes, "urlopen", raise_http)
        result = probes.create_server_bucket(
            "https://host", "barbara", "key", ssl_context=_ssl_context()
        )

        assert result.ok is True and result.status == 409

    def test_403_quota_names_the_limit(self, monkeypatch):
        body = b'{"info": "Bucket quota exceeded for account", "max_buckets_per_account": 3}'

        def raise_http(*_a, **_k):
            raise urllib.error.HTTPError("u", 403, "quota", {}, io.BytesIO(body))

        monkeypatch.setattr(probes, "urlopen", raise_http)
        result = probes.create_server_bucket(
            "https://host", "barbara", "key", ssl_context=_ssl_context()
        )

        assert result.ok is False and result.status == 403
        assert result.reason == probes.REASON_QUOTA
        assert result.limit == 3

    def test_403_without_a_quota_body_is_a_rejected_key(self, monkeypatch):
        def raise_http(*_a, **_k):
            raise urllib.error.HTTPError("u", 403, "forbidden", {}, io.BytesIO(b"{}"))

        monkeypatch.setattr(probes, "urlopen", raise_http)
        result = probes.create_server_bucket(
            "https://host", "barbara", "key", ssl_context=_ssl_context()
        )

        assert result.ok is False and result.reason == probes.REASON_UNAUTHORIZED
        assert result.limit is None


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


def _health_then_bucket(monkeypatch, health, bucket, seen: list[str] | None = None):
    """Patch ``urlopen``: answer /health and the bucket path independently."""

    def dispatch(request, **_kwargs):
        url = request.full_url
        if seen is not None:
            seen.append(url)
        answer = health if url.endswith("/health") else bucket
        if isinstance(answer, int):
            if 200 <= answer < 300:
                return _Response(answer)
            raise urllib.error.HTTPError("u", answer, "boom", {}, None)
        raise answer

    monkeypatch.setattr(probes, "urlopen", dispatch)


class TestBucketAccessProbe:
    """The shared health → bucket sequence and its reason codes."""

    def test_200_is_ok_with_no_reason(self, monkeypatch):
        _health_then_bucket(monkeypatch, 200, 200)
        result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "data", "k", ssl_context=_ssl_context()
        )
        assert result.ok is True and result.status == 200
        assert reason == ""

    def test_a_dead_server_is_not_reported_as_a_missing_share(self, monkeypatch):
        seen: list[str] = []
        _health_then_bucket(monkeypatch, 503, 200, seen)
        result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "data", "k", ssl_context=_ssl_context()
        )
        assert reason == "server_error" and result.status == 503
        assert all("/api/v1/buckets/" not in url for url in seen)

    def test_unreachable_health(self, monkeypatch):
        _health_then_bucket(monkeypatch, urllib.error.URLError("no route"), 200)
        _result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "data", "k", ssl_context=_ssl_context()
        )
        assert reason == "unreachable"

    def test_404_is_share_missing(self, monkeypatch):
        _health_then_bucket(monkeypatch, 200, 404)
        result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "data", "k", ssl_context=_ssl_context()
        )
        assert reason == "share_missing" and result.status == 404

    def test_400_is_a_bad_name(self, monkeypatch):
        _health_then_bucket(monkeypatch, 200, 400)
        _result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "da ta", "k", ssl_context=_ssl_context()
        )
        assert reason == "bad_share"

    def test_401_and_403_are_unauthorized(self, monkeypatch):
        for status in (401, 403):
            _health_then_bucket(monkeypatch, 200, status)
            _result, reason = probes.probe_server_bucket_access(
                "https://host:9753", "data", "k", ssl_context=_ssl_context()
            )
            assert reason == "unauthorized", status

    def test_5xx_on_the_bucket_is_a_server_error(self, monkeypatch):
        _health_then_bucket(monkeypatch, 200, 502)
        _result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "data", "k", ssl_context=_ssl_context()
        )
        assert reason == "server_error"

    def test_a_bucket_fetch_failure_is_unreachable(self, monkeypatch):
        _health_then_bucket(monkeypatch, 200, urllib.error.URLError("reset"))
        _result, reason = probes.probe_server_bucket_access(
            "https://host:9753", "data", "k", ssl_context=_ssl_context()
        )
        assert reason == "unreachable"


class TestServerFailureReason:
    def test_rejected_key_is_unauthorized(self):
        assert probes.server_failure_reason(probes.ServerProbeResult(False, 401, 1, True)) == (
            "unauthorized"
        )
        assert probes.server_failure_reason(probes.ServerProbeResult(False, 403, 1, True)) == (
            "unauthorized"
        )

    def test_server_side_fault(self):
        assert probes.server_failure_reason(probes.ServerProbeResult(False, 500, 1, False)) == (
            "server_error"
        )

    def test_network_failure_is_unreachable(self):
        assert probes.server_failure_reason(probes.ServerProbeResult(False, None, 1, False)) == (
            "unreachable"
        )
