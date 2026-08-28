---
icon: circle-play
description: Try the Algenta HTTP API live — set your key and base URL, then send real requests to every endpoint from the browser.
---

# API explorer

Every endpoint below renders live from the Algenta OpenAPI specification. Expand an operation to see parameters, request and response schemas, and example payloads, then use **Test it** to call the API directly from this page with your own key.

{% hint style="info" %}
Generated from the canonical OpenAPI spec, so it always matches the deployed engine. Set your base URL (your self-hosted deployment or `https://api.algenta.ai`) and API key in the **Test it** panel. For a flat index see the [endpoint reference](reference.md); for prose, the [API overview](overview.md).
{% endhint %}

## Account

### `GET /v1/me`

{% openapi-operation spec="algenta-api" path="/v1/me" method="get" %}
{% endopenapi-operation %}

### `PATCH /v1/me`

{% openapi-operation spec="algenta-api" path="/v1/me" method="patch" %}
{% endopenapi-operation %}

### `GET /v1/usage`

{% openapi-operation spec="algenta-api" path="/v1/usage" method="get" %}
{% endopenapi-operation %}

### `GET /v1/limits`

{% openapi-operation spec="algenta-api" path="/v1/limits" method="get" %}
{% endopenapi-operation %}

### `GET /v1/distributions`

{% openapi-operation spec="algenta-api" path="/v1/distributions" method="get" %}
{% endopenapi-operation %}

### `GET /v1/templates`

{% openapi-operation spec="algenta-api" path="/v1/templates" method="get" %}
{% endopenapi-operation %}

### `GET /v1/api-keys`

{% openapi-operation spec="algenta-api" path="/v1/api-keys" method="get" %}
{% endopenapi-operation %}

### `POST /v1/api-keys`

{% openapi-operation spec="algenta-api" path="/v1/api-keys" method="post" %}
{% endopenapi-operation %}

### `POST /v1/products/{product}/onboard`

{% openapi-operation spec="algenta-api" path="/v1/products/{product}/onboard" method="post" %}
{% endopenapi-operation %}

### `POST /v1/telys/onboard`

{% openapi-operation spec="algenta-api" path="/v1/telys/onboard" method="post" %}
{% endopenapi-operation %}

### `GET /v1/products/{product}/whoami`

{% openapi-operation spec="algenta-api" path="/v1/products/{product}/whoami" method="get" %}
{% endopenapi-operation %}

### `DELETE /v1/api-keys/{key_id}`

{% openapi-operation spec="algenta-api" path="/v1/api-keys/{key_id}" method="delete" %}
{% endopenapi-operation %}

### `GET /v1/provider-keys`

{% openapi-operation spec="algenta-api" path="/v1/provider-keys" method="get" %}
{% endopenapi-operation %}

### `POST /v1/provider-keys`

{% openapi-operation spec="algenta-api" path="/v1/provider-keys" method="post" %}
{% endopenapi-operation %}

### `DELETE /v1/provider-keys/{backend}`

{% openapi-operation spec="algenta-api" path="/v1/provider-keys/{backend}" method="delete" %}
{% endopenapi-operation %}

## Agent Runtime

### `POST /v1/agent/runs`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs" method="post" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/checkpoints`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/checkpoints" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/mission-events`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/mission-events" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/telemetry`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/telemetry" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/{run_id}`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/{run_id}/events`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/events" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/{run_id}/mission-events`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/mission-events" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/{run_id}/checkpoints`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/checkpoints" method="get" %}
{% endopenapi-operation %}

### `GET /v1/agent/runs/{run_id}/telemetry`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/telemetry" method="get" %}
{% endopenapi-operation %}

### `POST /v1/agent/runs/{run_id}/replay`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/replay" method="post" %}
{% endopenapi-operation %}

### `POST /v1/agent/runs/{run_id}/fork`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/fork" method="post" %}
{% endopenapi-operation %}

### `POST /v1/agent/runs/{run_id}/resume`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/resume" method="post" %}
{% endopenapi-operation %}

### `POST /v1/agent/runs/{run_id}/cancel`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/cancel" method="post" %}
{% endopenapi-operation %}

### `POST /v1/agent/runs/{run_id}/approve`

{% openapi-operation spec="algenta-api" path="/v1/agent/runs/{run_id}/approve" method="post" %}
{% endopenapi-operation %}

## Async Jobs

### `GET /v1/jobs/list`

{% openapi-operation spec="algenta-api" path="/v1/jobs/list" method="get" %}
{% endopenapi-operation %}

### `POST /v1/jobs`

{% openapi-operation spec="algenta-api" path="/v1/jobs" method="post" %}
{% endopenapi-operation %}

