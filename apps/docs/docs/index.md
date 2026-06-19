---
slug: /
sidebar_position: 1
---

# Overview

Algenta is a self-hosted decision and governed data/query runtime you deploy on your infrastructure.

Start the service with one command, verify the API, and then choose the first live lane that matches the job:

- inspect the live contract: `GET /v1/meta/contract`
- first decision: `POST /v1/simulate`
- first governed dataset query: `GET /v1/data?search=...&compact=1` -> `GET /v1/data/{dataset_id}/summary` -> `POST /v1/query`
- first unified route selection: `POST /v1/capabilities/route`

If an older self-hosted node still returns `404` for `GET /v1/meta/contract`,
use `/openapi.json` and read `x-primary-data-query-contract` instead.

Integrate via API, SDK, CLI, or MCP after the service is running.

If the request needs customer-agnostic routing across data, MCP, skills,
native tools, or runtime libraries, start with
[Capability Plane](/api-reference/capability-plane).
`algenta_managed` routes can execute through Algenta; `client_managed` routes
must execute in the customer app or adapter path and fail closed otherwise.

```bash
curl -sSL https://codna.ai/install.sh | bash
```

Open [Quickstart](/quickstart).
