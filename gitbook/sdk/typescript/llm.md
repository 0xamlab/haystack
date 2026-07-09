---
icon: robot
description: TypeScript SDK methods for the governed LLM surface — chat, responses, embeddings, rerank, tokenization, model artifacts — plus model catalog and runtime discovery.
---

# LLM and model discovery

These `AlgentaClient` methods cover the governed LLM surface (chat completions, responses, embeddings, rerank, tokenization, and model-artifact resolution) plus the discovery calls that tell you which models and which engine build the instance actually serves. Method names are `camelCase`; bodies stay `snake_case`. Every model call is routed per the instance catalog — a model not in `listModels()` cannot be called.

## Chat and responses

`chatCompletions` runs a message list to completion; `streamChatCompletions` returns an `AsyncGenerator` of chunk responses. The `responses` and `streamResponses` pair works the same way over the responses API. `model` is optional — omit it to use the instance default.

```typescript title="chat.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });

// Single completion.
const completion = await client.chatCompletions({
  messages: [
    { role: "system", content: "You are terse." },
    { role: "user", content: "Summarize Q3 in one line." },
  ],
});
console.log(completion.choices[0].message.content);

// Streamed completion.
for await (const chunk of client.streamChatCompletions({
  messages: [{ role: "user", content: "List three risks." }],
})) {
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `chatCompletions(request)` | `POST /v1/chat/completions` | `messages` with `role`/`content`; returns a `ChatCompletionsResponse`. Sends `stream: false`. |
| `streamChatCompletions(request)` | `POST /v1/chat/completions` | `AsyncGenerator` of `ChatCompletionsStreamChunkResponse`. Sends `stream: true`. |
| `responses(request)` | `POST /v1/responses` | `input` string or array; returns a `ResponsesResponse`. Sends `stream: false`. |
| `streamResponses(request)` | `POST /v1/responses` | `AsyncGenerator` of `ResponseStreamEventResponse`. Sends `stream: true`. |

## Embeddings and rerank

`embeddings` returns one vector per input; `embeddingSimilarity` scores two vectors directly; `rerank` orders documents (each with a precomputed `embedding`) against a `query_embedding`.

```typescript title="embeddings.ts"
// Embed text.
const embedded = await client.embeddings({
  input: ["empty cart at checkout", "payment declined"],
});
console.log(embedded.data.length, embedded.dimensions);

// Rerank documents against a query embedding.
const reranked = await client.rerank({
  query_embedding: embedded.data[0].embedding,
  documents: [
    { id: "doc_1", embedding: embedded.data[0].embedding, text: "empty cart at checkout" },
    { id: "doc_2", embedding: embedded.data[1].embedding, text: "payment declined" },
  ],
  top_n: 2,
});
console.log(reranked.data.map((d) => [d.id, d.rank, d.score]));
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `embeddings(request)` | `POST /v1/embeddings` | `input` string or array; optional `dimensions`. |
| `embeddingSimilarity(request)` | `POST /v1/embeddings/similarity` | `left` and `right` vectors; returns a `score`. |
| `rerank(request)` | `POST /v1/rerank` | `query_embedding` plus `documents` (`id`, `embedding`, `text?`); optional `top_n`. |

## Tokenization

| Method | HTTP | Notes |
| --- | --- | --- |
| `tokenize(request)` | `POST /v1/tokenize` | Returns the `tokens` array and `token_count` for the `input`. |
| `countTokens(request)` | `POST /v1/count_tokens` | Returns just the `token_count` for the `input`. |

## Model artifacts

| Method | HTTP | Notes |
| --- | --- | --- |
| `resolveArtifactBridge(request)` | `POST /v1/artifacts/resolve` | Resolves a model artifact by `repo_id` and `filename`; defaults to `local_files_only: true`. |

## Model catalog and runtime discovery

Before you route to a model, ask the instance what it can run. `listModels` returns the executable catalog; `getContract` returns the machine-readable platform contract (and falls back to `/openapi.json` if the contract endpoint is absent); the runtime getters read the signed manifest and validation artifacts for the active build.

```typescript title="discovery.ts"
const models = await client.listModels();          // GET /v1/models
const contract = await client.getContract();        // GET /v1/meta/contract
const manifest = await client.getRuntimeManifest(); // GET /v1/runtime/manifest
console.log(models.data.length, manifest);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `listModels()` | `GET /v1/models` | The catalog of models this instance can execute. |
| `getContract()` | `GET /v1/meta/contract` | Machine-readable platform contract; falls back to `/openapi.json`. |
| `getRuntimeManifest()` | `GET /v1/runtime/manifest` | Signed manifest of the active runtime build. |
| `getRuntimeModules()` | `GET /v1/admin/runtime/modules` | Registered runtime-library modules. |
| `getRuntimeBenchmarks()` | `GET /v1/admin/runtime/benchmarks` | Published runtime benchmarks. |
| `getRuntimeReleaseValidation()` | `GET /v1/admin/runtime/validation` | Release-validation proof for the build. |

{% hint style="success" %}
`getContract`, `getRuntimeManifest`, and the runtime getters validate their payloads against the runtime-proof contract. An invalid or tampered response raises an error rather than returning unverified data.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Connect data sources</strong></td><td>Create connectors, onboard datasets, and triage repositories.</td><td><a href="connectors-and-data.md">connectors-and-data.md</a></td></tr>
<tr><td><strong>Simulate and query</strong></td><td>Run Monte Carlo decisions and governed data queries.</td><td><a href="simulations-and-queries.md">simulations-and-queries.md</a></td></tr>
<tr><td><strong>Discover the API</strong></td><td>Bootstrap from the health, contract, and models endpoints.</td><td><a href="../../api/overview.md">../../api/overview.md</a></td></tr>
</tbody></table>
