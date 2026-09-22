"""Live checks for the Hub kernel loader and the native lane — real Hub, real compiled kernels.

Run with `ALGENTA_SPACES_LIVE=1 python3 -m pytest tests/spaces/integration -q -m slow`.
Needs `kernels`, `torch` and network (or a populated `HF_HOME`). When `HF_HOME`
is unset and the default cache directory cannot be written, the kernels are
fetched into a per-session temporary cache instead — nothing is faked.

What is proven here:

* `thyn-ai/algenta-stats` and `thyn-ai/algenta-text` load through `hubkernel.load`
  with the twenty-repo `TRUST`; the variant is the one built for this platform
  and the snapshot on disk is the capped v1 revision.
* `warm_up` runs each family's card example and the results are the published
  values (z-test of 50/1000 vs 65/1000; Levenshtein kitten/sitting = 3).
* `describe` lists `ab_testing.z_test_proportions` and
  `text.fuzzy.levenshtein_distance` with their parameters, and hides nothing
  a form should show.
* `ab_testing.z_test_proportions(50, 1000, 65, 1000)` through `Lane.submit`
  matches `statsmodels.stats.proportion.proportions_ztest` (or the normal
  survival function from `scipy.stats` when statsmodels is absent).
* ABI §9 wall-time proof: two heavy calls from two threads take the serialised
  sum, not the max — through the lane (one worker by construction) and
  straight against two families from two plain threads (the compiled cap).
"""

from __future__ import annotations

import math
import os
import platform
import random
import threading
import time
from pathlib import Path

import pytest
from algenta_spaces import hubkernel as hk
from algenta_spaces import lane

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("ALGENTA_SPACES_LIVE") != "1", reason="set ALGENTA_SPACES_LIVE=1"
    ),
]

Z_EXPECTED = [-1.440793230951582, 0.1496431923825119]
# The kernel's p-value differs from statsmodels by 8.6e-9 (its normal CDF), the z statistic by
# under 1e-12; the tolerances below state exactly that, so a card may claim "matches statsmodels
# to 1e-7" for the p-value and "to 1e-9" for z — nothing tighter.
Z_ABS_TOL = 1e-9
P_ABS_TOL = 1e-7
# fit_normal over 400k floats: about 0.7 s on Apple M-series, seconds on cpu-basic. Its argument
# is a 400k-element list, so JSON marshalling is a visible share: fine for the lane check (the
# lane serialises the whole call) but not for the §9 check, which needs native compute with
# negligible transport — the red-team gate calls the C ABI directly for the same reason.
HEAVY_N = 400_000
# bayesian_ab_test draws BAYES_SAMPLES Beta posteriors from five scalars: seconds of native
# compute behind a 60-byte request, so wall time measures the compiled cap and nothing else.
BAYES_SAMPLES = 1_500_000
LONG_A = "kitten" * 1000  # levenshtein 6,000 x 7,000: about 0.4 s of native compute, 13 KB of args
LONG_B = "sitting" * 1000
CAP_RATIO_MIN = 0.80  # the red-team gate's CAPPED threshold: wall / serialised sum


