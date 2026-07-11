from __future__ import annotations

import json
import sys
import types

import pytest

from apps.api_server.config import get_settings
from apps.api_server.connectors.sql_connector import SQLConnector
from apps.api_server.services.connectors.tester import (
    classify_connector_failure,
    test_connector_real,
    test_connector_real_detailed,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_connector_real_supports_file_csv_path(tmp_path):
    csv_path = tmp_path / "facts.csv"
    csv_path.write_text("entity_id,measure_total\nA1,10\nA2,20\n", encoding="utf-8")

    success, message, latency_ms = await test_connector_real(
        "file",
        {
            "file_type": "csv",
            "file_path": str(csv_path),
        },
    )

    assert success is True
    assert "2 records" in message
    assert latency_ms >= 0


@pytest.mark.anyio
async def test_connector_real_supports_file_json_inline():
    payload = json.dumps({"data": {"items": [{"entity_id": "A1", "measure_total": 10}]}})

    success, message, _ = await test_connector_real(
        "file_upload",
        {
            "file_type": "json",
            "content": payload,
            "json_path": "data.items",
        },
    )

    assert success is True
    assert "1 records" in message


def test_classify_connector_failure_maps_not_found_without_unknown_fallback() -> None:
    error_type, recoverable = classify_connector_failure(message="AWS S3 error: NoSuchKey")

    assert error_type == "not_found"
    assert recoverable is True


def test_classify_connector_failure_maps_unsupported_version_to_invalid_identifier() -> None:
    error_type, recoverable = classify_connector_failure(
        message="REST API error payload: version: Unsupported Version"
    )

    assert error_type == "invalid_identifier"
    assert recoverable is True


def test_classify_connector_failure_maps_blob_not_found_to_not_found() -> None:
    error_type, recoverable = classify_connector_failure(
        message="The specified blob does not exist. ErrorCode:BlobNotFound"
    )

    assert error_type == "not_found"
    assert recoverable is True


def test_classify_connector_failure_maps_snowflake_network_policy_to_permission() -> None:
    error_type, recoverable = classify_connector_failure(
        message=(
            "DatabaseError: 250001 (08001): Failed to connect to DB: "
            "ymkarhb-rzc05955.snowflakecomputing.com:443. Fail : Network policy is required."
        )
    )

    assert error_type == "permission"
    assert recoverable is True


def test_classify_connector_failure_maps_snowflake_bad_password_to_auth() -> None:
    error_type, recoverable = classify_connector_failure(
        message=(
            "DatabaseError: 250001 (08001): Failed to connect to DB: "
            "ymkarhb-rzc05955.snowflakecomputing.com:443. Incorrect username or password was specified."
        )
    )

    assert error_type == "auth"
    assert recoverable is True


def test_classify_connector_failure_maps_redis_bad_password_to_auth() -> None:
    error_type, recoverable = classify_connector_failure(
        message="Redis error: invalid username-password pair"
    )

    assert error_type == "auth"
    assert recoverable is True


def test_classify_connector_failure_maps_oracle_exception_to_auth() -> None:
    error_type, recoverable = classify_connector_failure(
        message="Oracle Database connection failed.",
        exception=RuntimeError("ORA-01017: invalid username/password; logon denied"),
    )

    assert error_type == "auth"
    assert recoverable is True


def test_classify_connector_failure_maps_postgres_missing_role_to_auth() -> None:
    error_type, recoverable = classify_connector_failure(
        message='PostgreSQL connection failed: role "nobody" does not exist'
    )

    assert error_type == "auth"
    assert recoverable is True


def test_classify_connector_failure_maps_neo4j_auth_error_to_auth() -> None:
    error_type, recoverable = classify_connector_failure(
        message="Neo4j error: The client is unauthorized due to authentication failure."
    )

    assert error_type == "auth"
    assert recoverable is True


def test_classify_connector_failure_maps_elasticsearch_api_key_error_to_auth() -> None:
    error_type, recoverable = classify_connector_failure(
        message=(
            "Elasticsearch error: unable to authenticate with provided credentials "
            "and anonymous access is not allowed for this request"
        )
    )

    assert error_type == "auth"
    assert recoverable is True


def test_classify_connector_failure_maps_snowflake_inaccessible_warehouse_to_permission() -> None:
    error_type, recoverable = classify_connector_failure(
        message=(
            "Snowflake warehouse 'COMPUTE_WH' is not accessible for current role 'PUBLIC'. "
            "Grant warehouse usage to that role or use a login permitted for a role "
            "with warehouse access."
        )
    )

    assert error_type == "permission"
    assert recoverable is True


def test_classify_connector_failure_maps_egress_policy_denied_to_permission() -> None:
    error_type, recoverable = classify_connector_failure(
        message=(
            "Egress blocked by privacy policy for surface 'tester_postgres_connector' "
            "(destination_not_allowlisted)."
        )
    )

    assert error_type == "permission"
    assert recoverable is True


@pytest.mark.anyio
async def test_connector_real_detailed_returns_structured_invalid_config_for_unknown_type() -> None:
    outcome = await test_connector_real_detailed("unknown_type", {})

    assert outcome.success is False
    assert outcome.status == "error"
    assert outcome.error_type == "invalid_config"
    assert outcome.recoverable is True


@pytest.mark.anyio
async def test_connector_real_detailed_uses_gcs_connector_validation_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class _FakeGCSConnector:
        def __init__(self, config: dict[str, object]) -> None:
            calls.append(config)

        async def validate_connection(self) -> tuple[bool, str]:
            return True, "gs://cloud-samples-data/example.csv accessible."

    monkeypatch.setattr(
        "apps.api_server.connectors.cloud_connector.GCSConnector",
        _FakeGCSConnector,
    )

    outcome = await test_connector_real_detailed(
        "gcs",
        {
            "bucket": "cloud-samples-data",
            "blob": "example.csv",
            "anonymous": True,
        },
    )

    assert len(calls) == 1
    assert calls[0]["bucket"] == "cloud-samples-data"
    assert outcome.success is True
    assert outcome.status == "live"
    assert outcome.error_type is None


@pytest.mark.anyio
async def test_connector_real_detailed_supports_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.connectors.oracle_connector import OracleConnector

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        OracleConnector,
        "_validate_sync",
        lambda config: calls.append(config),
    )

    outcome = await test_connector_real_detailed(
        "oracle",
        {
            "user": "APP_READER",
            "password": "secret",
            "dsn": "oracle.internal:1521/analytics",
        },
    )

    assert len(calls) == 1
    assert outcome.success is True
    assert outcome.status == "live"
    assert outcome.error_type is None


