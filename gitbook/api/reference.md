---
icon: code
description: The complete Algenta HTTP API endpoint reference — every operation grouped by area, with method, path, and summary, generated from the OpenAPI spec.
---

# API endpoint reference

Every Algenta HTTP operation, grouped by area and generated from the canonical OpenAPI spec — so the list is complete and current. All routes are versioned under `/v1`; authenticate with `Authorization: Bearer <key>` (legacy `X-API-Key` is accepted).

{% hint style="info" %}
To call any endpoint live (parameters, schemas, Test it), use the [API explorer](explorer.md). Errors are listed on [Error codes](errors.md); limits on [Rate limits & quotas](rate-limits.md).
{% endhint %}

## Account

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/me` | Get current user and org info |
| `PATCH` | `/v1/me` | Update current user and/or org name |
| `GET` | `/v1/usage` | Get usage summary for current billing period |
| `GET` | `/v1/limits` | Get rate limits and quotas for current plan |
| `GET` | `/v1/distributions` | List supported distribution types |
| `GET` | `/v1/templates` | List built-in simulation templates |
| `GET` | `/v1/api-keys` | List active API keys |
| `POST` | `/v1/api-keys` | Create a new API key |
| `DELETE` | `/v1/api-keys/{key_id}` | Revoke an API key |

## Async Jobs

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/jobs/list` | List async jobs for this org |
| `POST` | `/v1/jobs` | Submit an async simulation job |
| `GET` | `/v1/jobs/{job_id}` | Poll job status |
| `GET` | `/v1/jobs/{job_id}/result` | Fetch job result |
| `POST` | `/v1/jobs/{job_id}/cancel` | Cancel a job |
| `POST` | `/v1/webhooks/test` | Test webhook delivery |

## Auth

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/auth/signup` | Create a new account |
| `POST` | `/auth/login` | Login and get a session token |
| `GET` | `/auth/verify` | Verify email address via token link |
| `POST` | `/auth/forgot-password` | Request a password reset email |
| `POST` | `/auth/reset-password` | Complete password reset with token |

## Billing

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/billing/checkout` | Create Stripe Checkout session |
| `POST` | `/v1/billing/portal` | Create Stripe Billing Portal session |
| `GET` | `/v1/billing/info` | Get current billing info |

## Calibration

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/calibration` | Get confidence calibration status |

## Data

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/data/connect` | Connect data, pick a dataset, and make it queryable. |
| `GET` | `/v1/data` | List visible datasets for the caller. |
| `GET` | `/v1/data/{dataset_id}/summary` | Get low-token discovery summary for one dataset. |
| `GET` | `/v1/data/{dataset_id}` | Get one dataset plus its schema. |
| `DELETE` | `/v1/data/{dataset_id}` | Disconnect data by deleting the dataset. |
| `POST` | `/v1/data/{dataset_id}/refresh` | Refresh a dataset from its saved origin. |

## Data Connectors

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/connectors` | List data connectors |
| `POST` | `/v1/connectors` | Create a data connector with credentials |
| `GET` | `/v1/connectors/{connector_id}` | Get one data connector |
| `PATCH` | `/v1/connectors/{connector_id}` | Update connector name or config |
| `DELETE` | `/v1/connectors/{connector_id}` | Delete a data connector |
| `GET` | `/v1/connectors/types` | List supported connector types |
| `POST` | `/v1/connectors/{connector_id}/test` | Test connector — real connection attempt |
| `POST` | `/v1/connectors/test` | Test an inline connector preview without saving it |
| `GET` | `/v1/connectors/{connector_id}/browse` | Browse connector schema — list tables, files, or datasets |
| `POST` | `/v1/connectors/browse` | Browse an inline connector preview without saving it |

## Data Mapping

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/map/{map_id}` | Poll for deep analysis (join keys + derived relationships) |
| `POST` | `/v1/map` | Instantly map any dataset — no schema, no ETL |

## Datasets

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/datasets/onboard` | Onboard a dataset — zero-config schema profiling + auto-training |
| `POST` | `/v1/datasets/onboard/file` | Onboard from file upload — CSV, Excel, Parquet, JSON, JSONL |
| `GET` | `/v1/datasets/{dataset_id}/status` | Live status and model tier for a dataset |
| `GET` | `/v1/datasets` | List all datasets registered for this org |
| `POST` | `/v1/datasets/{dataset_id}/retrain` | Re-trigger semantic training for a dataset |

## Decision

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/recommend` | Compare actions and get a recommendation |
| `POST` | `/v1/score` | Score a simulation with custom weights |
| `POST` | `/v1/batch` | Run multiple simulations in one request |
| `POST` | `/v1/compare` | Side-by-side scenario comparison |

