"""algenta_spaces.hosted_api — a fake client with the engine's real wire shapes, no network.

The canned bodies below are copied from the shapes `governed.py` and the API
routers return (`DecisionLogResponse`, the execute confirmation, the 409 gate
body, `RecommendResponse`, `MeResult`). They are test data, not app code.
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

import pytest
from _rules import _assert_clean_copy
from algenta_spaces import hosted_api
from algenta_spaces.hosted_api import (
    ConfigState,
    Denial,
    EngineError,
    EngineUnavailableError,
    HostedGoverned,
    NotAllowedError,
    NotConfiguredError,
    RateLimitedError,
    Receipt,
)

KEY = "de_test_0123456789abcdefABCDEF"  # gitleaks:allow - test fake, shaped like SECRET_RE
ODD_KEY = "plain-key-with-no-prefix-0001"
DECISION_ID = "8b4a1f2e-0c3d-4e5f-9a6b-7c8d9e0f1a2b"
WEBHOOK = "https://thyn-ai-algenta.hf.space/hook/abc"

ME_BODY = {
    "user": {"id": "usr_1", "email": "ops@example.org", "name": "Ops"},
    "org": {"id": "org_1", "name": "demo-tenant", "plan": "free"},
}
RECOMMEND_BODY = {
    "recommended_action": "expand_eu",
    "confidence": 0.87,
    "rationale": "Highest expected value with acceptable downside.",
    "action_results": [{"name": "expand_eu"}, {"name": "hold"}],
    "total_actions": 2,
    "decision_plan": None,
}
LOG_BODY = {
    "id": DECISION_ID,
    "org_id": "org_1",
    "run_id": None,
    "context": "Logged from the Algenta flagship Space.",
    "chosen_action": "expand_eu",
    "options_considered": ["expand_eu", "hold"],
    "expected_value": 120.5,
    "confidence": 0.87,
    "rationale": "Interactive governed-execution walkthrough.",
    "risk_p5": -0.02,
    "risk_p95": 0.4,
    "risk_pol": 0.1,
    "request_hash": "sha256:req",
    "result_hash": "sha256:res",
    "policy_snapshot_id": "policy-snap-7",
    "schema_snapshot_id": "schema-snap-3",
    "manifest_version": "1.0.24",
    "actual_outcome": None,
    "outcome_delta": None,
    "outcome_notes": None,
    "outcome_recorded_at": None,
    "executed_at": None,
    "execution_status": None,
    "execution_webhook_url": None,
    "execution_response_code": None,
    "created_at": "2026-09-22T14:02:00Z",
    "updated_at": "2026-09-22T14:02:00Z",
}
RECEIPT_BODY = {
    "decision_id": DECISION_ID,
    "webhook_url": WEBHOOK,
    "execution_status": "delivered",
    "response_code": 200,
    "executed_at": "2026-09-22T14:03:10Z",
    "policy_snapshot_id": "policy-snap-7",
    "schema_snapshot_id": "schema-snap-3",
    "manifest_version": "1.0.24",
    "payload_summary": {"chosen_action": "expand_eu"},
    "safety_overridden": False,
}
DENIAL_409 = {
    "error": {
        "code": "execution_blocked_confidence",
        "gate": "confidence",
        "message": "Decision confidence 0.61 is below policy.min_confidence 0.8.",
        "override_hint": "Pass override_safety=true (operator only) to bypass the confidence gate.",
    }
}
AUTH_401 = {"error": {"code": "invalid_api_key", "message": f"Invalid API key {KEY}"}}
RATE_429 = {"error": {"code": "rate_limited", "message": "Rate limit exceeded"}}
WEBHOOK_POST = {
    "event": "decision.execute",
    "decision_id": DECISION_ID,
    "org_id": "org_1",
    "decision": {"chosen_action": "expand_eu", "confidence": 0.87},
    "integrity": {
        "request_hash": "sha256:req",
        "result_hash": "sha256:res",
        "policy_snapshot_id": "policy-snap-7",
        "schema_snapshot_id": "schema-snap-3",
        "manifest_version": "1.0.24",
    },
}


class SdkError(Exception):
    """The attribute surface of `decision_engine.DecisionEngineError`."""

    def __init__(self, message: str, status_code: int, body: dict[str, Any], request_id: str):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = body
        self.error_code = body.get("error", {}).get("code", "unknown_error")
        self.request_id = request_id


class SdkRateLimitError(SdkError):
    def __init__(self, retry_after: int):
        super().__init__("Rate limit exceeded", 429, RATE_429, "req_429")
        self.retry_after = retry_after


class Model:
    """A pydantic-shaped object: `model_dump(mode="json")`."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        assert mode == "json"
        return dict(self._data)