### `GET /v1/jobs/{job_id}`

{% openapi-operation spec="algenta-api" path="/v1/jobs/{job_id}" method="get" %}
{% endopenapi-operation %}

### `GET /v1/jobs/{job_id}/result`

{% openapi-operation spec="algenta-api" path="/v1/jobs/{job_id}/result" method="get" %}
{% endopenapi-operation %}

### `POST /v1/jobs/{job_id}/cancel`

{% openapi-operation spec="algenta-api" path="/v1/jobs/{job_id}/cancel" method="post" %}
{% endopenapi-operation %}

### `POST /v1/webhooks/test`

{% openapi-operation spec="algenta-api" path="/v1/webhooks/test" method="post" %}
{% endopenapi-operation %}

## Auth

### `POST /auth/signup`

{% openapi-operation spec="algenta-api" path="/auth/signup" method="post" %}
{% endopenapi-operation %}

### `POST /auth/login`

{% openapi-operation spec="algenta-api" path="/auth/login" method="post" %}
{% endopenapi-operation %}

### `GET /auth/verify`

{% openapi-operation spec="algenta-api" path="/auth/verify" method="get" %}
{% endopenapi-operation %}

### `POST /auth/forgot-password`

{% openapi-operation spec="algenta-api" path="/auth/forgot-password" method="post" %}
{% endopenapi-operation %}

### `POST /auth/reset-password`

{% openapi-operation spec="algenta-api" path="/auth/reset-password" method="post" %}
{% endopenapi-operation %}

## BYOK

### `GET /byok`

{% openapi-operation spec="algenta-api" path="/byok" method="get" %}
{% endopenapi-operation %}

### `POST /byok`

{% openapi-operation spec="algenta-api" path="/byok" method="post" %}
{% endopenapi-operation %}

### `DELETE /byok`

{% openapi-operation spec="algenta-api" path="/byok" method="delete" %}
{% endopenapi-operation %}

## Billing

### `GET /billing/plans`

{% openapi-operation spec="algenta-api" path="/billing/plans" method="get" %}
{% endopenapi-operation %}

### `POST /v1/billing/checkout`

{% openapi-operation spec="algenta-api" path="/v1/billing/checkout" method="post" %}
{% endopenapi-operation %}

### `POST /v1/billing/portal`

{% openapi-operation spec="algenta-api" path="/v1/billing/portal" method="post" %}
{% endopenapi-operation %}

### `GET /v1/billing/info`

{% openapi-operation spec="algenta-api" path="/v1/billing/info" method="get" %}
{% endopenapi-operation %}

## Calibration

### `GET /v1/calibration`

{% openapi-operation spec="algenta-api" path="/v1/calibration" method="get" %}
{% endopenapi-operation %}

## Capability Plane

### `GET /v1/capability-providers`

{% openapi-operation spec="algenta-api" path="/v1/capability-providers" method="get" %}
{% endopenapi-operation %}

### `GET /v1/capability-providers/{provider_id}`

{% openapi-operation spec="algenta-api" path="/v1/capability-providers/{provider_id}" method="get" %}
{% endopenapi-operation %}

### `GET /v1/capability-bindings`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings" method="get" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings" method="post" %}
{% endopenapi-operation %}

### `GET /v1/capability-bindings/{binding_id}`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}" method="get" %}
{% endopenapi-operation %}

### `PATCH /v1/capability-bindings/{binding_id}`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}" method="patch" %}
{% endopenapi-operation %}

### `DELETE /v1/capability-bindings/{binding_id}`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}" method="delete" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings/test`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/test" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings/{binding_id}/test`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}/test" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings/discover`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/discover" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings/{binding_id}/discover`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}/discover" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings/{binding_id}/authorize/start`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}/authorize/start" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capability-bindings/{binding_id}/authorize/complete`

{% openapi-operation spec="algenta-api" path="/v1/capability-bindings/{binding_id}/authorize/complete" method="post" %}
{% endopenapi-operation %}

### `GET /v1/capabilities`

{% openapi-operation spec="algenta-api" path="/v1/capabilities" method="get" %}
{% endopenapi-operation %}

### `GET /v1/capabilities/{capability_id}`

{% openapi-operation spec="algenta-api" path="/v1/capabilities/{capability_id}" method="get" %}
{% endopenapi-operation %}

### `POST /v1/capabilities/route`

