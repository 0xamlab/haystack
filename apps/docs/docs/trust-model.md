---
sidebar_position: 8
---

# Trust Model

This page separates current safe claims from the target model.

## Current safe claims

### Enterprise deployment

- `self_hosted` is the private-by-default enterprise profile
- `air_gapped` is the strict privacy profile
- `ALGENTA_DISABLE_TELEMETRY=1` means no outbound/vendor telemetry, not “no local audit”
- `GET /v1/admin/privacy-report` is the buyer-facing proof endpoint for the active privacy contract

### Local mode

- execution can run locally
- local mode does not require an API key
- connected local data stays in the local runtime path
- plain `Runtime()` stays in the unrestricted local path
- explicit hosted local mode, such as `Runtime(api_key="<YOUR_ALGENTA_API_KEY>")` in Python or `new Runtime({ apiKey: "<YOUR_ALGENTA_API_KEY>" })` in TypeScript, can enforce a stored local device license and local credit bucket for offline execution when the advanced runtime components are present
- `air_gapped` local mode requires a local signed license and does not silently fall back to the hosted control plane

### API mode

- requests are processed through Algenta services
- the direct API client and API-backed runtime mode are explicit choices
- persisted operator and review surfaces are explicit too: replayable agent runs,
  immutable audit-log artifacts, and execution-policy snapshots are retrieved
  through named APIs and do not depend on hidden local state

## Target model

Algenta is converging toward:

- service-first deployment
- self-hosted by default for enterprise
- cloud-managed as convenience, not the canonical private data plane
- strict privacy profile for air-gapped buyers
- HTTP/API integration by default
- optional local runtime for development or embedded execution
- tighter guarantees around minimal metadata sharing where applicable

## Why this matters

Docs and product language must not claim stronger data-locality guarantees than the current code path proves today.
