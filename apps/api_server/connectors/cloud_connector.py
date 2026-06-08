"""Cloud object storage connector (S3, GCS, Azure Blob)."""

from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    async_http_request,
    audit_context_from_config,
    aws_endpoint_url,
    azure_endpoint_url,
    enforce_egress_sync,
    google_endpoint_url,
    sync_http_request,
)

from .base import BaseConnector, ConnectorRegistry
from .file_connector import FileConnector


@ConnectorRegistry.register
class S3Connector(BaseConnector):
    """Fetch data from an S3 (or S3-compatible) object.

    Config keys:
        bucket:       S3 bucket name (required).
        key:          Object key / path (required).
        file_type:    One of ``"csv"``, ``"tsv"``, ``"json"``, ``"parquet"``,
                      ``"excel"`` — auto-detected from key extension if omitted.
        region:       AWS region (default ``"us-east-1"``).
        aws_access_key_id / aws_secret_access_key:
                      Override credentials (uses IAM role / env vars if absent).
        access_key_id / secret_access_key:
                      Accepted aliases for AWS credentials.
        endpoint_url: Override endpoint for S3-compatible stores (MinIO, etc.).
        anonymous:    Read a public bucket/object without credentials.
        json_path:    Dot-path to records array inside a JSON file.
    """

    connector_type: str = "s3"

    async def fetch_data(self) -> list[dict[str, Any]]:
        bucket: str = self.config["bucket"]
        key: str = self.config["key"]
        file_type: str = self.config.get("file_type", "") or _ext_to_type(key)
        body = await _s3_get_bytes(self.config, bucket=bucket, key=key)

        return await _bytes_to_records(body, file_type, self.config)

    async def fetch_table(self) -> Any | None:
        bucket: str = self.config["bucket"]
        key: str = self.config["key"]
        file_type: str = self.config.get("file_type", "") or _ext_to_type(key)
        body = await _s3_get_bytes(self.config, bucket=bucket, key=key)
        return await _bytes_to_table(body, file_type, self.config)

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            bucket = self.config["bucket"]
            key = self.config["key"]
            await _s3_head_object(self.config, bucket=bucket, key=key)
            return True, f"s3://{bucket}/{key} is accessible."
        except Exception as exc:
            return False, f"S3 check failed: {exc}"


@ConnectorRegistry.register
class GCSConnector(BaseConnector):
    """Fetch data from a Google Cloud Storage object.

    Config keys:
        bucket:         GCS bucket name (required).
        blob:           Object path (required).
        file_type:      Format — auto-detected from extension if omitted.
        credentials:    Path to service account JSON or inline JSON string.
        service_account_json:
                        Accepted alias for inline service account JSON.
        anonymous:      Read a public bucket/object without credentials.
        json_path:      Dot-path to records array.
    """

    connector_type: str = "gcs"

    async def fetch_data(self) -> list[dict[str, Any]]:
        bucket: str = self.config["bucket"]
        blob: str = self.config["blob"]
        file_type: str = self.config.get("file_type", "") or _ext_to_type(blob)
        body = await _gcs_get_bytes(self.config, bucket=bucket, blob=blob)
        return await _bytes_to_records(body, file_type, self.config)

    async def fetch_table(self) -> Any | None:
        bucket: str = self.config["bucket"]
        blob: str = self.config["blob"]
        file_type: str = self.config.get("file_type", "") or _ext_to_type(blob)
        body = await _gcs_get_bytes(self.config, bucket=bucket, blob=blob)
        return await _bytes_to_table(body, file_type, self.config)

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            await _gcs_validate(self.config, bucket=self.config["bucket"], blob=self.config["blob"])
            return True, f"gs://{self.config['bucket']}/{self.config['blob']} accessible."
        except Exception as exc:
            return False, f"GCS check failed: {exc}"


