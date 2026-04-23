from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from uuid import uuid4

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DEFAULT_DB_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://angel:@localhost:5432/decision_engine",
)


def postgres_connection_config(database_url: str) -> dict[str, object]:
    url = make_url(database_url)
    return {
        "host": url.host or "localhost",
        "port": int(url.port or 5432),
        "database": url.database or "",
        "user": url.username or "",
        "password": url.password or "",
    }


def postgres_canonical_connector(
    descriptor: Mapping[str, object],
) -> dict[str, object]:
    connection_string = str(descriptor.get("connection_string") or "").strip()
    if not connection_string:
        raise ValueError("Postgres descriptor requires connection_string.")
    config = postgres_connection_config(connection_string)
    location: dict[str, object] = {
        "host": config["host"],
        "port": config["port"],
        "database": config["database"],
    }
    schema = descriptor.get("schema")
    if isinstance(schema, str) and schema.strip():
        location["schema"] = schema.strip()
    table = descriptor.get("table")
    if isinstance(table, str) and table.strip():
        location["table"] = table.strip()

    credentials: dict[str, object] = {}
    user = config.get("user")
    if isinstance(user, str) and user.strip():
        credentials["user"] = user.strip()
    password = config.get("password")
    if isinstance(password, str):
        credentials["password"] = password

    connector: dict[str, object] = {
        "type": "postgres",
        "location": location,
    }
    if credentials:
        connector["auth"] = {"credentials": credentials}
    return connector


@contextmanager
def temporary_postgres_fixture(
    records: Sequence[Mapping[str, object]],
    *,
    table: str = "orders",
    database_url: str | None = None,
    schema_prefix: str = "aa_runtime_live",
) -> Iterator[dict[str, str]]:
    connection_string = (database_url or DEFAULT_DB_URL_SYNC).strip()
    schema = f"{schema_prefix}_{uuid4().hex[:12]}"
    frame = pd.DataFrame(records)
    engine = create_engine(connection_string, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        frame.to_sql(table, engine, schema=schema, if_exists="replace", index=False)
        yield {
            "type": "postgres",
            "connection_string": connection_string,
            "schema": schema,
            "table": table,
        }
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
