import sqlite3

import pytest

from apps.api_server.connectors.sql_connector import SQLConnector


@pytest.mark.asyncio
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

    connector = SQLConnector({
        "connection_string": f"sqlite+pysqlite:///{db_path}",
        "query": "SELECT entity_id, measure_total FROM facts ORDER BY entity_id",
        "limit": 10,
    })

    rows = await connector.fetch_data()

    assert rows == [
        {"entity_id": "A1", "measure_total": 10.0},
        {"entity_id": "A2", "measure_total": 20.0},
    ]


@pytest.mark.asyncio
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
