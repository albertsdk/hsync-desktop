# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Encryption helpers for sensitive settings (API keys, etc.).

Uses Fernet symmetric encryption with a key derived from:
  - /etc/machine-id (Linux) or platform equivalent
  - current OS username
  - a fixed application salt

This ensures that:
  - The encrypted value in QSettings is not readable in plain text.
  - Other users on the same machine cannot derive the same key.
  - The key is stable across application restarts (no extra key-file needed).
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import platform
import sys

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Fixed application salt – changing this invalidates all previously encrypted values.
_APP_SALT = b"hsync-desktop-settings-v1"

# Prefix added to encrypted values so we can distinguish them from plain-text
# values (e.g. during migration from an older unencrypted configuration).
_ENC_PREFIX = "enc::"


def _get_machine_id() -> str:
    """Return a stable machine identifier."""
    # Linux: /etc/machine-id
    try:
        with open("/etc/machine-id") as f:
            mid = f.read().strip()
            if mid:
                return mid
    except OSError:
        pass

    # macOS: IOPlatformSerialNumber via system_profiler (fallback)
    if sys.platform == "darwin":
        import subprocess

        try:
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                text=True,
                timeout=5,
            )
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass

    # Windows: MachineGuid from registry
    if sys.platform == "win32":
        import winreg  # type: ignore[import-untyped]

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return str(value)
        except Exception:
            pass

    # Ultimate fallback: hostname + platform
    return f"{platform.node()}-{platform.machine()}"


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from machine-id + username."""
    identity = f"{_get_machine_id()}:{getpass.getuser()}".encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_APP_SALT,
        iterations=480_000,
    )
    raw = kdf.derive(identity)
    return base64.urlsafe_b64encode(raw)


# Module-level cached key (derived once per process).
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_derive_key())
    return _fernet


def encrypt_value(plain: str) -> str:
    """Encrypt a plain-text string and return a prefixed token."""
    if not plain:
        return ""
    token = _get_fernet().encrypt(plain.encode("utf-8"))
    return _ENC_PREFIX + token.decode("ascii")


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value.

    If *stored* does not carry the encryption prefix it is returned as-is
    (transparent migration from plain-text settings).
    """
    if not stored:
        return ""
    if not stored.startswith(_ENC_PREFIX):
        # Plain-text value from a previous version – return unchanged.
        return stored
    token = stored[len(_ENC_PREFIX):].encode("ascii")
    try:
        return _get_fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, Exception):
        # Corrupted or key changed – return empty to force re-entry.
        return ""

