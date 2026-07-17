---
icon: chart-scatter
description: Generate text embeddings, score two vectors with a similarity metric, and rerank candidate documents over the Algenta LLM API — from curl, Python, TypeScript, or the CLI.
---

# Generate embeddings

The Algenta LLM API has three vector routes. `POST /v1/embeddings` turns text into vectors. `POST /v1/embeddings/similarity` scores two precomputed vectors. `POST /v1/rerank` orders candidate documents by their precomputed vectors against a query vector. This guide runs all three.

Only `/v1/embeddings` generates vectors from text — similarity and rerank operate on vectors you already have. Each route names a `model` id from [LLM models & providers](models.md).

## Before you start

You need:

- An API key sent as `Authorization: Bearer $ALGENTA_API_KEY`. See [Authentication](../authentication.md).
- `$ALGENTA_API_URL` — `https://api.algenta.ai` (hosted) or your engine, e.g. `http://localhost:8000`.
- A `model` id. For generation use a provider-backed embeddings id or the built-in `text.hash_embedding_v1`; for scoring use `embeddings.cosine_similarity` (also `embeddings.euclidean_distance` or `embeddings.manhattan_distance`).

## Embed text

`input` is a single string or a list of strings. Each returned vector carries its `index` and `token_count`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/embeddings" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:text-embedding-3-small",
    "input": ["first document", "second document"]
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url=os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai"),
)

result = client.embeddings(
    ["first document", "second document"],
    model="provider.openai:text-embedding-3-small",
)
print(len(result.data), "vectors")
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: process.env.ALGENTA_API_URL ?? "https://api.algenta.ai",
});

const result = await client.embeddings({
  model: "provider.openai:text-embedding-3-small",
  input: ["first document", "second document"],
});
console.log(result.data.length, "vectors");
```
{% endtab %}

{% tab title="CLI" %}
```bash
# request.json holds {"model": "...", "input": ["...", "..."]}
de llm embeddings request.json
de llm embeddings request.json --format json
```
{% endtab %}
{% endtabs %}

The `200` response is a `list` of embedding vectors plus `usage`.

```json title="embeddings.json"
{
  "object": "list",
  "model": "provider.openai:text-embedding-3-small",
  "dimensions": 64,
  "provider_backend": "openai",
  "provider_model_id": "provider.openai:text-embedding-3-small",
  "data": [
    {"object": "embedding", "index": 0, "embedding": [0.01, -0.02, "..."], "token_count": 2},
    {"object": "embedding", "index": 1, "embedding": [0.03, 0.00, "..."], "token_count": 2}
  ],
  "usage": {"prompt_tokens": 4, "total_tokens": 4}
}
```

{% hint style="success" %}
**Expected result** — a `200` with `object: "list"` and one `data[]` vector per input string, each with its `index` and `token_count`. For a provider-routed model, `provider_backend` names the backend that served the request.
{% endhint %}

{% hint style="info" %}
The `dimensions` field (default `64`) sets the output width of the built-in `text.hash_embedding_v1` encoder. Provider-backed models return their own native dimensionality.
{% endhint %}

## Score two vectors

`POST /v1/embeddings/similarity` scores two vectors you supply as `left` and `right`. It does not generate embeddings. The metric comes from the model: `embeddings.cosine_similarity`, `embeddings.euclidean_distance`, or `embeddings.manhattan_distance`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/embeddings/similarity" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embeddings.cosine_similarity",
    "left": [0.1, 0.2, 0.3],
    "right": [0.1, 0.25, 0.28]
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
result = client.embedding_similarity(
    [0.1, 0.2, 0.3],
    [0.1, 0.25, 0.28],
    model="embeddings.cosine_similarity",
)
print(result.score, result.similarity_metric)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
const result = await client.embeddingSimilarity({
  model: "embeddings.cosine_similarity",
  left: [0.1, 0.2, 0.3],
  right: [0.1, 0.25, 0.28],
});
console.log(result.score, result.similarity_metric);
```
{% endtab %}

