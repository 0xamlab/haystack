"""Governed — one real governed execution on the hosted engine, receipt or denial.

The lane is `algenta_spaces.hosted_api.HostedGoverned` over the Space secret
`ALGENTA_API_KEY` — a shared tenant every visitor of this Space executes
against, which is why the cost limits and the kill switch sit in front of every
call. At boot the tab asks `status()` once: without a key the tab shows one
quiet not-configured card and none of the controls — there is no other path,
and the two endpoints answer with that same card. With a key, one primary
action runs the whole chain against the real engine:

    recommend (two named actions, the engine's own simulation)
      → log_decision (the chosen action, the declared confidence, the risk P5)
        → execute_decision (webhook_url = this Space's own /hook/<nonce>)
          → Receipt with the engine's webhook POST shown next to it,
            or a Denial naming the gate that held it.

The profile radio is the integration contract's four profiles (`observe`,
`govern`, `execute`, `full` — `contracts/integration-tool-contract.json` in
thyn-ai/algenta-integrations, mirrored here as data): the chain stops at the
first tool the profile does not expose (`first_tool_outside_profile`), exactly
as every algenta-* integration filters the tools outside the profile out of the
model-facing tool list — under `observe` that is `log_decision` (the
recommendation stands; nothing is logged, nothing runs, no decision id exists),
under `govern` it is `execute_decision` (the decision is logged; nothing ran),
and `execute` and `full` run the whole chain. The intercepted card names the
tool, the call it stopped and only the steps that did run (round 17: the
observe card showed a decision id and said "the decision is logged" while the
profile has no `log_decision`). From 1280 px up its four pills share one row at their natural
widths; below that (`PROFILE_GRID_MAX_WIDTH`) the controls column is too narrow
for the four — 465 px of pills in a 422 px row at 1024 — so the pills are two
even rows of two, each 44 px, never three and an orphan (round 10: `Full` sat
alone on a second row at 1024 × 768).

**Execute again** re-sends the session's last decision id, and the button says
what the engine will do with it: after a *failed* delivery the engine executes
the decision again and issues a new receipt (`Execute again · a new receipt`);
after a *delivered* one the engine's idempotency gate holds the repeat with HTTP
409 (`execution_policy_service.check_execution_gates`) unless an operator
forces it, so the button reads `Execute again · expect the idempotency gate`
and the answer renders as `Held by the idempotency gate`; after a denial the
button names that gate. `force` / `override_safety` are the schema's
operator-only fields, shown with their human labels.

The receipt tells the engine's truth. Its chip follows `execution_status`:
`delivered · HTTP 200` in the live tone, `webhook_failed · HTTP <code>` (or `no
HTTP response`) in the red tone when the engine's POST to this Space failed —
then the card's hairline is red too, a failure during the run. The engine's
POST appears under a receipt only when the engine reported `delivered` **and**
this Space accepted a POST for that decision: `webhook.Hook` takes a POST only
when its nonce matches, its decision id was logged in this process and armed
for exactly one POST, its integrity ids equal what `log_decision` returned and
its summary is the decision this Space logged (the engine's decision webhook
carries no signature, and the card says so). Every other POST is refused with
400 and, when it named this decision, shown as `unexpected POST · rejected` in
the error tone — never as a delivery. The receipt's Webhook row names the host
and says the nonce is hidden; the URL with the nonce is printed nowhere.

A refused input never becomes a red card: `check_inputs` answers a `Refusal`
naming the offending control, and the page writes one sentence under that
control and echoes it in the status row beside Run — the convention the Try and
Playground tabs use — while the result column shows the empty state, because
nothing ran. Every handler catches everything else: an exception the lane does
not normalise is logged server-side and rendered as the designed red card
(`unexpected_error`, one sentence, no traceback), so the stock toast never
shows and the loading card always resolves.

On screen every step, gate, tool and integrity id carries a human name; the
identifiers live in the "Engine responses" JSON and the "Connect your agent"
snippets, and the engine's address appears only in the latter's code — the
not-configured card says the lane is not connected, never which variable turns
it on, and every card's footer reads "hosted engine · <UTC>". The receipt says
each fact once and stamps every moment one way: the engine's `executed_at`
(ISO, microseconds) is the card's sub-line as the fleet stamp in a `<time>`
whose `datetime` keeps the second (`iso_stamp`), the three integrity ids are
the receipt's rows and are not repeated under the POST (the hook verified them
equal), the decision id is the Decision row alone, the POST's body is
summarised in words (`webhook.describe_body`: `decision summary, decision id,
event, integrity block, metadata, organisation id`) above the body itself in
the fleet's capped code block (`cards.code_block`: 24 lines visible, wrapping
inside its column, an inner scroller in the tab order), and every fleet stamp
on the card and in the audit is a `<time>`.

Layout is the fleet's two-column contract (`css.LAYOUT_CSS`): the row carries
`COLS_CLASS`, the controls column `CONTROLS_CLASS` and the results column
`RESULTS_CLASS`, so the controls keep their natural height whatever the
results do (the final review measured `equal_height=True` growing the Run
button to 459 px and a slider block to 532 px under an open Engine responses
block). The card block carries `FILL_CLASS` and takes the column's slack as
page, never as card: a Governed card — empty, receipt, denial or interception
— is as tall as its content (`GOV_CSS` pins `.alg-card` in `RESULTS_COL_CLASS`
to its content where the shared contract would grow a result card to the
column; the review measured 680 px of dashed void in the empty card and 450 px
between an interception's last row and its foot). The disclosures sit under
the row at the page's width: "Engine responses" (hidden until an engine call
was made, collapsed then, the whole JSON in the capped code block with a
`Copy JSON` chip beside it), "This session", "Connect your agent" and "How
this works". Every hosted call passes the cost limits (`limits.py`, lane
`governed`) and the kill switch feature `hosted`. The audit list is this
session's decisions, kept in `gr.State`. The two snippets are the remote MCP
client config (`MCP_ENDPOINT` from `algenta._contract`) and a smolagents
example that neither passes `trust_remote_code=True` nor spreads `**os.environ`
into the server.
"""

from __future__ import annotations

import html
import json
import logging
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from algenta_spaces import cards, hosted_api
from algenta_spaces.css import (
    COLS_CLASS,
    CONTROLS_CLASS,
    FILL_CLASS,
    RESULTS_CLASS,
    block,
    rule,
    stylesheet,
)
from algenta_spaces.hosted_api import (
    ConfigState,
    Decision,
    Denial,
    EngineError,
    EngineUnavailableError,
    HostedError,
    HostedGoverned,
    NotConfiguredError,
    RateLimitedError,
    Receipt,
    Recommendation,
)
from algenta_spaces.runtime import utc_stamp
from algenta_spaces.shell import check_copy

import webhook as webhook_mod

from . import TAB_GOV, Deps, TabSpec, common
from .llm_tab import (
    copy_chip,
    render_empty_card,
    render_failure_card,
    render_loading_card,
    render_quiet_card,
    request_hint,
    visitor_key,
)

log = logging.getLogger(__name__)

LABEL = "Governed"
API_RUN = "gov_run"
API_EXECUTE_AGAIN = "gov_execute_again"
API_NAMES: tuple[str, ...] = (API_RUN, API_EXECUTE_AGAIN)

LANE_KIND = "governed"
FEATURE = "hosted"

#: thyn-ai/algenta-integrations `contracts/integration-tool-contract.json` → `profiles`.
PROFILES: tuple[str, ...] = ("observe", "govern", "execute", "full")
PROFILE_LABELS: Mapping[str, str] = {
    "observe": "Observe",
    "govern": "Govern",
    "execute": "Execute",
    "full": "Full",
}
DEFAULT_PROFILE = "execute"
PROFILE_TOOLS: Mapping[str, tuple[str, ...]] = {
    "observe": ("get_contract", "query_data", "simulate", "recommend"),
    "govern": (
        "get_contract",
        "query_data",
        "simulate",
        "recommend",
        "plan_decision",
        "log_decision",
    ),
    "execute": (
        "get_contract",
        "query_data",
        "simulate",
        "recommend",
        "plan_decision",
        "log_decision",
        "execute_decision",
    ),
    "full": ("*",),
}
#: The engine's wildcard: every tool it lists (the `full` profile's one entry).
EVERY_TOOL = "*"
#: The tools one run calls, in order; the chain stops at the first one outside the profile.
CHAIN_TOOLS: tuple[str, ...] = ("recommend", "log_decision", "execute_decision")


def allows(profile: str, tool: str) -> bool:
    """True when the profile exposes `tool` (the `*` profile exposes every tool)."""
    tools = PROFILE_TOOLS[profile]
    return EVERY_TOOL in tools or tool in tools


def first_tool_outside_profile(profile: str, tools: Sequence[str] = CHAIN_TOOLS) -> str:
    """The first of `tools` the profile does not expose — where the integration intercepts the
    chain — or an empty string when the profile exposes every one of them (`execute`, `full`).
    `observe` → `log_decision`, `govern` → `execute_decision`."""
    return next((tool for tool in tools if not allows(profile, tool)), "")


def chain_steps(profile: str, tools: Sequence[str] = CHAIN_TOOLS) -> tuple[str, ...]:
    """The tools of `tools` a run under `profile` calls: every one up to the intercepted tool."""
    blocked = first_tool_outside_profile(profile, tools)
    return tuple(tools) if not blocked else tuple(tools)[: tuple(tools).index(blocked)]


