"""Oracle Database connector using python-oracledb Thin mode and Arrow batches."""

from __future__ import annotations

import asyncio
import atexit
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, ClassVar

from apps.api_server.services.connector_egress import (
    connector_audit_context,
    connector_host_destination,
    enforce_connector_destination,
)

from .base import BaseConnector, ConnectorRegistry

_HOST_PATTERN = re.compile(r"\(\s*HOST\s*=\s*([^)\s]+)\s*\)", re.IGNORECASE)
_PORT_PATTERN = re.compile(r"\(\s*PORT\s*=\s*(\d+)\s*\)", re.IGNORECASE)
_EASY_CONNECT_PATTERN = re.compile(
    r"^(?:tcps?://)?(?P<host>[^:/()\s]+)(?::(?P<port>\d+))?/(?P<service>[^?\s]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class OracleConnectionSettings:
    user: str
    password: str
    dsn: str
    host: str
    port: int
    config_dir: str | None = None
    wallet_location: str | None = None
    wallet_password: str | None = None


@dataclass(frozen=True, slots=True)
class OraclePoolSettings:
    minimum: int
    maximum: int
    increment: int
    wait_timeout_ms: int
    idle_timeout_seconds: int
    ping_interval_seconds: int


@dataclass(frozen=True, slots=True)
class _OraclePoolCacheKey:
    """Process-local pool identity with credentials excluded from representations."""

    user: str
    password: str = field(repr=False)
    dsn: str
    host: str
    port: int
    config_dir: str | None
    wallet_location: str | None
    wallet_password: str | None = field(repr=False)
    pool_settings: OraclePoolSettings


class _OraclePoolGroup:
    """Bounded Thin-mode pool shards with deterministic least-loaded routing."""

    def __init__(
        self,
        connect_kwargs: dict[str, Any],
        settings: OraclePoolSettings,
    ) -> None:
        self._connect_kwargs = connect_kwargs
        self._settings = settings
        self._lock = threading.RLock()
        self._closed = False
        self._acquiring = 0
        self._pools = [
            self._create_pool(minimum=1 if index < settings.minimum else 0)
            for index in range(settings.maximum)
        ]
        self._claims = [0] * settings.maximum
        self._active_count = max(1, settings.minimum)

    def _create_pool(self, *, minimum: int) -> Any:
        import oracledb

        return oracledb.create_pool(
            **self._connect_kwargs,
            min=minimum,
            max=1,
            increment=1,
            getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
            wait_timeout=self._settings.wait_timeout_ms,
            timeout=self._settings.idle_timeout_seconds,
            ping_interval=self._settings.ping_interval_seconds,
        )

    def acquire(self) -> Any:
        with self._lock:
            if self._closed:
                raise RuntimeError("Oracle connection pool is closed.")
            active_loads = [
                int(getattr(self._pools[index], "busy", 0)) + self._claims[index]
                for index in range(self._active_count)
            ]
            if min(active_loads) > 0 and self._active_count < len(self._pools):
                self._active_count = min(
                    len(self._pools),
                    self._active_count + self._settings.increment,
                )
                active_loads.extend([0] * (self._active_count - len(active_loads)))
            selected_index = min(
                range(self._active_count),
                key=lambda index: (active_loads[index], index),
            )
            selected_pool = self._pools[selected_index]
            self._claims[selected_index] += 1
            self._acquiring += 1
        try:
            return selected_pool.acquire()
        finally:
            with self._lock:
                self._acquiring -= 1
                self._claims[selected_index] -= 1

    @property
    def busy(self) -> int:
        with self._lock:
            return self._acquiring + sum(int(getattr(pool, "busy", 0)) for pool in self._pools)

    def close(self, *, force: bool) -> None:
        with self._lock:
            self._closed = True
            pools = tuple(self._pools)
        for pool in pools:
            pool.close(force=force)


def _text(config: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = config.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _positive_int(value: Any, *, default: int, field_name: str) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        raise ValueError(f"Oracle connector {field_name} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Oracle connector {field_name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError(f"Oracle connector {field_name} must be a positive integer.")
    return parsed


def _non_negative_int(value: Any, *, default: int, field_name: str) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        raise ValueError(f"Oracle connector {field_name} must be a non-negative integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Oracle connector {field_name} must be a non-negative integer.") from exc
    if parsed < 0:
        raise ValueError(f"Oracle connector {field_name} must be a non-negative integer.")
    return parsed


def _settings_from_sqlalchemy_url(connection_string: str) -> dict[str, Any]:
    from sqlalchemy.engine import make_url

    url = make_url(connection_string)
    if not url.drivername.startswith("oracle"):
        raise ValueError("Oracle connection_string must use oracle or oracle+oracledb.")
    query = dict(url.query)
    return {
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port,
        "service_name": query.get("service_name") or url.database,
        "dsn": query.get("dsn"),
        "config_dir": query.get("config_dir"),
        "wallet_location": query.get("wallet_location"),
        "wallet_password": query.get("wallet_password"),
    }


def _dsn_host_port(dsn: str) -> tuple[str, int | None]:
    host_match = _HOST_PATTERN.search(dsn)
    if host_match:
        port_match = _PORT_PATTERN.search(dsn)
        return host_match.group(1), int(port_match.group(1)) if port_match else None
    easy_match = _EASY_CONNECT_PATTERN.match(dsn.strip())
    if easy_match:
        raw_port = easy_match.group("port")
        return easy_match.group("host"), int(raw_port) if raw_port else None
    return "", None


@ConnectorRegistry.register
class OracleConnector(BaseConnector):
    """Fetch Oracle query results through a pooled Arrow-compatible fast path."""

    connector_type = "oracle"
    _DEFAULT_PORT = 1521
    _DEFAULT_BATCH_SIZE = 10_000
    _POOL_CACHE_MAX_SIZE = 16
    _pool_cache: ClassVar[OrderedDict[_OraclePoolCacheKey, _OraclePoolGroup]] = OrderedDict()
    _pool_cache_lock: ClassVar[threading.RLock] = threading.RLock()
    _BROWSE_STATEMENT = """
        SELECT owner, object_name, object_type
        FROM all_objects
        WHERE object_type IN ('TABLE', 'VIEW')
          AND owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'CTXSYS', 'MDSYS', 'ORDSYS')
        ORDER BY owner, object_name
        FETCH FIRST 200 ROWS ONLY
    """
    _BROWSE_SCHEMA_STATEMENT = """
        SELECT owner, object_name, object_type
        FROM all_objects
        WHERE object_type IN ('TABLE', 'VIEW')
          AND owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'CTXSYS', 'MDSYS', 'ORDSYS')
          AND owner = :owner
        ORDER BY owner, object_name
        FETCH FIRST 200 ROWS ONLY
    """

    @classmethod
    def connection_settings(cls, config: dict[str, Any]) -> OracleConnectionSettings:
        merged = dict(config)
        connection_string = _text(config, "connection_string")
        if connection_string:
            parsed = _settings_from_sqlalchemy_url(connection_string)
            for key, value in parsed.items():
                if value not in (None, "") and merged.get(key) in (None, ""):
                    merged[key] = value

        user = _text(merged, "user", "username")
        password = _text(merged, "password")
        dsn = _text(merged, "dsn", "connect_descriptor")
        host = _text(merged, "host")
        service_name = _text(merged, "service_name", "database")
        wallet_location = _text(merged, "wallet_location") or None
        config_dir = _text(merged, "config_dir", "tns_admin") or None
        wallet_password = _text(merged, "wallet_password") or None
        default_port = 1522 if wallet_location else cls._DEFAULT_PORT
        port = _positive_int(merged.get("port"), default=default_port, field_name="port")

        if not dsn and host and service_name:
            protocol = "tcps" if wallet_location else "tcp"
            dsn = f"{protocol}://{host}:{port}/{service_name}"
        parsed_host, parsed_port = _dsn_host_port(dsn)
        host = host or parsed_host
        port = parsed_port or port

        missing = [
            field
            for field, value in (("user", user), ("password", password), ("dsn", dsn))
            if not value
        ]
        if missing:
            raise ValueError("Oracle connector requires non-empty " + ", ".join(missing) + ".")
        if not host:
            raise ValueError(
                "Oracle connector requires host or a DSN containing HOST for egress validation."
            )
        if wallet_location and not wallet_password:
            raise ValueError(
                "Oracle connector wallet_location requires wallet_password in Thin mode."
            )

        return OracleConnectionSettings(
            user=user,
            password=password,
            dsn=dsn,
            host=host,
            port=port,
            config_dir=config_dir,
            wallet_location=wallet_location,
            wallet_password=wallet_password,
        )

    @staticmethod
    def _connect_kwargs(settings: OracleConnectionSettings) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "user": settings.user,
            "password": settings.password,
            "dsn": settings.dsn,
        }
        if settings.config_dir:
            kwargs["config_dir"] = settings.config_dir
        if settings.wallet_location:
            kwargs["wallet_location"] = settings.wallet_location
            kwargs["wallet_password"] = settings.wallet_password
        return kwargs

    @classmethod
    def pool_settings(cls, config: dict[str, Any]) -> OraclePoolSettings:
        minimum = _non_negative_int(
            config.get("pool_min"),
            default=0,
            field_name="pool_min",
        )
        maximum = _positive_int(
            config.get("pool_max"),
            default=4,
            field_name="pool_max",
        )
        increment = _positive_int(
            config.get("pool_increment"),
            default=1,
            field_name="pool_increment",
        )
        if maximum < minimum:
            raise ValueError("Oracle connector pool_max must be at least pool_min.")
        if increment > maximum:
            raise ValueError("Oracle connector pool_increment cannot exceed pool_max.")
        return OraclePoolSettings(
            minimum=minimum,
            maximum=maximum,
            increment=increment,
            wait_timeout_ms=_positive_int(
                config.get("pool_wait_timeout_ms"),
                default=2_000,
                field_name="pool_wait_timeout_ms",
            ),
            idle_timeout_seconds=_positive_int(
                config.get("pool_idle_timeout_seconds"),
                default=300,
                field_name="pool_idle_timeout_seconds",
            ),
            ping_interval_seconds=_positive_int(
                config.get("pool_ping_interval_seconds"),
                default=60,
                field_name="pool_ping_interval_seconds",
            ),
        )

    @staticmethod
    def _pool_cache_key(
        settings: OracleConnectionSettings,
        pool_settings: OraclePoolSettings,
    ) -> _OraclePoolCacheKey:
        return _OraclePoolCacheKey(
            user=settings.user,
            password=settings.password,
            dsn=settings.dsn,
            host=settings.host,
            port=settings.port,
            config_dir=settings.config_dir,
            wallet_location=settings.wallet_location,
            wallet_password=settings.wallet_password,
            pool_settings=pool_settings,
        )

    @classmethod
    def close_pools(cls) -> None:
        with cls._pool_cache_lock:
            pools = list(cls._pool_cache.values())
            cls._pool_cache.clear()
        for pool in pools:
            pool.close(force=True)

    @classmethod
    def _evict_idle_pool_locked(cls) -> bool:
        for cache_key, pool in tuple(cls._pool_cache.items()):
            if pool.busy != 0:
                continue
            cls._pool_cache.pop(cache_key, None)
            pool.close(force=True)
            return True
        return False

    @classmethod
    def _pool_for_settings(
        cls,
        settings: OracleConnectionSettings,
        pool_settings: OraclePoolSettings,
    ) -> tuple[_OraclePoolCacheKey, _OraclePoolGroup]:
        cache_key = cls._pool_cache_key(settings, pool_settings)
        with cls._pool_cache_lock:
            cached_pool = cls._pool_cache.get(cache_key)
            if cached_pool is not None:
                cls._pool_cache.move_to_end(cache_key)
                return cache_key, cached_pool
            if len(cls._pool_cache) >= cls._POOL_CACHE_MAX_SIZE:
                cls._evict_idle_pool_locked()
            if len(cls._pool_cache) >= cls._POOL_CACHE_MAX_SIZE:
                raise RuntimeError(
                    "Oracle pool cache is at capacity and every cached pool is busy."
                )
            pool = _OraclePoolGroup(cls._connect_kwargs(settings), pool_settings)
            cls._pool_cache[cache_key] = pool
            return cache_key, pool

    @classmethod
    def _enforce_egress(
        cls,
        settings: OracleConnectionSettings,
        config: dict[str, Any],
        *,
        surface: str,
    ) -> None:
        enforce_connector_destination(
            connector_host_destination(settings.host, port=settings.port),
            surface=surface,
            audit_context=connector_audit_context(config),
        )

    @classmethod
    def _connect_sync(
        cls,
        settings: OracleConnectionSettings,
        config: dict[str, Any],
    ) -> Any:
        pool_settings = cls.pool_settings(config)
        cache_key, pool = cls._pool_for_settings(settings, pool_settings)
        try:
            return pool.acquire()
        except Exception:
            with cls._pool_cache_lock:
                if pool.busy == 0:
                    cls._pool_cache.pop(cache_key, None)
                    pool.close(force=True)
            raise

    @staticmethod
    def _bounded_query(query: str, limit: int | None) -> tuple[str, dict[str, int]]:
        query_body = query.strip().rstrip(";")
        if not query_body:
            raise ValueError("Oracle connector query is required.")
        first_token = query_body.lstrip().split(None, 1)[0].upper()
        if first_token not in {"SELECT", "WITH"}:
            raise ValueError("Oracle connector query must be a SELECT or WITH statement.")
        if limit is None:
            return query_body, {}
        return (
            f"SELECT * FROM ({query_body}) algenta_source WHERE ROWNUM <= :algenta_limit",  # noqa: S608 -- explicit connector query input
            {"algenta_limit": limit},
        )

    @classmethod
    def _fetch_table_sync(cls, config: dict[str, Any]) -> Any | None:
        import pyarrow as pa

        settings = cls.connection_settings(config)
        cls._enforce_egress(settings, config, surface="oracle_connector_fetch_table")
        limit_value = config.get("limit")
        limit = (
            None
            if limit_value in (None, "")
            else _positive_int(limit_value, default=1, field_name="limit")
        )
        batch_size = _positive_int(
            config.get("fetch_batch_size"),
            default=cls._DEFAULT_BATCH_SIZE,
            field_name="fetch_batch_size",
        )
        statement, parameters = cls._bounded_query(_text(config, "query"), limit)
        connection = cls._connect_sync(settings, config)
        try:
            tables = [
                pa.table(frame)
                for frame in connection.fetch_df_batches(
                    statement=statement,
                    parameters=parameters or None,
                    size=batch_size,
                )
            ]
        finally:
            connection.close()
        if not tables:
            return None
        if len(tables) == 1:
            return tables[0]
        return pa.concat_tables(tables, promote_options="permissive")

    @classmethod
    def _validate_sync(cls, config: dict[str, Any]) -> None:
        settings = cls.connection_settings(config)
        cls._enforce_egress(settings, config, surface="oracle_connector_validate")
        connection = cls._connect_sync(settings, config)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                row = cursor.fetchone()
                if row is None or int(row[0]) != 1:
                    raise RuntimeError("Oracle validation query returned an unexpected result.")
        finally:
            connection.close()

    @classmethod
    def _browse_sync(cls, config: dict[str, Any]) -> list[dict[str, Any]]:
        settings = cls.connection_settings(config)
        cls._enforce_egress(settings, config, surface="oracle_connector_browse")
        requested_schema = _text(config, "schema").upper()
        parameters = {"owner": requested_schema} if requested_schema else None
        statement = cls._BROWSE_SCHEMA_STATEMENT if requested_schema else cls._BROWSE_STATEMENT
        connection = cls._connect_sync(settings, config)
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters or {})
                rows = cursor.fetchall()
        finally:
            connection.close()
        return [
            {
                "id": f"{owner}.{object_name}",
                "label": f"{owner}.{object_name}",
                "kind": str(object_type).lower(),
                "selection": {"table": f"{owner}.{object_name}"},
                "schema": owner,
                "name": object_name,
            }
            for owner, object_name, object_type in rows
        ]

    async def fetch_table(self) -> Any | None:
        return await asyncio.to_thread(self._fetch_table_sync, self.config)

    async def fetch_data(self) -> list[dict[str, Any]]:
        table = await self.fetch_table()
        return [] if table is None else table.to_pylist()

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            await asyncio.to_thread(self._validate_sync, self.config)
            return True, "Oracle Database connection successful."
        except Exception:
            return False, "Oracle Database connection failed."


atexit.register(OracleConnector.close_pools)
