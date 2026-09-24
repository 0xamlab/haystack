"""The probe's logic without its hardware: phases, gates, parity, timings and the health shape.

Standard library only, importable on any machine, so every rule the Space applies on the GPU
is unit-tested on the build Mac (`tests/spaces/test_gpu_probe.py`). `probe.py` (the stage
runners) and `app.py` (the web app and orchestrator) call into this module; nothing here imports
torch, kernels, transformers or algenta.

Errors are `ProbeError(code, message)`: the code is what `/health` shows for a failed phase and
what the page prints, never a traceback.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import probe_config as cfg

SCHEMA = "algenta-gpu-probe/3"
#: The phases in the order they run. `record` writes run.json and is the only in-process one.
#: `baseline` (the same decode without Algenta) runs right after `decode`: the decode process has
#: exited by then, which is what returns the session's device memory (run 13 measured the runtime
#: keeping 7.2 GB after `close()`), so the baseline has the whole GPU; the CPU reference, the
#: heaviest host-memory stage, still runs last before the page is served.
PHASES: tuple[str, ...] = (
    "driver",
    "kernel",
    "convert",
    "decode",
    "baseline",
    "reference",
    "record",
)
#: Phases whose failure is recorded and does not stop the run. The baseline is the comparison
#: beside the parity verdict, not the verdict: its block on `/health` carries its own code and
#: the page shows its lanes as unavailable, while the parity record is still written.
SOFT_PHASES: frozenset[str] = frozenset({"baseline"})
PENDING, RUNNING, OK, ERROR, SKIPPED = "pending", "running", "ok", "error", "skipped"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SNAPSHOT_RE = re.compile(r"/snapshots/([0-9a-f]{40})(?:/|$)")
_VARIANT_RE = re.compile(r"/build/([A-Za-z0-9_.-]+)(?:/|$)")
_DRIVER_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


class ProbeError(RuntimeError):
    """A gate refused, or a stage could not do its work; `code` is the phase-level code."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def is_sha(text: object) -> bool:
    return isinstance(text, str) and bool(_SHA_RE.match(text))


# ---------------------------------------------------------------------------
# Phase state machine
# ---------------------------------------------------------------------------


@dataclass
class PhaseRecord:
    name: str
    status: str = PENDING
    code: str | None = None
    message: str | None = None
    wall_s: float | None = None
    started_utc: str | None = None
    finished_utc: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    log_tail: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "wall_s": self.wall_s,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
        }
        if self.log_tail:
            out["log_tail"] = list(self.log_tail)
        return out


