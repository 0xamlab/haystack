"""Object storage service for persisted full simulation results."""

from __future__ import annotations

import json
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