#: The profiles whose run reaches `execute_decision` — derived from the tool lists, never a
#: second copy of them.
EXECUTE_PROFILES: frozenset[str] = frozenset(p for p in PROFILES if allows(p, "execute_decision"))
#: The engine's tool ids, as a visitor reads them; the ids stay in the JSON and the snippets.
TOOL_NAMES: Mapping[str, str] = {
    "get_contract": "Read the contract",
    "query_data": "Query data",
    "simulate": "Simulate",
    "recommend": "Recommend",
    "plan_decision": "Plan a decision",
    "log_decision": "Log a decision",
    "execute_decision": "Execute a decision",
    "*": "Every tool the engine lists",
}
STEP_NAMES: Mapping[str, str] = {
    "recommend": "Recommendation",
    "log_decision": "Decision log",
    "execute_decision": "Execution",
    "run": "Run",
}
GATE_NAMES: Mapping[str, str] = {
    "idempotency": "idempotency",
    "confidence": "confidence",
    "risk_floor": "risk floor",
    "existence": "existence",
    "profile": "profile",
}
INTEGRITY_NAMES: Mapping[str, str] = {
    "policy_snapshot_id": "Policy snapshot",
    "schema_snapshot_id": "Schema snapshot",
    "manifest_version": "Manifest version",
    "executed_at": "Executed at",
    "request_hash": "Request hash",
    "result_hash": "Result hash",
}
PROFILE_LINES: Mapping[str, str] = {
    "observe": "Read-only: discovery, exact queries, simulation, recommendations.",
    "govern": "Adds planning and logging decisions; nothing is executed.",
    "execute": "Adds executing an already-logged decision.",
    "full": "Every tool the engine lists; opt-in only.",
}
OPERATOR_ONLY = ("force", "override_safety")

HOLD = "hold"
VARIABLE = "revenue"
OBJECTIVE = "maximize_net_value"
RUNS = 100  # the API's minimum; the tenant pays simulations per run
HOLD_SPREAD = 0.01
ACTION_MAX_CHARS = 200
DEFAULT_ACTION = "expand_eu"
LOW = (0, 1_000_000, 1_000, 80_000)
HIGH = (0, 1_000_000, 1_000, 200_000)
HOLD_VALUE = (0, 1_000_000, 1_000, 100_000)
CONFIDENCE = (0.0, 1.0, 0.01, 0.93)
RISK_P5 = (-0.5, 0.5, 0.01, 0.02)
WEBHOOK_TIMEOUT_S = 10.0
WEBHOOK_WAIT_S = 2.0
CONTEXT = "Logged from the Algenta flagship Space."

#: `packages/algenta/algenta/_contract.py:MCP_ENDPOINT` (the SDK needs CPython 3.14; mirrored).
MCP_ENDPOINT = "https://api.algenta.ai/mcp"
MCP_CLIENT_CONFIG = json.dumps(
    {
        "mcpServers": {
            "algenta": {
                "url": MCP_ENDPOINT,
                "headers": {"Authorization": "Bearer <your API key>"},
            }
        }
    },
    indent=2,
)
SMOLAGENTS_SNIPPET = """\
# pip install smolagents[mcp]  ·  the server is the published algenta-mcp package
# The observe profile is the default; execute-tier tools stay off unless the engine
# operator enables them for your key. Nothing here forwards your whole environment.
import os

from mcp import StdioServerParameters
from smolagents import CodeAgent, InferenceClientModel, MCPClient

server = StdioServerParameters(
    command="uvx",
    args=["algenta-mcp"],
    env={
        "ALGENTA_API_KEY": os.environ["ALGENTA_API_KEY"],
        "ALGENTA_BASE_URL": "https://api.algenta.ai",
    },
)

with MCPClient(server) as tools:
    agent = CodeAgent(tools=tools, model=InferenceClientModel(), add_base_tools=False)
    agent.run("Compare expand_eu with hold on the orders dataset, then log the decision.")
"""
#: The Connect disclosure's opening line; the engine's address rides in the code block below it.
ENGINE_NOTE_TEXT = "The engine's address is in the snippets below; each one carries it as code."
#: The engine's address as a one-line code block, next to the two snippets.
ENGINE_CODE_LABEL = "Engine"

TITLE_RECEIPT = "Execution receipt"
#: A control column in a two-up row (two sliders, two checkboxes): two fit beside each other in
#: the controls column on the desktop, one per row on a phone.
CONTROL_MIN_WIDTH = 240
#: The controls column and the results column: equal halves that stack below this.
COLUMN_MIN_WIDTH = 320
#: The results column (`css.RESULTS_CLASS` beside it): its cards are never taller than their
#: content — the fill block takes the column's slack as page (`GOV_CSS`).
RESULTS_COL_CLASS = "alg-gov-results"
#: The card block in that column: `css.FILL_CLASS` plus this, for the tests and the probes.
CARD_BLOCK_CLASS = "alg-gov-card-block"
#: The Engine responses block and the POST body under a receipt: the whole JSON in the fleet's
#: capped code block (`cards.code_block`, `ENGINE_JSON_LINES` lines visible, an inner scroller
#: in the tab order); the `Copy JSON` chip beside the former is wired to the same full text.
ENGINE_JSON_LINES = 24
ENGINE_JSON_LANGUAGE = "json"
COPY_JSON_TEXT = cards.copy_label(ENGINE_JSON_LANGUAGE)
#: The chip's own class: two words stay on one line at the chip's natural width (`GOV_CSS`).
COPY_JSON_CLASS = "alg-gov-copy"
COPY_JSON_JS = (
    "async (text) => { try { await navigator.clipboard.writeText(text ?? ''); return 'Copied'; }"
    f" catch (error) {{ return '{COPY_JSON_TEXT}'; }} }}"
)
WEBHOOK_BODY_CAPTION = "Webhook body"
#: The receipt's Body row: the POST's top-level keys in words (`webhook.describe_body`).
BODY_ROW_LABEL = "Body"
#: The receipt's sub-line: when the engine executed, as the fleet stamp in a `<time>`.
EXECUTED_TEXT = "executed {stamp}"
TITLE_DENIED = "Held by the {gate} gate"
TITLE_INTERCEPTED = "Not in the {profile} profile"
TITLE_LANE = "Governed lane"
TITLE_EMPTY = "Governed execution"
RUN_TEXT = "Run governed execution"
#: The Execute again button's three truths: before any decision, after a failed delivery
#: (the engine executes again), after a delivered one or a denial (a gate will hold it).
AGAIN_TEXT = "Execute again"
AGAIN_NEW_RECEIPT_TEXT = "Execute again · a new receipt"
AGAIN_EXPECT_GATE_TEXT = "Execute again · expect the {gate} gate"
CONNECT_TITLE = "Connect your agent"
ENGINE_JSON_TITLE = "Engine responses"
AUDIT_TITLE = "This session"
HOW_TITLE = "How this works"
LABEL_PROFILE = "Profile"
#: The Profile radio's own class (`GOV_CSS` reaches its option pills through it).
PROFILE_RADIO_CLASS = "alg-gov-profile-radio"
#: Up to this width the Profile pills are two even rows of two (see the module docstring);
#: the fleet's tablet breakpoint (the Ecosystem table wraps its cells up to the same width).
PROFILE_GRID_MAX_WIDTH = 1279
LABEL_ACTION = "Action"
LABEL_LOW = "Pessimistic value"
LABEL_HIGH = "Optimistic value"
LABEL_HOLD = "Hold outcome"
#: The visitor's own confidence in the decision (`log_decision.confidence`) — not the engine's
#: ranking confidence, which the Recommendation row prints as `engine confidence`.
LABEL_CONFIDENCE = "Declared confidence"
#: `log_decision.risk_p5`: the decision's pessimistic outcome at the 5th percentile. Not the
#: policy's risk floor — that is the gate the engine compares it against (`GATE_NAMES`).
LABEL_RISK = "Risk (P5)"
LABEL_FORCE = "Force execution (operators only)"
LABEL_OVERRIDE = "Override the safety gate (operators only)"
LABEL_RAW = "Engine JSON"
FOOT_LABEL = "hosted engine"
LABEL_MCP = "MCP client"
LABEL_SMOL = "smolagents"
EMPTY_TEXT = "Run a governed execution to see the engine's receipt, or the gate that held it."
EMPTY_ROWS = ("recommendation", "decision", "execution")
#: What a screen reader hears for an empty step row before a run (these are steps, not timings).
PENDING_TEXT = "not run yet"
LOADING_TEXT = "Asking the hosted engine: recommend, log the decision, execute it."
#: The loading sentence names the steps the profile will run (`loading_text`): every step under
#: `execute` and `full` (`LOADING_TEXT`), fewer under `govern` and `observe`.
LOADING_STEPS_TEXT = "Asking the hosted engine: {steps}."
STEP_PHRASES: Mapping[str, str] = {
    "recommend": "recommend",
    "log_decision": "log the decision",
    "execute_decision": "execute it",
}
LOADING_AGAIN_TEXT = (
    "Sending the last decision to the hosted engine again; after a failed delivery it executes "
    "again and issues a new receipt."
)
LOADING_AGAIN_GATE_TEXT = (
    "Sending the last decision to the hosted engine again; expect the {gate} gate to hold it."
)
HOW_TEXT = (
    "Every step is a real call to the hosted engine on a shared tenant: the recommendation runs "
    f"the engine's simulation over two named actions ({RUNS} runs each), logging records the "
    "chosen one with your declared confidence and its risk at the 5th percentile, executing "
    "asks the engine to deliver it to "
    "this Space's own webhook. The engine answers in the same call with a receipt and its "
    "integrity ids, or holds it at a policy gate such as confidence or the risk floor. The "
    "receipt says whether the engine's POST reached this Space, and a POST is shown only once "
    "this Space has verified its nonce, its decision id, its integrity ids and its summary; "
    "the engine signs no decision webhook. Executing again sends the same decision once more: "
    "after a failed delivery the engine executes it again and issues a new receipt; after a "
    "delivered one its idempotency gate holds the repeat unless an operator forces it."
)
NOT_CONFIGURED_HINT = "The hosted lane is not connected on this Space."
BOOT_UNAVAILABLE_HINT = (
    "The hosted engine did not answer when this Space booted; a run asks it again."
)
BOOT_RATE_LIMITED_HINT = (
    "The hosted engine throttled this Space when it booted; a run asks it again."
)
#: What the intercepted card says, by the tool the integration stopped: `govern` stops at
#: `execute_decision` (the decision is logged), `observe` at `log_decision` (nothing is logged).
INTERCEPT_TEXT = (
    "Executing a decision is not in this profile; the decision is logged and nothing ran."
)
INTERCEPT_LOG_TEXT = (
    "Logging a decision is not in this profile; the recommendation stands, nothing was logged "
    "or run."
)
INTERCEPT_TEXTS: Mapping[str, str] = {
    "execute_decision": INTERCEPT_TEXT,
    "log_decision": INTERCEPT_LOG_TEXT,
}
#: The intercepted card's sub-line names the call the integration stopped: the engine was
#: called for every step before it (round 17: "before the engine was called" under `govern`,
#: after two real engine calls).
INTERCEPT_SUB_TEXT = "before the {call} call reached the engine"
CALL_WORDS: Mapping[str, str] = {
    "recommend": "recommend",
    "log_decision": "log",
    "execute_decision": "execute",
}
WEBHOOK_MISSED_TEXT = (
    "The engine reported delivery; its POST had not reached this Space within {wait:g} s."
)
WEBHOOK_FAILED_TEXT = "The engine's POST to this Space's webhook failed."
#: The receipt's Webhook row: the host the engine delivered to; the nonce is printed nowhere.
WEBHOOK_ROW_LABEL = "Webhook"
WEBHOOK_ROW_TEXT = "this Space's webhook · {host} · nonce hidden"
#: Under an accepted POST: what was checked, and what was not there to check.
VERIFIED_TEXT = "nonce, session, integrity and summary verified"
NO_SIGNATURE_TEXT = (
    "The engine's decision webhook carries no signature; this Space verified the nonce, the "
    "decision it logged in this session and the integrity ids instead."
)
#: A POST naming this decision that failed verification: refused with 400, never a delivery.
REJECTED_TEXT = "unexpected POST · rejected"
REJECTED_NOTE = (
    "A POST naming this decision reached this Space's webhook and failed verification; it was "
    "refused and is not shown."
)
MISMATCH_NOTE = "The POST this Space accepted does not match the engine's receipt."
NOT_RECEIVED_TEXT = "not received yet"
DELIVERED_TEXT = "delivered"
NO_HTTP_TEXT = "no HTTP response"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"
STATUS_DENIED = "denied"
CODE_WEBHOOK_FAILED = "webhook_failed"
CODE_UNEXPECTED = "unexpected_error"
HINT_UNEXPECTED = (
    "This Space hit an error of its own during the run; the detail is in its log, not on this page."
)
CODE_CLIENT_MISSING = "hosted_client_not_installed"
CLIENT_MISSING_HINT = (
    "The hosted client is not installed in this container, so the governed lane is off."
)
#: How the boot stage spells a probe that failed before the SDK client existed.
CLIENT_MISSING_MARKERS: tuple[str, ...] = ("ModuleNotFoundError", "ImportError")
CODE_PAUSED = common.CODE_SWITCHED_OFF
HINT_PAUSED = common.SWITCHED_OFF_HINT
CODE_RATE_LIMITED = hosted_api.RATE_LIMITED_CODE
CODE_UNAVAILABLE = hosted_api.UNAVAILABLE_CODE
CODE_INVALID = "invalid_input"
CODE_NO_DECISION = "no_decision_yet"
HINT_NO_DECISION = "Run a governed execution first; then the same decision can be sent again."
INTERCEPT_CODE = "tool_not_in_profile"
INTERCEPT_GATE = "profile"
GATE_IDEMPOTENCY = "idempotency"