class PhaseMachine:
    """Phases run strictly in `order`; a failure marks the rest `skipped` with `upstream_failed`.

    `start` refuses a phase whose predecessor is not settled (`ok`, or failed and soft), and
    refuses to start anything twice: the run is one pass, and a restart is a new machine. A
    `soft` phase's failure is recorded on its own record and the run goes on; every other
    failure marks the rest `skipped` with `upstream_failed`.
    """

    def __init__(self, order: Sequence[str] = PHASES, soft: Iterable[str] = SOFT_PHASES) -> None:
        if not order or len(set(order)) != len(order):
            raise ValueError("phase order must be a non-empty sequence of distinct names")
        self.order = tuple(order)
        self.soft = frozenset(soft) & frozenset(self.order)
        self.records: dict[str, PhaseRecord] = {name: PhaseRecord(name) for name in self.order}
        self.started_utc: str | None = None
        self.finished_utc: str | None = None

    def _settled(self, name: str) -> bool:
        rec = self.records[name]
        return rec.status == OK or (rec.status == ERROR and name in self.soft)

    def _record(self, name: str) -> PhaseRecord:
        try:
            return self.records[name]
        except KeyError:
            raise ValueError(f"unknown phase {name!r}; order is {', '.join(self.order)}") from None

    def start(self, name: str, *, now: str | None = None) -> PhaseRecord:
        rec = self._record(name)
        index = self.order.index(name)
        if not all(self._settled(p) for p in self.order[:index]):
            raise ValueError(f"phase {name!r} cannot start before its predecessors are ok")
        if rec.status != PENDING:
            raise ValueError(f"phase {name!r} is {rec.status}; it can only start once")
        if index == 0:
            self.started_utc = now or utc_now()
        rec.status = RUNNING
        rec.started_utc = now or utc_now()
        return rec

    def finish(
        self,
        name: str,
        data: Mapping[str, Any] | None = None,
        *,
        wall_s: float | None = None,
        log_tail: Iterable[str] = (),
        now: str | None = None,
    ) -> PhaseRecord:
        rec = self._record(name)
        if rec.status != RUNNING:
            raise ValueError(f"phase {name!r} is {rec.status}, not running")
        rec.status = OK
        rec.data = dict(data or {})
        rec.wall_s = None if wall_s is None else round(float(wall_s), 2)
        rec.log_tail = list(log_tail)
        rec.finished_utc = now or utc_now()
        if name == self.order[-1]:
            self.finished_utc = rec.finished_utc
        return rec

    def fail(
        self,
        name: str,
        code: str,
        message: str,
        *,
        wall_s: float | None = None,
        data: Mapping[str, Any] | None = None,
        log_tail: Iterable[str] = (),
        now: str | None = None,
    ) -> PhaseRecord:
        rec = self._record(name)
        if rec.status != RUNNING:
            raise ValueError(f"phase {name!r} is {rec.status}, not running")
        stamp = now or utc_now()
        rec.status = ERROR
        rec.code = code
        rec.message = message
        rec.data = dict(data or {})
        rec.wall_s = None if wall_s is None else round(float(wall_s), 2)
        rec.log_tail = list(log_tail)
        rec.finished_utc = stamp
        if name in self.soft:
            return rec
        for later in self.order[self.order.index(name) + 1 :]:
            self.records[later].status = SKIPPED
            self.records[later].code = "upstream_failed"
            self.records[later].message = f"not run: {name} failed with {code}"
        self.finished_utc = stamp
        return rec

    def _hard_failed(self, rec: PhaseRecord) -> bool:
        return rec.status == ERROR and rec.name not in self.soft

    @property
    def status(self) -> str:
        """`pending` before any start, `running`, `ok` once every phase is settled (a soft
        phase may have failed), `error` once a phase that stops the run has failed."""
        statuses = [r.status for r in self.records.values()]
        if any(self._hard_failed(r) for r in self.records.values()):
            return ERROR
        if all(self._settled(name) for name in self.order):
            return OK
        if all(s == PENDING for s in statuses):
            return PENDING
        return RUNNING

    @property
    def phase(self) -> str:
        """The running phase, else the one that stopped the run, else `done`, else the next."""
        for rec in self.records.values():
            if rec.status == RUNNING:
                return rec.name
        for rec in self.records.values():
            if self._hard_failed(rec):
                return rec.name
        if self.status == OK:
            return "done"
        for rec in self.records.values():
            if rec.status == PENDING:
                return rec.name
        return "done"

    @property
    def failure(self) -> PhaseRecord | None:
        """The failure that stopped the run; a soft phase's failure is on its own record."""
        return next((r for r in self.records.values() if self._hard_failed(r)), None)

    def data(self, name: str) -> dict[str, Any]:
        return dict(self._record(name).data)

    def snapshot(self) -> dict[str, Any]:
        return {name: rec.as_dict() for name, rec in self.records.items()}


# ---------------------------------------------------------------------------
# Gates: the driver, the device, the kernel
# ---------------------------------------------------------------------------


def parse_driver_version(text: object) -> tuple[int, int, int]:
    """`580.178.04` -> (580, 178, 4); raises `driver_version_unreadable` for anything else."""
    match = _DRIVER_RE.search(str(text or ""))
    if not match:
        raise ProbeError(
            "driver_version_unreadable", f"no NVIDIA driver version in {str(text)[:60]!r}"
        )
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def driver_gate(
    driver_version: object, floor_major: int = cfg.DRIVER_FLOOR_MAJOR
) -> dict[str, Any]:
    """Refuse a driver below the CUDA build's floor with `driver_below_floor`."""
    parsed = parse_driver_version(driver_version)
    if parsed[0] < floor_major:
        raise ProbeError(
            "driver_below_floor",
            f"NVIDIA driver {'.'.join(str(p) for p in parsed)} is below the {floor_major} floor "
            "the CUDA build needs",
            {"driver_version": str(driver_version), "driver_floor": floor_major},
        )
    return {
        "driver_version": ".".join(str(p) for p in parsed),
        "base_driver_major": parsed[0],
        "driver_floor": floor_major,
        "meets_driver_floor": True,
    }


def compute_capability_gate(
    cc: Sequence[int],
    supported: Iterable[Sequence[int]] = cfg.SUPPORTED_COMPUTE_CAPABILITIES,
) -> tuple[int, int]:
    """Refuse a device the published CUDA build has no library for."""
    try:
        major, minor = int(cc[0]), int(cc[1])
    except (TypeError, ValueError, IndexError):
        raise ProbeError(
            "compute_capability_unreadable", f"not a compute capability: {cc!r}"
        ) from None
    built = sorted((int(m), int(n)) for m, n in supported)
    # PTX is forward-compatible within the build: any device at or above the oldest target runs.
    if (major, minor) < built[0]:
        raise ProbeError(
            "compute_capability_unsupported",
            f"compute capability {major}.{minor} is below the oldest published target "
            f"{built[0][0]}.{built[0][1]}",
            {"compute_capability": [major, minor], "supported": [list(b) for b in built]},
        )
    return major, minor


