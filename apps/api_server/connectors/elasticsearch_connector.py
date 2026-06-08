"""Elasticsearch connector for explicit search fetches and index browsing."""

from __future__ import annotations

import asyncio
import json
from threading import Lock
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    audit_context_from_config,
    sync_http_request,
)

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class ElasticsearchConnector(BaseConnector):
    """Run explicit Elasticsearch queries against a cluster or Elastic Cloud deployment.

    Config keys:
        url / endpoint / connection_string:
            Elasticsearch base URL, for example https://cluster.example.com:443
        api_key:
            Base64-encoded Elasticsearch API key for Authorization: ApiKey <value>
        index:
            Explicit index name for fetch_data().
        query:
            Optional Elasticsearch Query DSL object or JSON string.
        limit / size:
            Optional maximum number of hits to materialize. Defaults to 100.
        include_hidden:
            Include dot-prefixed indices in browse output. Defaults to false.
    """

    connector_type = "elasticsearch"
    _DEFAULT_LIMIT = 100
    _DEFAULT_TIMEOUT_SECONDS = 5.0
    _DEFAULT_BROWSE_LIMIT = 100
    _BROWSE_PATH = "/_cat/indices"
    _VALIDATE_PATH = "/"
    _CLIENTS: dict[str, httpx.Client] = {}
    _CLIENTS_LOCK = Lock()

    async def fetch_data(self) -> list[dict[str, Any]]:
        settings = self._connection_settings(self.config)
        index = self._index_name(self.config)
        query = self._query_body(self.config)
        limit = self._positive_int(
            self.config.get("limit", self.config.get("size")),
            default=self._DEFAULT_LIMIT,
            field_name="limit",
        )
        return await asyncio.to_thread(
            self._fetch_sync,
            settings,
            index,
            query,
            limit,
            audit_context_from_config(self.config),
        )

    async def validate_connection(self) -> tuple[bool, str]:
        settings = self._connection_settings(self.config)
        try:
            await asyncio.to_thread(
                self._validate_sync,
                settings,
                audit_context_from_config(self.config),
            )
        except Exception as exc:
            return False, f"Connection failed: {exc}"
        return True, "Connected successfully."

    @classmethod
    def _connection_settings(cls, config: dict[str, Any]) -> dict[str, Any]:
        raw_url = ""
        for field_name in ("url", "endpoint", "connection_string"):
            raw_value = config.get(field_name)
            if isinstance(raw_value, str) and raw_value.strip():
                raw_url = raw_value.strip()
                break
        if not raw_url:
            raise ValueError(
                "Elasticsearch connector requires url, endpoint, or connection_string."
            )

        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported Elasticsearch connection string: {raw_url}")
        if not parsed.hostname:
            raise ValueError("Elasticsearch connection string requires host.")

        base_url = raw_url.rstrip("/")
        api_key = str(
            config.get("api_key", config.get("apiKey", config.get("password", ""))) or ""
        ).strip()
        if not api_key:
            raise ValueError("Elasticsearch connector requires api_key.")

        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return {
            "base_url": base_url,
            "api_key": api_key,
            "host": host,
            "port": port,
        }

    @classmethod
    def _index_name(cls, config: dict[str, Any]) -> str:
        index = str(config.get("index", "") or "").strip()
        if not index:
            raise ValueError("Elasticsearch connector fetch_data requires index.")
        return index

    @classmethod
    def _query_body(cls, config: dict[str, Any]) -> dict[str, Any]:
        raw_query = config.get("query")
        if raw_query in (None, ""):
            return {"query": {"match_all": {}}}
        if isinstance(raw_query, dict):
            return dict(raw_query)
        if isinstance(raw_query, str):
            parsed = json.loads(raw_query)
            if not isinstance(parsed, dict):
                raise ValueError("Elasticsearch query JSON must decode to an object.")
            return dict(parsed)
        raise ValueError("Elasticsearch connector query must be an object or JSON string.")

    @classmethod
    def _positive_int(cls, raw_value: Any, *, default: int, field_name: str) -> int:
        if raw_value in (None, ""):
            return default
        value = int(raw_value)
        if value <= 0:
            raise ValueError(f"Elasticsearch connector {field_name} must be greater than zero.")
        return value

    @staticmethod
    def _parse_optional_int(raw_value: Any) -> int | None:
        if raw_value in (None, ""):
            return None
        try:
            normalized = str(raw_value).strip().replace(",", "")
            if not normalized:
                return None
            return int(float(normalized))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _client_cache_key(cls, settings: dict[str, Any]) -> str:
        return str(settings["base_url"])

    @classmethod
    def _auth_headers(cls, settings: dict[str, Any]) -> dict[str, str]:
        return {
            "Authorization": f"ApiKey {settings['api_key']}",
            "Accept": "application/json",
        }

    @classmethod
    def _connect_sync(cls, settings: dict[str, Any]) -> httpx.Client:
        return httpx.Client(
            base_url=str(settings["base_url"]),
            timeout=cls._DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

    @staticmethod
    def _close_sync(client: httpx.Client) -> None:
        try:
            client.close()
        except Exception:
            return

    @classmethod
    def _acquire_client(cls, settings: dict[str, Any]) -> httpx.Client:
        cache_key = cls._client_cache_key(settings)
        with cls._CLIENTS_LOCK:
            client = cls._CLIENTS.get(cache_key)
            if client is None:
                client = cls._connect_sync(settings)
                cls._CLIENTS[cache_key] = client
            return client

    @classmethod
    def _release_client(
        cls,
        settings: dict[str, Any],
        client: httpx.Client,
        *,
        discard: bool,
    ) -> None:
        if not discard:
            return
        cache_key = cls._client_cache_key(settings)
        with cls._CLIENTS_LOCK:
            cached = cls._CLIENTS.get(cache_key)
            if cached is client:
                cls._CLIENTS.pop(cache_key, None)
        cls._close_sync(client)

    @classmethod
    def _clear_client_cache(cls) -> None:
        with cls._CLIENTS_LOCK:
            clients = list(cls._CLIENTS.values())
            cls._CLIENTS = {}
        for client in clients:
            cls._close_sync(client)

    @classmethod
    def _validate_sync(
        cls,
        settings: dict[str, Any],
        audit_context: EgressAuditContext | None = None,
    ) -> None:
        client = cls._acquire_client(settings)
        discard_client = False
        try:
            response = sync_http_request(
                method="GET",
                url=cls._VALIDATE_PATH,
                surface="elasticsearch_validate",
                policy_destination=str(settings["base_url"]),
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=cls._auth_headers(settings),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or "version" not in payload:
                raise RuntimeError("Elasticsearch validation response missing version payload.")
        except Exception:
            discard_client = True
            raise
        finally:
            cls._release_client(settings, client, discard=discard_client)

    @classmethod
    def _browse_sync(
        cls,
        settings: dict[str, Any],
        *,
        limit: int,
        include_hidden: bool,
        audit_context: EgressAuditContext | None = None,
    ) -> list[dict[str, Any]]:
        client = cls._acquire_client(settings)
        discard_client = False
        try:
            response = sync_http_request(
                method="GET",
                url=cls._BROWSE_PATH,
                surface="elasticsearch_browse",
                policy_destination=str(settings["base_url"]),
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=cls._auth_headers(settings),
                params={
                    "format": "json",
                    "h": "index,health,status,docs.count,store.size",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError("Elasticsearch browse response must be a JSON list.")
            items: list[dict[str, Any]] = []
            for row in payload:
                if not isinstance(row, dict):
                    continue
                index_name = str(row.get("index", "") or "").strip()
                if not index_name:
                    continue
                if not include_hidden and index_name.startswith("."):
                    continue
                items.append(
                    {
                        "id": index_name,
                        "label": index_name,
                        "kind": "index",
                        "selection": {"index": index_name},
                        "health": str(row.get("health", "") or "").strip() or None,
                        "status": str(row.get("status", "") or "").strip() or None,
                        "docs_count": str(row.get("docs.count", "") or "").strip() or None,
                        "row_count": cls._parse_optional_int(row.get("docs.count")),
                        "store_size": str(row.get("store.size", "") or "").strip() or None,
                    }
                )
                if len(items) >= limit:
                    break
            return items
        except Exception:
            discard_client = True
            raise
        finally:
            cls._release_client(settings, client, discard=discard_client)

    @classmethod
    def _fetch_sync(
        cls,
        settings: dict[str, Any],
        index: str,
        query: dict[str, Any],
        limit: int,
        audit_context: EgressAuditContext | None = None,
    ) -> list[dict[str, Any]]:
        client = cls._acquire_client(settings)
        discard_client = False
        try:
            payload = dict(query)
            payload.setdefault("size", limit)
            path = f"/{quote(index, safe=',*')}/_search"
            response = sync_http_request(
                method="POST",
                url=path,
                surface="elasticsearch_fetch",
                policy_destination=str(settings["base_url"]),
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=cls._auth_headers(settings),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            if not isinstance(hits, list):
                raise RuntimeError("Elasticsearch search response missing hits.hits list.")
            rows: list[dict[str, Any]] = []
            for hit in hits[:limit]:
                if not isinstance(hit, dict):
                    continue
                source = hit.get("_source")
                row: dict[str, Any] = {}
                if isinstance(source, dict):
                    for key, value in source.items():
                        row[str(key)] = value
                elif source is not None:
                    row["_source"] = source
                row["_index"] = hit.get("_index")
                row["_id"] = hit.get("_id")
                row["_score"] = hit.get("_score")
                rows.append(row)
            return rows
        except Exception:
            discard_client = True
            raise
        finally:
            cls._release_client(settings, client, discard=discard_client)
