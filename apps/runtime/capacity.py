"""Compute-Unit capacity measurement — cgroup-aware effective vCPU.

The server/enterprise licensing metric is the **Compute Unit**: a fixed number of concurrent
*effective* vCPUs (``vcpu_per_unit``, default 4) equals one unit, aggregated across the
licensed pool. This module answers the single hard question that makes that metric fair on
Kubernetes: *how many vCPUs can THIS runtime actually use?*

``effective_vcpu`` is the **minimum finite positive** constraint among every real limit the
process is subject to — so a 2-vCPU-limited pod on a 96-vCPU node measures 2, not 96:

  * process CPU affinity (``sched_getaffinity``)
  * cpuset effective CPUs (cgroup v2 ``cpuset.cpus.effective`` / v1 ``cpuset.cpus``)
  * cgroup v2 ``cpu.max`` quota/period (walking ancestors — a parent may be tighter)
  * cgroup v1 ``cpu.cfs_quota_us`` / ``cpu.cfs_period_us``
  * the VM/OS-visible logical CPU count (``os.cpu_count``) — the fallback when nothing else caps

Rules (from the approved plan §1):
  * CPU *requests* never reduce licensing; only enforceable *limits* do (we read quota/affinity/
    cpuset, never Kubernetes requests, which aren't visible to the process anyway).
  * Fractional values are preserved here; rounding happens only at the POOL level
    (``pool_units``) — never per node/pod/process.
  * No enforceable limit ⇒ the VM/host allocation visible to the process.
  * Fail SAFE: any unreadable signal is skipped, never guessed high; if everything is
    unreadable we fall back to ``os.cpu_count()`` (or 1.0 as the last resort).

Pure stdlib, cross-platform, no imports beyond the runtime; on macOS/Windows only the
``os.cpu_count`` path contributes (no cgroups), which is correct for a laptop.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

# Default Compute-Unit size. The AUTHORITATIVE value at runtime comes from the signed license
# claim ``measurement_policy_version`` + ``vcpu_per_unit`` (Stripe-driven); this constant is
# only the local default when computing a pre-license estimate or a diagnostic.
DEFAULT_VCPU_PER_UNIT = 4

_CGROUP_V2_ROOT = "/sys/fs/cgroup"
_PROC_SELF_CGROUP = "/proc/self/cgroup"


@dataclass(frozen=True)
class CapacityMeasurement:
    """The resolved effective-vCPU and the raw signals behind it (for diagnostics + reports).

    ``effective_vcpu`` is what licensing counts. ``constraints`` maps each signal name to the
    finite positive vCPU value it reported (absent = not applicable / unreadable). ``source``
    names the binding constraint (the one that produced ``effective_vcpu``).
    """

    effective_vcpu: float
    source: str
    constraints: dict[str, float] = field(default_factory=dict)

    def units(self, vcpu_per_unit: int = DEFAULT_VCPU_PER_UNIT) -> float:
        """This runtime's fractional Compute-Unit contribution (NOT rounded — see ``pool_units``)."""
        return node_contribution(self.effective_vcpu, vcpu_per_unit)


# ── individual constraint readers (each: float | None; None = no constraint / unreadable) ──


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _affinity_vcpu() -> float | None:
    """CPUs this process may be scheduled on. Linux-only; unavailable elsewhere → None."""
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is None:
        return None
    try:
        count = len(getaffinity(0))
    except OSError:
        return None
    return float(count) if count > 0 else None


def _parse_cpu_list(spec: str) -> float | None:
    """Count CPUs in a Linux cpu-list string like ``0-3,7`` → 5.0. Empty/invalid → None."""
    total = 0
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                total += int(hi) - int(lo) + 1
            except ValueError:
                return None
        else:
            try:
                int(part)
            except ValueError:
                return None
            total += 1
    return float(total) if total > 0 else None


