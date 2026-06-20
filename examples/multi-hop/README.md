# Multi-hop Query Examples

These files show the canonical multihop query surfaces that Algenta already
ships.

## Files

- `data_connect_request.json` — high-level `POST /v1/data/connect` body for
  onboarding a governed database dataset
- `query_request.json` — exact `POST /v1/query` or `POST /v1/verify` body with
  explicit `join_path`
- `query_batch_request.json` — the same exact request wrapped for
  `de data query-batch <request.json>`
- `sql_report_request.json` — read-only joined rowset for
  `POST /v1/query/sql-report` or `de data sql-report <request.json>`
- `sql_report_correlation_request.json` — multi-source statistical SQL report
  for cases that Mission may route through `query_sql_source`
- `python_public_client_flow.py` — Python SDK replacement flow for the common
  Mission discovery, onboarding, exact query, batch query, and SQL report steps
- `typescript_public_client_flow.ts` — TypeScript SDK replacement flow for the
  same public surfaces
- `python_runtime_library_flow.py` — Python local-runtime replacement flow for
  Mission library tools such as `get_algenta_library_health` and
  `execute_algenta_library`
- `typescript_runtime_library_flow.ts` — TypeScript local-runtime replacement
  flow for the same Mission library tool lane
- `mcp_governed_exact_sequence.json` — MCP tool sequence for Mission-style
  governed exact dataset discovery and `query_data(...)`
- `mcp_governed_sql_report_sequence.json` — MCP tool sequence for Mission-style
  multihop statistical SQL via `query_sql_report(...)`
- `mcp_runtime_library_sequence.json` — MCP tool sequence for Mission-style
  local runtime library discovery and `execute_runtime_library(...)`
- `mission_functionality_surface_map.json` — machine-readable Mission-to-public
  surface map for governed query functions and local runtime/library functions
  across HTTP, Python SDK, TypeScript SDK, CLI, and MCP
- `mission_mojo_llm_module_status.json` — machine-readable Mission usage matrix
  for all `22` Mojo LLM modules

## How to use them

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

1. Replace every placeholder source name, dataset id, join key, and column with
   exact values from:
   - `GET /v1/data?search=...&compact=1`
   - `GET /v1/data/{dataset_id}/summary`
2. Use `data_connect_request.json` when you need the public onboarding
   replacement for Mission-style `ensure_governed_dataset`:

```bash
ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"
if [ -z "$ALGENTA_API_KEY" ]; then
  echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example." >&2
  exit 1
fi

ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.algenta.ai}}}"

curl -X POST "${ALGENTA_BASE_URL}/v1/data/connect" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/multi-hop/data_connect_request.json
```

The shell snippet above uses the Cloud Managed default when no base URL env var
is set. In `self_hosted` and `air_gapped`, set `ALGENTA_BASE_URL`,
`DE_BASE_URL`, or `ALGENTA_API_URL` explicitly to your self-hosted base URL
before running it.
The request still uses the canonical bearer header shape,
`Authorization: Bearer <YOUR_ALGENTA_API_KEY>`, with the token supplied through
`ALGENTA_API_KEY` or `DE_API_KEY`.

If the response returns `status = "needs_selection"`, resend `POST /v1/data/connect`
with the returned `connection_id` plus one exact `selection` value from
`choices[]`.
3. Send `query_request.json` to:
   - `POST /v1/verify`
   - then `POST /v1/query`
4. Use `query_batch_request.json` when you want the same exact multihop request
   through the current public CLI contract:

```bash
de data query-batch examples/multi-hop/query_batch_request.json
```

5. Use `sql_report_request.json` only when you need a wide joined rowset or
   custom SQL analysis:

```bash
de data sql-report examples/multi-hop/sql_report_request.json
```

6. Use `sql_report_correlation_request.json` when the Mission-side workflow
   would otherwise reach for `query_sql_source` to do a custom statistical join:

```bash
de data sql-report examples/multi-hop/sql_report_correlation_request.json
```

That is the public replacement for a custom governed SQL report. There is no
one-to-one public hosted `query_sql_source` endpoint in this repo.

7. Use the runnable client examples when you want the Mission-to-public-surface
   translation in code instead of JSON:

```bash
python3 examples/multi-hop/python_public_client_flow.py
```

```bash
pnpm dlx tsx examples/multi-hop/typescript_public_client_flow.ts
```

Both files show the public replacements for:

- `ensure_governed_dataset`
- `list_data`
- `get_data_schema`
- `query_data`
- `query_data_batch`
- `query_sql_source` / `query_sql_report`

8. Use the local-runtime examples when the Mission path you are porting uses
the direct local Algenta library tools instead of governed hosted query
surfaces:

```bash
python3 examples/multi-hop/python_runtime_library_flow.py
```

```bash
pnpm dlx tsx examples/multi-hop/typescript_runtime_library_flow.ts
```

Those files show the public replacements for:

- `get_algenta_library_health`
- `list_algenta_libraries`
- `inspect_algenta_library`
- `get_algenta_library_module`
- `execute_algenta_library`

9. Use the MCP sequences when you are wiring an agent client that talks to the
public MCP server directly instead of using the HTTP, CLI, or SDK surfaces:

- [`mcp_governed_exact_sequence.json`](mcp_governed_exact_sequence.json)
- [`mcp_governed_sql_report_sequence.json`](mcp_governed_sql_report_sequence.json)
- [`mcp_runtime_library_sequence.json`](mcp_runtime_library_sequence.json)

Those files show the public replacements for:

- `list_data`
- `get_data_summary`
- `query_data`
- `query_sql_source` via `query_sql_report`
- `list_algenta_libraries`
- `execute_algenta_library`

## Mission Mojo LLM module note

Mission does mount the local Algenta runtime library tools, but that does not
mean the Mojo LLM modules are the default path for governed multihop analytics.

- Use governed discovery plus `query` / `query-batch` / `sql-report` for
  multihop data analysis
- Use the local runtime library lane only for direct deterministic compute
- Mission currently catalogs `22` Mojo LLM modules, but only `19` are covered
  in its checked-in end-to-end conversation harness today
- `vector_kernels.ranker` is only used in lower-level source-ranking helpers
- `rerank_eval` and `inference_cost_latency` are cataloged but not currently
  used in Mission's checked-in execution paths

If you do need the same local runtime-library lane Mission mounts for direct
deterministic compute, use:

- [`python_runtime_library_flow.py`](python_runtime_library_flow.py)
- [`typescript_runtime_library_flow.ts`](typescript_runtime_library_flow.ts)
- [`apps/docs/docs/integrations/local-runtime.md`](../../apps/docs/docs/integrations/local-runtime.md)

The exact module-by-module status lives in:

- [`mission_mojo_llm_module_status.json`](mission_mojo_llm_module_status.json)

The full machine-readable Mission functionality map lives in:

- [`mission_functionality_surface_map.json`](mission_functionality_surface_map.json)

## What not to do

- Do not use `query_sql_report` for ordinary exact grouped metrics.
- Do not guess `dataset_id`, `source_name`, `metric_column`, or join keys.
- Do not exceed `join_path.max_hops = 6` (`7` tables).
- Do not look for public hosted routes named `query_sql_source`,
  `register_sql_source`, `get_sources_graph`, or `map_data_sources`.

For the full guide, see
[`apps/docs/docs/api-reference/multi-hop-joins.md`](../../apps/docs/docs/api-reference/multi-hop-joins.md).
