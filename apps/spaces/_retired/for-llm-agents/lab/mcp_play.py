"""Tab 4 — MCP playground: algenta-mcp as a real MCP server.

The tool registry shown here is the REAL one: names, descriptions and input
schemas read from the published algenta-mcp 1.0.17 PyPI package and vendored
into this Space (scripts/dump_mcp_tools.py), so nothing is invented. The
initialize / tools-list frames are the JSON-RPC envelopes a real MCP client
exchanges with the server, rendered from that vendored registry (no live stdio
server runs inside the Space). The "call it" runner executes read-only demo
tools against the SIMULATED engine (tab 3's engine) and shows the raw
request/response frames plus the engine's receipt envelope.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "algenta_mcp_tools.json"

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "algenta-mcp"

#: The observe-profile read-only tools the runner supports, with the demo
#: arguments shown in the request frame. Deterministic — same args every call.
CALLABLE_DEMO_TOOLS: dict[str, dict[str, Any]] = {
    "get_contract": {},
    "query_data": {
        "source": "orders",
        "intent": "gross revenue by month for the current year",
        "limit": 5,
    },
    "simulate": {
        "variables": {
            "price": {"distribution": "normal", "mean": 49.0, "sd": 4.0},
            "volume": {"distribution": "uniform", "min": 900, "max": 1400},
        },
        "expression": "price * volume",
        "runs": 10_000,
    },
    "recommend": {
        "actions": ["full_refund", "replacement_shipment", "store_credit"],
        "context": "customer never received order #123 ($19.99)",
    },
}

_cache: dict = {}


def registry() -> dict:
    if "registry" not in _cache:
        _cache["registry"] = json.loads(DATA_PATH.read_text())
    return _cache["registry"]


def package_version() -> str:
    return registry()["package_version"]


def profile_tools(profile: str) -> list[str] | str:
    """Tools a profile exposes; `full` = the whole registry (per the contract)."""
    if profile == "full":
        return "* (every tool the connected engine's MCP registry advertises — 140 in algenta-mcp 1.0.17)"
    return registry()["profile_tools"][profile]


def tool_table(profile: str):
    """Dataframe rows for the registry browser, filtered by profile."""
    import pandas as pd

    tools = registry()["tools"]
    if profile != "full":
        allowed = set(profile_tools(profile))
        tools = [t for t in tools if t["name"] in allowed]
    rows = [
        {
            "tool": t["name"],
            "description": (t["description"][:150] + "…")
            if len(t["description"]) > 150
            else t["description"],
            "required args": ", ".join(t["required"]) or "—",
        }
        for t in tools
    ]
    return pd.DataFrame(rows, columns=["tool", "description", "required args"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mcp_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in registry()["tools"]
    ]


def mcp_frame(kind: str) -> str:
    """The JSON-RPC frames a real MCP client exchanges with algenta-mcp."""
    if kind == "initialize":
        frames = {
            "request": {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                    "clientInfo": {"name": "demo-mcp-client", "version": "1.0.0"},
                },
            },
            "response": {
                "jsonrpc": "2.0",
                "id": 0,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": package_version()},
                },
            },
        }
    elif kind == "tools_list":
        frames = {
            "request": {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            "response": {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": _mcp_tool_specs()},
            },
        }
    else:
        frames = {"error": f"unknown frame kind {kind!r}"}
    return json.dumps(frames, indent=2)


# ---------------------------------------------------------------------------
# Simulated engine: deterministic read-only tool implementations
# ---------------------------------------------------------------------------


def _sim_get_contract(_args: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "contract": "algenta-public-contract",
        "contract_version": "1.2.0-demo",
        "profiles": {
            "observe": {"tools": registry()["profile_tools"]["observe"], "default": True},
            "govern": {"tools": registry()["profile_tools"]["govern"]},
            "execute": {"tools": registry()["profile_tools"]["execute"]},
            "full": {"tools": "*"},
        },
        "operator_only_fields": ["force", "override_safety"],
        "note": "SIMULATED contract document — same shape as the real get_contract response.",
    }


def _sim_query_data(args: dict[str, Any]) -> dict[str, Any]:
    seed = int(hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    months = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
    rows = [
        {"month": m, "gross_revenue_usd": round(rng.uniform(180_000, 260_000), 2)}
        for m in months[: args.get("limit", 5)]
    ]
    return {
        "source": args.get("source"),
        "intent": args.get("intent"),
        "rows": rows,
        "row_count": len(rows),
        "engine": "simulated",
        "seed": seed,
    }


def _sim_simulate(args: dict[str, Any]) -> dict[str, Any]:
    runs = int(args.get("runs", 10_000))
    rng = random.Random(20260920)
    values = sorted(rng.gauss(49.0, 4.0) * rng.uniform(900, 1400) for _ in range(runs))
    return {
        "expression": args.get("expression"),
        "runs": runs,
        "p5": round(values[int(0.05 * runs)], 2),
        "p50": round(values[int(0.50 * runs)], 2),
        "p95": round(values[int(0.95 * runs)], 2),
        "mean": round(sum(values) / runs, 2),
        "seed": 20260920,
        "engine": "simulated",
    }


def _sim_recommend(args: dict[str, Any]) -> dict[str, Any]:
    ranked = [
        {
            "action": "replacement_shipment",
            "score": 0.91,
            "why": "preserves margin; customer gets the item",
        },
        {"action": "full_refund", "score": 0.83, "why": "fastest resolution; loses the sale"},
        {
            "action": "store_credit",
            "score": 0.64,
            "why": "retains revenue; slowest for the customer",
        },
    ]
    ranked = [r for r in ranked if r["action"] in set(args.get("actions", []))] or ranked
    return {
        "context": args.get("context"),
        "ranked": ranked,
        "recommended": ranked[0]["action"],
        "engine": "simulated",
    }


_SIM_HANDLERS = {
    "get_contract": _sim_get_contract,
    "query_data": _sim_query_data,
    "simulate": _sim_simulate,
    "recommend": _sim_recommend,
}


def mcp_call(tool_name: str) -> tuple[str, str]:
    """Run one read-only demo tool against the simulated engine. Never raises."""
    try:
        if tool_name not in CALLABLE_DEMO_TOOLS:
            return "", (
                f"⚠️ `{tool_name}` is not one of the read-only demo tools. "
                "The playground runs observe-profile tools only."
            )
        args = CALLABLE_DEMO_TOOLS[tool_name]
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
        result_payload = _SIM_HANDLERS[tool_name](args)
        receipt = {
            "tool": tool_name,
            "profile": "observe",
            "engine": "simulated (real wire shapes)",
            "receipt_id": "rcpt-demo-" + hashlib.sha256(tool_name.encode()).hexdigest()[:12],
            "at": _now_iso(),
            "policy_gates": [],
            "note": "observe-profile tools are read-only: no policy gates fire; "
            "execute_decision is where denials/receipts happen (see tab 3).",
        }
        response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result_payload, indent=2)}],
                "isError": False,
            },
        }
        frames = {"request": request, "response": response}
        return json.dumps(frames, indent=2), json.dumps(receipt, indent=2)
    except Exception as exc:
        return "", f"⏸️ **call held** — {type(exc).__name__}: {exc}."


def demo_args_preview(tool_name: str) -> str:
    if tool_name not in CALLABLE_DEMO_TOOLS:
        return ""
    return json.dumps({tool_name: CALLABLE_DEMO_TOOLS[tool_name]}, indent=2)
