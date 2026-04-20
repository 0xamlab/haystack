"""Cloud object storage connector (S3, GCS, Azure Blob)."""
from __future__ import annotations

import asyncio
import base64
from typing import Any
from urllib.parse import urlparse

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

        try:
            from google.cloud import storage  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "GCS support requires google-cloud-storage: pip install google-cloud-storage"
            ) from exc

        import asyncio

        def _sync_fetch() -> bytes:
            client = _build_gcs_client(storage, self.config)
            return client.bucket(bucket).blob(blob).download_as_bytes()

        body = await asyncio.to_thread(_sync_fetch)
        return await _bytes_to_records(body, file_type, self.config)

    async def fetch_table(self) -> Any | None:
        bucket: str = self.config["bucket"]
        blob: str = self.config["blob"]
        file_type: str = self.config.get("file_type", "") or _ext_to_type(blob)

        try:
            from google.cloud import storage  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "GCS support requires google-cloud-storage: pip install google-cloud-storage"
            ) from exc

        def _sync_fetch() -> bytes:
            client = _build_gcs_client(storage, self.config)
            return client.bucket(bucket).blob(blob).download_as_bytes()

        body = await asyncio.to_thread(_sync_fetch)
        return await _bytes_to_table(body, file_type, self.config)

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            await self.fetch_data()
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

        try:
            from azure.storage.blob import BlobClient, BlobServiceClient  # type: ignore[import]
            from azure.storage.blob.aio import (
                BlobServiceClient as AsyncBlobServiceClient,  # type: ignore[import]
            )
        except ImportError as exc:
            raise ImportError(
                "Azure support requires azure-storage-blob: pip install azure-storage-blob"
            ) from exc

        body: bytes
        if target["blob_url"] or target["anonymous"]:
            def _sync_fetch() -> bytes:
                if target["blob_url"]:
                    client = BlobClient.from_blob_url(target["blob_url"])
                else:
                    service = BlobServiceClient(account_url=target["account_url"], credential=None)
                    client = service.get_blob_client(
                        container=target["container"],
                        blob=target["blob"],
                    )
                return client.download_blob().readall()

            body = await asyncio.to_thread(_sync_fetch)
        else:
            async with AsyncBlobServiceClient.from_connection_string(
                target["connection_string"]
            ) as svc:
                blob_client = svc.get_blob_client(
                    container=target["container"],
                    blob=target["blob"],
                )
                stream = await blob_client.download_blob()
                body = await stream.readall()

        return await _bytes_to_records(body, file_type, self.config)

    async def fetch_table(self) -> Any | None:
        target = _azure_target(self.config)
        file_type: str = self.config.get("file_type", "") or _ext_to_type(target["blob_name"])

        try:
            from azure.storage.blob import BlobClient, BlobServiceClient  # type: ignore[import]
            from azure.storage.blob.aio import (
                BlobServiceClient as AsyncBlobServiceClient,  # type: ignore[import]
            )
        except ImportError as exc:
            raise ImportError(
                "Azure support requires azure-storage-blob: pip install azure-storage-blob"
            ) from exc

        body: bytes
        if target["blob_url"] or target["anonymous"]:
            def _sync_fetch() -> bytes:
                if target["blob_url"]:
                    client = BlobClient.from_blob_url(target["blob_url"])
                else:
                    service = BlobServiceClient(account_url=target["account_url"], credential=None)
                    client = service.get_blob_client(
                        container=target["container"],
                        blob=target["blob"],
                    )
                return client.download_blob().readall()

            body = await asyncio.to_thread(_sync_fetch)
        else:
            async with AsyncBlobServiceClient.from_connection_string(
                target["connection_string"]
            ) as svc:
                blob_client = svc.get_blob_client(
                    container=target["container"],
                    blob=target["blob"],
                )
                stream = await blob_client.download_blob()
                body = await stream.readall()

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


def _s3_client_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"region_name": config.get("region", "us-east-1")}
    endpoint_url = config.get("endpoint_url")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if _truthy(config.get("anonymous")):
        from botocore import UNSIGNED  # type: ignore[import]
        from botocore.config import Config as BotoConfig  # type: ignore[import]

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


async def _s3_get_bytes(config: dict[str, Any], *, bucket: str, key: str) -> bytes:
    kwargs = _s3_client_kwargs(config)
    try:
        from aiobotocore.session import get_session  # type: ignore[import]
    except ImportError:
        import boto3  # type: ignore[import]

        def _sync_fetch() -> bytes:
            client = boto3.client("s3", **kwargs)
            resp = client.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()

        return await asyncio.to_thread(_sync_fetch)

    session = get_session()
    async with session.create_client("s3", **kwargs) as client:
        resp = await client.get_object(Bucket=bucket, Key=key)
        return await resp["Body"].read()


async def _s3_head_object(config: dict[str, Any], *, bucket: str, key: str) -> None:
    kwargs = _s3_client_kwargs(config)
    try:
        from aiobotocore.session import get_session  # type: ignore[import]
    except ImportError:
        import boto3  # type: ignore[import]

        def _sync_head() -> None:
            client = boto3.client("s3", **kwargs)
            client.head_object(Bucket=bucket, Key=key)

        await asyncio.to_thread(_sync_head)
        return

    session = get_session()
    async with session.create_client("s3", **kwargs) as client:
        await client.head_object(Bucket=bucket, Key=key)


def _build_gcs_client(storage: Any, config: dict[str, Any]) -> Any:
    creds = config.get("credentials") or config.get("service_account_json")
    if _truthy(config.get("anonymous")):
        return storage.Client.create_anonymous_client()
    if creds:
        import json as _json

        from google.oauth2 import service_account  # type: ignore[import]

        if isinstance(creds, str) and creds.strip().startswith("{"):
            info = _json.loads(creds)
        elif isinstance(creds, str):
            with open(creds, encoding="utf-8") as handle:
                info = _json.load(handle)
        else:
            info = creds
        credentials = service_account.Credentials.from_service_account_info(info)
        return storage.Client(credentials=credentials, project=config.get("project_id"))
    return storage.Client(project=config.get("project_id"))


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
    try:
        from azure.storage.blob import BlobClient, BlobServiceClient  # type: ignore[import]
        from azure.storage.blob.aio import (
            BlobServiceClient as AsyncBlobServiceClient,  # type: ignore[import]
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
