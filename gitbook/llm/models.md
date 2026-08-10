---
icon: cubes
description: The Algenta LLM model catalog — GET /v1/models, the provider.<backend>:<model> id scheme, the ten configurable backends, dynamic model discovery, and per-backend BYOK.
---

# LLM models & providers

Every Algenta LLM call names a `model` id, and every id you can call is advertised by `GET /v1/models`. The catalog holds three kinds of model:

- **Built-in utility models** — deterministic, always present, no provider or key required (tokenizer, lexical embeddings, similarity/rerank kernels).
- **Provider-backed models** — a concrete upstream model on a backend you configure (for example a specific OpenAI or Anthropic model).
- **Discovered models** — one routable id per model a configured backend currently offers, expanded live from a single wildcard registry entry.

This page is the reference for the catalog endpoint, the id scheme, the backends and their capabilities, dynamic discovery, and how you supply keys per backend.

## GET /v1/models

Returns the truthful, currently executable catalog. Only runtime-backed or explicitly configured provider-backed models are advertised — a model appears here only if the engine can actually route to it right now. The route is authenticated and metered (rate-limited per minute, counted against your quota).

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_API_URL/v1/models" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
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

catalog = client.list_models()
for model in catalog.data:
    print(model.id, model.capabilities, "available" if model.available else "unavailable")
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: process.env.ALGENTA_API_URL ?? "https://api.algenta.ai",
});

