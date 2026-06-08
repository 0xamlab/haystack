"""Unit tests for API key generation and hashing in auth_service."""

import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api_server.services.auth_service import (
    consume_auth_session_dirty,
    generate_api_key,
    hash_api_key,
    is_api_key_expired,
    verify_api_key,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class TestGenerateApiKey:
    def test_key_format_live(self) -> None:
        raw_key, prefix, hashed = generate_api_key()
        assert raw_key.startswith("de_live_"), (
            f"Key should start with 'de_live_', got: {raw_key[:12]}"
        )

    def test_key_format_test(self) -> None:
        raw_key, prefix, hashed = generate_api_key(test=True)
        assert raw_key.startswith("de_test_"), (
            f"Key should start with 'de_test_', got: {raw_key[:12]}"
        )

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


class TestApiKeyExpiry:
    def test_is_api_key_expired_handles_none_future_and_past(self) -> None:
        now = datetime(2026, 5, 19, tzinfo=UTC)
        assert is_api_key_expired(None, now=now) is False
        assert is_api_key_expired(now + timedelta(days=1), now=now) is False
        assert is_api_key_expired(now - timedelta(seconds=1), now=now) is True

    @pytest.mark.anyio
    async def test_verify_api_key_rejects_expired_cached_key(self) -> None:
        expired_epoch = int((datetime.now(UTC) - timedelta(seconds=60)).timestamp())
        redis = SimpleNamespace(
            hgetall=AsyncMock(
                return_value={
                    b"org_id": str(uuid.uuid4()).encode(),
                    b"key_id": str(uuid.uuid4()).encode(),
                    b"plan": b"pro",
                    b"status": b"active",
                    b"role": b"member",
                    b"email": b"cached@example.com",
                    b"user_id": b"",
                    b"expires_at": str(expired_epoch).encode(),
                }
            ),
            delete=AsyncMock(return_value=1),
        )
        session = SimpleNamespace(execute=AsyncMock())

        result = await verify_api_key("de_live_cached_key", session, redis)

        assert result is None
        session.execute.assert_not_called()
        redis.delete.assert_awaited()

    @pytest.mark.anyio
    async def test_verify_api_key_reads_device_binding_metadata_from_cache(self) -> None:
        org_id = uuid.uuid4()
        key_id = uuid.uuid4()
        redis = SimpleNamespace(
            hgetall=AsyncMock(
                return_value={
                    b"org_id": str(org_id).encode(),
                    b"key_id": str(key_id).encode(),
                    b"key_prefix": b"de_live_cache",
                    b"plan": b"enterprise",
                    b"device_limit": b"2",
                    b"device_limit_configured": b"1",
                    b"status": b"active",
                    b"role": b"member",
                    b"email": b"cached@example.com",
                    b"user_id": b"",
                    b"expires_at": str(
                        int((datetime.now(UTC) + timedelta(days=30)).timestamp())
                    ).encode(),
                }
            ),
            delete=AsyncMock(return_value=0),
        )
        session = SimpleNamespace(execute=AsyncMock())

        result = await verify_api_key("de_live_cached_key", session, redis)

        assert result is not None
        assert result["org_id"] == org_id
        assert result["key_id"] == key_id
        assert result["key_prefix"] == "de_live_cache"
        assert result["device_limit"] == 2
        assert result["device_limit_configured"] is True
        session.execute.assert_not_called()

    @pytest.mark.anyio
    async def test_verify_api_key_rejects_expired_database_key(self) -> None:
        expired_key = SimpleNamespace(
            id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            user_id=None,
            status=SimpleNamespace(value="active"),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        session = SimpleNamespace(
            execute=AsyncMock(return_value=_ScalarResult(expired_key)),
        )
        redis = SimpleNamespace(
            hgetall=AsyncMock(return_value={}),
            hset=AsyncMock(),
            expire=AsyncMock(),
        )

        result = await verify_api_key("de_live_db_key", session, redis)

        assert result is None
        redis.hset.assert_not_called()
        redis.expire.assert_not_called()

    @pytest.mark.anyio
    async def test_verify_api_key_returns_device_binding_metadata_from_database(self) -> None:
        org_id = uuid.uuid4()
        key_id = uuid.uuid4()
        api_key = SimpleNamespace(
            id=key_id,
            org_id=org_id,
            user_id=None,
            key_prefix="de_live_db12",
            device_limit=2,
            status=SimpleNamespace(value="active"),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        org = SimpleNamespace(plan=SimpleNamespace(value="enterprise"))
        session = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    _ScalarResult(api_key),
                    _ScalarResult(org),
                    _ScalarResult(None),
                ]
            ),
        )
        redis = SimpleNamespace(
            hgetall=AsyncMock(return_value={}),
            hset=AsyncMock(),
            expire=AsyncMock(),
        )
        session.info = {}

        result = await verify_api_key("de_live_db_key", session, redis)

        assert result is not None
        assert result["org_id"] == org_id
        assert result["key_id"] == key_id
        assert result["key_prefix"] == "de_live_db12"
        assert result["device_limit"] == 2
        assert result["device_limit_configured"] is True
        redis.hset.assert_awaited()
        redis.expire.assert_awaited()
        assert consume_auth_session_dirty(session) is True
        assert consume_auth_session_dirty(session) is False
