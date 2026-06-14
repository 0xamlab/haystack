"""Object storage service for persisted full simulation results."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Protocol, cast

import structlog

from apps.api_server.config import SettingsProxy
from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    async_http_request,
    aws_endpoint_url,
    enforce_egress_sync,
)

logger = structlog.get_logger(__name__)
settings = SettingsProxy()


class ResultStorageUnavailableError(RuntimeError):
    """Raised when object storage is required but unavailable."""


@dataclass(frozen=True)
class StoredResultReference:
    blob_ref: str
    result_url: str
    storage_backend: str
    size_bytes: int


class _S3ClientProtocol(Protocol):
    def head_bucket(self, **kwargs: Any) -> object: ...

    def create_bucket(self, **kwargs: Any) -> object: ...

    def put_bucket_lifecycle_configuration(
        self,
        **kwargs: Any,
    ) -> object: ...

    def put_object(
        self,
        **kwargs: Any,
    ) -> object: ...

    def list_objects_v2(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def generate_presigned_url(
        self,
        client_method: str,
        **kwargs: Any,
    ) -> str: ...


def _bucket_name() -> str:
    return settings.s3_bucket_name or "simulation-results"


def _object_key(org_id: uuid.UUID, run_id: uuid.UUID) -> str:
    return f"{org_id}/{run_id}.json"


def _blob_ref(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def _get_client(*, audit_context: EgressAuditContext | None = None) -> _S3ClientProtocol:
    """Build an S3-compatible client from shared storage settings."""
    try:
        import boto3
    except ImportError as exc:
        raise ResultStorageUnavailableError(
            "boto3 is required for object storage result persistence."
        ) from exc

    try:
        enforce_egress_sync(
            aws_endpoint_url(
                aws_service_name="s3",
                region_name=settings.s3_region,
                endpoint_url=settings.s3_endpoint_url,
            ),
            surface="result_storage_client",
            explicit_configured=True,
            egress_class="operator_service",
            audit_context=audit_context,
        )
        client = boto3.client(
            service_name="s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        return cast(_S3ClientProtocol, client)
    except Exception as exc:
        raise ResultStorageUnavailableError("Failed to initialize object storage client.") from exc


# Per-org prefix under which the repository-intelligence object store keys every artifact
# (mirrors repository_intelligence_object_store.artifact_key: <prefix>/tenants/<org>/...). Kept as a
# literal here to avoid a circular import (that module imports this one for its S3 client).
_RI_TENANT_PREFIX = "repository_intelligence/tenants"


def repository_object_store_is_s3() -> bool:
    """True when the repository-intelligence object store routes to S3/MinIO (opt-in). Storage-cap
    accounting sums the durable S3 footprint; the node-local backend is not metered."""
    return (os.environ.get("ALGENTA_RI_OBJECT_STORE") or "local").strip().lower() == "s3"


def compute_org_storage_bytes(org_id: uuid.UUID | str) -> int:
    """Sum the bytes an org currently stores in the repository-intelligence S3 bucket.

    Source of truth for the storage cap: a live ``ListObjectsV2`` sum over the org's tenant prefix,
    so it always reflects S3 lifecycle expiry (90-day TTL) with no counter to drift. Returns 0 when
    the S3 backend isn't active (node-local self-host) or on ANY error — fail-OPEN, because a storage
    cap must never turn a transient S3 blip into a hard request failure (it is best-effort, like the
    managed-LLM spend meter). Synchronous (boto3); call via ``asyncio.to_thread`` from async code."""
    if not repository_object_store_is_s3():
        return 0
    prefix = f"{_RI_TENANT_PREFIX}/{org_id}/"
    try:
        client = _get_client()
        bucket = _bucket_name()
        total = 0
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []) or []:
                total += int(obj.get("Size", 0) or 0)
            if resp.get("IsTruncated"):
                token = resp.get("NextContinuationToken")
                if not token:
                    break
            else:
                break
        return total
    except Exception as exc:
        logger.debug("compute_org_storage_bytes_failed", org_id=str(org_id), error=str(exc))
        return 0


def _ensure_bucket(client: _S3ClientProtocol, bucket_name: str) -> None:
    """Create the bucket when missing or raise a storage availability error."""
    try:
        client.head_bucket(Bucket=bucket_name)
        return
    except Exception as exc:
        logger.debug("storage_bucket_head_failed", bucket=bucket_name, error=str(exc))

    try:
        client.create_bucket(Bucket=bucket_name)
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "expire-old-results",
                        "Status": "Enabled",
                        "Expiration": {"Days": 90},
                    }
                ]
            },
        )
        logger.info("storage_bucket_created", bucket=bucket_name)
    except Exception as exc:
        raise ResultStorageUnavailableError(
            f"Failed to create or configure object storage bucket '{bucket_name}'."
        ) from exc


async def store_result(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    result_data: dict[str, Any],
) -> StoredResultReference:
    """
    Persist the full simulation envelope in object storage.

    The canonical persistence path is object storage whenever result storage is enabled.
    Callers decide whether storage unavailability is fatal or can be tolerated.
    """
    result_json = json.dumps(result_data, default=str)
    size_bytes = len(result_json.encode("utf-8"))
    bucket_name = _bucket_name()
    object_key = _object_key(org_id, run_id)
    client = _get_client(audit_context=EgressAuditContext(org_id=org_id))
    _ensure_bucket(client, bucket_name)

    try:
        client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=result_json.encode("utf-8"),
            ContentType="application/json",
        )
        result_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_key},
            ExpiresIn=7 * 86400,
        )
    except Exception as exc:
        raise ResultStorageUnavailableError(
            f"Failed to upload simulation result to object storage for run {run_id}."
        ) from exc

    logger.info(
        "result_stored_in_object_storage",
        run_id=str(run_id),
        bucket=bucket_name,
        object_key=object_key,
        size_kb=size_bytes // 1024,
    )
    return StoredResultReference(
        blob_ref=_blob_ref(bucket_name, object_key),
        result_url=result_url,
        storage_backend="s3",
        size_bytes=size_bytes,
    )


async def get_result(result_url: str, *, org_id: uuid.UUID | None = None) -> dict[str, Any] | None:
    """Download a persisted result from object storage using a pre-signed URL."""
    try:
        response = await async_http_request(
            method="GET",
            url=result_url,
            surface="result_storage_fetch",
            explicit_configured=True,
            egress_class="operator_service",
            audit_context=EgressAuditContext(org_id=org_id) if org_id else None,
            client_kwargs={"timeout": 30},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return cast(dict[str, Any], data)
        logger.warning("result_fetch_invalid_payload", url=result_url[:80])
        return None
    except Exception as exc:
        logger.warning("result_fetch_failed", url=result_url[:80], error=str(exc))
        return None


def generate_presigned_download_url(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    expires_in: int = 3600,
) -> str | None:
    """Generate a fresh pre-signed URL for a persisted run payload."""
    try:
        client = _get_client(audit_context=EgressAuditContext(org_id=org_id))
        return str(
            client.generate_presigned_url(
                "get_object",
                Params={"Bucket": _bucket_name(), "Key": _object_key(org_id, run_id)},
                ExpiresIn=expires_in,
            )
        )
    except ResultStorageUnavailableError as exc:
        logger.warning("presigned_url_unavailable", run_id=str(run_id), error=str(exc))
        return None
    except Exception as exc:
        logger.warning("presigned_url_failed", run_id=str(run_id), error=str(exc))
        return None
