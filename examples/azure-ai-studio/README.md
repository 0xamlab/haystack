# Algenta — Azure AI Foundry and Studio

Use Algenta from Azure-hosted copilots, prompt flows, and assistant-style agents.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

All snippets below resolve `ALGENTA_URL` from `ALGENTA_BASE_URL`,
`DE_BASE_URL`, or `ALGENTA_API_URL`. In Cloud Managed, set that to
`https://api.algenta.ai`. In `self_hosted` and `air_gapped`, set it to your
self-hosted base URL and use the API key provisioned by your self-hosted
operator deployment.

## Recommended paths

- Function tool for live contract inspection before discovery
- OpenAPI import for full hosted action coverage
- Function tool for governed dataset discovery and exact query
- Function tool for constrained read-only SQL reports
- Function tool for simulation when the flow is doing decision analysis
- Prompt Flow node for controlled orchestration

## Option A0: Azure OpenAI Assistants (Function Calling) — Contract Tool

### 1. Register the Tool

Upload `algenta_contract_tool_definition.json` as a function tool in your Azure
OpenAI Assistant configuration.

### 2. Implement the Function Handler

```python
import json
import os
import requests

ALGENTA_KEY = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not ALGENTA_KEY:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
ALGENTA_URL = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or os.environ.get("ALGENTA_API_URL")
)
if not ALGENTA_URL:
    raise RuntimeError(
        "Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example. "
        "Use https://api.algenta.ai only in Cloud Managed."
    )


def call_algenta_contract() -> str:
    resp = requests.get(
        f"{ALGENTA_URL}/v1/meta/contract",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
        timeout=30,
    )
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)
```

Use this tool first when the assistant needs the live discovery, summary, exact
query, batch, SQL-report, CLI, or MCP contract exposed by the running service.
If an older self-hosted node still returns `404` for `/v1/meta/contract`, fetch
`/openapi.json` and read `x-primary-data-query-contract` instead.

## Option A1: Azure OpenAI Assistants (Function Calling) — Exact Query Tool

### 1. Register the Tool

Upload `algenta_query_tool_definition.json` as a function tool in your Azure OpenAI Assistant configuration.

### 2. Implement the Function Handler

