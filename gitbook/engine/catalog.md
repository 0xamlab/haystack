---
icon: layer-group
description: The Algenta engine catalog — every engine, its slug, API path, tier, and use cases, plus the three endpoints that enumerate them at runtime.
---

# Engine catalog

Algenta ships as a set of named **engines**, each a bundle of compute the instance can execute behind a stable API path. This page is the reference for that catalog: the full list, how the engines are grouped into tiers, and the three read-only endpoints that let you enumerate them at runtime instead of hardcoding a list.

The catalog is served from the instance itself, so it always reflects the build you are actually talking to. Ask the engine what it offers, then route to the API path it reports.

## Endpoints

All three are read-only `GET` endpoints and can be called with a bearer API key (`Authorization: Bearer $ALGENTA_API_KEY`), as in the examples below. Base URL is `https://api.algenta.ai` for Algenta cloud or your own origin such as `http://localhost:8000` when self-hosted.

| Method + path | Purpose | Key query params |
| --- | --- | --- |
| `GET /v1/engines` | List the full engine catalog (paginated). | `page` (default `1`), `limit` (default `25`, max `200`) |
| `GET /v1/engines/tiers` | The same engines grouped by tier. | — |
| `GET /v1/engines/{slug}` | Detail for one engine, addressed by its `slug`. | — |

## Engine object

Every engine is returned with the same fields.

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Human-readable engine name, e.g. `Decision Engine`. |
| `slug` | string | Stable identifier used in the URL and as a routing key, e.g. `decision`. |
| `description` | string | One-paragraph summary of what the engine does. |
| `api_path` | string | Top-level route prefix the engine serves, e.g. `/v1/decision`. |
| `mojo_libs` | string[] | The runtime libraries that contribute to the engine. |
| `use_cases` | string[] | Representative workloads the engine targets. |
| `tier` | string | One of `core`, `advanced`, or `platform`. |

## The catalog by tier

Engines are grouped into three tiers. `GET /v1/engines/tiers` returns exactly these three arrays: `core`, `advanced`, and `platform`.

{% tabs %}
{% tab title="Core" %}
The foundational engines most deployments use directly.

| Engine | `slug` | `api_path` | Use cases |
| --- | --- | --- | --- |
| Decision Engine | `decision` | `/v1/decision` | pricing, risk analysis, supply chain, routing |
| Inference Engine | `inference` | `/v1/inference` | chat, generation, embeddings, real-time inference |
| Agent Engine | `agent` | `/v1/agent` | automation, copilots, workflows, orchestration |
| Retrieval Engine | `retrieval` | `/v1/retrieval` | enterprise search, knowledge systems, copilots, RAG |
| Optimization Engine | `optimize` | `/v1/optimize` | pricing optimization, routing, scheduling, resource allocation |
| Serving Engine | `serving` | `/v1/serving` | APIs, real-time serving, scaling, production deployment |
{% endtab %}

{% tab title="Advanced" %}
Engines for the model and data lifecycle.

| Engine | `slug` | `api_path` | Use cases |
| --- | --- | --- | --- |
| Training Engine | `training` | `/v1/training` | model training, fine-tuning, RLHF, experimentation |
| Data Engine | `data` | `/v1/data` | ETL, feature pipelines, analytics, data quality |
| Model Engine | `model` | `/v1/model` | loading, managing, adapting models, format conversion |
| Cost Engine | `cost` | `/v1/cost` | cost optimization, routing workloads, infra decisions, FinOps |
{% endtab %}

{% tab title="Platform" %}
Cross-cutting engines that govern and combine the others.

| Engine | `slug` | `api_path` | Use cases |
| --- | --- | --- | --- |
| Security & Governance Engine | `security` | `/v1/security` | compliance, safe AI, enterprise deployment, audit |
| Hybrid Intelligence Engine | `hybrid` | `/v1/hybrid` | strategic decisions, forecasting + optimization, advanced analytics, digital twins |
{% endtab %}
{% endtabs %}

{% hint style="info" %}
The catalog is the source of truth for `api_path`. Read `slug` -> `api_path` from the live catalog and route to it, rather than hardcoding a prefix that a future build may move.
{% endhint %}

## List every engine

`GET /v1/engines` returns the paginated catalog.

{% code title="List engines" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/engines?limit=50" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```json title="Response (truncated)"
{
  "count": 12,
  "total": 12,
  "page": 1,
  "limit": 50,
  "pages": 1,
  "engines": [
    {
      "name": "Decision Engine",
      "slug": "decision",
      "description": "Unified simulation + optimization + scoring + risk engine...",
      "api_path": "/v1/decision",
      "mojo_libs": ["engines_monte_carlo", "distributions", "risk"],
      "use_cases": ["pricing", "risk analysis", "supply chain", "routing"],
      "tier": "core"
    }
  ]
}
```

The list envelope carries the standard pagination fields (`count` for this page, `total` across all pages, plus `page`, `limit`, and `pages`). Page through with `page` and `limit` when you request a small `limit`.

## Group engines by tier

`GET /v1/engines/tiers` returns the catalog pre-grouped.

{% code title="Engines by tier" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/engines/tiers" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```json title="Response (shape)"
{
  "core": [ { "slug": "decision", "...": "..." } ],
  "advanced": [ { "slug": "training", "...": "..." } ],
  "platform": [ { "slug": "security", "...": "..." } ]
}
```

## Get one engine

`GET /v1/engines/{slug}` returns a single engine's full object.

{% code title="Get the decision engine" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/engines/decision" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```json title="Response"
{
  "name": "Decision Engine",
  "slug": "decision",
  "description": "Unified simulation + optimization + scoring + risk engine. Combines Monte Carlo, distributions, and ML-fusion for pricing, risk analysis, supply-chain, and routing decisions.",
  "api_path": "/v1/decision",
  "mojo_libs": [
    "engines_monte_carlo",
    "distributions",
    "decision_ml_fusion",
    "optimization_constrained",
    "multi_objective",
    "risk",
    "causal",
    "bayesian_inference",
    "scipy_optimize_ops",
    "stochastic"
  ],
  "use_cases": ["pricing", "risk analysis", "supply chain", "routing"],
  "tier": "core"
}
```

An unknown slug returns `404`, and the error names the valid slugs so you can correct the request:

```json title="Unknown slug"
{
  "detail": "Engine 'decisian' not found. Valid slugs: ['agent', 'cost', 'data', 'decision', ...]"
}
```

{% hint style="info" %}
Slugs are stable identifiers. Prefer them over engine names when you store a routing target, since names are display strings and may be reworded.
{% endhint %}

## Related references

- [API overview](../api/overview.md) — base URL, auth, discovery, and the error envelope.
- [Engine health & verification](health.md) — confirm the running build and its readiness.
- [How the engine works](../concepts/engine.md) — the model behind the engines.
