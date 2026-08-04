"""Shared harness for the TPC-DS-derived query translations in this directory.

Every query in `verified_queries.py` runs through this module's helpers to reach
the SAME two things every other query does:

  1. The real query-plane engine (`algenta.query.Query` -> the compiled
     `mojo_build/simulate_queryplane` worker over a real AF_UNIX frame — see
     `run_query`). There is no Python fallback: if the worker is unavailable,
     `MojoRuntime.health()` raises rather than answering.
  2. An isolated LOCAL Postgres database (`tpcds_derived_bench_20260804`,
     created fresh for this task — never the shared `NEON_TEST_DB_URL` database
     the rest of this repo's suites use) loaded with real `dsdgen`-generated
     TPC-DS SF=1 data. See `RESULTS.md` for exactly how it was built and how to
     rebuild it.

Central, load-bearing fact about the engine this harness works around: the
query-plane's wire protocol is PURELY NUMERIC — every cell is a `float64` or
absent (see `mojo/engine/query/plan.mojo`; there is no string cell type on the
wire at all, only column names and op names are text). TPC-DS's queries filter
and GROUP BY string dimension attributes (state, category, brand name, ...)
constantly. `dim_with_code` is the one, disclosed way this harness bridges that
gap: it resolves a dimension table's string column(s) to a dense integer code
at the CONNECTOR boundary (one `DENSE_RANK() OVER (ORDER BY ...)` per distinct
string tuple, via a single-table SQL query — never a cross-table join done in
Postgres on the repo's behalf), and only decodes that code back to the display
string for the final, already-aggregated, typically <=100 output rows. The
engine itself never sees a string; it joins, filters and aggregates on the
integer code, which is what is actually being tested here.

The second load-bearing fact: the engine's `MAX_ROWS = 1_000_000` per-frame
cap (`mojo/engine/query/plan.mojo`) is smaller than several SF=1 fact tables
(`store_sales` = 2,880,404 rows; `catalog_sales` = 1,441,548). `chunk` splits a
fact table into batches under that cap and every query below re-runs the SAME
op chain per batch, combining partial `sum`/`count` aggregates in Python
afterwards — the engine still does 100% of the per-row filter/join/aggregate
work; only the map-reduce combine step across batches happens outside it.
"""

from __future__ import annotations

import decimal
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALGENTA_PKG = REPO_ROOT / "packages" / "algenta"
if str(ALGENTA_PKG) not in sys.path:
    sys.path.insert(0, str(ALGENTA_PKG))

_WORKER_DEFAULT = str(REPO_ROOT / "mojo_build" / "simulate_queryplane")
os.environ.setdefault("ALGENTA_RUNTIME_WORKER", _WORKER_DEFAULT)
os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
# A repo-dev worker binary is unsigned; see tests/integration/test_query_plane_e2e.py's
# own docstring for why `allow` here does not weaken what is proved.
#
# This worktree's OWN mojo_env/ was never `pixi install`-ed (that install is large and
# out of scope for this task); the compiled worker's shared libs (libKGENCompilerRTShared,
# libpython3.14, ...) are instead resolved from a SIBLING checkout's already-populated
# pixi env via DYLD_LIBRARY_PATH — a library-search-path pointer only, never a copy.
_this_worktree_lib = REPO_ROOT / "mojo_env" / ".pixi" / "envs" / "default" / "lib"
_main_checkout_lib = Path("/Users/angel/Developer/decision-engine/mojo_env/.pixi/envs/default/lib")
_default_lib = str(_this_worktree_lib if _this_worktree_lib.is_dir() else _main_checkout_lib)
os.environ.setdefault("DYLD_LIBRARY_PATH", os.environ.get("ALGENTA_MOJO_ENV_LIB", _default_lib))

import duckdb  # noqa: E402
import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
from algenta.mojo_runtime import MojoRuntime  # noqa: E402
from algenta.query import Query, col  # noqa: E402,F401  (col re-exported for query scripts)

PG_DSN = os.environ.get(
    "TPCDS_PG_DSN", "dbname=tpcds_derived_bench_20260804 host=localhost user=angel"
)
DUCKDB_PATH = os.environ.get("TPCDS_DUCKDB_PATH", "/tmp/tpcds-work/tpcds_sf1.duckdb")
TRANSLATED_QUERIES_DIR = os.environ.get(
    "TPCDS_TRANSLATED_QUERIES_DIR", "/tmp/tpcds-work/queries_duckdb_translated"
)

CHUNK_SIZE = 900_000  # under the engine's MAX_ROWS=1,000,000 per-frame cap

_RUNTIME = None


def runtime():
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = MojoRuntime(mode="local")
        health = _RUNTIME.health()
        if health.get("status") != "ok":
            raise RuntimeError(f"runtime unavailable: {health}")
    return _RUNTIME


def _coerce_cell(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def pg_fetch(sql: str, params: tuple = ()) -> list[dict]:
    """A fetch from the isolated local Postgres DB.

    Every call site in `verified_queries.py` either reads ONE base table (with
    filters/expressions only over that table's own columns), or joins together
    small DIMENSION tables (customer + its demographic/address dimensions,
    never a fact table) to resolve a customer-level attribute the engine then
    matches by surrogate key. No call site here ever joins a FACT table
    (store_sales / catalog_sales / web_sales / catalog_returns / inventory) to
    anything — that join is always done by the engine, over the fact table's
    real rows, or this would not be testing the engine at all.
    """
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [{k: _coerce_cell(v) for k, v in dict(r).items()} for r in cur.fetchall()]


def duck_run(sql_path: str) -> tuple[list[str], list[tuple]]:
    """The independent correctness oracle: DuckDB, over a native-table copy of
    the EXACT SAME rows loaded into the isolated Postgres DB (materialized once
    via DuckDB's postgres_scanner — see RESULTS.md), running the real TPC-DS
    query text with only the two mechanical dialect fixes documented there."""
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        sql = open(sql_path).read()
        t0 = time.perf_counter()
        r = con.execute(sql)
        cols = [d[0] for d in r.description]
        rows = r.fetchall()
        return cols, rows, time.perf_counter() - t0
    finally:
        con.close()


def chunk(rows: list, size: int = CHUNK_SIZE):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def run_query(q: Query):
    return q.run(runtime(), routing_module="stats")


def dim_with_code(
    sk_col: str,
    string_cols: list[str],
    from_where: str,
    extra_cols: list[str] | None = None,
):
    """Dictionary-encode a dimension table's string column(s) into ONE dense
    integer code, bijective per distinct string tuple (DENSE_RANK ties break
    identically for duplicate strings, which is exactly SQL GROUP BY's own
    tie rule — see RESULTS.md's i_item_id/SCD note). Returns
    (engine_rows[[sk, code, *extra]], code -> string tuple)."""
    extra_cols = extra_cols or []
    order_by = ", ".join(string_cols)
    select_extra = (", " + ", ".join(extra_cols)) if extra_cols else ""
    sql = (
        f"SELECT {sk_col}, DENSE_RANK() OVER (ORDER BY {order_by}) AS grp_code, "
        f"{', '.join(string_cols)}{select_extra} FROM {from_where}"
    )
    recs = pg_fetch(sql)
    code_to_strings: dict[float, tuple] = {}
    engine_rows = []
    for r in recs:
        code = float(r["grp_code"])
        code_to_strings[code] = tuple(r[c] for c in string_cols)
        row = [r[sk_col], code] + [r[c] for c in extra_cols]
        engine_rows.append(row)
    return engine_rows, code_to_strings
