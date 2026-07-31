"""A caller-supplied INDEX must not be able to kill the worker, and a count bound cannot stop it.

`tests/integration/test_kernel_count_arg_robustness.py` covers the COUNT hazard: `n` larger than
the list it measures. This module covers the neighbouring class that a count relation provably
cannot catch -- a parameter that is a direct SUBSCRIPT rather than a length.

The two are not the same shape, and conflating them is what left this open:

* A negative COUNT is harmless. `for i in range(-3)` runs zero times and reads nothing.
* A negative INDEX is fatal. Mojo does not normalise it: `a[-1]` on a 5-element List is
  `Assert Error: index -1 is out of bounds, valid range is 0 to 4` and the process ends.

MEASURED on `origin/main` (2026-07-31), on the compiled shard that actually owns `stats`
(`runtime-shards.json` maps `stats` -> `algenta-runtime-worker-018`), reading the serving pid
before and after each call:

    pctile([], 0, 50)        -> pid gone
    ins_sort(five, -1, 4)    -> pid gone
    ins_sort(five, 0, 99)    -> pid gone
    part3(five, -1, 4)       -> pid gone
    part3(five, 0, 99)       -> pid gone
    part3([], 0, 0)          -> pid gone

`pctile` is the one worth reading twice. It HAS a declared `n <= len(v)` relation and the guard
does refuse `pctile([], 1, 50)`. But `pctile([], 0, 50)` SATISFIES that relation -- `0 <= 0` -- and
still died, because the kernel's index is clamped to `>= 0` and so reads `v[0]` whatever `n` is.
A declared count bound is therefore not sufficient on its own, and an `[enforced]` relation that
passes is not evidence the call is safe.

`part3` carries a third requirement that is neither a count nor a range: it reads `a[hi-1]` and
relies on the pivot sitting there as a SENTINEL so the inner `while a[i] < piv` walk terminates.
With `hi < lo + 2` there is no room for the sentinel and the walk runs off the end.

**And `ins_sort` / `part3` already DECLARED the bound they did not check.** #429 gave both

    - lo + 1 <= len(a) [kernel_validated]
    - hi + 1 <= len(a) [kernel_validated]

`[kernel_validated]` is the tag that tells the guard to stand down because the kernel checks the
bound itself. No such check existed, so the guard stood down as instructed and the kernel read
`a[-1]`. That is the capability gate's own vocabulary being used to wave through the exact hazard
it was built to stop — worse than an undeclared function, which at least claims nothing.

`[kernel_validated]` is nonetheless the RIGHT tag for these two, which is why this fix is in the
kernel rather than in the declaration: `[enforced]` would refuse `ins_sort(a, 100, 0)`, and that
is a legal no-op today because `range(lo + 1, hi + 1)` is empty whenever `lo >= hi`.

All three functions are published contract exports reachable over the wire today, and all three
take `mut` lists, so the abort also loses whatever the caller was mutating.
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
    """The shard that owns `stats`, not merely any worker.

    Against the DEFAULT worker every call below returns `module_not_registered` without reaching a
    kernel, so the assertions would all pass while proving nothing. That is not hypothetical --
    it is how a first run of this probe came back green against unpatched code.
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
        if name:
            candidate = _SHARD_DIR / name
            if candidate.is_file():
                return str(candidate)
    return None


pytestmark = pytest.mark.skipif(
    _binary() is None,
    reason=(
        "no compiled shard owning `stats`; build with "
        "scripts/build_runtime_shards.py --shard-size 24"
    ),
)

FIVE = [5.0, 4.0, 3.0, 2.0, 1.0]
SORTED_FIVE = [1.0, 2.0, 3.0, 4.0, 5.0]


@pytest.fixture(scope="module")
def runtime():
    from algenta.native import worker

    binary = _binary()
    assert binary is not None
    os.environ["ALGENTA_RUNTIME_WORKER"] = binary
    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    resolved = worker.resolve_worker(module_name="stats", require_verified=False)
    assert resolved is not None, "no worker resolved"
    assert Path(resolved.path).resolve() == Path(binary).resolve(), (
        f"resolved {resolved.path}, expected {binary}; these assertions would measure a "
        "different runtime"
    )
    return MojoRuntime(mode="local")