@pytest.mark.anyio
async def test_connector_real_detailed_activates_snowflake_session_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class _FakeCursor:
        def execute(self, _query: str):
            return None

    class _FakeConnection:
        def cursor(self):
            return _FakeCursor()

        def close(self) -> None:
            return None

    connector_module = types.ModuleType("snowflake.connector")
    connector_module.connect = lambda **kwargs: _FakeConnection()
    snowflake_module = types.ModuleType("snowflake")
    snowflake_module.connector = connector_module

    monkeypatch.setitem(sys.modules, "snowflake", snowflake_module)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector_module)
    monkeypatch.setattr(
        SQLConnector,
        "_activate_snowflake_session_context",
        lambda conn, *, warehouse="", database="", schema="": calls.append(
            {
                "warehouse": warehouse,
                "database": database,
                "schema": schema,
            }
        ),
    )

    outcome = await test_connector_real_detailed(
        "snowflake",
        {
            "account": "acct",
            "user": "user",
            "password": "pass",
            "warehouse": "COMPUTE_WH",
            "database": "SNOWFLAKE_SAMPLE_DATA",
            "schema": "TPCH_SF1",
        },
    )

    assert outcome.success is True
    assert calls == [
        {
            "warehouse": "COMPUTE_WH",
            "database": "SNOWFLAKE_SAMPLE_DATA",
            "schema": "TPCH_SF1",
        }
    ]


@pytest.mark.anyio
async def test_connector_real_detailed_supports_clickhouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClickHouseClient:
        def __init__(self) -> None:
            self.commands: list[str] = []
            self.closed = False

        def command(self, query: str):
            self.commands.append(query)
            return 1

        def close(self) -> None:
            self.closed = True

    client = _FakeClickHouseClient()
    connect_calls: list[str] = []

    # The connector guards on `import clickhouse_connect` before reaching
    # SQLConnector._clickhouse_connect. CI doesn't install the package
    # (it's an optional connector dep), so stub it into sys.modules so the
    # import succeeds and the monkeypatched _clickhouse_connect is reached.
    import sys

    monkeypatch.setitem(sys.modules, "clickhouse_connect", types.ModuleType("clickhouse_connect"))

    monkeypatch.setattr(
        SQLConnector,
        "_clickhouse_connect",
        lambda connection_string: (
            connect_calls.append(connection_string),
            client,
        )[1],
    )

    outcome = await test_connector_real_detailed(
        "clickhouse",
        {
            "url": "https://clickhouse.example.com:8443",
            "user": "default",
            "password": "pass",
            "database": "default",
        },
    )

    assert outcome.success is True
    assert outcome.status == "live"
    assert outcome.error_type is None
    assert connect_calls == [
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    ]
    assert client.commands == ["SELECT 1"]


