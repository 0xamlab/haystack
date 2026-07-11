---
icon: python
description: Install algenta-sdk, construct the sync or async AlgentaClient, configure retries and timeouts, handle typed errors, and jump to the Python method reference by domain.
---

# The Algenta Python client

`algenta-sdk` is the typed Python client for the Algenta HTTP API. You install it as `algenta-sdk` and import it as `decision_engine`; the client is a thin, faithful surface over the same `/v1` contract described in [API overview](../../api/overview.md), so every method maps to one endpoint. This page covers installation, constructing the client, sync versus async, retries and timeouts, and the exception hierarchy — then routes you to the method reference for each domain.

{% hint style="info" %}
The distribution is `algenta-sdk`; the import name is `decision_engine`. This is the historical, stable module name.
{% endhint %}

## Install

```bash title="install.sh"
pip install algenta-sdk
```

The client requires Python 3.10 or newer. CI verifies fresh wheel installs on Python 3.10, 3.12, and 3.14.

## Construct the client

Pass your API key explicitly, or let the constructor read it from the environment. Point `base_url` at the hosted API (the default) or at your own engine.

```python title="client.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",   # default; override for self-hosted
)
```

The API key resolves, in order, from the `api_key=` argument, then `ALGENTA_API_KEY`, then the legacy `DE_API_KEY`. If none is set, the constructor raises `ValueError`.

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `api_key` | `str` or `None` | `None` | Falls back to `ALGENTA_API_KEY`, then `DE_API_KEY`. |
| `base_url` | `str` or `None` | `https://api.algenta.ai` | Point at your self-hosted engine, e.g. `http://localhost:8000`. |
| `timeout` | `float` | `120.0` | Per-request timeout in seconds. |
| `max_retries` | `int` | `3` | Automatic retries on `429` and `5xx`. |

The client is a context manager that holds a pooled HTTP client; use `with` (or call `close()`) so connections are released.

```python title="context_manager.py"
with AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"]) as client:
    print(client.list_models().data)
```

{% hint style="info" %}
`AlgentaClient` is the preferred name. `DecisionEngineClient` and `CodnaClient` are accepted aliases for the same class, kept for backward compatibility.
{% endhint %}

## Sync vs async

Every method has an async equivalent on `AsyncAlgentaClient`, which is an async context manager exposing the identical surface. Aliases `AsyncDecisionEngineClient` and `AsyncCodnaClient` refer to the same class.

{% tabs %}
{% tab title="Sync" %}
```python title="sync.py"
import os
from decision_engine import AlgentaClient

with AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"]) as client:
    datasets = client.list_datasets(search="orders", compact=True)
    print(datasets.datasets)
```
{% endtab %}

{% tab title="Async" %}
```python title="async.py"
import asyncio
import os
from decision_engine import AsyncAlgentaClient

async def main() -> None:
    async with AsyncAlgentaClient(api_key=os.environ["ALGENTA_API_KEY"]) as client:
        datasets = await client.list_datasets(search="orders", compact=True)
        print(datasets.datasets)

asyncio.run(main())
```
{% endtab %}
{% endtabs %}

## Retries and timeouts

The client automatically retries `429` (rate limit) and `5xx` (server) responses up to `max_retries` (default `3`), then raises the corresponding typed exception. Each request is bounded by `timeout` seconds (default `120.0`). Tune both in the constructor:

```python title="tuning.py"
client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    timeout=30.0,
    max_retries=5,
)
```

## Errors

Every method raises a subclass of `DecisionEngineError`. All are importable from `decision_engine`.

| Exception | Raised on | Notes |
| --- | --- | --- |
| `AuthenticationError` | `401` | Missing, invalid, expired, or revoked API key. |
| `ValidationError` | `422` | Request failed validation; inspect `.validation_errors` / `.field_errors`. |
| `NotFoundError` | `404` | Resource not found. |
| `RateLimitError` | `429` | Quota or rate limit exceeded; carries `.retry_after`. The client already retried up to `max_retries`. |
| `ServerError` | `5xx` | Server-side error. |
| `DecisionEngineError` | any | Base class; carries `.status_code`, `.error_code`, `.request_id`, and `.details`. |

```python title="errors.py"
from decision_engine import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    DecisionEngineError,
)

try:
    client.get_dataset_summary("does-not-exist")
except NotFoundError as exc:
    print(exc.error_code, exc.request_id)
except RateLimitError as exc:
    print("retry after", exc.retry_after)   # already retried up to max_retries
except ValidationError as exc:
    print(exc.field_errors)
except DecisionEngineError as exc:
    print(exc.status_code, exc)
```

## Reference by domain

Each method maps to one endpoint. Pick the surface you need.

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Simulate and query</strong></td><td>Monte Carlo, resolve, query, verify, recommend.</td><td><a href="simulations-and-queries.md">simulations-and-queries.md</a></td></tr>
<tr><td><strong>Decisions and products</strong></td><td>Decision memory plus product decision, optimize, forecast.</td><td><a href="decisions-and-products.md">decisions-and-products.md</a></td></tr>
<tr><td><strong>Connectors and datasets</strong></td><td>Create connectors, onboard and query datasets.</td><td><a href="connectors-and-data.md">connectors-and-data.md</a></td></tr>
<tr><td><strong>Repository intelligence</strong></td><td>Snapshot, triage, graph-query, simulate, apply.</td><td><a href="repositories.md">repositories.md</a></td></tr>
<tr><td><strong>LLM and embeddings</strong></td><td>Models, tokenize, chat, responses, embeddings, rerank.</td><td><a href="llm.md">llm.md</a></td></tr>
</tbody></table>

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Run your first simulation</strong></td><td>Call <code>simulate</code> and read the decision envelope.</td><td><a href="simulations-and-queries.md">simulations-and-queries.md</a></td></tr>
<tr><td><strong>Understand the HTTP contract</strong></td><td>See the endpoints every method calls.</td><td><a href="../../api/overview.md">../../api/overview.md</a></td></tr>
<tr><td><strong>See the full integration guide</strong></td><td>Runtime, CLI, and end-to-end examples.</td><td><a href="../python.md">../python.md</a></td></tr>
</tbody></table>
