---
sidebar_position: 3
---

# CLI

The CLI is now runtime-first as well.

## Private-profile base URL behavior

Use `DE_BASE_URL`, `ALGENTA_BASE_URL`, `ALGENTA_API_URL`, or a saved CLI
`base_url` when you want the CLI to target a running self-hosted Algenta
service.

- `self_hosted` and `air_gapped` profiles require an explicit CLI target
- `self_hosted` and `air_gapped` profiles fail closed for Codna-owned cloud URLs
- private profiles allow private/internal origins by default and public customer
  origins only when they are present in `ALGENTA_EGRESS_ALLOWLIST`

## Install

```bash
pip install algenta-core
```

## Primary command

```bash
algenta demo
```

In a real terminal, that opens the interactive scenario picker and walks through:

- bundled source registration
- structured request selection
- resolved plan metadata
- verification / guardrail behavior
- query result, latency, and plan hash

For deterministic scripted runs, use one of the explicit scenario modes:

```bash
algenta demo --list
algenta demo --all --no-interactive
algenta demo --scenario region --no-interactive
algenta demo --scenario canada_filter --no-interactive
algenta demo --scenario guardrail --no-interactive
```

In the interactive terminal menu, the non-numeric actions are spelled out as:

- `all` -> run every scenario
- `recipes` -> show the local, CLI, and API follow-up recipes
- `quit` -> exit the demo

The menu also accepts chained input such as `1,recipes` or `all,quit`.

## Brandable import preview

```bash
algenta import orders.csv --name orders
```

That runs a branded local import preview and prints:

- source name and origin
- row and field counts
- schema revision
- registration latency
- copy-pasteable next-step code for `Runtime.resolve() -> Runtime.query()`

Important:

- this validates local registration and schema discovery
- it does **not** persist a runtime session across separate CLI invocations

For related exports, the same command supports a local bundle:

```bash
algenta import orders.csv financial.csv ratings.csv
```

That prints a branded bundle summary with imported sources, explicit per-file failures, and deterministic shared-field overlap hints.

## Other supported commands

```bash
de contract
de data list --search orders --compact --limit 5
de data summary orders_facts
de data query-batch batch_request.json
de data sql-report sql_report_request.json
de connectors create connector_request.json --format json
de connectors list --page 1 --limit 25 --format json
de connectors get <connector_id> --format json
de connectors update <connector_id> connector_update_request.json --format json
de connectors test <connector_id> --format json
de connectors preview-test connector_preview_request.json --format json
de connectors browse <connector_id> --format json
de connectors preview-browse connector_preview_request.json --format json
de connectors delete <connector_id> --format json
de capabilities providers --format json
de capabilities provider provider.skill_pack.algenta --format json
de capabilities bindings --provider-id provider.skill_pack.algenta --format json
de capabilities list --kind skill,mcp_tool --format json
de capabilities route examples/capability-plane/capability_route_request.json --format json
de capabilities execute examples/capability-plane/capability_execute_request.json --format json
de repositories snapshot <repository_id> repository_snapshot_request.json --format json
de repositories get-snapshot <repository_id> <snapshot_id> --format json
de repositories triage <repository_id> repository_triage_request.json --format json
de repositories decision-plan <repository_id> repository_decision_plan_request.json --format json
de repositories simulate <repository_id> repository_simulation_request.json --format json
de repositories apply <repository_id> repository_apply_request.json --format json
de recommend recommend_request.json --format json
de decision score score_request.json --format json
de decision batch batch_request.json --format json
de decision compare compare_request.json --format json
de product decision product_decision_request.json --format json
de product agent-run product_agent_run_request.json --format json
de product optimize product_optimize_request.json --format json
de product retrieve product_retrieve_request.json --format json
de product forecast product_forecast_request.json --format json
de job list --page 2 --limit 10 --status queued --format json
de job status <job_id> --format json
de job result <job_id> --format json
de job cancel <job_id> --format json
de job wait <job_id> --timeout 30 --format json
de webhook test https://example.com/webhook --format json
de triggers register trigger_request.json --format json
de triggers list --status active --page 1 --limit 10 --format json
de triggers fire <trigger_id> --force --format json
de triggers pause <trigger_id> --format json
de triggers resume <trigger_id> --format json
de triggers delete <trigger_id> --format json
de decisions log decision_log_request.json --format json
de decisions list --with-outcome-only --format json
de decisions get <decision_id> --format json
de decisions outcome <decision_id> decision_outcome_request.json --format json
de decisions execute <decision_id> decision_execute_request.json --format json
de decisions delete <decision_id> --format json
de account update account_update_request.json --format json
de account distributions --format json
de account templates --format json
de team list --format json
de team invite new.user@example.com member --format json
de team update-role user_123 viewer --format json
de team remove user_123 --format json
de team audit-logs --format json
de team audit-artifacts --format json
de devices list --format json
de devices revoke <registration_id> --format json
de billing info --format json
de credits refresh credits_refresh_request.json --format json
de metering ingest metering_request.json --format json
de execution-policy get --format json
de execution-policy snapshots --format json
de execution-policy update execution_policy_request.json --format json
de deployments regions --format json
de deployments get --format json
de deployments create deployment_request.json --format json
de deployments cost <deployment_id> --format json
de deployments delete <deployment_id> --format json
de llm models --format json
de llm resolve-artifact artifact_request.json --format json
de llm chat chat_request.json --stream --format json
de llm responses responses_request.json --stream
de agent-runs list --status completed --format json
de agent-runs events <run_id> --stream --format json
de agent-runs checkpoints <run_id> --format json
de agent-runs query-checkpoints --status completed --format json
de agent-runs mission-events <run_id> --limit 25 --format json
de agent-runs query-mission-events --status completed --format json
de agent-runs telemetry <run_id> --limit 25 --format json
de agent-runs query-telemetry --status completed --format json
algenta map file1.csv [file2.csv ...]
algenta query "total revenue by product line" orders.csv
algenta simulate
algenta benchmark
algenta version
algenta upgrade
```