```python
import os
import json
import requests
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_KEY"],
    api_version="2024-05-01-preview",
)

ALGENTA_KEY = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not ALGENTA_KEY:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
ALGENTA_URL = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or os.environ.get("ALGENTA_API_URL")
)
if not ALGENTA_URL:
    raise RuntimeError(
        "Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example. "
        "Use https://api.algenta.ai only in Cloud Managed."
    )


def call_algenta_query(arguments: dict) -> str:
    """Discover one dataset, fetch its summary, then run one exact query or query batch."""
    contract_resp = requests.get(
        f"{ALGENTA_URL}/v1/meta/contract",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
        timeout=30,
    )
    contract_resp.raise_for_status()
    contract = contract_resp.json()

    dataset_id = arguments.get("dataset_id")
    if not dataset_id:
        search = arguments.get("dataset_search", "otp")
        search_resp = requests.get(
            f"{ALGENTA_URL}/v1/data",
            headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
            params={"search": search, "compact": True, "limit": 5},
            timeout=30,
        )
        search_resp.raise_for_status()
        datasets = search_resp.json().get("datasets", [])
        if not datasets:
            return json.dumps({"error": f"No dataset matched search '{search}'."}, indent=2)
        dataset_id = datasets[0]["dataset_id"]

    summary_resp = requests.get(
        f"{ALGENTA_URL}/v1/data/{dataset_id}/summary",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
        timeout=30,
    )
    summary_resp.raise_for_status()
    summary = summary_resp.json()

    batch_queries = arguments.get("batch_queries") or []
    if batch_queries:
        payload = {
            "defaults": {"dataset_id": dataset_id},
            "queries": [
                {
                    "key": item["key"],
                    "request": {
                        "metric": {
                            "role": item.get("metric_role", "metric"),
                            "hint": item["metric_hint"],
                        },
                        **({"aggregation": item["aggregation"]} if item.get("aggregation") else {}),
                        **({"group_by": item["group_by"]} if item.get("group_by") else {}),
                        **({"filter": item["filter"]} if item.get("filter") else {}),
                        **({"limit": item["limit"]} if item.get("limit") else {}),
                        **({"order": item["order"]} if item.get("order") else {}),
                    },
                }
                for item in batch_queries
            ],
        }
        query_resp = requests.post(
            f"{ALGENTA_URL}/v1/query/batch",
            headers={"Authorization": f"Bearer {ALGENTA_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
    else:
        payload = {
            "dataset_id": dataset_id,
            "metric": {
                "role": arguments.get("metric_role", "metric"),
                "hint": arguments["metric_hint"],
            },
            "limit": arguments.get("limit", 12),
            "order": arguments.get("order", "desc"),
        }
        if arguments.get("aggregation"):
            payload["aggregation"] = arguments["aggregation"]
        if arguments.get("group_by"):
            payload["group_by"] = arguments["group_by"]
        if arguments.get("filter"):
            payload["filter"] = arguments["filter"]
        query_resp = requests.post(
            f"{ALGENTA_URL}/v1/query",
            headers={"Authorization": f"Bearer {ALGENTA_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )

    query_resp.raise_for_status()
    result = query_resp.json()

    return json.dumps(
        {
            "contract": {
                "contract_endpoint": contract["primary_data_query_contract"]["api"]["contract_endpoint"],
                "discovery_endpoint": contract["primary_data_query_contract"]["api"]["discovery_endpoint"],
                "query_batch_endpoint": contract["primary_data_query_contract"]["api"]["query_batch_endpoint"],
            },
            "dataset_id": dataset_id,
            "dataset_name": summary["name"],
            "summary": summary,
            "result": result,
        },
        indent=2,
    )


# ── Run Assistant with tool ─────────────────────────────────────────────────
import json

with open("algenta_query_tool_definition.json") as f:
    tool_def = json.load(f)

with open("algenta_contract_tool_definition.json") as f:
    contract_tool_def = json.load(f)

assistant = client.beta.assistants.create(
    model="gpt-4o",
    instructions=(
        "You are a data analyst. Inspect the live Algenta contract first, then use "
        "the Algenta query tool for KPIs, metrics, or operational facts over connected "
        "data. Start with dataset discovery, use low-token summaries, then run governed "
        "exact queries."
    ),
    tools=[
        {"type": "function", "function": contract_tool_def},
        {"type": "function", "function": tool_def},
    ],
)

thread = client.beta.threads.create()
client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content=(
        "Inspect the live Algenta contract, then find the dataset that matches OTP, "
        "summarize it, and return the overall OTP rate plus a monthly breakdown for "
        "the last 12 months."
    ),
)

run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=assistant.id,
)

# Handle function calls
if run.status == "requires_action":
    tool_calls = run.required_action.submit_tool_outputs.tool_calls
    outputs = []
    for tc in tool_calls:
        args = json.loads(tc.function.arguments)
        result = call_algenta_query(args)
        outputs.append({"tool_call_id": tc.id, "output": result})

    run = client.beta.threads.runs.submit_tool_outputs_and_poll(
        thread_id=thread.id,
        run_id=run.id,
        tool_outputs=outputs,
    )

# Get response
messages = client.beta.threads.messages.list(thread_id=thread.id)
print(messages.data[0].content[0].text.value)
```

## Option A2: Azure OpenAI Assistants (Function Calling) — SQL Report Tool

Use `algenta_sql_report_tool_definition.json` when the Azure assistant needs a
wide read-only rowset over an already authorized dataset instead of one exact
metric query or exact-query batch.

### 1. Register the Tool

Upload `algenta_sql_report_tool_definition.json` as a function tool in your
Azure OpenAI Assistant configuration.

### 2. Implement the Function Handler

