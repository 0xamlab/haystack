"""algenta_spaces.bench — rulebook v0.4 with deterministic fake lanes and an injectable clock."""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest
from algenta_spaces import bench


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeLane:
    """A callable that costs a scripted duration per call on the fake clock and logs its calls."""

    def __init__(self, clock: FakeClock, name: str, durations_ms: list[float], log: list[str]):
        self.clock, self.name, self.durations, self.log = clock, name, durations_ms, log
        self.calls = 0

    def __call__(self) -> str:
        dt = self.durations[self.calls % len(self.durations)]
        self.calls += 1
        self.clock.advance(dt / 1e3)
        self.log.append(self.name)
        return f"answer-{self.name}"


def _gate_ok(outputs: dict) -> tuple[bool, str]:
    assert set(outputs) == {"ours", "theirs"}
    return True, "exact match"


def _lanes(clock, log, ours_ms, theirs_ms):
    return [
        bench.LaneSpec("theirs", bench.SIDE_INCUMBENT, FakeLane(clock, "theirs", theirs_ms, log)),
        bench.LaneSpec("ours", bench.SIDE_ALGENTA, FakeLane(clock, "ours", ours_ms, log)),
    ]


def test_statistics_helpers():
    samples = list(range(1, 22))  # 1..21
    assert bench.p95(samples) == 20  # nearest rank: ceil(0.95*21)=20 -> 20th value
    assert bench.p95([5, 1, 9]) == 9  # below 20 samples: the max
    assert bench.mad([1, 2, 3, 4, 100]) == 1
    assert bench.cv([10, 10, 10]) == 0.0
    assert bench.cv([1, 3]) == pytest.approx(statistics.stdev([1, 3]) / 2)
    assert bench.cv([7]) == 0.0
    with pytest.raises(ValueError):
        bench.p95([])
    assert bench.auto_repeats(249.9) == 21
    assert bench.auto_repeats(250.0) == 11


def test_calls_per_sample_makes_every_sample_last_ten_milliseconds():
    """v0.4: k = ceil(10 ms / warm call), 1 at or over the floor, capped, off when the floor is 0.
    The floor is the measured one (the sweep in `bench`'s docstring), not the 2 ms first tried."""
    assert bench.SAMPLE_MIN_MS == 10.0 and bench.CALLS_MAX == 200
    assert bench.calls_per_sample(0.09) == 112  # the deployed hero: 112 × 0.09 = 10.08 ms
    assert bench.calls_per_sample(0.1385) == 73  # the build Mac's hero under load
    assert bench.calls_per_sample(0.6) == 17
    assert bench.calls_per_sample(2.5) == 4  # Levenshtein M on the build Mac
    assert bench.calls_per_sample(5.0) == 2
    assert bench.calls_per_sample(9.99) == 2
    assert bench.calls_per_sample(10.0) == 1 and bench.calls_per_sample(24.3) == 1
    assert bench.calls_per_sample(120.0) == 1
    assert bench.calls_per_sample(0.001) == 200 and bench.calls_per_sample(0.0) == 200
    assert bench.calls_per_sample(0.05) == 200 and bench.calls_per_sample(0.051) == 197
    assert bench.calls_per_sample(0.0005, cap=50) == 50
    assert bench.calls_per_sample(0.09, sample_min_ms=0) == 1  # the v0.3 protocol
    assert bench.calls_per_sample(0.5, sample_min_ms=2.0) == 4
    assert bench.calls_per_sample(1.0, sample_min_ms=2.0) == 2
    with pytest.raises(ValueError):
        bench.calls_per_sample(0.5, cap=0)
    with pytest.raises(ValueError):
        bench.summarise(bench.LaneSpec("a", bench.SIDE_ALGENTA, lambda: 1), [1.0], k=0)


