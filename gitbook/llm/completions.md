---
icon: comments
description: Run chat completions, the unified response envelope, tokenize, and count_tokens over the Algenta LLM API — with streaming, from curl, Python, TypeScript, or the CLI.
---

# Run chat completions

The Algenta LLM API exposes an OpenAI-shaped surface for text generation and token accounting. This guide covers the four request-side routes: `POST /v1/chat/completions` (a chat transcript in, an assistant message out), `POST /v1/responses` (a unified envelope over the same models), and `POST /v1/tokenize` / `POST /v1/count_tokens` (deterministic token accounting). Chat and responses both support streaming.

Every route names a `model` id. Use a built-in utility model for deterministic behavior, or a provider-backed id for a real LLM — see [LLM models & providers](models.md).

## Before you start

You need:

- An API key sent as `Authorization: Bearer $ALGENTA_API_KEY`. See [Authentication](../authentication.md).
- `$ALGENTA_API_URL` — `https://api.algenta.ai` (hosted) or your engine, e.g. `http://localhost:8000`.
- A `model` id from `GET /v1/models`. The examples use `provider.openai:gpt-4o`; substitute any chat-capable id you see in the catalog (the built-in `text.tokenizer` also serves chat deterministically).

## Chat completions

Send an ordered `messages` transcript. Each message has a `role` (`system`, `user`, `assistant`, or `developer`) and `content`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/chat/completions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:gpt-4o",
    "messages": [
      {"role": "system", "content": "You are concise."},
      {"role": "user", "content": "Summarize the CAP theorem in one sentence."}
    ]
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

result = client.chat_completions(
    [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Summarize the CAP theorem in one sentence."},
    ],
    model="provider.openai:gpt-4o",
)
print(result.choices[0].message.content)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: process.env.ALGENTA_API_URL ?? "https://api.algenta.ai",
});

const result = await client.chatCompletions({
  model: "provider.openai:gpt-4o",
  messages: [
    { role: "system", content: "You are concise." },
    { role: "user", content: "Summarize the CAP theorem in one sentence." },
  ],
});
console.log(result.choices[0].message.content);
```
{% endtab %}

{% tab title="CLI" %}
```bash
# request.json holds {"model": "...", "messages": [...]}
de llm chat request.json
de llm chat request.json --format json
```
{% endtab %}
{% endtabs %}

The `200` response is a `chat.completion`: one assistant `choices[0].message.content`, plus `usage` and — for provider-routed models — which backend served it.

```json title="chat-completion.json"
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "model": "provider.openai:gpt-4o",
  "provider_backend": "openai",
  "provider_model_id": "provider.openai:gpt-4o",
  "provider_attempts": [
    {
      "provider_backend": "openai",
      "provider_model_id": "provider.openai:gpt-4o",
      "outcome": "selected",
      "error_code": null
    }
  ],
  "choices": [
    {
      "index": 0,
      "finish_reason": "stop",
      "message": {"role": "assistant", "content": "Under a network partition a distributed store can keep either consistency or availability, not both."}
    }
  ],
  "usage": {"prompt_tokens": 24, "completion_tokens": 18, "total_tokens": 42}
}
```

{% hint style="success" %}
**Expected result** — a `200` with `object: "chat.completion"` and a non-empty `choices[0].message.content`. For a provider-routed model, `provider_backend` names the backend that served it and `provider_attempts` shows the routing path (`selected` for the one that answered, `failed` for any earlier attempt).
{% endhint %}

### Stream the completion

Set `stream: true` to receive Server-Sent Events instead of one JSON body. The stream emits `chat.completion.chunk` events with incremental `delta.content`, then a final `data: [DONE]`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -N -X POST "$ALGENTA_API_URL/v1/chat/completions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:gpt-4o",
    "messages": [{"role": "user", "content": "Count to five."}],
    "stream": true
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
for chunk in client.stream_chat_completions(
    [{"role": "user", "content": "Count to five."}],
    model="provider.openai:gpt-4o",
):
    print(chunk)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
for await (const chunk of client.streamChatCompletions({
  model: "provider.openai:gpt-4o",
  messages: [{ role: "user", content: "Count to five." }],
})) {
  console.log(chunk);
}
```
{% endtab %}

