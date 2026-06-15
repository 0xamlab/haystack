"""Shared idempotency and write-conflict middleware for public v1 endpoints."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, cast

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_WRITE_METHODS = frozenset({"POST", "PATCH", "DELETE"})
_ENTRY_TTL_SECONDS = 24 * 60 * 60
_WRITE_LOCK_TTL_SECONDS = 30
_LOCAL_MAX_RESPONSES = 2048
# atomic compare-and-delete: only the token holder deletes the lock (closes the GET-then-DELETE
# TOCTOU where the lock could expire + be re-acquired by another request between read and delete).
_COMPARE_AND_DELETE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)
_READ_LIKE_POST_PATHS = frozenset(
    {
        "/v1/query",
        "/v1/verify",
        "/v1/map",
        "/v1/simulate",
        "/v1/simulate/what-if",
        "/v1/recommend",
        "/v1/compare",
        "/v1/decision",
        "/v1/optimize",
        "/v1/retrieve",
        "/v1/forecast",
    }
)

logger = structlog.get_logger(__name__)


@dataclass
class _StoredResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]
    media_type: str | None


@dataclass
class _StoredEnvelope:
    payload_hash: str
    response: _StoredResponse
    updated_at: float


class _RedisClientProtocol(Protocol):
    async def get(self, key: str) -> object: ...

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool | None = None,
    ) -> object: ...

    async def delete(self, key: str) -> object: ...

    async def eval(self, script: str, numkeys: int, *args: object) -> object: ...


class _BodyIteratorResponseProtocol(Protocol):
    body_iterator: AsyncIterator[bytes | str | memoryview]


class _LocalCoordinationStore:
    def __init__(self) -> None:
        self._responses: dict[str, _StoredEnvelope] = {}
        self._write_locks: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def get_response(self, key: str) -> _StoredEnvelope | None:
        async with self._lock:
            self._prune_locked()
            return self._responses.get(key)

    async def store_response(self, key: str, payload_hash: str, response: _StoredResponse) -> None:
        async with self._lock:
            self._prune_locked()
            self._responses[key] = _StoredEnvelope(
                payload_hash=payload_hash,
                response=response,
                updated_at=time.time(),
            )
            if len(self._responses) > _LOCAL_MAX_RESPONSES:
                overflow = len(self._responses) - _LOCAL_MAX_RESPONSES
                oldest = sorted(self._responses.items(), key=lambda item: item[1].updated_at)
                for stale_key, _ in oldest[:overflow]:
                    self._responses.pop(stale_key, None)

    async def acquire_write_lock(self, key: str, ttl_seconds: int) -> str | None:
        async with self._lock:
            self._prune_locked()
            current = self._write_locks.get(key)
            now = time.time()
            if current is not None and current[1] > now:
                return None
            token = uuid.uuid4().hex
            self._write_locks[key] = (token, now + ttl_seconds)
            return token

    async def release_write_lock(self, key: str, token: str) -> None:
        async with self._lock:
            current = self._write_locks.get(key)
            if current and current[0] == token:
                self._write_locks.pop(key, None)

    def _prune_locked(self) -> None:
        now = time.time()
        stale_responses = [
            key
            for key, envelope in self._responses.items()
            if now - envelope.updated_at > _ENTRY_TTL_SECONDS
        ]
        for key in stale_responses:
            self._responses.pop(key, None)

        stale_locks = [
            key for key, (_, expires_at) in self._write_locks.items() if expires_at <= now
        ]
        for key in stale_locks:
            self._write_locks.pop(key, None)


class _RedisCoordinationStore:
    def __init__(self, redis_client: _RedisClientProtocol) -> None:
        self._redis = redis_client

    async def get_response(self, key: str) -> _StoredEnvelope | None:
        raw = await self._redis.get(_response_storage_key(key))
        if raw is None:
            return None
        decoded = _decode_redis_value(raw)
        if not decoded:
            return None
        data = json.loads(decoded)
        return _StoredEnvelope(
            payload_hash=data["payload_hash"],
            response=_StoredResponse(
                status_code=int(data["status_code"]),
                body=base64.b64decode(data["body_b64"].encode("utf-8")),
                headers={str(k): str(v) for k, v in data.get("headers", {}).items()},
                media_type=data.get("media_type"),
            ),
            updated_at=float(data.get("updated_at", time.time())),
        )

    async def store_response(self, key: str, payload_hash: str, response: _StoredResponse) -> None:
        payload = json.dumps(
            {
                "payload_hash": payload_hash,
                "status_code": response.status_code,
                "body_b64": base64.b64encode(response.body).decode("utf-8"),
                "headers": response.headers,
                "media_type": response.media_type,
                "updated_at": time.time(),
            }
        )
        await self._redis.set(_response_storage_key(key), payload, ex=_ENTRY_TTL_SECONDS)

    async def acquire_write_lock(self, key: str, ttl_seconds: int) -> str | None:
        token = uuid.uuid4().hex
        acquired = await self._redis.set(
            _write_lock_storage_key(key),
            token,
            ex=ttl_seconds,
            nx=True,
        )
        if acquired:
            return token
        return None

    async def release_write_lock(self, key: str, token: str) -> None:
        # Single atomic compare-and-delete instead of GET-then-DELETE: between a separate read and
        # delete the lock could expire and be re-acquired by another request (new token), and the
        # stale holder would then delete THAT request's lock. The Lua eval makes the check+delete
        # indivisible so only the live token holder ever removes the key.
        await self._redis.eval(_COMPARE_AND_DELETE, 1, _write_lock_storage_key(key), token)


class _ResilientCoordinationStore:
    def __init__(
        self,
        primary: _RedisCoordinationStore,
        fallback: _LocalCoordinationStore,
    ) -> None:
        self._primary = primary
        self._active: _RedisCoordinationStore | _LocalCoordinationStore = primary
        self._fallback = fallback

    async def get_response(self, key: str) -> _StoredEnvelope | None:
        return await self._call("get_response", key)

    async def store_response(self, key: str, payload_hash: str, response: _StoredResponse) -> None:
        await self._call("store_response", key, payload_hash, response)

    async def acquire_write_lock(self, key: str, ttl_seconds: int) -> str | None:
        return await self._call("acquire_write_lock", key, ttl_seconds)

    async def release_write_lock(self, key: str, token: str) -> None:
        # Release against BOTH backends best-effort. acquire_write_lock may have landed on Redis
        # before a mid-request failover flipped _active to the local fallback (store_response/get
        # failing over), so releasing only _active would strand the Redis-held lock until its TTL —
        # a spurious resource_write_conflict (409) for a same-key retry within that window. The
        # token-compare (Lua compare-and-delete on Redis, token check locally) makes a release on the
        # backend that does NOT hold the lock a safe no-op, so releasing both is always correct.
        for store in (self._primary, self._fallback):
            try:
                await store.release_write_lock(key, token)
            except Exception as exc:  # noqa: BLE001 — best-effort; the lock TTL reclaims it
                logger.debug(
                    "idempotency_release_degraded", store=type(store).__name__, error=str(exc)
                )

    async def _call(self, method_name: str, *args: object) -> object:
        store = self._active
        try:
            method = getattr(store, method_name)
            return await method(*args)
        except Exception as exc:
            if store is self._fallback:
                raise
            logger.warning(
                "idempotency_store_unavailable",
                store="redis",
                fallback="local",
                operation=method_name,
                error=str(exc),
            )
            self._active = self._fallback
            fallback_method = getattr(self._fallback, method_name)
            return await fallback_method(*args)


_LOCAL_STORE = _LocalCoordinationStore()


def _response_storage_key(key: str) -> str:
    return f"idempotency:v1:response:{hashlib.sha256(key.encode('utf-8')).hexdigest()}"


def _write_lock_storage_key(key: str) -> str:
    return f"idempotency:v1:lock:{hashlib.sha256(key.encode('utf-8')).hexdigest()}"


def _decode_redis_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _coordination_store(
    request: Request,
) -> _LocalCoordinationStore | _ResilientCoordinationStore:
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        return _ResilientCoordinationStore(
            primary=_RedisCoordinationStore(cast(_RedisClientProtocol, redis_client)),
            fallback=_LOCAL_STORE,
        )
    return _LOCAL_STORE


def _principal_fingerprint(request: Request) -> str:
    auth = request.headers.get("Authorization", "").strip()
    legacy = request.headers.get("X-API-Key", "").strip()
    principal = auth or legacy or "anonymous"
    return hashlib.sha256(principal.encode("utf-8")).hexdigest()


def _payload_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


async def _read_response_body(response: Response) -> bytes:
    if getattr(response, "body", None) is not None:
        body = response.body
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode("utf-8")
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is None:
        return b""
    chunks: list[bytes] = []
    streaming_response = cast(_BodyIteratorResponseProtocol, response)
    async for chunk in streaming_response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk)
        elif isinstance(chunk, str):
            chunks.append(chunk.encode("utf-8"))
        else:
            chunks.append(bytes(chunk))
    return b"".join(chunks)


def _rebuild_response(stored: _StoredResponse) -> Response:
    headers = dict(stored.headers)
    headers.pop("content-length", None)
    return Response(
        content=stored.body,
        status_code=stored.status_code,
        headers=headers,
        media_type=stored.media_type,
    )


def _should_skip_write_protection(request: Request) -> bool:
    method = request.method.upper()
    path = request.url.path
    if method not in _WRITE_METHODS:
        return True
    if not path.startswith("/v1/"):
        return True
    if path.startswith("/v1/simulate/stream"):
        return True
    if method == "POST" and path in _READ_LIKE_POST_PATHS:
        return True
    if method == "POST" and path.startswith("/v1/connectors/") and path.endswith("/test"):
        return True
    return False


def _write_conflict_response(request: Request) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "resource_write_conflict",
                "message": (
                    "Another write is already in progress for this resource "
                    "scope. Retry after it completes."
                ),
                "request_id": request_id,
                "docs_url": "https://docs.codna.ai/errors/resource_write_conflict",
            }
        },
    )


def _idempotency_conflict_response(request: Request, issue: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "idempotency_key_conflict",
                "message": (
                    "The supplied Idempotency-Key was already used with a "
                    "different request payload."
                ),
                "details": [{"field": "Idempotency-Key", "issue": issue}],
                "request_id": request_id,
                "docs_url": "https://docs.codna.ai/errors/idempotency_key_conflict",
            }
        },
    )


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _should_skip_write_protection(request):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        body = await request.body()
        payload_hash = _payload_hash(body)
        principal_hash = _principal_fingerprint(request)
        write_scope_key = f"{request.method}:{request.url.path}:{principal_hash}"
        store = _coordination_store(request)

        if idempotency_key:
            response_scope_key = f"{write_scope_key}:{idempotency_key}"
            existing = await store.get_response(response_scope_key)
            if existing is not None:
                if existing.payload_hash != payload_hash:
                    return _idempotency_conflict_response(request, "idempotency_key_conflict")
                return _rebuild_response(existing.response)
        else:
            response_scope_key = ""

        token = await store.acquire_write_lock(write_scope_key, _WRITE_LOCK_TTL_SECONDS)
        if token is None:
            return _write_conflict_response(request)

        try:
            if idempotency_key:
                existing = await store.get_response(response_scope_key)
                if existing is not None:
                    if existing.payload_hash != payload_hash:
                        return _idempotency_conflict_response(request, "idempotency_key_conflict")
                    return _rebuild_response(existing.response)

            response = await call_next(request)
            if response.headers.get("content-type", "").startswith("text/event-stream"):
                return response

            body_bytes = await _read_response_body(response)
            stored = _StoredResponse(
                status_code=response.status_code,
                body=body_bytes,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            if idempotency_key:
                await store.store_response(response_scope_key, payload_hash, stored)
            return _rebuild_response(stored)
        finally:
            await store.release_write_lock(write_scope_key, token)