def parse_nvidia_smi(line: str, fields: Sequence[str]) -> dict[str, str]:
    """One `--format=csv,noheader` row into `{field: value}`; a short row is an error."""
    values = [part.strip() for part in line.strip().split(",")]
    if len(values) != len(fields) or not all(values):
        raise ProbeError(
            "nvidia_smi_unreadable",
            f"nvidia-smi answered {line.strip()!r} for {','.join(fields)}",
        )
    return dict(zip(fields, values, strict=True))


def snapshot_sha_of(path: object) -> str:
    """The Hub cache revision in a snapshot path, or an empty string."""
    match = _SNAPSHOT_RE.search(str(path or ""))
    return match.group(1) if match else ""


def variant_of(path: object) -> str:
    """The `build/<variant>` segment of a kernel path, or an empty string."""
    match = _VARIANT_RE.search(str(path or ""))
    return match.group(1) if match else ""


def revision_gate(path: object, expected: str = cfg.KERNEL_REVISION) -> str:
    """The loaded kernel must come from the pinned snapshot, else `kernel_revision_mismatch`."""
    found = snapshot_sha_of(path)
    if found != expected:
        raise ProbeError(
            "kernel_revision_mismatch",
            f"kernel loaded from revision {found[:12] or '(none)'}, pinned {expected[:12]}",
            {"loaded": found, "expected": expected},
        )
    return found


def variant_gate(path: object, expected: str = cfg.EXPECTED_VARIANT) -> str:
    found = variant_of(path)
    if found != expected:
        raise ProbeError(
            "kernel_variant_mismatch",
            f"kernels resolved build variant {found or '(none)'}, expected {expected}",
            {"loaded": found, "expected": expected},
        )
    return found


def tier_gate(manifest: Mapping[str, Any], expected: int = cfg.EXPECTED_STAGE_TIER) -> int:
    """The native manifest must declare the staging tier that admits Qwen3-1.7B."""
    tier = manifest.get("resident_stage_tier")
    if tier is None:
        raise ProbeError(
            "kernel_tier_missing", "the native manifest declares no resident_stage_tier"
        )
    if isinstance(tier, bool) or not isinstance(tier, int) or tier != expected:
        raise ProbeError(
            "kernel_tier_mismatch",
            f"native manifest resident_stage_tier is {tier!r}, expected {expected} "
            "(the default tier refuses Qwen3-1.7B with resident_dimension_too_large)",
            {"resident_stage_tier": tier, "expected": expected},
        )
    return tier


def expected_library(manifest: Mapping[str, Any], cc: Sequence[int]) -> str:
    """The library the published loader picks for `cc`: the exact `sm_<cc>` build when present,
    else the newest built target not above the device (PTX forward compatibility), mirroring
    `_native._select_library` in the kernel package."""
    libraries = manifest.get("cuda_libraries") or {}
    if not isinstance(libraries, Mapping) or not libraries:
        raise ProbeError("kernel_manifest_invalid", "the native manifest lists no cuda_libraries")
    major, minor = int(cc[0]), int(cc[1])
    exact = f"sm_{major}{minor}"
    if exact in libraries:
        return str(libraries[exact])
    device_cc = major * 10 + minor
    usable = sorted(
        int(t[3:])
        for t in libraries
        if t.startswith("sm_") and t[3:].isdigit() and int(t[3:]) <= device_cc
    )
    if usable:
        return str(libraries[f"sm_{usable[-1]}"])
    raise ProbeError(
        "gpu_unsupported",
        f"the build's oldest CUDA target is above compute capability {major}.{minor}; "
        f"it carries {', '.join(sorted(libraries))}",
    )


def library_gate(selected: object, manifest: Mapping[str, Any], cc: Sequence[int]) -> str:
    """The library the runtime loaded must be the one the device's capability calls for."""
    wanted = expected_library(manifest, cc)
    if selected != wanted:
        raise ProbeError(
            "kernel_library_mismatch",
            f"the runtime loaded {selected!r}; compute capability {cc[0]}.{cc[1]} calls for "
            f"{wanted}",
            {"selected": selected, "expected": wanted},
        )
    return wanted


def cuda_targets_of(manifest: Mapping[str, Any]) -> list[str]:
    targets = manifest.get("cuda_targets") or list(manifest.get("cuda_libraries") or {})
    return sorted(str(t) for t in targets)


# ---------------------------------------------------------------------------
# Parity and timings
# ---------------------------------------------------------------------------


