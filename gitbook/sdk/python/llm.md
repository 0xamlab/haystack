---
icon: robot
description: Python SDK reference for the governed LLM surface — list_models, tokenize, count_tokens, chat_completions, responses, embeddings, embedding_similarity, and rerank.
---

# LLM and embeddings methods

These methods call Algenta's governed LLM surface: model discovery, tokenization, chat completions, the responses API, embeddings, similarity, and reranking. They are available on both `AlgentaClient` and `AsyncAlgentaClient` (await the async calls). Every model argument routes through the instance's model catalog — call `list_models()` first to see what is executable, as described in [API overview](../../api/overview.md).

## Method reference

| Method | Purpose |
| --- | --- |
| `list_models()` | List the LLM utility models this instance can execute (`LLMModelListResult`). Reads `/v1/models`. |
| `tokenize(text, *, model="text.tokenizer")` | Tokenize text (`TokenizeResult`). Posts to `/v1/tokenize`. |
| `count_tokens(text, *, model="text.tokenizer")` | Count tokens in text (`CountTokensResult`). Posts to `/v1/count_tokens`. |
| `chat_completions(messages, *, model="text.tokenizer")` | Run a chat completion (`ChatCompletionsResult`). Posts to `/v1/chat/completions`. |
| `stream_chat_completions(messages, *, model="text.tokenizer")` | Stream a chat completion as chunks. Posts to `/v1/chat/completions`. |
| `responses(input_value, *, model="text.tokenizer", dimensions=64)` | Run the responses API and return output items (`ResponsesResult`). Posts to `/v1/responses`. |
| `stream_responses(input_value, *, model="text.tokenizer", dimensions=64)` | Stream responses events. Posts to `/v1/responses`. |
| `embeddings(input_value, *, model="text.hash_embedding_v1", dimensions=64)` | Compute embeddings (`EmbeddingsResult`). Posts to `/v1/embeddings`. |
| `embedding_similarity(left, right, *, model="embeddings.cosine_similarity")` | Compute similarity between two vectors (`EmbeddingSimilarityResult`). Posts to `/v1/embeddings/similarity`. |
| `rerank(query_embedding, documents, *, model="embeddings.cosine_similarity", top_n=None)` | Rerank documents against a query embedding (`RerankResponseResult`). Posts to `/v1/rerank`. |
| `resolve_artifact_bridge(*, repo_id, filename, revision=None, local_files_only=True)` | Resolve a model artifact through the governed artifact bridge (`ArtifactBridgeResolveResult`). Posts to `/v1/artifacts/resolve`. |

## Example: discover a model and run a chat completion

```python title="chat.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

# Only models listed here are executable on this instance.
models = client.list_models()
print([m.id for m in models.data])

count = client.count_tokens("How many tokens is this?")
print(count.token_count)

reply = client.chat_completions(
    [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Summarize the incident in one sentence."},
    ],
)
print(reply.choices[0].message.content)
```

## Example: embed, compare, and rerank

```python title="embeddings.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

vectors = client.embeddings(["orders pipeline", "checkout latency"])
left = vectors.data[0].embedding
right = vectors.data[1].embedding

similarity = client.embedding_similarity(left, right)
print(similarity.score)

ranked = client.rerank(
    query_embedding=left,
    documents=[
        {"id": "doc-1", "text": "checkout latency runbook"},
        {"id": "doc-2", "text": "billing reconciliation notes"},
    ],
    top_n=1,
)
for item in ranked.data:
    print(item.rank, item.id, item.score)
```

## Related pages

{% content-ref url="../../api/overview.md" %}
[overview.md](../../api/overview.md)
{% endcontent-ref %}

{% content-ref url="simulations-and-queries.md" %}
[simulations-and-queries.md](simulations-and-queries.md)
{% endcontent-ref %}

{% content-ref url="../mcp.md" %}
[mcp.md](../mcp.md)
{% endcontent-ref %}
