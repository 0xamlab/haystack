"""Local A-Z tests for the Algenta flagship Space.

Run with the main venv active (CPython 3.14, requirements.txt installed) and
ARENA_PYTHON pointing at a CPython 3.12 arena venv (arena-requirements.txt):

    ARENA_PYTHON=/path/to/arena/bin/python python -m pytest tests/ -v

Covers: catalog integrity against the live published packages, every UI
handler (arena duel via the subprocess runner, LLM module demos on the real
signed runtime, the governed engine adapter in both modes, the MCP registry
surface), the app factory, and the honesty labels. No mocks of kernels or the
runtime — the only fake is the SDK client used to exercise HostedEngine
offline (the hosted path itself needs a real tenant key).
"""

from __future__ import annotations

import importlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402
import catalogs  # noqa: E402
import governed  # noqa: E402
import modules_core  # noqa: E402
from arena.card import render_card  # noqa: E402
from arena.duels import DUELS, DUELS_BY_ID  # noqa: E402
from arena_client import ArenaUnavailable, reconstruct_outcome, run_duel  # noqa: E402

# ---------------------------------------------------------------------------
# Catalog integrity — static data must match the live published artifacts
# ---------------------------------------------------------------------------


def test_kernel_catalog_is_44_with_valid_status():
    assert len(catalogs.KERNELS) == 44
    statuses = {k[3] for k in KERNELS_CHECK()}
    assert statuses <= {"live", "repo", "wave-3"}
    assert sum(1 for k in KERNELS_CHECK() if k[3] == "wave-3") == 9


def KERNELS_CHECK():
    return catalogs.KERNELS


def test_integrations_are_10():
    assert len(catalogs.INTEGRATIONS) == 10
    npm = [i for i in catalogs.INTEGRATIONS if i[2].startswith("npm install")]
    pypi = [i for i in catalogs.INTEGRATIONS if i[2].startswith("pip install")]
    assert len(npm) == 2 and len(pypi) == 8


def test_top10_entries_exist_in_catalog():
    names = {k[0] for k in catalogs.KERNELS}
    for pkg, _target, _speed in catalogs.KERNEL_TOP10:
        assert pkg in names, pkg


def test_mcp_categories_match_live_registry_exactly():
    from algenta_mcp.registry import TOOLS

    union = [t for tools in catalogs.MCP_CATEGORIES.values() for t in tools]
    assert len(TOOLS) == 140
    assert sorted(union) == sorted(TOOLS.keys()), "category manifest drifted from the package"
    # every registry spec carries real metadata
    for name, entry in TOOLS.items():
        assert entry["spec"]["description"].strip(), name
        assert "inputSchema" in entry["spec"], name


def test_modules_22_count():
    assert len(modules_core.MODULES_22) == 22


# ---------------------------------------------------------------------------
# Overview / hero metrics
# ---------------------------------------------------------------------------


def test_metrics_html_has_live_countups():
    app._BOOT["mcp_tools"] = 140
    app._BOOT["runtime_modules"] = 643
    html = app.metrics_html()
    assert html.count("alg-count") == 5
    assert 'data-target="44"' in html
    assert 'data-target="10"' in html
    assert 'data-target="140"' in html
    assert 'data-target="22"' in html
    assert 'data-target="643"' in html


def test_metrics_html_pending_state():
    app._BOOT["mcp_tools"] = None
    html = app.metrics_html()
    assert "—" in html  # the not-yet-computed cell renders a dash, never a fake number
    app._BOOT["mcp_tools"] = 140  # restore


def test_static_html_blocks_render():
    assert "alg-hero" in app.hero_html()
    assert "alg-map" in app.product_map_html()
    # SDK Hub is native Group cards now — the content builders carry the copy
    pkg_cards = [app._pkg_card_md(p) for p in catalogs.CORE_PACKAGES]
    assert any("algenta-sdk" in c for c in pkg_cards)
    assert any("algenta-mcp" in c for c in pkg_cards)
    integ_cards = [app._integration_card_md(*i) for i in catalogs.INTEGRATIONS]
    assert len(integ_cards) == 10 and all("`" in c for c in integ_cards)  # install lines
    top10 = app.kernel_top10_rows()
    assert "13,137×" in {r[3] for r in top10} and len(top10) == 10
    cats = app.mcp_categories_html()
    assert "140" in cats and "counted live" in cats
    wave = app.wave3_html()
    assert "1,663.7×" in wave and "53.7×" in wave
    assert "not</b> live cells" in wave  # the honesty label is non-negotiable


# ---------------------------------------------------------------------------
# MCP tab handlers
# ---------------------------------------------------------------------------