@pytest.mark.anyio
async def test_connector_real_detailed_supports_elasticsearch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validate_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.elasticsearch_connector.ElasticsearchConnector._validate_sync",
        staticmethod(lambda settings, audit_context=None: validate_calls.append(dict(settings))),
    )

    outcome = await test_connector_real_detailed(
        "elasticsearch",
        {
            "url": "https://elastic.example.com:443",
            "api_key": "secret-key",
        },
    )

    assert outcome.success is True
    assert outcome.status == "live"
    assert outcome.error_type is None
    assert validate_calls == [
        {
            "base_url": "https://elastic.example.com:443",
            "api_key": "secret-key",
            "host": "elastic.example.com",
            "port": 443,
        }
    ]


@pytest.mark.anyio
async def test_connector_real_detailed_reuses_clickhouse_validation_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClickHouseClient:
        def __init__(self) -> None:
            self.commands: list[str] = []
            self.closed = False

        def command(self, query: str):
            self.commands.append(query)
            return 1

        def close(self) -> None:
            self.closed = True

    SQLConnector._clear_clickhouse_client_pools()
    client = _FakeClickHouseClient()
    connect_calls: list[str] = []

    # See test_connector_real_detailed_supports_clickhouse for why this stub
    # is needed in CI (clickhouse-connect is an optional dep, not installed).
    import sys

    monkeypatch.setitem(sys.modules, "clickhouse_connect", types.ModuleType("clickhouse_connect"))

    monkeypatch.setattr(
        SQLConnector,
        "_clickhouse_connect",
        lambda connection_string: (
            connect_calls.append(connection_string),
            client,
        )[1],
    )

    first = await test_connector_real_detailed(
        "clickhouse",
        {
            "url": "https://clickhouse.example.com:8443",
            "user": "default",
            "password": "pass",
            "database": "default",
        },
    )
    second = await test_connector_real_detailed(
        "clickhouse",
        {
            "url": "https://clickhouse.example.com:8443",
            "user": "default",
            "password": "pass",
            "database": "default",
        },
    )

    assert first.success is True
    assert second.success is True
    assert connect_calls == [
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    ]
    assert client.commands == ["SELECT 1", "SELECT 1"]
    assert client.closed is False
    SQLConnector._clear_clickhouse_client_pools()
    assert client.closed is True


@pytest.mark.anyio
async def test_connector_real_detailed_supports_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validate_calls: list[str] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.redis_connector.RedisConnector._validate_sync",
        staticmethod(
            lambda connection_url, audit_context=None: validate_calls.append(connection_url)
        ),
    )

    outcome = await test_connector_real_detailed(
        "redis",
        {
            "url": "redis://default:pass@redis.example.com:15638/0",
        },
    )

    assert outcome.success is True
    assert outcome.status == "live"
    assert outcome.error_type is None
    assert validate_calls == ["redis://default:pass@redis.example.com:15638/0"]


@pytest.mark.anyio
async def test_connector_real_detailed_reuses_redis_validation_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.connectors.redis_connector import RedisConnector

    class _FakeRedisClient:
        def __init__(self) -> None:
            self.closed = False
            self.ping_calls = 0

        def ping(self) -> bool:
            self.ping_calls += 1
            return True

        def close(self) -> None:
            self.closed = True

    RedisConnector._clear_client_cache()
    fake_client = _FakeRedisClient()
    connect_calls: list[str] = []

    monkeypatch.setattr(
        RedisConnector,
        "_connect_sync",
        staticmethod(
            lambda connection_url: (
                connect_calls.append(connection_url),
                fake_client,
            )[1]
        ),
    )

    first = await test_connector_real_detailed(
        "redis",
        {"url": "redis://default:pass@redis.example.com:15638/0"},
    )
    second = await test_connector_real_detailed(
        "redis",
        {"url": "redis://default:pass@redis.example.com:15638/0"},
    )

    assert first.success is True
    assert second.success is True
    assert connect_calls == ["redis://default:pass@redis.example.com:15638/0"]
    assert fake_client.ping_calls == 2
    assert fake_client.closed is False
    RedisConnector._clear_client_cache()
    assert fake_client.closed is True


