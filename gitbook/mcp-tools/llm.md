---
icon: brain
description: MCP reference for Algenta's deterministic utility-model tools — list models, tokenize, count tokens, chat, responses, embeddings, similarity, and rerank.
---

# LLM utility MCP tools

These tools expose Algenta's deterministic utility-model surface over MCP. They are reproducible, tokenizer- and lexical-embedding-backed routes — not provider-backed generative models — so the same input always yields the same output. Use them to size prompts, produce stable embeddings, and rerank candidates without spending on a generative provider. Each tool wraps a single authenticated endpoint.

Configure `algenta-mcp` first so the `algenta` tools appear in your client — see [MCP server](../sdk/mcp.md). Always call `list_models` before the others: it reports which models the instance can actually execute and their routing, failover, timeout, and auth-header readiness.

{% hint style="info" %}
`chat_completions` and `responses` are the deterministic **utility** chat and response surfaces, backed by tokenization or lexical embeddings. They are not generative chat models. To route a real generative objective, use the [capability plane](capability-plane.md).
{% endhint %}

## Tools

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `list_models` | List the model catalog with routing, failover, timeout, and auth-header readiness. | _(none)_ |
| `resolve_artifact_bridge` | Resolve one Hugging Face artifact path through the cache-safe compatibility bridge. | `repo_id`, `filename` (required); `revision`, `local_files_only` (default `true`) |
| `tokenize` | Tokenize UTF-8 text with a deterministic tokenizer model. | `input` (required); `model` (default `text.tokenizer`) |
| `count_tokens` | Count tokens with a deterministic tokenizer model. | `input` (required); `model` (default `text.tokenizer`) |
| `chat_completions` | Run the deterministic utility chat surface (tokenizer-backed). | `messages` (required; `role`+`content`); `model` (default `text.tokenizer`) |
| `responses` | Run the unified utility response surface over tokenization or lexical embeddings. | `input` (required; string or array); `model` (default `text.tokenizer`), `dimensions` (default 64, 1–4096) |
| `embeddings` | Generate deterministic lexical embeddings. | `input` (required; string or array); `model` (default `text.hash_embedding_v1`), `dimensions` (default 64, 1–4096) |
| `embedding_similarity` | Score two caller-supplied vectors with a similarity model. | `left`, `right` (required; number arrays); `model` (default `embeddings.cosine_similarity`) |
| `rerank` | Rank caller-supplied document embeddings deterministically. | `query_embedding`, `documents` (required; each `id`+`embedding`); `model` (default `embeddings.cosine_similarity`), `top_n` |

## Endpoint mapping

| Tool | Method | Endpoint |
|------|--------|----------|
| `list_models` | `GET` | `/v1/models` |
| `resolve_artifact_bridge` | `POST` | `/v1/artifacts/resolve` |
| `tokenize` | `POST` | `/v1/tokenize` |
| `count_tokens` | `POST` | `/v1/count_tokens` |
| `chat_completions` | `POST` | `/v1/chat/completions` |
| `responses` | `POST` | `/v1/responses` |
| `embeddings` | `POST` | `/v1/embeddings` |
| `embedding_similarity` | `POST` | `/v1/embeddings/similarity` |
| `rerank` | `POST` | `/v1/rerank` |

## Worked examples

### Read the model catalog

`list_models` takes no arguments and returns the truthful catalog for this instance. Call it before routing to any other tool.

{% code title="list_models (tool call)" %}
```json
{ "name": "list_models", "arguments": {} }
```
{% endcode %}

```bash
curl -sS "$ALGENTA_BASE_URL/v1/models" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '.data[].id'
```

### Count tokens before a call

Size any text against the deterministic tokenizer. The result is stable across calls, so you can budget prompts reliably.

{% code title="count_tokens (tool call)" %}
```json
{
  "name": "count_tokens",
  "arguments": {
    "input": "the quick brown fox",
    "model": "text.tokenizer"
  }
}
```
{% endcode %}

```bash
curl -sS "$ALGENTA_BASE_URL/v1/count_tokens" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "input": "the quick brown fox", "model": "text.tokenizer" }'
```

### Embed text, then rerank candidates

`embeddings` accepts a string or an array of strings and returns fixed-dimension lexical vectors. Feed those vectors into `rerank` to order documents against a query embedding.

{% code title="embeddings (tool call)" %}
```json
{
  "name": "embeddings",
  "arguments": {
    "input": ["renewals dashboard", "quarterly churn report"],
    "model": "text.hash_embedding_v1",
    "dimensions": 64
  }
}
```
{% endcode %}

{% code title="rerank (tool call)" %}
```json
{
  "name": "rerank",
  "arguments": {
    "query_embedding": [0.12, 0.04, 0.88],
    "documents": [
      { "id": "doc-1", "embedding": [0.10, 0.05, 0.90], "text": "renewals dashboard" },
      { "id": "doc-2", "embedding": [0.80, 0.10, 0.02], "text": "payroll export" }
    ],
    "top_n": 1
  }
}
```
{% endcode %}

{% hint style="info" %}
`resolve_artifact_bridge` defaults to `local_files_only: true` and never downloads. Set it to `false` explicitly if you want the bridge to fetch an artifact that is not already cached.
{% endhint %}

## Related pages

{% content-ref url="../sdk/mcp.md" %}
[mcp.md](../sdk/mcp.md)
{% endcontent-ref %}

{% content-ref url="capability-plane.md" %}
[capability-plane.md](capability-plane.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
