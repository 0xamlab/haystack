"""Shared imports + helpers for test_api_key_expiry_contract_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import json

from contextlib import contextmanager

from datetime import UTC, datetime, timedelta

from uuid import UUID, uuid4

import pytest

from fastapi import Depends, HTTPException

from fastapi.responses import JSONResponse, StreamingResponse

from httpx import ASGITransport, AsyncClient

from pydantic import BaseModel

from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal

from apps.api_server.middleware.auth import get_current_org, get_redis

from apps.api_server.models import (
    APIKey,
    APIKeyStatus,
    Organization,
    OrgPlan,
    OrgStatus,
    User,
    UserRole,
    UserStatus,
)

from apps.api_server.models.device import DeviceRegistration

from apps.api_server.services.auth_service import hash_api_key

class _RedisStub:
    async def hgetall(self, *_args, **_kwargs) -> dict[bytes, bytes]:
        return {}

    async def delete(self, *_args, **_kwargs) -> int:
        return 0

    async def hset(self, *_args, **_kwargs) -> int:
        return 1

    async def expire(self, *_args, **_kwargs) -> bool:
        return True

class _SyntheticValidationPayload(BaseModel):
    count: int

async def _seed_api_key(
    *,
    label: str,
    expires_at: datetime | None,
    plan: OrgPlan = OrgPlan.PRO,
) -> tuple[str, str]:
    raw_key = f"de_live_{uuid4().hex}{uuid4().hex[:8]}"
    slug = f"pytest-api-key-{uuid4().hex[:12]}"
    email = f"{slug}@example.com"

    async with AsyncSessionLocal() as session:
        org = Organization(
            name=f"Pytest {label}",
            slug=slug,
            plan=plan,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()

        user = User(
            org_id=org.id,
            email=email,
            password_hash="pytest-api-key-contract",
            name=f"Pytest {label}",
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(user)
        await session.flush()

        api_key = APIKey(
            org_id=org.id,
            user_id=user.id,
            label=label,
            key_prefix=raw_key[:12],
            hashed_key=hash_api_key(raw_key),
            status=APIKeyStatus.ACTIVE,
            expires_at=expires_at,
        )
        session.add(api_key)
        await session.commit()
        return raw_key, str(api_key.id)

async def _device_registration_snapshot(
    *,
    api_key_id: str,
    device_id: str,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeviceRegistration).where(
                DeviceRegistration.api_key_id == UUID(api_key_id),
                DeviceRegistration.device_id == device_id,
            )
        )
        row = result.scalar_one()
        return {
            "id": str(row.id),
            "heartbeat_count": row.heartbeat_count,
            "last_heartbeat_at": row.last_heartbeat_at,
            "status": getattr(row.status, "value", row.status),
        }

def _hosted_device_headers(
    raw_key: str,
    device_id: str,
    *,
    platform: str = "linux",
    platform_version: str = "6.8",
    hostname_hash: str = "deadbeef" * 8,
    sdk_version: str = "algenta-test/1.0.0",
    binding_token: str = "",
) -> dict[str, str]:
    headers = {
        "X-API-Key": raw_key,
        "X-Algenta-Device-Id": device_id,
        "X-Algenta-Platform": platform,
        "X-Algenta-Platform-Version": platform_version,
        "X-Algenta-Hostname-Hash": hostname_hash,
        "X-Algenta-SDK-Version": sdk_version,
    }
    if binding_token:
        headers["X-Algenta-Device-Binding-Token"] = binding_token
    return headers

@contextmanager
def _temporary_route(app, path: str, endpoint, *, methods: list[str]):
    app.router.add_api_route(path, endpoint, methods=methods)
    app.openapi_schema = None
    try:
        yield
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "endpoint", None) is not endpoint
        ]
        app.openapi_schema = None



__all__ = [
    "annotations",
    "json",
    "contextmanager",
    "UTC",
    "datetime",
    "timedelta",
    "UUID",
    "uuid4",
    "pytest",
    "Depends",
    "HTTPException",
    "JSONResponse",
    "StreamingResponse",
    "ASGITransport",
    "AsyncClient",
    "BaseModel",
    "select",
    "AsyncSessionLocal",
    "get_current_org",
    "get_redis",
    "APIKey",
    "APIKeyStatus",
    "Organization",
    "OrgPlan",
    "OrgStatus",
    "User",
    "UserRole",
    "UserStatus",
    "DeviceRegistration",
    "hash_api_key",
    "_RedisStub",
    "_SyntheticValidationPayload",
    "_seed_api_key",
    "_device_registration_snapshot",
    "_hosted_device_headers",
    "_temporary_route",
]
