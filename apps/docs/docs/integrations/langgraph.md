---
sidebar_position: 3
---

# LangGraph

Add Decision Engine as a tool node in your LangGraph AI agent.

## Installation

```bash
pip install decision-engine-sdk langgraph langchain-openai
```

## Usage

```python
from langchain_core.tools import tool
from decision_engine import DecisionEngineClient

client = DecisionEngineClient(api_key="de_live_...")

@tool
def run_decision_simulation(
    variables: dict,
    objective: str = "maximize_net_value"
) -> dict:
    """Run a Monte Carlo simulation to evaluate a decision scenario."""
    result = client.simulate(
        mode="auto",
        scenario={"variables": variables, "objective": objective}
    )
    return {
        "recommended_action": result.recommended_action,
        "confidence": result.confidence,
        "rationale": result.rationale,
        "expected_value": result.metrics.expected_value,
        "probability_of_loss": result.metrics.probability_of_loss,
    }
```

Full example: [`examples/langgraph/decision_tool.py`](https://github.com/decisionengine/decision-engine/tree/main/examples/langgraph/decision_tool.py)