@ConnectorRegistry.register
class AzureBlobConnector(BaseConnector):
    """Fetch data from Azure Blob Storage.

    Config keys:
        connection_string:  Azure Storage connection string.
        account_url:        Azure storage account URL.
        blob_url:           Full public blob URL.
        container:          Container name.
        blob:               Blob path.
        file_type:          Format — auto-detected from extension if omitted.
        anonymous:          Read a public blob/container without credentials.
        json_path:          Dot-path to records array.
    """

    connector_type: str = "azure_blob"

    async def fetch_data(self) -> list[dict[str, Any]]:
        target = _azure_target(self.config)
        file_type: str = self.config.get("file_type", "") or _ext_to_type(target["blob_name"])
        body = await _azure_get_bytes(self.config)
        return await _bytes_to_records(body, file_type, self.config)

    async def fetch_table(self) -> Any | None:
        target = _azure_target(self.config)
        file_type: str = self.config.get("file_type", "") or _ext_to_type(target["blob_name"])
        body = await _azure_get_bytes(self.config)
        return await _bytes_to_table(body, file_type, self.config)

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            await _azure_validate(self.config)
            target = _azure_target(self.config)
            if target["blob_url"]:
                return True, f"{target['blob_url']} is accessible."
            return True, f"azure://{target['container']}/{target['blob']} is accessible."
        except Exception as exc:
            return False, f"Azure check failed: {exc}"


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _ext_to_type(path: str) -> str:
    """Guess file format from extension."""
    p = path.lower().split("?")[0]  # strip query string
    if p.endswith(".parquet") or p.endswith(".pq"):
        return "parquet"
    if p.endswith(".xlsx") or p.endswith(".xls"):
        return "excel"
    if p.endswith(".tsv"):
        return "tsv"
    if p.endswith(".json") or p.endswith(".jsonl"):
        return "json"
    return "csv"  # safe default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, int | float):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


_PUBLIC_OBJECT_TIMEOUT = httpx.Timeout(20.0, connect=5.0)
_PUBLIC_OBJECT_HEADERS = {"User-Agent": "decision-engine-cloud-connector/1.0"}
_PUBLIC_SYNC_CLIENT: httpx.Client | None = None
_PUBLIC_HTTP_AUDIT_CONTEXT: ContextVar[EgressAuditContext | None] = ContextVar(
    "cloud_connector_public_http_audit_context",
    default=None,
)


def _connector_audit_context(config: dict[str, Any]) -> EgressAuditContext:
    return audit_context_from_config(config)


def _quote_object_path(path: str) -> str:
    return quote(path.lstrip("/"), safe="/!$&'()*+,;=:@~.-_")


@contextmanager
def _public_http_audit_scope(audit_context: EgressAuditContext | None):
    token = _PUBLIC_HTTP_AUDIT_CONTEXT.set(audit_context)
    try:
        yield
    finally:
        _PUBLIC_HTTP_AUDIT_CONTEXT.reset(token)


def _public_sync_client() -> httpx.Client:
    global _PUBLIC_SYNC_CLIENT
    if _PUBLIC_SYNC_CLIENT is None:
        _PUBLIC_SYNC_CLIENT = httpx.Client(
            timeout=_PUBLIC_OBJECT_TIMEOUT,
            follow_redirects=True,
            headers=_PUBLIC_OBJECT_HEADERS,
        )
    return _PUBLIC_SYNC_CLIENT


def _sync_http_get_bytes(url: str, *, audit_context: EgressAuditContext | None) -> bytes:
    response = sync_http_request(
        method="GET",
        url=url,
        surface="cloud_connector_public_get",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
        client=_public_sync_client(),
    )
    response.raise_for_status()
    return response.content


async def _http_get_bytes(url: str) -> bytes:
    return await asyncio.to_thread(
        _sync_http_get_bytes,
        url,
        audit_context=_PUBLIC_HTTP_AUDIT_CONTEXT.get(),
    )


def _sync_http_validate_access(url: str, *, audit_context: EgressAuditContext | None) -> None:
    client = _public_sync_client()
    response = sync_http_request(
        method="HEAD",
        url=url,
        surface="cloud_connector_public_head",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
        client=client,
    )
    if response.status_code in {405, 501}:
        response = sync_http_request(
            method="GET",
            url=url,
            surface="cloud_connector_public_probe",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context,
            client=client,
            headers={"Range": "bytes=0-0"},
        )
    response.raise_for_status()


async def _http_validate_access(url: str) -> None:
    await asyncio.to_thread(
        _sync_http_validate_access,
        url,
        audit_context=_PUBLIC_HTTP_AUDIT_CONTEXT.get(),
    )


def _has_explicit_cloud_credentials(config: dict[str, Any], names: tuple[str, ...]) -> bool:
    return any(str(config.get(name, "") or "").strip() for name in names)