{% tab title="CLI" %}
```bash
# request.json holds {"model": "...", "left": [...], "right": [...]}
de llm embedding-similarity request.json
```
{% endtab %}
{% endtabs %}

The `200` response is `{ model, similarity_metric, score, dimension }`.

## Rerank documents

`POST /v1/rerank` orders candidate documents by their precomputed embeddings against a `query_embedding`. Each document needs an `id` and `embedding`, with optional `text` and `metadata` returned unchanged. `top_n` (optional) limits how many ranked rows come back.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/rerank" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embeddings.cosine_similarity",
    "query_embedding": [0.1, 0.2, 0.3],
    "documents": [
      {"id": "doc-a", "embedding": [0.1, 0.2, 0.29], "text": "closest"},
      {"id": "doc-b", "embedding": [0.9, 0.1, 0.0], "text": "farther"}
    ],
    "top_n": 2
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
result = client.rerank(
    [0.1, 0.2, 0.3],
    [
        {"id": "doc-a", "embedding": [0.1, 0.2, 0.29], "text": "closest"},
        {"id": "doc-b", "embedding": [0.9, 0.1, 0.0], "text": "farther"},
    ],
    model="embeddings.cosine_similarity",
    top_n=2,
)
for item in result.data:
    print(item.rank, item.id, item.score)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
const result = await client.rerank({
  model: "embeddings.cosine_similarity",
  query_embedding: [0.1, 0.2, 0.3],
  documents: [
    { id: "doc-a", embedding: [0.1, 0.2, 0.29], text: "closest" },
    { id: "doc-b", embedding: [0.9, 0.1, 0.0], text: "farther" },
  ],
  top_n: 2,
});
for (const item of result.data) {
  console.log(item.rank, item.id, item.score);
}
```
{% endtab %}

{% tab title="CLI" %}
```bash
# request.json holds {"model": "...", "query_embedding": [...], "documents": [...], "top_n": 2}
de llm rerank request.json
```
{% endtab %}
{% endtabs %}

The `200` response lists ranked rows in order, plus counts.

```json title="rerank.json"
{
  "object": "list",
  "model": "embeddings.cosine_similarity",
  "similarity_metric": "cosine",
  "total_documents": 2,
  "returned_documents": 2,
  "data": [
    {"object": "rerank_result", "id": "doc-a", "index": 0, "rank": 1, "score": 0.999, "text": "closest"},
    {"object": "rerank_result", "id": "doc-b", "index": 1, "rank": 2, "score": 0.41, "text": "farther"}
  ]
}
```

## Troubleshooting

<details>

<summary>404 model_not_supported</summary>

The `model` id is not in `GET /v1/models`. Copy an exact id from the catalog. For a provider embeddings model, confirm the backend is configured and its key is present. Note that some backends serve chat only — see the capability table in [LLM models & providers](models.md).

</details>

<details>

<summary>422 invalid_embedding_dimensions or model_capability_unsupported</summary>

`invalid_embedding_dimensions` means `left` and `right` (or a document embedding and the query embedding) are not the same length — rerank and similarity compare vectors of equal width. `model_capability_unsupported` means the model does not support this route; check the descriptor's `capabilities`.

</details>

<details>

<summary>429, 503, or 504</summary>

`429` is a rate limit or provider rate limit; back off and retry. `503` (`backend_unavailable`) and `504` (`provider_timeout`) come from the upstream provider. Error bodies follow `{ "error": { "code", "message", "details", "request_id" } }`; see [Error codes](../api/errors.md).

</details>

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Run chat completions</strong></td><td>Generate text, responses, and token counts.</td><td><a href="completions.md">completions.md</a></td></tr>
<tr><td><strong>Pick a model</strong></td><td>Browse the catalog, backends, and discovery.</td><td><a href="models.md">models.md</a></td></tr>
<tr><td><strong>API endpoint reference</strong></td><td>Full request and response schemas.</td><td><a href="../api/reference.md">../api/reference.md</a></td></tr>
</tbody></table>