{% tab title="CLI" %}
```bash
de llm chat request.json --stream
```
{% endtab %}
{% endtabs %}

## The unified response envelope

`POST /v1/responses` runs the same models behind one envelope. `input` is a single string or a list of strings; the response carries `output` items and `usage`. It also supports `stream: true`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/responses" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:gpt-4o",
    "input": "Give me one fact about the ocean."
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
result = client.responses(
    "Give me one fact about the ocean.",
    model="provider.openai:gpt-4o",
)
print(result.output)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
const result = await client.responses({
  model: "provider.openai:gpt-4o",
  input: "Give me one fact about the ocean.",
});
console.log(result.output);
```
{% endtab %}

{% tab title="CLI" %}
```bash
de llm responses request.json
de llm responses request.json --stream
```
{% endtab %}
{% endtabs %}

The `200` response is a `response` object with `status: "completed"`, an `output` array, and `usage`.

## Tokenize and count tokens

`POST /v1/tokenize` and `POST /v1/count_tokens` run a tokenizer model deterministically. They default to `text.tokenizer`; pass any tokenizer-capable `model`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/tokenize" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "text.tokenizer", "input": "hello world"}'

curl -sS -X POST "$ALGENTA_API_URL/v1/count_tokens" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "text.tokenizer", "input": "hello world"}'
```
{% endtab %}

{% tab title="Python" %}
```python
tokens = client.tokenize("hello world", model="text.tokenizer")
print(tokens.tokens, tokens.token_count)

count = client.count_tokens("hello world", model="text.tokenizer")
print(count.token_count)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
const tokens = await client.tokenize({ model: "text.tokenizer", input: "hello world" });
console.log(tokens.tokens, tokens.token_count);

const count = await client.countTokens({ model: "text.tokenizer", input: "hello world" });
console.log(count.token_count);
```
{% endtab %}

{% tab title="CLI" %}
```bash
de llm tokenize --input "hello world" --model text.tokenizer
de llm count-tokens --input "hello world" --model text.tokenizer
```
{% endtab %}
{% endtabs %}

`/v1/tokenize` returns `{ model, tokenizer_kind, tokens, token_count }`; `/v1/count_tokens` returns `{ model, tokenizer_kind, token_count }`.

## Troubleshooting

<details>

<summary>404 model_not_supported</summary>

The `model` id is not in `GET /v1/models`. List the catalog and copy an exact id. For a provider model, confirm the backend is configured and its key is present (`provider_auth_configured: true`). See [LLM models & providers](models.md).

</details>

<details>

<summary>422 model_capability_unsupported</summary>

The model exists but does not support this route — for example calling `/v1/chat/completions` with an embeddings-only model. Check the descriptor's `capabilities` and `supported_endpoints`.

</details>

<details>

<summary>429, 502, 503, or 504</summary>

`429` is a rate limit or a provider rate limit (`provider_rate_limited`); back off and retry. `502`/`503` (`backend_unavailable`) and `504` (`provider_timeout`) come from the upstream provider — retry, and for `router` models the engine may fail over to the next target automatically. Error bodies follow `{ "error": { "code", "message", "details", "request_id" } }`; see [Error codes](../api/errors.md).

</details>

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Generate embeddings</strong></td><td>Embed text, then score similarity and rerank.</td><td><a href="embeddings.md">embeddings.md</a></td></tr>
<tr><td><strong>Pick a model</strong></td><td>Browse the catalog, backends, and discovery.</td><td><a href="models.md">models.md</a></td></tr>
<tr><td><strong>Bring your own key</strong></td><td>Supply a provider credential per backend.</td><td><a href="../guides/byok.md">../guides/byok.md</a></td></tr>
</tbody></table>