class FakeClient:
    def __init__(self, api_key: str, base_url: str | None, *, responses: dict[str, Any]):
        self.api_key = api_key
        self.base_url = base_url
        self.responses = responses
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _answer(self, name: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((name, args, kwargs))
        answer = self.responses[name]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def me(self) -> Any:
        return self._answer("me")

    def recommend(self, actions: Any, **kwargs: Any) -> Any:
        return self._answer("recommend", actions, **kwargs)

    def log_decision(self, request: dict[str, Any]) -> Any:
        return self._answer("log_decision", request)

    def execute_decision(self, decision_id: str, **kwargs: Any) -> Any:
        return self._answer("execute_decision", decision_id, **kwargs)

    def get_decision(self, decision_id: str) -> Any:
        return self._answer("get_decision", decision_id)

    def delete_decision(self, decision_id: str) -> Any:  # never allow-listed
        return self._answer("delete_decision", decision_id)


def make(
    responses: dict[str, Any] | None = None,
    *,
    key: str = KEY,
    env_extra: dict[str, str] | None = None,
    **kwargs: Any,
) -> tuple[HostedGoverned, list[FakeClient]]:
    canned = {
        "me": Model(ME_BODY),
        "recommend": dict(RECOMMEND_BODY),
        "log_decision": Model(LOG_BODY),
        "execute_decision": dict(RECEIPT_BODY),
        "get_decision": Model({**LOG_BODY, "execution_status": "delivered"}),
    }
    canned.update(responses or {})
    made: list[FakeClient] = []

    def factory(api_key: str, base_url: str | None) -> FakeClient:
        client = FakeClient(api_key, base_url, responses=canned)
        made.append(client)
        return client

    env = {"ALGENTA_API_KEY": key} if key else {}
    env.update(env_extra or {})
    return HostedGoverned(factory, env=env, **kwargs), made


# --- configuration ------------------------------------------------------------


def test_without_a_key_nothing_is_called_and_every_call_raises_not_configured():
    hg, made = make(key="")
    assert hg.configured is False
    status = hg.status()
    assert status.state is ConfigState.NOT_CONFIGURED
    assert status.reason == hosted_api.NOT_CONFIGURED_REASON
    assert not status.ready
    with pytest.raises(NotConfiguredError):
        hg.recommend([{"name": "a"}])
    with pytest.raises(NotConfiguredError):
        hg.log_decision("a", confidence=0.9, risk_p5=0.0, context="c", rationale="r")
    with pytest.raises(NotConfiguredError):
        hg.execute_decision(DECISION_ID, webhook_url=WEBHOOK)
    with pytest.raises(NotConfiguredError):
        hg.get_decision(DECISION_ID)
    assert made == []


def test_the_key_is_read_from_the_injected_env_name_and_never_appears_in_repr_or_attributes():
    hg = HostedGoverned(
        lambda api_key, base_url: FakeClient(api_key, base_url, responses={}),
        env={"SPACE_KEY": KEY, "ALGENTA_API_KEY": "de_live_wrong_one_000000"},
        key_env="SPACE_KEY",
    )
    assert hg.configured
    assert KEY not in repr(hg)
    for value in vars(hg).values():
        assert not (isinstance(value, str) and KEY in value)
    assert hg.key_env == "SPACE_KEY"


def test_base_url_env_reaches_the_factory_and_the_client_is_built_once():
    hg, made = make(env_extra={"ALGENTA_BASE_URL": "https://api.example.org"})
    assert hg.base_url == "https://api.example.org"
    hg.status()
    hg.get_decision(DECISION_ID)
    assert len(made) == 1
    assert made[0].api_key == KEY
    assert made[0].base_url == "https://api.example.org"


def test_the_base_url_is_always_explicit_and_never_read_from_the_process_env(monkeypatch):
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("DE_BASE_URL", "http://127.0.0.1:1")
    hg, made = make()
    assert hg.base_url == hosted_api.DEFAULT_BASE_URL == "https://api.algenta.ai"
    hg.status()
    assert made[0].base_url == "https://api.algenta.ai"
    assert "https://api.algenta.ai" in repr(hg)
    with pytest.raises(ValueError, match="https"):
        make(env_extra={"ALGENTA_BASE_URL": "http://api.example.org"})
    hg, _ = make(env_extra={"ALGENTA_BASE_URL": "http://localhost:8000"})
    assert hg.base_url == "http://localhost:8000"


def test_allow_list_narrowing_refuses_before_the_client_exists():
    hg, made = make(allow={"me", "recommend", "log_decision", "get_decision"})
    with pytest.raises(NotAllowedError, match="execute_decision"):
        hg.execute_decision(DECISION_ID, webhook_url=WEBHOOK)
    assert made == []
    with pytest.raises(ValueError, match="delete_decision"):
        make(allow={"me", "delete_decision"})


# --- status probe ---------------------------------------------------------------


def test_status_ready_carries_the_org_and_a_utc_stamp():
    hg, made = make()
    status = hg.status(now=1_790_000_000.0)
    assert status.state is ConfigState.READY
    assert status.ready
    assert status.org == "demo-tenant"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", status.checked_utc)
    assert made[0].calls == [("me", (), {})]


@pytest.mark.parametrize("code", [401, 403])
def test_status_maps_rejected_keys_to_not_configured_without_the_key(code: int):
    err = SdkError(f"Invalid API key {KEY}", code, AUTH_401, "req_auth")
    hg, _ = make({"me": err, "get_decision": err})
    status = hg.status()
    assert status.state is ConfigState.NOT_CONFIGURED
    assert status.reason == hosted_api.REJECTED_KEY_REASON
    assert KEY not in status.reason
    with pytest.raises(NotConfiguredError) as info:
        hg.get_decision(DECISION_ID)
    assert info.value.status_code == code
    assert info.value.request_id == "req_auth"
    assert KEY not in str(info.value)


def test_status_maps_429_5xx_and_transport_failures():
    hg, _ = make({"me": SdkRateLimitError(retry_after=42)})
    status = hg.status()
    assert status.state is ConfigState.RATE_LIMITED
    assert "42 s" in status.reason
    hg, _ = make({"me": SdkError("upstream", 503, {}, "req_503")})
    assert hg.status().state is ConfigState.UNAVAILABLE
    hg, _ = make({"me": ConnectionError("dns")})
    status = hg.status()
    assert status.state is ConfigState.UNAVAILABLE
    assert "dns" in status.reason


# --- error normalisation ----------------------------------------------------------


def test_429_becomes_rate_limited_with_the_engine_hint():
    hg, _ = make({"get_decision": SdkRateLimitError(retry_after=7)})
    with pytest.raises(RateLimitedError) as info:
        hg.get_decision(DECISION_ID)
    assert info.value.retry_after_s == 7.0
    assert info.value.status_code == 429


def test_5xx_and_transport_errors_become_engine_unavailable():
    hg, _ = make({"get_decision": SdkError("boom", 502, {}, "req_502")})
    with pytest.raises(EngineUnavailableError) as info:
        hg.get_decision(DECISION_ID)
    assert info.value.status_code == 502
    hg, _ = make({"get_decision": TimeoutError("read timed out")})
    with pytest.raises(EngineUnavailableError, match="read timed out"):
        hg.get_decision(DECISION_ID)


def test_other_engine_errors_keep_their_code_and_scrubbed_message():
    body = {"error": {"code": "validation_error", "message": f"bad field, Bearer {KEY}"}}
    hg, _ = make({"get_decision": SdkError(f"bad field, Bearer {KEY}", 422, body, "req_422")})
    with pytest.raises(EngineError) as info:
        hg.get_decision(DECISION_ID)
    assert info.value.code == "validation_error"
    assert KEY not in str(info.value)
    assert KEY not in json.dumps(info.value.body)
    assert "[redacted]" in str(info.value)


def test_programming_errors_are_not_swallowed():
    hg, _ = make({"get_decision": TypeError("wrong call")})
    with pytest.raises(TypeError, match="wrong call"):
        hg.get_decision(DECISION_ID)


# --- the four calls ------------------------------------------------------------------


def test_recommend_normalises_the_response():
    hg, made = make()
    rec = hg.recommend([{"name": "expand_eu"}, {"name": "hold"}], context="q3")
    assert rec.recommended_action == "expand_eu"
    assert rec.confidence == pytest.approx(0.87)
    assert rec.total_actions == 2
    assert rec.raw["action_results"][1] == {"name": "hold"}
    assert made[0].calls[0][0] == "recommend"
    assert made[0].calls[0][2] == {"context": "q3"}


def test_log_decision_builds_the_request_and_returns_the_decision():
    hg, made = make()
    dec = hg.log_decision(
        "  expand_eu ",
        confidence=0.87123,
        risk_p5=-0.0204,
        context="ctx",
        rationale="why",
        options_considered=["expand_eu", "hold"],
    )
    request = made[0].calls[0][1][0]
    assert request == {
        "chosen_action": "expand_eu",
        "confidence": 0.871,
        "risk_p5": -0.02,
        "context": "ctx",
        "rationale": "why",
        "options_considered": ["expand_eu", "hold"],
    }
    assert dec.decision_id == DECISION_ID
    assert dec.chosen_action == "expand_eu"
    assert dec.execution_status is None
    assert dec.integrity == {
        "request_hash": "sha256:req",
        "result_hash": "sha256:res",
        "policy_snapshot_id": "policy-snap-7",
        "schema_snapshot_id": "schema-snap-3",
        "manifest_version": "1.0.24",
    }


def test_execute_decision_returns_the_receipt_and_passes_the_origin():
    hg, made = make()
    out = hg.execute_decision(
        f" {DECISION_ID} ", webhook_url=f" {WEBHOOK} ", timeout_seconds=5, force=True
    )
    assert isinstance(out, Receipt)
    assert out.delivered
    assert out.response_code == 200
    assert out.policy_snapshot_id == "policy-snap-7"
    assert out.payload_summary == {"chosen_action": "expand_eu"}
    assert out.safety_overridden is False
    name, args, kwargs = made[0].calls[0]
    assert (name, args) == ("execute_decision", (DECISION_ID,))
    assert kwargs == {
        "webhook_url": WEBHOOK,
        "timeout_seconds": 5.0,
        "force": True,
        "override_safety": False,
        "metadata": {"origin": hosted_api.DEFAULT_ORIGIN},
    }


def test_execute_decision_turns_a_409_gate_into_a_denial():
    err = SdkError(DENIAL_409["error"]["message"], 409, DENIAL_409, "req_409")
    hg, _ = make({"execute_decision": err})
    out = hg.execute_decision(DECISION_ID, webhook_url=WEBHOOK)
    assert isinstance(out, Denial)
    assert out.gate == "confidence"
    assert out.code == "execution_blocked_confidence"
    assert out.override_hint.startswith("Pass override_safety=true")
    assert out.status_code == 409
    assert out.request_id == "req_409"


def test_execute_decision_turns_a_404_and_an_empty_id_into_existence_denials():
    hg, made = make({"execute_decision": SdkError("Decision not found", 404, {}, "req_404")})
    out = hg.execute_decision(DECISION_ID, webhook_url=WEBHOOK)
    assert isinstance(out, Denial)
    assert (out.gate, out.code, out.status_code) == ("existence", "decision_not_found", 404)
    assert DECISION_ID in out.message
    out = hg.execute_decision("   ", webhook_url=WEBHOOK)
    assert isinstance(out, Denial) and out.gate == "existence"
    assert len(made[0].calls) == 1
    with pytest.raises(ValueError, match="webhook_url"):
        hg.execute_decision(DECISION_ID, webhook_url="  ")


def test_execute_decision_still_raises_for_other_failures():
    hg, _ = make({"execute_decision": SdkError("bad", 422, {}, "req")})
    with pytest.raises(EngineError):
        hg.execute_decision(DECISION_ID, webhook_url=WEBHOOK)


def test_get_decision_reads_execution_status_and_rejects_empty_ids():
    hg, _ = make()
    dec = hg.get_decision(DECISION_ID)
    assert dec.execution_status == "delivered"
    with pytest.raises(ValueError):
        hg.get_decision(" ")


# --- helpers ------------------------------------------------------------------------


def test_scrub_redacts_key_shapes_bearer_tokens_and_the_exact_key():
    text = f"key {KEY} and Bearer abc.def-ghi_123 and de_live_ABCDEFGH and {ODD_KEY}"
    out = hosted_api.scrub(text, exact=(ODD_KEY, ""))
    assert KEY not in out and ODD_KEY not in out
    assert "abc.def-ghi_123" not in out and "de_live_ABCDEFGH" not in out
    assert out.count("[redacted]") == 4
    assert hosted_api.scrub("nothing secret") == "nothing secret"


def test_exact_key_scrub_covers_keys_the_pattern_would_miss():
    body = {"error": {"code": "x", "message": f"bad key {ODD_KEY}"}}
    hg, _ = make({"get_decision": SdkError(f"bad key {ODD_KEY}", 400, body, "r")}, key=ODD_KEY)
    with pytest.raises(EngineError) as info:
        hg.get_decision(DECISION_ID)
    assert ODD_KEY not in str(info.value)


def test_gate_from_error_code():
    assert hosted_api.gate_from_error_code("execution_blocked_idempotency") == "idempotency"
    assert hosted_api.gate_from_error_code("execution_blocked_confidence") == "confidence"
    assert hosted_api.gate_from_error_code("execution_blocked_risk_floor") == "risk_floor"
    assert hosted_api.gate_from_error_code("decision_not_found") == "existence"
    assert hosted_api.gate_from_error_code("validation_error") is None


def test_to_plain_handles_models_dataclasses_and_collections():
    @dataclasses.dataclass
    class Row:
        a: int
        b: tuple[int, ...]

    class Obj:
        def __init__(self) -> None:
            self.x = 1
            self._hidden = 2

    plain = hosted_api.to_plain(
        {"m": Model({"k": [Row(1, (2, 3))]}), "o": Obj(), "s": frozenset({1}), "n": None}
    )
    assert plain == {"m": {"k": [{"a": 1, "b": [2, 3]}]}, "o": {"x": 1}, "s": [1], "n": None}
    assert hosted_api.to_plain(1 + 2j) == "(1+2j)"  # no __dict__, no dump: str()


def test_malformed_engine_responses_are_engine_errors():
    with pytest.raises(EngineError, match="incomplete receipt"):
        hosted_api.to_receipt({"decision_id": DECISION_ID})
    with pytest.raises(EngineError, match="without an id"):
        hosted_api.to_decision({"chosen_action": "x"})
    with pytest.raises(EngineError, match="no recommendation object"):
        hosted_api.to_recommendation([1, 2])
    denial = hosted_api.to_denial({"code": "execution_blocked_risk_floor"})
    assert (denial.gate, denial.override_hint) == ("risk_floor", None)
    assert "risk_floor" in denial.message


# --- webhook receiver ------------------------------------------------------------------


def test_webhook_receiver_path_url_and_nonce_match():
    path, rx = hosted_api.webhook_receiver(lambda: "n0nce-A", clock=lambda: 1_790_000_000.0)
    assert path == "/hook/n0nce-A" == rx.path
    assert (
        rx.url("https://thyn-ai-algenta.hf.space/")
        == "https://thyn-ai-algenta.hf.space/hook/n0nce-A"
    )
    with pytest.raises(ValueError):
        rx.url("http://plain.example")
    body = json.dumps(WEBHOOK_POST).encode()
    assert rx.verify("other", body, {}) is None
    event = rx.verify("n0nce-A", body, {"content-type": "application/json"})
    assert event is not None
    assert event.decision_id == DECISION_ID
    assert event.event == hosted_api.WEBHOOK_EVENT
    assert event.signed is False
    assert event.integrity["policy_snapshot_id"] == "policy-snap-7"
    assert event.received_utc.endswith("UTC")
    assert rx.events(DECISION_ID) == [event]
    assert rx.events("nope") == []
    assert rx.signed is False


def test_webhook_receiver_rejects_bad_bodies_and_bounds_the_log():
    _, rx = hosted_api.webhook_receiver(lambda: "n", keep=2)
    assert rx.verify("n", b"not json", {}) is None
    assert rx.verify("n", b"[1,2]", {}) is None
    assert rx.verify("n", b"\xff\xfe", {}) is None
    for i in range(3):
        assert rx.verify("n", json.dumps({"decision_id": str(i)}).encode(), {}) is not None
    assert [e.decision_id for e in rx.events()] == ["1", "2"]


def test_webhook_receiver_with_a_secret_requires_a_valid_hmac():
    secret = b"shared-signing-secret"
    _, rx = hosted_api.webhook_receiver(lambda: "n", secret=secret)
    body = json.dumps(WEBHOOK_POST).encode()
    assert rx.signed
    assert rx.verify("n", body, {}) is None
    assert rx.verify("n", body, {"X-Algenta-Signature": "sha256=" + "0" * 64}) is None
    good = rx.signature(body)
    assert good.startswith("sha256=") and len(good) == 71
    assert rx.verify("n", body + b" ", {"X-Algenta-Signature": good}) is None
    event = rx.verify("n", body, {"X-Algenta-Signature": good})
    assert event is not None and event.signed is True
    _, unsigned = hosted_api.webhook_receiver(lambda: "n")
    with pytest.raises(ValueError):
        unsigned.signature(body)


def test_webhook_receiver_validates_its_inputs():
    with pytest.raises(ValueError):
        hosted_api.WebhookReceiver("")
    with pytest.raises(ValueError):
        hosted_api.WebhookReceiver("a/b")
    with pytest.raises(ValueError):
        hosted_api.WebhookReceiver("a", keep=0)
    path, _ = hosted_api.webhook_receiver()
    assert re.fullmatch(r"/hook/[A-Za-z0-9_\-]{20,}", path)


# --- the card ------------------------------------------------------------------------


def test_status_card_is_empty_when_ready_and_a_clean_unavailable_card_otherwise():
    hg, _ = make()
    assert hosted_api.render_status_card(hg.status()) == ""
    hg, _ = make(key="")
    html = hosted_api.render_status_card(hg.status(now=1_790_000_000.0))
    assert hosted_api.NOT_CONFIGURED_CODE in html
    assert hosted_api.NOT_CONFIGURED_REASON in html
    assert 'data-kind="unavailable"' in html
    _assert_clean_copy(html)
    hg, _ = make({"me": SdkRateLimitError(retry_after=9)})
    html = hosted_api.render_status_card(hg.status())
    assert "HOSTED-RATE-LIMITED" in html
    _assert_clean_copy(html)
    for text in (hosted_api.NOT_CONFIGURED_REASON, hosted_api.REJECTED_KEY_REASON):
        _assert_clean_copy(text)


# --- the real client, constructed offline ------------------------------------------------


def test_default_factory_builds_the_real_client_with_every_allow_listed_method():
    pytest.importorskip("algenta")
    client = hosted_api.default_client_factory(KEY, hosted_api.DEFAULT_BASE_URL)
    assert type(client).__name__ == "AlgentaClient"
    assert client.api_key == KEY
    assert client.base_url.startswith("https://api.algenta.ai")
    for method in hosted_api.DEFAULT_ALLOW:
        assert callable(getattr(client, method)), method