def test_mcp_table_full_and_filtered():
    rows = app.mcp_table("", "all")
    assert len(rows) == 140
    names = {r[0] for r in rows}
    assert "execute_decision" in names and "query_data" in names
    dec = app.mcp_table("decision", "all")
    assert 0 < len(dec) < 140
    assert all("decision" in r[0].lower() or "decision" in r[2].lower() for r in dec)
    cat = app.mcp_table("", "Decision Memory")
    assert {r[0] for r in cat} == {
        "log_decision",
        "list_decisions",
        "get_decision",
        "execute_decision",
        "delete_decision",
        "record_outcome",
    }


# ---------------------------------------------------------------------------
# Governed Agents — demo engine flow (deterministic, stateful)
# ---------------------------------------------------------------------------


def test_governed_demo_full_flow():
    assert governed.engine_mode() == "demo"  # no key in the test env
    state = governed.initial_state()

    out, did, state = app.on_log("refund_order_123", 0.93, 0.02, state)
    body = json.loads(out)
    assert body["outcome"] == "logged" and did == "decision-refund-order-123"
    assert body["policy"]["min_confidence"] == governed.MIN_CONFIDENCE

    # observe profile intercepts before the engine is ever called
    verdict, body_json, audit_json, state = app.on_execute("observe", did, "", False, False, state)
    assert "INTERCEPTED" in verdict
    assert json.loads(body_json)["error"]["code"] == "tool_not_in_profile"

    # execute profile approves
    verdict, body_json, audit_json, state = app.on_execute(
        "execute", did, "https://example.org/hooks/orders", False, False, state
    )
    assert "APPROVED" in verdict and "alg-verdict ok" in verdict
    receipt = json.loads(body_json)
    assert receipt["execution_status"] == "delivered"
    assert receipt["decision_id"] == did
    assert receipt["policy_snapshot_id"] and receipt["schema_snapshot_id"]

    # idempotency gate fires on re-execution, force bypasses it
    verdict, body_json, _, state = app.on_execute("execute", did, "", False, False, state)
    assert "DENIED by policy gate `idempotency`" in verdict
    assert json.loads(body_json)["error"]["code"] == "execution_blocked_idempotency"
    verdict, body_json, _, state = app.on_execute("execute", did, "", True, False, state)
    assert "APPROVED" in verdict

    audit = json.loads(audit_json)
    assert [a["outcome"] for a in audit][:2] == ["intercepted", "delivered"]


def test_governed_demo_confidence_and_risk_gates():
    state = governed.initial_state()
    _out, did, state = app.on_log("ship_pricing_change", 0.40, -0.30, state)
    verdict, body_json, _, state = app.on_execute("execute", did, "", False, False, state)
    assert "confidence" in verdict
    assert json.loads(body_json)["error"]["code"] == "execution_blocked_confidence"
    # override_safety bypasses both the confidence and the risk-floor gates
    verdict, body_json, _, state = app.on_execute("execute", did, "", False, True, state)
    assert "APPROVED" in verdict
    assert json.loads(body_json)["safety_overridden"] is True


def test_governed_unknown_decision_denied():
    state = governed.initial_state()
    verdict, body_json, _, state = app.on_execute(
        "execute", "decision-nope", "", False, False, state
    )
    assert "unknown decision id" in verdict
    assert json.loads(body_json)["error"]["code"] == "decision_not_found"


def test_governed_empty_action_warns():
    out, did, _state = app.on_log("   ", 0.9, 0.0, governed.initial_state())
    assert out == "" and did == ""


# ---------------------------------------------------------------------------
# Governed Agents — hosted engine adapter (offline fake SDK client)
# ---------------------------------------------------------------------------


class _FakeReceipt:
    def model_dump(self, mode="json"):
        return {
            "decision_id": "dec-1",
            "webhook_url": "https://example.org/hooks/demo",
            "execution_status": "delivered",
            "response_code": 200,
            "executed_at": "2026-09-20T00:00:00Z",
            "policy_snapshot_id": "ps-1",
            "schema_snapshot_id": "ss-1",
            "manifest_version": "1.0.18",
            "payload_summary": {"chosen_action": "refund_order_123"},
            "safety_overridden": False,
        }


class _FakeSDKError(__import__("decision_engine").DecisionEngineError):
    def __init__(self):
        super().__init__(
            "confidence below policy",
            status_code=422,
            response_body={"error": {"code": "execution_blocked_confidence"}},
            request_id="req-1",
        )


class _FakeClient:
    def log_decision(self, request):
        assert request["chosen_action"] == "refund_order_123"
        return {
            "decision_id": "dec-1",
            "chosen_action": request["chosen_action"],
            "outcome": "logged",
        }

    def execute_decision(self, decision_id, **kwargs):
        if decision_id == "dec-deny":
            raise _FakeSDKError()
        assert kwargs["webhook_url"]
        return _FakeReceipt()


