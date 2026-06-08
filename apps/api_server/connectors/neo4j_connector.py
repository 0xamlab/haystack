"""Neo4j connector for explicit Cypher fetches and connectivity checks."""

from __future__ import annotations

import asyncio
from threading import Lock
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse

from apps.api_server.services.connector_egress import (
    connector_audit_context,
    enforce_neo4j_settings_egress,
)

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class Neo4jConnector(BaseConnector):
    """Run explicit Cypher queries against Neo4j.

    Config keys:
        uri / url / connection_string:
            Neo4j URI, for example neo4j+s://example.databases.neo4j.io
        username / user:
            Neo4j username.
        password:
            Neo4j password.
        database:
            Optional database name. Defaults to the server default.
        query / cypher:
            Explicit Cypher query to execute for fetch_data().
        parameters:
            Optional Cypher parameters.
        limit:
            Optional maximum number of records to materialize. Defaults to 1000.
    """

    connector_type = "neo4j"
    _DEFAULT_LIMIT = 1000
    _DEFAULT_CONNECTION_TIMEOUT_SECONDS = 5.0
    _VALIDATE_QUERY = "RETURN 1 AS ok"
    _BROWSE_QUERY = """
    CALL () {
      CALL db.labels() YIELD label
      RETURN "label" AS item_kind, label AS item_value
      UNION ALL
      CALL db.relationshipTypes() YIELD relationshipType
      RETURN "relationship_type" AS item_kind, relationshipType AS item_value
    }
    RETURN item_kind, item_value
    ORDER BY item_kind, item_value
    LIMIT $limit
    """
    _DRIVERS: dict[tuple[str, str, str], Any] = {}
    _DRIVERS_LOCK = Lock()

    async def fetch_data(self) -> list[dict[str, Any]]:
        settings = self._connection_settings(self.config)
        query = self._query_text(self.config)
        parameters = self._query_parameters(self.config)
        limit = self._positive_int(
            self.config.get("limit"),
            default=self._DEFAULT_LIMIT,
            field_name="limit",
        )
        return await asyncio.to_thread(
            self._fetch_sync,
            settings,
            query,
            parameters,
            limit,
            connector_audit_context(self.config),
        )

    async def validate_connection(self) -> tuple[bool, str]:
        settings = self._connection_settings(self.config)
        try:
            await asyncio.to_thread(
                self._validate_sync,
                settings,
                connector_audit_context(self.config),
            )
        except Exception as exc:
            return False, f"Connection failed: {exc}"
        return True, "Connected successfully."

    @classmethod
    def _connection_settings(cls, config: dict[str, Any]) -> dict[str, str]:
        raw_uri = ""
        for field_name in ("uri", "url", "connection_string"):
            raw_value = config.get(field_name)
            if isinstance(raw_value, str) and raw_value.strip():
                raw_uri = raw_value.strip()
                break

        if not raw_uri:
            host = str(config.get("host", "") or "").strip()
            if not host:
                raise ValueError("Neo4j connector requires uri, url, or connection_string.")
            scheme = str(config.get("scheme", "neo4j") or "neo4j").strip()
            port_value = str(config.get("port", "") or "").strip()
            raw_uri = f"{scheme}://{host}{f':{port_value}' if port_value else ''}"

        parsed = urlparse(raw_uri)
        if parsed.scheme not in {
            "neo4j",
            "neo4j+s",
            "neo4j+ssc",
            "bolt",
            "bolt+s",
            "bolt+ssc",
        }:
            raise ValueError(f"Unsupported Neo4j connection string: {raw_uri}")
        if not parsed.hostname:
            raise ValueError("Neo4j connection string requires host.")

        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = host
        if parsed.port is not None:
            netloc += f":{parsed.port}"
        sanitized_uri = urlunparse(parsed._replace(netloc=netloc))

        username = str(config.get("username", config.get("user", "")) or "").strip() or unquote(
            parsed.username or ""
        )
        password = str(config.get("password", "") or "")
        if not password and parsed.password is not None:
            password = unquote(parsed.password)
        if not username:
            raise ValueError("Neo4j connector requires username or user.")
        if password == "":
            raise ValueError("Neo4j connector requires password.")

        database = str(config.get("database", config.get("db", "")) or "").strip()
        return {
            "uri": sanitized_uri,
            "username": username,
            "password": password,
            "database": database,
            "host": parsed.hostname,
            "port": str(parsed.port or ""),
        }

    @classmethod
    def _query_text(cls, config: dict[str, Any]) -> str:
        query = str(config.get("query", config.get("cypher", "")) or "").strip()
        if not query:
            raise ValueError("Neo4j connector fetch_data requires a non-empty 'query' or 'cypher'.")
        return query

    @classmethod
    def _query_parameters(cls, config: dict[str, Any]) -> dict[str, Any]:
        raw_parameters = config.get("parameters", {})
        if raw_parameters in (None, ""):
            return {}
        if not isinstance(raw_parameters, dict):
            raise ValueError("Neo4j connector parameters must be an object.")
        return dict(raw_parameters)

    @classmethod
    def _positive_int(cls, raw_value: Any, *, default: int, field_name: str) -> int:
        if raw_value in (None, ""):
            return default
        value = int(raw_value)
        if value <= 0:
            raise ValueError(f"Neo4j connector {field_name} must be greater than zero.")
        return value

    @classmethod
    def _connect_sync(cls, settings: dict[str, str]) -> Any:
        from neo4j import GraphDatabase

        return GraphDatabase.driver(
            settings["uri"],
            auth=(settings["username"], settings["password"]),
            connection_timeout=cls._DEFAULT_CONNECTION_TIMEOUT_SECONDS,
            connection_acquisition_timeout=cls._DEFAULT_CONNECTION_TIMEOUT_SECONDS,
            liveness_check_timeout=cls._DEFAULT_CONNECTION_TIMEOUT_SECONDS,
            max_connection_lifetime=1800,
        )

    @staticmethod
    def _close_sync(driver: Any) -> None:
        try:
            driver.close()
        except Exception:
            return

    @classmethod
    def _driver_cache_key(cls, settings: dict[str, str]) -> tuple[str, str, str]:
        return (
            settings["uri"],
            settings["username"],
            settings["password"],
        )

    @classmethod
    def _acquire_driver(cls, settings: dict[str, str]) -> Any:
        cache_key = cls._driver_cache_key(settings)
        with cls._DRIVERS_LOCK:
            driver = cls._DRIVERS.get(cache_key)
            if driver is None:
                driver = cls._connect_sync(settings)
                cls._DRIVERS[cache_key] = driver
            return driver

    @classmethod
    def _release_driver(cls, settings: dict[str, str], driver: Any, *, discard: bool) -> None:
        if not discard:
            return
        cache_key = cls._driver_cache_key(settings)
        with cls._DRIVERS_LOCK:
            cached = cls._DRIVERS.get(cache_key)
            if cached is driver:
                cls._DRIVERS.pop(cache_key, None)
        cls._close_sync(driver)

    @classmethod
    def _clear_driver_cache(cls) -> None:
        with cls._DRIVERS_LOCK:
            drivers = list(cls._DRIVERS.values())
            cls._DRIVERS = {}
        for driver in drivers:
            cls._close_sync(driver)

    @classmethod
    def _session_kwargs(cls, settings: dict[str, str]) -> dict[str, Any]:
        database = settings.get("database", "").strip()
        return {"database": database} if database else {}

    @classmethod
    def _validate_sync(
        cls,
        settings: dict[str, str],
        audit_context: object | None = None,
    ) -> None:
        enforce_neo4j_settings_egress(
            settings,
            surface="neo4j_connector_validate",
            audit_context=audit_context,
        )
        driver = cls._acquire_driver(settings)
        discard_driver = False
        try:
            with driver.session(**cls._session_kwargs(settings)) as session:
                record = session.run(cls._VALIDATE_QUERY).single()
            if record is None or int(record["ok"]) != 1:
                raise RuntimeError("Neo4j validation query returned no rows.")
        except Exception:
            discard_driver = True
            raise
        finally:
            cls._release_driver(settings, driver, discard=discard_driver)

    @classmethod
    def _browse_sync(
        cls,
        settings: dict[str, str],
        *,
        limit: int,
        audit_context: object | None = None,
    ) -> list[dict[str, Any]]:
        enforce_neo4j_settings_egress(
            settings,
            surface="neo4j_connector_browse",
            audit_context=audit_context,
        )
        driver = cls._acquire_driver(settings)
        discard_driver = False
        try:
            items: list[dict[str, Any]] = []
            with driver.session(**cls._session_kwargs(settings)) as session:
                result = session.run(cls._BROWSE_QUERY, {"limit": limit})
                for record in result:
                    item_kind = str(record["item_kind"])
                    item_value = str(record["item_value"])
                    if item_kind == "label":
                        items.append(
                            {
                                "id": f"label:{item_value}",
                                "label": item_value,
                                "kind": "label",
                                "selection": {"label": item_value},
                            }
                        )
                    elif item_kind == "relationship_type":
                        items.append(
                            {
                                "id": f"relationship_type:{item_value}",
                                "label": item_value,
                                "kind": "relationship_type",
                                "selection": {"relationship_type": item_value},
                            }
                        )
            return items
        except Exception:
            discard_driver = True
            raise
        finally:
            cls._release_driver(settings, driver, discard=discard_driver)

    @classmethod
    def _fetch_sync(
        cls,
        settings: dict[str, str],
        query: str,
        parameters: dict[str, Any],
        limit: int,
        audit_context: object | None = None,
    ) -> list[dict[str, Any]]:
        enforce_neo4j_settings_egress(
            settings,
            surface="neo4j_connector_fetch",
            audit_context=audit_context,
        )
        driver = cls._acquire_driver(settings)
        discard_driver = False
        try:
            records: list[dict[str, Any]] = []
            with driver.session(**cls._session_kwargs(settings)) as session:
                result = session.run(query, parameters)
                for index, record in enumerate(result):
                    if index >= limit:
                        break
                    records.append(
                        {key: cls._coerce_graph_value(value) for key, value in record.items()}
                    )
            return records
        except Exception:
            discard_driver = True
            raise
        finally:
            cls._release_driver(settings, driver, discard=discard_driver)

    @classmethod
    def _coerce_graph_value(cls, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, list):
            return [cls._coerce_graph_value(item) for item in value]
        if isinstance(value, tuple):
            return [cls._coerce_graph_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._coerce_graph_value(item) for key, item in value.items()}
        if hasattr(value, "labels") and hasattr(value, "element_id") and hasattr(value, "items"):
            return {
                "_type": "node",
                "element_id": str(value.element_id),
                "labels": sorted(str(label) for label in value.labels),
                "properties": {
                    str(key): cls._coerce_graph_value(item)
                    for key, item in dict(value.items()).items()
                },
            }
        if hasattr(value, "start_node") and hasattr(value, "end_node") and hasattr(value, "items"):
            relationship_type = getattr(value, "type", type(value).__name__)
            return {
                "_type": "relationship",
                "element_id": str(getattr(value, "element_id", "")),
                "relationship_type": str(relationship_type),
                "start_node_element_id": str(value.start_node.element_id),
                "end_node_element_id": str(value.end_node.element_id),
                "properties": {
                    str(key): cls._coerce_graph_value(item)
                    for key, item in dict(value.items()).items()
                },
            }
        if hasattr(value, "nodes") and hasattr(value, "relationships"):
            return {
                "_type": "path",
                "nodes": [cls._coerce_graph_value(item) for item in value.nodes],
                "relationships": [cls._coerce_graph_value(item) for item in value.relationships],
            }
        if hasattr(value, "isoformat") and callable(value.isoformat):
            return value.isoformat()
        return str(value)
