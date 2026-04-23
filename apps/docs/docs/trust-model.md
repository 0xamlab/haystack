---
sidebar_position: 8
---

# Trust Model

This page separates current safe claims from the target model.

## Current safe claims

### Local mode

- execution can run locally
- local mode does not require an API key
- connected local data stays in the local runtime path
- plain `Runtime()` stays in the unrestricted local path
- explicit hosted local mode, such as `Runtime(api_key="de_live_...")` in Python or `new Runtime({ apiKey: "de_live_..." })` in TypeScript, can enforce a stored local device license and local credit bucket for offline execution when the advanced runtime components are present

### API mode

- requests are processed through Algenta services
- the direct API client and API-backed runtime mode are explicit choices

## Target model

Algenta is converging toward:

- local-first execution
- optional cloud assist
- tighter guarantees around minimal metadata sharing where applicable

## Why this matters

Docs and product language must not claim stronger data-locality guarantees than the current code path proves today.