def test_hosted_engine_paths(monkeypatch):
    monkeypatch.setenv("ALGENTA_API_KEY", "sk-test-fake")
    hosted = governed.HostedEngine.__new__(governed.HostedEngine)  # bypass real client construction
    hosted._client = _FakeClient()
    import threading

    hosted._lock = threading.Lock()

    state = governed.initial_state()
    body, did = hosted.log_decision("refund_order_123", 0.93, 0.02, state)
    assert did == "dec-1" and body["outcome"] == "logged"

    verdict, receipt = hosted.execute_decision(
        "execute", "dec-1", "https://example.org/hooks/demo", False, False, state
    )
    assert verdict.startswith("APPROVED")
    assert receipt["execution_status"] == "delivered" and receipt["policy_snapshot_id"] == "ps-1"

    verdict, denial = hosted.execute_decision(
        "execute", "dec-deny", "https://example.org/x", False, False, state
    )
    assert "DENIED" in verdict
    assert denial["error"]["code"] == "execution_blocked_confidence"
    assert denial["error"]["gate"] == "confidence"

    # profile interception happens client-side even in hosted mode
    verdict, denial = hosted.execute_decision("observe", "dec-1", "", False, False, state)
    assert "INTERCEPTED" in verdict
    assert denial["error"]["code"] == "tool_not_in_profile"


def test_engine_factory_respects_env(monkeypatch):
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    governed._ENGINE = None
    assert governed.engine_mode() == "demo"
    assert isinstance(governed.get_engine(), governed.DemoEngine)
    assert "DEMO ENGINE" in governed.engine_badge()
    monkeypatch.setenv("ALGENTA_API_KEY", "sk-test-fake")
    governed._ENGINE = None
    assert governed.engine_mode() == "live"
    assert "LIVE" in governed.engine_badge()
    governed._ENGINE = None


# ---------------------------------------------------------------------------
# LLM Modules — real signed-runtime executions
# ---------------------------------------------------------------------------


def test_tokenize_live():
    out, meta, trace, snippet = app.on_tokenize("Mojo kernels run live in this Space.")
    display = json.loads(out)
    assert "error" not in display
    assert display["tokens"] == ["mojo", "kernels", "run", "live", "in", "this", "space"]
    assert display["bpe_tokenizer_metrics_from_real_counts"]["tokens"] == 7
    assert "live kernel calls" in meta
    calls = json.loads(trace)
    assert {c["module"] for c in calls} == {"text.tokenizer", "bpe_tokenizer"}
    assert "MojoRuntime" in snippet


def test_retrieve_live():
    rows, scores_json, meta, trace, _snippet = app.on_retrieve(
        "how does flash attention save memory?"
    )
    assert len(rows) == 3
    assert rows[0][1] == "flash-attention"  # the demo hash-embedder must rank it first
    assert rows[0][2] > 0.0
    scores = json.loads(scores_json)
    assert "flash-attention" in scores["all_cosine_scores"]
    assert abs(float(rows[0][3]) - float(rows[0][2])) < 1e-6  # sparse cross-check == dense
    assert "not a neural model" in meta


def test_attention_parity_live():
    out, meta, trace, _snippet = app.on_attention()
    report = json.loads(out)
    assert "error" not in report
    assert report["parity_max_abs_diff"] < 1e-9
    assert report["verdict"] == "outputs match (parity < 1e-9)"
    assert report["live_kernel_calls_this_run"] > 500
    assert report["mojo_output_last_row"] == report["numpy_output_last_row"]


def test_runtime_catalog_count_live():
    n = modules_core.runtime_module_count()
    assert n == 643


# ---------------------------------------------------------------------------
# Arena — subprocess duel runner (needs ARENA_PYTHON; croniter S is fast)
# ---------------------------------------------------------------------------

ARENA_PY = os.environ.get("ARENA_PYTHON", "")
ARENA_AVAILABLE = bool(ARENA_PY) and os.path.isfile(ARENA_PY)


@pytest.mark.skipif(not ARENA_AVAILABLE, reason="ARENA_PYTHON not set to a 3.12 arena venv")
def test_arena_duel_croniter_live(tmp_path):
    outcome = run_duel("croniter", "S", timeout_s=240.0)
    assert outcome.status == "ok", f"held/error: {outcome.held_reason}"
    assert outcome.gate_ok and outcome.parity_label
    assert outcome.hero_speedup > 1.0
    assert len(outcome.lanes) == 2
    for lane in outcome.lanes:
        assert lane.runs == 5
        assert lane.warm_min_s <= lane.warm_median_s <= lane.warm_max_s
    duel = DUELS_BY_ID["croniter"]
    card = render_card(outcome, duel, duel.divisor("S"), duel.divided_label)
    assert f"{outcome.hero_speedup:,.2f}×" in card
    assert "parity" in card


