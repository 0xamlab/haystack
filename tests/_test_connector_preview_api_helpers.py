"""Shared imports + helpers for test_connector_preview_api_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-4/tests/test_connector_preview_api.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import asyncio

import threading

import time

from datetime import UTC, datetime

from types import SimpleNamespace

from typing import Any

import pytest

from apps.api_server.db.session import get_db

from apps.api_server.middleware.auth import get_current_org, get_redis

from apps.api_server.services.connectors.preview_cache import (
    ConnectorBrowsePreviewOutcome,
    clear_inline_preview_browse_cache,
    clear_inline_preview_inflight,
    clear_inline_preview_test_cache,
    run_distributed_inline_preview_browse_once,
    run_distributed_inline_preview_test_once,
    run_inline_preview_once,
)

from apps.api_server.services.connectors.tester import ConnectorTestOutcome

class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[object, float | None]] = {}
        self._lock = threading.Lock()

    def _get_live_entry(self, key: str) -> tuple[object, float | None] | None:
        entry = self._values.get(key)
        if entry is None:
            return None
        _, expires_at = entry
        if expires_at is not None and expires_at <= time.time():
            self._values.pop(key, None)
            return None
        return entry

    async def incr(self, _key: str) -> int:
        with self._lock:
            entry = self._get_live_entry(_key)
            current = 0 if entry is None else int(entry[0])
            next_value = current + 1
            expires_at = None if entry is None else entry[1]
            self._values[_key] = (next_value, expires_at)
            return next_value

    async def expire(self, _key: str, _ttl: int) -> bool:
        with self._lock:
            entry = self._get_live_entry(_key)
            if entry is None:
                return False
            value, _ = entry
            self._values[_key] = (value, time.time() + _ttl)
            return True

    async def get(self, key: str) -> object | None:
        with self._lock:
            entry = self._get_live_entry(key)
            return None if entry is None else entry[0]

    async def set(
        self,
        key: str,
        value: object,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        with self._lock:
            entry = self._get_live_entry(key)
            if nx and entry is not None:
                return False
            expires_at = time.time() + ex if ex is not None else None
            self._values[key] = (value, expires_at)
            return True

    async def delete(self, key: str) -> int:
        with self._lock:
            existed = self._get_live_entry(key) is not None
            self._values.pop(key, None)
            return 1 if existed else 0

    async def eval(self, _script: str, _numkeys: int, key: str, token: str, ttl: int) -> int:
        with self._lock:
            entry = self._get_live_entry(key)
            if entry is None:
                return 0
            value, _ = entry
            if str(value) != token:
                return 0
            self._values[key] = (value, time.time() + ttl)
            return 1

class _FakeDbSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

@pytest.fixture
async def connector_preview_client(app, client):
    clear_inline_preview_test_cache()
    clear_inline_preview_browse_cache()
    clear_inline_preview_inflight()
    fake_redis = _FakeRedis()
    fake_auth: dict[str, Any] = {
        "org_id": "org_a",
        "role": "member",
        "user_id": "u1",
        "key_id": "k1",
    }
    app.dependency_overrides[get_current_org] = lambda: fake_auth
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        yield client
    finally:
        clear_inline_preview_test_cache()
        clear_inline_preview_browse_cache()
        clear_inline_preview_inflight()
        app.dependency_overrides.clear()

async def _successful_browse_outcome() -> ConnectorBrowsePreviewOutcome:
    return ConnectorBrowsePreviewOutcome(
        items=[{"id": "cache:key", "label": "cache:key", "kind": "key"}],
        message="1 key available.",
        discovery={
            "scope_noun": "keyspace",
            "returned_count": 1,
            "count_kind": "sample",
        },
        labels={"entity_noun": "key", "row_noun": "value"},
    )



__all__ = [
    "annotations",
    "asyncio",
    "threading",
    "time",
    "UTC",
    "datetime",
    "SimpleNamespace",
    "Any",
    "pytest",
    "get_db",
    "get_current_org",
    "get_redis",
    "ConnectorBrowsePreviewOutcome",
    "clear_inline_preview_browse_cache",
    "clear_inline_preview_inflight",
    "clear_inline_preview_test_cache",
    "run_distributed_inline_preview_browse_once",
    "run_distributed_inline_preview_test_once",
    "run_inline_preview_once",
    "ConnectorTestOutcome",
    "_FakeRedis",
    "_FakeDbSession",
    "connector_preview_client",
    "_successful_browse_outcome",
]