def test_run_cell_measured_statistics_ratio_direction_and_order():
    clock, log = FakeClock(), []
    # every call is over the 10 ms floor, so each sample is one call (k = 1), as v0.3 timed it
    ours = [20.0, 22.0, 18.0, 20.0, 21.0]
    theirs = [60.0, 66.0, 54.0, 60.0, 63.0]
    lanes = _lanes(clock, log, ours, theirs)
    said = []
    cell = bench.run_cell(
        lanes,
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 1.0,
        quota=8,
        seed=7,
        progress=said.append,
    )
    assert cell.status == bench.STATUS_MEASURED and cell.measured
    assert cell.n == 21  # warm call under 250 ms
    assert cell.warmups == 2
    assert cell.seed == 7 and cell.cpu_quota == 8 and cell.load_1m == 1.0
    assert cell.rulebook == bench.RULEBOOK_VERSION == "0.6"
    # order: gate (theirs, ours), 2 interleaved warm-ups, 21 interleaved rounds
    assert log[:2] == ["theirs", "ours"]
    assert log[2:6] == ["theirs", "ours"] * 2
    assert log[6:] == ["theirs", "ours"] * 21
    assert len(log) == 2 + 4 + 42
    lane_ours, lane_theirs = cell.lane(bench.SIDE_ALGENTA), cell.lane(bench.SIDE_INCUMBENT)
    assert lane_ours.n == lane_theirs.n == 21
    assert lane_ours.k == lane_theirs.k == 1 and cell.k == 1
    assert lane_ours.sample_ms == pytest.approx(20.0)
    assert lane_ours.median_ms == pytest.approx(20.0)
    assert lane_theirs.median_ms == pytest.approx(60.0)
    assert lane_ours.min_ms == pytest.approx(18.0) and lane_ours.max_ms == pytest.approx(22.0)
    assert lane_ours.p95_ms == pytest.approx(22.0)
    assert lane_ours.mad_ms == pytest.approx(1.0)  # 9 of 21 samples sit on the median
    assert lane_ours.cv == pytest.approx(bench.cv(lane_ours.samples_ms))
    assert lane_ours.stable and lane_theirs.stable
    # ratio = best incumbent / algenta, so a faster algenta lane gives a ratio above 1
    assert cell.ratio == pytest.approx(3.0)
    assert cell.parity_label == "exact match"
    assert cell.elapsed_s > 0 and cell.ts_utc.endswith(" UTC")
    assert said[0] == "checking theirs" and said[-1] == "measured"
    assert "timing 21 interleaved runs" in said


