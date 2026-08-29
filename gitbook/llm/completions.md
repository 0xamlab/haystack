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

Send an ordered `messages` transcript. Each message has a `role` (`system`, `user`, `assistant`, `developer`, or `tool`) and `content`.

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

## Tool calling

Pass `tools` (a list of function definitions) on a provider-backed model and the assistant message can answer with `tool_calls` instead of (or alongside) `content`. `finish_reason` is `"tool_calls"` whenever the model called one; a request that never sets `tools` keeps returning `finish_reason: "stop"` exactly as before. `tool_choice` (`"auto"`, `"required"`, `"none"`, or `{"type": "function", "function": {"name": "..."}}`) and `parallel_tool_calls` are optional. Non-streaming only for now — pass `stream: true` together with `tools` and the engine returns `422 model_capability_unsupported` rather than silently dropping the tool call from the SSE stream.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/chat/completions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:gpt-4o",
    "messages": [{"role": "user", "content": "What is the weather in Paris?"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get the current weather for a location.",
        "parameters": {
          "type": "object",
          "properties": {"location": {"type": "string"}},
          "required": ["location"]
        }
      }
    }],
    "tool_choice": "auto"
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
result = client.chat_completions(
    [{"role": "user", "content": "What is the weather in Paris?"}],
    model="provider.openai:gpt-4o",
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }],
    tool_choice="auto",
)
for tool_call in result.choices[0].message.tool_calls or []:
    print(tool_call.function.name, tool_call.function.arguments)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
const result = await client.chatCompletions({
  model: "provider.openai:gpt-4o",
  messages: [{ role: "user", content: "What is the weather in Paris?" }],
  tools: [{
    type: "function",
    function: {
      name: "get_weather",
      description: "Get the current weather for a location.",
      parameters: {
        type: "object",
        properties: { location: { type: "string" } },
        required: ["location"],
      },
    },
  }],
  tool_choice: "auto",
});
for (const toolCall of result.choices[0].message.tool_calls ?? []) {
  console.log(toolCall.function.name, toolCall.function.arguments);
}
```
{% endtab %}
{% endtabs %}

The assistant message carries `tool_calls` instead of (or alongside) text, and the arguments are always a JSON-encoded string (`function.arguments`), matching the OpenAI wire shape regardless of which backend actually served the request:

```json title="chat-completion-tool-calls.json"
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "model": "provider.openai:gpt-4o",
  "provider_backend": "openai",
  "provider_model_id": "provider.openai:gpt-4o",
  "provider_attempts": [{"provider_backend": "openai", "provider_model_id": "provider.openai:gpt-4o", "outcome": "selected", "error_code": null}],
  "choices": [
    {
      "index": 0,
      "finish_reason": "tool_calls",
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {"name": "get_weather", "arguments": "{\"location\":\"Paris\"}"}
          }
        ]
      }
    }
  ],
  "usage": {"prompt_tokens": 24, "completion_tokens": 18, "total_tokens": 42}
}
```

To continue the conversation, append the assistant's `tool_calls` message and a `role: "tool"` message carrying the result (`tool_call_id` must match the call it answers):

```json title="tool-result-followup.json"
{
  "model": "provider.openai:gpt-4o",
  "messages": [
    {"role": "user", "content": "What is the weather in Paris?"},
    {"role": "assistant", "content": null, "tool_calls": [{"id": "call_abc123", "type": "function", "function": {"name": "get_weather", "arguments": "{\"location\":\"Paris\"}"}}]},
    {"role": "tool", "tool_call_id": "call_abc123", "content": "15C, partly cloudy"}
  ]
}
```

### Per-backend tool-calling support

| Backend | Tools | `tool_choice` |
|---|---|---|
| `openai`, `openai_compatible`, `groq`, `xai`, `mistral` | Full — forwarded verbatim | `"auto"`, `"required"`, `"none"`, or a named-function choice |
| `anthropic` | Full — translated to Claude's `tool_use`/`tool_result` blocks | Same set, translated to Claude's `tool_choice` |
| `google_genai` | Full — translated to `functionDeclarations`; Gemini assigns no call id, so the engine synthesizes one | Same set, translated to `functionCallingConfig` |
| `cohere` | Full | `"auto"` and `"required"`/`"none"` only — forcing one named function returns `422 model_capability_unsupported` (Cohere's Chat v2 API has no per-function forcing) |
| `ollama` | Full | `"auto"` only — forcing `"required"`/`"none"`/a named function returns `422 model_capability_unsupported` (`/api/chat` has no request-side forcing knob) |
| `algenta_local` | Supported on a checkpoint with a chat template (rendered into the Qwen3 template's tools preamble; `<tool_call>` blocks in the generation are parsed back into structured `tool_calls`) — refuses `422 model_capability_unsupported` on a checkpoint with no chat template | `"auto"` (default) and `"none"` only — the template's preamble is a hint the model may act on, not a mechanism that forces one, so `"required"`/a named-function choice return `422 model_capability_unsupported` |
| `text.tokenizer` | Not supported — `422 model_capability_unsupported` | — |

## The unified response envelope

`POST /v1/responses` runs the same models behind one envelope. The response carries `output` items and `usage`, and supports `stream: true`. `input` accepts either of two shapes, which are never mixed:

- **Legacy shape** — a single string, or a list of strings. Each string is an INDEPENDENT single-turn request against the model; a list of N strings makes N separate completions in one call, not a conversation. This is unchanged from before and is what every example below without `tools`/`previous_response_id` uses.
- **Typed shape** — a list of OpenResponses-style items, each an object with a `type`: `message` (`{"type": "message", "role": "user"|"assistant"|"system"|"developer", "content": "..."}`), `function_call` (an assistant tool call, mirroring `tool_calls` on a Chat Completions message), or `function_call_output` (a tool's result, mirroring a `role: "tool"` message). A typed array is processed as ONE multi-turn conversation, exactly like a Chat Completions `messages` list. The engine classifies a list as typed the moment every item is an object with a `type` key; anything else falls back to the legacy shape.

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

### Tool calling and multi-turn conversations

Pass `tools`/`tool_choice`/`parallel_tool_calls` together with the typed input-array shape to run a real multi-turn conversation with tool calling — the same knobs, translation, and per-backend support matrix as [chat completions' tool calling](#tool-calling) above. A tool-call-only turn returns `content[0].text: null` alongside a populated `content[0].tool_calls` and `finish_reason: "tool_calls"`. As with chat completions, `stream: true` together with a turn that calls a tool returns `422 model_capability_unsupported` rather than dropping the tool call from the SSE stream.

To continue the conversation, send only the NEW turn's items (a `function_call_output` answering the prior tool call, or a new `message`) and set `previous_response_id` to the `id` from the prior call — the engine prepends that call's stored history for you:

{% tabs %}
{% tab title="cURL" %}
```bash
# Turn 1: the model asks to call get_weather.
curl -sS -X POST "$ALGENTA_API_URL/v1/responses" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:gpt-4o",
    "input": [{"type": "message", "role": "user", "content": "What is the weather in Paris?"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}
      }
    }],
    "tool_choice": "auto"
  }'
