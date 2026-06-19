---
sidebar_position: 9
---

# Supported Secondary Modes

Self-hosted service deployment is the product path.

These modes remain supported, but they are secondary to the service-first contract and should not be confused with the primary installation story.

## Simulation workflows

Simulation remains fully implemented and tested:

- `/v1/simulate`
- `/v1/recommend`
- `/v1/jobs`
- simulation-focused SDK and integration flows

## Local helper APIs

`algenta-core` still ships:

- `map_data`
- `list_datasets`
- `get_dataset_summary`
- `query_data`
- `query_with_metadata`
- `query_batch`
- `query_sql_report`
- `simulate`
- `decision`
- `optimize`
- `forecast`

These remain supported. They are simply not the first examples shown anymore.

## Direct API client

The lower-level direct client remains supported:

```python
from decision_engine import AlgentaClient
```

That direct surface also exposes the governed data/query helpers Mission now needs directly:

- `client.get_contract()`
- `client.list_datasets(search="orders", compact=True)`
- `client.get_dataset_summary(dataset_id)`
- `client.query_with_metadata(request)`
- `client.query_batch(request)`
- `client.query_sql_report(request)`
- `client.list_agent_runs(...)`
- `client.query_agent_run_checkpoints(...)`
- `client.query_agent_run_mission_events(...)`
- `client.query_agent_run_telemetry(...)`
- `client.replay_agent_run(run_id, checkpoint_id=...)`
- `client.fork_agent_run(run_id, checkpoint_id=...)`
- `client.get_audit_log_artifacts(...)`
- `client.list_execution_policy_snapshots()`

## MCP

MCP remains a broad, production-capable integration layer:

- `get_contract()`
- `list_data(search="orders", compact=true)`
- `get_data_summary(dataset_id)`
- `query_data(...)`
- `query_batch(...)`
- `query_sql_report(...)`
- `list_agent_runs(...)`
- `query_agent_run_checkpoints(...)`
- `query_agent_run_mission_events(...)`
- `query_agent_run_telemetry(...)`
- `get_audit_log_artifacts()`
- `list_execution_policy_snapshots()`
