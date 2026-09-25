---
icon: code
description: The complete Algenta HTTP API endpoint reference — every operation grouped by area, with method, path, and summary, generated from the OpenAPI spec.
---

# API endpoint reference

Every Algenta HTTP operation, grouped by area and generated from the canonical OpenAPI spec — so the list is complete and current. All routes are versioned under `/v1`; authenticate with `Authorization: Bearer <key>` (legacy `X-API-Key` is accepted).

{% hint style="info" %}
To call any endpoint live (parameters, schemas, Test it), use the [API explorer](explorer.md). Errors are listed on [Error codes](errors.md); execution policy and safety bounds on [Execution policy & safety limits](rate-limits.md).
{% endhint %}

## Account

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/api-keys` | List active API keys |
| `POST` | `/v1/api-keys` | Create a new API key |
| `DELETE` | `/v1/api-keys/{key_id}` | Revoke an API key |
| `GET` | `/v1/distributions` | List supported distribution types |
| `GET` | `/v1/limits` | Get execution policy and request safety bounds |
| `GET` | `/v1/me` | Get current user and org info |
| `PATCH` | `/v1/me` | Update current user and/or org name |
| `POST` | `/v1/products/{product}/onboard` | Self-service product onboarding (Supabase-authed): activate the free tier + mint the first API key |
| `GET` | `/v1/products/{product}/whoami` | Diagnose which org this identity resolves to and whether its devices are visible |
| `GET` | `/v1/provider-keys` | List configured per-tenant provider/engine keys (no key material) |
| `POST` | `/v1/provider-keys` | Set or rotate a per-tenant provider/engine key (BYOK; stored encrypted, never returned) |
| `DELETE` | `/v1/provider-keys/{backend}` | Delete a per-tenant provider/engine key |
| `POST` | `/v1/telys/onboard` | Self-service Telys onboarding (Supabase-authed): activate telys_developer + mint the first API key |
| `GET` | `/v1/templates` | List built-in simulation templates |
| `GET` | `/v1/usage` | Get usage summary for current billing period |

## Agent Runtime

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/agent/runs` | Create a persisted agent run |
| `GET` | `/v1/agent/runs` | List persisted agent runs |
| `GET` | `/v1/agent/runs/checkpoints` | Query persisted agent run checkpoints across runs |
| `GET` | `/v1/agent/runs/mission-events` | Query mission-event records across agent runs |
| `GET` | `/v1/agent/runs/telemetry` | Query telemetry batches across agent runs |
| `GET` | `/v1/agent/runs/{run_id}` | Get a persisted agent run |
| `POST` | `/v1/agent/runs/{run_id}/approve` | Approve a waiting agent run |
| `POST` | `/v1/agent/runs/{run_id}/cancel` | Cancel a pending agent run (idempotent) |
| `GET` | `/v1/agent/runs/{run_id}/checkpoints` | List persisted agent run checkpoints |
| `GET` | `/v1/agent/runs/{run_id}/events` | List persisted agent run events |
| `POST` | `/v1/agent/runs/{run_id}/fork` | Fork a persisted agent run from a checkpoint |
| `GET` | `/v1/agent/runs/{run_id}/mission-events` | List canonical agent run mission events |
| `POST` | `/v1/agent/runs/{run_id}/replay` | Replay a persisted agent run checkpoint deterministically |
| `POST` | `/v1/agent/runs/{run_id}/resume` | Resume a paused agent run |
| `GET` | `/v1/agent/runs/{run_id}/telemetry` | List agent run telemetry batches |

## Async Jobs

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/jobs` | Submit an async simulation job |
| `GET` | `/v1/jobs/list` | List async jobs for this org |
| `GET` | `/v1/jobs/{job_id}` | Poll job status |
| `POST` | `/v1/jobs/{job_id}/cancel` | Cancel a job (idempotent) |
| `GET` | `/v1/jobs/{job_id}/result` | Fetch job result |
| `POST` | `/v1/webhooks/test` | Test webhook delivery |

## Auth

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/auth/forgot-password` | Request a password reset email |
| `POST` | `/auth/login` | Login and get a session token |
| `POST` | `/auth/reset-password` | Complete password reset with token |
| `POST` | `/auth/signup` | Create a new account |
| `GET` | `/auth/verify` | Verify email address via token link |
| `POST` | `/v1/auth/forgot-password` | Request a password reset email |
| `POST` | `/v1/auth/login` | Login and get a session token |
| `POST` | `/v1/auth/reset-password` | Complete password reset with token |
| `POST` | `/v1/auth/signup` | Create a new account |
| `GET` | `/v1/auth/verify` | Verify email address via token link |

