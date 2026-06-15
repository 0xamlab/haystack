---
sidebar_position: 11
---

# How Codna Works Today

This page is the explicit truth-separation page for the repo.

## Current truth

Codna today is a hybrid system with:

- a self-hosted service deployment path
- governed data discovery and query flows
- a strong deterministic runtime core
- simulation workflows
- local helper APIs
- MCP breadth
- local runtime/device flows

## Primary path

The primary path we now publish is:

- deploy the self-hosted service
- verify `GET /v1/health`
- inspect the live machine-readable contract through `GET /v1/meta/contract`
- run the first decision through `POST /v1/simulate`
- or run the first governed query through `GET /v1/data?search=...&compact=1` -> `GET /v1/data/{dataset_id}/summary` -> `POST /v1/resolve` -> `POST /v1/verify` -> `POST /v1/query`
- widen from exact query to `POST /v1/query/batch` or `POST /v1/query/sql-report` only when the question actually needs it
- integrate over HTTP or SDK against the running service

On older self-hosted nodes that still return `404` for `/v1/meta/contract`,
raw HTTP integrations should fall back to `/openapi.json` and inspect
`x-primary-data-query-contract` instead.

The local `Runtime()` path remains supported, but it is the development/runtime surface rather than the product install path.

Once the service is running, the direct API client, hosted runtime facade, and
MCP operator surface all expose the same persisted lineage-aware operator
workflows:

- `list_agent_runs(...)` / `listAgentRuns({ ... })` for persisted run discovery
- `query_agent_run_checkpoints(...)` / `queryAgentRunCheckpoints({ ... })` for
  cross-run checkpoint inspection
- `query_agent_run_mission_events(...)` /
  `queryAgentRunMissionEvents({ ... })` for canonical mission-trace inspection
- `query_agent_run_telemetry(...)` / `queryAgentRunTelemetry({ ... })` for
  persisted runtime telemetry
- `replay_agent_run(...)` / `replayAgentRun(...)` and `fork_agent_run(...)` /
  `forkAgentRun(...)` for deterministic replay and branch-from-checkpoint flows
- `get_audit_log_artifacts(...)` / `getAuditLogArtifacts({ ... })` and
  `list_execution_policy_snapshots()` / `listExecutionPolicySnapshots()` for
  immutable audit artifacts and execution-policy lineage review

## Target model

The target architecture is:

- service-first deployment
- deterministic backend/runtime core
- optional local runtime for development and embedded use

## Why this page exists

This repository contains multiple real product surfaces. The docs now make the distinction explicit so usage guidance stays aligned with code truth.

## Related pages

- [Quickstart](/quickstart)
- [Query](/query)
- [Direct API Client](/direct-api-client)
- [Local Runtime](/integrations/local-runtime)
- [MCP](/mcp)
- [TypeScript SDK](/sdks/typescript)
- [Competitor Compatibility](/competitor-compatibility)