# -> {"id": "resp_...", "output": [{"content": [{"tool_calls": [{"id": "call_abc123", ...}], "finish_reason": "tool_calls"}]}]}

# Turn 2: continue with the tool's result -- only the new item, plus previous_response_id.
curl -sS -X POST "$ALGENTA_API_URL/v1/responses" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "provider.openai:gpt-4o",
    "input": [{"type": "function_call_output", "call_id": "call_abc123", "output": "15C, partly cloudy"}],
    "previous_response_id": "resp_..."
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
first = client.responses(
    [{"type": "message", "role": "user", "content": "What is the weather in Paris?"}],
    model="provider.openai:gpt-4o",
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }],
    tool_choice="auto",
)
call = first.output[0].content[0].tool_calls[0]

second = client.responses(
    [{"type": "function_call_output", "call_id": call.id, "output": "15C, partly cloudy"}],
    model="provider.openai:gpt-4o",
    previous_response_id=first.id,
)
print(second.output[0].content[0].text)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
const first = await client.responses({
  model: "provider.openai:gpt-4o",
  input: [{ type: "message", role: "user", content: "What is the weather in Paris?" }],
  tools: [{
    type: "function",
    function: {
      name: "get_weather",
      parameters: {
        type: "object",
        properties: { location: { type: "string" } },
        required: ["location"],
      },
    },
  }],
  tool_choice: "auto",
});
const call = first.output[0].content[0].tool_calls![0];

const second = await client.responses({
  model: "provider.openai:gpt-4o",
  input: [{ type: "function_call_output", call_id: call.id, output: "15C, partly cloudy" }],
  previous_response_id: first.id,
});
console.log(second.output[0].content[0].text);
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
**`previous_response_id` is in-memory and single-process.** The prior turn's history is held only in the memory of the Algenta process that served it — it does not survive a process restart, and a follow-up request will not find it if load balancing routes it to a different worker or replica than the one that answered the first call. Self-hosted single-process deployments and short-lived scripts are fine; a multi-replica production deployment should treat this as ephemeral and pass the full typed input array itself (including prior `message`/`function_call`/`function_call_output` items) instead of relying on `previous_response_id` across requests that may land on different workers.
{% endhint %}

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
