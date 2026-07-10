---
icon: js
description: Install algenta-sdk, construct an AlgentaClient, and learn the promise-based method surface and the typed error hierarchy before you call the engine.
---

# TypeScript SDK client

The TypeScript and JavaScript client is implemented in the repository package named `algenta-sdk`. The public npm package is not live yet, so this page documents the source-build contract and future npm package shape. It wraps the [HTTP API](../../api/overview.md) in one typed `AlgentaClient`, works on Node.js 18+ and modern browsers, and uses `fetch` with no required dependencies. The method surface itself is split across four reference pages linked at the end.

{% hint style="info" %}
Methods are `camelCase`, but request bodies and query parameters stay `snake_case`. You call `getDatasetSummary(...)` and `queryWithMetadata(...)`, and the payloads you pass and receive use fields like `dataset_id`, `source_name`, and `metric_column`. This mirrors the HTTP contract exactly.
{% endhint %}

## Install

Use the source checkout until the npm package is published:

```bash title="source-build.sh"
git clone https://github.com/thyn-ai/algenta.git
cd algenta
pnpm install
pnpm --filter algenta-sdk build
```

## Construct the client

`new AlgentaClient(config)` takes an optional config object. If you omit `apiKey`, the client reads it from `ALGENTA_API_KEY`, then the legacy `DE_API_KEY`. If none is set, the constructor throws with guidance rather than failing silently.

```typescript title="client.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,          // falls back to DE_API_KEY, then throws
  baseUrl: "https://api.algenta.ai",            // or http://localhost:8000 for self-host
});

const models = await client.listModels();
console.log(models);
```

`new AlgentaClient(config)` accepts an `AlgentaClientConfig`:

| Option | Type | Default | Notes |
| --- | --- | --- | --- |
| `apiKey` | `string` | `ALGENTA_API_KEY`, then `DE_API_KEY` | Required. Read from the environment if not passed. |
| `baseUrl` | `string` | `https://api.algenta.ai` (`DEFAULT_BASE_URL`) | Set an explicit origin for a self-hosted engine. |
| `timeout` | `number` | `120000` | Per-request timeout in milliseconds, enforced with `AbortController`. |
| `maxRetries` | `number` | `3` | Retries with exponential backoff; honors `Retry-After` on `429`. |
| `defaultHeaders` | `Record<string, string>` | `{}` | Merged into every request. |

{% hint style="warning" %}
A self-hosted engine needs an explicit `baseUrl`. The client never silently falls back to Algenta cloud — pass `http://localhost:8000` (or your own origin) and the API key provisioned by that deployment.
{% endhint %}

## Calls return promises

Every method returns a `Promise`, so use `await` (or `.then`). Streaming methods — `streamChatCompletions` and `streamResponses` — return an `AsyncGenerator`, so iterate them with `for await`.

```typescript title="promises.ts"
// Awaitable request/response.
const summary = await client.getDatasetSummary("ds_nps_scores");
console.log(summary.dataset_id, summary.name);

// Streaming method: iterate the async generator.
for await (const chunk of client.streamChatCompletions({
  messages: [{ role: "user", content: "Summarize Q3 in one line." }],
})) {
  process.stdout.write(chunk.choices?.[0]?.delta?.content ?? "");
}
```

## Errors

All client errors extend `DecisionEngineError` and carry a normalized `errorCode`, a `statusCode`, the raw `responseBody`, and a `details` accessor (with `validationErrors` for `422` bodies). Import the subclass you want to branch on.

```typescript title="errors.ts"
import {
  AlgentaClient,
  AuthenticationError,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "algenta-sdk";

try {
  await client.getDataset("does-not-exist");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.error("Not found:", err.errorCode);
  } else if (err instanceof RateLimitError) {
    console.error("Rate limited; retry after", err.retryAfter, "seconds");
  } else if (err instanceof AuthenticationError) {
    console.error("Check your API key");
  } else if (err instanceof ValidationError) {
    console.error("Invalid request:", err.validationErrors);
  }
}
```

| Error | HTTP status | Retried automatically |
| --- | --- | --- |
| `AuthenticationError` | 401 | No |
| `NotFoundError` | 404 | No |
| `ValidationError` | 422 | No |
| `RateLimitError` | 429 | Yes, honoring `Retry-After` up to `maxRetries` |
| `ServerError` | 5xx | Yes, with exponential backoff |
| `DecisionEngineError` | other | Base class for the hierarchy |

{% hint style="success" %}
Branch on `err.errorCode` (or `instanceof`), not on the human-readable `message`. Codes are stable; messages are not.
{% endhint %}

{% expandable title="Compatibility names for older integrations" %}
`AlgentaClient` is the canonical export. The same constructor is also exported as `DecisionEngineClient` and `CodnaClient`, with matching `AlgentaClientConfig` / `DecisionEngineClientConfig` / `CodnaClientConfig` config types, so older integrations keep working unchanged.

```typescript
import { AlgentaClient, DecisionEngineClient, CodnaClient } from "algenta-sdk";
// All three are the same class.
```
{% endexpandable %}

## Where to go next

Pick the method group you need — each page tables every method with its HTTP route and runnable examples.

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Simulate and query</strong></td><td>Run Monte Carlo decisions and governed data queries.</td><td><a href="simulations-and-queries.md">simulations-and-queries.md</a></td></tr>
<tr><td><strong>Decisions and products</strong></td><td>Log decision memory and call the product endpoints.</td><td><a href="decisions-and-products.md">decisions-and-products.md</a></td></tr>
<tr><td><strong>Connectors and data</strong></td><td>Manage connectors, datasets, and repository intelligence.</td><td><a href="connectors-and-data.md">connectors-and-data.md</a></td></tr>
</tbody></table>