## BYOK

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/byok` | List the caller's configured per-org BYOK backends (website / Supabase-authenticated; no key material) |
| `POST` | `/byok` | Set the caller's per-org BYOK key (website / Supabase-authenticated; write-only) |
| `DELETE` | `/byok` | Remove the caller's per-org BYOK key (idempotent) |
| `GET` | `/v1/byok` | List the caller's configured per-org BYOK backends (website / Supabase-authenticated; no key material) |
| `POST` | `/v1/byok` | Set the caller's per-org BYOK key (website / Supabase-authenticated; write-only) |
| `DELETE` | `/v1/byok` | Remove the caller's per-org BYOK key (idempotent) |

## Billing

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/billing/plans` | Public — active plans for an app, dynamic from Stripe |
| `POST` | `/v1/billing/checkout` | Create Stripe Checkout session |
| `GET` | `/v1/billing/info` | Get current billing info |
| `GET` | `/v1/billing/plans` | Public — active plans for an app, dynamic from Stripe |
| `POST` | `/v1/billing/portal` | Create Stripe Billing Portal session |

## Calibration

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/calibration` | Get confidence calibration status |

## Capability Plane

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/capabilities` | List unified capabilities |
| `POST` | `/v1/capabilities/execute` | Execute one unified capability |
| `POST` | `/v1/capabilities/outcomes` | Record one capability outcome |
| `POST` | `/v1/capabilities/route` | Route an objective to one unified capability |
| `GET` | `/v1/capabilities/{capability_id}` | Get one unified capability |
| `GET` | `/v1/capability-bindings` | List capability bindings |
| `POST` | `/v1/capability-bindings` | Create a capability binding |
| `POST` | `/v1/capability-bindings/discover` | Preview-discover capabilities for an unsaved binding |
| `POST` | `/v1/capability-bindings/test` | Preview-test an unsaved capability binding |
| `GET` | `/v1/capability-bindings/{binding_id}` | Get one capability binding |
| `PATCH` | `/v1/capability-bindings/{binding_id}` | Update one capability binding |
| `DELETE` | `/v1/capability-bindings/{binding_id}` | Delete one capability binding (idempotent) |
| `POST` | `/v1/capability-bindings/{binding_id}/authorize/complete` | Complete capability-binding authorization |
| `POST` | `/v1/capability-bindings/{binding_id}/authorize/start` | Start capability-binding authorization |
| `POST` | `/v1/capability-bindings/{binding_id}/discover` | Discover capabilities for a saved binding |
| `POST` | `/v1/capability-bindings/{binding_id}/test` | Test a saved capability binding |
| `POST` | `/v1/capability-executions/{plan_id}/approve` | Approve a proposed capability execution plan |
| `GET` | `/v1/capability-providers` | List unified capability providers |
| `GET` | `/v1/capability-providers/{provider_id}` | Get one unified capability provider |

## Data

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/data` | List visible datasets for the caller. |
| `POST` | `/v1/data/connect` | Connect data, pick a dataset, and make it queryable. |
| `GET` | `/v1/data/{dataset_id}` | Get one dataset plus its schema. |
| `DELETE` | `/v1/data/{dataset_id}` | Disconnect data by deleting the dataset. |
| `POST` | `/v1/data/{dataset_id}/refresh` | Refresh a dataset from its saved origin. |
| `GET` | `/v1/data/{dataset_id}/summary` | Get low-token discovery summary for one dataset. |

## Data Connectors

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/connectors` | List data connectors |
| `POST` | `/v1/connectors` | Create a data connector with credentials |
| `POST` | `/v1/connectors/browse` | Browse an inline connector preview without saving it |
| `POST` | `/v1/connectors/test` | Test an inline connector preview without saving it |
| `GET` | `/v1/connectors/types` | List supported connector types |
| `GET` | `/v1/connectors/{connector_id}` | Get one data connector |
| `PATCH` | `/v1/connectors/{connector_id}` | Update connector name or config |
| `DELETE` | `/v1/connectors/{connector_id}` | Delete a data connector (idempotent) |
| `GET` | `/v1/connectors/{connector_id}/browse` | Browse connector schema — list tables, files, or datasets |
| `POST` | `/v1/connectors/{connector_id}/test` | Test connector — real connection attempt |

