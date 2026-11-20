# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Share access: confirm a bucket on the server, and provision a missing one.

One implementation for the three surfaces that meet a bucket name — the setup
wizard's connection step, the Settings dialog's bucket field, and the share
creation flow (which mints a name the server has never seen). Each used to
assemble the trust resolution, the probe and the create call itself, which is
how the three could disagree about when the API key may travel.

The key only leaves the process over the verified or certificate-confined context
``resolve_bucket_trust`` returns: a refused resolution fails closed instead of
falling back to an unverified connection. Both operations are blocking and belong
on a probe thread (the GUI runs them through ``AsyncProbe``).
"""

from __future__ import annotations

from dataclasses import dataclass

from hsync_desktop.engine.async_probe import ProbeOutcome
from hsync_desktop.engine.probes import (
    REASON_QUOTA,
    REASON_UNREACHABLE,
    create_server_bucket,
    probe_server_bucket_access,
)
from hsync_desktop.engine.server_trust_probe import (
    REASON_TRUST_PIN_FAILED,
    BucketTrust,
    pin_observed_fingerprint,
    resolve_bucket_trust,
)

__all__ = ["ShareTrust", "check_share_access", "provision_share_bucket"]


@dataclass(frozen=True)
class ShareTrust:
    """How one surface asks for the server's identity to be checked.

    ``policy`` is a ``TrustPolicy`` value; the wizard maps its single
    "trust this server's certificate" switch to ``auto``/``chain``, while the
    Settings and share flows pass the stored preference.
    """

    policy: str | None = None
    insecure: bool = False
    ca_cert: str = ""
    binary: str | None = None


def _resolve(base_url: str, trust: ShareTrust, timeout: float) -> BucketTrust:
    """Resolve the TLS context for one authenticated call (no store writes)."""
    return resolve_bucket_trust(
        base_url=base_url,
        policy=trust.policy,
        insecure=trust.insecure,
        ca_cert=trust.ca_cert,
        binary=trust.binary,
        timeout=timeout,
    )


def _refused(resolved: BucketTrust) -> ProbeOutcome:
    """The outcome of a trust resolution that may not carry the API key."""
    return ProbeOutcome(
        False,
        None,
        fingerprint=resolved.fingerprint,
        reason=resolved.reason or REASON_UNREACHABLE,
    )


def check_share_access(
    base_url: str,
    bucket: str,
    api_key: str,
    *,
    trust: ShareTrust,
    timeout: float,
    pin_first_sighting: bool = True,
) -> ProbeOutcome:
    """Confirm *api_key* may use *bucket* on *base_url*.

    A first sighting (TOFU) is pinned only once the check passed, so a failed
    check never stores an identity that could not be used. The wizard's
    connection test passes ``pin_first_sighting=False``: it probes before the
    user has chosen the identity policy, so Finish pins with the draft's choice
    instead.
    """
    resolved = _resolve(base_url, trust, timeout)
    if resolved.reason or resolved.ssl_context is None:
        return _refused(resolved)
    result, reason = probe_server_bucket_access(
        base_url, bucket, api_key, ssl_context=resolved.ssl_context, timeout=timeout
    )
    if reason:
        return ProbeOutcome(False, result.status, fingerprint=resolved.fingerprint, reason=reason)
    pins = pin_first_sighting and resolved.needs_pin
    if pins and not pin_observed_fingerprint(trust.binary, base_url, resolved.fingerprint):
        return ProbeOutcome(
            False,
            result.status,
            fingerprint=resolved.fingerprint,
            reason=REASON_TRUST_PIN_FAILED,
        )
    return ProbeOutcome(True, result.status, fingerprint=resolved.fingerprint, pinned=pins)


def provision_share_bucket(
    base_url: str,
    bucket: str,
    api_key: str,
    *,
    trust: ShareTrust,
    timeout: float,
    pin_first_sighting: bool = True,
) -> ProbeOutcome:
    """Create *bucket* on the server, then confirm the account can use it.

    A 409 is a success (the bucket is there, which is what the caller wanted).
    A quota refusal keeps its own reason and the server's limit, because only
    deleting a share or raising the cap can help.
    """
    resolved = _resolve(base_url, trust, timeout)
    if resolved.reason or resolved.ssl_context is None:
        return _refused(resolved)
    created = create_server_bucket(
        base_url, bucket, api_key, ssl_context=resolved.ssl_context, timeout=timeout
    )
    if not created.ok:
        reason = "create_quota" if created.reason == REASON_QUOTA else "create_failed"
        return ProbeOutcome(False, created.status, reason=reason, limit=created.limit)
    return check_share_access(
        base_url,
        bucket,
        api_key,
        trust=trust,
        timeout=timeout,
        pin_first_sighting=pin_first_sighting,
    )
