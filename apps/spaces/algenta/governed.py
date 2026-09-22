"""Governed-execution engine adapter — one interface, two backends.

The UI talks to `GovernedEngine` only. Which backend serves it is decided by
the environment, with zero UI change:

* `ALGENTA_API_KEY` present  → `HostedEngine`: real calls to the Algenta API
  through the published `algenta-sdk` client (`decision_engine.AlgentaClient`),
  against `ALGENTA_BASE_URL` (default https://api.algenta.ai). Receipts and
  denials are the engine's own, normalized into the same display envelopes.
* otherwise                → `DemoEngine`: the deterministic demo engine from
  the governed-tool-calls Space. It replicates the production API's wire
  shapes (same field names, same three named policy gates) against a local
  in-session store. The UI labels this mode honestly on every render.

Both backends are intentionally small and deterministic in behavior: the demo
path is fully deterministic per session; the hosted path's behavior is the
real engine's.
"""

from __future__ import annotations

import os
import re
import threading
from datetime import UTC, datetime
from typing import Any

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

DEMO_MODE_LABEL = (
    "DEMO ENGINE — deterministic demo engine with the production API's wire shapes. "
    "Set the ALGENTA_API_KEY Space secret to run this same UI against a real tenant."
)
HOSTED_MODE_LABEL = "LIVE — real tenant via algenta-sdk"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def initial_state() -> dict[str, Any]:
    return {"decisions": {}, "audit": [], "seq": 0}


def ensure_state(state: Any) -> dict[str, Any]:
    """Normalize the state argument across UI and API callers."""
    if state is None:
        return initial_state()
    if callable(state):
        return state()
    return state


# ---------------------------------------------------------------------------
# Demo engine — deterministic, same envelopes as the real API
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "decision"


class DemoEngine:
    """The proven deterministic demo engine (governed-tool-calls Space shapes)."""

    mode = "demo"
    mode_label = DEMO_MODE_LABEL

    def log_decision(
        self, chosen_action: str, confidence: float, risk_p5: float, state: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        state = ensure_state(state)
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
        return body, decision_id

    def execute_decision(
        self,
        profile: str,
        decision_id: str,
        webhook_url: str,
        force: bool,
        override_safety: bool,
        state: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        state = ensure_state(state)
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
                f"INTERCEPTED — `{profile}` profile never exposes `execute_decision` to the model."
            )
            return verdict, body

        decision = state["decisions"].get(decision_id)
        if decision is None:
            body = _denial(
                "decision_not_found",
                "existence",
                f"No logged decision with id `{decision_id}` in this demo session. Log one above first.",
                None,
            )
            audit.append(
                {
                    "at": _now_iso(),
                    "decision_id": decision_id,
                    "outcome": "denied",
                    "gate": "existence",
                }
            )
            verdict = "DENIED — unknown decision id."
            return verdict, body

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
                    {
                        "at": _now_iso(),
                        "decision_id": decision_id,
                        "outcome": "denied",
                        "gate": gate,
                    }
                )
                verdict = f"DENIED by policy gate `{gate}` — synchronous, in the same call. No execution happened."
                return verdict, body

        decision["delivered"] = True
        receipt = {
            "decision_id": decision_id,
            "webhook_url": webhook_url.strip() or "https://example.org/hooks/demo",
            "execution_status": "delivered",
            "response_code": 200,
            "executed_at": _now_iso(),
            "policy_snapshot_id": "policy-snap-demo-1",
            "schema_snapshot_id": "schema-snap-demo-1",
            "manifest_version": "1.0.18",
            "payload_summary": {"chosen_action": decision["chosen_action"]},
            "safety_overridden": bool(override_safety),
        }
        audit.append(
            {"at": _now_iso(), "decision_id": decision_id, "outcome": "delivered", "gate": None}
        )
        verdict = "APPROVED — all policy gates cleared. Execution receipt returned synchronously:"
        return verdict, receipt


def _denial(code: str, gate: str, message: str, override_hint: str | None) -> dict[str, Any]:
    return {
        "error": {"code": code, "gate": gate, "message": message, "override_hint": override_hint}
    }


# ---------------------------------------------------------------------------
# Hosted engine — real tenant through the published algenta-sdk client
# ---------------------------------------------------------------------------


