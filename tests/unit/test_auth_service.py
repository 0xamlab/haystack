"""Unit tests for API key generation and hashing in auth_service."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api_server.services.auth_service import generate_api_key, hash_api_key


class TestGenerateApiKey:
    def test_key_format_live(self) -> None:
        raw_key, prefix, hashed = generate_api_key()
        assert raw_key.startswith("de_live_"), f"Key should start with 'de_live_', got: {raw_key[:12]}"

    def test_key_format_test(self) -> None:
        raw_key, prefix, hashed = generate_api_key(test=True)
        assert raw_key.startswith("de_test_"), f"Key should start with 'de_test_', got: {raw_key[:12]}"

    def test_key_prefix_matches_raw(self) -> None:
        raw_key, prefix, hashed = generate_api_key()
        assert raw_key.startswith(prefix), f"Prefix {prefix!r} not found at start of {raw_key[:20]}"

    def test_prefix_length(self) -> None:
        _, prefix, _ = generate_api_key()
        assert len(prefix) == 12, f"Expected prefix length 12, got {len(prefix)}"

    def test_hashed_key_is_64_chars(self) -> None:
        """SHA-256 hex digest is always 64 characters."""
        _, _, hashed = generate_api_key()
        assert len(hashed) == 64, f"Expected 64 char SHA-256 hash, got {len(hashed)}"

    def test_hashed_key_is_hex(self) -> None:
        _, _, hashed = generate_api_key()
        int(hashed, 16)  # Raises ValueError if not valid hex

    def test_two_keys_are_unique(self) -> None:
        raw_1, _, hash_1 = generate_api_key()
        raw_2, _, hash_2 = generate_api_key()
        assert raw_1 != raw_2
        assert hash_1 != hash_2

    def test_raw_key_not_stored_in_prefix(self) -> None:
        """The raw key beyond the prefix should not be derivable from prefix alone."""
        raw_key, prefix, hashed = generate_api_key()
        assert raw_key != prefix  # prefix is shorter than raw key

    def test_raw_key_min_length(self) -> None:
        """Raw key should be at least 40 chars (prefix + 32 random chars)."""
        raw_key, _, _ = generate_api_key()
        assert len(raw_key) >= 40


class TestHashApiKey:
    def test_hash_is_deterministic(self) -> None:
        raw = "de_live_testkey123456789012345678"
        assert hash_api_key(raw) == hash_api_key(raw)

    def test_different_keys_different_hashes(self) -> None:
        assert hash_api_key("key_a") != hash_api_key("key_b")

    def test_hash_matches_generate_output(self) -> None:
        """Hash of generated raw key should match the returned hash."""
        raw_key, _, hashed = generate_api_key()
        assert hash_api_key(raw_key) == hashed

    def test_raw_key_not_in_hash(self) -> None:
        """Raw key must not appear in its own hash (one-way)."""
        raw_key, _, hashed = generate_api_key()
        # The hash should not contain the raw key
        assert raw_key not in hashed
