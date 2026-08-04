# Benchmark derived from TPC-H — status: BLOCKED on Neon API credentials

Scoped from `~/.claude/plans/benchmark-discovery-stac-tpc-synthesis.md` §2. This is an internal,
work-in-progress status note, not a results page — no query has been run against this repo's
query engine yet, so no correctness or timing claim is made here. Per this repo's standing
publication policy, this stays in `benchmarks/` (never `gitbook/`) until it contains verified
results, and even then only promotes externally on an outright, disclosed win.

## Why this is blocked

The task that scoped this run required loading TPC-H-derived tables into an **isolated Neon
branch** (Neon's copy-on-write branching), explicitly *not* the shared main database this repo's
other suites depend on (`NEON_TEST_DB_URL` in `.env`, shared with sqai/mission), and explicitly
*not* a silent local-SQLite substitute. Creating that isolated branch requires **Neon API/CLI
access** (a `NEON_API_KEY`/`NEON_PROJECT_ID`-style credential usable with `neonctl` or the Neon
REST API) — a Postgres connection string alone cannot create a branch.

Searched exhaustively for such a credential and found none:

- `.env` / `.env.example` (repo root and the three `codex-*` sibling clones) — only
  `NEON_TEST_DB_URL` (a plain Postgres connection string to the shared main DB), no
  `NEON_API_KEY` / `NEON_PROJECT_ID`.
- Shell profiles (`~/.zshrc`, `~/.zprofile`, `~/.bash_profile`, `~/.profile`) and the current
  process environment — nothing Neon-related.
- `~/.claude/settings.json` and other Claude config — only historical Bash-permission log
  entries that happen to reference the same `NEON_TEST_DB_URL` connection string (via curl/API
  test commands against the local connector service), not an API key.
- `gh secret list -R thyn-ai/algenta` — no Neon-named secret (and secret values aren't readable
  even if one existed).
- `neonctl` — not installed, and running it via `npx neonctl` has no stored credentials to use
  (`neonctl auth` requires an interactive browser device-flow login, which isn't available in
  this non-interactive environment).

Per the task's explicit instruction, this is a named, real constraint from the product owner, not
something to route around by writing into the shared main DB or substituting local SQLite — so
the Postgres-backed load, the real end-to-end engine run against it, correctness verification,
and the SF=10 timing step are all **on hold pending a Neon API credential** being supplied.

**No Neon branch was created.** There is nothing to delete or keep — the product owner's own
cleanup note (requested at the end of the task) is moot until a branch actually exists.

## What was done anyway (ungated, pre-authorized, zero risk)

The product owner explicitly pre-authorized cloning/building/running
`github.com/electrum/tpch-dbgen` by name, independent of the Neon question, so that prep is done
and ready for whoever resumes this with credentials:

- Cloned `electrum/tpch-dbgen` to `/tmp/tpch-work/tpch-dbgen`, built `dbgen`/`qgen` on this
  machine (`gcc`, `MACHINE=MAC DATABASE=ORACLE WORKLOAD=TPCH` per the repo's own `makefile`;
  builds clean modulo pre-existing deprecation warnings in the 2010-vintage C source, no errors).
- Generated SF=1 data: `dbgen -vf -s 1` into `/tmp/tpch-work/tpch-dbgen/sf1/`, 8 `.tbl` files,
  1.1 GB total. `lineitem.tbl` has exactly 6,001,215 rows, matching TPC-H SF=1's documented
  LINEITEM cardinality — confirms the generator ran correctly at the intended scale.
- The 22 reference query templates (`queries/1.sql` … `queries/22.sql`, unsubstituted `qgen`
  form) are present in the same clone for the translation pass.

This data was intentionally left uncommitted (1.1 GB of generated fixture data does not belong in
git) at `/tmp/tpch-work/tpch-dbgen/sf1/` on this machine, ready to load into an isolated Neon
branch the moment one exists.

## What is genuinely not done, and why

Everything downstream of "load into Postgres" was intentionally not attempted, rather than
substituting an unapproved path to produce a partial answer that could be mistaken for a real
Neon-backed run:

- Loading the SF=1 tables into any live Postgres instance.
- Verifying which of the two connector paths in `apps/api_server/connectors/` this task meant by
  "the real connector path... different from the file-connector path used for the earlier CSV
  benchmark" — deferred until there's an actual target database to point it at.
- Translating the 22 TPC-H queries into this repo's query-plan JSON op-chain, and the
  correctness-vs-DuckDB/SQLite verification pass.
- Any SF=10 timing comparison.

## Resuming this

Once a Neon API credential (or an explicit decision to use a different isolated Postgres
instance instead of Neon) is available:

1. `neonctl branches create --project-id <id> --name tpch-derived-bench` (or the REST-API
   equivalent), get that branch's own connection string.
2. Load `/tmp/tpch-work/tpch-dbgen/sf1/*.tbl` into it, tables prefixed `tpch_`, via the real
   connector path (verify in `apps/api_server/connectors/` which one is Postgres-backed and
   local/no-sidecar).
3. Continue at plan §2.5 step 3 (hand-translate + DuckDB-verify all 22 queries at SF=1).

Worktree: `/private/tmp/tpc-query-plane-gaps` (branch `feat/query-plane-union-composite-multiagg`,
PR #537, open) — the same worktree the multi-aggregate/composite-join/UNION kernel work landed in.