def _pids() -> list[int]:
    """PIDs of the worker processes the SDK holds.

    `health()` is NOT a liveness test here: the session layer transparently respawns a dead
    worker, so health reports `ok` on a brand-new process and the kill is invisible. Only process
    identity separates "survived" from "died and was replaced", and being replaced is not
    surviving -- it takes every resident dataset and open cursor with it.
    """
    from algenta.native import worker

    return sorted(s._proc.pid for s in worker._SESSIONS.values() if s._proc is not None)


def _serving(rt: MojoRuntime) -> list[int]:
    out = rt.execute("stats", "median", [FIVE, 5])
    assert out.get("result") == pytest.approx(3.0), (
        f"the warm-up did not reach stats.median (got {out!r}); every assertion below would be "
        "vacuous. Is this the shard that owns `stats`?"
    )
    pids = _pids()
    assert pids, "no worker process held; the assertions below would be vacuous"
    return pids


def test_the_warmup_reaches_the_kernel(runtime):
    assert _serving(runtime)


@pytest.mark.parametrize(
    ("function", "args", "why"),
    [
        ("pctile", [[], 0, 50], "index clamped to >=0 reads v[0] of an EMPTY list"),
        ("ins_sort", [FIVE, -1, 4], "negative lo is a direct subscript"),
        ("ins_sort", [FIVE, 0, 99], "hi past the end"),
        ("part3", [FIVE, -1, 4], "negative lo"),
        ("part3", [FIVE, 0, 99], "hi past the end"),
        ("part3", [[], 0, 0], "empty list, and no room for the a[hi-1] sentinel"),
    ],
)
def test_a_hostile_index_does_not_kill_the_worker(runtime, function, args, why):
    """THE REGRESSION. Each of these six ended the serving pid on `origin/main`."""
    before = _serving(runtime)
    try:
        runtime.execute("stats", function, args)
    except Exception:
        pass  # a typed refusal is fine; dying is not
    after = _pids()
    assert after == before, (
        f"stats.{function}{args} ended the worker process (pids {before} -> {after}): {why}. "
        "An uncatchable bounds abort is not something a caller can recover from, and the respawn "
        "has lost every resident dataset."
    )


def test_a_satisfied_count_relation_is_not_evidence_of_safety(runtime):
    """`pctile([], 0, 50)` satisfies `n <= len(v)` (0 <= 0) and still died.

    Pinned separately from the parametrised case because it is the reason the count guard alone
    is not enough: a relation that PASSES tells you nothing about a subscript the kernel forms
    from something other than that count.
    """
    before = _serving(runtime)
    refused = runtime.execute("stats", "pctile", [[], 1, 50])
    assert refused.get("success") is False, "n=1 over an empty list should be refused by the guard"
    assert _pids() == before

    allowed = runtime.execute("stats", "pctile", [[], 0, 50])
    assert _pids() == before, "n=0 passes the declared relation and must still not kill the worker"
    assert allowed.get("result") == pytest.approx(0.0), (
        "an empty percentile answers 0.0, matching what `quantile` already returns for an empty "
        f"input rather than inventing a second spelling; got {allowed.get('result')!r}"
    )


@pytest.mark.parametrize(
    ("function", "args", "expected_result", "expected_list"),
    [
        ("ins_sort", [FIVE, 0, 4], None, SORTED_FIVE),
        ("part3", [FIVE, 0, 4], 2, None),
    ],
)
def test_a_legal_range_is_unchanged(runtime, function, args, expected_result, expected_list):
    """The guards must be non-behavioural for every range that was already legal.

    Asserted on the SORTED OUTPUT, not just on survival: a guard that returned early on a valid
    range would leave the list untouched and still "pass" a liveness check, which would be a
    silent wrong answer of exactly the kind this class of fix must not introduce.
    """
    before = _serving(runtime)
    out = runtime.execute("stats", function, list(args))
    assert _pids() == before
    payload = out.get("result")
    assert isinstance(payload, dict), f"expected a mutated-args payload, got {payload!r}"
    if expected_result is not None:
        assert payload.get("result") == expected_result, payload
    if expected_list is not None:
        assert payload["mutated_args"]["a"] == pytest.approx(expected_list), payload


