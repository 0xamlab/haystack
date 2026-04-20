# Algenta — Azure AI Foundry and Studio

Use Algenta from Azure-hosted copilots, prompt flows, and assistant-style agents.

## Recommended paths

- OpenAPI import for action-style use
- Function tool or Prompt Flow node for controlled orchestration

## Option A: Azure OpenAI Assistants (Function Calling)

### 1. Register the Tool

Upload `algenta_tool_definition.json` as a function tool in your Azure OpenAI Assistant configuration.

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

ALGENTA_KEY = os.environ["ALGENTA_API_KEY"]
ALGENTA_URL = "https://api.algenta.ai"


def call_algenta(arguments: dict) -> str:
    """Execute Algenta simulation and return formatted result."""
    mode = arguments.get("mode", "auto")
    payload = {
        "mode": mode,
        "runs": arguments.get("runs", 50000),
        "seed": arguments.get("seed", 42),
    }

    if mode == "auto":
        payload["scenario"] = {
            "name": arguments.get("name", "Decision Analysis"),
            "variables": arguments.get("variables", {}),
            "objective": arguments.get("objective", "maximize_net_value"),
        }

    if arguments.get("simulation_model"):
        payload["simulation_model"] = arguments["simulation_model"]

    resp = requests.post(
        f"{ALGENTA_URL}/v1/simulate",
        headers={"Authorization": f"Bearer {ALGENTA_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()

    return json.dumps({
        "recommended_action": result["recommended_action"],
        "confidence": result["confidence"],
        "rationale": result["rationale"],
        "expected_value": result["metrics"]["expected_value"],
        "probability_of_loss": result["metrics"]["probability_of_loss"],
        "var_95": result["metrics"].get("var_95"),
        "scenarios_run": result["scenarios_run"],
        "result_hash": result.get("result_hash"),
    }, indent=2)


# ── Run Assistant with tool ─────────────────────────────────────────────────
import json

with open("algenta_tool_definition.json") as f:
    tool_def = json.load(f)

assistant = client.beta.assistants.create(
    model="gpt-4o",
    instructions=(
        "You are a strategic decision advisor. When asked about business decisions, "
        "market expansion, investment analysis, or risk assessment, use the "
        "algenta_simulate tool to run probabilistic simulations and provide "
        "data-driven recommendations."
    ),
    tools=[{"type": "function", "function": tool_def}],
)

thread = client.beta.threads.create()
client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content=(
        "Should we expand to the European market? "
        "Revenue potential: $500K-$2M, expansion cost: $300K-$800K, "
        "probability of regulatory issues: moderate."
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
        result = call_algenta(args)
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
    Algenta Decision Engine simulation tool for Azure Prompt Flow.

    Args:
        variables: Dict of variable name → {low, high} ranges
        objective: maximize_net_value | minimize_risk | etc.
        runs: Number of Monte Carlo scenarios

    Returns:
        Decision envelope with recommendation, confidence, and metrics
    """
    resp = requests.post(
        "https://api.algenta.ai/v1/simulate",
        headers={
            "Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}",
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
ALGENTA_API_KEY=de_live_...  # From https://app.algenta.ai/dashboard/api-keys
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=...
```

## First validation

Use one simple simulation request first, confirm Bearer auth works, then add dataset or write-capable actions afterward.
