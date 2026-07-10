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

import contextlib
import json
import os
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import structlog

from apps.api_server.services.secret_redaction import redact_secret_fields

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
        # B10: defense-in-depth — never persist a credential-shaped field (incl. the S3 mirror).
        self.put_bytes(
            key,
            json.dumps(redact_secret_fields(payload), indent=2, sort_keys=True).encode("utf-8"),
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
        # B10: defense-in-depth — never persist a credential-shaped field (incl. the S3 mirror).
        self.put_bytes(
            key,
            json.dumps(redact_secret_fields(payload), indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def get_json(self, key: str) -> dict[str, Any] | None:
        data = self.get_bytes(key)
        return json.loads(data.decode("utf-8")) if data is not None else None

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client().put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get_bytes(self, key: str) -> bytes | None:
        # Resolve the client OUTSIDE the try: _client() -> storage_service._get_client/_ensure_bucket
        # raise ResultStorageUnavailableError on egress-deny / connectivity / bucket failure, and an
        # availability fault must PROPAGATE so a caller can map it to a retryable 503 — it must never
        # be masked as a "no object" miss (a fail-closed requirement: a missing-because-unreachable
        # object is NOT the same as a definitively-absent one). Only a genuine not-found maps to None.
        client = self._client()
        try:
            response = client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            return body.read()
        except Exception as exc:  # noqa: BLE001 — distinguish not-found from a real fault below
            code = ""
            response_meta = getattr(exc, "response", None)
            if isinstance(response_meta, dict):
                code = str(response_meta.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                logger.debug("ri_object_store_get_miss", key=key, error=str(exc))
                return None
            # Auth / throttling / connectivity / 5xx / mid-read failure: do NOT swallow — re-raise so
            # the fault surfaces (callers translate it to a retryable 503, never a 404/410).
            raise

    def exists(self, key: str) -> bool:
        # Inherits get_bytes' semantics: returns False only for a genuine not-found, and PROPAGATES
        # availability faults (does not return False). Not used for fail-closed disambiguation.
        return self.get_bytes(key) is not None


class AzureBlobBackend:
    """Azure Blob Storage backend — the native store for a customer-hosted Azure gateway.

    Mirrors :class:`S3Backend`'s contract, including its fail-closed ``get_bytes`` semantics: a
    genuine not-found returns ``None``, but any availability fault (auth/throttle/connectivity)
    PROPAGATES so a caller maps it to a retryable 503 — a missing-because-unreachable object is
    never confused with a definitively-absent one.

    Auth prefers a **connection string** (``AZURE_STORAGE_CONNECTION_STRING``); otherwise it uses
    the account URL (``AZURE_STORAGE_ACCOUNT_URL``) with ``DefaultAzureCredential`` — i.e. the
    ACA container's **managed identity**, so no storage secret is distributed. ``client_factory``
    is injectable for tests, so this is unit-testable without the Azure SDK installed.
    """

    name = "azure_blob"

    def __init__(
        self,
        container: str,
        *,
        account_url: str | None = None,
        connection_string: str | None = None,
        client_factory: Any | None = None,
    ) -> None:
        self._container = container
        self._account_url = account_url
        self._connection_string = connection_string
        self._client_factory = client_factory
        self._cc: Any | None = None

    def _container_client(self) -> Any:
        if self._cc is not None:
            return self._cc
        if self._client_factory is not None:
            self._cc = self._client_factory()
            return self._cc
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:  # pragma: no cover - exercised only on a real Azure deploy
            raise RuntimeError(
                "azure-storage-blob is required for ALGENTA_RI_OBJECT_STORE=azure_blob"
            ) from exc
        if self._connection_string:
            svc = BlobServiceClient.from_connection_string(self._connection_string)
        elif self._account_url:
            from azure.identity import DefaultAzureCredential

            svc = BlobServiceClient(
                account_url=self._account_url, credential=DefaultAzureCredential()
            )
        else:
            raise RuntimeError(
                "Azure Blob backend needs AZURE_STORAGE_CONNECTION_STRING or "
                "AZURE_STORAGE_ACCOUNT_URL"
            )
        cc = svc.get_container_client(self._container)
        with contextlib.suppress(Exception):  # container already exists is the normal case
            cc.create_container()
        self._cc = cc
        return cc

    def put_json(self, key: str, payload: dict[str, Any]) -> None:
        self.put_bytes(
            key,
            json.dumps(redact_secret_fields(payload), indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def get_json(self, key: str) -> dict[str, Any] | None:
        data = self.get_bytes(key)
        return json.loads(data.decode("utf-8")) if data is not None else None

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._container_client().upload_blob(name=key, data=data, overwrite=True)

    def get_bytes(self, key: str) -> bytes | None:
        cc = self._container_client()
        try:
            return cc.download_blob(key).readall()
        except Exception as exc:  # noqa: BLE001 - distinguish not-found from a real fault
            if _is_azure_not_found(exc):
                logger.debug("ri_object_store_get_miss", key=key, backend="azure_blob")
                return None
            # Auth/throttle/connectivity/5xx: PROPAGATE (never mask as a miss).
            raise

    def exists(self, key: str) -> bool:
        return self.get_bytes(key) is not None


def _is_azure_not_found(exc: Exception) -> bool:
    """True only for a definitive blob-not-found (ResourceNotFoundError / HTTP 404)."""
    if type(exc).__name__ == "ResourceNotFoundError":
        return True
    return getattr(exc, "status_code", None) == 404


def object_store_mode() -> str:
    return (os.environ.get("ALGENTA_RI_OBJECT_STORE") or "local").strip().lower()


def get_object_store() -> ObjectStoreBackend:
    """Select the artifact backend. Opt-in S3 via ALGENTA_RI_OBJECT_STORE=s3 (fail-closed: a
    configured-but-unavailable S3 client raises); otherwise the node-local filesystem."""
    mode = object_store_mode()
    if mode == "s3":
        from apps.api_server.services.storage_service import _bucket_name

        return S3Backend(_bucket_name())
    if mode == "azure_blob":
        container = (os.environ.get("AZURE_BLOB_CONTAINER") or "").strip()
        if not container:
            raise RuntimeError("ALGENTA_RI_OBJECT_STORE=azure_blob requires AZURE_BLOB_CONTAINER")
        return AzureBlobBackend(
            container,
            account_url=(os.environ.get("AZURE_STORAGE_ACCOUNT_URL") or "").strip() or None,
            connection_string=(os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or "").strip()
            or None,
        )
    from apps.api_server.services.repository_intelligence_runtime import _runtime_dir

    return LocalFsBackend(_runtime_dir() / "object_store")
