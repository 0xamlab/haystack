import sqlite3
import sys
import types

import pyarrow as pa
import pytest

from apps.api_server.connectors.sql_connector import SQLConnector


@pytest.fixture(autouse=True)
def _clear_clickhouse_client_pools() -> None:
    SQLConnector._clear_clickhouse_client_pools()
    yield
    SQLConnector._clear_clickhouse_client_pools()


@pytest.mark.anyio
async def test_sql_connector_supports_sync_sqlite_dsn(tmp_path):
    db_path = tmp_path / "benchmark.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE facts (entity_id TEXT, measure_total REAL)")
        conn.execute("INSERT INTO facts VALUES (?, ?)", ("A1", 10.0))
        conn.execute("INSERT INTO facts VALUES (?, ?)", ("A2", 20.0))
        conn.commit()
    finally:
        conn.close()

    connector = SQLConnector(
        {
            "connection_string": f"sqlite+pysqlite:///{db_path}",
            "query": "SELECT entity_id, measure_total FROM facts ORDER BY entity_id",
            "limit": 10,
        }
    )

    rows = await connector.fetch_data()

    assert rows == [
        {"entity_id": "A1", "measure_total": 10.0},
        {"entity_id": "A2", "measure_total": 20.0},
    ]


@pytest.mark.anyio
async def test_sql_connector_fetches_full_query_when_limit_is_omitted(tmp_path):
    db_path = tmp_path / "full_fetch.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE facts (entity_id TEXT, measure_total REAL)")
        conn.executemany(
            "INSERT INTO facts VALUES (?, ?)",
            [("A1", 10.0), ("A2", 20.0), ("A3", 30.0)],
        )
        conn.commit()
    finally:
        conn.close()

    connector = SQLConnector(
        {
            "connection_string": f"sqlite+pysqlite:///{db_path}",
            "query": "SELECT entity_id, measure_total FROM facts ORDER BY entity_id",
        }
    )

    rows = await connector.fetch_data()

    assert rows == [
        {"entity_id": "A1", "measure_total": 10.0},
        {"entity_id": "A2", "measure_total": 20.0},
        {"entity_id": "A3", "measure_total": 30.0},
    ]


