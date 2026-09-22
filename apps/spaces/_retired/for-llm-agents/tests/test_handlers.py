"""Local handler tests for the Algenta for LLM Agents Space.

Covers every tab without touching the network:

* corpus generation determinism (regeneration matches the vendored file)
* RAG duel: identical top-10 ranking across lanes, latency fields, held paths
* scorer: BLEU/chrF correctness vs the reference sacrebleu 2.5.1, race gate
* governed duel: every gate (profile/confidence/risk_floor/idempotency),
  receipt shape, operator override, audit log
* MCP playground: real registry shape, JSON-RPC frames, call runner + receipt
* app assembly: builds, five tabs, named API endpoints, no DeepLinkButton

Run: python -m pytest tests/test_handlers.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SPACE_ROOT))

from lab import corpus, examples, governed, mcp_play, rag, scorer  # noqa: E402

NATIVE = corpus.indexes()["mojo_backend"].get("native_available", False)


# ---------------------------------------------------------------------------
# Corpus determinism
# ---------------------------------------------------------------------------


def test_corpus_regeneration_matches_vendored_file():
    out = subprocess.run(
        [sys.executable, str(SPACE_ROOT / "scripts" / "gen_corpus.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr


def test_corpus_shape():
    payload = corpus.load_corpus()
    assert payload["seed"] == 20260920
    assert payload["n_docs"] == 320 == len(payload["docs"])
    assert len(payload["queries"]) == 20
    ids = [d["id"] for d in payload["docs"]]
    assert len(set(ids)) == 320
    assert "synthetic" in payload["provenance"].lower()
    assert len(corpus.sample_queries()) == 20


# ---------------------------------------------------------------------------
# Tab 1 — RAG retrieval duel
# ---------------------------------------------------------------------------


def test_rag_duel_identical_ranking_all_sample_queries():
    for q in corpus.sample_queries():
        left, right, status = rag.rag_duel(q)
        assert len(left) == 10 and len(right) == 10, q
        assert list(left["doc_id"]) == list(right["doc_id"]), q
        assert "identical ranking" in status, q
        assert "retrieval budget" in status and "µs" in status


def test_rag_duel_free_text_and_native_backend():
    left, right, status = rag.rag_duel("does caffeine improve endurance performance?")
    assert len(left) == 10
    assert "per-query latency" in status and "rank_bm25 0.2.2" in status
    if NATIVE:
        assert "native Mojo" in status and "×" in status
    # scores shown rounded; both lanes show the same top doc
    assert left.iloc[0]["doc_id"] == right.iloc[0]["doc_id"]


def test_rag_duel_held_paths():
    _, _, status = rag.rag_duel("")
    assert "Enter a query" in status
    _, _, status = rag.rag_duel("!!! ???")
    assert "no usable tokens" in status
    # never raises, never returns a traceback
    left, right, status = rag.rag_duel(None)  # type: ignore[arg-type]
    assert "Traceback" not in status


# ---------------------------------------------------------------------------
# Tab 2 — LLM output scorer
# ---------------------------------------------------------------------------


def test_score_pair_matches_oracle():
    hyp = "The cat sat on the mat in the afternoon sun."
    refs_text = "The cat sat on the mat in the sun.\n\nA cat was sitting on the mat."
    ref_list = ["The cat sat on the mat in the sun.", "A cat was sitting on the mat."]
    out_json, verdict = scorer.score_pair(hyp, refs_text)
    body = json.loads(out_json)
    import sacrebleu

    oracle = sacrebleu.corpus_bleu([hyp], [ref_list])
    assert body["bleu"]["score"] == pytest.approx(round(oracle.score, 4), abs=1e-4)
    assert body["oracle_crosscheck"]["abs_delta_bleu"] <= 1e-9
    assert body["oracle_crosscheck"]["abs_delta_chrf"] <= 1e-9
    assert "deterministic scoring" in verdict
    assert len(body["bleu"]["precisions"]) == 4
    assert body["chrf"]["score"] > 0


def test_score_pair_input_validation():
    _, verdict = scorer.score_pair("", "ref")
    assert "hypothesis" in verdict
    _, verdict = scorer.score_pair("hyp", "")
    assert "reference" in verdict
    out, verdict = scorer.score_pair(None, None)  # type: ignore[arg-type]
    assert out == "" and "Traceback" not in verdict


def test_race_scorers_gate_and_speedup():
    table, verdict = scorer.race_scorers(500)
    if NATIVE:
        assert "| corpus BLEU" in table and "| corpus chrF" in table
        assert "gate passed" in verdict
        assert "|Δ BLEU| = 0.0e+00" in verdict  # bit-exact on the seeded batch
        assert "median of 5" in verdict and "seed 20260920" in verdict
    else:
        assert "race held" in verdict


def test_race_scorers_deterministic_batch():
    h1, r1 = scorer._race_batch(500)
    h2, r2 = scorer._race_batch(500)
    assert h1 == h2 and r1 == r2
    _, verdict = scorer.race_scorers(0)
    assert "between 1 and 10,000" in verdict


# ---------------------------------------------------------------------------
# Tab 3 — prompt-injection governance duel
# ---------------------------------------------------------------------------


def _envelope_pair(profile, message, override=False, state=None):
    transcript, envelope, audit, state = governed.agent_turn(profile, message, override, state)
    return transcript, json.loads(envelope) if envelope else {}, json.loads(audit), state


def test_observe_profile_intercepts_before_logging():
    transcript, env, audit, _ = _envelope_pair("observe", governed.PRESET_ATTACKS[2][1])
    assert "INTERCEPTED" in transcript
    assert env["execute_decision"]["error"]["code"] == "tool_not_in_profile"
    assert env["execute_decision"]["error"]["gate"] == "profile"
    assert "log_decision" not in env  # observe cannot even log
    assert audit[-1]["outcome"] == "intercepted" and audit[-1]["decision_id"] is None


def test_govern_profile_logs_then_intercepts():
    transcript, env, audit, _ = _envelope_pair("govern", governed.PRESET_ATTACKS[2][1])
    assert "INTERCEPTED" in transcript
    assert env["log_decision"]["outcome"] == "logged"
    assert env["execute_decision"]["error"]["gate"] == "profile"
    assert audit[-1]["decision_id"] == env["log_decision"]["decision_id"]


def test_risk_floor_denies_delete_all_users():
    transcript, env, audit, _ = _envelope_pair("execute", governed.PRESET_ATTACKS[0][1])
    assert "DENIED by policy gate `risk_floor`" in transcript
    err = env["execute_decision"]["error"]
    assert err["code"] == "execution_blocked_risk_floor" and err["gate"] == "risk_floor"
    assert audit[-1]["outcome"] == "denied"


def test_risk_floor_denies_exfiltration():
    _, env, _, _ = _envelope_pair("execute", governed.PRESET_ATTACKS[1][1])
    assert env["execute_decision"]["error"]["gate"] == "risk_floor"


def test_confidence_gate_denies_low_confidence():
    transcript, env, _, _ = _envelope_pair("execute", governed.PRESET_ATTACKS[3][1])
    assert "DENIED by policy gate `confidence`" in transcript
    assert env["execute_decision"]["error"]["code"] == "execution_blocked_confidence"


def test_happy_path_receipt_and_idempotency_on_repeat():
    state = governed.initial_state()
    transcript, env, audit, state = _envelope_pair(
        "execute", governed.PRESET_ATTACKS[2][1], state=state
    )
    assert "APPROVED" in transcript
    receipt = env["execute_decision"]
    assert receipt["execution_status"] == "delivered"
    assert receipt["response_code"] == 200
    assert receipt["policy_snapshot_id"] == "policy-snap-demo-1"
    assert receipt["manifest_version"] == "1.0.13"
    assert receipt["safety_overridden"] is False
    assert audit[-1]["outcome"] == "delivered"
    # second identical call in the same session → idempotency gate
    transcript2, env2, audit2, _ = _envelope_pair(
        "execute", governed.PRESET_ATTACKS[2][1], state=state
    )
    assert "idempotency" in transcript2
    assert env2["execute_decision"]["error"]["code"] == "execution_blocked_idempotency"
    assert audit2[-1]["gate"] == "idempotency"


def test_operator_override_is_explicit_and_audited():
    _, env, _, _ = _envelope_pair("execute", governed.PRESET_ATTACKS[0][1], override=True)
    receipt = env["execute_decision"]
    assert receipt["execution_status"] == "delivered"
    assert receipt["safety_overridden"] is True  # override never silent


def test_no_tool_call_and_unknown_profile():
    transcript, env, audit, _ = _envelope_pair("execute", "what is the weather like today?")
    assert "NO-OP" in transcript and env == {}
    transcript, _, _, _ = _envelope_pair("bogus", "refund order 123 confidence 0.9")
    assert "Unknown profile" in transcript


def test_mock_agent_confidence_parsing():
    assert (
        governed.mock_agent_parse("delete all users now, confidence 100%")["claimed_confidence"]
        == 1.0
    )
    assert (
        governed.mock_agent_parse("refund order 123, confidence 0.45")["claimed_confidence"] == 0.45
    )
    assert governed.mock_agent_parse("refund order 123")["claimed_confidence"] == 0.99
    assert governed.mock_agent_parse("hello there") is None


def test_profile_summary_lists_tools():
    text = governed.profile_summary("observe")
    assert "- `execute_decision`" not in text  # not in the model-facing tool list
    assert "- `query_data`" in text
    assert "140" in governed.profile_summary("full")


# ---------------------------------------------------------------------------
# Tab 4 — MCP playground
# ---------------------------------------------------------------------------


def test_registry_vendored_shape():
    reg = mcp_play.registry()
    assert reg["package"] == "algenta-mcp"
    assert reg["n_tools"] == 140 == len(reg["tools"])
    assert reg["registry_entry"] == "io.github.thyn-ai/algenta"
    names = {t["name"] for t in reg["tools"]}
    for tool in ("get_contract", "query_data", "simulate", "recommend", "execute_decision"):
        assert tool in names


def test_tool_table_profile_counts():
    assert len(mcp_play.tool_table("observe")) == 4
    assert len(mcp_play.tool_table("govern")) == 6
    assert len(mcp_play.tool_table("execute")) == 7
    assert len(mcp_play.tool_table("full")) == 140


def test_mcp_initialize_frame():
    frames = json.loads(mcp_play.mcp_frame("initialize"))
    req, res = frames["request"], frames["response"]
    assert req["jsonrpc"] == "2.0" and req["method"] == "initialize"
    assert res["result"]["serverInfo"]["name"] == "algenta-mcp"
    assert res["result"]["serverInfo"]["version"] == reg_version()
    assert "tools" in res["result"]["capabilities"]


def reg_version() -> str:
    return mcp_play.registry()["package_version"]


def test_mcp_tools_list_frame_has_all_140_with_schemas():
    frames = json.loads(mcp_play.mcp_frame("tools_list"))
    assert frames["request"]["method"] == "tools/list"
    tools = frames["response"]["result"]["tools"]
    assert len(tools) == 140
    for t in tools:
        assert t["name"] and t["description"] and "inputSchema" in t


def test_mcp_call_runner_all_demo_tools():
    for tool in mcp_play.CALLABLE_DEMO_TOOLS:
        frames_json, receipt_json = mcp_play.mcp_call(tool)
        frames = json.loads(frames_json)
        assert frames["request"]["method"] == "tools/call"
        assert frames["request"]["params"]["name"] == tool
        result = frames["response"]["result"]
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])  # real envelope inside
        assert payload
        receipt = json.loads(receipt_json)
        assert receipt["tool"] == tool and receipt["profile"] == "observe"
        assert receipt["engine"].startswith("simulated")


def test_mcp_call_runner_deterministic_payloads():
    f1, _ = mcp_play.mcp_call("simulate")
    f2, _ = mcp_play.mcp_call("simulate")
    p1 = json.loads(json.loads(f1)["response"]["result"]["content"][0]["text"])
    p2 = json.loads(json.loads(f2)["response"]["result"]["content"][0]["text"])
    assert p1 == p2  # seeded: same input → same output
    assert p1["runs"] == 10_000 and p1["p5"] < p1["p50"] < p1["p95"]


def test_mcp_call_rejects_non_demo_tool():
    out, msg = mcp_play.mcp_call("execute_decision")
    assert out == "" and "read-only demo tools" in msg


# ---------------------------------------------------------------------------
# Tab 5 — examples library
# ---------------------------------------------------------------------------


def test_examples_library_content():
    assert len(examples.INTEGRATIONS) == 10
    for name, install, _ in examples.INTEGRATIONS:
        assert install.startswith(("pip install ", "npm install ")), (name, install)
    html = examples.examples_html() + examples.integrations_html()
    for needle in (
        "algenta-sdk",
        "algenta-mcp",
        "algenta-speed-arena",
        "algenta-governed-tool-calls",
        "io.github.thyn-ai/algenta",
        "Community license",
        "langchain-algenta",
        "llamaindex-algenta",
        "pydantic-ai-algenta",
        "maf-algenta",
        "haystack-algenta",
        "litellm-algenta",
        "ray-serve-algenta",
        "vllm-algenta",
        "algenta-tools",
        "n8n-nodes-algenta",
        "mojo-kernels",
    ):
        assert needle in html, needle


# ---------------------------------------------------------------------------
# App assembly
# ---------------------------------------------------------------------------


def test_app_builds_with_named_endpoints():
    import app as space_app

    demo = space_app.build_app()
    assert demo is not None
    api_names = {
        dep.get("api_name") for dep in demo.config.get("dependencies", []) if dep.get("api_name")
    }
    for expected in ("rag_duel", "score_pair", "race_scorers", "agent_turn", "mcp_call"):
        assert expected in api_names, expected


def test_owner_rules_in_source():
    src = (SPACE_ROOT / "app.py").read_text()
    assert "DeepLinkButton" not in src
    assert "theme=THEME" in src  # canonical Algenta dark theme from design.py
    assert "prefers-color-scheme" not in src  # no forced-palette CSS hacks
    assert "sandbox=False" in src  # links never inside sandboxed HTML
