"""Shared imports + helpers for test_resolve_api_contract_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-3/tests/test_resolve_api_contract.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import io

import pandas as pd

import pytest

from apps.api_server.middleware.auth import get_current_org, get_redis

from apps.api_server.routers import query as query_router

from apps.api_server.services.auto_planner import JoinHop, QueryPlan

class _RedisStub:
    async def incr(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 1

    async def expire(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def get(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return b"0"

    async def set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def setex(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def incrby(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 1

    async def ping(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return True

    async def hgetall(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return {}

    async def hset(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def aclose(self) -> None:
        return None

@pytest.fixture
def auth_overrides(app):
    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        }

    async def _fake_redis() -> _RedisStub:
        return _RedisStub()

    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = _fake_redis
    yield
    app.dependency_overrides.clear()
    query_router._RESOLVE_CACHE.clear()
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._GRAPH_NODE_CACHE.clear()
    query_router._DATASET_EXACT_COLUMN_CACHE.clear()
    query_router._DF_CACHE.clear()

def _ready_entry(
    source_id: str, name: str, schema_revision: str = "schema_rev_1"
) -> dict[str, str]:
    return {
        "id": source_id,
        "name": name,
        "schema_revision": schema_revision,
        "decision_mode": "deterministic_only",
        "visibility": "private",
        "owner_key_id": "key_resolve",
    }



__all__ = [
    "annotations",
    "io",
    "pd",
    "pytest",
    "get_current_org",
    "get_redis",
    "query_router",
    "JoinHop",
    "QueryPlan",
    "_RedisStub",
    "auth_overrides",
    "_ready_entry",
]
