from __future__ import annotations

import asyncio
import importlib.util
import shutil
import socket
import tempfile
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
_CONNECTIVITY_PATH = Path(__file__).resolve().with_name("test_go_live_connectivity_real.py")
_CONNECTIVITY_SPEC = importlib.util.spec_from_file_location(
    "go_live_connectivity_real_helpers",
    _CONNECTIVITY_PATH,
)
if _CONNECTIVITY_SPEC is None or _CONNECTIVITY_SPEC.loader is None:
    raise RuntimeError(f"Unable to load connectivity helpers from {_CONNECTIVITY_PATH}")
_CONNECTIVITY = importlib.util.module_from_spec(_CONNECTIVITY_SPEC)
_CONNECTIVITY_SPEC.loader.exec_module(_CONNECTIVITY)

ERP_DB_URL = "postgresql://angel:@localhost:5432/aerogenie"
ERP_SCHEMA = "erp_augmented"
ERP_CONNECTOR_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "aerogenie",
    "user": "angel",
    "password": "",
    "schema": ERP_SCHEMA,
}
ERP_CHAIN = (
    ("AircraftApu", "dbo__aircraft_apu"),
    ("SrcvLine", "dbo__srcv_line"),
    ("RfqLineChanges", "dbo__rfq_line_changes"),
    ("FboLine", "dbo__fbo_line"),
    ("AircraftHdr", "dbo__aircraft_hdr"),
)
ERP_CHAIN_EDGES = (
    ("AircraftApu", "SrcvLine"),
    ("SrcvLine", "RfqLineChanges"),
    ("RfqLineChanges", "FboLine"),
    ("FboLine", "AircraftHdr"),
)
ERP_SIX_HOP_CHAIN = (
    ("BanksAccounts", "dbo__banks_accounts"),
    ("Banks", "dbo__banks"),
    ("BanksStatement", "dbo__banks_statement"),
    ("TcheckHdr", "dbo__tcheck_hdr"),
    ("Deposits", "dbo__deposits"),
    ("BanksCheckbooks", "dbo__banks_checkbooks"),
    ("CheckHdr", "dbo__check_hdr"),
)
ERP_SIX_HOP_EDGE_KEYS = (
    ("BanksAccounts", "Banks", "BANK_ID"),
    ("Banks", "BanksStatement", "BANK_ID"),
    ("BanksStatement", "TcheckHdr", "BANK_ID"),
    ("TcheckHdr", "Deposits", "ACCOUNT_NO"),
    ("Deposits", "BanksCheckbooks", "BANK_ID"),
    ("BanksCheckbooks", "CheckHdr", "BANK_ID"),
)
GROUND_TRUTH_SQL = text(
    """
    select
      coalesce(ah."ACTIVE"::text, '<null>') as active_group,
      count(aa."DOC_NO")::bigint as cnt
    from erp_augmented.dbo__aircraft_apu aa
    join erp_augmented.dbo__srcv_line sl on aa."SERIAL_NO" = sl."SERIAL_NO"
    join erp_augmented.dbo__rfq_line_changes rlc on sl."SERIAL_NO" = rlc."SERIAL_NO"
    join erp_augmented.dbo__fbo_line fl on rlc."SERIAL_NO" = fl."SERIAL_NO"
    join erp_augmented.dbo__aircraft_hdr ah on fl."SERIAL_NO" = ah."SERIAL_NO"
    group by coalesce(ah."ACTIVE"::text, '<null>')
    order by cnt desc, active_group
    """
)
GROUND_TRUTH_SIX_HOP_SQL = text(
    """
    select
      coalesce(ch."CLEARED"::text, '<null>') as cleared_group,
      count(ba."ACCOUNT_NO")::bigint as cnt
    from erp_augmented.dbo__banks_accounts ba
    join erp_augmented.dbo__banks b on ba."BANK_ID" = b."BANK_ID"
    join erp_augmented.dbo__banks_statement bs on b."BANK_ID" = bs."BANK_ID"
    join erp_augmented.dbo__tcheck_hdr th on bs."BANK_ID" = th."BANK_ID"
    join erp_augmented.dbo__deposits d on th."ACCOUNT_NO" = d."ACCOUNT_NO"
    join erp_augmented.dbo__banks_checkbooks bc on d."BANK_ID" = bc."BANK_ID"
    join erp_augmented.dbo__check_hdr ch on bc."BANK_ID" = ch."BANK_ID"
    group by coalesce(ch."CLEARED"::text, '<null>')
    order by cnt desc, cleared_group
    """
)


