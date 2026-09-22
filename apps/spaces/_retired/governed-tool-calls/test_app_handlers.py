"""Functional tests for the hf-space app handlers.

Run with any Python that has gradio installed: `python test_app_handlers.py`.
Not imported by app.py; safe (but unnecessary) to upload to the Space.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# --- profile summary ---
md = app.profile_summary("observe")
check(
    "observe summary lists 4 tools, no execute_decision",
    "execute_decision" not in md and "`query_data`" in md,
)
md = app.profile_summary("execute")
check("execute summary includes execute_decision", "`execute_decision`" in md)

# --- log_decision ---
state = app.initial_state()
out, did, state = app.log_decision("Refund Order 123", 0.93, 0.02, state)
body = json.loads(out)
check(
    "log returns deterministic decision_id",
    did == "decision-refund-order-123" and body["decision_id"] == did,
)
check("log echoes policy thresholds", body["policy"] == {"min_confidence": 0.8, "risk_floor": 0.05})

# --- profile interception: observe cannot execute ---
verdict, raw, audit, state = app.execute_decision(
    "observe", did, "https://example.org/hook", False, False, state
)
denial = json.loads(raw)
check(
    "observe profile intercepted", "INTERCEPTED" in verdict and denial["error"]["gate"] == "profile"
)
check("interception uses structured envelope", denial["error"]["code"] == "tool_not_in_profile")
check("audit recorded interception", json.loads(audit)[-1]["outcome"] == "intercepted")

# --- unknown decision id under execute profile ---
verdict, raw, _, state = app.execute_decision(
    "execute", "decision-nope", "https://example.org/hook", False, False, state
)
check("unknown id denied", "DENIED" in verdict and json.loads(raw)["error"]["gate"] == "existence")

# --- happy path: receipt shape ---
verdict, raw, audit, state = app.execute_decision(
    "execute", did, "https://example.org/hook", False, False, state
)
receipt = json.loads(raw)
expected_fields = {
    "decision_id",
    "webhook_url",
    "execution_status",
    "response_code",
    "executed_at",
    "policy_snapshot_id",
    "schema_snapshot_id",
    "manifest_version",
    "payload_summary",
    "safety_overridden",
}
check("approved verdict", verdict.startswith("✅"))
check("receipt has the full real-envelope field set", expected_fields <= set(receipt))
check(
    "receipt values",
    receipt["execution_status"] == "delivered"
    and receipt["response_code"] == 200
    and receipt["safety_overridden"] is False
    and receipt["decision_id"] == did,
)

# --- idempotency gate, then force bypass ---
verdict, raw, _, state = app.execute_decision(
    "execute", did, "https://example.org/hook", False, False, state
)
denial = json.loads(raw)
check(
    "second execute blocked on idempotency",
    denial["error"]["code"] == "execution_blocked_idempotency"
    and denial["error"]["gate"] == "idempotency",
)
verdict, raw, _, state = app.execute_decision(
    "execute", did, "https://example.org/hook", True, False, state
)
check("force bypasses idempotency", json.loads(raw)["execution_status"] == "delivered")

# --- confidence gate, then override_safety bypass ---
out, did2, state = app.log_decision("Ship risky refactor", 0.42, 0.01, state)
verdict, raw, _, state = app.execute_decision(
    "execute", did2, "https://example.org/hook", False, False, state
)
denial = json.loads(raw)
check(
    "low confidence blocked on confidence gate",
    denial["error"]["gate"] == "confidence"
    and "policy.min_confidence" in denial["error"]["message"],
)
verdict, raw, _, state = app.execute_decision(
    "execute", did2, "https://example.org/hook", False, True, state
)
receipt = json.loads(raw)
check(
    "override_safety bypasses confidence and is flagged on receipt",
    receipt["execution_status"] == "delivered" and receipt["safety_overridden"] is True,
)

# --- risk_floor gate ---
out, did3, state = app.log_decision("Migrate billing schema", 0.95, -0.31, state)
verdict, raw, _, state = app.execute_decision(
    "execute", did3, "https://example.org/hook", False, False, state
)
denial = json.loads(raw)
check(
    "negative risk_p5 blocked on risk_floor gate",
    denial["error"]["gate"] == "risk_floor"
    and denial["error"]["code"] == "execution_blocked_risk_floor",
)

# --- full profile can execute ---
out, did4, state = app.log_decision("Rotate api keys", 0.99, 0.2, state)
verdict, raw, audit, state = app.execute_decision(
    "full", did4, "https://example.org/hook", False, False, state
)
check("full profile executes", json.loads(raw)["execution_status"] == "delivered")

# --- audit accumulates every outcome ---
audit_list = json.loads(audit)
check("audit log accumulated all outcomes", len(audit_list) == 9)

# --- empty action rejected ---
out, did_x, _ = app.log_decision("   ", 0.5, 0.0, app.initial_state())
check("blank action rejected without state change", did_x == "" and out.startswith("⚠️"))

print()
if failures:
    print(f"{len(failures)} FAILURES")
    sys.exit(1)
print("ALL APP HANDLER TESTS PASSED")
