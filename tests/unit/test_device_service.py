from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.api_server.services.device_service import (
    DeviceBindingError,
    _hosted_request_device_info,
    _resolve_api_key,
    _validate_device_info_lengths,
    hosted_api_device_binding_required,
)
from apps.api_server.services.plan_limits import (
    effective_device_limit,
    validate_api_key_device_limit,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.anyio
async def test_resolve_api_key_rejects_expired_key() -> None:
    expired_key = SimpleNamespace(
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(expired_key)))

    resolved = await _resolve_api_key("de_live_expired_key", session)

    assert resolved is None


@pytest.mark.anyio
async def test_resolve_api_key_accepts_unexpired_key() -> None:
    active_key = SimpleNamespace(
        expires_at=datetime.now(UTC) + timedelta(days=730),
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(active_key)))

    resolved = await _resolve_api_key("de_live_active_key", session)

    assert resolved is active_key


def test_effective_device_limit_uses_per_key_cap_under_enterprise() -> None:
    assert effective_device_limit("enterprise", 2) == 2
    assert effective_device_limit("enterprise", 0) == 0


def test_effective_device_limit_clamps_invalid_unlimited_override_on_finite_plan() -> None:
    assert effective_device_limit("pro", None) == 5
    assert effective_device_limit("pro", 3) == 3
    assert effective_device_limit("pro", 0) == 5


def test_validate_api_key_device_limit_enforces_plan_cap() -> None:
    assert validate_api_key_device_limit("pro", None) is None
    assert validate_api_key_device_limit("pro", 5) == 5
    assert validate_api_key_device_limit("enterprise", 0) == 0
    assert validate_api_key_device_limit("enterprise", 12) == 12

    with pytest.raises(ValueError, match="at most 5 device\\(s\\) per key"):
        validate_api_key_device_limit("pro", 6)

    with pytest.raises(ValueError, match="does not support unlimited devices per key"):
        validate_api_key_device_limit("pro", 0)


def test_validate_device_info_lengths_accepts_runtime_shaped_metadata() -> None:
    _validate_device_info_lengths(
        {
            "device_id": "device-1234567890abcd",
            "platform": "linux",
            "platform_version": "6.8.0",
            "hostname_hash": "deadbeef" * 8,
            "sdk_version": "algenta-ts-live/1.0.0",
        }
    )


def test_validate_device_info_lengths_rejects_overlong_sdk_version() -> None:
    with pytest.raises(ValueError, match="sdk_version"):
        _validate_device_info_lengths(
            {
                "device_id": "device-1234567890abcd",
                "platform": "linux",
                "platform_version": "6.8.0",
                "hostname_hash": "deadbeef" * 8,
                "sdk_version": "a" * 129,
            }
        )


def test_hosted_api_device_binding_required_only_for_configured_finite_caps() -> None:
    assert (
        hosted_api_device_binding_required(
            {
                "org_id": uuid.uuid4(),
                "key_id": uuid.uuid4(),
                "key_prefix": "de_live_abcd",
                "user_id": None,
                "plan": "enterprise",
                "device_limit": 2,
                "device_limit_configured": True,
                "role": "member",
                "email": "api_key",
            }
        )
        is True
    )
    assert (
        hosted_api_device_binding_required(
            {
                "org_id": uuid.uuid4(),
                "key_id": uuid.uuid4(),
                "key_prefix": "de_live_abcd",
                "user_id": None,
                "plan": "enterprise",
                "device_limit": 0,
                "device_limit_configured": True,
                "role": "member",
                "email": "api_key",
            }
        )
        is False
    )
    assert (
        hosted_api_device_binding_required(
            {
                "org_id": uuid.uuid4(),
                "key_id": uuid.uuid4(),
                "key_prefix": "de_live_abcd",
                "user_id": None,
                "plan": "pro",
                "device_limit": 5,
                "device_limit_configured": False,
                "role": "member",
                "email": "api_key",
            }
        )
        is False
    )


def test_hosted_request_device_info_requires_device_id_header() -> None:
    request = SimpleNamespace(headers={})

    with pytest.raises(DeviceBindingError, match="finite number of devices"):
        _hosted_request_device_info(request)


def test_hosted_request_device_info_accepts_header_metadata() -> None:
    request = SimpleNamespace(
        headers={
            "X-Codna-Device-Id": "hosted-device-000001",
            "X-Codna-Platform": "linux",
            "X-Codna-Platform-Version": "6.8.0",
            "X-Codna-Hostname-Hash": "deadbeef" * 8,
            "X-Codna-SDK-Version": "algenta-ts/1.0.0",
            "User-Agent": "algenta-ts/1.0.0",
        }
    )

    info = _hosted_request_device_info(request)

    assert info == {
        "device_id": "hosted-device-000001",
        "platform": "linux",
        "platform_version": "6.8.0",
        "hostname_hash": "deadbeef" * 8,
        "sdk_version": "algenta-ts/1.0.0",
    }


def test_hosted_request_device_info_requires_hostname_hash_for_capped_keys() -> None:
    request = SimpleNamespace(
        headers={
            "X-Codna-Device-Id": "hosted-device-000001",
            "X-Codna-Platform": "linux",
            "X-Codna-Platform-Version": "6.8.0",
            "X-Codna-SDK-Version": "algenta-ts/1.0.0",
            "User-Agent": "algenta-ts/1.0.0",
        }
    )

    with pytest.raises(DeviceBindingError, match="finite number of devices"):
        _hosted_request_device_info(request)
