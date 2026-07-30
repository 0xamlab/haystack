"""Unit tests for algenta.batch — shard grouping, ordering and error isolation.

Uses the real contract (so argument validation and result decoding are genuine)
but stubs the worker transport, so these run without a compiled binary.
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

from algenta import batch as batch_mod  # noqa: E402
from algenta.native import worker as worker_mod  # noqa: E402


@pytest.fixture
def transport(monkeypatch):
    """Stub shard routing + frame transport, recording every frame sent."""
    sent: list[dict] = []
    # Put `stats` and `median`-ish modules on one worker, `feature_hashing` on another.
    routes = {"stats": "/w/worker-000", "feature_hashing": "/w/worker-001"}

    def fake_require_worker(*, module_name=None, require_verified=False):
        return SimpleNamespace(path=routes.get(module_name, "/w/worker-000"))

    def fake_execute(request, *, timeout=60.0, require_verified=False, module_name=None):
        sent.append({"frame": request, "module_name": module_name})
        results = []
        for item in request["requests"]:
            if item["function"] == "__boom__":
                results.append(
                    {
                        "error": "function_not_registered: nope",
                        "error_code": "function_not_registered",
                        "error_message": "nope",
                    }
                )
                if not request.get("partial_ok", True):
                    break
            else:
                results.append({"result": 1.5})
        return {"results": results, "count": len(results)}

    monkeypatch.setattr(worker_mod, "require_worker", fake_require_worker)
    monkeypatch.setattr(worker_mod, "execute", fake_execute)
    return sent


def _item(module: str, function: str, args):
    return {"module": module, "function": function, "args": args}


def test_empty_batch_is_a_zero_envelope(transport) -> None:
    out = batch_mod.execute_batch([])
    assert out == {"results": [], "count": 0, "ok": 0, "failed": 0, "frames": 0, "latency_ms": 0.0}
    assert transport == []


def test_single_shard_sends_exactly_one_frame(transport) -> None:
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("stats", "median", [[1.0, 2.0, 3.0], 3]),
    ]
    out = batch_mod.execute_batch(items)
    assert out["frames"] == 1, "two same-shard calls must not cost two frames"
    assert out["count"] == 2
    assert out["ok"] == 2
    assert len(transport) == 1
    assert transport[0]["frame"]["type"] == "batch_execute"
    assert transport[0]["module_name"] == "stats"


def test_cross_shard_batch_splits_by_worker_and_preserves_order(transport) -> None:
    # collision_rate_estimate returns Float64, matching the stub's result type.
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("feature_hashing", "collision_rate_estimate", [100, 1024]),
        _item("stats", "median", [[1.0, 2.0, 3.0], 3]),
    ]
    out = batch_mod.execute_batch(items)
    # A worker only holds its own shard's modules, so this cannot be one frame.
    assert out["frames"] == 2
    assert out["count"] == 3
    assert out["ok"] == 3
    routed = {frame["module_name"] for frame in transport}
    assert routed == {"stats", "feature_hashing"}
    # The stats group carries items 0 and 2; the feature_hashing group carries 1.
    by_module = {frame["module_name"]: frame["frame"]["requests"] for frame in transport}
    assert len(by_module["stats"]) == 2
    assert len(by_module["feature_hashing"]) == 1


def test_cross_shard_failure_lands_at_the_callers_index(transport, monkeypatch) -> None:
    """Reassembly must map group-local positions back to caller indices."""

    def per_shard(request, *, timeout=60.0, require_verified=False, module_name=None):
        if module_name == "feature_hashing":
            return {
                "results": [
                    {
                        "error": "x",
                        "error_code": "mojo_library_execution_failed",
                        "error_message": "second shard failed",
                    }
                ]
            }
        return {"results": [{"result": 1.5} for _ in request["requests"]]}

    monkeypatch.setattr(worker_mod, "execute", per_shard)
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("feature_hashing", "collision_rate_estimate", [100, 1024]),
        _item("stats", "median", [[1.0, 2.0, 3.0], 3]),
    ]
    out = batch_mod.execute_batch(items)
    assert out["results"][0]["success"] is True
    assert out["results"][1]["success"] is False, "failure must land at index 1, not 2"
    assert out["results"][1]["error_code"] == "mojo_library_execution_failed"
    assert out["results"][2]["success"] is True


def test_contract_violation_never_reaches_a_worker(transport) -> None:
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("stats", "__no_such_function__", []),
    ]
    out = batch_mod.execute_batch(items)
    assert out["results"][0]["success"] is True
    assert out["results"][1]["success"] is False
    assert out["results"][1]["error_code"] == "function_not_registered"
    # Only the valid item was framed.
    assert len(transport[0]["frame"]["requests"]) == 1


def test_per_item_worker_error_does_not_sink_neighbours(transport) -> None:
    # `median` exists, so this reaches the worker; the stub fails on __boom__ only.
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("stats", "median", [[1.0, 2.0, 3.0], 3]),
    ]
    out = batch_mod.execute_batch(items)
    assert out["ok"] == 2 and out["failed"] == 0

    # Now force a worker-side failure on the second item.
    def failing(request, *, timeout=60.0, require_verified=False, module_name=None):
        return {
            "results": [
                {"result": 1.5},
                {
                    "error": "x",
                    "error_code": "mojo_library_execution_failed",
                    "error_message": "boom",
                },
            ]
        }

    worker_mod.execute = failing
    out2 = batch_mod.execute_batch(items)
    assert out2["ok"] == 1
    assert out2["failed"] == 1
    assert out2["results"][0]["success"] is True
    assert out2["results"][1]["error_code"] == "mojo_library_execution_failed"


def test_short_circuit_marks_unreached_items_not_executed(transport, monkeypatch) -> None:
    def truncating(request, *, timeout=60.0, require_verified=False, module_name=None):
        # partial_ok=False: worker stops after the first item.
        return {"results": [{"result": 1.5}]}

    monkeypatch.setattr(worker_mod, "execute", truncating)
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("stats", "median", [[1.0, 2.0, 3.0], 3]),
    ]
    out = batch_mod.execute_batch(items, partial_ok=False)
    assert out["results"][0]["success"] is True
    assert out["results"][1]["error_code"] == "not_executed"


def test_worker_unavailable_fails_every_item_in_that_group(transport, monkeypatch) -> None:
    def unavailable(request, *, timeout=60.0, require_verified=False, module_name=None):
        raise worker_mod.NativeWorkerUnavailable("no worker")

    monkeypatch.setattr(worker_mod, "execute", unavailable)
    items = [
        _item("stats", "compute_mean", [[1.0, 2.0], 2]),
        _item("stats", "median", [[1.0, 2.0, 3.0], 3]),
    ]
    out = batch_mod.execute_batch(items)
    assert out["ok"] == 0
    assert all(entry["error_code"] == "compute_runtime_unavailable" for entry in out["results"])


def test_malformed_envelope_fails_the_group_with_a_code(transport, monkeypatch) -> None:
    def garbage(request, *, timeout=60.0, require_verified=False, module_name=None):
        return {"error_code": "mojo_library_execution_failed", "error_message": "bad frame"}

    monkeypatch.setattr(worker_mod, "execute", garbage)
    out = batch_mod.execute_batch([_item("stats", "compute_mean", [[1.0, 2.0], 2])])
    assert out["failed"] == 1
    assert out["results"][0]["error_code"] == "mojo_library_execution_failed"
