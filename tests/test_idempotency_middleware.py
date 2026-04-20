from __future__ import annotations

import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api_server.middleware.idempotency import IdempotencyMiddleware
from apps.api_server.middleware.request_id import RequestIDMiddleware


class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[object, float | None]] = {}
        self._lock = threading.Lock()

    async def get(self, key: str):
        with self._lock:
            entry = self._values.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and expires_at <= time.time():
                self._values.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: object, ex: int | None = None, nx: bool = False):
        with self._lock:
            existing = self._values.get(key)
            if nx and existing is not None:
                _, expires_at = existing
                if expires_at is None or expires_at > time.time():
                    return False
            expires_at = time.time() + ex if ex is not None else None
            self._values[key] = (value, expires_at)
            return True

    async def delete(self, key: str) -> int:
        with self._lock:
            existed = key in self._values
            self._values.pop(key, None)
            return 1 if existed else 0


def _build_app(redis_client: object | None = None, delay_seconds: float = 0.0) -> tuple[FastAPI, dict[str, int]]:
    app = FastAPI()
    counters = {"creates": 0, "queries": 0}
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.state.redis = redis_client

    @app.post("/v1/widgets")
    async def create_widget(payload: dict) -> dict:
        if delay_seconds:
            import asyncio

            await asyncio.sleep(delay_seconds)
        counters["creates"] += 1
        return {"create_count": counters["creates"], "payload": payload}

    @app.get("/v1/widgets")
    async def list_widgets() -> dict:
        return {"ok": True}

    @app.post("/v1/query")
    async def query_widget(payload: dict) -> dict:
        if delay_seconds:
            import asyncio

            await asyncio.sleep(delay_seconds)
        counters["queries"] += 1
        return {"query_count": counters["queries"], "payload": payload}

    return app, counters


def test_duplicate_write_replays_original_response() -> None:
    app, counters = _build_app()
    with TestClient(app) as client:
        headers = {"Idempotency-Key": "idem-1", "X-Request-Id": "req-first"}
        first = client.post("/v1/widgets", json={"name": "alpha"}, headers=headers)
        second = client.post("/v1/widgets", json={"name": "alpha"}, headers={"Idempotency-Key": "idem-1"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert counters["creates"] == 1
    assert second.headers["X-Request-Id"] != first.headers["X-Request-Id"]


def test_duplicate_key_with_different_payload_conflicts() -> None:
    app, counters = _build_app()
    with TestClient(app) as client:
        first = client.post("/v1/widgets", json={"name": "alpha"}, headers={"Idempotency-Key": "idem-2"})
        second = client.post("/v1/widgets", json={"name": "beta"}, headers={"Idempotency-Key": "idem-2"})

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_key_conflict"
    assert counters["creates"] == 1


def test_requests_without_idempotency_key_do_not_collapse() -> None:
    app, counters = _build_app()
    with TestClient(app) as client:
        first = client.post("/v1/widgets", json={"name": "alpha"})
        second = client.post("/v1/widgets", json={"name": "alpha"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["create_count"] == 1
    assert second.json()["create_count"] == 2
    assert counters["creates"] == 2


def test_read_endpoints_ignore_idempotency_key() -> None:
    app, counters = _build_app()
    with TestClient(app) as client:
        response = client.get("/v1/widgets", headers={"Idempotency-Key": "idem-read"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert counters["creates"] == 0


def test_duplicate_write_replays_from_shared_redis_store() -> None:
    redis_client = _FakeRedis()
    app_one, counters = _build_app(redis_client=redis_client)
    app_two, _ = _build_app(redis_client=redis_client)

    with TestClient(app_one) as first_client:
        first = first_client.post("/v1/widgets", json={"name": "alpha"}, headers={"Idempotency-Key": "idem-redis"})

    with TestClient(app_two) as second_client:
        second = second_client.post("/v1/widgets", json={"name": "alpha"}, headers={"Idempotency-Key": "idem-redis"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert counters["creates"] == 1


def test_concurrent_write_conflict_returns_explicit_409() -> None:
    redis_client = _FakeRedis()
    app, counters = _build_app(redis_client=redis_client, delay_seconds=0.15)
    results: list[tuple[int, dict]] = []

    def _send(body: dict[str, str]) -> None:
        with TestClient(app) as client:
            response = client.post("/v1/widgets", json=body)
            results.append((response.status_code, response.json()))

    first = threading.Thread(target=_send, args=({"name": "first"},))
    second = threading.Thread(target=_send, args=({"name": "second"},))
    first.start()
    time.sleep(0.03)
    second.start()
    first.join()
    second.join()

    statuses = sorted(status for status, _ in results)
    assert statuses == [200, 409]
    assert counters["creates"] == 1
    conflict = next(body for status, body in results if status == 409)
    assert conflict["error"]["code"] == "resource_write_conflict"


def test_concurrent_query_posts_do_not_trigger_write_conflict() -> None:
    redis_client = _FakeRedis()
    app, counters = _build_app(redis_client=redis_client, delay_seconds=0.15)
    results: list[tuple[int, dict]] = []

    def _send(body: dict[str, str]) -> None:
        with TestClient(app) as client:
            response = client.post("/v1/query", json=body)
            results.append((response.status_code, response.json()))

    first = threading.Thread(target=_send, args=({"name": "first"},))
    second = threading.Thread(target=_send, args=({"name": "second"},))
    first.start()
    time.sleep(0.03)
    second.start()
    first.join()
    second.join()

    assert sorted(status for status, _ in results) == [200, 200]
    assert counters["queries"] == 2