Use the CLI data surface when you want the same public hosted discovery/query contract without writing code:

- `de contract` for the live machine-readable Algenta contract
- `de data list --search ... --compact` for low-token dataset discovery
- `de data summary <dataset_id>` for the low-token dataset summary
- `de data query-batch <request.json>` for governed exact-query batches
- `de data sql-report <request.json>` for constrained read-only rowset reports
- `de connectors create <request.json>` to save one reusable connector configuration
- `de connectors list` for saved connector inventory
- `de connectors get <connector_id>` for one saved connector definition
- `de connectors update <connector_id> <request.json>` to change saved connector config or metadata
- `de connectors test <connector_id>` to persist a real connector health check
- `de connectors preview-test <request.json>` to test one inline connector without saving it
- `de connectors browse <connector_id>` for saved connector schema or item discovery
- `de connectors preview-browse <request.json>` to browse one inline connector without saving it
- `de connectors delete <connector_id>` to remove one saved connector
- `de capabilities providers` for unified capability-provider inventory
- `de capabilities provider <provider_id>` for one provider profile and auth summary
- `de capabilities bindings [--provider-id ...] [--scope ...]` for unified binding inventory
- `de capabilities list [--kind ...] [--provider-id ...] [--binding-id ...]` for routed capability inventory across data, MCP, skills, native tools, and runtime libraries
- `de capabilities route <request.json>` to route one objective to the selected capability before branching into a specialist workflow
- `de capabilities execute <request.json>` to execute one selected `algenta_managed` capability by canonical capability id
  Checked-in request bodies live in `examples/capability-plane/`