@pytest.mark.anyio
async def test_sql_connector_fetch_table_returns_arrow(tmp_path):
    db_path = tmp_path / "benchmark.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE facts (entity_id TEXT, measure_total REAL)")
        conn.execute("INSERT INTO facts VALUES (?, ?)", ("A1", 10.0))
        conn.execute("INSERT INTO facts VALUES (?, ?)", ("A2", 20.0))
        conn.commit()
    finally:
        conn.close()

    connector = SQLConnector(
        {
            "connection_string": f"sqlite+pysqlite:///{db_path}",
            "query": "SELECT entity_id, measure_total FROM facts ORDER BY entity_id",
            "limit": 10,
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["entity_id", "measure_total"]


@pytest.mark.anyio
async def test_sql_connector_fetch_table_uses_chunked_sync_path_for_sync_dsns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    db_path = tmp_path / "chunked.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE facts (entity_id TEXT, measure_total REAL)")
        conn.execute("INSERT INTO facts VALUES (?, ?)", ("A1", 10.0))
        conn.execute("INSERT INTO facts VALUES (?, ?)", ("A2", 20.0))
        conn.commit()
    finally:
        conn.close()

    async def _unexpected_fetch_data(self) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
        raise AssertionError("fetch_data should not be used for sync fetch_table")

    monkeypatch.setattr(SQLConnector, "fetch_data", _unexpected_fetch_data)

    connector = SQLConnector(
        {
            "connection_string": f"sqlite+pysqlite:///{db_path}",
            "query": "SELECT entity_id, measure_total FROM facts ORDER BY entity_id",
        }
    )

    table = await connector.fetch_table()

    assert table is not None
    assert table.num_rows == 2
    assert table.column_names == ["entity_id", "measure_total"]


def test_sql_connector_concat_chunk_tables_promotes_null_and_string_columns():
    first = pa.table({"disruption_event_id": [None, None]})
    second = pa.table({"disruption_event_id": ["evt-1", "evt-2"]})

    combined = SQLConnector._concat_chunk_tables([first, second])

    assert combined.schema.field("disruption_event_id").type == pa.string()
    assert combined.column("disruption_event_id").to_pylist() == [
        None,
        None,
        "evt-1",
        "evt-2",
    ]


def test_sql_connector_concat_chunk_tables_promotes_numeric_columns():
    first = pa.table({"score": [1, 2]})
    second = pa.table({"score": [1.5, 2.5]})

    combined = SQLConnector._concat_chunk_tables([first, second])

    assert combined.schema.field("score").type == pa.float64()
    assert combined.column("score").to_pylist() == [1.0, 2.0, 1.5, 2.5]


class _FakeSnowflakeDictCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list[str] = []

    def execute(self, query: str) -> None:
        self.executed.append(query)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSnowflakeConnection:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False
        self.default_cursor = _FakeSnowflakeDictCursor(rows=[])
        self.dict_cursor = _FakeSnowflakeDictCursor(rows=rows)

    def cursor(self, cursor_class=None):
        if cursor_class is not None:
            return self.dict_cursor
        return self.default_cursor

    def close(self) -> None:
        self.closed = True


class _WarehouseFailureCursor:
    def __init__(self, *, current_role: str) -> None:
        self._current_role = current_role
        self.executed: list[str] = []
        self._last_query = ""

    def execute(self, query: str) -> None:
        self.executed.append(query)
        self._last_query = query
        if query.startswith("USE WAREHOUSE "):
            raise RuntimeError("Object does not exist, or operation cannot be performed.")

    def fetchone(self):
        if self._last_query == "SELECT CURRENT_ROLE()":
            return (self._current_role,)
        return None

    def close(self) -> None:
        return None


class _WarehouseFailureConnection:
    def __init__(self, *, current_role: str) -> None:
        self.closed = False
        self.activation_cursor = _WarehouseFailureCursor(current_role=current_role)
        self.role_cursor = _WarehouseFailureCursor(current_role=current_role)
        self._cursor_calls = 0

    def cursor(self, cursor_class=None):
        self._cursor_calls += 1
        if self._cursor_calls == 1:
            return self.activation_cursor
        return self.role_cursor

    def close(self) -> None:
        self.closed = True


class _FakeClickHouseQueryResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def named_results(self):
        return list(self._rows)


class _FakeClickHouseClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.queries: list[str] = []
        self.commands: list[str] = []
        self.closed = False

    def query(self, query: str):
        self.queries.append(query)
        return _FakeClickHouseQueryResult(self.rows)

    def command(self, query: str):
        self.commands.append(query)
        return 1

    def close(self) -> None:
        self.closed = True


class _BrokenClickHouseClient(_FakeClickHouseClient):
    def query(self, query: str):
        self.queries.append(query)
        raise RuntimeError("query failed")


@pytest.mark.anyio
async def test_sql_connector_fetch_data_uses_native_snowflake_driver(monkeypatch):
    rows = [{"N_NAME": "ALGERIA"}, {"N_NAME": "BRAZIL"}]
    connection = _FakeSnowflakeConnection(rows)
    connect_calls = []

    connector_module = types.ModuleType("snowflake.connector")

    def _connect(**kwargs):
        connect_calls.append(kwargs)
        return connection

    connector_module.connect = _connect
    connector_module.DictCursor = object()
    snowflake_module = types.ModuleType("snowflake")
    snowflake_module.connector = connector_module

    monkeypatch.setitem(sys.modules, "snowflake", snowflake_module)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector_module)

    connector = SQLConnector(
        {
            "connection_string": (
                "snowflake://user%40example.com:token%2Fvalue@acct-xyz/"
                "SNOWFLAKE_SAMPLE_DATA/TPCH_SF1?warehouse=COMPUTE_WH"
            ),
            "query": "SELECT N_NAME FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION ORDER BY N_NATIONKEY",
            "limit": 100,
        }
    )

    fetched = await connector.fetch_data()

    assert fetched == rows
    assert connect_calls == [
        {
            "account": "acct-xyz",
            "user": "user@example.com",
            "password": "token/value",
            "warehouse": "COMPUTE_WH",
            "database": "SNOWFLAKE_SAMPLE_DATA",
            "schema": "TPCH_SF1",
            "login_timeout": 8,
        }
    ]
    assert connection.closed is True
    assert connection.default_cursor.executed == [
        'USE WAREHOUSE "COMPUTE_WH"',
    ]
    assert connection.dict_cursor.executed == [
        "SELECT * FROM (SELECT N_NAME FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION ORDER BY N_NATIONKEY) "
        "AS algenta_source LIMIT 100"
    ]


@pytest.mark.anyio
async def test_sql_connector_validate_connection_uses_native_snowflake_driver(monkeypatch):
    connection = _FakeSnowflakeConnection(rows=[])
    connector_module = types.ModuleType("snowflake.connector")
    connector_module.connect = lambda **kwargs: connection
    connector_module.DictCursor = object()
    snowflake_module = types.ModuleType("snowflake")
    snowflake_module.connector = connector_module

    monkeypatch.setitem(sys.modules, "snowflake", snowflake_module)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector_module)

    connector = SQLConnector(
        {
            "connection_string": (
                "snowflake://user:token@acct-xyz/"
                "SNOWFLAKE_SAMPLE_DATA/TPCH_SF1?warehouse=COMPUTE_WH"
            ),
            "query": "SELECT 1",
            "limit": 1,
        }
    )

    ok, message = await connector.validate_connection()

    assert ok is True
    assert message == "Connected successfully."
    assert connection.closed is True
    assert connection.default_cursor.executed == [
        'USE WAREHOUSE "COMPUTE_WH"',
        "SELECT 1",
    ]