def test_run_cell_ratio_below_one_when_incumbent_is_faster():
    clock, log = FakeClock(), []
    cell = bench.run_cell(
        _lanes(clock, log, [40.0], [20.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=2,
    )
    assert cell.measured
    assert cell.ratio == pytest.approx(0.5)


def test_run_cell_without_interleave_runs_each_lane_in_a_block():
    clock, log = FakeClock(), []
    cell = bench.run_cell(
        _lanes(clock, log, [1.0], [2.0]),
        correctness_gate=_gate_ok,
        interleave=False,
        repeats=5,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=2,
    )
    assert cell.n == 5
    # ours is a 1 ms call: ten calls per sample (k = 10) so each sample lasts 10 ms; theirs is
    # a 2 ms call, five per sample
    assert cell.lane(bench.SIDE_ALGENTA).k == 10 and cell.lane(bench.SIDE_INCUMBENT).k == 5
    assert cell.k is None, "lanes that batched differently share no single k"
    assert (
        log
        == ["theirs", "ours"]
        + ["theirs", "theirs", "ours", "ours"]
        + ["theirs"] * 25
        + ["ours"] * 50
    )
    assert cell.lane(bench.SIDE_ALGENTA).median_ms == pytest.approx(1.0), "per-call figures"
    assert cell.lane(bench.SIDE_ALGENTA).sample_ms == pytest.approx(10.0)
    assert cell.lane(bench.SIDE_INCUMBENT).sample_ms == pytest.approx(10.0)
    assert cell.ratio == pytest.approx(2.0)
    # the v0.3 protocol on request: one call per sample whatever the cost
    plain = bench.run_cell(
        _lanes(clock, [], [1.0], [2.0]),
        correctness_gate=_gate_ok,
        interleave=False,
        repeats=5,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=2,
        sample_min_ms=0,
    )
    assert plain.lane(bench.SIDE_ALGENTA).k == 1 and plain.k == 1


def test_run_cell_batches_a_sub_millisecond_call_into_samples_of_k_calls():
    """v0.4: the deployed hero (0.09 ms) is timed as 21 samples of 112 back-to-back calls; the
    statistics are per call, the progress line and the cell say k."""
    clock, log = FakeClock(), []
    said = []
    ours_only = [
        bench.LaneSpec("ours", bench.SIDE_ALGENTA, FakeLane(clock, "ours", [0.09], log)),
    ]
    cell = bench.run_cell(
        ours_only,
        correctness_gate=lambda o: (True, "ran"),
        clock=clock,
        loadavg=lambda: 0.0,
        quota=8,
        progress=said.append,
    )
    assert cell.measured and cell.n == 21
    lane = cell.lane(bench.SIDE_ALGENTA)
    assert lane.k == 112 and cell.k == 112
    assert len(log) == 1 + 2 + 21 * 112, "gate, two warm-ups, then 21 samples of 112 calls"
    assert lane.median_ms == pytest.approx(0.09) and lane.sample_ms == pytest.approx(10.08)
    assert lane.min_ms == pytest.approx(0.09) and lane.max_ms == pytest.approx(0.09)
    assert len(lane.samples_ms) == 21
    assert "timing 21 interleaved runs × 112 calls" in said
    # lanes at different speeds: the progress line names both, fastest first
    mixed_said = []
    mixed = bench.run_cell(
        _lanes(clock, [], [0.5], [30.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=8,
        progress=mixed_said.append,
    )
    assert mixed.lane(bench.SIDE_ALGENTA).k == 20 and mixed.lane(bench.SIDE_INCUMBENT).k == 1
    assert "timing 21 interleaved runs × 20/1 calls" in mixed_said
    assert mixed.ratio == pytest.approx(60.0), "the ratio is per call, as before"
    # the cap holds for a warm-up that clocked at nearly nothing
    tiny = bench.run_cell(
        [bench.LaneSpec("t", bench.SIDE_ALGENTA, FakeLane(clock, "t", [0.001], []))],
        correctness_gate=lambda o: (True, ""),
        clock=clock,
        loadavg=lambda: 0.0,
        quota=8,
    )
    assert tiny.lane(bench.SIDE_ALGENTA).k == bench.CALLS_MAX


def test_batching_removes_timer_jitter_that_fails_the_gate_one_call_at_a_time():
    """The mechanism: a 0.1 ms call whose single-call timings alternate 0.05 / 0.15 ms (timer
    and scheduler jitter of the size the deployed host shows) fails CV ≤ 15 % one call at a
    time and passes it batched — the same calls, the same medians, the jitter averaged out."""
    clock = FakeClock()
    jitter = [0.05, 0.15]
    lanes = [bench.LaneSpec("j", bench.SIDE_ALGENTA, FakeLane(clock, "j", jitter, []))]
    one_call = bench.run_cell(
        lanes,
        correctness_gate=lambda o: (True, ""),
        clock=clock,
        loadavg=lambda: 0.0,
        quota=8,
        sample_min_ms=0,
    )
    assert one_call.status == bench.STATUS_NOISY and "spread above 15 percent" in one_call.reason
    assert one_call.lane(bench.SIDE_ALGENTA).cv > 0.4
    lanes = [bench.LaneSpec("j", bench.SIDE_ALGENTA, FakeLane(clock, "j", jitter, []))]
    batched = bench.run_cell(
        lanes, correctness_gate=lambda o: (True, ""), clock=clock, loadavg=lambda: 0.0, quota=8
    )
    lane = batched.lane(bench.SIDE_ALGENTA)
    assert batched.measured and lane.k == 200  # the fastest warm-up (0.05 ms) sets k: the cap
    assert lane.cv == pytest.approx(0.0) and lane.median_ms == pytest.approx(0.1)
    assert lane.median_ms == pytest.approx(statistics.fmean(jitter)), "the same mean cost"


def test_run_cell_slow_warm_call_picks_eleven_repeats():
    clock, log = FakeClock(), []
    cell = bench.run_cell(
        _lanes(clock, log, [300.0], [400.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=2,
        budget_s=600,
    )
    assert cell.n == 11
    assert cell.lane(bench.SIDE_ALGENTA).p95_ms == cell.lane(bench.SIDE_ALGENTA).max_ms


def test_run_cell_noisy_on_high_cv_is_not_recorded():
    clock, log = FakeClock(), []
    # ours alternates 50 / 250 ms: CV far above 0.15 (every call is over the 10 ms floor, so
    # nothing is batched — batching alternating sub-floor calls is exactly what evens them out,
    # see test_batching_removes_timer_jitter…)
    cell = bench.run_cell(
        _lanes(clock, log, [50.0, 250.0], [300.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=2,
    )
    assert cell.status == bench.STATUS_NOISY
    assert cell.reason.startswith("noisy — not recorded")
    assert "spread above 15 percent on ours" in cell.reason
    assert cell.ratio is None
    assert not cell.lane(bench.SIDE_ALGENTA).stable


def test_run_cell_records_the_load_average_and_never_gates_on_it():
    """v0.6: inside a Space the load average is the host's; a stable cell records whatever it
    reads, and the figure rides on the result for the card's foot (the deployed Space refused
    stable measurements at `load 14.1 on 8 vCPU` under v0.5)."""
    clock, log = FakeClock(), []
    cell = bench.run_cell(
        _lanes(clock, log, [10.0], [30.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 14.1,
        quota=2,
    )
    assert cell.status == bench.STATUS_MEASURED and cell.measured
    assert cell.load_1m == 14.1 and cell.cpu_quota == 2
    assert "load" not in (cell.reason or "")
    assert not hasattr(bench, "LOAD_FACTOR"), "the load gate is gone, not just loosened"


def test_run_cell_gate_failure_holds_without_timing():
    clock, log = FakeClock(), []

    def gate(outputs):
        return False, "differs at index 3"

    cell = bench.run_cell(
        _lanes(clock, log, [1.0], [2.0]), correctness_gate=gate, clock=clock, quota=2
    )
    assert cell.status == bench.STATUS_GATE_FAILED
    assert cell.reason == "differs at index 3"
    assert log == ["theirs", "ours"]  # only the gate calls
    assert cell.lanes == [] and cell.ratio is None


def test_run_cell_over_budget_is_not_measurable_here():
    clock, log = FakeClock(), []
    cell = bench.run_cell(
        _lanes(clock, log, [4000.0], [4000.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 0.0,
        quota=2,
        budget_s=60.0,
    )
    assert cell.status == bench.STATUS_OVER_BUDGET
    assert cell.reason == "not measurable here — over 60 s"
    assert cell.lanes == []
    assert cell.elapsed_s > 60.0
    # gate 8 s + warm-ups 16 s = 24 s, then repeats until the budget trips
    assert len(log) < 2 + 4 + 22


def test_run_cell_lane_exception_is_an_error_status_not_a_traceback():
    clock = FakeClock()

    def boom():
        raise RuntimeError("kernel not loaded")

    lanes = [
        bench.LaneSpec("ours", bench.SIDE_ALGENTA, boom),
        bench.LaneSpec("theirs", bench.SIDE_INCUMBENT, lambda: 1),
    ]
    said = []
    cell = bench.run_cell(
        lanes, correctness_gate=_gate_ok, clock=clock, quota=2, progress=said.append
    )
    assert cell.status == bench.STATUS_ERROR
    assert cell.reason == "RuntimeError: kernel not loaded"
    assert said[-1] == cell.reason


def test_run_cell_and_lane_spec_validation():
    clock = FakeClock()
    with pytest.raises(ValueError):
        bench.run_cell([], correctness_gate=_gate_ok, clock=clock, quota=1)
    with pytest.raises(ValueError):
        bench.LaneSpec("x", "referee", lambda: 1)
    with pytest.raises(ValueError):
        bench.LaneSpec(" ", bench.SIDE_ALGENTA, lambda: 1)
    incumbents_only = [bench.LaneSpec("a", bench.SIDE_INCUMBENT, lambda: 1)]
    with pytest.raises(ValueError):
        bench.run_cell(incumbents_only, correctness_gate=_gate_ok, clock=clock, quota=1)
    dupes = [
        bench.LaneSpec("a", bench.SIDE_ALGENTA, lambda: 1),
        bench.LaneSpec("a", bench.SIDE_INCUMBENT, lambda: 1),
    ]
    with pytest.raises(ValueError):
        bench.run_cell(dupes, correctness_gate=_gate_ok, clock=clock, quota=1)
    ours_only = [bench.LaneSpec("ours", bench.SIDE_ALGENTA, FakeLane(clock, "ours", [2.0], []))]
    cell = bench.run_cell(
        ours_only,
        correctness_gate=lambda o: (True, "ran"),
        clock=clock,
        repeats=3,
        loadavg=lambda: 0.0,
        quota=1,
    )
    assert cell.measured and cell.ratio is None  # parity-only cells have no incumbent
    assert cell.lane(bench.SIDE_ALGENTA).median_ms == pytest.approx(2.0)
    with pytest.raises(ValueError):
        bench.ratio_of([])


def test_ratio_of_uses_the_best_incumbent():
    ours = bench.LaneResult("o", bench.SIDE_ALGENTA, 21, 10.0, 11.0, 0.5, 0.05, 9.0, 12.0)
    slow = bench.LaneResult("s", bench.SIDE_INCUMBENT, 21, 90.0, 99.0, 1.0, 0.05, 80.0, 100.0)
    fast = bench.LaneResult("f", bench.SIDE_INCUMBENT, 21, 30.0, 33.0, 1.0, 0.05, 27.0, 34.0)
    assert bench.ratio_of([slow, ours, fast]) == pytest.approx(3.0)
    assert bench.ratio_of([ours]) is None
    cell = bench.CellResult(status=bench.STATUS_MEASURED, lanes=[slow, fast, ours])
    assert cell.lane(bench.SIDE_INCUMBENT) is fast
    assert cell.lane("nobody") is None


def test_hardware_footer_reads_cgroup_quota_cpuinfo_and_space_hardware(tmp_path: Path):
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("processor\t: 0\nmodel name\t: AMD EPYC 7R13 Processor\nflags\t: avx2\n")
    cpu_max = tmp_path / "cpu.max"
    cpu_max.write_text("800000 100000\n")
    env = {
        "SPACE_ID": "thyn-ai/algenta",
        "SPACE_HARDWARE": "cpu-upgrade",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    footer = bench.hardware_footer(
        env, packages=["pytest", "no-such-dist-xyz"], cpuinfo=cpuinfo, cpu_max=cpu_max
    )
    assert footer.startswith(
        "Space thyn-ai/algenta · cpu-upgrade · AMD EPYC 7R13 Processor · 8 vCPU · "
    )
    # the final review: `OMP=8` is an env-style token on the primary card; the value stays real
    assert " · threads 1 · " in footer and "OMP=" not in footer and "OPENBLAS" not in footer
    assert "pytest==" in footer and "no-such-dist-xyz not installed" in footer
    assert footer.endswith(f"rulebook v{bench.RULEBOOK_VERSION}")
    assert "cpu-basic" not in footer and "cgroup" not in footer
    deployed = bench.hardware_footer(
        {"SPACE_ID": "thyn-ai/algenta-staging", "OMP_NUM_THREADS": "8"},
        cpuinfo=cpuinfo,
        cpu_max=cpu_max,
    )
    assert "Space thyn-ai/algenta-staging" in deployed, "the Space id stays as provenance"
    assert f" · threads 8 · rulebook v{bench.RULEBOOK_VERSION}" in deployed
    local = bench.hardware_footer({}, cpuinfo=cpuinfo, cpu_max=cpu_max)
    assert local.startswith("local run · AMD EPYC")


def test_cpu_quota_fallbacks(tmp_path: Path):
    unlimited = tmp_path / "cpu.max"
    unlimited.write_text("max 100000\n")
    quota_v1 = tmp_path / "quota"
    period_v1 = tmp_path / "period"
    quota_v1.write_text("200000\n")
    period_v1.write_text("100000\n")
    assert bench.cpu_quota(unlimited, quota_v1, period_v1) == 2
    quota_v1.write_text("-1\n")
    assert bench.cpu_quota(unlimited, quota_v1, period_v1, fallback=3) == 3
    assert bench.cpu_quota(tmp_path / "none", tmp_path / "none", tmp_path / "none") >= 1
    fractional = tmp_path / "frac"
    fractional.write_text("50000 100000\n")
    assert bench.cpu_quota(fractional) == 1


def test_cpu_model_falls_back_without_proc(tmp_path: Path):
    model = bench.cpu_model(tmp_path / "missing")
    assert isinstance(model, str) and model


def test_load_and_thread_env():
    assert bench.load_1m() >= 0.0
    assert bench.thread_env({}) == ""
    assert bench.thread_env({"MKL_NUM_THREADS": "2"}) == "threads 2"
    assert bench.thread_env({"OMP_NUM_THREADS": "8", "OPENBLAS_NUM_THREADS": " 8 "}) == "threads 8"
    assert (
        bench.thread_env({"OMP_NUM_THREADS": "8", "OPENBLAS_NUM_THREADS": "1"})
        == "threads OpenMP 8 · OpenBLAS 1"
    )
    assert "=" not in bench.thread_env({"OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "2"})


def test_hardware_footer_spells_the_architecture_the_human_way():
    """`x86_64` is a snake_case token in a caption (the identifier gate flags it); the footer
    writes `x86-64` / `arm64` and leaves an unknown machine name alone."""
    assert bench.arch_name("x86_64") == "x86-64" and bench.arch_name("AMD64") == "x86-64"
    assert bench.arch_name("aarch64") == "arm64" and bench.arch_name("arm64") == "arm64"
    assert bench.arch_name(" riscv64 ") == "riscv64"
    footer = bench.hardware_footer({"SPACE_ID": "thyn-ai/algenta"})
    assert "x86_64" not in footer and "aarch64" not in footer


def test_v05_gate_reads_the_robust_spread_and_the_mean_median_agreement():
    """Two spikes among 21 samples inflate the CV past 15 % while the median and MAD do not
    move: stable under v0.5. A 50/50 alternation has MAD 0 but a mean far from its median:
    noisy (the skew guard)."""
    spiky = [0.085] * 19 + [0.14, 0.16]
    lane = bench.summarise(bench.LaneSpec("s", bench.SIDE_ALGENTA, lambda: None), spiky)
    assert lane.cv > 0.15 and lane.spread == 0.0 and lane.skew < 0.15 and lane.stable
    assert bench.robust_cv([1.0, 1.1, 0.9, 1.0, 1.05]) == pytest.approx(
        bench.ROBUST_SCALE * 0.05 / 1.0
    )
    bimodal = [0.05, 0.15] * 10 + [0.05]
    lane = bench.summarise(bench.LaneSpec("b", bench.SIDE_ALGENTA, lambda: None), bimodal)
    assert lane.spread == 0.0 and lane.skew > 0.15 and not lane.stable
    assert bench.robust_cv([0.0, 0.0]) == 0.0