def compare_tokens(native: Sequence[int], reference: Sequence[int]) -> dict[str, Any]:
    """Prefix agreement of two greedy token streams and where they first part."""
    native = [int(t) for t in native]
    reference = [int(t) for t in reference]
    compared = min(len(native), len(reference))
    prefix = 0
    while prefix < compared and native[prefix] == reference[prefix]:
        prefix += 1
    full = bool(reference) and len(native) == len(reference) and prefix == len(reference)
    divergence = None
    if prefix < compared:
        divergence = {"index": prefix, "native": native[prefix], "reference": reference[prefix]}
    elif len(native) != len(reference):
        divergence = {"index": prefix, "native": None, "reference": None, "length_only": True}
    return {
        "compared": compared,
        "prefix_match": prefix,
        "full_match": full,
        "first_divergence": divergence,
    }


def parity_report(
    native: Sequence[int],
    reference: Sequence[int],
    *,
    reference_margins: Sequence[float] | None = None,
    native_decoded: str | None = None,
    reference_decoded: str | None = None,
) -> dict[str, Any]:
    """`parity: 8/8`, or the first divergent index with the reference's top-2 logit margin there
    (how confidently the reference chose its token: a near-tie is a different finding from a
    disagreement at a clear margin)."""
    cmp = compare_tokens(native, reference)
    n_ref = len(reference)
    report: dict[str, Any] = {
        "native_tokens": [int(t) for t in native],
        "reference_tokens": [int(t) for t in reference],
        "native_decoded": native_decoded,
        "reference_decoded": reference_decoded,
        **cmp,
        "verdict": f"{cmp['prefix_match']}/{n_ref}",
        "reference_top2_margin_at_divergence": None,
    }
    div = cmp["first_divergence"]
    if div is not None and reference_margins is not None and div["index"] < len(reference_margins):
        report["reference_top2_margin_at_divergence"] = round(
            float(reference_margins[div["index"]]), 6
        )
    return report


def step_timings(
    step_ms: Sequence[float], *, steady_from: int = cfg.STEADY_FROM_STEP
) -> dict[str, Any]:
    """Per-step figures defined identically for every lane.

    `steady_step_ms` is the mean of steps `steady_from` to n (3 to 8 for an eight-token decode)
    and `steady_tok_per_s` is 1000 over it: the per-token cost once the lane is past its first
    step and its warm-up. `all_steps_tok_per_s` is n tokens over the sum of all n steps, first
    step and warm-up included. Fewer than `steady_from` steps give no steady figure.
    """
    steps = [float(s) for s in step_ms]
    n = len(steps)
    total = sum(steps)
    steady = steps[steady_from - 1 :] if n >= steady_from else []
    steady_mean = sum(steady) / len(steady) if steady else None
    return {
        "n_tokens": n,
        "step_ms": [round(s, 2) for s in steps],
        "first_step_ms": round(steps[0], 2) if steps else None,
        "mean_step_ms": round(total / n, 2) if n else None,
        "steady_steps": f"{steady_from}-{n}" if steady else None,
        "steady_step_ms": None if steady_mean is None else round(steady_mean, 2),
        "steady_tok_per_s": round(1000.0 / steady_mean, 2) if steady_mean else None,
        "all_steps_tok_per_s": round(n / (total / 1000.0), 2) if n and total > 0 else None,
    }


def decode_timings(open_s: float | None, step_ms: Sequence[float]) -> dict[str, Any]:
    """What the Algenta decode measured, named for what it is.

    `open_s` is the session open: the f64 blob uploaded to the device as f32 and the prompt
    prefilled, after which the first token is already computed (its step is sub-millisecond, so
    `ttft_s`, open plus the first step, is the session open). Step 2 is the warm-up, inside the
    timed steps. The steady figures come from `step_timings`; `tok_per_s` is the older headline,
    the steps after the first (warm-up included), kept so earlier records read the same.
    """
    out = step_timings(step_ms)
    steps = out["step_ms"]
    n = len(steps)
    out["open_s"] = None if open_s is None else round(float(open_s), 2)
    out["ttft_s"] = None
    out["ttft_is_session_open"] = True
    out["tok_per_s"] = None
    if steps and open_s is not None:
        out["ttft_s"] = round(float(open_s) + float(step_ms[0]) / 1000.0, 2)
    if n >= 2:
        after_first = sum(float(s) for s in step_ms[1:])
        if after_first > 0:
            out["tok_per_s"] = round((n - 1) / (after_first / 1000.0), 2)
    return out