def test_a_kernel_validated_relation_means_the_kernel_really_does_validate(runtime):
    """`[kernel_validated]` is a claim about the KERNEL, and it was false.

    `stats.part3` and `stats.ins_sort` declare

        - lo + 1 <= len(a) [kernel_validated]
        - hi + 1 <= len(a) [kernel_validated]

    `[kernel_validated]` tells the guard to stand down, because the kernel checks the bound
    itself and answers with a typed value. That is the correct tag for these two -- the alternative,
    `[enforced]`, would refuse `ins_sort(a, 100, 0)`, which is a legal no-op today, since
    `range(lo + 1, hi + 1)` is empty whenever `lo >= hi`.

    But no such check existed. The guard stood down as instructed and the kernel then read
    `a[-1]`, so the declaration was an assurance with nothing behind it -- the precise failure the
    capability gate exists to prevent, arriving through the gate's own vocabulary.

    So this asserts the claim rather than the absence of a crash: for each declared bound, the
    violating call comes back with the kernel's own answer AND the process survives. A test that
    only checked survival would also pass if someone re-tagged these `[enforced]`, which would
    silently break the legal no-op.
    """
    import re

    engine = _REPO_ROOT / "mojo" / "engine" / "stats.mojo"
    source = engine.read_text(encoding="utf-8")
    for name in ("part3", "ins_sort"):
        block = re.search(rf"@capability {name}\b(.*?)@endcapability", source, re.S)
        assert block is not None, f"{name} lost its capability block; this test is now vacuous"
        body = block.group(1)
        for bound in ("lo + 1 <= len(a)", "hi + 1 <= len(a)"):
            assert f"- {bound} [kernel_validated]" in body, (
                f"{name} no longer declares `{bound} [kernel_validated]`. If it moved to "
                "[enforced], the guard now refuses before dispatch and `ins_sort(a, 100, 0)` "
                "stops being the legal no-op it has always been."
            )

    before = _serving(runtime)
    # Each of these violates a declared, kernel-validated bound.
    assert runtime.execute("stats", "part3", [FIVE, -1, 4])["result"]["result"] == -1
    assert runtime.execute("stats", "part3", [FIVE, 0, 99])["result"]["result"] == -1
    assert _pids() == before, "part3 must validate its own declared bound, not abort on it"

    # ins_sort has no status channel, so its validation shows up as "the list is untouched".
    out = runtime.execute("stats", "ins_sort", [FIVE, -1, 4])
    assert out["result"]["mutated_args"]["a"] == pytest.approx(FIVE), (
        "a refused range must leave the list alone rather than half-sorting it"
    )
    assert _pids() == before

    # ...and the legal no-op the [kernel_validated] tag protects is still a no-op, not a refusal.
    noop = runtime.execute("stats", "ins_sort", [FIVE, 100, 0])
    assert noop.get("success") is True, (
        f"ins_sort(a, 100, 0) is a legal no-op and must not be refused; got {noop!r}"
    )
    assert noop["result"]["mutated_args"]["a"] == pytest.approx(FIVE)
    assert _pids() == before


def test_fast_sort_still_sorts_through_both_guarded_helpers(runtime):
    """`fast_sort` calls BOTH guarded helpers internally, so this is the caller-side proof.

    It takes the `ins_sort` path for n <= 16 and the `part3` path above it, and pushes `p-1` /
    `p+1` onto its stack -- which can be `lo-1` or `hi+1`. If either guard fired on a range
    `fast_sort` considers valid, the result would come back unsorted rather than crashing, so
    survival alone would not catch it. Sizes straddle the n<=16 threshold deliberately.
    """
    before = _serving(runtime)
    for n in (1, 2, 5, 16, 17, 40):
        values = [float((n * 7 + i * 13) % n) for i in range(n)] if n > 1 else [1.0]
        out = runtime.execute("stats", "fast_sort", [values, n])
        assert _pids() == before, f"fast_sort(n={n}) ended the worker"
        got = out["result"]["mutated_args"]["a"]
        assert got == pytest.approx(sorted(values)), (
            f"fast_sort(n={n}) returned {got}, expected {sorted(values)} — a guard fired on a "
            "range fast_sort considers valid, which loses the sort instead of crashing"
        )