#: The controls a refusal can name, and the message slot under each (`FIELD_SLOTS` keys are the
#: `check_inputs` field names; values are the four slots the page draws).
SLOT_ACTION = "action"
SLOT_VALUES = "values"
SLOT_HOLD = "hold"
SLOT_RISK = "risk"
SLOTS: tuple[str, ...] = (SLOT_ACTION, SLOT_VALUES, SLOT_HOLD, SLOT_RISK)
FIELD_SLOTS: Mapping[str, str] = {
    "action": SLOT_ACTION,
    "low": SLOT_VALUES,
    "high": SLOT_VALUES,
    "hold_value": SLOT_HOLD,
    "confidence": SLOT_HOLD,
    "risk_p5": SLOT_RISK,
}
FIELD_LABELS: Mapping[str, str] = {
    "action": LABEL_ACTION,
    "low": LABEL_LOW,
    "high": LABEL_HIGH,
    "hold_value": LABEL_HOLD,
    "confidence": LABEL_CONFIDENCE,
    "risk_p5": LABEL_RISK,
}
#: The two confidences on one card, named apart: the Recommendation row's is the engine's
#: ranking confidence (`Recommendation.confidence`), the Chosen action row's the one the visitor
#: declared (`Decision.confidence`, the form's field). Round 17: `confidence 1.00` and
#: `confidence 0.93` sat on adjacent rows.
ENGINE_CONFIDENCE_TEXT = "engine confidence"
DECLARED_CONFIDENCE_TEXT = "declared confidence"
#: The Chosen action row's `risk_p5` (see `LABEL_RISK`); the gate stays `GATE_NAMES["risk_floor"]`.
RISK_P5_TEXT = "risk P5"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


def initial_state() -> dict[str, Any]:
    return {
        "decisions": {},
        "audit": [],
        "last_decision_id": "",
        "last_execution_status": "",
        "last_gate": "",
    }


def ensure_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict) or "decisions" not in state or "audit" not in state:
        return initial_state()
    for key, value in initial_state().items():
        state.setdefault(key, value)
    return state


def _audit(state: dict[str, Any], step: str, outcome: str, decision_id: str = "", gate: str = ""):
    state["audit"].append(
        {
            "at": utc_stamp(),
            "step": step,
            "outcome": outcome,
            "decision_id": decision_id,
            "gate": gate,
        }
    )


def expected_gate(state: Mapping[str, Any]) -> str:
    """The gate the engine will hold a re-execution at, or an empty string: `idempotency`
    after a delivered execution (`check_execution_gates`, 409), the denial's gate after a
    denial, nothing after a failed delivery or before any execution."""
    if not state.get("last_decision_id"):
        return ""
    status = str(state.get("last_execution_status") or "")
    if status == STATUS_DELIVERED:
        return GATE_IDEMPOTENCY
    if status == STATUS_DENIED:
        return str(state.get("last_gate") or "")
    return ""


def again_label(state: Mapping[str, Any]) -> str:
    """What Execute again will do, as the button says it (`AGAIN_*_TEXT`)."""
    gate = expected_gate(state)
    if gate:
        return AGAIN_EXPECT_GATE_TEXT.format(gate=gate_name(gate))
    if str(state.get("last_execution_status") or "") == STATUS_FAILED:
        return AGAIN_NEW_RECEIPT_TEXT
    return AGAIN_TEXT


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Refusal:
    """One refused input: the control (`FIELD_SLOTS` key) and one sentence a visitor reads."""

    field: str
    message: str

    @property
    def slot(self) -> str:
        return FIELD_SLOTS[self.field]


def _number(field_name: str, value: Any, spec: tuple) -> float:
    lo, hi, _, _ = spec
    label = FIELD_LABELS[field_name]
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a number.")
    if not lo <= float(value) <= hi:
        raise ValueError(f"{label} must be between {lo:g} and {hi:g}.")
    return float(value)


def clean_action(text: Any) -> str:
    action = str(text or "").strip()
    if not action:
        raise ValueError(f"{LABEL_ACTION} needs a name.")
    if len(action) > ACTION_MAX_CHARS:
        raise ValueError(f"{LABEL_ACTION} is longer than {ACTION_MAX_CHARS} characters.")
    if any(ord(ch) < 32 for ch in action):
        raise ValueError(f"{LABEL_ACTION} holds control characters.")
    if action.lower() == HOLD:
        raise ValueError(f"{LABEL_ACTION} cannot be named {HOLD!r}; that is the baseline.")
    return action


def recommend_actions(action: str, low: float, high: float, hold_value: float) -> list[dict]:
    """The two `NamedAction`s `/v1/recommend` compares: the action's range and hold ± 1 %."""
    if high <= low:
        raise ValueError(f"{LABEL_HIGH} must be above the pessimistic value.")
    if hold_value <= 0:
        raise ValueError(f"{LABEL_HOLD} must be above zero.")
    hold_low = round(hold_value * (1.0 - HOLD_SPREAD), 2)
    hold_high = round(hold_value * (1.0 + HOLD_SPREAD), 2)

    def named(name: str, lo: float, hi: float) -> dict[str, Any]:
        return {
            "name": name,
            "request": {
                "mode": "auto",
                "scenario": {
                    "variables": {VARIABLE: {"low": lo, "high": hi}},
                    "objective": OBJECTIVE,
                },
                "runs": RUNS,
            },
        }

    return [named(action, low, high), named(HOLD, hold_low, hold_high)]


def check_inputs(
    action: Any, low: Any, high: Any, hold_value: Any, confidence: Any, risk_p5: Any
) -> Refusal | None:
    """The one pre-flight check: the first control whose value the run cannot use, with the
    sentence the page writes under it — or None when every input is usable."""
    try:
        clean_action(action)
    except ValueError as exc:
        return Refusal("action", str(exc))
    values: dict[str, float] = {}
    for name, value, spec in (
        ("low", low, LOW),
        ("high", high, HIGH),
        ("hold_value", hold_value, HOLD_VALUE),
        ("confidence", confidence, CONFIDENCE),
        ("risk_p5", risk_p5, RISK_P5),
    ):
        try:
            values[name] = _number(name, value, spec)
        except ValueError as exc:
            return Refusal(name, str(exc))
    if values["high"] <= values["low"]:
        return Refusal("high", f"{LABEL_HIGH} must be above the pessimistic value.")
    if values["hold_value"] <= 0:
        return Refusal("hold_value", f"{LABEL_HOLD} must be above zero.")
    return None


def field_messages(refusal: Refusal | None) -> dict[str, str]:
    """The four message slots: the refusal's sentence under its control, nothing elsewhere."""
    messages = dict.fromkeys(SLOTS, "")
    if refusal is not None:
        messages[refusal.slot] = common.render_field_message(refusal.message)
    return messages


def status_html(refusal: Refusal | None) -> str:
    """The status row beside Run: the refusal echoed, or the empty live region."""
    return common.render_status("", refusal.message if refusal is not None else "")


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    """What one run produced, step by step; `raw` is every engine body for the accordion."""

    recommendation: Recommendation | None = None
    decision: Decision | None = None
    receipt: Receipt | None = None
    denial: Denial | None = None
    intercepted_profile: str = ""
    intercepted_tool: str = ""
    webhook: webhook_mod.HookEvent | None = None
    webhook_host: str = ""
    rejected: list[webhook_mod.Rejection] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def delivered(self) -> bool:
        return self.receipt is not None and self.receipt.delivered


