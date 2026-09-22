"""Deterministic tests for the governed-agent backend.

The model-dependent tests are skipped unless HF_TOKEN/HF_API_KEY is set (the
live backend streams from HF Inference Providers); every other test runs
without network or model. Run: pytest tests/ -q
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import corpus
import pytest
import space_core as core

# --------------------------------------------------------------------------
# profile filtering
# --------------------------------------------------------------------------


def test_profile_tools_filtering():
    assert "execute_action" not in core.profile_tools("observe")
    assert "execute_action" not in core.profile_tools("govern")
    assert "execute_action" in core.profile_tools("execute")
    assert "execute_action" in core.profile_tools("full")
    for profile in ("observe", "govern", "execute", "full"):
        assert "recommend" in core.profile_tools(profile)
        assert "search_corpus" in core.profile_tools(profile)


# --------------------------------------------------------------------------
# tool-choice validation (parse + schema)
# --------------------------------------------------------------------------


def test_validate_choice_ok():
    choice, err = core._validate_choice(
        '{"tool": "search_corpus", "arguments": {"query": "zinc"}}',
        core.profile_tools("observe"),
    )
    assert err is None
    assert choice["tool"] == "search_corpus"
    assert choice["arguments"] == {"query": "zinc"}


def test_validate_choice_rejects_unavailable_tool():
    choice, err = core._validate_choice(
        '{"tool": "execute_action", "arguments": {"action": "x", "confidence": 0.9, "risk_p5": 0.0}}',
        core.profile_tools("observe"),
    )
    assert choice is None
    assert "not available" in err


def test_validate_choice_rejects_bad_args():
    choice, err = core._validate_choice(
        '{"tool": "search_corpus", "arguments": {"query": 42}}',
        core.profile_tools("observe"),
    )
    assert choice is None
    assert "validation" in err


def test_validate_choice_rejects_non_json():
    choice, err = core._validate_choice("no json here", core.profile_tools("observe"))
    assert choice is None
    assert err


def test_validate_choice_final_answer_requires_text():
    choice, err = core._validate_choice(
        '{"tool": "final_answer", "arguments": {}, "answer": ""}',
        core.profile_tools("observe"),
    )
    assert choice is None
    assert "answer" in err


# --- owner transcript 2026-09-21: the model omits `arguments` inconsistently
# --- for final_answer; missing/null coerces to {} (flagged), wrong type rejects


def test_validate_choice_final_answer_without_arguments_key():
    # the exact shape from the owner's transcript ("what is the weather today")
    choice, err = core._validate_choice(
        '{"tool": "final_answer", "answer": "I cannot provide weather information."}',
        core.profile_tools("observe"),
    )
    assert err is None
    assert choice["tool"] == "final_answer"
    assert choice["arguments"] == {}
    assert choice["arguments_defaulted"] is True


def test_validate_choice_final_answer_null_arguments():
    choice, err = core._validate_choice(
        '{"tool": "final_answer", "arguments": null, "answer": "hello there"}',
        core.profile_tools("observe"),
    )
    assert err is None
    assert choice["arguments"] == {}
    assert choice["arguments_defaulted"] is True


def test_validate_choice_final_answer_with_arguments_not_defaulted():
    choice, err = core._validate_choice(
        '{"tool": "final_answer", "arguments": {}, "answer": "hello there"}',
        core.profile_tools("observe"),
    )
    assert err is None
    assert choice["arguments"] == {}
    assert choice["arguments_defaulted"] is False


def test_validate_choice_rejects_wrong_type_arguments():
    choice, err = core._validate_choice(
        '{"tool": "search_corpus", "arguments": 42}',
        core.profile_tools("observe"),
    )
    assert choice is None
    assert "arguments must be a JSON object" in err


def test_validate_choice_rejects_list_arguments():
    choice, err = core._validate_choice(
        '{"tool": "search_corpus", "arguments": ["zinc"]}',
        core.profile_tools("observe"),
    )
    assert choice is None
    assert "arguments must be a JSON object" in err


# --------------------------------------------------------------------------
# governance: gates, receipts, signatures
# --------------------------------------------------------------------------


def test_profile_interception_logs_nothing():
    state = core.initial_state()
    result, _ = core._tool_execute_action(
        {"action": "refund_order_123", "confidence": 0.97, "risk_p5": -0.02},
        "observe",
        False,
        False,
        state,
    )
    assert result["log_decision"] is None
    assert result["execute_action"]["error"]["code"] == "tool_not_in_profile"
    assert result["execute_action"]["error"]["gate"] == "profile"
    assert state["decisions"] == {}
    assert state["audit"][-1]["outcome"] == "intercepted"


def test_confidence_gate_denies():
    state = core.initial_state()
    result, _ = core._tool_execute_action(
        {"action": "refund_order_123", "confidence": 0.45, "risk_p5": -0.02},
        "execute",
        False,
        False,
        state,
    )
    err = result["execute_action"]["error"]
    assert err["code"] == "execution_blocked_confidence"
    assert err["gate"] == "confidence"
    assert result["log_decision"]["outcome"] == "logged"
    assert state["audit"][-1]["outcome"] == "denied"


def test_risk_floor_gate_denies():
    state = core.initial_state()
    result, _ = core._tool_execute_action(
        {"action": "delete_all_users", "confidence": 0.99, "risk_p5": -0.9},
        "execute",
        False,
        False,
        state,
    )
    err = result["execute_action"]["error"]
    assert err["code"] == "execution_blocked_risk_floor"
    assert err["gate"] == "risk_floor"


def test_override_safety_bypasses_confidence():
    state = core.initial_state()
    result, _ = core._tool_execute_action(
        {"action": "refund_order_123", "confidence": 0.45, "risk_p5": -0.02},
        "execute",
        False,
        True,
        state,
    )
    receipt = result["execute_action"]
    assert receipt["execution_status"] == "delivered"
    assert receipt["safety_overridden"] is True


def test_receipt_signature_verifies():
    state = core.initial_state()
    result, _ = core._tool_execute_action(
        {"action": "refund_order_123", "confidence": 0.97, "risk_p5": -0.02},
        "execute",
        False,
        False,
        state,
    )
    receipt = result["execute_action"]
    assert receipt["execution_status"] == "delivered"
    assert receipt["response_code"] == 200
    for field in ("policy_snapshot_id", "schema_snapshot_id", "manifest_version", "signature"):
        assert field in receipt
    body = {k: v for k, v in receipt.items() if k != "signature"}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(bytes.fromhex(state["hmac_key"]), payload, hashlib.sha256).hexdigest()
    assert receipt["signature"] == expected
    assert state["audit"][-1]["outcome"] == "delivered"


def test_idempotency_replay_denied_then_force():
    state = core.initial_state()
    args = {"action": "refund_order_123", "confidence": 0.97, "risk_p5": -0.02}
    first, _ = core._tool_execute_action(args, "execute", False, False, state)
    assert first["execute_action"]["execution_status"] == "delivered"
    second, _ = core._tool_execute_action(args, "execute", False, False, state)
    assert second["execute_action"]["error"]["gate"] == "idempotency"
    third, _ = core._tool_execute_action(args, "execute", True, False, state)
    assert third["execute_action"]["execution_status"] == "delivered"


def test_recommend_writes_no_decision():
    state = core.initial_state()
    result, _ = core._tool_recommend(
        {"action": "refund_order_123", "confidence": 0.97, "risk_p5": -0.02}, state
    )
    assert result["outcome"] == "recommended"
    assert all(g["would_pass"] for g in result["gate_preview"])
    assert state["decisions"] == {}
    assert state["audit"][-1]["kind"] == "recommend"


def test_recommend_preview_flags_risk_floor():
    state = core.initial_state()
    result, _ = core._tool_recommend(
        {"action": "delete_all_users", "confidence": 0.99, "risk_p5": -0.9}, state
    )
    failed = [g["gate"] for g in result["gate_preview"] if not g["would_pass"]]
    assert failed == ["risk_floor"]


# --------------------------------------------------------------------------
# tools (kernel-backed; backend-agnostic — native or labeled fallback)
# --------------------------------------------------------------------------


def test_search_corpus_real_ranking():
    result, meta = core._tool_search_corpus({"query": "Kármán vortex street vortex shedding"})
    assert result["results"]
    assert "Kármán" in result["results"][0]["title"]
    assert result["results"][0]["url"].startswith("https://en.wikipedia.org/")
    scores = [r["bm25_score"] for r in result["results"]]
    assert scores == sorted(scores, reverse=True)
    assert "backend" in meta and meta["latency_ms"] >= 0


def test_corpus_is_real_and_licensed():
    """The vendored corpus: real Wikipedia passages with attribution."""
    payload = corpus.load_corpus()
    docs = payload["docs"]
    assert len(docs) >= 3000
    assert "Wikipedia" in payload["provenance"]
    assert "CC BY-SA" in payload["license"]
    for d in docs[:50]:
        assert d["id"].startswith("W") and d["title"] and d["url"] and len(d["text"]) >= 500


def test_corpus_index_builds_and_is_measured():
    corpus.mojo_index()
    stats = corpus.index_stats()
    assert stats is not None
    assert stats["docs"] == len(corpus.docs())
    assert stats["build_ms"] > 0


def test_score_answer_matches_oracle():
    result, _ = core._tool_score_answer(
        {
            "hypothesis": "The new battery charges to eighty percent in twelve minutes.",
            "reference": "The new battery charges to 80% in 12 minutes.",
        }
    )
    assert result["bleu"]["score"] > 0
    assert result["chrf"]["score"] > 0
    assert result["oracle_crosscheck"]["abs_delta_bleu"] <= 1e-9
    assert result["oracle_crosscheck"]["abs_delta_chrf"] <= 1e-9


def test_simulate_mm1_deterministic_and_consistent():
    pytest.importorskip("algenta.mojo_runtime")
    args = {"scenario": "mm1_queue", "arrival_rate": 0.9, "service_rate": 1.0, "n_customers": 2000}
    r1, meta = core._tool_simulate(args)
    r2, _ = core._tool_simulate(args)
    assert r1["simulated"] == r2["simulated"]  # deterministic kernel
    assert r1["queue_stable"] is True
    theory = r1["mm1_closed_form"]
    assert theory["server_utilization"] == 0.9
    assert theory["avg_system_time"] == 10.0
    assert r1["identity_check"]["residual"] < 0.05
    sim = r1["simulated"]
    assert 0.0 < sim["server_utilization"] < 1.0
    assert 0.0 < sim["avg_queue_wait"] < sim["avg_system_time"]


def test_simulate_unstable_queue_flagged():
    pytest.importorskip("algenta.mojo_runtime")
    args = {"scenario": "mm1_queue", "arrival_rate": 2.0, "service_rate": 1.0, "n_customers": 1000}
    result, _ = core._tool_simulate(args)
    assert result["queue_stable"] is False
    assert result["mm1_closed_form"] is None


# --------------------------------------------------------------------------
# boot status + provider-path rendering (no network needed)
# --------------------------------------------------------------------------


def test_boot_status_shape():
    bs = core.boot_status()
    assert isinstance(bs["ready"], bool)
    assert isinstance(bs["stages"], list) and bs["stages"]
    for stage in bs["stages"]:
        assert stage["state"] in ("pending", "running", "done", "error")
        assert stage["id"] in ("kernels", "inference")


def test_render_trace_discloses_provider():
    turn = core.agent_turn("", "observe", False, False, core.initial_state())
    assert turn["held"] and turn["error"] == "empty question"
    trace = core.render_trace(turn)
    assert "HF Inference Providers" in trace
    assert "TURN HELD" in trace


def test_agent_turn_events_terminal_done():
    events = list(core.agent_turn_events("", "observe", False, False, None))
    assert events[-1]["type"] == "done"
    assert all(
        e["type"] in ("step_start", "token", "step_end", "tool_start", "tool_end", "done")
        for e in events
    )


# --------------------------------------------------------------------------
# empty / whitespace questions — held at core, nudged (never a card) in the UI
# --------------------------------------------------------------------------


def test_empty_question_held_at_core():
    turn = core.agent_turn("", "observe", False, False, core.initial_state())
    assert turn["held"] and turn["error"] == "empty question"


def test_whitespace_question_held_at_core():
    turn = core.agent_turn("  \n\t ", "observe", False, False, core.initial_state())
    assert turn["held"] and turn["error"] == "empty question"


def test_ui_empty_question_nudge_no_card_no_model_call():
    """Owner bug 1: empty submit rendered a full governed-turn card ending in
    'TURN HELD'. The handler must short-circuit to a gentle nudge instead."""
    import app

    state = core.initial_state()
    frames = list(app._run_turn_stream("", "observe", False, False, state, []))
    assert len(frames) == 1  # single short-circuit frame, no streaming
    final = frames[-1]
    chat = final[-1]
    assert len(chat) == 1  # one gentle assistant nudge, no user bubble
    msg = chat[0]
    role = msg["role"] if isinstance(msg, dict) else msg.role
    content = msg["content"] if isinstance(msg, dict) else msg.content
    metadata = (msg.get("metadata") if isinstance(msg, dict) else msg.metadata) or {}
    assert role == "assistant"
    assert "preset" in content
    assert "governed turn" not in str(metadata.get("title", ""))
    assert final[0] == ""  # no trace was rendered
    assert state["audit"] == []  # nothing logged, no model call


def test_ui_whitespace_question_nudge_no_card():
    import app

    state = core.initial_state()
    frames = list(app._run_turn_stream("  \n\t ", "observe", False, False, state, []))
    chat = frames[-1][-1]
    assert len(chat) == 1
    msg = chat[0]
    role = msg["role"] if isinstance(msg, dict) else msg.role
    content = msg["content"] if isinstance(msg, dict) else msg.content
    assert role == "assistant"
    assert "preset" in content
    assert state["audit"] == []


# --------------------------------------------------------------------------
# retry path — malformed output fails after exactly one retry (transport
# stubbed ONLY here to drive retry-exhaustion deterministically; the product
# never stubs the model)
# --------------------------------------------------------------------------


def test_malformed_json_fails_after_retry(monkeypatch):
    seen: list[list[str]] = []

    def fake_stream(messages, *, json_mode, max_tokens):
        seen.append([m["content"] for m in messages])
        yield {"token": "not json at all"}
        yield {
            "stats": {
                "text": "not json at all",
                "seconds": 0.1,
                "ttft_seconds": 0.05,
                "prompt_tokens": 10,
                "completion_tokens": 3,
                "tok_per_s": 30.0,
            }
        }

    monkeypatch.setattr(core, "_chat_stream", fake_stream)
    events = list(
        core.agent_turn_events("give me nonsense", "observe", False, False, core.initial_state())
    )
    turn = events[-1]["turn"]
    assert turn["held"]
    assert "tool selection failed after retry" in turn["error"]
    selections = [s for s in turn["steps"] if s.get("step", "").startswith("tool selection")]
    assert len(selections) == 2  # both attempts shown
    assert all(s["valid"] is False for s in selections)
    assert all("validation_error" in s for s in selections)
    # the retry feedback spells out the exact contract, arguments key included
    assert len(seen) == 2
    retry_feedback = seen[1][-1]
    assert "VALIDATION ERROR" in retry_feedback
    assert 'use "arguments": {} when no arguments are needed' in retry_feedback


def test_render_trace_discloses_defaulted_arguments():
    turn = {
        "question": "q",
        "profile": "observe",
        "steps": [
            {
                "step": "tool selection attempt 1",
                "kind": "model_call",
                "seconds": 1.0,
                "ttft_seconds": 0.5,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "tok_per_s": 10.0,
                "raw_output": '{"tool": "final_answer", "answer": "x"}',
                "valid": True,
                "arguments_defaulted": True,
            }
        ],
        "held": False,
    }
    trace = core.render_trace(turn)
    assert "arguments: {} (defaulted)" in trace


# --------------------------------------------------------------------------
# argument-grounding guardrail (no model needed)
# --------------------------------------------------------------------------


def test_extract_numbers_normalization():
    n = core._extract_numbers("cut cost by 10k per month, increase sales by 5%, burn is $15k")
    assert 10000.0 in n and 15000.0 in n
    assert 5.0 in n and 0.05 in n  # % contributes both interpretations
    assert -0.02 in core._extract_numbers("worst case risk_p5 -0.02")
    assert 123.0 in core._extract_numbers("order #123")
    assert 19.99 in core._extract_numbers("refund of $19.99")
    assert 10000.0 in core._extract_numbers("10,000 customers")
    assert 0.9 in core._extract_numbers("arrival rate 0.9")


def test_grounding_check_flags_fabricated_arguments():
    # the owner's exact transcript: 10k / 5% / 15k in the message
    q = (
        "can you simulate revenue change if we cut cost by 10k per month, and increase "
        "sales by 5%? our current burn rate is 15k per month"
    )
    bad, defaulted = core._grounding_check(
        "simulate",
        {"scenario": "mm1_queue", "arrival_rate": 5, "service_rate": 10, "n_customers": 1000},
        q,
    )
    assert "service_rate=10" in bad  # 10k normalizes to 10000, not 10
    assert "n_customers=1000" in bad  # not in the message, not the default
    assert "arrival_rate=5" not in bad  # 5% normalizes to 5 (either interpretation)
    assert defaulted == []


def test_grounding_check_passes_grounded_arguments():
    bad, defaulted = core._grounding_check(
        "simulate",
        {"scenario": "mm1_queue", "arrival_rate": 0.9, "service_rate": 1.0},
        "Simulate an M/M/1 queue with arrival rate 0.9, service rate 1.0",
    )
    assert bad == [] and defaulted == []


def test_grounding_check_discloses_explicit_default():
    bad, defaulted = core._grounding_check(
        "simulate",
        {"scenario": "mm1_queue", "arrival_rate": 5, "service_rate": 10, "n_customers": 5000},
        "simulate a queue with arrival rate 5 and service rate 10",
    )
    assert bad == []
    assert defaulted == ["n_customers: 5000 (documented default)"]


def test_apply_defaults_fills_and_discloses():
    args, notes = core._apply_defaults(
        "simulate", {"scenario": "mm1_queue", "arrival_rate": 1.0, "service_rate": 2.0}
    )
    assert args["n_customers"] == 5000
    assert notes == ["n_customers: 5000 (documented default)"]
    args2, notes2 = core._apply_defaults(
        "simulate",
        {"scenario": "mm1_queue", "arrival_rate": 1.0, "service_rate": 2.0, "n_customers": 800},
    )
    assert args2["n_customers"] == 800 and notes2 == []


def _stub_stream_factory(responses, calls):
    def fake_stream(messages, *, json_mode, max_tokens):
        calls.append([m["content"] for m in messages])
        text = responses[min(len(calls) - 1, len(responses) - 1)]
        yield {"token": text}
        yield {
            "stats": {
                "text": text,
                "seconds": 0.1,
                "ttft_seconds": 0.05,
                "prompt_tokens": 10,
                "completion_tokens": 3,
                "tok_per_s": 30.0,
            }
        }

    return fake_stream


def test_retry_then_abstain_on_fabricated_arguments(monkeypatch):
    """Transport stubbed ONLY to drive the guardrail flow deterministically;
    the product never stubs the model. The tool must NEVER run."""
    calls: list[list[str]] = []
    monkeypatch.setattr(
        core,
        "_chat_stream",
        _stub_stream_factory(
            [
                '{"tool": "simulate", "arguments": {"scenario": "mm1_queue", "arrival_rate": 5, "service_rate": 10, "n_customers": 1000}}',
                '{"tool": "simulate", "arguments": {"scenario": "mm1_queue", "arrival_rate": 5, "service_rate": 10, "n_customers": 1000}}',
                "I can't run a revenue what-if here: the only simulator is an M/M/1 queue, and the rates would have to be invented.",
            ],
            calls,
        ),
    )
    executed: list = []
    monkeypatch.setattr(core, "execute_tool", lambda *a, **k: executed.append(a) or ({}, {}))
    q = (
        "can you simulate revenue change if we cut cost by 10k per month, and increase "
        "sales by 5%? our current burn rate is 15k per month"
    )
    events = list(core.agent_turn_events(q, "observe", False, False, core.initial_state()))
    turn = events[-1]["turn"]
    assert turn["abstained"] is True
    assert turn["held"] is False
    assert turn["tool_call"] is None and turn["tool_result"] is None
    assert executed == []  # the tool NEVER ran
    assert turn["answer"].strip()  # composed honest decline
    assert len(calls) == 3  # selection x2 + abstain composition
    feedback = calls[1][-1]
    assert "GROUNDING ERROR" in feedback
    assert "service_rate=10" in feedback and "n_customers=1000" in feedback
    trace = core.render_trace(turn)
    assert "guardrail fired" in trace
    assert "ABSTAINED" in trace
    assert "service_rate=10" in trace


def test_retry_then_final_answer_after_grounding_feedback(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(
        core,
        "_chat_stream",
        _stub_stream_factory(
            [
                '{"tool": "simulate", "arguments": {"scenario": "mm1_queue", "arrival_rate": 5, "service_rate": 10, "n_customers": 1000}}',
                '{"tool": "final_answer", "arguments": {}, "answer": "I cannot simulate revenue changes here — I can simulate an M/M/1 queue if you provide arrival and service rates."}',
            ],
            calls,
        ),
    )
    executed: list = []
    monkeypatch.setattr(core, "execute_tool", lambda *a, **k: executed.append(a) or ({}, {}))
    q = "can you simulate revenue change if we cut cost by 10k per month? burn rate is 15k per month"
    turn = core.agent_turn(q, "observe", False, False, core.initial_state())
    assert turn["held"] is False and turn["abstained"] is False
    assert turn["tool_call"]["tool"] == "final_answer"
    assert turn["answer"].strip()
    assert executed == []
    assert len(calls) == 2  # no abstain composition — the model abstained itself


def test_grounded_simulate_runs_with_disclosed_default(monkeypatch):
    pytest.importorskip("algenta.mojo_runtime")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        core,
        "_chat_stream",
        _stub_stream_factory(
            [
                '{"tool": "simulate", "arguments": {"scenario": "mm1_queue", "arrival_rate": 5, "service_rate": 10}}',
                "The queue is stable: utilization 0.5, avg system time 0.2.",
            ],
            calls,
        ),
    )
    turn = core.agent_turn(
        "simulate a queue with arrival rate 5 and service rate 10",
        "observe",
        False,
        False,
        core.initial_state(),
    )
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "simulate"
    assert turn["tool_result"]["inputs"]["n_customers"] == 5000
    assert turn["tool_result"]["defaults_applied"] == ["n_customers: 5000 (documented default)"]
    assert turn["tool_result"]["queue_stable"] is True
    trace = core.render_trace(turn)
    assert "defaults applied" in trace and "5000" in trace


# --------------------------------------------------------------------------
# end-to-end agent turn with the REAL model (skipped without inference creds)
# --------------------------------------------------------------------------


def _inference_available() -> bool:
    return bool(os.environ.get("HF_TOKEN") or os.environ.get("HF_API_KEY"))


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_retrieval_end_to_end():
    turn = core.agent_turn(
        "What is a Kármán vortex street? Cite the sources.",
        "observe",
        False,
        False,
        core.initial_state(),
    )
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "search_corpus"
    assert turn["tool_result"]["results"]
    assert any("Kármán" in r["title"] for r in turn["tool_result"]["results"])
    assert turn["answer"].strip()
    assert not turn["answer"].lstrip().startswith("{")  # prose, not a JSON echo
    toks = [s for s in turn["steps"] if s.get("kind") == "model_call"]
    assert toks and all(s["tok_per_s"] > 0 for s in toks)
    assert all(s["completion_tokens"] > 0 for s in toks)  # provider usage counters


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_events_stream_real_tokens():
    events = list(
        core.agent_turn_events(
            "Score this candidate answer against the reference. Candidate: 'The new battery "
            "charges to eighty percent in twelve minutes.' Reference: 'The new battery charges "
            "to 80% in 12 minutes.'",
            "observe",
            False,
            False,
            core.initial_state(),
        )
    )
    assert events[-1]["type"] == "done"
    turn = events[-1]["turn"]
    assert not turn["held"], turn.get("error")
    token_events = [e for e in events if e["type"] == "token"]
    assert token_events, "expected streamed token events"
    # every token event carries its step and non-empty text
    assert all(e["step"] and e["text"] for e in token_events)
    # streamed composition tokens reassemble into the final answer
    composed = "".join(e["text"] for e in token_events if e["step"] == "answer composition")
    assert composed.strip() == turn["answer"]
    # step ordering: selection before tool execution before composition
    kinds = [e["type"] for e in events]
    assert kinds.index("step_start") < kinds.index("tool_start") < len(kinds) - 1


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_hi_final_answer_end_to_end():
    """Owner transcript: 'hi' → final_answer WITH arguments — must compose."""
    turn = core.agent_turn("hi", "observe", False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "final_answer"
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_weather_out_of_scope_final_answer():
    """Owner transcript: 'what is the weather today' → final_answer, possibly
    WITHOUT the arguments key — must compose, never a held turn."""
    turn = core.agent_turn(
        "what is the weather today", "observe", False, False, core.initial_state()
    )
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "final_answer"
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_revenue_question_never_fabricates():
    """Owner transcript 2026-09-21: the revenue what-if. Must NOT run a tool on
    fabricated arguments — abstain (guardrail) or a direct final_answer decline."""
    q = (
        "can you simulate revenue change if we cut cost by 10k per month, and increase "
        "sales by 5%? our current burn rate is 15k per month"
    )
    turn = core.agent_turn(q, "observe", False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    if turn["tool_call"] and turn["tool_call"]["tool"] != "final_answer":
        # a real tool may only have run with fully grounded arguments
        bad, _ = core._grounding_check(turn["tool_call"]["tool"], turn["tool_call"]["arguments"], q)
        assert bad == [], f"un-grounded tool call executed: {turn['tool_call']}"
        return
    assert turn["abstained"] or turn["tool_call"]["tool"] == "final_answer"
    assert turn["answer"].strip()
    if turn["abstained"]:
        assert "ABSTAINED" in core.render_trace(turn)


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_queue_without_rates_never_invents_them():
    """'simulate a queue' — no rates given: the agent must ask for them (or use
    only documented defaults, disclosed) — never invent 5/10."""
    turn = core.agent_turn("simulate a queue", "observe", False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    if turn["abstained"]:
        # the guardrail caught invented rates and the turn declined honestly
        assert "ABSTAINED" in core.render_trace(turn)
    elif turn["tool_call"] and turn["tool_call"]["tool"] == "simulate":
        args = turn["tool_call"]["arguments"]
        bad, _ = core._grounding_check("simulate", args, "simulate a queue")
        assert bad == [], f"invented rates executed: {args}"
    else:
        assert turn["tool_call"]["tool"] == "final_answer"
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_agent_turn_grounded_queue_runs_for_real():
    turn = core.agent_turn(
        "simulate a queue with arrival rate 5 and service rate 10",
        "observe",
        False,
        False,
        core.initial_state(),
    )
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "simulate"
    assert float(turn["tool_call"]["arguments"]["arrival_rate"]) == 5
    assert float(turn["tool_call"]["arguments"]["service_rate"]) == 10
    assert turn["tool_result"]["queue_stable"] is True
    assert turn["tool_result"]["simulated"]["server_utilization"] > 0
    assert turn["answer"].strip()


# --------------------------------------------------------------------------
# curated presets — each one's expected tool path (model-gated, real turns)
# --------------------------------------------------------------------------


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_preset_transformer_retrieval():
    import app

    _, profile, question = app.PRESET_QUESTIONS[1]
    turn = core.agent_turn(question, profile, False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "search_corpus"
    assert any(
        "Transformer" in r["title"] or "Attention" in r["title"]
        for r in turn["tool_result"]["results"]
    )
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_preset_support_queue_simulation():
    import app

    _, profile, question = app.PRESET_QUESTIONS[2]
    turn = core.agent_turn(question, profile, False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "simulate"
    args = turn["tool_call"]["arguments"]
    assert float(args["arrival_rate"]) == 5 and float(args["service_rate"]) == 10
    assert turn["tool_result"]["queue_stable"] is True
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_preset_score_summary():
    import app

    _, profile, question = app.PRESET_QUESTIONS[3]
    turn = core.agent_turn(question, profile, False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "score_answer"
    assert turn["tool_result"]["bleu"]["score"] > 0 and turn["tool_result"]["chrf"]["score"] > 0
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_preset_approved_refund():
    import app

    _, profile, question = app.PRESET_QUESTIONS[4]
    turn = core.agent_turn(question, profile, False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "execute_action"
    assert turn["governance"]["execute_action"]["execution_status"] == "delivered"
    assert turn["answer"].strip()


@pytest.mark.skipif(not _inference_available(), reason="HF_TOKEN (Inference Providers) not set")
def test_preset_risk_floor_denial():
    import app

    _, profile, question = app.PRESET_QUESTIONS[5]
    turn = core.agent_turn(question, profile, False, False, core.initial_state())
    assert not turn["held"], turn.get("error")
    assert turn["tool_call"]["tool"] == "execute_action"
    err = turn["governance"]["execute_action"]["error"]
    assert err["gate"] == "risk_floor" and err["code"] == "execution_blocked_risk_floor"
    assert turn["answer"].strip()
