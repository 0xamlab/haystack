"""Redis connector for deterministic key-value inspection."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from threading import Lock
from typing import Any
from urllib.parse import quote, unquote, urlparse

from apps.api_server.services.connector_egress import (
    connector_audit_context,
    enforce_redis_connection_egress,
)

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class RedisConnector(BaseConnector):
    """Fetch deterministic key snapshots from Redis.

    Config keys:
        url / connection_string / redis_url:
            Redis DSN, for example redis://user:pass@host:6379/0
        keys:
            Explicit Redis keys to materialize. Required for fetch_data().
        value_max_items:
            Maximum collection members to include per key snapshot.
        key_pattern:
            Optional pattern for browse helpers.
        limit:
            Optional browse limit.
    """

    connector_type = "redis"
    _DEFAULT_SOCKET_TIMEOUT_SECONDS = 5.0
    _DEFAULT_SCAN_LIMIT = 100
    _DEFAULT_VALUE_MAX_ITEMS = 100
    _SCAN_HEADROOM_FACTOR = 4
    _DEFAULT_SCAN_CAP_FLOOR = 50
    _DEFAULT_SCAN_CAP_CEILING = 500
    _CLIENTS: dict[str, Any] = {}
    _CLIENTS_LOCK = Lock()

    async def fetch_data(self) -> list[dict[str, Any]]:
        connection_url = self._connection_url(self.config)
        keys = self._configured_keys(self.config)
        if not keys:
            raise ValueError("Redis connector fetch_data requires a non-empty 'keys' list.")
        value_max_items = self._positive_int(
            self.config.get("value_max_items"),
            default=self._DEFAULT_VALUE_MAX_ITEMS,
            field_name="value_max_items",
        )
        return await asyncio.to_thread(
            self._fetch_sync,
            connection_url,
            keys,
            value_max_items,
            connector_audit_context(self.config),
        )

    async def validate_connection(self) -> tuple[bool, str]:
        connection_url = self._connection_url(self.config)
        try:
            await asyncio.to_thread(
                self._validate_sync,
                connection_url,
                connector_audit_context(self.config),
            )
        except Exception as exc:
            return False, f"Connection failed: {exc}"
        return True, "Connected successfully."

    @classmethod
    def _connection_url(cls, config: dict[str, Any]) -> str:
        for field_name in ("connection_string", "url", "redis_url"):
            raw_value = config.get(field_name)
            if isinstance(raw_value, str) and raw_value.strip():
                return raw_value.strip()

        host = str(config.get("host", "") or "").strip()
        if not host:
            raise ValueError("Redis connector requires url, redis_url, or connection_string.")
        port = int(config.get("port", 6379) or 6379)
        db = int(config.get("database", config.get("db", 0)) or 0)
        user = str(config.get("user", config.get("username", "")) or "").strip()
        password = str(config.get("password", "") or "")
        auth = ""
        if user or password:
            auth = f"{quote(user, safe='')}:{quote(password, safe='')}@"
        return f"redis://{auth}{host}:{port}/{db}"

    @classmethod
    def _parse_connection_url(cls, connection_url: str) -> dict[str, Any]:
        parsed = urlparse(connection_url)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError(f"Unsupported Redis connection string: {connection_url}")
        if not parsed.hostname:
            raise ValueError("Redis connection string requires host.")
        database = 0
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            try:
                database = int(path_parts[0])
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError("Redis connection string database must be an integer.") from exc
        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port or (6380 if parsed.scheme == "rediss" else 6379),
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": database,
        }

    @classmethod
    def _connect_sync(cls, connection_url: str) -> Any:
        import redis

        redis_module: Any = redis
        return redis_module.from_url(
            connection_url,
            decode_responses=True,
            socket_connect_timeout=cls._DEFAULT_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=cls._DEFAULT_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=30,
        )

    @staticmethod
    def _close_sync(client: Any) -> None:
        try:
            client.close()
        except Exception:
            return

    @classmethod
    def _validate_sync(
        cls,
        connection_url: str,
        audit_context: object | None = None,
    ) -> None:
        enforce_redis_connection_egress(
            connection_url,
            surface="redis_connector_validate",
            audit_context=audit_context,
        )
        client = cls._acquire_client(connection_url)
        discard_client = False
        try:
            client.ping()
        except Exception:
            discard_client = True
            raise
        finally:
            cls._release_client(connection_url, client, discard=discard_client)

    @classmethod
    def _browse_sync(
        cls,
        connection_url: str,
        *,
        pattern: str,
        limit: int,
        audit_context: object | None = None,
    ) -> list[dict[str, Any]]:
        items, _metadata = cls._browse_summary_sync(
            connection_url,
            pattern=pattern,
            limit=limit,
            audit_context=audit_context,
        )
        return items

    @classmethod
    def _browse_summary_sync(
        cls,
        connection_url: str,
        *,
        pattern: str,
        limit: int,
        audit_context: object | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        enforce_redis_connection_egress(
            connection_url,
            surface="redis_connector_browse",
            audit_context=audit_context,
        )
        client = cls._acquire_client(connection_url)
        discard_client = False
        try:
            keys, scan_exhausted, scan_cap = cls._scan_keys_with_meta(
                client,
                pattern=pattern,
                limit=limit,
            )
            items = cls._browse_items_for_keys(client, keys)
            keyspace_total_count: int | None = None
            dbsize = getattr(client, "dbsize", None)
            if callable(dbsize):
                try:
                    keyspace_total_count = int(dbsize())
                except Exception:
                    keyspace_total_count = None
            metadata = {
                "keyspace_total_count": keyspace_total_count,
                "scan_exhausted": scan_exhausted,
                "scan_cap": scan_cap,
                "pattern": pattern,
                "returned_count": len(items),
            }
            return items, metadata
        except Exception:
            discard_client = True
            raise
        finally:
            cls._release_client(connection_url, client, discard=discard_client)

    @classmethod
    def _fetch_sync(
        cls,
        connection_url: str,
        keys: list[str],
        value_max_items: int,
        audit_context: object | None = None,
    ) -> list[dict[str, Any]]:
        enforce_redis_connection_egress(
            connection_url,
            surface="redis_connector_fetch",
            audit_context=audit_context,
        )
        client = cls._acquire_client(connection_url)
        discard_client = False
        try:
            return cls._materialize_key_records(
                client,
                keys,
                value_max_items=value_max_items,
            )
        except Exception:
            discard_client = True
            raise
        finally:
            cls._release_client(connection_url, client, discard=discard_client)

    @classmethod
    def _acquire_client(cls, connection_url: str) -> Any:
        with cls._CLIENTS_LOCK:
            client = cls._CLIENTS.get(connection_url)
            if client is None:
                client = cls._connect_sync(connection_url)
                cls._CLIENTS[connection_url] = client
            return client

    @classmethod
    def _release_client(
        cls,
        connection_url: str,
        client: Any,
        *,
        discard: bool,
    ) -> None:
        if not discard:
            return
        with cls._CLIENTS_LOCK:
            cached = cls._CLIENTS.get(connection_url)
            if cached is client:
                cls._CLIENTS.pop(connection_url, None)
        cls._close_sync(client)

    @classmethod
    def _clear_client_cache(cls) -> None:
        with cls._CLIENTS_LOCK:
            clients = list(cls._CLIENTS.values())
            cls._CLIENTS = {}
        for client in clients:
            cls._close_sync(client)

    @classmethod
    def _configured_keys(cls, config: dict[str, Any]) -> list[str]:
        raw_keys = config.get("keys")
        if raw_keys is None:
            return []
        if isinstance(raw_keys, str):
            items = [item.strip() for item in raw_keys.split(",")]
        elif isinstance(raw_keys, Iterable):
            items = [str(item).strip() for item in raw_keys]
        else:
            raise ValueError(
                "Redis connector keys must be a list of strings or comma-separated string."
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not item or item in seen:
                continue
            normalized.append(item)
            seen.add(item)
        return normalized

    @classmethod
    def _positive_int(cls, raw_value: Any, *, default: int, field_name: str) -> int:
        if raw_value in (None, ""):
            return default
        value = int(raw_value)
        if value <= 0:
            raise ValueError(f"Redis connector {field_name} must be greater than zero.")
        return value

    @classmethod
    def _scan_keys(cls, client: Any, *, pattern: str, limit: int) -> list[str]:
        keys, _scan_exhausted, _scan_cap = cls._scan_keys_with_meta(
            client,
            pattern=pattern,
            limit=limit,
        )
        return keys

    @classmethod
    def _scan_keys_with_meta(
        cls,
        client: Any,
        *,
        pattern: str,
        limit: int,
    ) -> tuple[list[str], bool, int]:
        safe_limit = cls._positive_int(limit, default=cls._DEFAULT_SCAN_LIMIT, field_name="limit")
        scan_cap = min(
            max(safe_limit * cls._SCAN_HEADROOM_FACTOR, cls._DEFAULT_SCAN_CAP_FLOOR),
            cls._DEFAULT_SCAN_CAP_CEILING,
        )
        cursor = 0
        scan_exhausted = False
        discovered: set[str] = set()
        scan_count = min(max(scan_cap, safe_limit, 10), 500)
        while True:
            cursor, batch = client.scan(
                cursor=cursor,
                match=pattern,
                count=scan_count,
            )
            for raw_key in batch:
                key = str(raw_key)
                if key:
                    discovered.add(key)
            if cursor == 0:
                scan_exhausted = True
                break
            if len(discovered) >= scan_cap:
                break
        return sorted(discovered)[:safe_limit], scan_exhausted, scan_cap

    @classmethod
    def _browse_items_for_keys(cls, client: Any, keys: list[str]) -> list[dict[str, Any]]:
        if not keys:
            return []
        pipeline = client.pipeline(transaction=False)
        for key in keys:
            pipeline.type(key)
            pipeline.ttl(key)
        responses = pipeline.execute()
        items: list[dict[str, Any]] = []
        for index, key in enumerate(keys):
            value_type = str(responses[index * 2] or "none")
            ttl_seconds = int(responses[(index * 2) + 1])
            items.append(
                {
                    "id": key,
                    "label": key,
                    "kind": "key",
                    "selection": {"keys": [key]},
                    "value_type": value_type,
                    "ttl_seconds": ttl_seconds,
                }
            )
        return items

    @classmethod
    def _materialize_key_records(
        cls,
        client: Any,
        keys: list[str],
        *,
        value_max_items: int,
    ) -> list[dict[str, Any]]:
        if not keys:
            return []
        pipeline = client.pipeline(transaction=False)
        for key in keys:
            pipeline.get(key)
            pipeline.ttl(key)
        responses = pipeline.execute(raise_on_error=False)

        rows: list[dict[str, Any] | None] = [None] * len(keys)
        fallback_indexes: list[int] = []
        for index, key in enumerate(keys):
            raw_value = responses[index * 2]
            ttl_seconds = int(responses[(index * 2) + 1])
            if isinstance(raw_value, Exception):
                fallback_indexes.append(index)
                continue
            if raw_value is None:
                if ttl_seconds == -2:
                    rows[index] = cls._base_record(
                        key,
                        value_type="none",
                        ttl_seconds=ttl_seconds,
                    )
                    continue
                fallback_indexes.append(index)
                continue
            rows[index] = cls._materialize_string_record(
                key,
                ttl_seconds=ttl_seconds,
                raw_value=raw_value,
            )

        if fallback_indexes:
            fallback_keys = [keys[index] for index in fallback_indexes]
            fallback_rows = cls._materialize_non_string_records(
                client,
                fallback_keys,
                value_max_items=value_max_items,
            )
            for row_index, row in zip(fallback_indexes, fallback_rows, strict=False):
                rows[row_index] = row

        return [row for row in rows if row is not None]

    @classmethod
    def _materialize_non_string_records(
        cls,
        client: Any,
        keys: list[str],
        *,
        value_max_items: int,
    ) -> list[dict[str, Any]]:
        pipeline = client.pipeline(transaction=False)
        for key in keys:
            pipeline.type(key)
            pipeline.ttl(key)
        responses = pipeline.execute()
        rows: list[dict[str, Any]] = []
        for index, key in enumerate(keys):
            value_type = str(responses[index * 2] or "none")
            ttl_seconds = int(responses[(index * 2) + 1])
            rows.append(
                cls._materialize_key_record(
                    client,
                    key,
                    value_type=value_type,
                    ttl_seconds=ttl_seconds,
                    value_max_items=value_max_items,
                )
            )
        return rows

    @classmethod
    def _materialize_key_record(
        cls,
        client: Any,
        key: str,
        *,
        value_type: str,
        ttl_seconds: int,
        value_max_items: int,
    ) -> dict[str, Any]:
        record = cls._base_record(
            key,
            value_type=value_type,
            ttl_seconds=ttl_seconds,
        )
        if value_type == "none":
            return record
        if value_type == "string":
            return cls._materialize_string_record(
                key,
                ttl_seconds=ttl_seconds,
                raw_value=client.get(key),
            )
        if value_type == "hash":
            mapping = {str(k): str(v) for k, v in client.hgetall(key).items()}
            record.update(cls._serialize_mapping(mapping, value_max_items=value_max_items))
            return record
        if value_type == "list":
            total_items = int(client.llen(key))
            items = [str(item) for item in client.lrange(key, 0, value_max_items - 1)]
            record.update(
                cls._serialize_sequence(
                    items,
                    total_items=total_items,
                    value_max_items=value_max_items,
                )
            )
            return record
        if value_type == "set":
            members = sorted(str(member) for member in client.smembers(key))
            record.update(
                cls._serialize_sequence(
                    members[:value_max_items],
                    total_items=len(members),
                    value_max_items=value_max_items,
                )
            )
            return record
        if value_type == "zset":
            total_items = int(client.zcard(key))
            pairs = client.zrange(key, 0, value_max_items - 1, withscores=True)
            zset_items = [
                {
                    "member": str(member),
                    "score": float(score),
                }
                for member, score in pairs
            ]
            record.update(
                cls._serialize_json(
                    zset_items,
                    total_items=total_items,
                    value_max_items=value_max_items,
                )
            )
            return record
        if value_type == "stream":
            total_items = int(client.xlen(key))
            entries = [
                {
                    "id": str(entry_id),
                    "fields": {str(field): str(value) for field, value in sorted(fields.items())},
                }
                for entry_id, fields in client.xrange(key, count=value_max_items)
            ]
            record.update(
                cls._serialize_json(
                    entries,
                    total_items=total_items,
                    value_max_items=value_max_items,
                )
            )
            return record
        record["value_text"] = f"<unsupported:{value_type}>"
        return record

    @staticmethod
    def _base_record(
        key: str,
        *,
        value_type: str,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "value_type": value_type,
            "ttl_seconds": ttl_seconds,
            "exists": value_type != "none",
            "item_count": 0,
            "truncated": False,
            "value_text": None,
            "value_json": None,
        }

    @classmethod
    def _materialize_string_record(
        cls,
        key: str,
        *,
        ttl_seconds: int,
        raw_value: Any,
    ) -> dict[str, Any]:
        record = cls._base_record(key, value_type="string", ttl_seconds=ttl_seconds)
        text_value = "" if raw_value is None else str(raw_value)
        canonical_json = cls._canonical_json_string(text_value)
        if canonical_json is None:
            record["value_text"] = text_value
        else:
            record["value_json"] = canonical_json
        record["item_count"] = 1
        return record

    @staticmethod
    def _canonical_json_string(text_value: str) -> str | None:
        stripped = text_value.strip()
        if not stripped:
            return None
        if not (
            (stripped.startswith("{") and stripped.endswith("}"))
            or (stripped.startswith("[") and stripped.endswith("]"))
        ):
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _serialize_mapping(
        mapping: dict[str, str],
        *,
        value_max_items: int,
    ) -> dict[str, Any]:
        items = sorted(mapping.items())[:value_max_items]
        serialized = dict(items)
        return {
            "item_count": len(mapping),
            "truncated": len(mapping) > len(serialized),
            "value_json": json.dumps(
                serialized,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            "value_text": None,
        }

    @staticmethod
    def _serialize_sequence(
        items: list[str],
        *,
        total_items: int,
        value_max_items: int,
    ) -> dict[str, Any]:
        sample = items[:value_max_items]
        return {
            "item_count": total_items,
            "truncated": total_items > len(sample),
            "value_json": json.dumps(sample, separators=(",", ":"), ensure_ascii=True),
            "value_text": None,
        }

    @staticmethod
    def _serialize_json(
        payload: list[dict[str, Any]],
        *,
        total_items: int,
        value_max_items: int,
    ) -> dict[str, Any]:
        sample = payload[:value_max_items]
        return {
            "item_count": total_items,
            "truncated": total_items > len(sample),
            "value_json": json.dumps(
                sample,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            "value_text": None,
        }
