"""algenta_spaces.bench — rulebook v0.3 with deterministic fake lanes and an injectable clock."""

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


def test_run_cell_measured_statistics_ratio_direction_and_order():
    clock, log = FakeClock(), []
    ours = [10.0, 11.0, 9.0, 10.0, 10.5]
    theirs = [30.0, 33.0, 27.0, 30.0, 31.5]
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
    assert cell.rulebook == "0.3"
    # order: gate (theirs, ours), 2 interleaved warm-ups, 21 interleaved rounds
    assert log[:2] == ["theirs", "ours"]
    assert log[2:6] == ["theirs", "ours"] * 2
    assert log[6:] == ["theirs", "ours"] * 21
    assert len(log) == 2 + 4 + 42
    lane_ours, lane_theirs = cell.lane(bench.SIDE_ALGENTA), cell.lane(bench.SIDE_INCUMBENT)
    assert lane_ours.n == lane_theirs.n == 21
    assert lane_ours.median_ms == pytest.approx(10.0)
    assert lane_theirs.median_ms == pytest.approx(30.0)
    assert lane_ours.min_ms == pytest.approx(9.0) and lane_ours.max_ms == pytest.approx(11.0)
    assert lane_ours.p95_ms == pytest.approx(11.0)
    assert lane_ours.mad_ms == pytest.approx(0.5)  # 9 of 21 samples sit on the median
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
    assert (
        log
        == ["theirs", "ours"] + ["theirs", "theirs", "ours", "ours"] + ["theirs"] * 5 + ["ours"] * 5
    )


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
    # ours alternates 5 / 25 ms: CV far above 0.15
    cell = bench.run_cell(
        _lanes(clock, log, [5.0, 25.0], [30.0]),
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


def test_run_cell_noisy_on_load_average_above_quota_times_one_and_a_half():
    clock, log = FakeClock(), []
    cell = bench.run_cell(
        _lanes(clock, log, [10.0], [30.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 3.1,
        quota=2,
    )
    assert cell.status == bench.STATUS_NOISY
    assert "load 3.1 on 2 vCPU" in cell.reason
    assert cell.ratio is None
    quiet = bench.run_cell(
        _lanes(clock, [], [10.0], [30.0]),
        correctness_gate=_gate_ok,
        clock=clock,
        loadavg=lambda: 3.0,
        quota=2,
    )
    assert quiet.measured


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
    assert "OMP=1 · OPENBLAS=1" in footer
    assert "pytest==" in footer and "no-such-dist-xyz not installed" in footer
    assert footer.endswith("rulebook v0.3")
    assert "cpu-basic" not in footer and "cgroup" not in footer
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
    assert bench.thread_env({"MKL_NUM_THREADS": "2"}) == "MKL=2"