{% openapi-operation spec="algenta-api" path="/v1/capabilities/route" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capabilities/execute`

{% openapi-operation spec="algenta-api" path="/v1/capabilities/execute" method="post" %}
{% endopenapi-operation %}

### `POST /v1/capabilities/outcomes`

{% openapi-operation spec="algenta-api" path="/v1/capabilities/outcomes" method="post" %}
{% endopenapi-operation %}

## Data

### `POST /v1/data/connect`

{% openapi-operation spec="algenta-api" path="/v1/data/connect" method="post" %}
{% endopenapi-operation %}

### `GET /v1/data`

{% openapi-operation spec="algenta-api" path="/v1/data" method="get" %}
{% endopenapi-operation %}

### `GET /v1/data/{dataset_id}/summary`

{% openapi-operation spec="algenta-api" path="/v1/data/{dataset_id}/summary" method="get" %}
{% endopenapi-operation %}

### `GET /v1/data/{dataset_id}`

{% openapi-operation spec="algenta-api" path="/v1/data/{dataset_id}" method="get" %}
{% endopenapi-operation %}

### `DELETE /v1/data/{dataset_id}`

{% openapi-operation spec="algenta-api" path="/v1/data/{dataset_id}" method="delete" %}
{% endopenapi-operation %}

### `POST /v1/data/{dataset_id}/refresh`

{% openapi-operation spec="algenta-api" path="/v1/data/{dataset_id}/refresh" method="post" %}
{% endopenapi-operation %}

## Data Connectors

### `GET /v1/connectors`

{% openapi-operation spec="algenta-api" path="/v1/connectors" method="get" %}
{% endopenapi-operation %}

### `POST /v1/connectors`

{% openapi-operation spec="algenta-api" path="/v1/connectors" method="post" %}
{% endopenapi-operation %}

### `GET /v1/connectors/{connector_id}`

{% openapi-operation spec="algenta-api" path="/v1/connectors/{connector_id}" method="get" %}
{% endopenapi-operation %}

### `PATCH /v1/connectors/{connector_id}`

{% openapi-operation spec="algenta-api" path="/v1/connectors/{connector_id}" method="patch" %}
{% endopenapi-operation %}

### `DELETE /v1/connectors/{connector_id}`

{% openapi-operation spec="algenta-api" path="/v1/connectors/{connector_id}" method="delete" %}
{% endopenapi-operation %}

### `GET /v1/connectors/types`

{% openapi-operation spec="algenta-api" path="/v1/connectors/types" method="get" %}
{% endopenapi-operation %}

### `POST /v1/connectors/{connector_id}/test`

{% openapi-operation spec="algenta-api" path="/v1/connectors/{connector_id}/test" method="post" %}
{% endopenapi-operation %}

### `POST /v1/connectors/test`

{% openapi-operation spec="algenta-api" path="/v1/connectors/test" method="post" %}
{% endopenapi-operation %}

### `GET /v1/connectors/{connector_id}/browse`

{% openapi-operation spec="algenta-api" path="/v1/connectors/{connector_id}/browse" method="get" %}
{% endopenapi-operation %}

### `POST /v1/connectors/browse`

{% openapi-operation spec="algenta-api" path="/v1/connectors/browse" method="post" %}
{% endopenapi-operation %}

## Data Mapping

### `GET /v1/map/{map_id}`

{% openapi-operation spec="algenta-api" path="/v1/map/{map_id}" method="get" %}
{% endopenapi-operation %}

### `POST /v1/map`

{% openapi-operation spec="algenta-api" path="/v1/map" method="post" %}
{% endopenapi-operation %}

## Datasets

### `POST /v1/datasets/onboard`

{% openapi-operation spec="algenta-api" path="/v1/datasets/onboard" method="post" %}
{% endopenapi-operation %}

### `POST /v1/datasets/onboard/file`

{% openapi-operation spec="algenta-api" path="/v1/datasets/onboard/file" method="post" %}
{% endopenapi-operation %}

### `GET /v1/datasets/{dataset_id}/status`

{% openapi-operation spec="algenta-api" path="/v1/datasets/{dataset_id}/status" method="get" %}
{% endopenapi-operation %}

### `GET /v1/datasets`

{% openapi-operation spec="algenta-api" path="/v1/datasets" method="get" %}
{% endopenapi-operation %}

### `POST /v1/datasets/{dataset_id}/retrain`

{% openapi-operation spec="algenta-api" path="/v1/datasets/{dataset_id}/retrain" method="post" %}
{% endopenapi-operation %}

## Decision

### `POST /v1/recommend`

{% openapi-operation spec="algenta-api" path="/v1/recommend" method="post" %}
{% endopenapi-operation %}

### `POST /v1/score`

{% openapi-operation spec="algenta-api" path="/v1/score" method="post" %}
{% endopenapi-operation %}

### `POST /v1/batch`

{% openapi-operation spec="algenta-api" path="/v1/batch" method="post" %}
{% endopenapi-operation %}

### `POST /v1/compare`

{% openapi-operation spec="algenta-api" path="/v1/compare" method="post" %}
{% endopenapi-operation %}

## Decision Memory

### `POST /v1/decisions/plan`

{% openapi-operation spec="algenta-api" path="/v1/decisions/plan" method="post" %}
{% endopenapi-operation %}

### `POST /v1/decisions`

{% openapi-operation spec="algenta-api" path="/v1/decisions" method="post" %}
{% endopenapi-operation %}

### `GET /v1/decisions`

{% openapi-operation spec="algenta-api" path="/v1/decisions" method="get" %}
{% endopenapi-operation %}

### `GET /v1/decisions/{decision_id}`

{% openapi-operation spec="algenta-api" path="/v1/decisions/{decision_id}" method="get" %}
{% endopenapi-operation %}

### `DELETE /v1/decisions/{decision_id}`

{% openapi-operation spec="algenta-api" path="/v1/decisions/{decision_id}" method="delete" %}
{% endopenapi-operation %}

### `PATCH /v1/decisions/{decision_id}/outcome`

{% openapi-operation spec="algenta-api" path="/v1/decisions/{decision_id}/outcome" method="patch" %}
{% endopenapi-operation %}

### `POST /v1/decisions/{decision_id}/execute`

{% openapi-operation spec="algenta-api" path="/v1/decisions/{decision_id}/execute" method="post" %}
{% endopenapi-operation %}

## Decision Workflow

### `POST /v1/decision-cases`

{% openapi-operation spec="algenta-api" path="/v1/decision-cases" method="post" %}
{% endopenapi-operation %}

### `PUT /v1/decision-cases/{case_id}`

{% openapi-operation spec="algenta-api" path="/v1/decision-cases/{case_id}" method="put" %}
{% endopenapi-operation %}

### `GET /v1/decision-cases/{case_id}`

{% openapi-operation spec="algenta-api" path="/v1/decision-cases/{case_id}" method="get" %}
{% endopenapi-operation %}

### `POST /v1/decision-cases/{case_id}/analysis-runs`

{% openapi-operation spec="algenta-api" path="/v1/decision-cases/{case_id}/analysis-runs" method="post" %}
{% endopenapi-operation %}

### `POST /v1/decision-cases/{case_id}/refresh`

{% openapi-operation spec="algenta-api" path="/v1/decision-cases/{case_id}/refresh" method="post" %}
{% endopenapi-operation %}

### `GET /v1/analysis-runs/{run_id}`

{% openapi-operation spec="algenta-api" path="/v1/analysis-runs/{run_id}" method="get" %}
{% endopenapi-operation %}

### `GET /v1/analysis-runs/{run_id}/result`

{% openapi-operation spec="algenta-api" path="/v1/analysis-runs/{run_id}/result" method="get" %}
{% endopenapi-operation %}

### `GET /v1/analysis-runs/{run_id}/evidence`

{% openapi-operation spec="algenta-api" path="/v1/analysis-runs/{run_id}/evidence" method="get" %}
{% endopenapi-operation %}

### `POST /v1/analysis-runs/{run_id}/action-plans`

{% openapi-operation spec="algenta-api" path="/v1/analysis-runs/{run_id}/action-plans" method="post" %}
{% endopenapi-operation %}

### `POST /v1/decision-plans/{plan_id}/approve`

{% openapi-operation spec="algenta-api" path="/v1/decision-plans/{plan_id}/approve" method="post" %}
{% endopenapi-operation %}

### `POST /v1/decision-plans/{plan_id}/execute`

{% openapi-operation spec="algenta-api" path="/v1/decision-plans/{plan_id}/execute" method="post" %}
{% endopenapi-operation %}

### `POST /v1/decision-cases/{case_id}/outcomes`

{% openapi-operation spec="algenta-api" path="/v1/decision-cases/{case_id}/outcomes" method="post" %}
{% endopenapi-operation %}

## Deployments

### `GET /v1/deployments/regions`

{% openapi-operation spec="algenta-api" path="/v1/deployments/regions" method="get" %}
{% endopenapi-operation %}

### `GET /v1/deployments`

{% openapi-operation spec="algenta-api" path="/v1/deployments" method="get" %}
{% endopenapi-operation %}

### `POST /v1/deployments`

{% openapi-operation spec="algenta-api" path="/v1/deployments" method="post" %}
{% endopenapi-operation %}

### `DELETE /v1/deployments/{deployment_id}`

{% openapi-operation spec="algenta-api" path="/v1/deployments/{deployment_id}" method="delete" %}
{% endopenapi-operation %}

### `GET /v1/deployments/{deployment_id}/cost`

{% openapi-operation spec="algenta-api" path="/v1/deployments/{deployment_id}/cost" method="get" %}
{% endopenapi-operation %}

## Engines

### `GET /v1/engines`

{% openapi-operation spec="algenta-api" path="/v1/engines" method="get" %}
{% endopenapi-operation %}

### `GET /v1/engines/tiers`

{% openapi-operation spec="algenta-api" path="/v1/engines/tiers" method="get" %}
{% endopenapi-operation %}

### `GET /v1/engines/{slug}`

{% openapi-operation spec="algenta-api" path="/v1/engines/{slug}" method="get" %}
{% endopenapi-operation %}

## Execution Policy

### `GET /v1/execution/policy`

{% openapi-operation spec="algenta-api" path="/v1/execution/policy" method="get" %}
{% endopenapi-operation %}

### `PATCH /v1/execution/policy`

{% openapi-operation spec="algenta-api" path="/v1/execution/policy" method="patch" %}
{% endopenapi-operation %}

### `GET /v1/execution/policy/snapshots`

{% openapi-operation spec="algenta-api" path="/v1/execution/policy/snapshots" method="get" %}
{% endopenapi-operation %}

## Export

### `GET /v1/runs/{run_id}/export.{fmt}`

{% openapi-operation spec="algenta-api" path="/v1/runs/{run_id}/export.{fmt}" method="get" %}
{% endopenapi-operation %}

## Infrastructure

### `GET /v1/infrastructure`

{% openapi-operation spec="algenta-api" path="/v1/infrastructure" method="get" %}
{% endopenapi-operation %}

### `POST /v1/nodes/register`

{% openapi-operation spec="algenta-api" path="/v1/nodes/register" method="post" %}
{% endopenapi-operation %}

### `POST /v1/nodes/heartbeat`

{% openapi-operation spec="algenta-api" path="/v1/nodes/heartbeat" method="post" %}
{% endopenapi-operation %}

### `DELETE /v1/nodes/{node_id}`

{% openapi-operation spec="algenta-api" path="/v1/nodes/{node_id}" method="delete" %}
{% endopenapi-operation %}

## Ingest

### `POST /v1/ingest`

{% openapi-operation spec="algenta-api" path="/v1/ingest" method="post" %}
{% endopenapi-operation %}

## LLM API

### `GET /v1/models`

{% openapi-operation spec="algenta-api" path="/v1/models" method="get" %}
{% endopenapi-operation %}

### `POST /v1/artifacts/resolve`

{% openapi-operation spec="algenta-api" path="/v1/artifacts/resolve" method="post" %}
{% endopenapi-operation %}

### `POST /v1/chat/completions`

{% openapi-operation spec="algenta-api" path="/v1/chat/completions" method="post" %}
{% endopenapi-operation %}

### `POST /v1/tokenize`

{% openapi-operation spec="algenta-api" path="/v1/tokenize" method="post" %}
{% endopenapi-operation %}

### `POST /v1/count_tokens`

{% openapi-operation spec="algenta-api" path="/v1/count_tokens" method="post" %}
{% endopenapi-operation %}

### `POST /v1/responses`

{% openapi-operation spec="algenta-api" path="/v1/responses" method="post" %}
{% endopenapi-operation %}

### `POST /v1/embeddings`

{% openapi-operation spec="algenta-api" path="/v1/embeddings" method="post" %}
{% endopenapi-operation %}

### `POST /v1/embeddings/similarity`

{% openapi-operation spec="algenta-api" path="/v1/embeddings/similarity" method="post" %}
{% endopenapi-operation %}

### `POST /v1/rerank`

{% openapi-operation spec="algenta-api" path="/v1/rerank" method="post" %}
{% endopenapi-operation %}

## Logs

### `GET /v1/logs`

{% openapi-operation spec="algenta-api" path="/v1/logs" method="get" %}
{% endopenapi-operation %}

## Playground

### `POST /v1/playground`

{% openapi-operation spec="algenta-api" path="/v1/playground" method="post" %}
{% endopenapi-operation %}

## Products

### `POST /v1/decision`

{% openapi-operation spec="algenta-api" path="/v1/decision" method="post" %}
{% endopenapi-operation %}

### `POST /v1/agent/run`

{% openapi-operation spec="algenta-api" path="/v1/agent/run" method="post" %}
{% endopenapi-operation %}

### `POST /v1/optimize`

{% openapi-operation spec="algenta-api" path="/v1/optimize" method="post" %}
{% endopenapi-operation %}

### `POST /v1/retrieve`

{% openapi-operation spec="algenta-api" path="/v1/retrieve" method="post" %}
{% endopenapi-operation %}

### `POST /v1/forecast`

{% openapi-operation spec="algenta-api" path="/v1/forecast" method="post" %}
{% endopenapi-operation %}

## Registry

### `POST /v1/registry/credentials`

{% openapi-operation spec="algenta-api" path="/v1/registry/credentials" method="post" %}
{% endopenapi-operation %}

## Repository Intelligence

### `GET /v1/repositories/capabilities`

{% openapi-operation spec="algenta-api" path="/v1/repositories/capabilities" method="get" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/snapshots`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/snapshots" method="post" %}
{% endopenapi-operation %}

### `GET /v1/repositories/{repository_id}/snapshots/{snapshot_id}`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/snapshots/{snapshot_id}" method="get" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/triage`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/triage" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/graph-query`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/graph-query" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/security-analyses`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/security-analyses" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/security-analyses/closure`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/security-analyses/closure" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/decision-plans`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/decision-plans" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/simulate`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/simulate" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/simulate-patch`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/simulate-patch" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/pipeline`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/pipeline" method="post" %}
{% endopenapi-operation %}

### `POST /v1/repositories/{repository_id}/apply`

{% openapi-operation spec="algenta-api" path="/v1/repositories/{repository_id}/apply" method="post" %}
{% endopenapi-operation %}

## Runs

### `GET /v1/runs`

{% openapi-operation spec="algenta-api" path="/v1/runs" method="get" %}
{% endopenapi-operation %}

### `GET /v1/runs/{run_id}`

{% openapi-operation spec="algenta-api" path="/v1/runs/{run_id}" method="get" %}
{% endopenapi-operation %}

### `GET /v1/analytics`

{% openapi-operation spec="algenta-api" path="/v1/analytics" method="get" %}
{% endopenapi-operation %}

## Runtime Libraries

### `GET /v1/libraries`

{% openapi-operation spec="algenta-api" path="/v1/libraries" method="get" %}
{% endopenapi-operation %}

### `GET /v1/libraries/health`

{% openapi-operation spec="algenta-api" path="/v1/libraries/health" method="get" %}
{% endopenapi-operation %}

### `POST /v1/libraries/execute`

{% openapi-operation spec="algenta-api" path="/v1/libraries/execute" method="post" %}
{% endopenapi-operation %}

## Semantic Query

### `POST /v1/resolve`

{% openapi-operation spec="algenta-api" path="/v1/resolve" method="post" %}
{% endopenapi-operation %}

### `POST /v1/query`

{% openapi-operation spec="algenta-api" path="/v1/query" method="post" %}
{% endopenapi-operation %}

### `POST /v1/sources/schema`

{% openapi-operation spec="algenta-api" path="/v1/sources/schema" method="post" %}
{% endopenapi-operation %}

### `POST /v1/query/batch`

{% openapi-operation spec="algenta-api" path="/v1/query/batch" method="post" %}
{% endopenapi-operation %}

### `POST /v1/query/sql-report`

{% openapi-operation spec="algenta-api" path="/v1/query/sql-report" method="post" %}
{% endopenapi-operation %}

### `POST /v1/verify`

{% openapi-operation spec="algenta-api" path="/v1/verify" method="post" %}
{% endopenapi-operation %}

## Simulation

### `POST /v1/simulate`

{% openapi-operation spec="algenta-api" path="/v1/simulate" method="post" %}
{% endopenapi-operation %}

### `GET /v1/simulate/templates`

{% openapi-operation spec="algenta-api" path="/v1/simulate/templates" method="get" %}
{% endopenapi-operation %}

### `GET /v1/simulate/templates/{template_id}`

{% openapi-operation spec="algenta-api" path="/v1/simulate/templates/{template_id}" method="get" %}
{% endopenapi-operation %}

### `POST /v1/templates/{template_id}/run`

{% openapi-operation spec="algenta-api" path="/v1/templates/{template_id}/run" method="post" %}
{% endopenapi-operation %}

## Source Registry

### `POST /v1/sources/register`

{% openapi-operation spec="algenta-api" path="/v1/sources/register" method="post" %}
{% endopenapi-operation %}

### `GET /v1/sources`

{% openapi-operation spec="algenta-api" path="/v1/sources" method="get" %}
{% endopenapi-operation %}

### `GET /v1/sources/graph`

{% openapi-operation spec="algenta-api" path="/v1/sources/graph" method="get" %}
{% endopenapi-operation %}

### `GET /v1/sources/{source_id}`

{% openapi-operation spec="algenta-api" path="/v1/sources/{source_id}" method="get" %}
{% endopenapi-operation %}

### `DELETE /v1/sources/{source_id}`

{% openapi-operation spec="algenta-api" path="/v1/sources/{source_id}" method="delete" %}
{% endopenapi-operation %}

## Streaming

### `POST /v1/simulate/stream`

{% openapi-operation spec="algenta-api" path="/v1/simulate/stream" method="post" %}
{% endopenapi-operation %}

## System

### `GET /v1/health`

{% openapi-operation spec="algenta-api" path="/v1/health" method="get" %}
{% endopenapi-operation %}

### `GET /v1/version`

{% openapi-operation spec="algenta-api" path="/v1/version" method="get" %}
{% endopenapi-operation %}

### `GET /v1/meta/contract`

{% openapi-operation spec="algenta-api" path="/v1/meta/contract" method="get" %}
{% endopenapi-operation %}

### `GET /v1/runtime/manifest`

{% openapi-operation spec="algenta-api" path="/v1/runtime/manifest" method="get" %}
{% endopenapi-operation %}

### `GET /v1/runtime/library-stats`

{% openapi-operation spec="algenta-api" path="/v1/runtime/library-stats" method="get" %}
{% endopenapi-operation %}

### `GET /v1/admin/runtime/modules`

{% openapi-operation spec="algenta-api" path="/v1/admin/runtime/modules" method="get" %}
{% endopenapi-operation %}

### `GET /v1/admin/runtime/benchmarks`

{% openapi-operation spec="algenta-api" path="/v1/admin/runtime/benchmarks" method="get" %}
{% endopenapi-operation %}

### `GET /v1/admin/runtime/validation`

{% openapi-operation spec="algenta-api" path="/v1/admin/runtime/validation" method="get" %}
{% endopenapi-operation %}

### `GET /v1/admin/egress-policy`

{% openapi-operation spec="algenta-api" path="/v1/admin/egress-policy" method="get" %}
{% endopenapi-operation %}

### `GET /v1/admin/egress-log`

{% openapi-operation spec="algenta-api" path="/v1/admin/egress-log" method="get" %}
{% endopenapi-operation %}

### `GET /v1/admin/privacy-report`

{% openapi-operation spec="algenta-api" path="/v1/admin/privacy-report" method="get" %}
{% endopenapi-operation %}

## Team

### `GET /v1/team`

{% openapi-operation spec="algenta-api" path="/v1/team" method="get" %}
{% endopenapi-operation %}

### `POST /v1/team/invite`

{% openapi-operation spec="algenta-api" path="/v1/team/invite" method="post" %}
{% endopenapi-operation %}

### `POST /v1/team/accept`

{% openapi-operation spec="algenta-api" path="/v1/team/accept" method="post" %}
{% endopenapi-operation %}

### `PATCH /v1/team/{user_id}/role`

{% openapi-operation spec="algenta-api" path="/v1/team/{user_id}/role" method="patch" %}
{% endopenapi-operation %}

### `DELETE /v1/team/{user_id}`

{% openapi-operation spec="algenta-api" path="/v1/team/{user_id}" method="delete" %}
{% endopenapi-operation %}

### `GET /v1/audit-logs`

{% openapi-operation spec="algenta-api" path="/v1/audit-logs" method="get" %}
{% endopenapi-operation %}

### `GET /v1/audit-logs/export.{fmt}`

{% openapi-operation spec="algenta-api" path="/v1/audit-logs/export.{fmt}" method="get" %}
{% endopenapi-operation %}

### `GET /v1/audit-logs/artifacts`

{% openapi-operation spec="algenta-api" path="/v1/audit-logs/artifacts" method="get" %}
{% endopenapi-operation %}

## Triggers

### `POST /v1/triggers`

{% openapi-operation spec="algenta-api" path="/v1/triggers" method="post" %}
{% endopenapi-operation %}

### `GET /v1/triggers`

{% openapi-operation spec="algenta-api" path="/v1/triggers" method="get" %}
{% endopenapi-operation %}

### `POST /v1/triggers/{trigger_id}/fire`

{% openapi-operation spec="algenta-api" path="/v1/triggers/{trigger_id}/fire" method="post" %}
{% endopenapi-operation %}

### `PATCH /v1/triggers/{trigger_id}/pause`

{% openapi-operation spec="algenta-api" path="/v1/triggers/{trigger_id}/pause" method="patch" %}
{% endopenapi-operation %}

### `DELETE /v1/triggers/{trigger_id}`

{% openapi-operation spec="algenta-api" path="/v1/triggers/{trigger_id}" method="delete" %}
{% endopenapi-operation %}

## What-If Analysis

### `POST /v1/simulate/what-if`

{% openapi-operation spec="algenta-api" path="/v1/simulate/what-if" method="post" %}
{% endopenapi-operation %}

## account

### `GET /account/devices`

{% openapi-operation spec="algenta-api" path="/account/devices" method="get" %}
{% endopenapi-operation %}

### `DELETE /account/devices/{registration_id}`

{% openapi-operation spec="algenta-api" path="/account/devices/{registration_id}" method="delete" %}
{% endopenapi-operation %}

### `GET /account/usage`

{% openapi-operation spec="algenta-api" path="/account/usage" method="get" %}
{% endopenapi-operation %}

### `GET /account/billing`

{% openapi-operation spec="algenta-api" path="/account/billing" method="get" %}
{% endopenapi-operation %}

### `POST /account/billing/checkout`

{% openapi-operation spec="algenta-api" path="/account/billing/checkout" method="post" %}
{% endopenapi-operation %}

### `POST /account/billing/portal`

{% openapi-operation spec="algenta-api" path="/account/billing/portal" method="post" %}
{% endopenapi-operation %}

### `GET /account/orgs`

{% openapi-operation spec="algenta-api" path="/account/orgs" method="get" %}
{% endopenapi-operation %}

### `GET /account/team`

{% openapi-operation spec="algenta-api" path="/account/team" method="get" %}
{% endopenapi-operation %}

### `POST /account/team/invite`

{% openapi-operation spec="algenta-api" path="/account/team/invite" method="post" %}
{% endopenapi-operation %}

### `PATCH /account/team/{user_id}/role`

{% openapi-operation spec="algenta-api" path="/account/team/{user_id}/role" method="patch" %}
{% endopenapi-operation %}

### `DELETE /account/team/{user_id}`

{% openapi-operation spec="algenta-api" path="/account/team/{user_id}" method="delete" %}
{% endopenapi-operation %}

## credits

### `POST /v1/credits/refresh`

{% openapi-operation spec="algenta-api" path="/v1/credits/refresh" method="post" %}
{% endopenapi-operation %}

## deployment

### `POST /v1/deployment/activate`

{% openapi-operation spec="algenta-api" path="/v1/deployment/activate" method="post" %}
{% endopenapi-operation %}

### `POST /v1/deployment/node/challenge`

{% openapi-operation spec="algenta-api" path="/v1/deployment/node/challenge" method="post" %}
{% endopenapi-operation %}

### `POST /v1/deployment/node/heartbeat`

{% openapi-operation spec="algenta-api" path="/v1/deployment/node/heartbeat" method="post" %}
{% endopenapi-operation %}

## devices

### `POST /v1/device/register`

{% openapi-operation spec="algenta-api" path="/v1/device/register" method="post" %}
{% endopenapi-operation %}

### `POST /v1/device/heartbeat`

{% openapi-operation spec="algenta-api" path="/v1/device/heartbeat" method="post" %}
{% endopenapi-operation %}

### `GET /v1/device/list`

{% openapi-operation spec="algenta-api" path="/v1/device/list" method="get" %}
{% endopenapi-operation %}

### `DELETE /v1/device/{registration_id}`

{% openapi-operation spec="algenta-api" path="/v1/device/{registration_id}" method="delete" %}
{% endopenapi-operation %}

### `GET /v1/runtime/authorize`

{% openapi-operation spec="algenta-api" path="/v1/runtime/authorize" method="get" %}
{% endopenapi-operation %}

## license

### `POST /v1/license/challenge`

{% openapi-operation spec="algenta-api" path="/v1/license/challenge" method="post" %}
{% endopenapi-operation %}

### `POST /v1/license/renew`

{% openapi-operation spec="algenta-api" path="/v1/license/renew" method="post" %}
{% endopenapi-operation %}

## metering

### `POST /v1/metering`

{% openapi-operation spec="algenta-api" path="/v1/metering" method="post" %}
{% endopenapi-operation %}

## oauth-device

### `POST /oauth/device/code`

{% openapi-operation spec="algenta-api" path="/oauth/device/code" method="post" %}
{% endopenapi-operation %}

### `POST /oauth/device/token`

{% openapi-operation spec="algenta-api" path="/oauth/device/token" method="post" %}
{% endopenapi-operation %}

### `GET /oauth/device/grant`

{% openapi-operation spec="algenta-api" path="/oauth/device/grant" method="get" %}
{% endopenapi-operation %}

### `POST /oauth/device/approve`

{% openapi-operation spec="algenta-api" path="/oauth/device/approve" method="post" %}
{% endopenapi-operation %}