@pytest.mark.anyio
async def test_connector_real_detailed_supports_neo4j(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validate_calls: list[dict[str, str]] = []

    neo4j_module = types.ModuleType("neo4j")
    monkeypatch.setitem(sys.modules, "neo4j", neo4j_module)
    monkeypatch.setattr(
        "apps.api_server.connectors.neo4j_connector.Neo4jConnector._validate_sync",
        staticmethod(lambda settings, audit_context=None: validate_calls.append(dict(settings))),
    )

    outcome = await test_connector_real_detailed(
        "neo4j",
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "pass",
            "database": "neo4j",
        },
    )

    assert outcome.success is True
    assert outcome.status == "live"
    assert outcome.error_type is None
    assert validate_calls == [
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "pass",
            "database": "neo4j",
            "host": "graph.example.com",
            "port": "",
        }
    ]


@pytest.mark.anyio
async def test_connector_real_detailed_reuses_neo4j_validation_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.connectors.neo4j_connector import Neo4jConnector

    neo4j_module = types.ModuleType("neo4j")
    monkeypatch.setitem(sys.modules, "neo4j", neo4j_module)

    class _FakeSession:
        def __init__(self) -> None:
            self.run_calls: list[tuple[str, dict[str, object] | None]] = []

        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def run(self, query: str, parameters: dict[str, object] | None = None):
            self.run_calls.append((query, parameters))

            class _FakeResult:
                @staticmethod
                def single():
                    return {"ok": 1}

            return _FakeResult()

    class _FakeDriver:
        def __init__(self) -> None:
            self.closed = False
            self.sessions: list[_FakeSession] = []

        def session(self, **_kwargs) -> _FakeSession:
            session = _FakeSession()
            self.sessions.append(session)
            return session

        def close(self) -> None:
            self.closed = True

    Neo4jConnector._clear_driver_cache()
    fake_driver = _FakeDriver()
    connect_calls: list[dict[str, str]] = []

    monkeypatch.setattr(
        Neo4jConnector,
        "_connect_sync",
        staticmethod(
            lambda settings: (
                connect_calls.append(dict(settings)),
                fake_driver,
            )[1]
        ),
    )

    first = await test_connector_real_detailed(
        "neo4j",
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "pass",
            "database": "neo4j",
        },
    )
    second = await test_connector_real_detailed(
        "neo4j",
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "pass",
            "database": "neo4j",
        },
    )

    assert first.success is True
    assert second.success is True
    assert connect_calls == [
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "pass",
            "database": "neo4j",
            "host": "graph.example.com",
            "port": "",
        }
    ]
    assert len(fake_driver.sessions) == 2
    assert fake_driver.sessions[0].run_calls == [(Neo4jConnector._VALIDATE_QUERY, None)]
    assert fake_driver.sessions[1].run_calls == [(Neo4jConnector._VALIDATE_QUERY, None)]
    assert fake_driver.closed is False
    Neo4jConnector._clear_driver_cache()
    assert fake_driver.closed is True


@pytest.mark.anyio
async def test_connector_real_detailed_blocks_postgres_egress_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_calls: list[dict[str, object]] = []
    asyncpg_module = types.ModuleType("asyncpg")

    async def _connect(**kwargs):
        connect_calls.append(kwargs)
        raise AssertionError("asyncpg.connect should not be called when egress is blocked")

    asyncpg_module.connect = _connect
    monkeypatch.setitem(sys.modules, "asyncpg", asyncpg_module)
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)

    outcome = await test_connector_real_detailed(
        "postgres",
        {
            "host": "warehouse.customer.example",
            "port": 5432,
            "database": "analytics",
            "user": "reader",
            "password": "secret",
        },
    )

    assert outcome.success is False
    assert outcome.error_type == "permission"
    assert "privacy policy" in outcome.message
    assert connect_calls == []


@pytest.mark.anyio
async def test_connector_real_detailed_blocks_snowflake_egress_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_calls: list[dict[str, object]] = []
    connector_module = types.ModuleType("snowflake.connector")

    def _connect(**kwargs):
        connect_calls.append(kwargs)
        raise AssertionError(
            "snowflake.connector.connect should not be called when egress is blocked"
        )

    connector_module.connect = _connect
    snowflake_module = types.ModuleType("snowflake")
    snowflake_module.connector = connector_module
    monkeypatch.setitem(sys.modules, "snowflake", snowflake_module)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector_module)
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)

    outcome = await test_connector_real_detailed(
        "snowflake",
        {
            "account": "acct-denied",
            "user": "reader",
            "password": "secret",
            "warehouse": "COMPUTE_WH",
            "database": "ANALYTICS",
        },
    )

    assert outcome.success is False
    assert outcome.error_type == "permission"
    assert "privacy policy" in outcome.message
    assert connect_calls == []