def _s3_public_object_url(config: dict[str, Any], *, bucket: str, key: str) -> str | None:
    if not _truthy(config.get("anonymous")):
        return None
    if str(config.get("endpoint_url", "") or "").strip():
        return None
    if _has_explicit_cloud_credentials(
        config,
        ("aws_access_key_id", "access_key_id", "aws_secret_access_key", "secret_access_key"),
    ):
        return None
    region = str(config.get("region", "us-east-1") or "us-east-1").strip() or "us-east-1"
    object_path = _quote_object_path(key)
    if "." in bucket:
        if region == "us-east-1":
            return f"https://s3.amazonaws.com/{bucket}/{object_path}"
        return f"https://s3.{region}.amazonaws.com/{bucket}/{object_path}"
    if region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{object_path}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{object_path}"


def _gcs_public_object_url(config: dict[str, Any], *, bucket: str, blob: str) -> str | None:
    if not _truthy(config.get("anonymous")):
        return None
    if _has_explicit_cloud_credentials(config, ("credentials", "service_account_json")):
        return None
    return f"https://storage.googleapis.com/{bucket}/{_quote_object_path(blob)}"


def _azure_public_object_url(target: dict[str, Any]) -> str | None:
    if not target["anonymous"]:
        return None
    if target["blob_url"]:
        return str(target["blob_url"])
    account_url = str(target["account_url"]).rstrip("/")
    container = quote(str(target["container"]).strip("/"), safe="!$&'()*+,;=:@~.-_")
    blob = _quote_object_path(str(target["blob"]))
    if not account_url or not container or not blob:
        return None
    return f"{account_url}/{container}/{blob}"


def _s3_client_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"region_name": config.get("region", "us-east-1")}
    endpoint_url = config.get("endpoint_url")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if _truthy(config.get("anonymous")):
        from botocore import UNSIGNED
        from botocore.config import Config as BotoConfig

        kwargs["config"] = BotoConfig(signature_version=UNSIGNED)
        return kwargs

    access_key = config.get("aws_access_key_id") or config.get("access_key_id")
    secret_key = config.get("aws_secret_access_key") or config.get("secret_access_key")
    session_token = config.get("aws_session_token") or config.get("session_token")
    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key
    if session_token:
        kwargs["aws_session_token"] = session_token
    return kwargs


def _s3_service_url(config: dict[str, Any]) -> str:
    return aws_endpoint_url(
        aws_service_name="s3",
        region_name=str(config.get("region", "us-east-1") or "us-east-1"),
        endpoint_url=(
            str(config.get("endpoint_url") or "").strip() or None
        ),
    )


