---
sidebar_position: 1
---

# API Reference

**Base URL:** `https://api.algenta.ai`

**Authentication:** API requests require an API key via:

- `Authorization: Bearer de_live_...`
- `X-API-Key: de_live_...` for legacy `v1` compatibility only

## Primary runtime endpoints

These are the endpoints that back the primary runtime-first story:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/sources/register` | Register a source in the Decision Intelligence Layer |
| `POST` | `/v1/resolve` | Resolve structured intent into an exact plan |
| `POST` | `/v1/verify` | Validate an exact plan before execution |
| `POST` | `/v1/query` | Execute a deterministic query |

## Supported secondary endpoints

These endpoints remain supported and proven, but they are secondary to the runtime-first docs story:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | [`/v1/simulate`](/api-reference/simulate) | Run a simulation |
| `POST` | `/v1/recommend` | Compare actions |
| `POST` | `/v1/score` | Score a scenario |
| `POST` | `/v1/batch` | Run multiple simulations |
| `POST` | `/v1/compare` | Compare named scenarios |
| `POST` | `/v1/jobs` | Submit async simulation job |
| `GET` | `/v1/jobs/{id}` | Poll job status |
| `GET` | `/v1/jobs/{id}/result` | Retrieve completed job result |

## Runtime contract notes

- `/v1/resolve` is the planning boundary.
- `/v1/query` is execution-only and should be given an exact plan or a resolved plan.
- `/v1/verify` is the trust/introspection surface for plan validation.

## Headers

| Header | Description |
|--------|-------------|
| `X-Request-Id` | Request identifier for tracing |
| `X-Decision-Hash` | Decision integrity hash when available |
| `X-Execution-Ms` | Canonical server execution time |
| `X-RateLimit-Limit` | Plan-based rate limit |
| `X-RateLimit-Remaining` | Remaining requests in the current window |
