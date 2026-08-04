"""Shared harness for the TPC-H-derived query translations in this directory.

Sibling of `benchmarks/tpcds_derived/engine_harness.py` — same two real things
every query below reaches:

  1. The real query-plane engine (`algenta.query.Query` -> the compiled
     `mojo_build/simulate_queryplane` worker over a real AF_UNIX frame). No
     Python fallback: `MojoRuntime.health()` raises if the worker is down.
  2. An isolated LOCAL Postgres database (`tpch_derived_bench_20260804`,
     created fresh for this task — never `NEON_TEST_DB_URL` or any of this
     machine's other local test databases) loaded with real `dbgen`-generated
     TPC-H SF=1 data (8 tables, `lineitem` = 6,001,215 rows, the documented
     SF=1 cardinality). See RESULTS.md for exactly how it was built.

Two load-bearing facts this harness works around, both already documented in
the TPC-DS-derived phase and unchanged here:

  - **The wire is purely numeric.** No string cell type exists anywhere in
    `algenta.query` / `mojo/engine/query/plan.mojo`. TPC-H's string columns
    fall into two different cases handled two different ways:
      * A column used only as an OUTPUT value, or as a JOIN/GROUP-BY key that
        never needs to leave the engine as a string — dictionary-encode via
        `dim_with_code` (dense integer code, decoded back to the string only
        for the final, already-aggregated output), exactly as TPC-DS did.
      * A LIKE/substring/text-literal predicate that is a pure function of ONE
        row of ONE table (e.g. `p_name like '%green%'`, `o_comment not like
        '%special%requests%'`) — there is no workaround that lets this reach
        the engine at all, since the predicate needs to inspect string
        BYTES the wire cannot carry. It is evaluated at the Postgres
        connector boundary, before those rows are ever sent to the engine —
        the same "connector boundary" the dictionary-encoding already uses,
        just applied as a pre-filter instead of a post-hoc decode. This is
        disclosed per query in RESULTS.md; it is never a join and never
        touches a second table.
  - **`MAX_ROWS = 1_000_000` per frame** (`mojo/engine/query/plan.mojo`).
    `lineitem` (6,001,215 rows) and `orders` (1,500,000) both exceed it.
    `chunk` splits a fact table into batches under that cap; every query
    below re-runs the SAME op chain per batch and combines partial `sum`/
    `count` aggregates in Python afterward — the engine still does 100% of
    the per-row filter/join/aggregate work; only the map-reduce combine
    across batches happens outside it.
"""

from __future__ import annotations

import datetime
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
_this_worktree_lib = REPO_ROOT / "mojo_env" / ".pixi" / "envs" / "default" / "lib"
_main_checkout_lib = Path("/Users/angel/Developer/decision-engine/mojo_env/.pixi/envs/default/lib")
_default_lib = str(_this_worktree_lib if _this_worktree_lib.is_dir() else _main_checkout_lib)
os.environ.setdefault("DYLD_LIBRARY_PATH", os.environ.get("ALGENTA_MOJO_ENV_LIB", _default_lib))

import duckdb  # noqa: E402
import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
from algenta.mojo_runtime import MojoRuntime  # noqa: E402
from algenta.query import Query, col, lit  # noqa: E402,F401  (col/lit re-exported for query scripts)

PG_DSN = os.environ.get(
    "TPCH_PG_DSN", "dbname=tpch_derived_bench_20260804 host=localhost user=angel"
)
DUCKDB_PATH = os.environ.get("TPCH_DUCKDB_PATH", "/tmp/tpch-work/tpch_sf1.duckdb")
TRANSLATED_QUERIES_DIR = os.environ.get(
    "TPCH_TRANSLATED_QUERIES_DIR", "/tmp/tpch-work/queries_duckdb"
)

CHUNK_SIZE = 900_000  # under the engine's MAX_ROWS=1,000,000 per-frame cap

_EPOCH = datetime.date(1970, 1, 1)

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
    if isinstance(v, datetime.date):
        return float((v - _EPOCH).days)
    return v


def epoch_day(d: str) -> float:
    """A 'YYYY-MM-DD' literal to the same epoch-day float `_coerce_cell` uses
    for a `date` column, so a filter threshold and a fetched column compare on
    the same numeric scale."""
    y, m, day = (int(x) for x in d.split("-"))
    return float((datetime.date(y, m, day) - _EPOCH).days)


def pg_fetch(sql: str, params: tuple | None = None) -> list[dict]:
    """A fetch from the isolated local Postgres DB.

    Every call site in `verified_queries.py` either reads ONE base table (with
    filters/expressions only over that table's own columns — including any
    LIKE/substring predicate, since that can only be evaluated here, never on
    the wire), or resolves small DIMENSION tables against each other (nation +
    region, or supplier + nation, never `lineitem`/`orders`/`partsupp` joined
    to anything here). The two big fact-shaped tables (`lineitem`, `orders`)
    are always fetched as a plain, single-table `SELECT ... FROM lineitem`/
    `FROM orders` with only single-table filters — every JOIN across tables
    happens in the engine, or this would not be testing the engine at all.
    """
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [{k: _coerce_cell(v) for k, v in dict(r).items()} for r in cur.fetchall()]


def duck_run(sql_path: str):
    """The independent correctness oracle: DuckDB, over a native-table copy of
    the EXACT SAME rows loaded into the isolated Postgres DB (materialized via
    DuckDB's postgres extension — see RESULTS.md), running the real TPC-H
    query text with only the two mechanical, disclosed dialect fixes (Q1's
    Oracle-style `day (3)` precision spec, Q15's view/select/drop-view ->
    CTE rewrite)."""
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        sql = Path(sql_path).read_text()
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
    integer code (see module docstring + RESULTS.md). Returns
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


def encode_strings(values: list) -> tuple[list[float], dict]:
    """Dictionary-encode a Python-side list of strings into dense integer
    codes, assigned in sorted order of the distinct values (deterministic,
    independent of fetch order). Used for a fact table's OWN string column
    (e.g. `l_returnflag`, `l_shipmode`) where a separate dimension table with
    its own surrogate key does not exist, so `dim_with_code`'s
    `DENSE_RANK() OVER (...)` — a full sort of the base table on Postgres's
    side — is unnecessary work; the encoding is computed once in Python
    instead, over the same values already fetched for the engine rows."""
    distinct = sorted({strip(v) for v in values})
    code_of = {v: float(i) for i, v in enumerate(distinct)}
    codes = [code_of[strip(v)] for v in values]
    code_to_value = {c: v for v, c in code_of.items()}
    return codes, code_to_value


def strip(v):
    return v.strip() if isinstance(v, str) else v


def close(a, b, tol=0.02) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) < tol


def timing_stats(samples: list[float]) -> str:
    s = sorted(samples)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return f"min={s[0]*1000:.1f}ms median={med*1000:.1f}ms max={s[-1]*1000:.1f}ms (n={n})"


def repeat(fn, n: int = 3) -> list[float]:
    """Run `fn()` `n` times, discarding its return value, and return the wall
    times. Used to get min/median/max across repetitions for the SAME
    already-fetched/already-parsed data — never re-fetches from Postgres and
    never re-parses the DuckDB query text, so what varies between repetitions
    is dispatch/compute cost only, not I/O setup cost counted once."""
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return times