def baseline_timings(load_s: float | None, step_ms: Sequence[float]) -> dict[str, Any]:
    """What a transformers lane measured: `load_s` is `from_pretrained` plus the move to the
    device; the steps are the timed generate's, step 1 being the prefill of the prompt, so
    `ttft_s` is step 1 from the timed call's start. The steady figures are `step_timings`."""
    out = step_timings(step_ms)
    out["load_s"] = None if load_s is None else round(float(load_s), 2)
    out["ttft_s"] = round(float(step_ms[0]) / 1000.0, 3) if step_ms else None
    out["ttft_is_session_open"] = False
    return out


def log_tail(text: str, lines: int = 20) -> list[str]:
    rows = [row for row in str(text or "").splitlines() if row.strip()]
    return rows[-lines:]


# ---------------------------------------------------------------------------
# The baseline lanes and the side-by-side view
# ---------------------------------------------------------------------------

LANE_TITLES: dict[str, str] = {
    "algenta": "Algenta CUDA kernels",
    "float32": "transformers CUDA",
    "float16": "transformers CUDA",
}
LANE_PRECISION: dict[str, str] = {
    "algenta": "f32 resident, uploaded from the f64 blob",
    "float32": "float32",
    "float16": "float16",
}
OK_LANE, UNAVAILABLE, ABSENT_LANE, PENDING_LANE = "ok", "unavailable", "absent", "pending"


def lane_view(lane: Mapping[str, Any], reference: Mapping[str, Any] | None) -> dict[str, Any]:
    """One baseline lane as `/health` shows it: the stage's facts, its timings and its parity
    against the CPU reference once that has run. A lane that failed keeps only its code."""
    if not lane.get("ok"):
        return {
            "ok": False,
            "dtype": lane.get("dtype"),
            "code": str(lane.get("code") or "baseline_failed"),
            "message": lane.get("message"),
        }
    out = dict(lane)
    out["timings"] = baseline_timings(lane.get("load_s"), lane.get("step_ms") or [])
    warm = lane.get("warmup") or {}
    out["warmup_timings"] = baseline_timings(None, warm.get("step_ms") or []) if warm else None
    out["parity"] = None
    if reference:
        out["parity"] = parity_report(
            lane.get("tokens") or [],
            reference.get("tokens") or [],
            reference_margins=reference.get("top2_margins"),
            native_decoded=lane.get("decoded"),
            reference_decoded=reference.get("decoded"),
        )
    return out


def baseline_block(machine: PhaseMachine, reference: Mapping[str, Any]) -> dict[str, Any]:
    """The `baseline` block of `/health`: the phase's status and code, then the stage's facts
    and each lane through `lane_view` once the phase is ok."""
    rec = machine.records["baseline"]
    block: dict[str, Any] = {
        "status": rec.status,
        "code": rec.code,
        "message": rec.message,
        "wall_s": rec.wall_s,
        "lanes": {},
    }
    if rec.status != OK:
        return block
    data = machine.data("baseline")
    block.update({k: v for k, v in data.items() if k != "lanes"})
    for dtype in cfg.BASELINE_DTYPES:
        lane = (data.get("lanes") or {}).get(dtype)
        if isinstance(lane, Mapping):
            block["lanes"][dtype] = lane_view(lane, reference)
        else:
            block["lanes"][dtype] = {
                "ok": False,
                "dtype": dtype,
                "code": "baseline_lane_missing",
                "message": "the stage reported no such lane",
            }
    return block


def _algenta_lane(body: Mapping[str, Any]) -> dict[str, Any]:
    decode = body.get("decode") or {}
    kernel = body.get("kernel") or decode
    phases = body.get("phases") or {}
    rec = phases.get("decode") or {}
    lane: dict[str, Any] = {
        "id": "algenta",
        "title": LANE_TITLES["algenta"],
        "precision": LANE_PRECISION["algenta"],
        "status": ABSENT_LANE,
        "code": None,
        "message": None,
    }
    if not decode:
        if rec.get("status") in (ERROR, SKIPPED):
            lane.update(status=UNAVAILABLE, code=rec.get("code"), message=rec.get("message"))
        elif rec.get("status") in (PENDING, RUNNING):
            lane["status"] = PENDING_LANE
        return lane
    timings = decode_timings(decode.get("open_s"), decode.get("step_ms") or [])
    steps = timings["step_ms"]
    taken = None
    start, after_open = decode.get("gpu_free_bytes_start"), decode.get("gpu_free_bytes_after_open")
    if isinstance(start, int) and isinstance(after_open, int):
        taken = max(0, start - after_open)
    revision = str(kernel.get("revision") or "")
    lane.update(
        status=OK_LANE,
        stack=" · ".join(
            part
            for part in (
                f"{cfg.KERNEL_REPO}@{revision[:8]}" if revision else cfg.KERNEL_REPO,
                str(kernel.get("mojo_version") or ""),
                str(kernel.get("selected_library") or ""),
            )
            if part
        ),
        tokens=list(decode.get("tokens") or []),
        decoded=decode.get("decoded"),
        parity=body.get("parity"),
        load_s=timings["open_s"],
        load_label="session open: the f64 blob uploaded as f32, then the prompt prefilled",
        ttft_s=timings["ttft_s"],
        ttft_note="= session open; the prefill runs there",
        first_step_ms=timings["first_step_ms"],
        first_step_note=(
            "prefill done at session open"
            + (
                f"; step 2 ({steps[1]:.1f} ms) is the warm-up, inside the timed steps"
                if len(steps) > 1
                else ""
            )
        ),
        steady_steps=timings["steady_steps"],
        steady_step_ms=timings["steady_step_ms"],
        steady_tok_per_s=timings["steady_tok_per_s"],
        all_steps_tok_per_s=timings["all_steps_tok_per_s"],
        step_ms=steps,
        device_taken_bytes=taken,
        peak_allocated_bytes=None,
        device_memory_note="taken on the device at session open (free memory before minus after)",
        versions={
            "kernel_revision": revision or None,
            "mojo_version": kernel.get("mojo_version"),
            "library": kernel.get("selected_library"),
            "backend": kernel.get("backend"),
        },
    )
    return lane


