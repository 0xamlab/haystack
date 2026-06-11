"""Pluggable object store for repository-intelligence artifacts (Wave B8 foundation).

The data-durability fix: durable RI artifacts (snapshot/triage manifests, decision plans,
simulations, source archives) currently live on one node's local volume — lose that volume
and every tenant's repository data is gone, and a second API/worker replica can't read it.
This module is the abstraction those artifacts move onto so they survive a node loss and are
readable from any replica.

Two backends, one interface:
  - LocalFsBackend  — node-local filesystem (the current behavior; the default, backward
    compatible).
  - S3Backend       — S3/MinIO, reusing storage_service's egress-guarded boto3 client (so the
    self-hosted/air-gapped fail-closed egress policy applies; loopback MinIO is allowed).

Keys are TENANT-SCOPED and path-safe:
  repository_intelligence/tenants/<org>/repositories/<repo>/<kind>/<artifact_id>
org_id / run id segments are server-derived + validated, so one tenant can't read or overwrite
another's artifacts (and there's no path traversal).

Backend selection is OPT-IN: ALGENTA_RI_OBJECT_STORE=s3 routes to S3/MinIO; anything else keeps
the node-local filesystem. This is the FOUNDATION — the read/write call-site migration in
repository_intelligence_runtime.py / repository_intelligence_storage.py (and the
materialized_snapshot/worktree scratch, which stays node-local) is staged on top of it.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_DEFAULT_PREFIX = "repository_intelligence"


def artifact_key(
    *,
    org_id: str,
    repository_id: str,
    kind: str,
    artifact_id: str,
    prefix: str = _DEFAULT_PREFIX,
) -> str:
    """Build a tenant-scoped, path-safe object key. Every segment is validated so a caller
    value can't traverse out of its tenant prefix or collide across tenants."""
    for label, part in (
        ("org_id", org_id),
        ("repository_id", repository_id),
        ("kind", kind),
        ("artifact_id", artifact_id),
    ):
        if not _KEY_SEGMENT.match(str(part)):
            raise ValueError(f"unsafe object-store key segment {label}={part!r}")
    return f"{prefix}/tenants/{org_id}/repositories/{repository_id}/{kind}/{artifact_id}"


@runtime_checkable
class ObjectStoreBackend(Protocol):
    name: str

    def put_json(self, key: str, payload: dict[str, Any]) -> None: ...
    def get_json(self, key: str) -> dict[str, Any] | None: ...
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get_bytes(self, key: str) -> bytes | None: ...
    def exists(self, key: str) -> bool: ...


class LocalFsBackend:
    """Node-local filesystem backend (the current behavior). Atomic writes; keys are confined
    under the store root."""

    name = "local_fs"

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        p = (self._root / key).resolve()
        root = self._root.resolve()
        if p != root and not str(p).startswith(str(root) + os.sep):
            raise ValueError(f"object key escaped the store root: {key!r}")
        return p

    def put_json(self, key: str, payload: dict[str, Any]) -> None:
        self.put_bytes(
            key,
            json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def get_json(self, key: str) -> dict[str, Any] | None:
        data = self.get_bytes(key)
        return json.loads(data.decode("utf-8")) if data is not None else None

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get_bytes(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Backend:
    """S3/MinIO backend. Reuses storage_service's egress-guarded boto3 client so the
    fail-closed self-hosted/air-gapped policy + audit apply to every artifact write."""

    name = "s3"

    def __init__(self, bucket: str) -> None:
        self._bucket = bucket

    def _client(self) -> Any:
        from apps.api_server.services.storage_service import _ensure_bucket, _get_client

        client = _get_client()
        _ensure_bucket(client, self._bucket)
        return client

    def put_json(self, key: str, payload: dict[str, Any]) -> None:
        self.put_bytes(
            key,
            json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def get_json(self, key: str) -> dict[str, Any] | None:
        data = self.get_bytes(key)
        return json.loads(data.decode("utf-8")) if data is not None else None

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client().put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get_bytes(self, key: str) -> bytes | None:
        try:
            response = self._client().get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            return body.read()
        except Exception as exc:  # noqa: BLE001 — a missing key / not-found is "no object"
            logger.debug("ri_object_store_get_miss", key=key, error=str(exc))
            return None

    def exists(self, key: str) -> bool:
        return self.get_bytes(key) is not None


def object_store_mode() -> str:
    return (os.environ.get("ALGENTA_RI_OBJECT_STORE") or "local").strip().lower()


def get_object_store() -> ObjectStoreBackend:
    """Select the artifact backend. Opt-in S3 via ALGENTA_RI_OBJECT_STORE=s3 (fail-closed: a
    configured-but-unavailable S3 client raises); otherwise the node-local filesystem."""
    if object_store_mode() == "s3":
        from apps.api_server.services.storage_service import _bucket_name

        return S3Backend(_bucket_name())
    from apps.api_server.services.repository_intelligence_runtime import _runtime_dir

    return LocalFsBackend(_runtime_dir() / "object_store")
