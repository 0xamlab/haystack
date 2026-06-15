from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from apps.api_server.middleware import auth as auth_module
from apps.api_server.services.auth_service import mark_auth_session_dirty


def _request(headers: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(),
        url=SimpleNamespace(path="/v1/query"),
        headers=headers or {},
    )


def _auth_context(is_platform: bool = False) -> auth_module.AuthContext:
    return {
        "org_id": "org-123",
        "key_id": "key-123",
        "key_prefix": "de_live_test",
        "user_id": None,
        "plan": "enterprise",
        "device_limit": 0,
        "device_limit_configured": False,
        "role": "member",
        "email": "api_key",
        "is_platform": is_platform,
        "workspace_id": None,
    }


@pytest.mark.anyio
async def test_get_current_org_skips_commit_for_cached_read_only_auth(monkeypatch) -> None:
    db = SimpleNamespace(commit=AsyncMock(), info={})
    request = _request()
    response = Response()

    async def _verify(raw_key: str, passed_db: object, redis_client: object):
        assert raw_key == "de_live_cached"
        assert passed_db is db
        return _auth_context()

    monkeypatch.setattr(auth_module, "verify_api_key", _verify)
    monkeypatch.setattr(auth_module, "bind_hosted_api_device", AsyncMock(return_value=None))

    ctx = await auth_module.get_current_org(
        request,
        response,
        db=db,
        redis_client=object(),
        api_key_value="de_live_cached",
        bearer=None,
    )

    assert ctx["org_id"] == "org-123"
    assert request.state.org_id == "org-123"
    db.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_get_current_org_commits_when_verify_api_key_mutates_state(monkeypatch) -> None:
    db = SimpleNamespace(commit=AsyncMock(), info={})
    request = _request()
    response = Response()

    async def _verify(raw_key: str, passed_db: object, redis_client: object):
        assert passed_db is db
        mark_auth_session_dirty(passed_db)
        return _auth_context()

    monkeypatch.setattr(auth_module, "verify_api_key", _verify)
    monkeypatch.setattr(auth_module, "bind_hosted_api_device", AsyncMock(return_value=None))

    await auth_module.get_current_org(
        request,
        response,
        db=db,
        redis_client=object(),
        api_key_value="de_live_db",
        bearer=None,
    )

    db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_get_current_org_commits_when_device_binding_writes(monkeypatch) -> None:
    db = SimpleNamespace(commit=AsyncMock(), info={})
    request = _request()
    response = Response()

    async def _verify(raw_key: str, passed_db: object, redis_client: object):
        return _auth_context()

    monkeypatch.setattr(auth_module, "verify_api_key", _verify)
    monkeypatch.setattr(
        auth_module,
        "bind_hosted_api_device",
        AsyncMock(return_value={"device_id": "device-1", "binding_token": "token-1"}),
    )

    await auth_module.get_current_org(
        request,
        response,
        db=db,
        redis_client=object(),
        api_key_value="de_live_bound",
        bearer=None,
    )

    db.commit.assert_awaited_once()
    assert request.state.device_id == "device-1"
    assert response.headers["X-Codna-Device-Binding-Token"] == "token-1"


@pytest.mark.anyio
async def test_platform_key_assumes_workspace_from_header(monkeypatch) -> None:
    ws = uuid.uuid4()
    db = SimpleNamespace(commit=AsyncMock(), info={})
    request = _request(headers={"X-Workspace-Id": str(ws)})
    response = Response()

    async def _verify(raw_key, passed_db, redis_client):
        return _auth_context(is_platform=True)

    monkeypatch.setattr(auth_module, "verify_api_key", _verify)
    monkeypatch.setattr(auth_module, "bind_hosted_api_device", AsyncMock(return_value=None))

    ctx = await auth_module.get_current_org(
        request, response, db=db, redis_client=object(), api_key_value="de_platform", bearer=None
    )
    assert ctx["workspace_id"] == ws


@pytest.mark.anyio
async def test_tenant_key_cannot_assume_workspace(monkeypatch) -> None:
    db = SimpleNamespace(commit=AsyncMock(), info={})
    request = _request(headers={"X-Workspace-Id": str(uuid.uuid4())})
    response = Response()

    async def _verify(raw_key, passed_db, redis_client):
        return _auth_context(is_platform=False)

    monkeypatch.setattr(auth_module, "verify_api_key", _verify)
    monkeypatch.setattr(auth_module, "bind_hosted_api_device", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_org(
            request, response, db=db, redis_client=object(), api_key_value="de_tenant", bearer=None
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "workspace_scope_not_permitted"


@pytest.mark.anyio
async def test_invalid_workspace_header_rejected(monkeypatch) -> None:
    db = SimpleNamespace(commit=AsyncMock(), info={})
    request = _request(headers={"X-Workspace-Id": "not-a-uuid"})
    response = Response()

    async def _verify(raw_key, passed_db, redis_client):
        return _auth_context(is_platform=True)

    monkeypatch.setattr(auth_module, "verify_api_key", _verify)
    monkeypatch.setattr(auth_module, "bind_hosted_api_device", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_org(
            request, response, db=db, redis_client=object(), api_key_value="de_platform", bearer=None
        )
    assert exc.value.status_code == 400