def _transformers_lane(dtype: str, block: Mapping[str, Any] | None) -> dict[str, Any]:
    lane: dict[str, Any] = {
        "id": dtype,
        "title": LANE_TITLES.get(dtype, "transformers CUDA"),
        "precision": LANE_PRECISION.get(dtype, dtype),
        "status": ABSENT_LANE,
        "code": None,
        "message": None,
    }
    if block is None:
        lane["message"] = "not in this record: the run predates the baseline stage"
        return lane
    status = block.get("status")
    if status in (ERROR, SKIPPED):
        lane.update(status=UNAVAILABLE, code=block.get("code"), message=block.get("message"))
        return lane
    if status != OK:
        lane["status"] = PENDING_LANE
        return lane
    data = (block.get("lanes") or {}).get(dtype) or {}
    if not data.get("ok"):
        lane.update(
            status=UNAVAILABLE,
            code=data.get("code") or "baseline_lane_missing",
            message=data.get("message"),
        )
        return lane
    timings = data.get("timings") or baseline_timings(data.get("load_s"), data.get("step_ms") or [])
    warm = data.get("warmup_timings") or {}
    n_prompt = block.get("n_prompt")
    warm_note = ""
    if warm.get("ttft_s") is not None:
        warm_note = f"; one warm-up generate excluded (first token {warm['ttft_s']:.2f} s"
        if warm.get("steady_step_ms") is not None:
            warm_note += f", steady {warm['steady_step_ms']:.1f} ms"
        warm_note += ")"
    lane.update(
        status=OK_LANE,
        stack=" · ".join(
            part
            for part in (
                f"transformers {block.get('transformers') or ''}".strip(),
                f"torch {block.get('torch') or ''}".strip(),
                f"CUDA {block.get('cuda') or ''}".strip() if block.get("cuda") else "",
            )
            if part
        ),
        tokens=list(data.get("tokens") or []),
        decoded=data.get("decoded"),
        parity=data.get("parity"),
        load_s=timings["load_s"],
        load_label="model load: from_pretrained, then moved to the device",
        ttft_s=timings["ttft_s"],
        ttft_note=(
            f"timed generate: the prefill of the {n_prompt} prompt tokens"
            if n_prompt
            else "timed generate: the prefill"
        ),
        first_step_ms=timings["first_step_ms"],
        first_step_note="step 1 is the prefill" + warm_note,
        steady_steps=timings["steady_steps"],
        steady_step_ms=timings["steady_step_ms"],
        steady_tok_per_s=timings["steady_tok_per_s"],
        all_steps_tok_per_s=timings["all_steps_tok_per_s"],
        step_ms=timings["step_ms"],
        device_taken_bytes=data.get("device_taken_bytes"),
        peak_allocated_bytes=data.get("peak_allocated_bytes"),
        device_memory_note=(
            "taken on the device after the load (free memory before minus after); "
            "peak allocated by torch over load and both generates"
        ),
        versions={
            "transformers": block.get("transformers"),
            "torch": block.get("torch"),
            "cuda": block.get("cuda"),
            "dtype": data.get("dtype"),
            "model_dtype": data.get("model_dtype"),
        },
    )
    return lane


