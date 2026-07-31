"""A non-finite result must not destroy the response, and must not become someone else's number.

JSON has no NaN and no infinity. `String(nan)` in Mojo emits the bare token `nan`, and `String`
of an infinity emits `inf` / `-inf` — none of which any strict parser accepts. Because the token
sits inside the response frame, a single non-finite value does not corrupt one field, it makes the
WHOLE frame unparseable. The client's `json.loads` then raises, the session layer terminates the
worker, and every resident dataset and open cursor goes with it.

MEASURED on `origin/main` against a compiled shard, reading the serving pid before and after:

    stats.compute_mean(FIVE, 0)            -> b'{"result":nan}'   -> pid gone
    stats.compute_mean([1e308, 1e308], 2)  -> b'{"result":inf}'   -> pid gone
    stats.compute_mean([-1e308,-1e308], 2) -> b'{"result":-inf}'  -> pid gone

**No guard could have stopped these.** `n = 0` satisfies every declared count relation (`0 <= 5`),
and the infinity cases have a legal count over a legal list. The value is produced by arithmetic
the kernel is entitled to do — `0.0 / 0.0`, and a sum that overflows — so this is not the count
class that #420 and #430 addressed. It is the serializer.

The fix is at the one leaf every path reaches: `_to_json_float64` / `_to_json_float32` in the
GENERATED dispatch. Guarding there covers bare returns, `List[Float64]`, nested lists, struct
fields at any depth, and mutated `mut` arguments — 5488 emitted result sites — rather than only the
bare-return case. Bare float returns additionally get a precise `non_finite_result` code naming the
kernel, because the module and function are known where that code is emitted.

Two neighbouring holes are closed with it:

* **Inbound.** A blacklist of `nan` / `inf` spellings misses the case that actually bites: `1e999`
  and `1.79e308` are ordinary decimals that the frozen `conv.parse_float64` turns into `+inf`,
  because its `_pow10(308)` multiply overflows. So the guard tests the PARSED VALUE, not the token
  text. Scalar float arguments only — list elements are deliberately left alone, because
  `stats.sort_values` documents dropping non-finite input rather than crashing.
* **The pipeline envelope.** With `continue_on_error`, a refused node used to leave `result`
  holding an EARLIER node's number while the envelope carried no `error_code` — so the SDK derived
  `success = True` and returned a plausible number from the wrong node. That would have converted
  today's loud crash into a silent wrong answer, which is strictly worse. `result` is now the
  terminal node's value or `null`, and a partial run carries `pipeline_partial`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.mojo_runtime import MojoRuntime  # noqa: E402

_SHARD_DIR = _REPO_ROOT / "mojo_build" / "runtime-shards"
_SHARD_MAP = _SHARD_DIR / "runtime-shards.json"


def _binary() -> str | None:
    """The worker that owns `stats`, never merely any worker.

    Against the default worker every call returns `module_not_registered` without reaching a
    kernel, so every assertion below would pass while proving nothing.
    """
    override = os.environ.get("ALGENTA_STATS_WORKER")
    if override and Path(override).is_file():
        return override
    if _SHARD_MAP.is_file():
        try:
            mapping = json.loads(_SHARD_MAP.read_text(encoding="utf-8"))
        except ValueError:
            mapping = {}
        name = (mapping.get("module_workers") or {}).get("stats")
        if name and (_SHARD_DIR / name).is_file():
            return str(_SHARD_DIR / name)
    return None


pytestmark = pytest.mark.skipif(
    _binary() is None,
    reason="no compiled worker owning `stats`; build with scripts/build_runtime_shards.py",
)

FIVE = [5.0, 4.0, 3.0, 2.0, 1.0]


@pytest.fixture(scope="module")
def runtime():
    from algenta.native import worker

    binary = _binary()
    assert binary is not None
    os.environ["ALGENTA_RUNTIME_WORKER"] = binary
    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    resolved = worker.resolve_worker(module_name="stats", require_verified=False)
    assert resolved is not None
    assert Path(resolved.path).resolve() == Path(binary).resolve()
    return MojoRuntime(mode="local")


def _pids() -> list[int]:
    """Process identity, because `health()` lies: the session layer respawns transparently, so it
    answers `ok` on a brand-new process and the kill is invisible."""
    from algenta.native import worker

    return sorted(s._proc.pid for s in worker._SESSIONS.values() if s._proc is not None)


def _serving(rt: MojoRuntime) -> list[int]:
    out = rt.execute("stats", "median", [FIVE, 5])
    assert out.get("result") == pytest.approx(3.0), f"warm-up missed the kernel: {out!r}"
    pids = _pids()
    assert pids, "no worker held; assertions would be vacuous"
    return pids


def test_the_warmup_reaches_the_kernel(runtime):
    assert _serving(runtime)


@pytest.mark.parametrize(
    ("args", "produces"),
    [
        ([FIVE, 0], "nan, from 0.0 / 0.0"),
        ([[1e308, 1e308], 2], "+inf, from a sum that overflows"),
        ([[-1e308, -1e308], 2], "-inf"),
    ],
)
def test_a_non_finite_result_is_refused_not_serialized(runtime, args, produces):
    """THE REGRESSION. Each of these ended the worker process on `origin/main`.

    Note the arguments are entirely legal: the count satisfies every declared relation, so no count
    guard is even consulted. The value is produced by arithmetic the kernel is allowed to do.
    """
    before = _serving(runtime)
    out = runtime.execute("stats", "compute_mean", args)
    after = _pids()
    assert after == before, (
        f"compute_mean{args} ({produces}) ended the worker process (pids {before} -> {after})"
    )
    assert out.get("success") is False, f"a non-finite result must not be reported as success: {out!r}"
    assert out.get("error_code") == "non_finite_result", (
        f"expected the precise code naming the kernel, got {out.get('error_code')!r}"
    )
    assert out.get("result") is None, (
        "there must be no numeric slot for a caller's default to fill"
    )


def test_every_finite_result_is_unchanged(runtime):
    """The guard must be non-behavioural for every value that already worked.

    Asserted on exact equality, not a tolerance: the change is a finiteness branch, so any drift in
    a finite value would mean the serializer itself changed.
    """
    before = _serving(runtime)
    for fn, args, want in (
        ("compute_mean", [FIVE, 5], 3.0),
        ("compute_mean", [FIVE, 2], 4.5),
        ("compute_mean", [FIVE, 1], 5.0),
        ("median", [FIVE, 5], 3.0),
        ("compute_variance", [FIVE, 5, 3.0], 2.5),
    ):
        out = runtime.execute("stats", fn, args)
        assert out.get("result") == want, f"stats.{fn}{args} -> {out.get('result')!r}, want {want}"
    assert _pids() == before


def test_a_finite_looking_argument_that_overflows_the_parser_is_refused(runtime):
    """`1.797e308` is an ordinary decimal, and the frozen parser turns it into `+inf`.

    This is why the inbound guard tests the parsed VALUE rather than the token text: a blacklist of
    `nan`/`inf` spellings does not match an all-digits-and-`e` literal, and `conv.parse_float64`'s
    `_pow10(308)` multiply overflows on the way in.
    """
    before = _serving(runtime)
    out = runtime.execute("stats", "compute_variance", [FIVE, 5, 1.7976931348623157e308])
    assert _pids() == before, "an overflowing argument must not end the worker"
    assert out.get("success") is False, f"expected a refusal, got {out!r}"
    assert out.get("error_code"), "the refusal must carry an error_code so batch/pipeline see it"


def test_a_refused_node_never_lends_its_slot_to_another_nodes_number(runtime):
    """The silent-wrong-answer this fix had to avoid creating.

    With `continue_on_error`, a failed terminal node used to leave `result` holding the last
    SUCCESSFUL node's value while the envelope carried no `error_code` — so `mojo_runtime`'s
    `success = not error_code` came out True and the caller received a plausible number produced by
    a different node than the one it asked for. Converting today's loud crash into that would have
    been strictly worse than the crash.

    `continue_on_error` is a frame field the Python SDK's `run_pipeline` does not expose, so the
    frame is sent through the session directly. That is deliberate rather than convenient: the field
    is read by `pipeline.mojo` and documented in `gitbook/engine/coarse-execution.md`, so it is
    reachable by any client that builds its own frame, and a test that could only drive it through
    the Python convenience wrapper would not cover it.

    MEASURED against the unpatched worker: this same frame raised `NativeWorkerUnavailable` and the
    pid was gone.
    """
    from algenta.native import worker

    resolution = worker.resolve_worker(module_name="stats", require_verified=False)
    assert resolution is not None
    session_cls = next(
        value
        for name, value in vars(worker).items()
        if name.endswith("Session") and isinstance(value, type)
    )
    session = session_cls(resolution)
    try:
        session.ensure_ready(30.0)
        pid = session._proc.pid
        out = session.execute(
            {
                "type": "pipeline_execute",
                "continue_on_error": True,
                "nodes": [
                    {"module": "stats", "function": "compute_mean", "args": [FIVE, 5]},
                    {"module": "stats", "function": "compute_mean", "args": [FIVE, 0]},
                ],
            },
            30.0,
        )
        assert session._proc is not None and session._proc.poll() is None, (
            f"the pipeline path ended worker pid {pid}"
        )
        assert out.get("failed") == 1 and out.get("ok") == 1, out
        assert out.get("result") is None, (
            "the terminal node failed, so `result` must be null rather than node 0's 3.0; got "
            f"{out.get('result')!r}"
        )
        assert out.get("error_code") == "pipeline_partial", (
            f"a partial run must carry a code, or `success` is derived as True; got {out!r}"
        )
        # The fix removes the SUBSTITUTION, not the data: node 0's answer is still there.
        assert out.get("results") == [pytest.approx(3.0), None], out
    finally:
        session.close()