@pytest.fixture(scope="module")
def hf_home(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A writable kernel cache: the configured one, else a temporary one for this session."""
    pytest.importorskip("kernels")
    pytest.importorskip("torch")
    from huggingface_hub import constants

    if os.environ.get("HF_HOME"):
        return os.environ["HF_HOME"]
    cache = Path(constants.HF_HUB_CACHE)
    try:
        cache.mkdir(parents=True, exist_ok=True)
        probe = cache / ".algenta-write-probe"
        probe.write_text("ok")
        probe.unlink()
        return str(cache.parent)
    except OSError:
        # huggingface_hub froze HF_HUB_CACHE at import, so setting HF_HOME here would not take
        # effect; the run must be started with HF_HOME pointing at a writable directory.
        pytest.skip(
            f"default Hub cache {cache} is not writable; run with HF_HOME=<writable dir> "
            "ALGENTA_SPACES_LIVE=1"
        )


@pytest.fixture(scope="module")
def stats(hf_home: str) -> hk.LoadedKernel:
    return hk.load("stats")


@pytest.fixture(scope="module")
def text(hf_home: str) -> hk.LoadedKernel:
    return hk.load("text")


@pytest.fixture
def native_lane():
    ln = lane.Lane()
    yield ln
    ln.shutdown(wait=True)


def test_load_reports_variant_and_pinned_revision(stats: hk.LoadedKernel, text: hk.LoadedKernel):
    for loaded in (stats, text):
        assert loaded.variant.startswith("torch"), loaded.variant
        system = platform.system().lower()
        assert ("darwin" if system == "darwin" else "linux") in loaded.variant
        assert loaded.snapshot_sha == loaded.capped_v1_sha, "cache holds a non-capped revision"
        assert loaded.pinned is True
        assert loaded.load_s > 0
        assert hk.variant_of(loaded.kernel) == loaded.variant
    assert stats.repo_id == "thyn-ai/algenta-stats" and text.repo_id == "thyn-ai/algenta-text"
    assert stats.capped_v1_sha == hk.FROZEN_CAPPED_V1_SHAS["thyn-ai/algenta-stats"]
    note = hk.platform_note([stats, text])
    assert stats.variant in note and "algenta-stats@ac35ffe" in note
    assert "kernels " in note and "torch " in note


def test_warm_up_runs_the_card_examples(stats: hk.LoadedKernel, text: hk.LoadedKernel):
    z_call = hk.warm_up(stats)
    assert z_call.as_call() == "ab_testing.z_test_proportions(50, 1000, 65, 1000)"
    assert z_call.result == pytest.approx(Z_EXPECTED, rel=1e-12)
    assert stats.warm and stats.warmup_ms == z_call.elapsed_ms and stats.warmup_ms > 0
    lev_call = hk.warm_up(text)
    assert lev_call.as_call() == "text.fuzzy.levenshtein_distance('kitten', 'sitting')"
    assert lev_call.result == 3
    assert text.warm and text.warmup_ms is not None
    # warm again: the runtime is initialised, so the second call is well under the first
    again = hk.warm_up(stats)
    assert again.elapsed_ms < 100.0, again.elapsed_ms


def test_describe_lists_the_hero_functions_with_params(
    stats: hk.LoadedKernel, text: hk.LoadedKernel
):
    view = hk.describe(stats)
    fn = view["modules"]["ab_testing"]["functions"]["z_test_proportions"]
    assert [(p["name"], p["type"]) for p in fn["params"]] == [
        ("successes_a", "Int"),
        ("n_a", "Int"),
        ("successes_b", "Int"),
        ("n_b", "Int"),
    ]
    assert all(p["has_default"] is False for p in fn["params"])
    assert fn["return_type"] == "List[Float64]"
    assert view["function_count"] > 100
    assert (
        "ab_testing" in view["modules"]
        and view["modules"]["ab_testing"]["family"] == "algenta-stats"
    )

    text_view = hk.describe(text)
    lev = text_view["modules"]["text.fuzzy"]["functions"]["levenshtein_distance"]
    assert [(p["name"], p["type"]) for p in lev["params"]] == [("a", "String"), ("b", "String")]
    assert lev["return_type"] == "Int"
    assert text_view["excluded"] == []  # neither family ships an excluded function
    import json

    json.dumps(view)
    json.dumps(text_view)


def _reference_p_value(successes: list[int], totals: list[int]) -> tuple[float, float, str]:
    try:
        from statsmodels.stats.proportion import proportions_ztest
    except ImportError:
        norm = pytest.importorskip("scipy.stats").norm
        p1, p2 = successes[0] / totals[0], successes[1] / totals[1]
        pooled = sum(successes) / sum(totals)
        se = math.sqrt(pooled * (1 - pooled) * (1 / totals[0] + 1 / totals[1]))
        z = (p1 - p2) / se
        return z, 2 * norm.sf(abs(z)), "scipy.stats.norm.sf"
    z, p = proportions_ztest(successes, totals)
    return float(z), float(p), "statsmodels.stats.proportion.proportions_ztest"


def test_z_test_through_the_lane_matches_the_reference(
    stats: hk.LoadedKernel, native_lane: lane.Lane
):
    ticket = native_lane.submit(
        hk.execute,
        stats,
        "ab_testing",
        "z_test_proportions",
        [50, 1000, 65, 1000],
        budget_s=5.0,
        label="z_test_proportions",
    )
    assert ticket.position == 0 and ticket.eta_s == 0.0
    call = ticket.result()
    z, p = call.result
    ref_z, ref_p, source = _reference_p_value([50, 65], [1000, 1000])
    assert z == pytest.approx(ref_z, abs=Z_ABS_TOL), source
    assert p == pytest.approx(ref_p, abs=P_ABS_TOL), (source, p - ref_p)
    assert call.elapsed_ms < 5000.0
    assert ticket.state == lane.DONE and native_lane.stats()["completed"] == 1


def _heavy_stats_args() -> list:
    rng = random.Random(1)  # noqa: S311 - a fixed seed for a timing fixture, not security
    return [[rng.random() for _ in range(HEAVY_N)]]


def _timed(fn, *args) -> tuple[float, float, object]:
    t0 = time.perf_counter()
    out = fn(*args)
    return t0, time.perf_counter(), out


def test_two_heavy_calls_through_the_lane_do_not_overlap(
    stats: hk.LoadedKernel, native_lane: lane.Lane
):
    args = _heavy_stats_args()
    warm = hk.execute(stats, "distribution_fit", "fit_normal", args)
    single = hk.execute(stats, "distribution_fit", "fit_normal", args).elapsed_ms / 1e3
    assert warm.result == pytest.approx([0.5, 0.2887], abs=0.01), (
        "fit_normal over uniform(0, 1) is mean 0.5, sd 0.289"
    )
    assert single > 0.05, f"the heavy call took {single * 1e3:.0f} ms — too light to prove anything"

    t_wall0 = time.perf_counter()
    t1 = native_lane.submit(
        _timed, hk.execute, stats, "distribution_fit", "fit_normal", args, budget_s=60, label="a"
    )
    t2 = native_lane.submit(
        _timed, hk.execute, stats, "distribution_fit", "fit_normal", args, budget_s=60, label="b"
    )
    assert (t1.position, t2.position) == (0, 1)
    assert t2.eta_s == lane.DEFAULT_ESTIMATE_S  # one ahead, no samples yet: 1 x initial estimate
    start_a, end_a, _ = t1.result()
    start_b, end_b, _ = t2.result()
    wall = time.perf_counter() - t_wall0
    assert start_b >= end_a, "the second call started before the first ended"
    serial = 2 * single
    ratio = wall / serial
    assert ratio >= CAP_RATIO_MIN, (
        f"wall {wall:.2f} s vs serialised {serial:.2f} s (ratio {ratio:.2f})"
    )
    assert native_lane.stats()["completed"] == 2 and native_lane.depth() == 0


def test_abi_9_two_families_from_two_threads_serialise(
    stats: hk.LoadedKernel, text: hk.LoadedKernel
):
    """The compiled cap, not the lane: two plain threads, two libraries, wall ≈ sum.

    Each thread calls a different family (two library instances, red-team
    scenario (c)); nothing in Python serialises them — the Hub wrapper's lock is
    per library — so only ABI §9 can keep them from overlapping.
    """
    stats_args = [50, 1000, 65, 1000, BAYES_SAMPLES]
    text_args = [LONG_A, LONG_B]
    bayes = ("bayesian", "bayesian_ab_test")
    lev = ("text.fuzzy", "levenshtein_distance")
    warm = hk.execute(stats, *bayes, stats_args)
    assert 0.6 < warm.result < 0.85, warm.result  # P(B > A) for 65/1000 vs 50/1000
    hk.execute(text, *lev, text_args)
    single_s = hk.execute(stats, *bayes, stats_args).elapsed_ms / 1e3
    single_t = hk.execute(text, *lev, text_args).elapsed_ms / 1e3
    assert single_s > 0.2 and single_t > 0.05, (single_s, single_t)

    results: dict[str, tuple[float, float, object]] = {}

    def run(name: str, loaded: hk.LoadedKernel, module: str, function: str, args: list) -> None:
        results[name] = _timed(hk.execute, loaded, module, function, args)

    threads = [
        threading.Thread(target=run, args=("stats", stats, *bayes, stats_args)),
        threading.Thread(target=run, args=("text", text, *lev, text_args)),
    ]
    t0 = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    wall = time.perf_counter() - t0
    assert set(results) == {"stats", "text"}
    assert results["text"][2].result == 3000
    serial = single_s + single_t
    ratio = wall / serial
    effective_workers = serial / wall
    assert ratio >= CAP_RATIO_MIN, (
        f"wall {wall:.2f} s vs serialised {serial:.2f} s: {effective_workers:.2f} effective workers"
    )
    assert effective_workers <= 1.0 / CAP_RATIO_MIN
    # The queue-then-run signature, whichever thread took the slot first: the second caller's
    # window ends at least its own (warm, single) duration after the holder's window ends,
    # because it waited inside the library and only then computed. Window OVERLAP is not
    # asserted — the waiter's window covers the holder's, which is exactly the misreading the
    # red-team gate rejects (ABI 9.7).
    singles = {"stats": single_s, "text": single_t}
    first, second = sorted(results, key=lambda name: results[name][0])
    holder_end = results[first][1]
    waiter_end = results[second][1]
    assert waiter_end >= holder_end + CAP_RATIO_MIN * singles[second], (
        f"{second} finished {waiter_end - holder_end:.2f} s after {first}; "
        f"its own call takes {singles[second]:.2f} s"
    )