def side_by_side(body: Mapping[str, Any]) -> dict[str, Any]:
    """The comparison as columns: the Algenta lane from `decode`, one lane per baseline dtype.

    Every figure is the run's own measurement through `decode_timings` / `baseline_timings`,
    so an earlier record renders with today's definitions. `predates` is true when the record
    has no `baseline` block at all (a run before the stage existed), which the page says in
    words rather than as a failure. A ratio is reported only for a baseline lane that decoded
    the same tokens as the Algenta lane, and only of the steady per-token times.
    """
    block = body.get("baseline")
    predates = "baseline" not in body
    lanes = [_algenta_lane(body)]
    for dtype in cfg.BASELINE_DTYPES:
        lanes.append(_transformers_lane(dtype, block if isinstance(block, Mapping) else None))
    algenta = lanes[0]
    ratios: list[dict[str, Any]] = []
    for lane in lanes[1:]:
        entry: dict[str, Any] = {"lane": lane["id"], "same_tokens": None, "steady_step_ratio": None}
        if lane["status"] == OK_LANE and algenta["status"] == OK_LANE:
            entry["same_tokens"] = bool(lane["tokens"]) and lane["tokens"] == algenta["tokens"]
            a, b = algenta.get("steady_step_ms"), lane.get("steady_step_ms")
            if entry["same_tokens"] and a and b:
                entry["steady_step_ratio"] = round(float(b) / float(a), 2)
        ratios.append(entry)
    driver = body.get("driver") or {}
    return {
        "gpu": driver.get("device_name") or (driver.get("nvidia_smi") or {}).get("name"),
        "predates": predates,
        "reference_tokens": list((body.get("reference") or {}).get("tokens") or []) or None,
        "steady_from_step": cfg.STEADY_FROM_STEP,
        "lanes": lanes,
        "ratios": ratios,
    }


# ---------------------------------------------------------------------------
# The stage protocol and the health / run.json shape
# ---------------------------------------------------------------------------


def stage_result_from_output(
    stdout: str, returncode: int, *, timed_out: bool = False
) -> dict[str, Any]:
    """Read a stage subprocess: its last stdout line is a JSON object with `ok`.

    A stage that could not even write that line (a native abort, an interpreter crash) becomes
    `stage_crashed` with the exit status; a stage past its budget is `stage_timeout`.
    """
    if timed_out:
        return {"ok": False, "code": "stage_timeout", "message": "the stage ran past its budget"}
    last = ""
    for row in reversed(str(stdout or "").splitlines()):
        if row.strip():
            last = row.strip()
            break
    payload: Any = None
    if last.startswith("{"):
        try:
            payload = json.loads(last)
        except ValueError:
            payload = None
    if isinstance(payload, dict) and "ok" in payload:
        if payload["ok"] is True and returncode == 0:
            return payload
        if payload["ok"] is False:
            payload.setdefault("code", "stage_failed")
            payload.setdefault("message", "the stage reported a failure without a message")
            return payload
    signal_note = f" (signal {-returncode})" if returncode < 0 else ""
    return {
        "ok": False,
        "code": "stage_crashed",
        "message": f"the stage exited with status {returncode}{signal_note} before reporting",
        "returncode": returncode,
    }


def evidence_rows(
    driver: Mapping[str, Any],
    kernel: Mapping[str, Any],
    convert: Mapping[str, Any],
    decode: Mapping[str, Any],
    parity: Mapping[str, Any],
) -> dict[str, Any]:
    """The two evidence rows' fields, in the artifact's names, from this run's data."""
    return {
        "GPU-SPACE-DRIVER-001": {
            "gpu": driver.get("device_name"),
            "nvidia_smi_driver_version": driver.get("driver_version"),
            "cuDriverGetVersion": driver.get("cu_driver_get_version"),
            "cuda_driver_api": driver.get("cuda_driver_api"),
            "compute_capability": driver.get("compute_capability"),
            "driver_floor": driver.get("driver_floor"),
            "meets_driver_floor": driver.get("meets_driver_floor"),
            "libcuda_mapped_paths": driver.get("libcuda_mapped_paths"),
        },
        "GPU-SPACE-PARITY-001": {
            "kernel_revision": kernel.get("revision"),
            "resident_stage_tier": kernel.get("resident_stage_tier"),
            "variant": kernel.get("variant"),
            "selected_library": kernel.get("selected_library"),
            "conversion_wall_s": convert.get("wall_s"),
            "conversion_reused": convert.get("reused"),
            "blob_bytes": convert.get("blob_bytes"),
            "prompt_token_ids": decode.get("prompt_ids"),
            "reference_tokens": parity.get("reference_tokens"),
            "native_tokens": parity.get("native_tokens"),
            "native_full_match": parity.get("full_match"),
            "open_s": decode.get("open_s"),
            "step_ms": decode.get("step_ms"),
        },
    }


