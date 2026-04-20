"""
LangGraph integration — Decision Engine tool wrapper.

This module provides @tool decorated functions that wrap the Decision Engine API
for use in LangGraph agent workflows.

Setup:
    pip install langchain-core decision-engine-sdk
    export DE_API_KEY=de_live_...

Usage:
    from examples.langgraph.decision_tool import simulate_decision, recommend_action

    # Use as LangGraph tool in an agent graph
    tools = [simulate_decision, recommend_action]
"""
import json
import os
import urllib.request
from typing import Any

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("DE_API_KEY", "")


def _api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Internal HTTP helper — no external dependencies."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())  # type: ignore[return-value]


# ── Try to import LangChain tool decorator ────────────────────────────────────
try:
    from langchain_core.tools import tool as _tool
    _HAS_LANGCHAIN = True
except ImportError:
    # Fallback: just use as regular Python functions
    def _tool(fn):  # type: ignore[misc]
        return fn
    _HAS_LANGCHAIN = False


@_tool
def simulate_decision(
    variables: dict[str, dict[str, float]],
    objective: str = "maximize_net_value",
    runs: int = 10000,
) -> str:
    """
    Simulate a decision scenario using Monte Carlo analysis.

    Use this tool when you need to:
    - Evaluate the expected outcome of a business decision
    - Quantify risk and uncertainty in a scenario
    - Get a probability-weighted recommendation

    Args:
        variables: Dict of variable names to {low, high} bounds.
                   Example: {"revenue": {"low": 80000, "high": 200000}}
        objective: Optimization objective (maximize_net_value, maximize_revenue, minimize_cost)
        runs: Number of Monte Carlo iterations (default: 10000)

    Returns:
        JSON string with recommended_action, confidence, expected_value, probability_of_loss
    """
    result = _api("POST", "/v1/simulate", {
        "mode": "auto",
        "scenario": {
            "variables": variables,
            "objective": objective,
        },
        "runs": runs,
    })
    # Return clean summary for LLM consumption
    return json.dumps({
        "recommended_action": result.get("recommended_action"),
        "confidence": result.get("confidence"),
        "rationale": result.get("rationale"),
        "expected_value": result.get("metrics", {}).get("expected_value"),
        "probability_of_loss": result.get("metrics", {}).get("probability_of_loss"),
        "p5_downside": result.get("percentiles", {}).get("p5"),
        "p95_upside": result.get("percentiles", {}).get("p95"),
        "scenarios_run": result.get("scenarios_run"),
    }, indent=2)


@_tool
def recommend_action(
    actions: list[dict[str, Any]],
    runs: int = 10000,
) -> str:
    """
    Compare multiple named actions and get a ranked recommendation.

    Use this tool when you need to:
    - Choose between two or more options with uncertainty
    - Rank alternatives by expected value and risk

    Args:
        actions: List of {name, variables, objective} dicts to compare.
                 Example: [{"name": "option_a", "variables": {"revenue": {"low": 80000, "high": 200000}}, "objective": "maximize_net_value"}]
        runs: Number of Monte Carlo iterations per action (default: 10000)

    Returns:
        JSON string with recommended_action and ranked list of alternatives
    """
    formatted_actions = []
    for action in actions:
        formatted_actions.append({
            "name": action["name"],
            "request": {
                "mode": "auto",
                "scenario": {
                    "variables": action.get("variables", {}),
                    "objective": action.get("objective", "maximize_net_value"),
                },
                "runs": runs,
            },
        })

    result = _api("POST", "/v1/recommend", {"actions": formatted_actions})
    return json.dumps({
        "recommended_action": result.get("recommended_action"),
        "confidence": result.get("confidence"),
        "rationale": result.get("rationale"),
        "ranking": [
            {
                "rank": a.get("rank"),
                "name": a.get("name"),
                "expected_value": a.get("expected_value"),
                "score": a.get("score"),
            }
            for a in result.get("action_results", [])
        ],
    }, indent=2)


# ── Example agent usage ───────────────────────────────────────────────────────

EXAMPLE_AGENT_CODE = '''
"""Example LangGraph agent using Decision Engine tools."""
import os
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from examples.langgraph.decision_tool import simulate_decision, recommend_action

# Create agent with Decision Engine tools
llm = ChatOpenAI(model="gpt-4o")
tools = [simulate_decision, recommend_action]
agent = create_react_agent(llm, tools)

# Run agent
result = agent.invoke({
    "messages": [
        {"role": "user", "content": (
            "We are deciding whether to launch Product A (revenue: $80k-200k, cost: $40k-90k) "
            "or Product B (revenue: $50k-300k, cost: $60k-120k). "
            "Which option has better expected value? Use the decision simulation tools."
        )}
    ]
})
print(result["messages"][-1].content)
'''

if __name__ == "__main__":
    # Quick test without LangChain
    print("Testing Decision Engine LangGraph tool directly...\n")
    result = simulate_decision(  # type: ignore[call-arg]
        variables={"revenue": {"low": 80000, "high": 200000}, "cost": {"low": 40000, "high": 90000}},
        objective="maximize_net_value",
        runs=5000,
    )
    print("simulate_decision result:")
    print(result)
    print("\nAgent usage example:")
    print(EXAMPLE_AGENT_CODE)