const catalog = await client.listModels();
for (const model of catalog.data) {
  console.log(model.id, model.capabilities.join(","), model.available);
}
```
{% endtab %}

{% tab title="CLI" %}
```bash
de llm models              # human-readable table
de llm models --format json
```
{% endtab %}
{% endtabs %}

The response is `{ "object": "list", "data": [ ... ] }`. Each entry is a model descriptor:

```json title="models.json"
{
  "object": "list",
  "data": [
    {
      "id": "text.tokenizer",
      "object": "model",
      "owned_by": "algenta",
      "runtime_module": "text",
      "description": "Deterministic word tokenizer.",
      "capabilities": ["tokenize", "count_tokens", "chat_completions"],
      "supported_endpoints": [
        "/v1/models", "/v1/tokenize", "/v1/count_tokens",
        "/v1/chat/completions", "/v1/responses"
      ],
      "tokenizer_kind": "word",
      "provider_backend": null,
      "provider_auth_configured": false,
      "available": true
    },
    {
      "id": "provider.openai:gpt-4o",
      "object": "model",
      "owned_by": "algenta",
      "description": "Provider-backed model routed through configured backend 'openai'.",
      "capabilities": ["chat_completions"],
      "supported_endpoints": ["/v1/models", "/v1/chat/completions", "/v1/responses"],
      "provider_backend": "openai",
      "provider_auth_env_vars": ["OPENAI_API_KEY"],
      "provider_auth_configured": true,
      "available": true
    }
  ]
}
```

Key descriptor fields:

| Field | Meaning |
| --- | --- |
| `id` | The value you pass as `model` in every LLM call. |
| `capabilities` | What the model can do: `tokenize`, `count_tokens`, `chat_completions`, `embeddings`, `embedding_similarity`, `rerank`. |
| `supported_endpoints` | The `/v1` routes that accept this model. |
| `provider_backend` | The upstream backend for provider-routed models; `null` for built-in utility models. |
| `provider_auth_configured` | Whether the required provider credentials are present, so the model is callable. |
| `routing_targets` / `resolved_routing_targets` | For `router` models, the ordered failover targets and their flattened leaves. |
| `available` | Whether the engine can route to this model right now. |

### Built-in utility models

These are always in the catalog. They are deterministic and require no provider or key — useful for local development, tests, and token accounting.

| Model id | Capabilities | Endpoints |
| --- | --- | --- |
| `text.tokenizer` | `tokenize`, `count_tokens`, `chat_completions` | `/v1/tokenize`, `/v1/count_tokens`, `/v1/chat/completions`, `/v1/responses` |
| `text.hash_embedding_v1` | `embeddings` | `/v1/embeddings`, `/v1/responses` |
| `embeddings.cosine_similarity` | `embedding_similarity`, `rerank` | `/v1/embeddings/similarity`, `/v1/rerank` |
| `embeddings.euclidean_distance` | `embedding_similarity`, `rerank` | `/v1/embeddings/similarity`, `/v1/rerank` |
| `embeddings.manhattan_distance` | `embedding_similarity`, `rerank` | `/v1/embeddings/similarity`, `/v1/rerank` |

{% hint style="info" %}
The utility chat and embedding models are deterministic kernels, not general-purpose LLMs. To call a real provider model, configure a backend (below) and pass its id.
{% endhint %}

## The `provider.<backend>:<model>` id scheme

Provider-backed models are registered on a self-hosted engine through one JSON registry (see [Configure a backend](#configure-a-backend)). Every registry entry has an `id` you choose. The recommended convention is to name the entry after its backend, `provider.<backend>` (for example `provider.openai`, `provider.anthropic`).

- A **static entry** (one concrete `model_name`) is addressable directly by its `id`, e.g. `provider.openai.gpt-4o`.
- A **discovery entry** (`model_name: "*"`) expands in `GET /v1/models` into one id per model the backend offers, formed as the entry `id`, a colon, and the discovered model — for example `provider.openai:gpt-4o` or `provider.anthropic:claude-sonnet-4`.

Pass whichever id you see in `GET /v1/models` as the `model` field. A chat or embeddings request to `provider.openai:gpt-4o` routes to the `provider.openai` entry's backend with `gpt-4o` as the upstream model.

## Supported backends

Ten backends are supported. Each entry declares its `backend`; the backend fixes which capabilities the entry can serve.

| Backend (`backend`) | Chat completions | Embeddings | Notes |
| --- | --- | --- | --- |
| `openai` | Yes | Yes | OpenAI. |
| `openai_compatible` | Yes | Yes | Any OpenAI-compatible endpoint. |
| `anthropic` | Yes | No | Anthropic (Claude); `anthropic-version` is set for you. |
| `google_genai` | Yes | Yes | Google Generative AI. |
| `mistral` | Yes | Yes | Mistral. |
| `cohere` | Yes | Yes | Cohere; supports `embedding_input_type`. |
| `groq` | Yes | No | Groq. |
| `xai` | Yes | Yes | xAI. |
| `ollama` | Yes | Yes | Local Ollama; the API key is optional. |
| `algenta_local` | Yes | No | Local Apple-Silicon GPU engine (Qwen3-family checkpoints); no `base_url`, no API key. |
| `router` | Yes | Yes | An ordered alias over other entries, with failover. |

## Configure a backend

Provider-backed models are configured on a self-hosted engine by setting the `ALGENTA_LLM_PROVIDER_MODELS_JSON` environment variable to a JSON list of entries. Each non-router entry needs an `id`, a `backend`, a `base_url`, an `api_key_env` (the name of the environment variable that holds the key — optional only for `ollama` and `algenta_local`), and a `model_name`. The `algenta_local` backend takes no `base_url` at all — see [The local GPU engine backend](#the-local-gpu-engine-backend).

```json title="provider-models.json"
[
  {
    "id": "provider.openai.gpt-4o",
    "backend": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "model_name": "gpt-4o"
  }
]
```

Restart the engine after changing the registry, then confirm the new id appears in `GET /v1/models`. See [Self-hosting](../self-hosting.md) and the [Configuration reference](../configuration.md) for where to set engine environment variables.

{% hint style="info" %}
`base_url` follows the backend's own convention (for example `.../v1` for OpenAI-compatible backends). The engine appends the standard chat/embeddings path to it.
{% endhint %}

## The local GPU engine backend

`algenta_local` runs chat completions on this machine's Apple-Silicon GPU through the Algenta engine — no upstream HTTP provider. The entry's `model_name` is a key into a second registry, `ALGENTA_LOCAL_LLM_MODELS_JSON`, which maps model names to checkpoint directories (Hugging Face snapshots of supported Qwen3-family models):

```json title="provider-models.json"
[
  {
    "id": "provider.algenta_local",
    "backend": "algenta_local",
    "model_name": "qwen3-0.6b-base"
  }
]
```

```json title="ALGENTA_LOCAL_LLM_MODELS_JSON"
{
  "qwen3-0.6b-base": "/path/to/Qwen3-0.6B-Base",
  "qwen3-1.7b": "/path/to/Qwen3-1.7B"
}
```

The engine resolves the Metal GPU worker through the standard SDK environment knobs (`ALGENTA_NATIVE_WORKER`, `ALGENTA_RUNTIME_FALLBACK_MODE=allow`). The first call on a checkpoint converts it once into `<checkpoint>/.algenta-cache/` and loads the weights; the worker then keeps the loaded weights RESIDENT, so repeat requests adopt them directly (no re-read, no re-quantization — measured ~18x faster than the first load). Switching to a different model tears the old weights down and loads the new one. Generation is greedy by default; the request's `temperature`, `top_p`, `max_tokens`, and `seed` fields enable seeded sampling (`temperature > 0` draws from the model distribution; same prompt + parameters + seed reproduce the identical completion). Responses stream through the same SSE shape as every other backend.

Current scope, stated precisely: chat completions only (no embeddings), one-shot generation re-chunked into SSE frames (true token-by-token streaming is the next gap-4 increment), and messages are flattened to prompt text without a chat template (a single message is used verbatim; multiple messages join as `role: content` lines).

## Dynamic model discovery

Instead of pinning a static `model_name`, an entry can opt in to discovery so the catalog always reflects the models the backend offers today. Set `model_name` to the wildcard `"*"`:

```json title="discovery-two-backends.json"
[
  {
    "id": "provider.openai",
    "backend": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "model_name": "*"
  },
  {
    "id": "provider.anthropic",
    "backend": "anthropic",
    "base_url": "https://api.anthropic.com/v1",
    "api_key_env": "ANTHROPIC_API_KEY",
    "model_name": "*"
  }
]
```

With those two entries configured and `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` set, `GET /v1/models` queries each backend's own list-models API and expands the wildcard into one routable id per discovered model: `provider.openai:gpt-4o`, `provider.anthropic:claude-sonnet-4`, and so on. There is no static list to keep current.

How discovery behaves:

- **Egress-guarded.** Discovery only calls the `base_url` you configured, under the same fail-closed egress policy as every other outbound request.
- **TTL-cached.** Discovered lists are cached and refreshed on a short interval, so the catalog stays fast under load.
- **Best-effort.** If a backend is unreachable or returns an error, discovery degrades to "no discovered models for that entry" and reuses the last cached list — it never fails the whole catalog.
- **Not for `router`.** The `router` alias composes other entries and is not itself discoverable.

## Bring your own key, per backend

Every provider-backed model authenticates with a key you supply — Algenta never bundles provider credentials. There are two ways to supply one, depending on how you run the engine.

{% tabs %}
{% tab title="Self-hosted (env var)" %}
Each registry entry names the environment variable that holds its key via `api_key_env`. Set that variable on the engine host:

```bash
export OPENAI_API_KEY="$OPENAI_API_KEY"
export ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
```

For backends that need extra upstream headers, map header names to environment variables with `header_envs` on the entry. The `ollama` backend can run without a key.
{% endtab %}

{% tab title="Hosted (per-organization)" %}
On a multi-tenant deployment, an org admin stores one key per backend through `POST /v1/provider-keys`. The key is encrypted at rest, never returned, and used only to serve that organization's calls:

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/provider-keys" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"backend\": \"anthropic\", \"api_key\": \"$ANTHROPIC_API_KEY\"}"
```

There is one key per `(organization, backend)`. See the [BYOK guide](../guides/byok.md) for the full lifecycle.
{% endtab %}
{% endtabs %}

The `provider_auth_configured` field on each `GET /v1/models` descriptor tells you whether the key for that backend is present, so you can confirm a model is callable before you use it.

## Related

- [Chat completions & responses](completions.md) — call chat, responses, tokenize, and count_tokens.
- [Embeddings, similarity & rerank](embeddings.md) — generate and score vectors.
- [Bring your own key (BYOK)](../guides/byok.md) — the per-tenant provider-key lifecycle.
- [API endpoint reference](../api/reference.md) — full request/response schemas.
- [Error codes](../api/errors.md) — provider and model error shapes.
