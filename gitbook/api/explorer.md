---
icon: circle-play
description: Try the Algenta HTTP API live — set your key and base URL, then send real requests to every endpoint from the browser.
---

# API explorer

Every endpoint below renders live from the Algenta OpenAPI specification. Expand an operation to see parameters, request and response schemas, and example payloads, then use **Test it** to call the API directly from this page with your own key. For prose walkthroughs and SDK equivalents, see the API reference and the SDK pages.

{% hint style="info" %}
These operations are generated from the canonical OpenAPI spec, so they always match the deployed engine. Set your base URL (your self-hosted deployment or `https://api.algenta.ai`) and API key in the **Test it** panel.
{% endhint %}

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

## Simulation

### `POST /v1/simulate`

{% openapi-operation spec="algenta-api" path="/v1/simulate" method="post" %}
{% endopenapi-operation %}

### `GET /v1/simulate/templates`

{% openapi-operation spec="algenta-api" path="/v1/simulate/templates" method="get" %}
{% endopenapi-operation %}

### `POST /v1/simulate/what-if`

{% openapi-operation spec="algenta-api" path="/v1/simulate/what-if" method="post" %}
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

## Governed data

### `GET /v1/data`

{% openapi-operation spec="algenta-api" path="/v1/data" method="get" %}
{% endopenapi-operation %}

### `GET /v1/data/{dataset_id}/summary`

{% openapi-operation spec="algenta-api" path="/v1/data/{dataset_id}/summary" method="get" %}
{% endopenapi-operation %}

### `GET /v1/data/{dataset_id}`

{% openapi-operation spec="algenta-api" path="/v1/data/{dataset_id}" method="get" %}
{% endopenapi-operation %}

## Semantic query

### `POST /v1/resolve`

{% openapi-operation spec="algenta-api" path="/v1/resolve" method="post" %}
{% endopenapi-operation %}

### `POST /v1/verify`

{% openapi-operation spec="algenta-api" path="/v1/verify" method="post" %}
{% endopenapi-operation %}

### `POST /v1/query`

{% openapi-operation spec="algenta-api" path="/v1/query" method="post" %}
{% endopenapi-operation %}

### `POST /v1/query/sql-report`

{% openapi-operation spec="algenta-api" path="/v1/query/sql-report" method="post" %}
{% endopenapi-operation %}

## Decision memory

### `POST /v1/decisions`

{% openapi-operation spec="algenta-api" path="/v1/decisions" method="post" %}
{% endopenapi-operation %}

### `GET /v1/decisions`

{% openapi-operation spec="algenta-api" path="/v1/decisions" method="get" %}
{% endopenapi-operation %}

### `PATCH /v1/decisions/{decision_id}/outcome`

{% openapi-operation spec="algenta-api" path="/v1/decisions/{decision_id}/outcome" method="patch" %}
{% endopenapi-operation %}

## Account & usage

### `GET /v1/me`

{% openapi-operation spec="algenta-api" path="/v1/me" method="get" %}
{% endopenapi-operation %}

### `GET /v1/usage`

{% openapi-operation spec="algenta-api" path="/v1/usage" method="get" %}
{% endopenapi-operation %}

### `GET /v1/limits`

{% openapi-operation spec="algenta-api" path="/v1/limits" method="get" %}
{% endopenapi-operation %}

## Billing

### `POST /v1/billing/checkout`

{% openapi-operation spec="algenta-api" path="/v1/billing/checkout" method="post" %}
{% endopenapi-operation %}

### `GET /v1/billing/info`

{% openapi-operation spec="algenta-api" path="/v1/billing/info" method="get" %}
{% endopenapi-operation %}

## Devices & local runtime

### `POST /v1/device/register`

{% openapi-operation spec="algenta-api" path="/v1/device/register" method="post" %}
{% endopenapi-operation %}

### `POST /v1/credits/refresh`

{% openapi-operation spec="algenta-api" path="/v1/credits/refresh" method="post" %}
{% endopenapi-operation %}

### `POST /v1/metering`

{% openapi-operation spec="algenta-api" path="/v1/metering" method="post" %}
{% endopenapi-operation %}
