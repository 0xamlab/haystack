from __future__ import annotations

import pytest

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org


class _UnexpectedDbSession:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("runs query should fail validation before touching the database")


@pytest.mark.anyio
async def test_runs_rejects_invalid_offset_query_before_database(app, client) -> None:
    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {
            "org_id": "org_a",
            "key_id": "k1",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        }

    async def _fake_db():  # type: ignore[no-untyped-def]
        yield _UnexpectedDbSession()

    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_db] = _fake_db

    try:
        response = await client.get("/v1/runs?limit=10&offset=';%20DROP%20TABLE%20x;--")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