def client_missing(status: hosted_api.HostedStatus | None) -> bool:
    """True when the boot probe failed because the SDK client itself is not installed here —
    the lane cannot run, whatever key is set, so the tab treats it as not configured."""
    if status is None or status.state is not ConfigState.UNAVAILABLE:
        return False
    return status.reason.startswith(CLIENT_MISSING_MARKERS)


def _lane_gate(
    deps: Deps,
    hosted: HostedGoverned | None,
    request: Any,
    status: hosted_api.HostedStatus | None = None,
) -> str | None:
    """The card that stops a run before the engine is called, or None to proceed."""
    if hosted is None or not hosted.configured:
        return not_configured_card(hosted)
    if client_missing(status):
        return status_card(status)
    if not deps.feature_on(FEATURE):
        return render_quiet_card(TITLE_LANE, CODE_PAUSED, HINT_PAUSED, hardware=_foot(hosted))
    if deps.limits is not None and LANE_KIND in deps.limits.policy.lanes:
        decision = deps.limits.check(visitor_key(request), LANE_KIND)
        if not decision.allowed:
            return render_quiet_card(
                TITLE_LANE, CODE_RATE_LIMITED, decision.reason, hardware=_foot(hosted)
            )
    return None


def run_chain(
    hosted: HostedGoverned,
    hook: webhook_mod.Hook | None,
    *,
    profile: str,
    action: str,
    low: float,
    high: float,
    hold_value: float,
    confidence: float,
    risk_p5: float,
    force: bool = False,
    override_safety: bool = False,
    state: dict[str, Any],
    out: Outcome | None = None,
) -> Outcome:
    """recommend → log_decision → execute_decision, stopping at the first tool the profile does
    not expose (`first_tool_outside_profile`: `log_decision` under `observe`, `execute_decision`
    under `govern`, none under `execute` and `full`), recording each step into `out` (the
    caller's, so the bodies of the steps that did run survive a later failure). An intercepted
    step is audited as that tool, `intercepted`, at the profile gate; nothing past it is called,
    and a run intercepted before `log_decision` leaves the session's decisions untouched."""
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {PROFILES}")
    out = Outcome() if out is None else out
    blocked = first_tool_outside_profile(profile)

    def intercept(tool: str, decision_id: str = "") -> Outcome:
        out.intercepted_profile = profile
        out.intercepted_tool = tool
        _audit(state, tool, "intercepted", decision_id, INTERCEPT_GATE)
        return out

    if blocked == "recommend":
        return intercept("recommend")
    actions = recommend_actions(action, low, high, hold_value)
    out.recommendation = hosted.recommend(actions, runs=RUNS)
    out.raw["recommend"] = out.recommendation.raw
    _audit(state, "recommend", f"recommends {out.recommendation.recommended_action}")
    if blocked == "log_decision":
        return intercept("log_decision")

    rationale = out.recommendation.rationale or "Recommended by the hosted engine."
    figures = hosted_api.action_result(out.recommendation, action)
    out.decision = hosted.log_decision(
        action,
        confidence=confidence,
        risk_p5=risk_p5,
        context=CONTEXT,
        rationale=rationale,
        options_considered=[a["name"] for a in actions],
        expected_value=figures.get("expected_value"),
        probability_of_loss=figures.get("probability_of_loss"),
    )
    out.raw["log_decision"] = out.decision.raw
    state["decisions"][out.decision.decision_id] = {
        "chosen_action": out.decision.chosen_action,
        "confidence": out.decision.confidence,
        "risk_p5": out.decision.risk_p5,
        "logged_utc": utc_stamp(),
        "integrity": dict(out.decision.integrity),
    }
    state["last_decision_id"] = out.decision.decision_id
    state["last_execution_status"] = ""
    state["last_gate"] = ""
    _audit(state, "log_decision", "logged", out.decision.decision_id)
    if blocked == "execute_decision":
        return intercept("execute_decision", out.decision.decision_id)
    execute_into(hosted, hook, out, out.decision.decision_id, force, override_safety, state)
    return out


def execute_into(
    hosted: HostedGoverned,
    hook: webhook_mod.Hook | None,
    out: Outcome,
    decision_id: str,
    force: bool,
    override_safety: bool,
    state: dict[str, Any],
) -> Outcome:
    """`execute_decision` for `decision_id` into `out`: the hook is armed with what this session
    logged for the decision, the engine is called, the accepted POST (if any) is read, the hook
    is settled and every refused POST naming the decision is carried on the outcome."""
    url = hook.url() if hook is not None else ""
    if not url:
        raise EngineError(webhook_mod.HINT_NO_PUBLIC_URL, code=webhook_mod.CODE_NO_PUBLIC_URL)
    assert hook is not None  # noqa: S101 - url() answered, so the hook exists
    logged = state["decisions"].get(decision_id)
    if not isinstance(logged, Mapping):
        raise EngineError(HINT_NO_DECISION, code=CODE_NO_DECISION)
    out.webhook_host = hook.host
    hook.expect(
        decision_id,
        integrity=logged.get("integrity") or {},
        chosen_action=str(logged.get("chosen_action", "")),
        confidence=logged.get("confidence"),
    )
    try:
        result = hosted.execute_decision(
            decision_id,
            webhook_url=url,
            timeout_seconds=WEBHOOK_TIMEOUT_S,
            force=bool(force),
            override_safety=bool(override_safety),
        )
        if isinstance(result, Denial):
            out.denial = result
            out.raw["execute_decision"] = {
                "error": {
                    "code": result.code,
                    "gate": result.gate,
                    "message": result.message,
                    "override_hint": result.override_hint,
                },
                "status_code": result.status_code,
                "request_id": result.request_id,
            }
            state["last_execution_status"] = STATUS_DENIED
            state["last_gate"] = result.gate
            _audit(state, "execute_decision", "denied", decision_id, result.gate)
            return out
        out.receipt = result
        out.raw["execute_decision"] = result.raw
        if result.delivered:
            out.webhook = hook.wait_for(decision_id, timeout_s=WEBHOOK_WAIT_S)
            if out.webhook is not None:
                out.raw["webhook"] = out.webhook.event.body
        state["last_execution_status"] = result.execution_status
        state["last_gate"] = ""
        _audit(state, "execute_decision", result.execution_status, decision_id)
        return out
    finally:
        hook.settle(decision_id)
        out.rejected = hook.rejections(decision_id)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _chip(text: str, tone: str = "neutral") -> str:
    return f'<span class="alg-chip alg-chip-{tone}">{_esc(text)}</span>'


def _row(key: str, value: object) -> str:
    return (
        f'<div class="alg-gov-row"><span class="alg-gov-key">{_esc(key)}</span>'
        f'<span class="alg-gov-val">{_esc(value)}</span></div>'
    )


def _foot(hosted: HostedGoverned | None) -> str:
    """The card footer: where and when — the engine's address is configuration, not copy."""
    del hosted
    return f"{FOOT_LABEL} · {utc_stamp()}"


def _time_html(stamp: object) -> str:
    """A fleet stamp (`2026-09-23 07:28 UTC`) as the card's `<time>` element; text that is not
    one, escaped as it came."""
    try:
        return cards.time_stamp(stamp)
    except ValueError:
        return _esc(stamp)


def _foot_html(hosted: HostedGoverned | None) -> str:
    """`hosted engine · <time>…</time>` — the one foot every Governed card prints."""
    return f'<div class="alg-card-foot">{_esc(FOOT_LABEL)} · {_time_html(utc_stamp())}</div>'


def iso_stamp(value: object) -> tuple[str, str]:
    """`("2026-09-23 07:28 UTC", "2026-09-23T07:28:40Z")` from the engine's ISO instant
    (`2026-09-23T07:28:40.930310Z`): the fleet stamp a reader sees and the second-precise
    datetime a machine reads. Anything that is not an ISO instant raises ValueError."""
    text = str(value).strip()
    if not text:
        raise ValueError("empty instant")
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    moment = moment.astimezone(UTC)
    return utc_stamp(moment), moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def executed_html(value: object) -> str:
    """The receipt's sub-line: `executed <time datetime="…Z">2026-09-23 07:28 UTC</time>` —
    the fleet's one stamp style, the engine's second kept in the datetime; an instant the
    engine spelled some other way is printed as it came."""
    try:
        stamp, iso = iso_stamp(value)
    except ValueError:
        return _esc(EXECUTED_TEXT.format(stamp=str(value)))
    time = f'<time class="{cards.TIME_CLASS}" datetime="{iso}">{_esc(stamp)}</time>'
    return EXECUTED_TEXT.format(stamp=time)


def engine_url(hosted: HostedGoverned | None) -> str:
    return hosted.base_url if hosted is not None else hosted_api.DEFAULT_BASE_URL


def tool_name(tool_id: str) -> str:
    """The human name of an engine tool id; an unknown id is shown as its words."""
    return TOOL_NAMES.get(tool_id, tool_id.replace("_", " "))


def step_name(step: str) -> str:
    return STEP_NAMES.get(step, step.replace("_", " "))


def gate_name(gate: str) -> str:
    return GATE_NAMES.get(gate, gate.replace("_", " "))


def call_word(tool: str) -> str:
    """The one word the intercepted card's sub-line calls a tool's engine call by."""
    return CALL_WORDS.get(tool, tool.replace("_", " "))


def intercept_text(tool: str) -> str:
    """The intercepted card's sentence for the tool the integration stopped at."""
    fallback = f"{tool_name(tool)} is not in this profile; nothing past it ran."
    return INTERCEPT_TEXTS.get(tool) or fallback


def loading_text(profile: str = DEFAULT_PROFILE) -> str:
    """The run's loading sentence: the steps this profile will ask the engine for, in order —
    `LOADING_TEXT` word for word under `execute` and `full`."""
    if profile not in PROFILES:
        profile = DEFAULT_PROFILE
    steps = [STEP_PHRASES[tool] for tool in chain_steps(profile)]
    return LOADING_STEPS_TEXT.format(steps=", ".join(steps))


def tool_chips(profile: str) -> str:
    """One chip per tool the profile allows; the `*` profile's chip would repeat the profile
    line word for word (`Every tool the engine lists`), so it is said once, in the line
    (round 11: the Full description printed twice, as a sentence and as a chip)."""
    return "".join(_chip(tool_name(tool)) for tool in PROFILE_TOOLS[profile] if tool != EVERY_TOOL)


