# Decision Engine Scorecard

Updated: 2026-04-15

## Current measured state

| Area | Current | Evidence | Status |
| --- | --- | --- | --- |
| Mojo correctness (A-Z) | 244/244 libraries passed, 2414/2414 functions passed, 216.3s total | `tests/integration/test_mojo_libraries_az.py` run on 2026-04-15 | Green |
| Mojo vs Python speed | 101.24x median, 191.89x mean, 7221.48x max | `benchmarks/summary.txt` | Green |
| Resolver accuracy (universal) | Not measured yet | No cross-industry benchmark corpus exists yet | Red |
| Narrow resolver regression | 12/13 correct = 92% on one hospitality schema; 30/30 regression tests passed | `benchmarks/summary.txt` hospitality benchmark and `tests/test_vector_resolver_hospitality.py` | Yellow |
| Join-path correctness | 2/2 passed | `tests/test_query_join_path.py` | Green |
| Import pipeline correctness | 4/4 active CSV pipeline integration tests passed | `tests/integration/test_csv_pipeline.py` | Green |
| Import/planner regression suite | 53/53 passed | `tests/unit/test_connectors.py`, `tests/test_auto_planner.py`, `tests/test_vector_resolver.py`, `tests/test_query_join_path.py` | Green |
| MCP end-to-end benchmark | 18/20 passed, 428.6 ms average latency | `benchmarks/claude_mcp_20q_summary.md` | Yellow |
| CSV ingest throughput | Backlog: 3370 rows/s; bookings_new: 3256 rows/s; quotes_new: 2299 rows/s; Available_Inventory (244 cols): 547 rows/s | Live parse run on 2026-04-15 with `FileConnector._parse_csv()` | Green |
| Vector hot path | Prefilter + rank at N=2048: 650 ns/query batch, 43.0x faster than full scan | `benchmarks/summary.txt` vector kernel section | Green |
| Arrow/Parquet ingest throughput | Not measured | Parquet connector path is still a stub | Red |

## Non-negotiable product requirement

This project must be scored against:

- any tabular data
- any column naming style
- any supported database or file source
- local, API, and MCP execution paths

Industry-specific results are useful only as narrow regressions. They are not product-level accuracy claims.

## Gaps that still matter

| Area | Current gap | Why it matters |
| --- | --- | --- |
| Import accuracy | No labeled corpus yet for "any DB/CSV import" percentage accuracy | We can say the path is safer and tested, but not yet claim a universal import accuracy %
| Resolver accuracy | Current measured percentage is industry-specific, not universal | Needed before claiming "any data, any column, any database"
| Join accuracy | Correctness tests are green, but there is no benchmark corpus with a reported accuracy % | Needed before claiming broad multi-hop join reliability
| Database coverage | No benchmark matrix yet across multiple DB engines and schemas | Needed before claiming "any database"
| Arrow/Parquet | `parquet` path is not production-ready yet | You want Arrow/Parquet, local installs, API, and MCP at scale
| API latency | No current end-to-end API benchmark summary in `benchmarks/` | Needed for deployment planning
| Local embedded latency | No dedicated local-only benchmark summary yet | Needed for desktop/offline installs

## Proposed production targets

| Area | Target |
| --- | --- |
| Import accuracy | >= 99% typed-field correctness on a labeled mixed-format import corpus |
| Resolver accuracy | >= 95% top-1 on a cross-domain corpus spanning generic ERP, finance, logistics, healthcare, retail, manufacturing, and synthetic unknown schemas |
| Join accuracy | >= 95% correct join-path selection on labeled 1-hop and 2-hop corpora across mixed-schema databases |
| Database coverage | Green benchmark runs on PostgreSQL, SQLite, DuckDB, MySQL-compatible, and CSV/Arrow/Parquet sources |
| Local hot query latency | p50 < 50 ms, p95 < 150 ms |
| API query latency | p50 < 150 ms, p95 < 400 ms |
| MCP query latency | p50 < 300 ms, p95 < 700 ms |
| CSV ingest throughput | >= 2k rows/s on tall files, >= 500 rows/s on wide 200+ column files |
| Arrow/Parquet ingest throughput | >= 50k rows/s local scan for common analytics shapes once implemented |

## Read this scorecard correctly

- The Mojo compute layer is already fast enough to justify the architecture.
- The hospitality resolver number is a narrow regression, not a product-wide accuracy claim.
- CSV import is materially improved and currently fast enough for local usage, but the project still lacks a formal universal import-accuracy benchmark.
- The missing pieces for the user requirement are universal benchmark corpora, database-matrix testing, and real Arrow/Parquet ingest.
