# algenta-sdk

TypeScript and JavaScript SDK for Algenta's HTTP API, local runtime,
simulations, governed data, and repository intelligence.

## Requirements

- Node.js 18 or newer
- An Algenta API key for Cloud Managed operations

## Install

```bash
npm install algenta-sdk
```

## Quickstart

```ts
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient(); // reads ALGENTA_API_KEY; defaults to https://api.algenta.ai

const datasets = await client.listDatasets({ search: "orders", compact: true });
const summary = await client.getDatasetSummary(datasets.datasets[0].dataset_id);
const result = await client.queryWithMetadata({
  dataset_id: summary.dataset_id,
  metric: { hint: "gross_revenue" },
  aggregation: "sum",
});
console.log(result.data.result);
```

Self-hosted engine? Pass `baseUrl: "http://localhost:8000"` and the API key
provisioned by your operator deployment. The `self_hosted` and `air_gapped`
deployment profiles fail closed and never silently fall back to Algenta's
cloud.

`AlgentaClient` also exposes connectors, exact and batch queries, SQL reports,
simulations, jobs, triggers, agent runs, decisions, deployment, account controls,
and repository intelligence. The complete typed reference and task-focused
examples live in the [TypeScript SDK documentation](https://docs.algenta.ai/sdks/typescript).

## Runtime and Local Libraries

`Runtime` is the mode-aware facade for local, Cloud Managed, and self-hosted
execution. Local runtime details are encapsulated by the package; users do not
install or operate a separate Mojo process. Private modes fail closed instead
of silently falling back to Algenta Cloud.

```ts
import { Runtime, libraries } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const rt = new Runtime({
  mode: "self_hosted",
  apiKey,
  baseUrl: "http://localhost:8000",
});

const models = await rt.listModels();
const tokenized = await rt.tokenize({ input: "alpha beta" });
const usage = await rt.usage();
const recommendation = await rt.recommend(
  [
    { name: "expand", request: { mode: "expert", runs: 250 } },
    { name: "hold", request: { mode: "expert", runs: 250 } },
  ],
  { runs: 250, seed: 42 },
);
const catalog = await libraries({ mode: "local" });

console.log(models.items.length, tokenized.tokens.length, usage.billing_period);
console.log(recommendation.recommended_action, catalog.modules.length);
```

Runtime forwards the governed helper groups for models and vector utilities,
account and team controls, API keys, jobs, triggers, connectors, datasets,
audit logs, execution policy, repository intelligence, agent runs, deployment
lifecycle, and decision helpers.

## Unified Capability Plane

```ts
const route = await client.routeCapabilities({
  objective: "Investigate the latest checkout incident.",
  kinds: ["dataset", "skill", "mcp_tool", "runtime_library"],
  artifact_affinities: ["incident"],
});

const capability = await client.getCapability(route.selected_capability_id, {
  includeInstruction: true,
});
const execution = await client.executeCapability({
  capability_id: route.selected_capability_id,
  binding_id: route.selected_binding_id,
  input: { objective: "Investigate the latest checkout incident." },
});

const providers = await client.listCapabilityProviders();
const skills = await client.listSkills();
const mcpProviders = await client.listMcpProviders();

console.log(capability, execution, providers, skills, mcpProviders);
```

Execution ownership remains authoritative: `algenta_managed` capabilities must
execute through the Algenta service, while local runtime adapters only execute
`client_managed` capabilities and fail closed otherwise. Runnable repository
examples live in `examples/capability-plane/` and
`examples/langgraph/capability_router.py`.

## Repository Intelligence

The repository workflow covers snapshot, triage, graph, plan, simulation, and
patch generation. Full request schemas are maintained in the
[repository reference](https://docs.algenta.ai/sdks/typescript/repositories).

For fully local planning, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`.
Stored plan revisions expose `planner_model_id`, `planner_execution_mode`, and
`planner_provider_backend`, so execution provenance remains explicit.

## Contract Exports

The package exports `DEFAULT_BASE_URL`, `PRIMARY_DATA_QUERY_CONTRACT`, client
and runtime classes, request and response types, validation errors, and the
local library catalog from its root entrypoint.

```ts
import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from "algenta-sdk";

console.log(DEFAULT_BASE_URL);
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint);
```

## Development

This package is a standalone npm package (the repository root has no
workspace), so all commands run from this directory:

```bash
cd packages/ts-sdk
npm ci
npm run build        # tsc — emits dist/
npm test             # tsc && vitest run
npm run lint         # tsc --noEmit
npm run lint:biome   # biome check .
```

## Documentation

- [TypeScript SDK](https://docs.algenta.ai/sdks/typescript)
- [Overview and setup](https://docs.algenta.ai/sdks/typescript/overview)
- [Connectors and data](https://docs.algenta.ai/sdks/typescript/connectors-and-data)
- [Simulations and queries](https://docs.algenta.ai/sdks/typescript/simulations-and-queries)
- [Repository intelligence](https://docs.algenta.ai/sdks/typescript/repositories)
- [Troubleshooting](https://docs.algenta.ai/help/troubleshooting)