def not_configured_card(hosted: HostedGoverned | None, hint: str = NOT_CONFIGURED_HINT) -> str:
    """The quiet not-configured card: hairline border, the code in a neutral chip, one sentence
    that names no variable and no address."""
    return render_quiet_card(
        hosted_api.NOT_CONFIGURED_TITLE,
        hosted_api.NOT_CONFIGURED_CODE,
        hint,
        hardware=_foot(hosted),
        state="not_configured",
    )


def status_card(status: hosted_api.HostedStatus) -> str:
    """The boot status as one quiet card, or nothing when the lane is ready.

    Not configured: the lane is off and the controls are not shown. Unavailable or throttled at
    boot: the controls stay (a run asks the engine again) and this card, above them, says what
    the boot probe found — one human sentence, the code in the chip, no address."""
    foot = f"{FOOT_LABEL} · {status.checked_utc}".rstrip(" ·")
    if status.state is ConfigState.NOT_CONFIGURED:
        # A key the engine rejected is worth saying (the operator reads it); a key that is not
        # set is the generic sentence — neither names a variable or an address.
        rejected = status.reason == hosted_api.REJECTED_KEY_REASON
        return render_quiet_card(
            hosted_api.NOT_CONFIGURED_TITLE,
            hosted_api.NOT_CONFIGURED_CODE,
            status.reason if rejected else NOT_CONFIGURED_HINT,
            hardware=foot,
            state="not_configured",
        )
    if client_missing(status):
        return render_quiet_card(
            TITLE_LANE,
            CODE_CLIENT_MISSING,
            CLIENT_MISSING_HINT,
            hardware=foot,
            state="not_configured",
        )
    if status.state is ConfigState.UNAVAILABLE:
        return render_quiet_card(TITLE_LANE, CODE_UNAVAILABLE, BOOT_UNAVAILABLE_HINT, hardware=foot)
    if status.state is ConfigState.RATE_LIMITED:
        return render_quiet_card(
            TITLE_LANE, CODE_RATE_LIMITED, BOOT_RATE_LIMITED_HINT, hardware=foot
        )
    return ""


def empty_card() -> str:
    return render_empty_card(TITLE_EMPTY, EMPTY_TEXT, rows=EMPTY_ROWS, pending_text=PENDING_TEXT)


def loading_card(again: bool = False, gate: str = "", profile: str = DEFAULT_PROFILE) -> str:
    """The loading card: the run's sentence (the steps the profile will run), or Execute
    again's — which names the gate the engine is expected to hold the repeat at, when there is
    one."""
    if not again:
        return render_loading_card(TITLE_LANE, loading_text(profile))
    if gate:
        return render_loading_card(TITLE_LANE, LOADING_AGAIN_GATE_TEXT.format(gate=gate_name(gate)))
    return render_loading_card(TITLE_LANE, LOADING_AGAIN_TEXT)


def _steps_html(out: Outcome) -> str:
    rows = []
    rec = out.recommendation
    if rec is not None:
        conf = ""
        if rec.confidence is not None:
            conf = f" · {ENGINE_CONFIDENCE_TEXT} {rec.confidence:.2f}"
        rows.append(
            _row(
                step_name("recommend"),
                f"{rec.recommended_action}{conf} · {rec.total_actions} actions compared",
            )
        )
    dec = out.decision
    if dec is not None:
        rows.append(_row("Decision", dec.decision_id))
        conf_text = "–" if dec.confidence is None else f"{dec.confidence:g}"
        risk_text = "–" if dec.risk_p5 is None else f"{dec.risk_p5:g}"
        rows.append(
            _row(
                "Chosen action",
                f"{dec.chosen_action} · {DECLARED_CONFIDENCE_TEXT} {conf_text}"
                f" · {RISK_P5_TEXT} {risk_text}",
            )
        )
    if out.webhook_host:
        rows.append(_row(WEBHOOK_ROW_LABEL, WEBHOOK_ROW_TEXT.format(host=out.webhook_host)))
    return f'<div class="alg-gov-steps">{"".join(rows)}</div>'


def _integrity_html(integrity: Mapping[str, str], *, skip: frozenset[str] = frozenset()) -> str:
    """One row per integrity id, human name first; `skip` leaves out the ids another block of
    the same card has already printed (a fact appears once on a receipt)."""
    return "".join(
        _row(INTEGRITY_NAMES.get(key, key.replace("_", " ")), value)
        for key, value in integrity.items()
        if value and key not in skip
    )


def http_text(response_code: int | None) -> str:
    """`HTTP 200`, or `no HTTP response` when the engine's POST got no status at all."""
    return f"HTTP {response_code}" if response_code is not None else NO_HTTP_TEXT


def receipt_failed(receipt: Receipt) -> bool:
    return receipt.execution_status == STATUS_FAILED


def receipt_status_chip(receipt: Receipt) -> str:
    """The receipt's one status chip, in the tone of what the engine reported: `delivered ·
    HTTP 200` live, `webhook_failed · HTTP 502` (or `no HTTP response`) red — the POST failed
    during this run — and any other status the engine may report as a neutral chip with its
    words."""
    http = http_text(receipt.response_code)
    if receipt.delivered:
        return cards.status_chip("live", f"{DELIVERED_TEXT} · {http}")
    if receipt_failed(receipt):
        return cards.status_chip("error", f"{CODE_WEBHOOK_FAILED} · {http}")
    return _chip(f"engine {receipt.execution_status} · {http}")


def receipt_matches_post(receipt: Receipt, event: webhook_mod.HookEvent) -> bool:
    """The engine's receipt and the POST this Space accepted describe one decision: the same id,
    and every key of the receipt's `payload_summary` that the POST's `decision` block carries
    agrees with it."""
    if receipt.decision_id != event.decision_id:
        return False
    decision = event.event.body.get("decision")
    if not isinstance(decision, Mapping):
        return False
    for key, value in receipt.payload_summary.items():
        if key not in decision:
            continue
        presented = decision[key]
        if isinstance(value, int | float) and not isinstance(value, bool):
            if not webhook_mod.same_confidence(presented, float(value)):
                return False
        elif str(presented) != str(value):
            return False
    return True


def rejected_html(rejected: list[webhook_mod.Rejection], note: str = REJECTED_NOTE) -> str:
    """Refused POSTs naming this decision, in the error tone — never green, never their body."""
    if not rejected:
        return ""
    count = len(rejected)
    text = REJECTED_TEXT if count == 1 else f"{REJECTED_TEXT} · {count}"
    return (
        '<div class="alg-gov-hook">'
        f'<div class="alg-chips">{cards.status_chip("error", text)}'
        f"{_chip(rejected[-1].received_utc)}</div>"
        f'<p class="alg-card-note">{_esc(note)}</p>'
        "</div>"
    )


#: The integrity ids the receipt's own rows print; the POST's block repeats them (verified equal
#: by the hook before the POST was accepted) and the card does not.
RECEIPT_INTEGRITY: frozenset[str] = frozenset(webhook_mod.INTEGRITY_KEYS)


def body_block(body: Mapping[str, Any]) -> str:
    """The engine's POST body, whole, in the fleet's capped code block: it wraps inside its
    column, shows `ENGINE_JSON_LINES` lines and scrolls inside a region in the tab order."""
    return cards.code_block(
        json.dumps(body, indent=2, ensure_ascii=False, default=str, sort_keys=True),
        ENGINE_JSON_LANGUAGE,
        caption=WEBHOOK_BODY_CAPTION,
        max_lines=ENGINE_JSON_LINES,
    )


def webhook_html(out: Outcome) -> str:
    """The engine's POST as this Space verified and received it — shown only under a receipt
    the engine reported `delivered` and only when the accepted POST matches that receipt — or
    the truth about its absence: `not received yet` (neutral) when the engine reported delivery
    and the wait ran out, one sentence when the engine itself reported the POST failed. A POST
    this Space refused is `unexpected POST · rejected`, red, under either."""
    receipt = out.receipt
    event = out.webhook
    rejected = rejected_html(out.rejected)
    if receipt is None:
        return rejected
    if receipt.delivered and event is not None:
        if not receipt_matches_post(receipt, event):
            return rejected_html([*out.rejected, _mismatch(event)], MISMATCH_NOTE)
        received = cards.status_chip("live", f"webhook received {event.event.received_utc}")
        return (
            '<div class="alg-gov-hook">'
            f'<div class="alg-chips">{received}'
            f"{_chip(VERIFIED_TEXT)}{_chip(event.event.event or 'event')}</div>"
            f"{_row(BODY_ROW_LABEL, webhook_mod.describe_body(event.event.body))}"
            f"{_integrity_html(event.event.integrity, skip=RECEIPT_INTEGRITY)}"
            f"{body_block(event.event.body)}"
            f'<p class="alg-card-note">{_esc(NO_SIGNATURE_TEXT)}</p>'
            "</div>"
            f"{rejected}"
        )
    if receipt_failed(receipt):
        return f'<p class="alg-card-note">{_esc(WEBHOOK_FAILED_TEXT)}</p>{rejected}'
    if receipt.delivered:
        return (
            '<div class="alg-gov-hook">'
            f'<div class="alg-chips">{_chip(NOT_RECEIVED_TEXT)}</div>'
            f'<p class="alg-card-note">{_esc(WEBHOOK_MISSED_TEXT.format(wait=WEBHOOK_WAIT_S))}</p>'
            "</div>"
            f"{rejected}"
        )
    return rejected


def _mismatch(event: webhook_mod.HookEvent) -> webhook_mod.Rejection:
    return webhook_mod.Rejection(
        event.event.received_utc,
        webhook_mod.REASON_SUMMARY,
        event.decision_id,
        tuple(sorted(event.event.body)),
    )