## Data Mapping

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/map` | Instantly map any dataset — no schema, no ETL |
| `GET` | `/v1/map/{map_id}` | Poll for deep analysis (join keys + derived relationships) |

## Datasets

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/datasets` | List all datasets registered for this org |
| `POST` | `/v1/datasets/onboard` | Onboard a dataset — zero-config schema profiling + auto-training |
| `POST` | `/v1/datasets/onboard/file` | Onboard from file upload — CSV, Excel, Parquet, JSON, JSONL |
| `POST` | `/v1/datasets/{dataset_id}/retrain` | Re-trigger semantic training for a dataset |
| `GET` | `/v1/datasets/{dataset_id}/status` | Live status and model tier for a dataset |

## Decision

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/batch` | Run multiple simulations in one request |
| `POST` | `/v1/compare` | Side-by-side scenario comparison |
| `POST` | `/v1/recommend` | Compare actions and get a recommendation |
| `POST` | `/v1/score` | Score a simulation with custom weights |

## Decision Memory

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/decisions` | Log a decision |
| `GET` | `/v1/decisions` | List logged decisions |
| `POST` | `/v1/decisions/plan` | Generate a structured decision plan |
| `GET` | `/v1/decisions/{decision_id}` | Get a single decision |
| `DELETE` | `/v1/decisions/{decision_id}` | Delete a decision log entry |
| `POST` | `/v1/decisions/{decision_id}/execute` | Execute a decision via webhook |
| `PATCH` | `/v1/decisions/{decision_id}/outcome` | Record actual outcome |

## Decision Workflow

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/analysis-runs/{run_id}` | Poll an analysis run |
| `POST` | `/v1/analysis-runs/{run_id}/action-plans` | Propose a safe execution plan (returns the plan_hash + single-use approval nonce) |
| `GET` | `/v1/analysis-runs/{run_id}/evidence` | Inspect evidence + provenance (what was accessed, under which retention mode) |
| `GET` | `/v1/analysis-runs/{run_id}/result` | Fetch the analysis result (host-independent object) |
| `POST` | `/v1/decision-cases` | Frame a decision (create a case + immutable revision 1) |
| `PUT` | `/v1/decision-cases/{case_id}` | Re-frame a decision (material change → new immutable revision) |
| `GET` | `/v1/decision-cases/{case_id}` | Get a decision case |
| `POST` | `/v1/decision-cases/{case_id}/analysis-runs` | Run the governed analysis (async: poll for the result) |
| `POST` | `/v1/decision-cases/{case_id}/outcomes` | Record what actually happened (closes the learning loop) |
| `POST` | `/v1/decision-cases/{case_id}/refresh` | Manually refresh: re-run the current revision with fresh evidence |
| `POST` | `/v1/decision-plans/{plan_id}/approve` | Approve a proposed plan (separately authenticated; plan_hash + single-use nonce) |
| `POST` | `/v1/decision-plans/{plan_id}/execute` | Execute an APPROVED plan (safe MVP actions only) |

## Deployments

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/deployments` | Get current org deployment |
| `POST` | `/v1/deployments` | Request a new cloud deployment |
| `GET` | `/v1/deployments/regions` | List available cloud providers and regions |
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
| `GET` | `/v1/execution/policy/snapshots` | List execution policy snapshots |

## Export

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/runs/{run_id}/export.{fmt}` | Export simulation run results |

## Infrastructure

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/infrastructure` | Real compute infrastructure health |
| `POST` | `/v1/nodes/heartbeat` | Worker node heartbeat |
| `POST` | `/v1/nodes/register` | Register a self-hosted compute node |
| `DELETE` | `/v1/nodes/{node_id}` | Deregister a node |

## Ingest

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/ingest` | Instant data ingestion — zero-config simulation from any table |

## LLM API

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/artifacts/resolve` | Resolve a Hugging Face artifact through the Algenta artifact bridge |
| `POST` | `/v1/chat/completions` | Run deterministic utility chat completion |
| `POST` | `/v1/count_tokens` | Count tokens with a supported Algenta tokenizer model |
| `POST` | `/v1/embeddings` | Generate embeddings from text |
| `POST` | `/v1/embeddings/similarity` | Score similarity between two embedding vectors |
| `GET` | `/v1/models` | List currently supported LLM utility models |
| `POST` | `/v1/rerank` | Rerank caller-supplied document embeddings |
| `POST` | `/v1/responses` | Run the unified model response envelope |
| `POST` | `/v1/tokenize` | Tokenize text with a supported Algenta tokenizer model |

## Logs

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/logs` | Stream structured logs via Server-Sent Events |

## Playground

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/playground` | Try Algenta — no API key required |

