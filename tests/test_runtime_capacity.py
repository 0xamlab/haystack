"""Compute-Unit capacity measurement (apps/runtime/capacity.py).

Covers the plan §9 capacity gates: cgroup v1/v2, fractional quotas, cpuset-only, nested
cgroups (parent tighter than leaf), no-quota fallback, and POOL-level rounding across many
small pods (the anti-per-node-minimum invariant: 20×0.5 vCPU = 3 units, never 20).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.runtime import capacity


# ── pure parsers ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("0-3", 4.0),
        ("0-3,7", 5.0),
        ("0", 1.0),
        ("0,2,4,6", 4.0),
        ("0-1,4-5", 4.0),
        ("", None),
        ("bogus", None),
    ],
)
def test_parse_cpu_list(spec: str, expected: float | None) -> None:
    assert capacity._parse_cpu_list(spec) == expected


@pytest.mark.parametrize(
    "contents,expected",
    [
        ("max 100000", None),  # unlimited
        ("50000 100000", 0.5),  # fractional quota
        ("200000 100000", 2.0),
        ("100000 100000", 1.0),
        ("0 100000", None),  # invalid quota
        ("50000 0", None),  # invalid period
        ("garbage", None),
    ],
)
def test_quota_from_cpu_max(contents: str, expected: float | None) -> None:
    assert capacity._quota_from_cpu_max(contents) == expected


# ── min-of-constraints resolution ───────────────────────────────────────────────


def _stub_readers(monkeypatch, **vals: float | None) -> None:
    """Stub each constraint reader with a fixed value (or None to omit)."""
    mapping = {
        "affinity": "_affinity_vcpu",
        "cpuset": "_cpuset_vcpu",
        "cgroup_v2_cpu_max": "_cgroup_v2_cpu_max_vcpu",
        "cgroup_v1_cpu_quota": "_cgroup_v1_cpu_quota_vcpu",
        "host_cpu_count": "_host_vcpu",
    }
    for key, fn in mapping.items():
        v = vals.get(key)
        monkeypatch.setattr(capacity, fn, lambda _v=v: _v)


def test_picks_min_real_limit_not_host(monkeypatch) -> None:
    # A 2-vCPU-quota pod on a 96-vCPU host measures 2, not 96.
    _stub_readers(monkeypatch, cgroup_v2_cpu_max=2.0, host_cpu_count=96.0)
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu == 2.0
    assert m.source == "cgroup_v2_cpu_max"


def test_cpuset_only_constraint(monkeypatch) -> None:
    _stub_readers(monkeypatch, cpuset=8.0, host_cpu_count=64.0)
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu == 8.0
    assert m.source == "cpuset"


def test_host_fallback_when_no_real_limit(monkeypatch) -> None:
    # No affinity/cpuset/quota → the VM/host allocation is authoritative (a bare VM/laptop).
    _stub_readers(monkeypatch, host_cpu_count=16.0)
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu == 16.0
    assert m.source == "host_cpu_count"


def test_last_resort_floor_when_nothing_readable(monkeypatch) -> None:
    _stub_readers(monkeypatch)  # all None
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu == 1.0
    assert m.source == "fallback"


def test_real_limit_clamped_to_host(monkeypatch) -> None:
    # A misconfigured quota above the host count can never exceed real hardware.
    _stub_readers(monkeypatch, cgroup_v1_cpu_quota=200.0, host_cpu_count=8.0)
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu == 8.0
    assert m.source == "host_cpu_count"


def test_tightest_of_several_real_limits(monkeypatch) -> None:
    _stub_readers(
        monkeypatch, affinity=4.0, cpuset=8.0, cgroup_v2_cpu_max=1.5, host_cpu_count=32.0
    )
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu == 1.5
    assert set(m.constraints) == {"affinity", "cpuset", "cgroup_v2_cpu_max", "host_cpu_count"}


# ── nested cgroup v2 ancestors (parent tighter than leaf) ────────────────────────


def test_cgroup_v2_ancestor_walk_takes_tightest(monkeypatch, tmp_path: Path) -> None:
    # leaf allows 4 vCPU, but an ancestor caps at 1 vCPU → effective is 1.
    root = tmp_path / "cgroup"
    leaf = root / "kubepods" / "pod123" / "container"
    leaf.mkdir(parents=True)
    (root / "kubepods" / "cpu.max").write_text("100000 100000")  # 1.0 vCPU (ancestor, tighter)
    (leaf / "cpu.max").write_text("400000 100000")  # 4.0 vCPU (leaf)
    (root / "cpu.max").write_text("max 100000")  # unlimited root

    monkeypatch.setattr(capacity, "_CGROUP_V2_ROOT", str(root))
    monkeypatch.setattr(capacity, "_PROC_SELF_CGROUP", str(tmp_path / "proc_cgroup"))
    (tmp_path / "proc_cgroup").write_text("0::/kubepods/pod123/container\n")

    assert capacity._cgroup_v2_cpu_max_vcpu() == 1.0


def test_cgroup_v1_reads_leaf_sub_cgroup_not_just_root(monkeypatch, tmp_path: Path) -> None:
    # The process's real limit is set at its cpu sub-cgroup (systemd slice / container), not the
    # mount root — the reader must walk /proc/self/cgroup to the leaf (the #5 review fix).
    root = tmp_path / "cgroup"
    leaf = root / "cpu,cpuacct" / "kubepods" / "pod1"
    leaf.mkdir(parents=True)
    (root / "cpu,cpuacct").mkdir(exist_ok=True)
    (root / "cpu,cpuacct" / "cpu.cfs_quota_us").write_text("-1")  # root: unlimited
    (root / "cpu,cpuacct" / "cpu.cfs_period_us").write_text("100000")
    (leaf / "cpu.cfs_quota_us").write_text("200000")  # leaf: 2.0 vCPU (the real limit)
    (leaf / "cpu.cfs_period_us").write_text("100000")

    monkeypatch.setattr(capacity, "_CGROUP_V2_ROOT", str(root))
    proc = tmp_path / "proc_cgroup"
    proc.write_text("4:cpu,cpuacct:/kubepods/pod1\n")
    monkeypatch.setattr(capacity, "_PROC_SELF_CGROUP", str(proc))

    assert capacity._cgroup_v1_cpu_quota_vcpu() == 2.0


def test_cgroup_v1_cpu_path_parse(monkeypatch, tmp_path: Path) -> None:
    proc = tmp_path / "proc_cgroup"
    proc.write_text("12:memory:/x\n4:cpu,cpuacct:/kubepods/burstable/pod2\n3:devices:/y\n")
    monkeypatch.setattr(capacity, "_PROC_SELF_CGROUP", str(proc))
    assert capacity._cgroup_v1_cpu_path() == "/kubepods/burstable/pod2"


def test_cgroup_v2_relative_path_parse(monkeypatch, tmp_path: Path) -> None:
    proc = tmp_path / "proc_cgroup"
    proc.write_text("0::/kubepods/burstable/podabc\n")
    monkeypatch.setattr(capacity, "_PROC_SELF_CGROUP", str(proc))
    assert capacity._cgroup_v2_relative_path() == "/kubepods/burstable/podabc"


# ── Compute-Unit math ────────────────────────────────────────────────────────────


def test_node_contribution_is_fractional_and_unrounded() -> None:
    assert capacity.node_contribution(2.0, 4) == 0.5
    assert capacity.node_contribution(0.5, 4) == 0.125
    assert capacity.node_contribution(96.0, 4) == 24.0


def test_pool_units_rounds_once_across_many_small_pods() -> None:
    # THE headline case: 20 pods limited to 0.5 vCPU = 10 vCPU total = ceil(10/4) = 3 units.
    # A per-node 4-unit minimum would (wrongly) charge 80. This must be 3.
    contributions = [capacity.node_contribution(0.5, 4) for _ in range(20)]
    assert capacity.pool_units(contributions, 4) == 3


def test_pool_units_from_effective_vcpus_convenience() -> None:
    # one 96-vCPU box = 24 units.
    assert capacity.effective_vcpu_from_measurements([96.0], 4) == 24
    # 3 nodes: 16 + 8 + 4 vCPU = 28 vCPU = ceil(7) = 7 units.
    assert capacity.effective_vcpu_from_measurements([16.0, 8.0, 4.0], 4) == 7


def test_pool_units_empty_is_zero() -> None:
    assert capacity.pool_units([], 4) == 0


def test_vcpu_per_unit_defaults_when_invalid() -> None:
    assert capacity.node_contribution(8.0, 0) == 8.0 / capacity.DEFAULT_VCPU_PER_UNIT
    assert capacity.node_contribution(8.0, -3) == 8.0 / capacity.DEFAULT_VCPU_PER_UNIT


def test_measurement_units_helper(monkeypatch) -> None:
    _stub_readers(monkeypatch, cgroup_v2_cpu_max=8.0, host_cpu_count=64.0)
    m = capacity.measure_effective_vcpu()
    assert m.units(4) == 2.0


def test_measure_is_deterministic_and_real(monkeypatch) -> None:
    # Called with no stubs on the real host: must return a positive finite number without raising.
    m = capacity.measure_effective_vcpu()
    assert m.effective_vcpu > 0
    assert m.source