def render_receipt(out: Outcome, hosted: HostedGoverned) -> str:
    """The engine's receipt as it stands: chip, hairline and webhook block follow
    `execution_status` (`receipt_status_chip`, `webhook_html`); a failed POST is the red card.
    Each fact once: `executed_at` is the sub-line's `<time>` (`executed_html`), the decision id
    the Decision row, the three integrity ids the receipt's rows and not again under the POST."""
    receipt = out.receipt
    if receipt is None:
        raise ValueError("render_receipt needs a receipt")
    chips = [receipt_status_chip(receipt)]
    if receipt.safety_overridden:
        chips.append(_chip("safety overridden", "warn"))
    integrity = {
        "policy_snapshot_id": receipt.policy_snapshot_id,
        "schema_snapshot_id": receipt.schema_snapshot_id,
        "manifest_version": receipt.manifest_version,
    }
    hook_html = webhook_html(out)
    tone = " alg-card-err" if receipt_failed(receipt) else ""
    return (
        f'<article class="alg-card{tone} alg-gov-card">'
        f'<h2 class="alg-card-title">{TITLE_RECEIPT}</h2>'
        f'<div class="alg-card-sub">{executed_html(receipt.executed_at)}</div>'
        f'<div class="alg-chips">{"".join(chips)}</div>'
        f"{_steps_html(out)}"
        f'<div class="alg-gov-integrity">{_integrity_html(integrity)}</div>'
        f"{hook_html}"
        f"{_foot_html(hosted)}"
        "</article>"
    )


def render_denial(out: Outcome, hosted: HostedGoverned) -> str:
    denial = out.denial
    if denial is None:
        raise ValueError("render_denial needs a denial")
    hint = (
        f'<p class="alg-card-note">{_esc(denial.override_hint)}</p>' if denial.override_hint else ""
    )
    status = f"HTTP {denial.status_code} · " if denial.status_code else ""
    return (
        '<article class="alg-card alg-card-warn alg-gov-card">'
        f'<h2 class="alg-card-title">{_esc(TITLE_DENIED.format(gate=gate_name(denial.gate)))}</h2>'
        f'<div class="alg-card-sub">{_esc(status)}synchronous, in the same call</div>'
        f'<div class="alg-chips">{cards.status_chip("measured", "held by the engine")}'
        f"{_chip(denial.code, 'warn')}</div>"
        f'<p class="alg-card-reason">{_esc(denial.message)}</p>'
        f"{hint}"
        f"{_steps_html(out)}"
        f"{rejected_html(out.rejected)}"
        f"{_foot_html(hosted)}"
        "</article>"
    )


def render_intercepted(out: Outcome, hosted: HostedGoverned) -> str:
    """The amber card for a chain the integration stopped: the title names the profile, the
    sub-line the call that never reached the engine, the sentence what did and did not happen
    for that tool (`intercept_text`), and the steps list only what ran — under `observe` the
    Recommendation row alone, no Decision row, since nothing was logged."""
    profile = out.intercepted_profile
    tool = out.intercepted_tool or "execute_decision"
    return (
        '<article class="alg-card alg-card-warn alg-gov-card">'
        f'<h2 class="alg-card-title">{_esc(TITLE_INTERCEPTED.format(profile=profile))}</h2>'
        f'<div class="alg-card-sub">{_esc(INTERCEPT_SUB_TEXT.format(call=call_word(tool)))}</div>'
        f'<div class="alg-chips">{cards.status_chip("measured", "intercepted by the integration")}'
        f"{_chip(INTERCEPT_CODE, 'warn')}</div>"
        f'<p class="alg-card-reason">{_esc(intercept_text(tool))}</p>'
        f'<p class="alg-card-note">The {_esc(profile)} profile exposes:</p>'
        f'<div class="alg-chips">{tool_chips(profile)}</div>'
        f"{_steps_html(out)}"
        f"{_foot_html(hosted)}"
        "</article>"
    )


def render_outcome(out: Outcome, hosted: HostedGoverned) -> str:
    if out.receipt is not None:
        return render_receipt(out, hosted)
    if out.denial is not None:
        return render_denial(out, hosted)
    if out.intercepted_profile:
        return render_intercepted(out, hosted)
    raise ValueError("an outcome has a receipt, a denial or an interception")


def error_code_of(exc: BaseException) -> str:
    """The one code the card and the audit print for `exc` — the lane's own for a `HostedError`,
    `invalid_input` for a refused input, `unexpected_error` for anything the lane did not
    normalise."""
    if isinstance(exc, NotConfiguredError):
        return hosted_api.NOT_CONFIGURED_CODE
    if isinstance(exc, RateLimitedError):
        return CODE_RATE_LIMITED
    if isinstance(exc, EngineUnavailableError):
        return CODE_UNAVAILABLE
    if isinstance(exc, EngineError):
        return cards.normalize_code(exc.code)
    if isinstance(exc, HostedError):
        return "hosted_error"
    if isinstance(exc, ValueError):
        return CODE_INVALID
    return CODE_UNEXPECTED


def render_error(exc: BaseException, hosted: HostedGoverned | None) -> str:
    """Every failure as a card with a code the runbook indexes: a refusal (no key, a throttled
    tenant, no decision to send again) is the quiet card; an engine, transport or input failure
    during the run is the red one; an exception the lane did not normalise is the red
    `unexpected_error` card with one sentence and no traceback (the traceback is logged
    server-side by the handler)."""
    foot = _foot(hosted)
    if isinstance(exc, NotConfiguredError):
        return not_configured_card(hosted, str(exc) or NOT_CONFIGURED_HINT)
    if isinstance(exc, RateLimitedError):
        hint = f"{exc} Retry in {exc.retry_after_s:.0f} s."
        return render_quiet_card(TITLE_LANE, CODE_RATE_LIMITED, hint, hardware=foot)
    if isinstance(exc, EngineError) and exc.code == CODE_NO_DECISION:
        return render_quiet_card(TITLE_LANE, CODE_NO_DECISION, HINT_NO_DECISION, hardware=foot)
    if isinstance(exc, HostedError | ValueError):
        return render_failure_card(TITLE_LANE, error_code_of(exc), str(exc), hardware=foot)
    return render_failure_card(TITLE_LANE, CODE_UNEXPECTED, HINT_UNEXPECTED, hardware=foot)


def _failed(state: dict[str, Any], step: str, exc: BaseException, decision_id: str = "") -> None:
    """Log the failure server-side (the traceback for anything the lane did not normalise) and
    record one audit row whose outcome carries the card's code."""
    code = error_code_of(exc)
    if code == CODE_UNEXPECTED:
        log.exception("governed %s failed unexpectedly", step)
    else:
        log.warning("governed %s failed: %s: %s", step, type(exc).__name__, exc)
    _audit(state, step, f"failed · {code}", decision_id)


def render_audit(state: Mapping[str, Any]) -> str:
    entries = list(state.get("audit", ()))
    if not entries:
        return '<p class="alg-gov-empty">No decisions in this session yet.</p>'
    headers = ("when", "step", "outcome", "gate", "decision")
    rows = "".join(
        "<tr>"
        f'<td data-label="when">{_time_html(e.get("at", ""))}</td>'
        f'<td data-label="step" class="alg-stack-lead">{_esc(step_name(e.get("step", "")))}</td>'
        f'<td data-label="outcome">{_esc(e.get("outcome", ""))}</td>'
        f'<td data-label="gate">{_esc(gate_name(e.get("gate", "")) or "–")}</td>'
        f'<td data-label="decision" class="alg-gov-mono">{_esc(e.get("decision_id", "") or "–")}'
        "</td>"
        "</tr>"
        for e in reversed(entries)
    )
    head = "".join(f'<th scope="col">{h}</th>' for h in headers)
    return (
        '<table class="alg-stack-table alg-gov-audit">'
        f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
    )


#: What stands in for the nonce wherever an engine body repeats the webhook URL.
NONCE_REDACTED = "[nonce hidden]"


def raw_json(out: Outcome | None, hook: webhook_mod.Hook | None = None) -> str:
    """Every engine body of the run as JSON — with the webhook nonce redacted wherever the
    engine echoed the URL it was given (the receipt's `webhook_url`), so the disclosure
    publishes no more than the card does."""
    text = json.dumps(out.raw if out is not None else {}, indent=2, default=str, sort_keys=True)
    if hook is not None and hook.nonce:
        text = text.replace(hook.nonce, NONCE_REDACTED)
    return text


def has_engine_json(text: str) -> bool:
    """True when the JSON holds at least one engine body — the Engine responses disclosure is
    shown exactly then, never as an open block reading `{}`."""
    stripped = text.strip()
    return bool(stripped) and stripped != "{}"


def render_engine_json(text: str) -> str:
    """The Engine responses block: the whole JSON in the fleet's capped code block — `LABEL_RAW`
    and the line count as its caption and its accessible name, `ENGINE_JSON_LINES` lines
    visible, the rest one scroll away inside a region that is in the tab order. Nothing is
    cut, so no cap note is needed; `Copy JSON` beside it copies the same text. A text without
    a body renders `{}`, never an empty block (the disclosure is hidden then anyway)."""
    return cards.code_block(
        text.strip() or "{}",
        ENGINE_JSON_LANGUAGE,
        caption=LABEL_RAW,
        max_lines=ENGINE_JSON_LINES,
    )


def copy_json_chip(gr: Any, source: Any) -> Any:
    """The fleet's 44 px Copy chip beside the Engine responses block, labelled `Copy JSON`
    (`cards.copy_label`): client-side, relabels itself `Copied`."""
    with gr.Row(elem_classes=["alg-copy-row"]):
        button = gr.Button(
            COPY_JSON_TEXT,
            variant="secondary",
            elem_classes=["alg-chip-btn", COPY_JSON_CLASS],
            scale=0,
        )
    button.click(None, [source], [button], js=COPY_JSON_JS, api_name=False, show_progress="hidden")
    return button


def request_preview(
    action: str = DEFAULT_ACTION,
    low: float = LOW[3],
    high: float = HIGH[3],
    hold_value: float = HOLD_VALUE[3],
) -> str:
    """The Engine JSON block's opening value: the `/v1/recommend` body the default run sends —
    the same `recommend_actions` the handler builds — so the block is never empty and what it
    shows is real."""
    actions = recommend_actions(action, low, high, hold_value)
    body = {"recommend": {"actions": actions, "runs": RUNS}}
    return json.dumps(body, indent=2, sort_keys=True)