def _cpuset_vcpu() -> float | None:
    """Effective cpuset size (cgroup v2 then v1). The kernel already intersects with ancestors
    in ``cpuset.cpus.effective``, so a single read is authoritative."""
    for path in (
        f"{_CGROUP_V2_ROOT}/cpuset.cpus.effective",  # v2
        f"{_CGROUP_V2_ROOT}/cpuset/cpuset.cpus",  # v1 mount
    ):
        spec = _read_text(path)
        if spec:
            got = _parse_cpu_list(spec)
            if got is not None:
                return got
    return None


def _quota_from_cpu_max(contents: str) -> float | None:
    """Parse a cgroup v2 ``cpu.max`` value (``"max 100000"`` = unlimited, ``"50000 100000"`` =
    0.5 vCPU). Returns the vCPU ceiling, or None when unlimited/malformed."""
    parts = contents.split()
    if len(parts) != 2:
        return None
    quota_s, period_s = parts
    if quota_s == "max":
        return None
    try:
        quota, period = int(quota_s), int(period_s)
    except ValueError:
        return None
    if quota <= 0 or period <= 0:
        return None
    return quota / period


def _cgroup_v2_relative_path() -> str:
    """This process's v2 cgroup path (from ``/proc/self/cgroup`` ``0::<path>``), '' if unknown."""
    contents = _read_text(_PROC_SELF_CGROUP)
    if not contents:
        return ""
    for line in contents.splitlines():
        # unified hierarchy line: "0::/some/path"
        if line.startswith("0::"):
            return line[3:].strip()
    return ""


def _cgroup_v2_cpu_max_vcpu() -> float | None:
    """Tightest ``cpu.max`` ceiling walking from this process's cgroup up to the root — a
    parent group may impose a smaller quota than the leaf."""
    tightest: float | None = None
    # Always include the mount root file (the container's own view).
    candidates = [f"{_CGROUP_V2_ROOT}/cpu.max"]
    rel = _cgroup_v2_relative_path().strip("/")
    if rel:
        parts = rel.split("/")
        for depth in range(len(parts)):
            sub = "/".join(parts[: depth + 1])
            candidates.append(f"{_CGROUP_V2_ROOT}/{sub}/cpu.max")
    for path in candidates:
        contents = _read_text(path)
        if not contents:
            continue
        ceiling = _quota_from_cpu_max(contents)
        if ceiling is not None and (tightest is None or ceiling < tightest):
            tightest = ceiling
    return tightest


def _cgroup_v1_cpu_path() -> str:
    """This process's cgroup-v1 ``cpu`` (or ``cpu,cpuacct``) controller path from
    ``/proc/self/cgroup`` (lines like ``4:cpu,cpuacct:/some/path``), '' if not found."""
    contents = _read_text(_PROC_SELF_CGROUP)
    if not contents:
        return ""
    for line in contents.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        controllers = parts[1].split(",")
        if "cpu" in controllers:
            return parts[2].strip()
    return ""


def _v1_quota_at(base: str) -> float | None:
    quota_s = _read_text(f"{base}/cpu.cfs_quota_us")
    period_s = _read_text(f"{base}/cpu.cfs_period_us")
    if not quota_s or not period_s:
        return None
    try:
        quota, period = int(quota_s), int(period_s)
    except ValueError:
        return None
    if quota <= 0 or period <= 0:  # -1 (or 0) ⇒ no limit
        return None
    return quota / period


def _cgroup_v1_cpu_quota_vcpu() -> float | None:
    """Tightest cgroup-v1 CFS quota ceiling, walking the process's actual cpu sub-cgroup up to the
    mount root — a systemd slice / container sub-cgroup (e.g. CPUQuota=200%) sets the limit at the
    LEAF, not the root mount, so reading only the mount misses it."""
    tightest: float | None = None
    for mount in (f"{_CGROUP_V2_ROOT}/cpu", f"{_CGROUP_V2_ROOT}/cpu,cpuacct"):
        # the mount root itself...
        got = _v1_quota_at(mount)
        if got is not None and (tightest is None or got < tightest):
            tightest = got
        # ...and every ancestor down to this process's leaf under it.
        rel = _cgroup_v1_cpu_path().strip("/")
        if rel:
            parts = rel.split("/")
            for depth in range(len(parts)):
                got = _v1_quota_at(f"{mount}/{'/'.join(parts[: depth + 1])}")
                if got is not None and (tightest is None or got < tightest):
                    tightest = got
    return tightest


