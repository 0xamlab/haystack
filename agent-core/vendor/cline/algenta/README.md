# Algenta agent-core — real adapter over the vendored Cline SDK

`adapter.ts` runs a headless `ClineCore` task (any provider Cline supports; key resolved
from `.env` via the SDK provider catalog) that edits files under a working directory.
`run-server.ts` exposes it over the NDJSON `POST /run` contract the Python loopback client
(`repository_intelligence_agent_core_client`) drives.

## Setup (once, after vendoring)
```
bun install
bun run build:sdk
bash algenta/postbuild.sh        # symlink @cline/* into node_modules
```

## Run the sidecar
```
AGENT_CORE_PORT=8765 ANTHROPIC_API_KEY=... bun algenta/run-server.ts
```

## Wire Python
Set `ALGENTA_AGENT_CORE_URL=http://127.0.0.1:8765`; the `verified_agentic` planner's
default runner then POSTs runs to the sidecar.

## Status
**LIVE-proven end-to-end:** Python `verified_agentic` → sidecar → `ClineCore` → real
Anthropic model → file edit → Python-recomputed diff. Any-provider (anthropic, gemini,
openai, bedrock, vertex, …). Full interface map: `../../../CLINE_SDK_INTERFACE.md`.