def profile_html(profile: str) -> str:
    """The profile's one-line description and, under it, a chip per tool it allows — no chip
    row at all for a profile whose tools the line already names (`full`)."""
    if profile not in PROFILES:
        profile = PROFILES[0]
    chips = tool_chips(profile)
    row = f'<div class="alg-chips alg-gov-tools">{chips}</div>' if chips else ""
    return f'<p class="alg-gov-profile">{_esc(PROFILE_LINES[profile])}</p>{row}'


# ---------------------------------------------------------------------------
# Handlers (pure: deps + inputs → outputs), wired by render()
# ---------------------------------------------------------------------------

Outputs = tuple[str, str, str, dict[str, Any]]


def on_run(
    deps: Deps,
    hosted: HostedGoverned | None,
    hook: webhook_mod.Hook | None,
    profile: str,
    action: Any,
    low: Any,
    high: Any,
    hold_value: Any,
    confidence: Any,
    risk_p5: Any,
    force: bool,
    override_safety: bool,
    state: Any,
    request: Any = None,
    status: hosted_api.HostedStatus | None = None,
) -> Outputs:
    """(card, raw engine json, audit html, state) — the handler behind `gov_run`.

    A refused input (`check_inputs`) returns the empty card with nothing run and nothing
    audited; the page draws the refusal under its control and in the status row. Nothing else
    escapes: a lane error is its coded card, and any other exception is logged with its
    traceback and rendered as the `unexpected_error` card, so the page never shows a stock
    toast and the loading card always resolves. The engine JSON carries every body the run
    did get, whether or not a later step failed (no public base after recommend and
    log_decision, say); it is `{}` only when the engine was never called."""
    state = ensure_state(state)
    out = Outcome()
    try:
        stop = _lane_gate(deps, hosted, request, status)
        if stop is not None:
            return stop, raw_json(None, hook), render_audit(state), state
        assert hosted is not None  # noqa: S101 - _lane_gate returned None
        if check_inputs(action, low, high, hold_value, confidence, risk_p5) is not None:
            return empty_card(), raw_json(None, hook), render_audit(state), state
        run_chain(
            hosted,
            hook,
            profile=str(profile),
            action=clean_action(action),
            low=_number("low", low, LOW),
            high=_number("high", high, HIGH),
            hold_value=_number("hold_value", hold_value, HOLD_VALUE),
            confidence=_number("confidence", confidence, CONFIDENCE),
            risk_p5=_number("risk_p5", risk_p5, RISK_P5),
            force=bool(force),
            override_safety=bool(override_safety),
            state=state,
            out=out,
        )
        return render_outcome(out, hosted), raw_json(out, hook), render_audit(state), state
    except Exception as exc:  # noqa: BLE001 - every failure is a card, never a toast
        _failed(state, "run", exc)
        return render_error(exc, hosted), raw_json(out, hook), render_audit(state), state


def on_execute_again(
    deps: Deps,
    hosted: HostedGoverned | None,
    hook: webhook_mod.Hook | None,
    profile: str,
    force: bool,
    override_safety: bool,
    state: Any,
    request: Any = None,
    status: hosted_api.HostedStatus | None = None,
) -> Outputs:
    """Re-send the session's last decision id and render what the engine answered: a new
    receipt after a failed delivery, the idempotency denial after a delivered one, the gate it
    named after a denial; a lower profile intercepts it first. Catches everything, like
    `on_run`."""
    state = ensure_state(state)
    decision_id = str(state.get("last_decision_id") or "")
    out = Outcome()
    try:
        stop = _lane_gate(deps, hosted, request, status)
        if stop is not None:
            return stop, raw_json(None, hook), render_audit(state), state
        assert hosted is not None  # noqa: S101 - _lane_gate returned None
        if not decision_id or decision_id not in state["decisions"]:
            card = render_quiet_card(
                TITLE_LANE, CODE_NO_DECISION, HINT_NO_DECISION, hardware=_foot(hosted)
            )
            return card, raw_json(None, hook), render_audit(state), state
        chosen = str(profile) if str(profile) in PROFILES else PROFILES[0]
        blocked = first_tool_outside_profile(chosen, ("execute_decision",))
        if blocked:
            out.intercepted_profile = chosen
            out.intercepted_tool = blocked
            _audit(state, blocked, "intercepted", decision_id, INTERCEPT_GATE)
            return render_intercepted(out, hosted), raw_json(out, hook), render_audit(state), state
        execute_into(hosted, hook, out, decision_id, bool(force), bool(override_safety), state)
        return render_outcome(out, hosted), raw_json(out, hook), render_audit(state), state
    except Exception as exc:  # noqa: BLE001 - every failure is a card, never a toast
        _failed(state, "execute_decision", exc, decision_id)
        return render_error(exc, hosted), raw_json(out, hook), render_audit(state), state


#: Sentinel a staged handler yields for an output it leaves as it is.
KEEP = object()


def staged(loading: str, run: Any) -> Iterator[tuple[Any, Any, Any, Any]]:
    """The loading card at once (JSON, audit and state untouched), then the four outputs."""
    yield loading, KEEP, KEEP, KEEP
    yield run()


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_MONO = "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"

# alg-gov-* classes only; the audit table shape is llm_tab.STATE_CSS's alg-stack-table, the
# two-column layout css.LAYOUT_CSS and the JSON blocks cards.CARD_CSS's capped code block.
GOV_CSS = stylesheet(
    rule("alg-gov-steps", "display: flex; flex-direction: column; gap: 4px; margin: 12px 0 0;"),
    rule("alg-gov-integrity", "display: flex; flex-direction: column; gap: 4px; margin: 12px 0 0;"),
    rule("alg-gov-hook", "margin: 12px 0 0;"),
    rule("alg-gov-row", f"display: flex; flex-wrap: wrap; gap: 4px 16px; {_CAPTION}"),
    rule("alg-gov-key", "flex: 0 0 160px; color: var(--alg-text-2);"),
    rule("alg-gov-val", f"flex: 1 1 240px; {_MONO} overflow-wrap: anywhere;"),
    rule("alg-gov-profile", f"{_CAPTION} color: var(--alg-text-2); margin: 4px 0 0;"),
    rule("alg-gov-tools", "margin: 8px 0 0;"),
    rule("alg-gov-mono", f"{_MONO} overflow-wrap: anywhere;"),
    rule("alg-gov-empty", f"{_CAPTION} color: var(--alg-text-2); margin: 0;"),
    # the results column: the fill block takes the column's slack as page (css.LAYOUT_CSS) and a
    # Governed card — receipt, denial, interception, empty — is never taller than its content
    # (the shared contract would grow a result card to the column; the review measured 450 px
    # between an interception's last row and its foot)
    rule(RESULTS_COL_CLASS, "flex: 0 0 auto;", suffix=" .alg-card"),
    # the Copy JSON chip: its natural width (Gradio's row gives a button `flex: 1` with a 0 basis,
    # which the copy row's 96 px minimum turns into a two-line `Copy / JSON`), one line
    rule(COPY_JSON_CLASS, "flex: 0 0 auto; white-space: nowrap;"),
    # a field message under a control takes no block padding of its own
    rule("alg-gov-field-msg", "padding: 0;"),
    rule("alg-gov-field-msg", "padding: 0;", suffix=" > div"),
    # the Profile pills below 1280 px: two even rows of two, each pill half the row (the flex
    # basis makes two fit and a third not), 44 px tall; the row is 44 + 8 + 44 on the grid
    block(
        f"@media (width <= {PROFILE_GRID_MAX_WIDTH}px)",
        rule(PROFILE_RADIO_CLASS, "flex: 1 1 40%;", suffix=' label:has(> input[type="radio"])'),
    ),
)


