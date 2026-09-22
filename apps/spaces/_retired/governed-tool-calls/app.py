"""Algenta governance demo — approve/deny a governed tool call and inspect the execution receipt.

A Hugging Face Space (Gradio) that demonstrates, interactively and deterministically, the
governance semantics of the Algenta decision engine SDK:

- tool profiles `observe` / `govern` / `execute` / `full` control which tools a model ever sees;
- `execute_decision` is the only safety-critical tool: it either returns an `ExecutionReceipt`
  or is blocked synchronously on one of three named policy gates
  (`idempotency`, `confidence`, `risk_floor`) with an `ExecutionDenial` body;
- `force` / `override_safety` are operator-only fields — every `algenta-*` integration package
  strips them from the model-facing schema.

The policy gates and envelopes here replicate the real engine's documented wire shapes (same
field names as the receipts returned by the hosted API and by `algenta-mcp`) against a local,
deterministic, simulated engine — no API key required. To run the real thing, use
`algenta-mcp` (PyPI) or the `algenta-sdk` against https://api.algenta.ai.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import gradio as gr
from design import FORCE_DARK_JS, THEME
from shell import SHELL_CSS, render_footer, render_header

# ---------------------------------------------------------------------------
# Contract constants (mirror contracts/integration-tool-contract.json)
# ---------------------------------------------------------------------------

PROFILE_TOOLS: dict[str, list[str]] = {
    "observe": ["get_contract", "query_data", "simulate", "recommend"],
    "govern": [
        "get_contract",
        "query_data",
        "simulate",
        "recommend",
        "plan_decision",
        "log_decision",
    ],
    "execute": [
        "get_contract",
        "query_data",
        "simulate",
        "recommend",
        "plan_decision",
        "log_decision",
        "execute_decision",
    ],
    "full": ["* (every tool the connected engine's MCP registry advertises)"],
}

PROFILE_DESCRIPTIONS: dict[str, str] = {
    "observe": "Read-only: discovery, exact queries, simulation, recommendations. Default for every algenta-* integration.",
    "govern": "Observe + decision planning and logging. Nothing can be executed.",
    "execute": "Govern + `execute_decision` (human-approved execution of a logged decision).",
    "full": "Everything the connected engine's MCP registry advertises. Opt-in only.",
}

#: Demo policy thresholds, standing in for `policy.min_confidence` / `policy.risk_floor`.
MIN_CONFIDENCE = 0.80
RISK_FLOOR = 0.05


# ---------------------------------------------------------------------------
# Simulated engine — deterministic, same envelopes as the real API
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "decision"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def initial_state() -> dict[str, Any]:
    return {"decisions": {}, "audit": [], "seq": 0}


def _ensure_state(state):
    """Normalize the state argument across UI and API callers.

    UI clicks pass the gr.State dict; API sessions pass None (no page load ran)
    or the initial_state callable itself (Gradio's default injection for the
    state parameter on named API endpoints).
    """
    if state is None:
        return initial_state()
    if callable(state):
        return state()
    return state


def log_decision(chosen_action: str, confidence: float, risk_p5: float, state: dict[str, Any]):
    """Simulated `log_decision` (govern profile): record a decision, return its id."""
    state = _ensure_state(state)
    if not chosen_action.strip():
        return "⚠️ Enter an action to log, e.g. `refund_order_123`.", "", state
    base = f"decision-{_slug(chosen_action)}"
    decision_id = base
    existing = state["decisions"].get(decision_id)
    if existing is not None and existing["chosen_action"] != chosen_action.strip():
        state["seq"] += 1
        decision_id = f"{base}-{state['seq'] + 1}"
    state["decisions"][decision_id] = {
        "decision_id": decision_id,
        "chosen_action": chosen_action.strip(),
        "confidence": round(float(confidence), 3),
        "risk_p5": round(float(risk_p5), 3),
        "logged_at": _now_iso(),
    }
    body = {
        "outcome": "logged",
        **state["decisions"][decision_id],
        "policy": {"min_confidence": MIN_CONFIDENCE, "risk_floor": RISK_FLOOR},
        "next": "Approve it below: `execute_decision` runs the policy gates synchronously.",
    }
    return json.dumps(body, indent=2), decision_id, state


def _denial(code: str, gate: str, message: str, override_hint: str | None) -> dict[str, Any]:
    return {
        "error": {"code": code, "gate": gate, "message": message, "override_hint": override_hint}
    }


def execute_decision(
    profile: str,
    decision_id: str,
    webhook_url: str,
    force: bool,
    override_safety: bool,
    state: dict[str, Any] | None,
):
    """Simulated `execute_decision`: profile interception, then the three real gates."""
    state = _ensure_state(state)
    decision_id = decision_id.strip()
    audit = state["audit"]

    # Layer 1 — integration profile check (client-side, before the engine is ever called).
    if profile not in ("execute", "full"):
        body = _denial(
            "tool_not_in_profile",
            "profile",
            f"`execute_decision` is not exposed under the `{profile}` profile: every algenta-* "
            "integration filters it out of the model-facing tool list and intercepts calls to it.",
            "Raise the integration profile to `execute` to allow human-approved execution.",
        )
        audit.append(
            {
                "at": _now_iso(),
                "decision_id": decision_id,
                "outcome": "intercepted",
                "gate": "profile",
            }
        )
        verdict = (
            f"⛔ INTERCEPTED — `{profile}` profile never exposes `execute_decision` to the model."
        )
        return verdict, json.dumps(body, indent=2), json.dumps(audit, indent=2), state

    decision = state["decisions"].get(decision_id)
    if decision is None:
        body = _denial(
            "decision_not_found",
            "existence",
            f"No logged decision with id `{decision_id}` in this demo session. Log one above first.",
            None,
        )
        audit.append(
            {"at": _now_iso(), "decision_id": decision_id, "outcome": "denied", "gate": "existence"}
        )
        verdict = "⛔ DENIED — unknown decision id."
        return verdict, json.dumps(body, indent=2), json.dumps(audit, indent=2), state

    # Layer 2 — the engine's three named, synchronous policy gates (real wire shapes).
    gates: list[tuple[bool, str, str, str, str]] = [
        (
            decision.get("delivered", False) and not force,
            "execution_blocked_idempotency",
            "idempotency",
            f"Decision `{decision_id}` was already delivered.",
            "Pass force=true (operator only) to override the idempotency gate for one re-execution.",
        ),
        (
            decision["confidence"] < MIN_CONFIDENCE and not override_safety,
            "execution_blocked_confidence",
            "confidence",
            f"Decision confidence {decision['confidence']} is below policy.min_confidence {MIN_CONFIDENCE}.",
            "Pass override_safety=true (operator only) to bypass the confidence gate.",
        ),
        (
            decision["risk_p5"] < -RISK_FLOOR and not override_safety,
            "execution_blocked_risk_floor",
            "risk_floor",
            f"risk_p5 {decision['risk_p5']} is below -policy.risk_floor ({-RISK_FLOOR}).",
            "Pass override_safety=true (operator only) to bypass the risk floor gate.",
        ),
    ]
    for blocked, code, gate, message, hint in gates:
        if blocked:
            body = _denial(code, gate, message, hint)
            audit.append(
                {"at": _now_iso(), "decision_id": decision_id, "outcome": "denied", "gate": gate}
            )
            verdict = f"⛔ DENIED by policy gate `{gate}` — synchronous, in the same call. No execution happened."
            return verdict, json.dumps(body, indent=2), json.dumps(audit, indent=2), state

    decision["delivered"] = True
    receipt = {
        "decision_id": decision_id,
        "webhook_url": webhook_url.strip() or "https://example.org/hooks/demo",
        "execution_status": "delivered",
        "response_code": 200,
        "executed_at": _now_iso(),
        "policy_snapshot_id": "policy-snap-demo-1",
        "schema_snapshot_id": "schema-snap-demo-1",
        "manifest_version": "1.0.13",
        "payload_summary": {"chosen_action": decision["chosen_action"]},
        "safety_overridden": bool(override_safety),
    }
    audit.append(
        {"at": _now_iso(), "decision_id": decision_id, "outcome": "delivered", "gate": None}
    )
    verdict = "✅ APPROVED — all policy gates cleared. Execution receipt returned synchronously:"
    return verdict, json.dumps(receipt, indent=2), json.dumps(audit, indent=2), state


def profile_summary(profile: str) -> str:
    tools = "\n".join(f"- `{t}`" for t in PROFILE_TOOLS[profile])
    return f"**`{profile}`** — {PROFILE_DESCRIPTIONS[profile]}\n\nModel-facing tools:\n{tools}"


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

SMOLAGENTS_SNIPPET = """\
# Consume the real governed tools from smolagents via algenta-mcp (PyPI: algenta-mcp,
# MCP Registry: io.github.thyn-ai/algenta). No separate protocol package needed.
from smolagents import CodeAgent, InferenceClientModel, ToolCollection
from mcp import StdioServerParameters
import os