def _require_tcp_service(host: str, port: int, label: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        if sock.connect_ex((host, port)) != 0:
            pytest.skip(f"{label} is not reachable at {host}:{port}")


def _fetch_ground_truth_or_skip(
    *,
    chain: tuple[tuple[str, str], ...],
    sql: object,
    group_key: str,
) -> dict[str, float]:
    engine = create_engine(ERP_DB_URL, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            present = {
                row[0]
                for row in conn.execute(
                    text(
                        """
                        select table_name
                        from information_schema.tables
                        where table_schema = :schema
                          and table_name = any(:tables)
                        """
                    ),
                    {
                        "schema": ERP_SCHEMA,
                        "tables": [table_name for _, table_name in chain],
                    },
                )
            }
            missing = sorted({table_name for _, table_name in chain} - present)
            if missing:
                pytest.skip("erp_augmented chain tables are unavailable: " + ", ".join(missing))
            rows = conn.execute(sql).mappings().all()
    except Exception as exc:
        pytest.skip(f"erp_augmented ground-truth query unavailable: {type(exc).__name__}: {exc}")
    finally:
        engine.dispose()

    result: dict[str, float] = {}
    for row in rows:
        normalized_group = str(row[group_key]).strip().lower()
        result[normalized_group] = float(row["cnt"])
    return result


def _register_dataset(
    client: httpx.Client,
    api_key: str,
    *,
    dataset_name: str,
    table_name: str,
) -> dict[str, object]:
    _, body = _CONNECTIVITY.api_request(
        client,
        "POST",
        "/v1/data/connect",
        api_key=api_key,
        json_body={
            "connection_type": "database",
            "provider": "postgres",
            "dataset_name": dataset_name,
            "connection_name": "ERP Augmented",
            "connection_config": ERP_CONNECTOR_CONFIG,
            "selection": {"table": f"{ERP_SCHEMA}.{table_name}"},
        },
        expected_status=200,
    )
    assert body["status"] == "ready", body
    assert body["selection"] == {"table": f"{ERP_SCHEMA}.{table_name}"}, body
    assert body["schema_summary"]["row_count"] > 0, body
    return body


def _find_connection(
    connections: list[dict[str, object]],
    *,
    left_source: str,
    right_source: str,
    key_name: str,
) -> dict[str, object] | None:
    for connection in connections:
        source_a = connection.get("source_a_name")
        source_b = connection.get("source_b_name")
        col_a = connection.get("col_a")
        col_b = connection.get("col_b")
        if (
            source_a == left_source
            and source_b == right_source
            and col_a == key_name
            and col_b == key_name
        ):
            return connection
        if (
            source_a == right_source
            and source_b == left_source
            and col_a == key_name
            and col_b == key_name
        ):
            return connection
    return None


def _reverse_cardinality(cardinality: str) -> str:
    if cardinality == "one_to_many":
        return "many_to_one"
    if cardinality == "many_to_one":
        return "one_to_many"
    return cardinality


def _build_join_edge(
    connection: dict[str, object],
    *,
    left_source: str,
    right_source: str,
    key_name: str,
) -> dict[str, object]:
    source_a = str(connection.get("source_a_name") or "")
    source_b = str(connection.get("source_b_name") or "")
    col_a = str(connection.get("col_a") or "")
    col_b = str(connection.get("col_b") or "")
    if col_a != key_name or col_b != key_name:
        raise AssertionError((left_source, right_source, key_name, connection))

    expected_cardinality = str(connection.get("cardinality") or "")
    if source_a == left_source and source_b == right_source:
        pass
    elif source_a == right_source and source_b == left_source:
        expected_cardinality = _reverse_cardinality(expected_cardinality)
    else:
        raise AssertionError((left_source, right_source, key_name, connection))

    edge = {
        "left_source": left_source,
        "left_key": key_name,
        "right_source": right_source,
        "right_key": key_name,
        "expected_cardinality": expected_cardinality,
    }
    if expected_cardinality == "many_to_many":
        edge["allow_many_to_many"] = True
    return edge


def _normalize_group_result(result_rows: list[dict[str, object]]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for row in result_rows:
        group_key = str(row["group"]).strip().lower()
        normalized[group_key] = float(row["value"])
    return normalized


def test_real_erp_augmented_five_table_join_path_matches_direct_sql() -> None:
    _require_tcp_service("127.0.0.1", 5432, "Postgres")
    _require_tcp_service("127.0.0.1", 6379, "Redis")
    ground_truth = _fetch_ground_truth_or_skip(
        chain=ERP_CHAIN,
        sql=GROUND_TRUTH_SQL,
        group_key="active_group",
    )

    _CONNECTIVITY.run_migrations(
        {
            "PYTHONPATH": str(ROOT),
            "DATABASE_URL": _CONNECTIVITY.DEFAULT_DB_URL,
            "DATABASE_URL_SYNC": _CONNECTIVITY.DEFAULT_DB_URL_SYNC,
            "REDIS_URL": _CONNECTIVITY.DEFAULT_REDIS_URL,
        }
    )
    api_key, _org_id = asyncio.run(_CONNECTIVITY.seed_api_key(_CONNECTIVITY.DEFAULT_DB_URL))

    tmp_root = Path(tempfile.mkdtemp(prefix="algenta-erp-join-"))
    api_server = None
    client = None
    try:
        sources_dir = tmp_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        api_port = _CONNECTIVITY.free_port()
        api_server = _CONNECTIVITY.start_api_server(
            api_port,
            sources_dir,
            {
                "API_ENV": "development",
                "DATABASE_URL": _CONNECTIVITY.DEFAULT_DB_URL,
                "DATABASE_URL_SYNC": _CONNECTIVITY.DEFAULT_DB_URL_SYNC,
                "DATABASE_READ_REPLICA_URL": _CONNECTIVITY.DEFAULT_DB_URL,
                "REDIS_URL": _CONNECTIVITY.DEFAULT_REDIS_URL,
                "ALGENTA_SOURCES_DIR": str(sources_dir),
            },
        )
        _CONNECTIVITY.wait_for_http(
            f"http://127.0.0.1:{api_port}/v1/health",
            timeout=90.0,
            proc=api_server,
            log_path=getattr(api_server, "algenta_log_path", None),
        )
        client = httpx.Client(base_url=f"http://127.0.0.1:{api_port}")

        dataset_ids: list[str] = []
        for dataset_name, table_name in ERP_CHAIN:
            body = _register_dataset(
                client,
                api_key,
                dataset_name=dataset_name,
                table_name=table_name,
            )
            dataset_ids.append(str(body["dataset_id"]))

        _, graph_body = _CONNECTIVITY.api_request(
            client,
            "GET",
            "/v1/sources/graph",
            api_key=api_key,
            expected_status=200,
        )
        assert graph_body["total_connections"] >= 4, graph_body
        connections = graph_body["connections"]
        for left_source, right_source in ERP_CHAIN_EDGES:
            connection = _find_connection(
                connections,
                left_source=left_source,
                right_source=right_source,
                key_name="SERIAL_NO",
            )
            assert connection is not None, (left_source, right_source, graph_body)
            assert connection.get("cardinality") == "one_to_one", connection

        _, query_body = _CONNECTIVITY.api_request(
            client,
            "POST",
            "/v1/query",
            api_key=api_key,
            json_body={
                "source_name": "AircraftApu",
                "metric_column": "DOC_NO",
                "aggregation": "count",
                "group_column": "ACTIVE",
                "order": "desc",
                "join_path": {
                    "base_source": "AircraftApu",
                    "group_source": "AircraftHdr",
                    "reject_on_fanout": True,
                    "edges": [
                        {
                            "left_source": "AircraftApu",
                            "left_key": "SERIAL_NO",
                            "right_source": "SrcvLine",
                            "right_key": "SERIAL_NO",
                            "expected_cardinality": "one_to_one",
                        },
                        {
                            "left_source": "SrcvLine",
                            "left_key": "SERIAL_NO",
                            "right_source": "RfqLineChanges",
                            "right_key": "SERIAL_NO",
                            "expected_cardinality": "one_to_one",
                        },
                        {
                            "left_source": "RfqLineChanges",
                            "left_key": "SERIAL_NO",
                            "right_source": "FboLine",
                            "right_key": "SERIAL_NO",
                            "expected_cardinality": "one_to_one",
                        },
                        {
                            "left_source": "FboLine",
                            "left_key": "SERIAL_NO",
                            "right_source": "AircraftHdr",
                            "right_key": "SERIAL_NO",
                            "expected_cardinality": "one_to_one",
                        },
                    ],
                },
            },
            expected_status=200,
        )

        assert query_body["row_count"] == int(sum(ground_truth.values())), query_body
        assert _normalize_group_result(query_body["result"]) == ground_truth, query_body
        assert any("Join hop 4" in step for step in query_body["plan"]), query_body["plan"]
        assert any("COUNT(*) BY `ACTIVE` (join-path)" in step for step in query_body["plan"]), (
            query_body["plan"]
        )
        assert len(dataset_ids) == 5
    finally:
        if client is not None:
            client.close()
        _CONNECTIVITY.stop_process(api_server)
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_real_erp_augmented_seven_table_join_path_matches_direct_sql() -> None:
    _require_tcp_service("127.0.0.1", 5432, "Postgres")
    _require_tcp_service("127.0.0.1", 6379, "Redis")
    ground_truth = _fetch_ground_truth_or_skip(
        chain=ERP_SIX_HOP_CHAIN,
        sql=GROUND_TRUTH_SIX_HOP_SQL,
        group_key="cleared_group",
    )

    _CONNECTIVITY.run_migrations(
        {
            "PYTHONPATH": str(ROOT),
            "DATABASE_URL": _CONNECTIVITY.DEFAULT_DB_URL,
            "DATABASE_URL_SYNC": _CONNECTIVITY.DEFAULT_DB_URL_SYNC,
            "REDIS_URL": _CONNECTIVITY.DEFAULT_REDIS_URL,
        }
    )
    api_key, _org_id = asyncio.run(_CONNECTIVITY.seed_api_key(_CONNECTIVITY.DEFAULT_DB_URL))

    tmp_root = Path(tempfile.mkdtemp(prefix="algenta-erp-join-six-hop-"))
    api_server = None
    client = None
    try:
        sources_dir = tmp_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        api_port = _CONNECTIVITY.free_port()
        api_server = _CONNECTIVITY.start_api_server(
            api_port,
            sources_dir,
            {
                "API_ENV": "development",
                "DATABASE_URL": _CONNECTIVITY.DEFAULT_DB_URL,
                "DATABASE_URL_SYNC": _CONNECTIVITY.DEFAULT_DB_URL_SYNC,
                "DATABASE_READ_REPLICA_URL": _CONNECTIVITY.DEFAULT_DB_URL,
                "REDIS_URL": _CONNECTIVITY.DEFAULT_REDIS_URL,
                "ALGENTA_SOURCES_DIR": str(sources_dir),
            },
        )
        _CONNECTIVITY.wait_for_http(
            f"http://127.0.0.1:{api_port}/v1/health",
            timeout=90.0,
            proc=api_server,
            log_path=getattr(api_server, "algenta_log_path", None),
        )
        client = httpx.Client(base_url=f"http://127.0.0.1:{api_port}")

        dataset_ids: list[str] = []
        for dataset_name, table_name in ERP_SIX_HOP_CHAIN:
            body = _register_dataset(
                client,
                api_key,
                dataset_name=dataset_name,
                table_name=table_name,
            )
            dataset_ids.append(str(body["dataset_id"]))

        _, graph_body = _CONNECTIVITY.api_request(
            client,
            "GET",
            "/v1/sources/graph",
            api_key=api_key,
            expected_status=200,
        )
        connections = graph_body["connections"]
        assert graph_body["total_connections"] >= len(ERP_SIX_HOP_EDGE_KEYS), graph_body

        join_edges: list[dict[str, object]] = []
        for left_source, right_source, key_name in ERP_SIX_HOP_EDGE_KEYS:
            connection = _find_connection(
                connections,
                left_source=left_source,
                right_source=right_source,
                key_name=key_name,
            )
            assert connection is not None, (left_source, right_source, key_name, graph_body)
            join_edges.append(
                _build_join_edge(
                    connection,
                    left_source=left_source,
                    right_source=right_source,
                    key_name=key_name,
                )
            )

        _, query_body = _CONNECTIVITY.api_request(
            client,
            "POST",
            "/v1/query",
            api_key=api_key,
            json_body={
                "source_name": "BanksAccounts",
                "metric_column": "ACCOUNT_NO",
                "aggregation": "count",
                "group_column": "CLEARED",
                "order": "desc",
                "join_path": {
                    "base_source": "BanksAccounts",
                    "group_source": "CheckHdr",
                    "max_hops": 6,
                    "reject_on_ambiguity": False,
                    "reject_on_fanout": False,
                    "edges": join_edges,
                },
            },
            expected_status=200,
        )

        assert query_body["row_count"] == int(sum(ground_truth.values())), query_body
        assert _normalize_group_result(query_body["result"]) == ground_truth, query_body
        assert any("Join hop 6" in step for step in query_body["plan"]), query_body["plan"]
        assert any("COUNT(*) BY `CLEARED` (join-path)" in step for step in query_body["plan"]), (
            query_body["plan"]
        )
        assert len(dataset_ids) == 7
    finally:
        if client is not None:
            client.close()
        _CONNECTIVITY.stop_process(api_server)
        shutil.rmtree(tmp_root, ignore_errors=True)