def _host_vcpu() -> float | None:
    count = os.cpu_count()
    return float(count) if count and count > 0 else None


# ── public API ────────────────────────────────────────────────────────────────


def measure_effective_vcpu() -> CapacityMeasurement:
    """Resolve this runtime's effective vCPU as the min finite positive constraint.

    Deterministic given the host/cgroup state; safe to call at boot and on every heartbeat
    (the plan requires re-measurement on hotplug/cgroup-change, which is just calling this again).
    """
    readings: dict[str, float | None] = {
        "affinity": _affinity_vcpu(),
        "cpuset": _cpuset_vcpu(),
        "cgroup_v2_cpu_max": _cgroup_v2_cpu_max_vcpu(),
        "cgroup_v1_cpu_quota": _cgroup_v1_cpu_quota_vcpu(),
        "host_cpu_count": _host_vcpu(),
    }
    constraints = {name: val for name, val in readings.items() if val is not None and val > 0}

    if not constraints:
        # Nothing readable at all — last-resort floor. Never guess high.
        return CapacityMeasurement(effective_vcpu=1.0, source="fallback", constraints={})

    # The host CPU count is a fallback bound, not an enforceable *limit*: only let it be the
    # binding constraint when no real limit (affinity/cpuset/quota) is present.
    real_limits = {k: v for k, v in constraints.items() if k != "host_cpu_count"}
    pool = real_limits or constraints
    source = min(pool, key=lambda k: pool[k])
    effective = pool[source]
    # A real limit can still exceed the host count on a misconfigured system; clamp to host.
    host = constraints.get("host_cpu_count")
    if host is not None and effective > host:
        effective, source = host, "host_cpu_count"
    return CapacityMeasurement(
        effective_vcpu=float(effective), source=source, constraints=dict(constraints)
    )


def node_contribution(effective_vcpu: float, vcpu_per_unit: int = DEFAULT_VCPU_PER_UNIT) -> float:
    """A single runtime's FRACTIONAL Compute-Unit contribution. Never rounded here — rounding
    at the node level is the per-node-minimum bug the plan explicitly forbids."""
    per_unit = vcpu_per_unit if vcpu_per_unit and vcpu_per_unit > 0 else DEFAULT_VCPU_PER_UNIT
    return max(0.0, float(effective_vcpu)) / per_unit


def pool_units(
    contributions: list[float] | tuple[float, ...],
    vcpu_per_unit: int = DEFAULT_VCPU_PER_UNIT,
) -> int:
    """Aggregate fractional node contributions into whole Compute Units for the pool:
    ``ceil(sum(contributions))``. Sum first, round ONCE — so twenty 0.5-vCPU pods (10 vCPU
    total) cost ``ceil(10/4)=3`` units, not ``20`` per-node minimums.

    ``contributions`` are the per-runtime fractional units from ``node_contribution`` /
    ``CapacityMeasurement.units``. Passing raw effective-vCPU values is a caller error; this
    expects already-divided contributions."""
    total = math.fsum(max(0.0, float(c)) for c in contributions)
    return int(math.ceil(total)) if total > 0 else 0


def effective_vcpu_from_measurements(
    effective_vcpus: list[float] | tuple[float, ...],
    vcpu_per_unit: int = DEFAULT_VCPU_PER_UNIT,
) -> int:
    """Convenience: pool units directly from a list of per-runtime effective-vCPU values."""
    per_unit = vcpu_per_unit if vcpu_per_unit and vcpu_per_unit > 0 else DEFAULT_VCPU_PER_UNIT
    return pool_units([node_contribution(v, per_unit) for v in effective_vcpus], per_unit)