- CLI execution ownership is authoritative:
- `algenta_managed` routes can execute through `de capabilities execute`
- `client_managed` routes must execute through the customer app or local adapter path and fail closed otherwise
- `de repositories snapshot <repository_id> <request.json>` to create or reuse one immutable repository snapshot
- `de repositories get-snapshot <repository_id> <snapshot_id>` to inspect one stored repository snapshot
- `de repositories triage <repository_id> <request.json>` to build one bounded workspace evidence bundle from repository signals
- `de repositories decision-plan <repository_id> <request.json>` to create one immutable repository DecisionPlan revision backed by `POST /decision-plans`
- `de repositories simulate <repository_id> <request.json>` to run the repository apply gate and return the DecisionEnvelope
- `de repositories apply <repository_id> <request.json>` to emit a patch, create a local branch, or open a remote PR after the gate passes
- `de recommend <request.json>` for ranked action recommendations
- `de decision score <request.json>` for weighted decision scoring
- `de decision batch <request.json>` for multi-request decision execution
- `de decision compare <request.json>` for side-by-side scenario comparison
- `de product decision <request.json>` for the simplified business-facing decision helper
- `de product agent-run <request.json>` for the simplified business-facing task helper
- `de product optimize <request.json>` for the simplified business-facing optimization helper
- `de product retrieve <request.json>` for the simplified business-facing retrieval helper
- `de product forecast <request.json>` for the simplified business-facing forecasting helper
- `de job list --page ... --limit ... [--status ...]` for paginated async job inventory
- `de job status <job_id>` to inspect one async job status payload directly
- `de job result <job_id>` to fetch one async job result payload directly
- `de job cancel <job_id>` to cancel one queued or running async job
- `de job wait <job_id> --timeout ...` to block until completion or terminal failure
- `de webhook test <callback_url>` to send one test webhook payload and inspect delivery status
- `de decisions log <request.json>` to persist one decision-memory record
- `de decisions list --with-outcome-only` for paginated decision-memory review
- `de decisions get <decision_id>` for one persisted decision-memory record
- `de decisions outcome <decision_id> <request.json>` to record a real outcome delta
- `de decisions execute <decision_id> <request.json>` to dispatch one decision-memory record to a webhook
- `de decisions delete <decision_id>` to remove one persisted decision-memory record
- `de account update <request.json>` to update the current user name and or organization name
- `de account distributions` for the current organization simulation distribution catalog
- `de account templates` for the current organization scenario template catalog
- `de team list` for the current organization member roster
- `de team invite <email> [role]` to create a pending team invitation
- `de team update-role <user_id> <role>` to update one team member role
- `de team remove <user_id>` to suspend one team member
- `de team audit-logs` for the current organization audit trail
- `de team audit-artifacts` for the immutable audit-artifact trail with content hashes
- `de devices list` for the current organization registered-device inventory
- `de devices revoke <registration_id>` to revoke one registered device slot
- `de billing info` for the current organization plan and subscription state
- `de credits refresh <request.json>` to request one local runtime credit batch
- `de metering ingest <request.json>` to flush one validated local metering batch
- `de execution-policy get` for the current autonomous execution thresholds
- `de execution-policy snapshots` for the full execution-policy snapshot history
- `de deployments regions` for deployment provider/region discovery
- `de deployments get` for the current organization deployment
- `de deployments cost <deployment_id>` for current-month deployment cost details
- `de llm models` for the truthful utility and provider-backed model catalog, including routed target, failover, timeout, aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness
- `de llm resolve-artifact <request.json>` for cache-safe Hugging Face artifact bridge resolution
- `de llm chat <request.json> --stream` for streamed deterministic utility chat
- `de llm responses <request.json> --stream` for streamed deterministic response events
- `de agent-runs list [--status ...]` for paginated persisted agent-run inventory
- `de agent-runs events <run_id> --stream` for SSE-backed agent-run event playback
- `de agent-runs checkpoints <run_id>` for one run's persisted checkpoint boundaries
- `de agent-runs query-checkpoints [--status ...]` for cross-run checkpoint discovery
- `de agent-runs mission-events <run_id> [--limit ...]` for canonical mission-event records
- `de agent-runs query-mission-events [--status ...]` for cross-run mission-event inspection
- `de agent-runs telemetry <run_id> [--limit ...]` for one run's persisted telemetry batches
- `de agent-runs query-telemetry [--status ...]` for cross-run telemetry inspection

The repository `decision-plan` CLI verb maps to the plural API resource
`POST /v1/repositories/{repository_id}/decision-plans`, so the command stays
verb-shaped while the HTTP contract stays resource-shaped.

For fully local self-hosted repository planning, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`
before starting the API server or local stack. That planner is explicit and
bounded; it currently supports deterministic Python return-literal mismatch
repairs and fails closed with `repository_local_planner_unsupported` outside
that contract.

The `de repositories decision-plan ...` summary prints planner provenance from
`repository_analysis.planner_model_id`,
`repository_analysis.planner_execution_mode`, and
`repository_analysis.planner_provider_backend` so the operator can see whether a
patch plan came from the bounded deterministic local planner or a
provider-backed chat planner.

The streamed CLI routes support both output modes:

- `--format json` prints one JSON object per SSE event line
- default table mode renders deterministic summaries for chat chunks, response lifecycle events, and completed agent-run streams

Example batch request file:

```json
{
  "defaults": {
    "dataset_id": "orders_facts"
  },
  "queries": [
    {
      "key": "overall_completed_orders",
      "request": {
        "metric": { "role": "metric", "hint": "completed_order_count" },
        "aggregation": "sum"
      }
    }
  ]
}
```

Example SQL report request file:

```json
{
  "sources": [{ "dataset_id": "orders_facts", "alias": "orders" }],
  "sql": "select order_month, gross_revenue from orders order by order_month desc limit 12",
  "max_rows": 100
}
```

## Why this matters

The CLI still supports simulation and helper flows, but the first command we recommend is now the runtime demo because it matches the primary product path.
