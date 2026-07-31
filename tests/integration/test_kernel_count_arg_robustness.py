"""A caller-supplied element COUNT must not be able to kill the worker.

Many kernels take `(values: List[Float64], n: Int)` and trust `n`. Reading past a List end in Mojo
is an UNCATCHABLE bounds assertion: it aborts the whole worker process, taking every resident
dataset and open cursor with it, and a `try/except` at any layer above does not help. Because `n`
arrives over the wire through `library_execute`, an unguarded count is a remotely-triggerable kill.

MEASURED on `origin/main` (2026-07-31): `stats.sort_values` looped `for i in range(n)` with no
`n <= len(v)` check, and `library_execute stats.sort_values [[5 floats], 25]` killed the serving
worker — a `pgrep` before and after showed the pid gone. `quantile`, `percentile` and `median` all
funnel through it, so four public contract exports shared one hole.

**Why no existing test caught it, which is the part worth remembering:** the generated A-Z suite
calls every contract function with a 5-element list and `5` for every `Int` (`_SCALAR_VALUES` and
the `_lf5` preamble in `tests/generate_mojo_tests.py`). So `n <= len(v)` always held and the suite
was green. The hazard is invisible to a harness whose sample count always matches its sample
length.

These assertions therefore check the property the suite cannot: the worker is still ALIVE and
serving after a hostile count. Whether the call succeeds or returns an error is secondary — a
defined answer and a typed refusal are both fine. A dead worker is not.

Generalising this into a sweep over every `(List, Int)` signature in the contract needs per-function
length metadata, which is what the Phase 6 capability manifest exists to provide; the same metadata
is what would let `batch_execute` pre-validate an item instead of losing the process to it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.mojo_runtime import MojoRuntime  # noqa: E402

_CANDIDATES = (
    os.environ.get("ALGENTA_RUNTIME_WORKER"),
    os.environ.get("ALGENTA_NATIVE_WORKER"),
    str(_REPO_ROOT / "mojo_build" / "runtime-shards" / "algenta-runtime-worker"),
    str(_REPO_ROOT / "mojo_build" / "simulate_queryplane"),
    str(_REPO_ROOT / "mojo_build" / "simulate"),
)


def _binary() -> str | None:
    for candidate in _CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


pytestmark = pytest.mark.skipif(
    _binary() is None,
    reason="no compiled runtime binary; build one with scripts/build_runtime_shards.py --shard-size 24",
)

# Five values, deliberately unsorted, with a median of 3.0 that is not the mean of the endpoints
# either, so a clamped answer is distinguishable from a truncated or zeroed one.
FIVE = [5.0, 4.0, 3.0, 2.0, 1.0]
HOSTILE_N = 25


@pytest.fixture(scope="module")
def runtime():
    """A local runtime on the compiled binary — never the daemon, never a Python fallback.

    A repo-dev build is unsigned, so the shard-map integrity check the packaged worker passes will
    reject it and the default `deny` fallback declines to run it at all. Relaxing to `allow` does
    NOT let a Python path answer: the resolution assertion below fails loudly if some other runtime
    is serving, rather than letting these tests pass against nothing.
    """
    from algenta.native import worker

    binary = _binary()
    assert binary is not None
    os.environ["ALGENTA_RUNTIME_WORKER"] = binary
    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")

    resolved = worker.resolve_worker(module_name="stats", require_verified=False)
    assert resolved is not None, "no worker resolved"
    assert Path(resolved.path).resolve() == Path(binary).resolve(), (
        f"resolved {resolved.path} but expected {binary}; this test would be measuring a "
        "different runtime"
    )
    return MojoRuntime(mode="local")


def _worker_pids() -> list[int]:
    """PIDs of the live worker processes the SDK is holding.

    Reaching into `worker._SESSIONS` is deliberate. Calling `health()` after a hostile request is
    NOT a liveness test: the session layer transparently RESPAWNS a dead worker, so health reports
    `ok` on a brand-new process and the kill is invisible. Measured against the pre-fix binary — the
    four hostile calls all "passed" a health check while the serving pid had in fact vanished. Only
    process identity distinguishes "survived" from "died and was replaced", and being replaced is
    not survival: it takes every resident dataset and open cursor with it.
    """
    from algenta.native import worker

    return sorted(s._proc.pid for s in worker._SESSIONS.values() if s._proc is not None)


def _serving_pids(rt: MojoRuntime) -> list[int]:
    """Force a session to exist, then report its pid."""
    out = rt.execute("stats", "median", [FIVE, 5])
    assert out.get("result") == pytest.approx(3.0), (
        f"the warm-up call did not reach stats.median (got {out!r}); every assertion below would be "
        "vacuous, so this fails loudly instead. Is stats on this shard? See runtime-shards.json "
        "module_workers['stats']."
    )
    pids = _worker_pids()
    assert pids, "no worker process is held; the assertions below would be vacuous"
    return pids


def test_the_warmup_call_actually_reaches_the_kernel(runtime):
    """Guards against the whole module passing because the shard does not contain `stats`.

    The default worker does NOT own `stats` (it is on the shard named by
    `runtime-shards.json`'s `module_workers`), and against the default worker every hostile call
    returns `module_not_registered` without touching a kernel — so the kill assertions would pass
    while proving nothing.
    """
    assert _serving_pids(runtime)


@pytest.mark.parametrize(
    ("function", "args"),
    [
        ("sort_values", [FIVE, HOSTILE_N]),
        ("quantile", [FIVE, HOSTILE_N, 0.5]),
        ("percentile", [FIVE, HOSTILE_N, 50]),
        ("median", [FIVE, HOSTILE_N]),
    ],
)
def test_an_over_length_count_does_not_kill_the_worker(runtime, function, args):
    """THE REGRESSION. Each of these four killed the serving worker on `origin/main`.

    Asserted on process identity, not on a health check — see `_worker_pids`. Measured pre-fix:
    `pid before: [95227]` then `pid after: []`.
    """
    before = _serving_pids(runtime)
    try:
        runtime.execute("stats", function, args)
    except Exception:
        # A typed refusal is an acceptable outcome. Dying is not.
        pass
    after = _worker_pids()
    assert after == before, (
        f"stats.{function} with n={HOSTILE_N} over a {len(FIVE)}-element list ended the worker "
        f"process (pids {before} -> {after}); an uncatchable bounds abort is not something a caller "
        "can recover from, and the respawn that follows has lost every resident dataset"
    )


def test_a_clamped_count_answers_the_question_actually_asked(runtime):
    """Clamping is deliberate: refusing-as-empty would route through `quantile`'s empty case and
    return 0.0, converting a crash into a silent wrong answer for a caller who merely passed too
    large an `n`."""
    before = _serving_pids(runtime)
    out = runtime.execute("stats", "median", [FIVE, HOSTILE_N])
    assert _worker_pids() == before
    assert out["result"] == pytest.approx(3.0), (
        f"median over the 5 available values should be 3.0, got {out['result']!r}"
    )


def test_a_valid_count_is_unchanged(runtime):
    """The guard must be non-behavioural for every count that was already legal."""
    before = _serving_pids(runtime)
    for n, expected in ((5, 3.0), (1, 5.0)):
        out = runtime.execute("stats", "median", [FIVE, n])
        assert out["result"] == pytest.approx(expected), (n, out)
    assert _worker_pids() == before


def test_a_negative_and_a_zero_count_are_survivable(runtime):
    before = _serving_pids(runtime)
    for n in (-3, 0):
        try:
            runtime.execute("stats", "sort_values", [FIVE, n])
        except Exception:
            pass
        assert _worker_pids() == before, f"n={n} ended the worker process"


def test_an_empty_list_with_a_hostile_count_is_survivable(runtime):
    before = _serving_pids(runtime)
    try:
        runtime.execute("stats", "sort_values", [[], HOSTILE_N])
    except Exception:
        pass
    assert _worker_pids() == before