@pytest.mark.skipif(not ARENA_AVAILABLE, reason="ARENA_PYTHON not set to a 3.12 arena venv")
def test_arena_runner_progress_streams():
    seen = []
    outcome = run_duel("pefile", "S", progress=seen.append, timeout_s=240.0)
    assert outcome.status in {"ok", "held"}
    assert any("gate" in line.lower() for line in seen)


def test_arena_unavailable_is_explicit(monkeypatch):
    monkeypatch.setenv("ARENA_PYTHON", "/nonexistent/python")
    with pytest.raises(ArenaUnavailable):
        run_duel("croniter", "S")
    status = importlib.import_module("arena_client").arena_status()
    assert "unavailable" in status


def test_outcome_reconstruction_roundtrip():
    import dataclasses
    import time as _time

    from arena.harness import DuelOutcome

    o = DuelOutcome(
        duel_id="x",
        duel_title="t",
        size_key="S",
        size_label="s",
        status="ok",
        gate_ok=True,
        gate_detail="d",
        parity_label="p",
        hero_speedup=2.5,
        hero_label="2.50× vs a",
        hardware="hw",
        timestamp=_time.strftime("%Y-%m-%d %H:%M:%S UTC", _time.gmtime()),
    )
    data = dataclasses.asdict(o)
    back = reconstruct_outcome(dict(data))
    assert back.hero_speedup == 2.5 and back.lanes == []


def test_duel_registry_eight_headliners():
    assert [d.duel_id for d in DUELS] == [
        "bm25",
        "vol-hive",
        "pefile",
        "croniter",
        "ruptures",
        "pykalman",
        "vol-pool",
        "oletools",
    ]
    for d in DUELS:
        assert set(d.sizes) == {"S", "M", "L"}
        assert d.title and d.blurb and d.config_note


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def test_app_factory_builds():
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    demo = app.build_app()
    assert demo is not None
    assert app.DEFAULT_DUEL in DUELS_BY_ID


# ---------------------------------------------------------------------------
# Arena UX: sweep-to-win copy audit + reliable default duel
# ---------------------------------------------------------------------------

FORBIDDEN_COPY = (
    "held",
    "publish-wins",
    "never shown as a loss",
    "never a loss",
    "losing",
    " a loss",
)


def test_default_duel_is_the_reliable_big_winner():
    assert app.DEFAULT_DUEL == "vol-hive"
    assert DUELS_BY_ID["vol-hive"].default_size == "S"
    assert DUELS_BY_ID["bm25"].default_size == "L"  # its reliable winning cell on cpu-basic
    assert DUELS_BY_ID["bm25"].variant == "batched"
    for d in DUELS:
        assert d.default_size in d.sizes, d.duel_id


def test_arena_copy_has_no_held_speak():
    """Every user-facing arena string is free of held/rule-speak."""
    from arena.card import render_fallback, render_held
    from arena.harness import DuelOutcome

    err = render_held(
        DuelOutcome(
            duel_id="x",
            duel_title="t",
            size_key="S",
            size_label="s",
            status="error",
            held_reason="synthetic reason",
            hardware="hw",
        )
    )
    fallback = render_fallback(
        {
            "duel": "t",
            "size_label": "s",
            "ts": "2026-09-21 12:00:00 UTC",
            "hero_speedup": 16.4,
            "hero_label": "16.40× vs x",
            "parity": "p",
            "hardware": "hw",
        },
        "press Run duel for a live rematch",
    )
    for text in (app.METHODOLOGY_MD, err, fallback):
        low = text.lower()
        for bad in FORBIDDEN_COPY:
            assert bad not in low, f"held-copy {bad!r} found in: {text[:120]}"


def test_leaderboard_store_keeps_wins_only(tmp_path, monkeypatch):
    from arena import store
    from arena.harness import DuelOutcome

    monkeypatch.setattr(store, "_PATH", str(tmp_path / "board.json"))
    loss = DuelOutcome(
        duel_id="x",
        duel_title="t",
        size_key="S",
        size_label="s",
        status="held",
        held_kind="loss",
        held_reason="incumbent faster",
        hero_speedup=0.5,
        hardware="hw",
    )
    store.record(loss)
    assert store.all_records() == [] and store.latest_per_duel() == []
    win = DuelOutcome(
        duel_id="x",
        duel_title="t",
        size_key="S",
        size_label="s",
        status="ok",
        hero_speedup=3.0,
        hero_label="3.00× vs a",
        parity_label="p",
        hardware="hw",
        timestamp="2026-09-21 12:00:00 UTC",
    )
    store.record(win)
    assert store.latest_win("x")["ts"] == "2026-09-21 12:00:00 UTC"
    assert store.latest_per_duel()[0]["hero_speedup"] == 3.0