def health_body(
    machine: PhaseMachine,
    *,
    versions: Mapping[str, Any] | None = None,
    space: Mapping[str, Any] | None = None,
    build: Mapping[str, Any] | None = None,
    run_json_written: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """The `/health` body: status, phase, every phase's record and the facts measured so far.

    Facts appear only once their phase is `ok`; before that the key is null. A failed phase is
    its code and message under `phases` and again as `failure` at the top for one-glance reads.
    """
    driver = machine.data("driver") if machine.records["driver"].status == OK else {}
    kernel = machine.data("kernel") if machine.records["kernel"].status == OK else {}
    convert = machine.data("convert") if machine.records["convert"].status == OK else {}
    decode = machine.data("decode") if machine.records["decode"].status == OK else {}
    reference = machine.data("reference") if machine.records["reference"].status == OK else {}
    baseline = baseline_block(machine, reference) if "baseline" in machine.records else None
    parity = None
    if decode and reference:
        parity = parity_report(
            decode.get("tokens", []),
            reference.get("tokens", []),
            reference_margins=reference.get("top2_margins"),
            native_decoded=decode.get("decoded"),
            reference_decoded=reference.get("decoded"),
        )
    failure = machine.failure
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": machine.status,
        "phase": machine.phase,
        "phases": machine.snapshot(),
        "failure": None if failure is None else {"phase": failure.name, **failure.as_dict()},
        "started_utc": machine.started_utc,
        "finished_utc": machine.finished_utc,
        "updated_utc": now or utc_now(),
        "run_json": run_json_written,
        "pins": {
            "kernel_repo": cfg.KERNEL_REPO,
            "kernel_revision": cfg.KERNEL_REVISION,
            "expected_variant": cfg.EXPECTED_VARIANT,
            "expected_stage_tier": cfg.EXPECTED_STAGE_TIER,
            "model_repo": cfg.MODEL_REPO,
            "model_revision": cfg.MODEL_REVISION,
            "prompt": cfg.PROMPT,
            "max_new_tokens": cfg.MAX_NEW_TOKENS,
            "driver_floor": cfg.DRIVER_FLOOR_MAJOR,
        },
        "driver": driver or None,
        "kernel": kernel or None,
        "model": convert or None,
        "decode": (
            {**decode, "timings": decode_timings(decode.get("open_s"), decode.get("step_ms", []))}
            if decode
            else None
        ),
        "baseline": baseline,
        "reference": reference or None,
        "parity": parity,
        "run12_recorded": {
            "tokens": list(cfg.RUN12_TOKENS),
            "decoded": cfg.RUN12_DECODED,
            "prompt_ids": list(cfg.RUN12_PROMPT_IDS),
            "artifact": cfg.RUN12_ARTIFACT,
            "matches_this_run": (
                None if parity is None else parity["native_tokens"] == list(cfg.RUN12_TOKENS)
            ),
        },
        "versions": dict(versions or {}),
        "space": dict(space or {}),
        "build": dict(build or {}),
    }
    return body


def run_record(body: Mapping[str, Any]) -> dict[str, Any]:
    """`run.json`: the health body plus the evidence rows and the decision.

    Built by the `record` phase while it is the one running, so every measuring phase that can
    stop the run must be `ok` and nothing may have failed; a soft phase (the baseline) may be
    `error`, and its block then carries the code. The record says `status: ok`, `phase: done`.
    """
    phases = body.get("phases") or {}
    measuring = [name for name in PHASES if name != "record" and name not in SOFT_PHASES]
    not_ok = [name for name in measuring if (phases.get(name) or {}).get("status") != OK]
    if not_ok or body.get("failure"):
        raise ProbeError(
            "run_incomplete",
            "run.json is written only for a complete run; not ok: "
            f"{', '.join(not_ok) or 'failure'}",
        )
    decode = dict(body.get("decode") or {})
    parity = body.get("parity") or {}
    return {
        **body,
        "status": OK,
        "phase": "done",
        "decision": "ok" if parity.get("full_match") else "parity_failed",
        "decision_reason": (
            "native CUDA build loaded and decoded; all tokens match the reference"
            if parity.get("full_match")
            else "native and reference tokens part at index "
            f"{(parity.get('first_divergence') or {}).get('index')}"
        ),
        "evidence": evidence_rows(
            body.get("driver") or {},
            body.get("kernel") or {},
            body.get("model") or {},
            decode,
            body.get("parity") or {},
        ),
    }


def public_error(exc: BaseException) -> ProbeError:
    """Any exception as a `ProbeError`: a typed code when the exception carries one (the kernel
    glue's `KernelError`, algenta's `InferenceError`), else the class name as the code."""
    if isinstance(exc, ProbeError):
        return exc
    code = getattr(exc, "code", None)
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    if isinstance(code, str) and code.strip():
        return ProbeError(code.strip(), text[:300])
    return ProbeError(type(exc).__name__, text[:300])