def build(
    deps: Deps,
    *,
    hosted: HostedGoverned | None = None,
    hook: webhook_mod.Hook | None = None,
    status: hosted_api.HostedStatus | None = None,
) -> TabSpec:
    """The tab spec. `hosted` defaults to the lane over `deps.env`; `hook` is the receiver the
    shell mounted (without one the execute step returns `webhook_url_unavailable`).

    The page: the boot card when the lane is not ready, then two equal columns that stack on a
    phone (`css.LAYOUT_CSS`: `COLS_CLASS` on the row, `CONTROLS_CLASS` and `RESULTS_CLASS` on
    the columns, `FILL_CLASS` on the card block — the controls keep their height, the card its
    content's): the controls (profile, action, the sliders two to a row with a message slot
    under each row, Run with its status row, the operator boxes, Execute again) and the result
    card. Under the row, at the page's width: the Engine responses disclosure (hidden until an
    engine call and collapsed then, the JSON in the capped code block with its Copy JSON chip),
    this session's audit (shown with the controls), then Connect and How this works, shown
    whether or not the lane is configured. A boot probe that failed because the SDK client is
    not installed (`client_missing`) is treated as not configured: one quiet card, no controls,
    and both endpoints answer with that card."""
    lane = HostedGoverned(env=deps.env) if hosted is None else hosted
    boot_status = lane.status() if status is None else status
    configured = boot_status.state is not ConfigState.NOT_CONFIGURED and not client_missing(
        boot_status
    )
    for text in (
        LABEL,
        RUN_TEXT,
        AGAIN_TEXT,
        CONNECT_TITLE,
        ENGINE_JSON_TITLE,
        AUDIT_TITLE,
        COPY_JSON_TEXT,
        LABEL_RAW,
        WEBHOOK_BODY_CAPTION,
        BODY_ROW_LABEL,
    ):
        check_copy(text, max_words=6, what="gov tab label")
    for text in (AGAIN_NEW_RECEIPT_TEXT, AGAIN_EXPECT_GATE_TEXT.format(gate="idempotency")):
        check_copy(text, max_words=8, what="gov tab label")
    for text in (
        HOW_TEXT,
        NOT_CONFIGURED_HINT,
        BOOT_UNAVAILABLE_HINT,
        BOOT_RATE_LIMITED_HINT,
        EMPTY_TEXT,
        LOADING_TEXT,
        LOADING_AGAIN_TEXT,
        LOADING_AGAIN_GATE_TEXT.format(gate="idempotency"),
        *(loading_text(p) for p in PROFILES),
        INTERCEPT_TEXT,
        INTERCEPT_LOG_TEXT,
        *(INTERCEPT_SUB_TEXT.format(call=call_word(t)) for t in CHAIN_TOOLS),
        NO_SIGNATURE_TEXT,
        REJECTED_NOTE,
        ENGINE_NOTE_TEXT,
    ):
        check_copy(text, what="gov copy")
    for text in (LABEL_CONFIDENCE, LABEL_RISK, LABEL_FORCE, LABEL_OVERRIDE):
        check_copy(text, max_words=6, what="gov control label")
    for line in PROFILE_LINES.values():
        check_copy(line, max_words=14, what="profile line")

    def render(gr: Any) -> dict[str, Any]:
        handles: dict[str, Any] = {"configured": configured, "status": boot_status}
        boot_card = status_card(boot_status)
        if boot_card:
            handles["status_card"] = gr.HTML(boot_card, elem_classes=[common.BLOCK_CLASS])
        state = gr.State(initial_state())

        def slider(spec: tuple, label: str) -> Any:
            # a number box, not a slider: a typed value above the range must be refused with a
            # field message, never clamped in silence (round 9: Rows 50 kept '50' in the box while
            # the slider and the run used 32); the handlers' range checks answer
            return gr.Number(value=spec[3], label=label, step=spec[2], precision=None)

        def pair(*builders: Any) -> list[Any]:
            """Two controls side by side, one column each, one under the other on a phone."""
            made = []
            with gr.Row():
                for build_control in builders:
                    with gr.Column(min_width=CONTROL_MIN_WIDTH):
                        made.append(build_control())
            return made

        def message_slot() -> Any:
            """The message under a control or a row of controls: hidden until a refusal."""
            return gr.HTML("", elem_classes=["alg-gov-field-msg"], visible=False)

        with gr.Row(visible=configured, elem_classes=[COLS_CLASS]) as controls:
            with gr.Column(
                scale=1, min_width=COLUMN_MIN_WIDTH, elem_classes=[CONTROLS_CLASS]
            ) as controls_column:
                profile = gr.Radio(
                    choices=[(PROFILE_LABELS[p], p) for p in PROFILES],
                    value=DEFAULT_PROFILE,
                    label=LABEL_PROFILE,
                    elem_classes=[PROFILE_RADIO_CLASS],
                )
                profile_note = gr.HTML(
                    profile_html(DEFAULT_PROFILE), elem_classes=[common.BLOCK_CLASS]
                )
                action = gr.Textbox(value=DEFAULT_ACTION, label=LABEL_ACTION)
                action_msg = message_slot()
                low, high = pair(lambda: slider(LOW, LABEL_LOW), lambda: slider(HIGH, LABEL_HIGH))
                values_msg = message_slot()
                hold_value, confidence = pair(
                    lambda: slider(HOLD_VALUE, LABEL_HOLD),
                    lambda: slider(CONFIDENCE, LABEL_CONFIDENCE),
                )
                hold_msg = message_slot()
                risk_p5 = slider(RISK_P5, LABEL_RISK)
                risk_msg = message_slot()
                run = gr.Button(RUN_TEXT, variant="primary", size="lg", elem_classes=["alg-run"])
                status_row = gr.HTML(common.render_status(), elem_classes=["alg-status-row"])
                force, override = pair(
                    lambda: gr.Checkbox(value=False, label=LABEL_FORCE),
                    lambda: gr.Checkbox(value=False, label=LABEL_OVERRIDE),
                )
                # disabled until this session holds a decision to re-send (launch review round 3:
                # an enabled Execute again before any decision)
                again = gr.Button(
                    AGAIN_TEXT,
                    variant="secondary",
                    size="lg",
                    elem_classes=["alg-run"],
                    interactive=False,
                )
            with gr.Column(
                scale=1,
                min_width=COLUMN_MIN_WIDTH,
                elem_classes=[RESULTS_CLASS, RESULTS_COL_CLASS],
            ) as results:
                card = gr.HTML(
                    empty_card(), elem_classes=[FILL_CLASS, CARD_BLOCK_CLASS, common.BLOCK_CLASS]
                )
        with gr.Accordion(
            ENGINE_JSON_TITLE, open=False, visible=False, elem_classes=["alg-disclosure"]
        ) as raw_disclosure:
            raw = gr.HTML(render_engine_json(request_preview()), elem_classes=[common.BLOCK_CLASS])
            raw_full = gr.Textbox(request_preview(), visible=False)
            copy_json = copy_json_chip(gr, raw_full)
        with gr.Accordion(
            AUDIT_TITLE, open=False, visible=configured, elem_classes=["alg-disclosure"]
        ) as audit_disclosure:
            audit = gr.HTML(render_audit(initial_state()), elem_classes=[common.BLOCK_CLASS])
        with gr.Accordion(CONNECT_TITLE, open=False, elem_classes=["alg-disclosure"]):
            engine_note = gr.HTML(
                common.render_note(ENGINE_NOTE_TEXT), elem_classes=[common.BLOCK_CLASS]
            )
            # One column: side by side, the 10-line MCP config ended 320 px above the 25-line
            # smolagents example (a void the review found with the disclosure open).
            mcp_code = gr.Code(
                value=MCP_CLIENT_CONFIG,
                language="json",
                label=LABEL_MCP,
                wrap_lines=True,
                buttons=[],
                interactive=False,
            )
            copy_chip(gr, mcp_code)
            smol_code = gr.Code(
                value=SMOLAGENTS_SNIPPET,
                language="python",
                label=LABEL_SMOL,
                wrap_lines=True,
                buttons=[],
                interactive=False,
            )
            copy_chip(gr, smol_code)
            engine_code = gr.Code(
                value=engine_url(lane),
                language=None,
                label=ENGINE_CODE_LABEL,
                lines=1,
                wrap_lines=True,
                buttons=[],
                interactive=False,
            )
        with gr.Accordion(HOW_TITLE, open=False, elem_classes=["alg-disclosure"]):
            gr.HTML(common.render_note(HOW_TEXT))

        profile.change(profile_html, profile, profile_note, api_name=False, show_progress="hidden")

        slots = {
            SLOT_ACTION: action_msg,
            SLOT_VALUES: values_msg,
            SLOT_HOLD: hold_msg,
            SLOT_RISK: risk_msg,
        }
        outputs = [
            card,
            raw,
            audit,
            state,
            raw_disclosure,
            raw_full,
            again,
            *(slots[slot] for slot in SLOTS),
            status_row,
        ]

        def _slot_updates(refusal: Refusal | None) -> list[Any]:
            messages = field_messages(refusal)
            return [gr.update(value=messages[slot], visible=bool(messages[slot])) for slot in SLOTS]

        def _outputs(card_html: Any, raw_text: Any, audit_html: Any, new_state: Any) -> tuple:
            """The handler's four values spread over every output the page redraws."""
            skip = gr.skip()
            if raw_text is KEEP:
                raw_updates: list[Any] = [skip, skip, skip]
            else:
                raw_updates = [
                    render_engine_json(raw_text),
                    gr.update(visible=has_engine_json(raw_text)),
                    raw_text,
                ]
            again_update = (
                skip
                if new_state is KEEP
                else gr.update(
                    value=again_label(new_state),
                    interactive=bool(new_state.get("last_decision_id")),
                )
            )
            return (
                skip if card_html is KEEP else card_html,
                raw_updates[0],
                skip if audit_html is KEEP else audit_html,
                skip if new_state is KEEP else new_state,
                raw_updates[1],
                raw_updates[2],
                again_update,
                *_slot_updates(None),
                status_html(None),
            )

        def _refused(refusal: Refusal) -> tuple:
            skip = gr.skip()
            return (
                empty_card(),
                skip,
                skip,
                skip,
                skip,
                skip,
                skip,
                *_slot_updates(refusal),
                status_html(refusal),
            )

        def _emit(stage: Iterator[tuple[Any, Any, Any, Any]]):
            for values in stage:
                yield _outputs(*values)

        def _run(p, a, lo, hi, hv, c, r, f, o, s, request=None):
            refusal = check_inputs(a, lo, hi, hv, c, r)
            if refusal is not None:
                yield _refused(refusal)
                return
            yield from _emit(
                staged(
                    loading_card(profile=str(p)),
                    lambda: on_run(
                        deps, lane, hook, p, a, lo, hi, hv, c, r, f, o, s, request, boot_status
                    ),
                )
            )

        def _again(p, f, o, s, request=None):
            gate = expected_gate(ensure_state(s))
            yield from _emit(
                staged(
                    loading_card(again=True, gate=gate),
                    lambda: on_execute_again(deps, lane, hook, p, f, o, s, request, boot_status),
                )
            )

        def _clear() -> tuple:
            """A refusal under a control clears the moment the visitor edits any of them."""
            return (*_slot_updates(None), status_html(None))

        request_hint(_run, gr)
        request_hint(_again, gr)
        hosted_event = {
            "concurrency_id": "hosted",
            "concurrency_limit": 2,
            "show_progress": "hidden",
        }

        run.click(
            _run,
            [profile, action, low, high, hold_value, confidence, risk_p5, force, override, state],
            outputs,
            api_name=API_RUN,
            **hosted_event,
        )
        again.click(
            _again,
            [profile, force, override, state],
            outputs,
            api_name=API_EXECUTE_AGAIN,
            **hosted_event,
        )
        for control in (action, low, high, hold_value, confidence, risk_p5):
            control.input(
                _clear,
                None,
                [*(slots[slot] for slot in SLOTS), status_row],
                api_name=False,
                show_progress="hidden",
            )
        handles.update(
            controls=controls,
            controls_column=controls_column,
            results=results,
            audit_disclosure=audit_disclosure,
            copy_json=copy_json,
            profile=profile,
            action=action,
            low=low,
            high=high,
            hold_value=hold_value,
            confidence=confidence,
            risk_p5=risk_p5,
            run=run,
            again=again,
            force=force,
            override=override,
            card=card,
            raw=raw,
            raw_disclosure=raw_disclosure,
            raw_full=raw_full,
            audit=audit,
            state=state,
            status_row=status_row,
            slots=slots,
            mcp_code=mcp_code,
            smol_code=smol_code,
            engine_note=engine_note,
            engine_code=engine_code,
            outputs=outputs,
            refused=_refused,
            spread=_outputs,
        )
        return handles

    return TabSpec(id=TAB_GOV, label=LABEL, render=render, api_names=API_NAMES)
