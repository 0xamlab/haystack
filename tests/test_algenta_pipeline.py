"""Unit tests for algenta.pipeline — reference binding and shard refusal.

Stubs the worker transport, so these run without a compiled binary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.mojo_runtime import _BundledRuntime  # noqa: E402
from algenta.native import worker as worker_mod  # noqa: E402
from algenta.pipeline import PREV, Pipeline, PipelineShardError, Ref  # noqa: E402


class _FakeRuntime:
    def __init__(self) -> None:
        self.sent: list[list[dict]] = []

    def run_pipeline(self, nodes):
        self.sent.append(nodes)
        return {"result": "ok", "nodes": len(nodes)}


def test_ref_and_prev_lower_to_wire_form() -> None:
    fake = _FakeRuntime()
    plan = (
        Pipeline(fake)
        .kernel("stats", "sort_values", [[3.0, 1.0, 2.0], 3])
        .kernel("stats", "median", [Ref(0), 3])
        .kernel("stats", "compute_mean", [PREV, 1])
    )
    nodes = plan.nodes()
    assert nodes[1]["args"] == ["$0", 3]
    assert nodes[2]["args"] == ["$1", 1], "PREV must resolve to the immediately-prior index"
    assert len(plan) == 3


def test_nested_refs_inside_lists_are_bound() -> None:
    fake = _FakeRuntime()
    plan = Pipeline(fake).kernel("m", "a", [1]).kernel("m", "b", [[Ref(0), 2], 3])
    assert plan.nodes()[1]["args"] == [["$0", 2], 3]


def test_prev_on_first_node_is_rejected() -> None:
    with pytest.raises(ValueError, match="no predecessor"):
        Pipeline(_FakeRuntime()).kernel("m", "f", [PREV])


def test_negative_ref_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Ref(-1)


def test_execute_delegates_the_built_nodes() -> None:
    fake = _FakeRuntime()
    Pipeline(fake).kernel("stats", "median", [[1.0], 1]).execute()
    assert len(fake.sent) == 1
    assert fake.sent[0][0]["function"] == "median"


def test_empty_plan_returns_a_zero_envelope() -> None:
    runtime = _BundledRuntime(
        mode="local", api_key="", timeout=5.0, auto_start_daemon=False, base_url=""
    )
    out = runtime.run_pipeline([])
    assert out["nodes"] == 0
    assert out["success"] is True


def test_cross_shard_plan_is_refused_not_half_executed(monkeypatch) -> None:
    routes = {"stats": "/w/worker-000", "feature_hashing": "/w/worker-001"}

    def fake_require_worker(*, module_name=None, require_verified=False):
        return SimpleNamespace(path=routes.get(module_name, "/w/worker-000"))

    def must_not_run(*args, **kwargs):  # pragma: no cover - asserts absence
        raise AssertionError("a cross-shard plan must not reach the worker")

    monkeypatch.setattr(worker_mod, "require_worker", fake_require_worker)
    monkeypatch.setattr(worker_mod, "execute", must_not_run)

    runtime = _BundledRuntime(
        mode="local", api_key="", timeout=5.0, auto_start_daemon=False, base_url=""
    )
    nodes = [
        {"module": "stats", "function": "median", "args": [[1.0], 1]},
        {"module": "feature_hashing", "function": "hash_feature", "args": ["x", 8, 1]},
    ]
    with pytest.raises(PipelineShardError) as exc:
        runtime.run_pipeline(nodes)
    assert "span more than one runtime shard" in str(exc.value)
    # The message must name which modules sit where, or it is not actionable.
    assert "stats" in str(exc.value) and "feature_hashing" in str(exc.value)


def test_single_shard_plan_sends_one_frame(monkeypatch) -> None:
    sent: list[dict] = []

    def fake_require_worker(*, module_name=None, require_verified=False):
        return SimpleNamespace(path="/w/worker-000")

    def fake_execute(request, *, timeout=60.0, require_verified=False, module_name=None):
        sent.append({"frame": request, "module_name": module_name})
        return {"result": 2.0, "nodes": 2, "ok": 2, "failed": 0, "plan_hash": "a" * 64}

    monkeypatch.setattr(worker_mod, "require_worker", fake_require_worker)
    monkeypatch.setattr(worker_mod, "execute", fake_execute)

    runtime = _BundledRuntime(
        mode="local", api_key="", timeout=5.0, auto_start_daemon=False, base_url=""
    )
    nodes = [
        {"module": "stats", "function": "sort_values", "args": [[2.0, 1.0], 2]},
        {"module": "stats", "function": "median", "args": ["$0", 2]},
    ]
    out = runtime.run_pipeline(nodes)
    assert len(sent) == 1, "a two-node chain must cost one frame"
    assert sent[0]["frame"]["type"] == "pipeline_execute"
    assert sent[0]["module_name"] == "stats"
    assert out["success"] is True
    assert "latency_ms" in out


def test_worker_error_code_marks_the_envelope_unsuccessful(monkeypatch) -> None:
    def fake_require_worker(*, module_name=None, require_verified=False):
        return SimpleNamespace(path="/w/worker-000")

    def failing(request, *, timeout=60.0, require_verified=False, module_name=None):
        return {
            "error_code": "pipeline_node_failed",
            "error_message": "node 1 failed",
            "failed_index": 1,
        }

    monkeypatch.setattr(worker_mod, "require_worker", fake_require_worker)
    monkeypatch.setattr(worker_mod, "execute", failing)

    runtime = _BundledRuntime(
        mode="local", api_key="", timeout=5.0, auto_start_daemon=False, base_url=""
    )
    out = runtime.run_pipeline([{"module": "stats", "function": "median", "args": [[1.0], 1]}])
    assert out["success"] is False
    assert out["failed_index"] == 1