```python
import json
import os
import requests

ALGENTA_KEY = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not ALGENTA_KEY:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
ALGENTA_URL = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or os.environ.get("ALGENTA_API_URL")
)
if not ALGENTA_URL:
    raise RuntimeError(
        "Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example. "
        "Use https://api.algenta.ai only in Cloud Managed."
    )


def call_algenta_sql_report(arguments: dict) -> str:
    """Discover one dataset, fetch its summary, then run one constrained SQL report."""
    contract_resp = requests.get(
        f"{ALGENTA_URL}/v1/meta/contract",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
        timeout=30,
    )
    contract_resp.raise_for_status()
    contract = contract_resp.json()

    dataset_id = arguments.get("dataset_id")
    if not dataset_id:
        search = arguments.get("dataset_search", "otp")
        search_resp = requests.get(
            f"{ALGENTA_URL}/v1/data",
            headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
            params={"search": search, "compact": True, "limit": 5},
            timeout=30,
        )
        search_resp.raise_for_status()
        datasets = search_resp.json().get("datasets", [])
        if not datasets:
            return json.dumps({"error": f"No dataset matched search '{search}'."}, indent=2)
        dataset_id = datasets[0]["dataset_id"]

    summary_resp = requests.get(
        f"{ALGENTA_URL}/v1/data/{dataset_id}/summary",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}"},
        timeout=30,
    )
    summary_resp.raise_for_status()
    summary = summary_resp.json()

    alias = arguments.get("alias", "dataset")
    sql_report_resp = requests.post(
        f"{ALGENTA_URL}/v1/query/sql-report",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}", "Content-Type": "application/json"},
        json={
            "sources": [{"dataset_id": dataset_id, "alias": alias}],
            "sql": arguments["sql"],
            "max_rows": arguments.get("max_rows", 100),
        },
        timeout=60,
    )
    sql_report_resp.raise_for_status()
    result = sql_report_resp.json()

    return json.dumps(
        {
            "contract": {
                "contract_endpoint": contract["primary_data_query_contract"]["api"]["contract_endpoint"],
                "sql_report_endpoint": contract["primary_data_query_contract"]["api"]["query_sql_report_endpoint"],
            },
            "dataset_id": dataset_id,
            "dataset_name": summary["name"],
            "summary": summary,
            "result": result,
        },
        indent=2,
    )
```

Use this tool only when the Azure agent needs a wide rowset that does not fit
one exact governed metric or exact-query batch. Keep it separate from
`algenta_query_tool_definition.json`.

## Option A3: Azure OpenAI Assistants — Simulation Tool

Use `algenta_tool_definition.json` when the Azure assistant is doing decision
analysis rather than governed dataset queries. That tool stays on the hosted
`/v1/simulate` surface.

## Option B: Azure AI Prompt Flow — Python Node

Add this as a Python node in your Prompt Flow:

```python
import requests
import os
from promptflow.core import tool

@tool
def algenta_simulate(
    variables: dict,
    objective: str = "maximize_net_value",
    runs: int = 50000
) -> dict:
    """
    Algenta simulation tool for Azure Prompt Flow.

    Args:
        variables: Dict of variable name → {low, high} ranges
        objective: maximize_net_value | minimize_risk | etc.
        runs: Number of Monte Carlo scenarios

    Returns:
        Decision envelope with recommendation, confidence, and metrics
    """
    api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
    base_url = (
        os.environ.get("ALGENTA_BASE_URL")
        or os.environ.get("DE_BASE_URL")
        or os.environ.get("ALGENTA_API_URL")
    )
    if not base_url:
        raise RuntimeError(
            "Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example. "
            "Use https://api.algenta.ai only in Cloud Managed."
        )
    resp = requests.post(
        f"{base_url}/v1/simulate",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "mode": "auto",
            "runs": runs,
            "scenario": {
                "variables": variables,
                "objective": objective,
            }
        },
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()

    return {
        "action": result["recommended_action"],
        "confidence": result["confidence"],
        "expected_value": result["metrics"]["expected_value"],
        "prob_of_loss": result["metrics"]["probability_of_loss"],
        "rationale": result["rationale"],
        "result_hash": result.get("result_hash"),
    }
```

## Environment Variables

Set in your Azure AI Studio environment:

```bash
ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>  # Cloud Managed only; use a self-hosted-issued key in private profiles
ALGENTA_BASE_URL=https://api.algenta.ai  # Cloud Managed only; replace with your self-hosted base URL in private profiles
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=...
```

Canonical key env var is `ALGENTA_API_KEY`. Legacy `DE_API_KEY` remains
accepted for compatibility in the snippets above.
Canonical base URL env var is `ALGENTA_BASE_URL`. Legacy `DE_BASE_URL` and
`ALGENTA_API_URL` remain accepted for compatibility in the snippets above.

## First validation

Validate the read-only data path first:

1. `GET /v1/data?search=orders&compact=1`
2. `GET /v1/data/{dataset_id}/summary`
3. `POST /v1/query` or `POST /v1/query/batch`

Then add `algenta_sql_report_tool_definition.json` or simulation only if the Azure flow really needs them.
