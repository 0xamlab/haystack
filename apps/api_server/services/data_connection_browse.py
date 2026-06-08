"""Browse execution helpers for connector discovery and SQL source selection."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from apps.api_server.services.connectors import normalize_type
from apps.api_server.services.connector_egress import connector_audit_context
from apps.api_server.services.data_connection_browse_sql import (
    _DATABASE_TYPES,
    _browse_postgres_compatible_sql,
    _browse_sql,
    _build_database_connection_string,
    _clear_sync_browse_engine_cache,
    _sql_source_selection_query,
    _sql_source_selection_query_for_provider,
    strip_none,
    truthy,
)
from apps.api_server.services.data_connection_discovery import build_discovery_metadata
from apps.api_server.services.repository_intelligence import browse_repository_connector

_BROWSE_RESULT_CACHE_TTL_SECONDS = 5.0
_BROWSE_RESULT_CACHE_MAX_ENTRIES = 128
_BROWSE_RESULT_CACHE: OrderedDict[
    str, tuple[float, tuple[list[dict[str, Any]], str, dict[str, Any]]]
] = OrderedDict()
_BROWSE_RESULT_CACHE_LOCK = Lock()

__all__ = [
    "_DATABASE_TYPES",
    "_build_database_connection_string",
    "_browse_elasticsearch",
    "_browse_postgres_compatible_sql",
    "_browse_redis_detailed",
    "_browse_sql",
    "_clear_browse_result_cache",
    "_clear_sync_browse_engine_cache",
    "_sql_source_selection_query",
    "_sql_source_selection_query_for_provider",
    "browse_connector_real",
    "browse_connector_real_detailed",
    "strip_none",
    "truthy",
]


def _browse_cache_key(
    connector_type: str,
    config: dict[str, Any],
) -> str:
    canonical_payload = json.dumps(
        {
            "connector_type": normalize_type(connector_type),
            "config": config,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _browse_cache_get(
    cache_key: str,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]] | None:
    now = time.monotonic()
    with _BROWSE_RESULT_CACHE_LOCK:
        cached = _BROWSE_RESULT_CACHE.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            _BROWSE_RESULT_CACHE.pop(cache_key, None)
            return None
        _BROWSE_RESULT_CACHE.move_to_end(cache_key)
        return copy.deepcopy(payload)


def _browse_cache_put(
    cache_key: str,
    items: list[dict[str, Any]],
    message: str,
    discovery: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    payload = (copy.deepcopy(items), message, copy.deepcopy(discovery))
    expires_at = time.monotonic() + _BROWSE_RESULT_CACHE_TTL_SECONDS
    with _BROWSE_RESULT_CACHE_LOCK:
        _BROWSE_RESULT_CACHE.pop(cache_key, None)
        _BROWSE_RESULT_CACHE[cache_key] = (expires_at, payload)
        while len(_BROWSE_RESULT_CACHE) > _BROWSE_RESULT_CACHE_MAX_ENTRIES:
            _BROWSE_RESULT_CACHE.popitem(last=False)
    return copy.deepcopy(payload)


def _clear_browse_result_cache() -> None:
    with _BROWSE_RESULT_CACHE_LOCK:
        _BROWSE_RESULT_CACHE.clear()


async def _browse_redis(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    items, _provider_metadata = await _browse_redis_detailed(config)
    return items, f"Found {len(items)} browsable Redis keys"


async def _browse_redis_detailed(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from apps.api_server.connectors.redis_connector import RedisConnector

    connection_url = RedisConnector._connection_url(config)
    pattern = str(config.get("key_pattern", "*") or "*").strip() or "*"
    limit = RedisConnector._positive_int(
        config.get("limit"),
        default=RedisConnector._DEFAULT_SCAN_LIMIT,
        field_name="limit",
    )
    items, provider_metadata = await asyncio.to_thread(
        RedisConnector._browse_summary_sync,
        connection_url,
        pattern=pattern,
        limit=limit,
        audit_context=connector_audit_context(config),
    )
    return items, provider_metadata


async def _browse_neo4j(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    from apps.api_server.connectors.neo4j_connector import Neo4jConnector

    settings = Neo4jConnector._connection_settings(config)
    limit = Neo4jConnector._positive_int(
        config.get("limit"),
        default=50,
        field_name="limit",
    )
    items = await asyncio.to_thread(
        Neo4jConnector._browse_sync,
        settings,
        limit=limit,
        audit_context=connector_audit_context(config),
    )
    return items, f"Found {len(items)} browsable Neo4j labels and relationship types"


async def _browse_elasticsearch(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    from apps.api_server.connectors.elasticsearch_connector import ElasticsearchConnector

    settings = ElasticsearchConnector._connection_settings(config)
    limit = ElasticsearchConnector._positive_int(
        config.get("limit"),
        default=ElasticsearchConnector._DEFAULT_BROWSE_LIMIT,
        field_name="limit",
    )
    include_hidden = truthy(config.get("include_hidden"))
    items = await asyncio.to_thread(
        ElasticsearchConnector._browse_sync,
        settings,
        limit=limit,
        include_hidden=include_hidden,
        audit_context=connector_audit_context(config),
    )
    return items, f"Found {len(items)} browsable Elasticsearch indices"


async def browse_connector_real(
    connector_type: str,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    items, message, _discovery = await browse_connector_real_detailed(connector_type, config)
    return items, message


async def browse_connector_real_detailed(
    connector_type: str,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    ct = normalize_type(connector_type)
    cache_key = _browse_cache_key(ct, config)
    cached = _browse_cache_get(cache_key)
    if cached is not None:
        items, message, discovery = cached
        return items, message, discovery

    def _cache_and_return(
        items: list[dict[str, Any]],
        message: str,
        discovery: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        cached_items, cached_message, cached_discovery = _browse_cache_put(
            cache_key,
            items,
            message,
            discovery,
        )
        return cached_items, cached_message, cached_discovery

    if ct == "elasticsearch":
        items, message = await _browse_elasticsearch(config)
        return _cache_and_return(
            items,
            message,
            build_discovery_metadata(ct, config=config, items=items),
        )
    if ct == "neo4j":
        items, message = await _browse_neo4j(config)
        return _cache_and_return(
            items,
            message,
            build_discovery_metadata(ct, config=config, items=items),
        )
    if ct == "redis":
        items, provider_metadata = await _browse_redis_detailed(config)
        message = f"Found {len(items)} browsable Redis keys"
        return _cache_and_return(
            items,
            message,
            build_discovery_metadata(
                ct,
                config=config,
                items=items,
                provider_metadata=provider_metadata,
            ),
        )
    if ct in _DATABASE_TYPES:
        items, message = await _browse_sql(config, provider=ct)
        return _cache_and_return(
            items,
            message,
            build_discovery_metadata(ct, config=config, items=items),
        )
    if ct == "s3":
        import boto3

        from apps.api_server.connectors.cloud_connector import _s3_client_kwargs
        from apps.api_server.services.egress_guard import (
            audit_context_from_config,
            aws_endpoint_url,
            enforce_egress_sync,
        )

        bucket = str(config.get("bucket", ""))
        if not bucket:
            return (
                [],
                "S3 browse requires bucket",
                build_discovery_metadata(
                    ct,
                    config=config,
                    items=[],
                ),
            )
        enforce_egress_sync(
            aws_endpoint_url(
                aws_service_name="s3",
                region_name=str(config.get("region", "us-east-1") or "us-east-1"),
                endpoint_url=(str(config.get("endpoint_url") or "").strip() or None),
            ),
            surface="browse_s3_connector",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_config(config),
        )
        s3 = boto3.client("s3", **_s3_client_kwargs(config))
        resp = s3.list_objects_v2(Bucket=bucket, MaxKeys=100)
        items = [
            {
                "id": obj["Key"],
                "label": obj["Key"],
                "kind": "object",
                "selection": {"object_path": obj["Key"]},
                "size": obj.get("Size"),
            }
            for obj in resp.get("Contents", [])
        ]
        return _cache_and_return(
            items,
            f"Found {len(items)} objects in s3://{bucket}",
            build_discovery_metadata(ct, config=config, items=items),
        )
    if ct == "gcs":
        from google.cloud import storage as gcs_storage

        from apps.api_server.connectors.cloud_connector import _build_gcs_client
        from apps.api_server.services.egress_guard import (
            audit_context_from_config,
            enforce_egress_sync,
            google_endpoint_url,
        )

        bucket = str(config.get("bucket", ""))
        if not bucket:
            return (
                [],
                "GCS browse requires bucket",
                build_discovery_metadata(
                    ct,
                    config=config,
                    items=[],
                ),
            )
        enforce_egress_sync(
            google_endpoint_url("storage.googleapis.com"),
            surface="browse_gcs_connector",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_config(config),
        )

        def _sync() -> list[dict[str, Any]]:
            client = _build_gcs_client(gcs_storage, config)
            return [
                {
                    "id": blob.name,
                    "label": blob.name,
                    "kind": "object",
                    "selection": {"object_path": blob.name},
                }
                for blob in client.bucket(bucket).list_blobs(max_results=100)
            ]

        items = await asyncio.to_thread(_sync)
        return _cache_and_return(
            items,
            f"Found {len(items)} objects in gs://{bucket}",
            build_discovery_metadata(ct, config=config, items=items),
        )
    if ct in {"azure", "azure_blob"}:
        from azure.storage.blob import BlobServiceClient
        from apps.api_server.connectors.cloud_connector import _azure_connection_string_parts
        from apps.api_server.services.egress_guard import (
            audit_context_from_config,
            azure_endpoint_url,
            enforce_egress_sync,
        )

        container = str(config.get("container", ""))
        if not container:
            return (
                [],
                "Azure browse requires container",
                build_discovery_metadata(
                    ct,
                    config=config,
                    items=[],
                ),
            )
        account_url = str(config.get("account_url", "") or "").strip()
        connection_string = str(config.get("connection_string", "") or "").strip()
        service_url = azure_endpoint_url(account_url) if account_url else "https://blob.core.windows.net"
        if not account_url and connection_string:
            connection_parts = _azure_connection_string_parts(connection_string)
            account_name = connection_parts.get("AccountName", "")
            endpoint_suffix = connection_parts.get("EndpointSuffix", "core.windows.net")
            if account_name:
                service_url = f"https://{account_name}.blob.{endpoint_suffix}"
        enforce_egress_sync(
            service_url,
            surface="browse_azure_connector",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_config(config),
        )

        def _sync() -> list[dict[str, Any]]:
            connection_string = str(config.get("connection_string", "") or "")
            account_url = str(config.get("account_url", "") or "")
            if connection_string:
                service = BlobServiceClient.from_connection_string(connection_string)
            elif account_url:
                service = BlobServiceClient(account_url=account_url, credential=None)
            else:
                raise RuntimeError("Azure browse requires connection_string or account_url")
            client = service.get_container_client(container)
            items: list[dict[str, Any]] = []
            for blob in client.list_blobs(
                name_starts_with=config.get("prefix"),
                results_per_page=100,
            ):
                items.append(
                    {
                        "id": blob.name,
                        "label": blob.name,
                        "kind": "object",
                        "selection": {"object_path": blob.name},
                    }
                )
                if len(items) >= 100:
                    break
            return items

        items = await asyncio.to_thread(_sync)
        return _cache_and_return(
            items,
            f"Found {len(items)} blobs in azure://{container}",
            build_discovery_metadata(ct, config=config, items=items),
        )
    if ct == "rest":
        url = str(config.get("url") or config.get("base_url") or "")
        if not url:
            return (
                [],
                "REST browse requires url or base_url",
                build_discovery_metadata(
                    ct,
                    config=config,
                    items=[],
                ),
            )
        choice = {
            "id": url,
            "label": url,
            "kind": "endpoint",
            "selection": strip_none({"url": url, "data_path": config.get("data_path")}),
        }
        return _cache_and_return(
            [choice],
            "REST endpoints use the configured URL directly",
            build_discovery_metadata(ct, config=config, items=[choice]),
        )
    if ct in {"github_repo", "gitlab_repo", "bitbucket_repo", "local_repo", "repo_archive"}:
        items, message = browse_repository_connector(connector_type=ct, config=config)
        return _cache_and_return(
            items,
            message,
            build_discovery_metadata(ct, config=config, items=items),
        )
    return (
        [],
        f"Browse not implemented for '{ct}'",
        build_discovery_metadata(
            ct,
            config=config,
            items=[],
        ),
    )