## Decision Memory

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/decisions` | Log a decision |
| `GET` | `/v1/decisions` | List logged decisions |
| `GET` | `/v1/decisions/{decision_id}` | Get a single decision |
| `DELETE` | `/v1/decisions/{decision_id}` | Delete a decision log entry |
| `PATCH` | `/v1/decisions/{decision_id}/outcome` | Record actual outcome |
| `POST` | `/v1/decisions/{decision_id}/execute` | Execute a decision via webhook |

## Deployments

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/deployments/regions` | List available cloud providers and regions |
| `GET` | `/v1/deployments` | Get current org deployment |
| `POST` | `/v1/deployments` | Request a new cloud deployment |
| `DELETE` | `/v1/deployments/{deployment_id}` | Deprovision a deployment |
| `GET` | `/v1/deployments/{deployment_id}/cost` | Get current month cloud cost for a deployment |

## Engines

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/engines` | List all engines |
| `GET` | `/v1/engines/tiers` | Engines by tier |
| `GET` | `/v1/engines/{slug}` | Engine detail |

## Execution Policy

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/execution/policy` | Get execution policy |
| `PATCH` | `/v1/execution/policy` | Update execution policy |

## Export

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/runs/{run_id}/export.{fmt}` | Export simulation run results |

## Infrastructure

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/infrastructure` | Real compute infrastructure health |
| `POST` | `/v1/nodes/register` | Register a self-hosted compute node |
| `POST` | `/v1/nodes/heartbeat` | Worker node heartbeat |
| `DELETE` | `/v1/nodes/{node_id}` | Deregister a node |

## Ingest

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/ingest` | Instant data ingestion — zero-config simulation from any table |

## Logs

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/logs` | Stream structured logs via Server-Sent Events |

## Playground

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/playground` | Try Codna — no API key required |

## Products

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/decision` | Get an optimal decision |
| `POST` | `/v1/agent/run` | Run an AI agent task |
| `POST` | `/v1/optimize` | Optimize a business variable |
| `POST` | `/v1/retrieve` | Search a knowledge base |
| `POST` | `/v1/forecast` | Forecast a business metric |

## Runs

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/runs` | List simulation runs for this org |
| `GET` | `/v1/runs/{run_id}` | Get a single simulation run |
| `GET` | `/v1/analytics` | Aggregated analytics for dashboard charts |

## Semantic Query

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/resolve` | Resolve structured intent into an exact executable plan |
| `POST` | `/v1/query` | Execute a structured query — schema-free, zero domain assumptions |
| `POST` | `/v1/sources/schema` | Infer and return the structural schema of data sources |
| `POST` | `/v1/query/batch` | Execute multiple governed exact queries in one request |
| `POST` | `/v1/query/sql-report` | Execute a constrained read-only SQL report over authorized datasets |
| `POST` | `/v1/verify` | Validate a structured query plan before execution |

## Simulation

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/simulate` | Run a simulation |
| `GET` | `/v1/simulate/templates` | List simulation templates for all industries |
| `GET` | `/v1/simulate/templates/{template_id}` | Get a simulation template with ready-to-run payload |
| `POST` | `/v1/templates/{template_id}/run` | Run a simulation template directly |

## Source Registry

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/sources/register` | Register a data source — profile, index, detect joins to all existing sources |
| `GET` | `/v1/sources` | List all registered sources for this org |
| `GET` | `/v1/sources/graph` | Connection graph — all detected join paths between registered sources |
| `GET` | `/v1/sources/{source_id}` | Get schema for a registered source |
| `DELETE` | `/v1/sources/{source_id}` | Remove a registered source |

## Streaming

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/simulate/stream` | Streaming simulation via Server-Sent Events |

## System

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/health` | Health check |
| `GET` | `/v1/version` | API and engine version |
| `GET` | `/v1/meta/contract` | Machine-readable Codna contract |

## Team

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/team` | List team members |
| `POST` | `/v1/team/invite` | Invite a team member |
| `PATCH` | `/v1/team/{user_id}/role` | Update a team member's role |
| `DELETE` | `/v1/team/{user_id}` | Remove a team member |
| `GET` | `/v1/audit-logs` | Paginated audit log from DB |

## Triggers

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/triggers` | Register a trigger |
| `GET` | `/v1/triggers` | List all triggers |
| `POST` | `/v1/triggers/{trigger_id}/fire` | Fire a trigger |
| `PATCH` | `/v1/triggers/{trigger_id}/pause` | Pause or resume a trigger |
| `DELETE` | `/v1/triggers/{trigger_id}` | Delete a trigger |

## What-If Analysis

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/simulate/what-if` | What-if parametric sweep |

## credits

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/credits/refresh` | Issue a new execution credit batch for a local runtime device |

## devices

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/device/register` | Register a device and receive a signed license token |
| `POST` | `/v1/device/heartbeat` | 24-hour device heartbeat — updates last_seen and returns device count |
| `GET` | `/v1/device/list` | List all registered devices for this org |
| `DELETE` | `/v1/device/{registration_id}` | Revoke a registered device |

## metering

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/metering` | Ingest local runtime execution analytics |
