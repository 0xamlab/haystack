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

### `DELETE /v1/api-keys/{key_id}`

{% openapi-operation spec="algenta-api" path="/v1/api-keys/{key_id}" method="delete" %}
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

## Billing

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

## Logs

### `GET /v1/logs`

{% openapi-operation spec="algenta-api" path="/v1/logs" method="get" %}
{% endopenapi-operation %}

## MCP

### `GET /mcp/tools`

{% openapi-operation spec="algenta-api" path="/mcp/tools" method="get" %}
{% endopenapi-operation %}

### `GET /mcp/sse`

{% openapi-operation spec="algenta-api" path="/mcp/sse" method="get" %}
{% endopenapi-operation %}

### `POST /mcp/messages`

{% openapi-operation spec="algenta-api" path="/mcp/messages" method="post" %}
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

## Team

### `GET /v1/team`

{% openapi-operation spec="algenta-api" path="/v1/team" method="get" %}
{% endopenapi-operation %}

### `POST /v1/team/invite`

{% openapi-operation spec="algenta-api" path="/v1/team/invite" method="post" %}
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

## credits

### `POST /v1/credits/refresh`

{% openapi-operation spec="algenta-api" path="/v1/credits/refresh" method="post" %}
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

## metering

### `POST /v1/metering`

{% openapi-operation spec="algenta-api" path="/v1/metering" method="post" %}
{% endopenapi-operation %}
