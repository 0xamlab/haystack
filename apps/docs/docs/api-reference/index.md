---
sidebar_position: 1
---

# API Reference

**Base URL:** `https://api.algenta.ai`

**Authentication:** All endpoints require an API key via:
- `Authorization: Bearer de_live_...` header
- `X-API-Key: de_live_...` header for legacy `v1` compatibility only

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | [`/v1/simulate`](/api-reference/simulate) | Run a Monte Carlo simulation |
| `POST` | [`/v1/recommend`](/api-reference/recommend) | Pick the best action from multiple options |
| `POST` | [`/v1/score`](/api-reference/score) | Score a single scenario (0.0–1.0) |
| `POST` | [`/v1/batch`](/api-reference/batch) | Run multiple simulations in one request |
| `POST` | [`/v1/compare`](/api-reference/compare) | Compare named scenarios head-to-head |
| `POST` | `/v1/jobs` | Submit async simulation job |
| `GET`  | `/v1/jobs/{id}` | Poll job status |
| `GET`  | `/v1/jobs/{id}/result` | Retrieve completed job result |
| `POST` | `/v1/jobs/{id}/cancel` | Cancel a running job |
| `GET`  | `/v1/me` | Current user + org info |
| `GET`  | `/v1/usage` | Monthly usage summary |
| `GET`  | `/v1/limits` | Plan-based limits |
| `GET`  | `/v1/api-keys` | List API keys |
| `POST` | `/v1/api-keys` | Create API key |
| `DELETE` | `/v1/api-keys/{id}` | Revoke API key |
| `GET`  | `/v1/templates` | Built-in simulation templates |
| `GET`  | `/v1/distributions` | Supported distribution types |

## Response envelope

Every simulation response returns a **DecisionEnvelope**:

```json
{
  "run_id": "uuid",
  "status": "completed",
  "engine_version": "0.1.0",
  "recommended_action": "proceed | caution | reject",
  "confidence": 0.82,
  "rationale": "Human-readable explanation",
  "metrics": {
    "expected_value": 105000.0,
    "median": 102000.0,
    "std_deviation": 38000.0,
    "variance": 1444000000.0,
    "probability_of_loss": 0.18,
    "var_95": -15000.0,
    "cvar_95": -25000.0
  },
  "percentiles": {
    "p5": 42000.0,
    "p25": 72000.0,
    "p50": 102000.0,
    "p75": 135000.0,
    "p95": 175000.0
  },
  "scenarios_run": 10000,
  "execution_ms": 42,
  "metadata": {
    "mode": "auto",
    "seed": 42,
    "billing_units": 1,
    "engine_version": "0.1.0"
  },
  "result_hash": "40a76a11..."
}
```

## Headers

| Header | Description |
|--------|-------------|
| `X-Request-Id` | Unique request identifier (echoed from `X-Request-Id` if provided) |
| `X-Decision-Hash` | `sha256=<hash>;v=1` — SHA-256 of decision output for tamper detection |
| `X-Execution-Ms` | Canonical server execution time for synchronous responses |
| `X-Mojo-Ms` | Mojo execution time when the compute path used Mojo |
| `X-RateLimit-Limit` | Per-minute request limit for the authenticated plan |
| `X-RateLimit-Remaining` | Remaining requests in the current rate-limit window |

## Status codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created (signup, API key creation) |
| `400` | Validation error |
| `401` | Authentication required or invalid |
| `404` | Resource not found |
| `422` | Request body schema error |
| `429` | Rate limit or quota exceeded |
| `500` | Internal engine error |