server_parameters = StdioServerParameters(
    command="uvx",
    args=["algenta-mcp"],
    env={
        "ALGENTA_API_KEY": os.environ["ALGENTA_API_KEY"],
        "ALGENTA_BASE_URL": "https://api.algenta.ai",
        **os.environ,
    },
)

with ToolCollection.from_mcp(server_parameters, trust_remote_code=True) as tools:
    agent = CodeAgent(tools=[*tools.tools], model=InferenceClientModel(), add_base_tools=False)
    agent.run("Query gross revenue for the orders dataset, then log a decision about it.")

# Or load the observe-profile Hub tool directly:
from smolagents import load_tool
algenta_query = load_tool("thyn-ai/algenta-governed-query", trust_remote_code=True)
"""

# Canonical Algenta dark theme (THEME) lives in design.py; the page chrome
# (header/footer) is the canonical fleet shell from shell.py. Badges carry the
# honesty claims: verified wire shapes ("ok"), simulated engine ("warn").

HEADER_HTML = render_header(
    title="Algenta Governed Tool Calls",
    tagline="Governed tool calls with execution receipts",
    badges=[
        (
            "receipts & denials verified against the real API's wire shapes",
            "ok",
        ),
        (
            "SIMULATED engine — deterministic, no API key, no real side effects",
            "warn",
        ),
    ],
    active="Governed tool calls",
)


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Algenta — governed tool calls", fill_width=True) as demo:
        gr.HTML(HEADER_HTML)
        state = gr.State(initial_state)

        with gr.Tab("Approve / deny a governed tool call"):
            profile = gr.Radio(
                choices=["observe", "govern", "execute", "full"],
                value="observe",
                label="Tool profile (what the model is allowed to see)",
            )
            profile_md = gr.Markdown(profile_summary("observe"))
            profile.change(profile_summary, profile, profile_md)

            gr.Markdown("### 1 · Log a decision (govern profile)")
            with gr.Row():
                action = gr.Textbox(label="Chosen action", value="refund_order_123", scale=2)
                confidence = gr.Slider(0.0, 1.0, value=0.93, step=0.01, label="Confidence")
                risk_p5 = gr.Slider(
                    -0.5, 0.5, value=0.02, step=0.01, label="risk_p5 (5th-percentile outcome)"
                )
            log_btn = gr.Button("log_decision", variant="secondary")
            logged_json = gr.Code(label="log_decision result", language="json")
            decision_id = gr.Textbox(label="decision_id", interactive=True)

            gr.Markdown("### 2 · Approve and execute (execute profile)")
            with gr.Row():
                webhook_url = gr.Textbox(
                    label="webhook_url (delivery target)",
                    value="https://example.org/hooks/orders",
                    scale=2,
                )
                force = gr.Checkbox(label="force (operator only)", value=False)
                override_safety = gr.Checkbox(label="override_safety (operator only)", value=False)
            gr.Markdown(
                "`force` / `override_safety` exist on the real schema for operators only — every "
                "`algenta-*` integration strips them from the model-facing tool schema."
            )
            exec_btn = gr.Button("execute_decision (human-approved)", variant="primary")
            verdict = gr.Markdown()
            result_json = gr.Code(label="ExecutionReceipt or ExecutionDenial", language="json")

        with gr.Tab("Audit log"):
            audit_json = gr.Code(
                label="Every outcome this session (append-only)", language="json", value="[]"
            )

        with gr.Tab("Use from smolagents"):
            gr.Markdown(
                "The same governed tools are consumable by Hugging Face **smolagents** through the "
                "Model Context Protocol. `algenta-mcp` is on PyPI and on the official MCP Registry "
                "as `io.github.thyn-ai/algenta`."
            )
            gr.Code(value=SMOLAGENTS_SNIPPET, language="python", label="smolagents + algenta-mcp")

        gr.HTML(render_footer())

        log_btn.click(
            log_decision, [action, confidence, risk_p5, state], [logged_json, decision_id, state]
        )
        exec_btn.click(
            execute_decision,
            [profile, decision_id, webhook_url, force, override_safety, state],
            [verdict, result_json, audit_json, state],
        )

    return demo


demo = build_demo()

if __name__ == "__main__":
    demo.launch(show_error=True, theme=THEME, css=SHELL_CSS, js=FORCE_DARK_JS)