def _azure_connection_string_parts(connection_string: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for section in connection_string.split(";"):
        if "=" not in section:
            continue
        key, value = section.split("=", 1)
        parts[key.strip()] = value.strip()
    return parts


def _azure_service_url(target: dict[str, Any]) -> str:
    if target["account_url"]:
        return azure_endpoint_url(str(target["account_url"]))
    connection_string = str(target.get("connection_string", "") or "").strip()
    if connection_string:
        parts = _azure_connection_string_parts(connection_string)
        account_name = parts.get("AccountName", "")
        endpoint_suffix = parts.get("EndpointSuffix", "core.windows.net")
        if account_name:
            return f"https://{account_name}.blob.{endpoint_suffix}"
    return "https://blob.core.windows.net"


async def _s3_get_bytes(config: dict[str, Any], *, bucket: str, key: str) -> bytes:
    audit_context = _connector_audit_context(config)
    public_url = _s3_public_object_url(config, bucket=bucket, key=key)
    if public_url is not None:
        with _public_http_audit_scope(audit_context):
            return await _http_get_bytes(public_url)
    kwargs = _s3_client_kwargs(config)
    enforce_egress_sync(
        _s3_service_url(config),
        surface="cloud_connector_s3_fetch",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
    )
    try:
        from aiobotocore.session import get_session
    except ImportError:
        import boto3

        def _sync_fetch() -> bytes:
            client = boto3.client("s3", **kwargs)
            resp = client.get_object(Bucket=bucket, Key=key)
            body = resp["Body"].read()
            return body if isinstance(body, bytes) else bytes(body)

        return await asyncio.to_thread(_sync_fetch)

    session = get_session()
    async with session.create_client("s3", **kwargs) as client:
        resp = await client.get_object(Bucket=bucket, Key=key)
        body = await resp["Body"].read()
        return body if isinstance(body, bytes) else bytes(body)


async def _s3_head_object(config: dict[str, Any], *, bucket: str, key: str) -> None:
    audit_context = _connector_audit_context(config)
    public_url = _s3_public_object_url(config, bucket=bucket, key=key)
    if public_url is not None:
        with _public_http_audit_scope(audit_context):
            await _http_validate_access(public_url)
        return
    kwargs = _s3_client_kwargs(config)
    enforce_egress_sync(
        _s3_service_url(config),
        surface="cloud_connector_s3_head",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
    )
    try:
        from aiobotocore.session import get_session
    except ImportError:
        import boto3

        def _sync_head() -> None:
            client = boto3.client("s3", **kwargs)
            client.head_object(Bucket=bucket, Key=key)

        await asyncio.to_thread(_sync_head)
        return

    session = get_session()
    async with session.create_client("s3", **kwargs) as client:
        await client.head_object(Bucket=bucket, Key=key)


def _build_gcs_client(storage: Any, config: dict[str, Any]) -> Any:
    enforce_egress_sync(
        google_endpoint_url("storage.googleapis.com"),
        surface="cloud_connector_gcs_client",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=_connector_audit_context(config),
    )
    creds = config.get("credentials") or config.get("service_account_json")
    if _truthy(config.get("anonymous")):
        return storage.Client.create_anonymous_client()
    if creds:
        import json as _json

        from google.oauth2 import service_account

        if isinstance(creds, str) and creds.strip().startswith("{"):
            info = _json.loads(creds)
        elif isinstance(creds, str):
            with open(creds, encoding="utf-8") as handle:
                info = _json.load(handle)
        else:
            info = creds
        credentials = service_account.Credentials.from_service_account_info(info)  # type: ignore[no-untyped-call]
        return storage.Client(credentials=credentials, project=config.get("project_id"))
    return storage.Client(project=config.get("project_id"))


def _validate_gcs_reference(*, bucket: str, blob: str) -> None:
    normalized_bucket = str(bucket).strip()
    normalized_blob = str(blob).strip()
    if not normalized_bucket:
        raise ValueError("invalid identifier: GCS bucket must not be empty")
    if any(char.isspace() for char in normalized_bucket) or "/" in normalized_bucket:
        raise ValueError(
            "invalid identifier: GCS bucket must be a bare bucket name without whitespace or '/'"
        )
    if not normalized_blob:
        raise ValueError("invalid identifier: GCS blob must not be empty")


async def _gcs_get_bytes(config: dict[str, Any], *, bucket: str, blob: str) -> bytes:
    _validate_gcs_reference(bucket=bucket, blob=blob)
    audit_context = _connector_audit_context(config)
    public_url = _gcs_public_object_url(config, bucket=bucket, blob=blob)
    if public_url is not None:
        with _public_http_audit_scope(audit_context):
            return await _http_get_bytes(public_url)
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise ImportError(
            "GCS support requires google-cloud-storage: pip install google-cloud-storage"
        ) from exc

    def _sync_fetch() -> bytes:
        client = _build_gcs_client(storage, config)
        body = client.bucket(bucket).blob(blob).download_as_bytes()
        return body if isinstance(body, bytes) else bytes(body)

    return await asyncio.to_thread(_sync_fetch)


async def _gcs_validate(config: dict[str, Any], *, bucket: str, blob: str) -> None:
    _validate_gcs_reference(bucket=bucket, blob=blob)
    audit_context = _connector_audit_context(config)
    public_url = _gcs_public_object_url(config, bucket=bucket, blob=blob)
    if public_url is not None:
        with _public_http_audit_scope(audit_context):
            await _http_validate_access(public_url)
        return
    await _gcs_get_bytes(config, bucket=bucket, blob=blob)


def _azure_target(config: dict[str, Any]) -> dict[str, Any]:
    blob_url = str(config.get("blob_url", "") or "").strip()
    container = str(config.get("container", "") or "").strip()
    blob = str(config.get("blob", "") or "").strip()
    account_url = str(config.get("account_url", "") or "").strip()
    connection_string = str(config.get("connection_string", "") or "").strip()
    anonymous = _truthy(config.get("anonymous"))

    if blob_url:
        parsed = urlparse(blob_url)
        parts = [part for part in parsed.path.split("/") if part]
        container = container or (parts[0] if parts else "")
        blob = blob or ("/".join(parts[1:]) if len(parts) > 1 else "")
        account_url = account_url or f"{parsed.scheme}://{parsed.netloc}"
    blob_name = blob or (blob_url.split("/")[-1] if blob_url else "")

    if blob_url:
        return {
            "blob_url": blob_url,
            "account_url": account_url,
            "container": container,
            "blob": blob,
            "blob_name": blob_name,
            "connection_string": connection_string,
            "anonymous": True,
        }
    if account_url and container and blob:
        return {
            "blob_url": "",
            "account_url": account_url,
            "container": container,
            "blob": blob,
            "blob_name": blob_name,
            "connection_string": connection_string,
            "anonymous": anonymous,
        }
    if connection_string and container and blob:
        return {
            "blob_url": "",
            "account_url": account_url,
            "container": container,
            "blob": blob,
            "blob_name": blob_name,
            "connection_string": connection_string,
            "anonymous": anonymous,
        }
    raise KeyError(
        "Azure Blob config requires blob_url, or connection_string/account_url "
        "with container and blob."
    )


async def _azure_validate(config: dict[str, Any]) -> None:
    target = _azure_target(config)
    audit_context = _connector_audit_context(config)
    public_url = _azure_public_object_url(target)
    if public_url is not None:
        with _public_http_audit_scope(audit_context):
            await _http_validate_access(public_url)
        return
    enforce_egress_sync(
        _azure_service_url(target),
        surface="cloud_connector_azure_validate",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
    )
    try:
        from azure.storage.blob import BlobClient, BlobServiceClient
        from azure.storage.blob.aio import (
            BlobServiceClient as AsyncBlobServiceClient,
        )
    except ImportError as exc:
        raise ImportError(
            "Azure support requires azure-storage-blob: pip install azure-storage-blob"
        ) from exc

    if target["blob_url"] or target["anonymous"]:

        def _sync_validate() -> None:
            if target["blob_url"]:
                client = BlobClient.from_blob_url(target["blob_url"])
            else:
                service = BlobServiceClient(account_url=target["account_url"], credential=None)
                client = service.get_blob_client(container=target["container"], blob=target["blob"])
            client.get_blob_properties()

        await asyncio.to_thread(_sync_validate)
        return

    async with AsyncBlobServiceClient.from_connection_string(target["connection_string"]) as svc:
        blob_client = svc.get_blob_client(container=target["container"], blob=target["blob"])
        await blob_client.get_blob_properties()


async def _azure_get_bytes(config: dict[str, Any]) -> bytes:
    target = _azure_target(config)
    audit_context = _connector_audit_context(config)
    public_url = _azure_public_object_url(target)
    if public_url is not None:
        with _public_http_audit_scope(audit_context):
            return await _http_get_bytes(public_url)
    enforce_egress_sync(
        _azure_service_url(target),
        surface="cloud_connector_azure_fetch",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
    )
    try:
        from azure.storage.blob.aio import (
            BlobServiceClient as AsyncBlobServiceClient,
        )
    except ImportError as exc:
        raise ImportError(
            "Azure support requires azure-storage-blob: pip install azure-storage-blob"
        ) from exc

    async with AsyncBlobServiceClient.from_connection_string(target["connection_string"]) as svc:
        blob_client = svc.get_blob_client(container=target["container"], blob=target["blob"])
        stream = await blob_client.download_blob()
        body = await stream.readall()
        return body if isinstance(body, bytes) else bytes(body)


async def _bytes_to_records(
    body: bytes,
    file_type: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert raw bytes to records using FileConnector parsers."""
    if file_type in ("parquet", "excel"):
        content = base64.b64encode(body).decode()
    else:
        content = body.decode("utf-8", errors="replace")

    fc_config = {
        "file_type": file_type,
        "content": content,
        "json_path": config.get("json_path", ""),
        "sheet": config.get("sheet", 0),
    }
    fc = FileConnector(fc_config)
    return await fc.fetch_data()


async def _bytes_to_table(
    body: bytes,
    file_type: str,
    config: dict[str, Any],
) -> Any | None:
    """Convert raw bytes to a columnar table when the payload format supports it."""
    if file_type in ("parquet", "excel"):
        content = base64.b64encode(body).decode()
    else:
        content = body.decode("utf-8", errors="replace")

    fc_config = {
        "file_type": file_type,
        "content": content,
        "json_path": config.get("json_path", ""),
        "sheet": config.get("sheet", 0),
        "delimiter": config.get("delimiter", ","),
    }
    fc = FileConnector(fc_config)
    return await fc.fetch_table()