def test_activate_snowflake_session_context_reports_inaccessible_warehouse_role() -> None:
    connection = _WarehouseFailureConnection(current_role="PUBLIC")

    with pytest.raises(RuntimeError) as excinfo:
        SQLConnector._activate_snowflake_session_context(
            connection,
            warehouse="COMPUTE_WH",
        )

    assert str(excinfo.value) == (
        "Snowflake warehouse 'COMPUTE_WH' is not accessible for current role 'PUBLIC'. "
        "Grant warehouse usage to that role or use a login permitted for a role "
        "with warehouse access."
    )
    assert connection.activation_cursor.executed == ['USE WAREHOUSE "COMPUTE_WH"']
    assert connection.role_cursor.executed == ["SELECT CURRENT_ROLE()"]


def test_sql_connector_parses_https_clickhouse_dsn() -> None:
    parsed = SQLConnector._parse_clickhouse_dsn(
        "https://default:pass@clickhouse.example.com:8443/default"
    )

    assert parsed == {
        "host": "clickhouse.example.com",
        "port": 8443,
        "user": "default",
        "password": "pass",
        "database": "default",
        "secure": True,
    }


@pytest.mark.anyio
async def test_sql_connector_fetch_data_uses_clickhouse_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClickHouseClient(
        rows=[{"trace_id": "t1", "fee_bps": 9}, {"trace_id": "t2", "fee_bps": 12}]
    )
    connect_calls: list[str] = []

    monkeypatch.setattr(
        SQLConnector,
        "_clickhouse_connect",
        lambda connection_string: (
            connect_calls.append(connection_string),
            client,
        )[1],
    )

    connector = SQLConnector(
        {
            "connection_string": "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true",
            "query": "SELECT trace_id, fee_bps FROM default.fees_decisions ORDER BY trace_id",
            "limit": 100,
        }
    )

    fetched = await connector.fetch_data()

    assert fetched == [{"trace_id": "t1", "fee_bps": 9}, {"trace_id": "t2", "fee_bps": 12}]
    assert connect_calls == [
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    ]
    assert client.queries == [
        "SELECT * FROM (SELECT trace_id, fee_bps FROM default.fees_decisions ORDER BY trace_id) "
        "AS algenta_source LIMIT 100"
    ]
    assert client.closed is False


@pytest.mark.anyio
async def test_sql_connector_validate_connection_uses_clickhouse_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClickHouseClient(rows=[])
    connect_calls: list[str] = []

    monkeypatch.setattr(
        SQLConnector,
        "_clickhouse_connect",
        lambda connection_string: (
            connect_calls.append(connection_string),
            client,
        )[1],
    )

    connector = SQLConnector(
        {
            "connection_string": "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true",
            "query": "SELECT 1",
        }
    )

    ok, message = await connector.validate_connection()

    assert ok is True
    assert message == "Connected successfully."
    assert connect_calls == [
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    ]
    assert client.commands == ["SELECT 1"]
    assert client.closed is False


@pytest.mark.anyio
async def test_sql_connector_reuses_clickhouse_client_for_repeated_fetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClickHouseClient(
        rows=[{"trace_id": "t1", "fee_bps": 9}, {"trace_id": "t2", "fee_bps": 12}]
    )
    connect_calls: list[str] = []

    monkeypatch.setattr(
        SQLConnector,
        "_clickhouse_connect",
        lambda connection_string: (
            connect_calls.append(connection_string),
            client,
        )[1],
    )

    connector = SQLConnector(
        {
            "connection_string": "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true",
            "query": "SELECT trace_id, fee_bps FROM default.fees_decisions ORDER BY trace_id",
            "limit": 100,
        }
    )

    first = await connector.fetch_data()
    second = await connector.fetch_data()

    assert first == second == [{"trace_id": "t1", "fee_bps": 9}, {"trace_id": "t2", "fee_bps": 12}]
    assert connect_calls == [
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    ]
    assert len(client.queries) == 2
    assert client.closed is False


@pytest.mark.anyio
async def test_sql_connector_discards_failed_clickhouse_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = _BrokenClickHouseClient(rows=[])
    healthy = _FakeClickHouseClient(rows=[{"trace_id": "t1"}])
    created_clients = [broken, healthy]
    connect_calls: list[str] = []

    def _fake_connect(connection_string: str):
        connect_calls.append(connection_string)
        return created_clients[len(connect_calls) - 1]

    monkeypatch.setattr(SQLConnector, "_clickhouse_connect", _fake_connect)

    connector = SQLConnector(
        {
            "connection_string": "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true",
            "query": "SELECT trace_id FROM default.execution_outcome_events ORDER BY trace_id",
            "limit": 10,
        }
    )

    with pytest.raises(RuntimeError, match="query failed"):
        await connector.fetch_data()

    recovered = await connector.fetch_data()

    assert recovered == [{"trace_id": "t1"}]
    assert len(connect_calls) == 2
    assert broken.closed is True
    assert healthy.closed is False