def _to_plain(obj: Any) -> Any:
    """Normalize SDK results (pydantic models / dataclasses / plain) to JSON-safe data."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return _to_plain(model_dump(mode="json"))
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses

        return _to_plain(dataclasses.asdict(obj))
    if hasattr(obj, "__dict__"):
        return _to_plain({k: v for k, v in vars(obj).items() if not k.startswith("_")})
    return str(obj)


class HostedEngine:
    """Real Algenta tenant via `algenta-sdk` (import name `decision_engine`).

    Constructed only when ALGENTA_API_KEY is present in the environment. Any
    SDK failure is normalized into the same denial envelope the demo engine
    emits, so the UI never branches on backend and never shows a traceback.
    """

    mode = "live"
    mode_label = HOSTED_MODE_LABEL

    def __init__(self) -> None:
        from decision_engine import AlgentaClient

        base_url = os.environ.get("ALGENTA_BASE_URL")  # SDK default: https://api.algenta.ai
        self._client = AlgentaClient(base_url=base_url) if base_url else AlgentaClient()
        self._lock = threading.Lock()

    def log_decision(
        self, chosen_action: str, confidence: float, risk_p5: float, state: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        state = ensure_state(state)
        request = {
            "chosen_action": chosen_action.strip(),
            "confidence": round(float(confidence), 3),
            "risk_p5": round(float(risk_p5), 3),
            "context": "Logged from the Algenta flagship Space (live tenant mode).",
            "rationale": "Interactive governed-execution walkthrough: log → approve → receipt.",
        }
        result = _to_plain(self._client.log_decision(request))
        decision_id = ""
        if isinstance(result, dict):
            decision_id = str(
                result.get("decision_id")
                or (result.get("decision") or {}).get("decision_id", "")
                or result.get("id", "")
            )
        body = {"outcome": "logged", "request": request, "response": result}
        return body, decision_id

    def execute_decision(
        self,
        profile: str,
        decision_id: str,
        webhook_url: str,
        force: bool,
        override_safety: bool,
        state: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        state = ensure_state(state)
        decision_id = decision_id.strip()
        audit = state["audit"]

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
                f"INTERCEPTED — `{profile}` profile never exposes `execute_decision` to the model."
            )
            return verdict, body

        from decision_engine import DecisionEngineError

        try:
            with self._lock:
                result = self._client.execute_decision(
                    decision_id,
                    webhook_url=webhook_url.strip() or "https://example.org/hooks/demo",
                    force=bool(force),
                    override_safety=bool(override_safety),
                    metadata={"origin": "algenta-flagship-space"},
                )
        except DecisionEngineError as exc:
            error = {
                "code": exc.error_code,
                "message": str(exc),
                "status_code": exc.status_code,
                "request_id": exc.request_id,
            }
            gate = _gate_from_error_code(exc.error_code)
            if gate:
                error["gate"] = gate
            body = {"error": error}
            audit.append(
                {
                    "at": _now_iso(),
                    "decision_id": decision_id,
                    "outcome": "denied",
                    "gate": gate or exc.error_code,
                }
            )
            verdict = (
                f"DENIED by the engine — `{exc.error_code}` (HTTP {exc.status_code}). "
                "Synchronous, in the same call. No execution happened."
            )
            return verdict, body

        receipt = _to_plain(result)
        audit.append(
            {"at": _now_iso(), "decision_id": decision_id, "outcome": "delivered", "gate": None}
        )
        verdict = "APPROVED — the real engine cleared its policy gates. Live execution receipt:"
        return verdict, receipt


def _gate_from_error_code(code: str) -> str | None:
    if "idempotency" in code:
        return "idempotency"
    if "confidence" in code:
        return "confidence"
    if "risk_floor" in code:
        return "risk_floor"
    return None


# ---------------------------------------------------------------------------
# Factory — the ONLY place the mode is chosen
# ---------------------------------------------------------------------------

_ENGINE: Any = None
_ENGINE_LOCK = threading.Lock()


def engine_mode() -> str:
    return "live" if os.environ.get("ALGENTA_API_KEY") else "demo"


def get_engine():
    """Return the process-wide engine. Hosted iff ALGENTA_API_KEY is set."""
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                _ENGINE = HostedEngine() if engine_mode() == "live" else DemoEngine()
    return _ENGINE


def engine_badge() -> str:
    return HOSTED_MODE_LABEL if engine_mode() == "live" else DEMO_MODE_LABEL


def profile_summary(profile: str) -> str:
    tools = "\n".join(f"- `{t}`" for t in PROFILE_TOOLS[profile])
    return f"**`{profile}`** — {PROFILE_DESCRIPTIONS[profile]}\n\nModel-facing tools:\n{tools}"