## Products

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/agent/run` | Run an AI agent task |
| `POST` | `/v1/decision` | Get an optimal decision |
| `POST` | `/v1/forecast` | Forecast a business metric |
| `POST` | `/v1/optimize` | Optimize a business variable |
| `POST` | `/v1/retrieve` | Search a knowledge base |

## Registry

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/registry/credentials` | Exchange a device-login token for read-only registry credentials (installer) |

## Repository Intelligence

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/repositories/capabilities` | List repository intelligence language support and progress |
| `POST` | `/v1/repositories/{repository_id}/apply` | Apply a simulated repository decision through patch, local branch, or remote PR |
| `POST` | `/v1/repositories/{repository_id}/decision-plans` | Create one stored immutable repository decision plan revision |
| `POST` | `/v1/repositories/{repository_id}/graph-query` | Query repository dependency and blast-radius graph from one persisted snapshot |
| `POST` | `/v1/repositories/{repository_id}/pipeline` | Run snapshot->triage->plan->simulate in one call (AR-OPT-9, flag-gated) |
| `POST` | `/v1/repositories/{repository_id}/security-analyses` | Prove reachability for a batch of scanner findings (snapshot-cached) |
| `POST` | `/v1/repositories/{repository_id}/security-analyses/closure` | Re-prove that a patch closes the original finding obligation |
| `POST` | `/v1/repositories/{repository_id}/simulate` | Simulate repository patch risk and populate the decision envelope gate |
| `POST` | `/v1/repositories/{repository_id}/simulate-patch` | Simulate an in-flight working-tree patch (no stored decision plan) |
| `POST` | `/v1/repositories/{repository_id}/snapshots` | Create or reuse an immutable repository snapshot |
| `GET` | `/v1/repositories/{repository_id}/snapshots/{snapshot_id}` | Get one immutable repository snapshot |
| `POST` | `/v1/repositories/{repository_id}/triage` | Triage a repository snapshot into a bounded workspace evidence bundle |

## Runs

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/analytics` | Aggregated analytics for dashboard charts |
| `GET` | `/v1/runs` | List simulation runs for this org |
| `GET` | `/v1/runs/{run_id}` | Get a single simulation run |

## Runtime Libraries

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/libraries` | List executable runtime libraries |
| `POST` | `/v1/libraries/execute` | Execute one runtime library function |
| `GET` | `/v1/libraries/health` | Check runtime library availability |

## Semantic Query

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/query` | Execute a structured query — schema-free, zero domain assumptions |
| `POST` | `/v1/query/batch` | Execute multiple governed exact queries in one request |
| `POST` | `/v1/query/sql-report` | Execute a constrained read-only SQL report over authorized datasets |
| `POST` | `/v1/resolve` | Resolve structured intent into an exact executable plan |
| `POST` | `/v1/sources/schema` | Infer and return the structural schema of data sources |
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
| `GET` | `/v1/sources` | List all registered sources for this org |
| `GET` | `/v1/sources/graph` | Connection graph — all detected join paths between registered sources |
| `POST` | `/v1/sources/register` | Register a data source — profile, index, detect joins to all existing sources |
| `GET` | `/v1/sources/{source_id}` | Get schema for a registered source |
| `DELETE` | `/v1/sources/{source_id}` | Remove a registered source |

## Streaming

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/simulate/stream` | Streaming simulation via Server-Sent Events |

## System

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/admin/egress-log` | Admin privacy egress log |
| `GET` | `/v1/admin/egress-policy` | Admin privacy egress policy |
| `GET` | `/v1/admin/privacy-report` | Admin privacy report |
| `GET` | `/v1/admin/runtime/benchmarks` | Admin runtime benchmark catalog |
| `GET` | `/v1/admin/runtime/modules` | Admin runtime module catalog |
| `GET` | `/v1/admin/runtime/validation` | Admin runtime release validation |
| `GET` | `/v1/health` | Health check |
| `GET` | `/v1/meta/contract` | Machine-readable Algenta contract |
| `GET` | `/v1/runtime/library-stats` | Runtime library contract counts |
| `GET` | `/v1/runtime/manifest` | Signed runtime manifest |
| `GET` | `/v1/version` | API and engine version |

## Team

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/v1/audit-logs` | Paginated audit log from DB |
| `GET` | `/v1/audit-logs/artifacts` | Paginated audit log artifacts from Parquet runtime storage |
| `GET` | `/v1/audit-logs/export.{fmt}` | Export the audit log (csv \| json) with a verifiable content hash |
| `GET` | `/v1/team` | List team members |
| `POST` | `/v1/team/accept` | Accept a team invitation |
| `POST` | `/v1/team/invite` | Invite a team member |
| `DELETE` | `/v1/team/{user_id}` | Remove a team member (idempotent) |
| `PATCH` | `/v1/team/{user_id}/role` | Update a team member's role |

## Triggers

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/triggers` | Register a trigger |
| `GET` | `/v1/triggers` | List all triggers |
| `DELETE` | `/v1/triggers/{trigger_id}` | Delete a trigger (idempotent) |
| `POST` | `/v1/triggers/{trigger_id}/fire` | Fire a trigger |
| `PATCH` | `/v1/triggers/{trigger_id}/pause` | Pause or resume a trigger |

