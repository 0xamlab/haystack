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

SCHEMA = "algenta-gpu-probe/2"
#: The phases in the order they run. `record` writes run.json and is the only in-process one.
PHASES: tuple[str, ...] = ("driver", "kernel", "convert", "decode", "reference", "record")
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

    `start` refuses a phase whose predecessor is not `ok`, and refuses to start anything twice:
    the run is one pass, and a restart is a new machine.
    """

    def __init__(self, order: Sequence[str] = PHASES) -> None:
        if not order or len(set(order)) != len(order):
            raise ValueError("phase order must be a non-empty sequence of distinct names")
        self.order = tuple(order)
        self.records: dict[str, PhaseRecord] = {name: PhaseRecord(name) for name in self.order}
        self.started_utc: str | None = None
        self.finished_utc: str | None = None

    def _record(self, name: str) -> PhaseRecord:
        try:
            return self.records[name]
        except KeyError:
            raise ValueError(f"unknown phase {name!r}; order is {', '.join(self.order)}") from None

    def start(self, name: str, *, now: str | None = None) -> PhaseRecord:
        rec = self._record(name)
        index = self.order.index(name)
        if any(self.records[p].status != OK for p in self.order[:index]):
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
        for later in self.order[self.order.index(name) + 1 :]:
            self.records[later].status = SKIPPED
            self.records[later].code = "upstream_failed"
            self.records[later].message = f"not run: {name} failed with {code}"
        self.finished_utc = stamp
        return rec

    @property
    def status(self) -> str:
        """`pending` before any start, `running`, `ok` once every phase is ok, else `error`."""
        statuses = [r.status for r in self.records.values()]
        if any(s == ERROR for s in statuses):
            return ERROR
        if all(s == OK for s in statuses):
            return OK
        if all(s == PENDING for s in statuses):
            return PENDING
        return RUNNING

    @property
    def phase(self) -> str:
        """The running phase, else the failed one, else `done`, else the next one to run."""
        for rec in self.records.values():
            if rec.status == RUNNING:
                return rec.name
        for rec in self.records.values():
            if rec.status == ERROR:
                return rec.name
        if self.status == OK:
            return "done"
        for rec in self.records.values():
            if rec.status == PENDING:
                return rec.name
        return "done"

    @property
    def failure(self) -> PhaseRecord | None:
        return next((r for r in self.records.values() if r.status == ERROR), None)

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


def decode_timings(open_s: float | None, step_ms: Sequence[float]) -> dict[str, Any]:
    """What the decode measured, named for what it is.

    `open_s` is the session open: weight upload to the device and the prompt prefill, after which
    the first token is already computed (its step is sub-millisecond). `ttft_s` is therefore open
    plus the first step. `tok_per_s` counts the steps after the first, the steady per-token cost;
    with one token there is no rate.
    """
    steps = [float(s) for s in step_ms]
    n = len(steps)
    out: dict[str, Any] = {
        "n_tokens": n,
        "open_s": None if open_s is None else round(float(open_s), 2),
        "first_token_ms": round(steps[0], 2) if steps else None,
        "ttft_s": None,
        "tok_per_s": None,
        "mean_step_ms": round(sum(steps) / n, 2) if n else None,
        "step_ms": [round(s, 2) for s in steps],
    }
    if steps and open_s is not None:
        out["ttft_s"] = round(float(open_s) + steps[0] / 1000.0, 2)
    if n >= 2:
        after_first = sum(steps[1:])
        if after_first > 0:
            out["tok_per_s"] = round((n - 1) / (after_first / 1000.0), 2)
    return out


def log_tail(text: str, lines: int = 20) -> list[str]:
    rows = [row for row in str(text or "").splitlines() if row.strip()]
    return rows[-lines:]


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

    Built by the `record` phase while it is the one running, so every measuring phase must be
    `ok` and nothing may have failed; the record itself says `status: ok`, `phase: done`.
    """
    phases = body.get("phases") or {}
    measuring = [name for name in PHASES if name != "record"]
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
