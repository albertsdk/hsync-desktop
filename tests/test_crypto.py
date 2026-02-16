# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.crypto module."""

import hsync_desktop.crypto as crypto


class TestEncryptionPrefix:
    """Test encryption prefix constant."""

    def test_enc_prefix(self):
        assert crypto._ENC_PREFIX == "enc::"


class TestEncryptValue:
    """Test encrypt_value function."""

    def test_encrypt_empty_string(self):
        result = crypto.encrypt_value("")
        assert result == ""

    def test_encrypt_none_value(self):
        result = crypto.encrypt_value("")
        assert result == ""

    def test_encrypt_returns_prefixed_token(self):
        result = crypto.encrypt_value("test-secret")
        assert result.startswith(crypto._ENC_PREFIX)

    def test_encrypt_produces_different_tokens(self):
        """Encrypting the same value twice should produce different tokens (due to IV)."""
        val = "my-secret-key"
        result1 = crypto.encrypt_value(val)
        result2 = crypto.encrypt_value(val)
        # Both should have prefix
        assert result1.startswith(crypto._ENC_PREFIX)
        assert result2.startswith(crypto._ENC_PREFIX)
        # But should be different due to random IV
        assert result1 != result2


class TestDecryptValue:
    """Test decrypt_value function."""

    def test_decrypt_empty_string(self):
        result = crypto.decrypt_value("")
        assert result == ""

    def test_decrypt_none_value(self):
        result = crypto.decrypt_value("")
        assert result == ""

    def test_decrypt_plain_text_returns_unchanged(self):
        """Values without encryption prefix should be returned as-is."""
        plain = "some-plain-text"
        result = crypto.decrypt_value(plain)
        assert result == plain

    def test_decrypt_encrypted_value(self):
        """Encrypt then decrypt should return original value."""
        original = "my-secret-api-key"
        encrypted = crypto.encrypt_value(original)
        decrypted = crypto.decrypt_value(encrypted)
        assert decrypted == original

    def test_decrypt_invalid_token_returns_empty(self):
        """Invalid encryption token should return empty string."""
        result = crypto.decrypt_value("enc::invalid-token")
        assert result == ""

    def test_decrypt_wrong_prefix_but_encoded(self):
        """Token with wrong prefix but valid base64 should be treated as plain."""
        result = crypto.decrypt_value("wrong::somebase64data")
        # Should be returned as-is since it doesn't have the correct prefix
        assert result == "wrong::somebase64data"

    def test_roundtrip_various_strings(self):
        """Test roundtrip with various string types."""
        test_values = [
            "simple",
            "with spaces",
            "with/slash",
            "with\nnewline",
            "unicode: èàü",
            "numbers: 12345",
            "special: !@#$%^&*()",
        ]
        for original in test_values:
            encrypted = crypto.encrypt_value(original)
            decrypted = crypto.decrypt_value(encrypted)
            assert decrypted == original, f"Failed for: {original}"


class TestAppSalt:
    """Test application salt constant."""

    def test_app_salt_is_bytes(self):
        assert isinstance(crypto._APP_SALT, bytes)

    def test_app_salt_contains_version(self):
        assert b"v1" in crypto._APP_SALT