## What-If Analysis

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/simulate/what-if` | What-if parametric sweep |

## account

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/account/billing` | Current plan + managed-LLM usage for the signed-in user (website / Supabase auth) |
| `POST` | `/account/billing/checkout` | Start Stripe Checkout for a plan upgrade (website / Supabase auth) |
| `POST` | `/account/billing/portal` | Open the Stripe Customer Portal (website / Supabase auth) |
| `GET` | `/account/devices` | List the signed-in user's devices + seat usage (website / Supabase auth) |
| `DELETE` | `/account/devices/{registration_id}` | Revoke one of the signed-in user's devices (frees a seat) |
| `GET` | `/account/orgs` | List every org the caller may act in (for the org picker) |
| `GET` | `/account/team` | List team members + seat usage (website / Supabase auth) |
| `POST` | `/account/team/invite` | Invite a team member (website / Supabase auth) |
| `DELETE` | `/account/team/{user_id}` | Remove a member (website / Supabase auth) |
| `PATCH` | `/account/team/{user_id}/role` | Change a member's role (website / Supabase auth) |
| `GET` | `/account/usage` | Current-period GitHub fixes used vs plan allowance (website / Supabase auth) |
| `GET` | `/v1/account/billing` | Current plan + managed-LLM usage for the signed-in user (website / Supabase auth) |
| `POST` | `/v1/account/billing/checkout` | Start Stripe Checkout for a plan upgrade (website / Supabase auth) |
| `POST` | `/v1/account/billing/portal` | Open the Stripe Customer Portal (website / Supabase auth) |
| `GET` | `/v1/account/devices` | List the signed-in user's devices + seat usage (website / Supabase auth) |
| `DELETE` | `/v1/account/devices/{registration_id}` | Revoke one of the signed-in user's devices (frees a seat) |
| `GET` | `/v1/account/orgs` | List every org the caller may act in (for the org picker) |
| `GET` | `/v1/account/team` | List team members + seat usage (website / Supabase auth) |
| `POST` | `/v1/account/team/invite` | Invite a team member (website / Supabase auth) |
| `DELETE` | `/v1/account/team/{user_id}` | Remove a member (website / Supabase auth) |
| `PATCH` | `/v1/account/team/{user_id}/role` | Change a member's role (website / Supabase auth) |
| `GET` | `/v1/account/usage` | Current-period GitHub fixes used vs plan allowance (website / Supabase auth) |

## credits

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/credits/refresh` | Issue a compatibility credit batch for a managed runtime |

## deployment

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/deployment/activate` | Activate an organization server deployment and mint its Compute-Unit license |
| `POST` | `/v1/deployment/node/challenge` | Issue a single-use nonce for deployment-node proof-of-possession |
| `POST` | `/v1/deployment/node/heartbeat` | L3 connected-pool: admit/renew an engine node's Compute-Unit lease against the pool |

## devices

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/device/heartbeat` | 24-hour device heartbeat — updates last_seen and returns device count |
| `GET` | `/v1/device/list` | List all registered devices for this org |
| `POST` | `/v1/device/register` | Register a device and receive a signed license token |
| `DELETE` | `/v1/device/{registration_id}` | Revoke a registered device |
| `GET` | `/v1/runtime/authorize` | Authorize a runtime bundle download for the calling API key |

## license

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/license/challenge` | Begin renewal proof-of-possession — receive a single-use nonce to sign |
| `POST` | `/v1/license/renew` | Renew a device license by proving possession of the bound device key |

## metering

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/v1/metering` | Ingest managed-deployment execution analytics |

## oauth-device

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/oauth/device/approve` | Device Approve |
| `POST` | `/oauth/device/code` | Device Code |
| `GET` | `/oauth/device/grant` | Device Grant Lookup |
| `POST` | `/oauth/device/token` | Device Token |
| `POST` | `/v1/oauth/device/approve` | Device Approve |
| `POST` | `/v1/oauth/device/code` | Device Code |
| `GET` | `/v1/oauth/device/grant` | Device Grant Lookup |
| `POST` | `/v1/oauth/device/token` | Device Token |
