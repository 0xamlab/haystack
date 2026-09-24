"""The probe's logic without its hardware: phases, gates, parsers, lanes and the health shape.

Standard library only, importable on any machine, so every rule the Space applies on the GPU
is unit-tested on the build Mac (`tests/spaces/test_gpu_probe.py`). `probe.py` (the stage
runners) and `app.py` (the web app and orchestrator) call into this module; nothing here imports
torch, kernels, transformers or algenta.

Errors are `ProbeError(code, message)`: the code is what `/health` shows for a failed phase or
lane and what the page prints, never a traceback.
"""

from __future__ import annotations

import json
import os
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import probe_config as cfg

SCHEMA = "algenta-gpu-probe/4"
#: The phases in the order they run. `record` writes run.json and is the only in-process one.
#: Every lane stage is its own process, so the GPU is empty at each stage start and a native
#: abort is a lane code, never the end of the web app. The two race lanes run first, right
#: after the conversion they share; the Hub kernels' parity path and the transformers lanes
#: follow; the CPU reference, the heaviest host-memory stage, runs last before the record.
PHASES: tuple[str, ...] = (
    "driver",
    "kernel",
    "convert",
    "engine",
    "llama",
    "decode",
    "baseline",
    "reference",
    "record",
)
#: Phases whose failure is recorded on their own record and does not stop the run: the four
#: lanes and the kernel load (the Hub lane's dependency). The driver, the conversion, the
#: reference and the record decide the run.
SOFT_PHASES: frozenset[str] = frozenset({"kernel", "engine", "llama", "decode", "baseline"})
#: A lane that needs an earlier soft phase: it is marked `upstream_failed` when that phase is
#: not ok, instead of failing on its own with a less useful code.
DEPENDS: dict[str, str] = {"decode": "kernel"}
LANE_PHASES: tuple[str, ...] = ("engine", "llama", "decode", "baseline")
PENDING, RUNNING, OK, ERROR, SKIPPED = "pending", "running", "ok", "error", "skipped"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SNAPSHOT_RE = re.compile(r"/snapshots/([0-9a-f]{40})(?:/|$)")
_VARIANT_RE = re.compile(r"/build/([A-Za-z0-9_.-]+)(?:/|$)")
_DRIVER_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
_CUDA_TARGET_RE = re.compile(r"^sm_(\d+?)(\d)(a?)$")
_KV_RE = re.compile(r"([A-Za-z_]\w*)=\s*([-+0-9.eE]+)")
_LLAMA_VERSION_RE = re.compile(r"version:\s*(\d+)\s*\(([0-9a-fA-F]+)\)")


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


def engine_protocol_of(name: object) -> str | None:
    """The lane A protocol a binary name selects: `conform_generate_cuda` (the wheel's engine,
    `CONFORM_*` lines) or `qwen3_p3_graph_cuda` (the packed-int8 graph driver); None for any
    other name, which the engine stage refuses before launch."""
    base = str(name or "").rsplit("/", 1)[-1]
    return base if base in cfg.ENGINE_PROTOCOLS else None


def selected_engine(env: Mapping[str, str] | None = None) -> str | None:
    """The binary `ALGENTA_CUDA_ENGINE` names, or None when the wheel's engine is the default."""
    env = os.environ if env is None else env
    return (env.get(cfg.ENGINE_ENV) or "").strip() or None


def active_prompt_fixture(env: Mapping[str, str] | None = None) -> str:
    """Which prompt this run converts and races: `PROBE_PROMPT_FIXTURE` when set (an unknown
    name is `prompt_fixture_unknown`), else `campaign` when `ALGENTA_CUDA_ENGINE` selects the
    packed-int8 graph driver (its oracle is bound to that fixture), else `battery`."""
    env = os.environ if env is None else env
    explicit = (env.get(cfg.PROMPT_FIXTURE_ENV) or "").strip().lower()
    if explicit:
        if explicit not in cfg.PROMPT_FIXTURES:
            raise ProbeError(
                "prompt_fixture_unknown",
                f"{cfg.PROMPT_FIXTURE_ENV}={explicit!r}; known: {', '.join(cfg.PROMPT_FIXTURES)}",
            )
        return explicit
    if engine_protocol_of(selected_engine(env)) == cfg.P3_ENGINE_NAME:
        return "campaign"
    return "battery"


def prompt_fixture_pin(env: Mapping[str, str] | None = None) -> str:
    """`active_prompt_fixture` for the health body's pins: an unknown name is reported as
    `unknown (<value>)` there instead of raised, so `/health` still answers; the convert stage
    raises the code."""
    try:
        return active_prompt_fixture(env)
    except ProbeError as exc:
        return f"unknown ({exc.message})"


def battery_prompt_ids(n: int = cfg.PROMPT_TOKENS) -> list[int]:
    """The eight-id cycle repeated to `n` tokens: the ids the wheel engine's `--prompt-len`
    override and `algenta_bench.py` generate."""
    cycle = cfg.PROMPT_CYCLE_IDS
    return [int(cycle[i % len(cycle)]) for i in range(int(n))]


def campaign_prompt_ids(n: int = cfg.PROMPT_TOKENS) -> list[int]:
    """The nvidia_race campaign fixture (`"The capital of France is Paris. " * 36 + "The capital
    of France"`), as the Qwen3 tokenizer encodes it: `785`, then the seven-id cycle, to `n`
    tokens (256 = 1 + 7 x 36 + 3). The packed-int8 graph driver's oracle expects exactly this
    prompt in the checkpoint manifest."""
    if int(n) <= 0:
        return []
    cycle = cfg.CAMPAIGN_PROMPT_CYCLE
    return [int(cfg.CAMPAIGN_PROMPT_HEAD)] + [int(cycle[i % len(cycle)]) for i in range(int(n) - 1)]


def race_prompt_ids(n: int = cfg.PROMPT_TOKENS, fixture: str | None = None) -> list[int]:
    """The prompt every lane of this run uses: the active fixture's ids (see
    `active_prompt_fixture`), or the named one."""
    name = active_prompt_fixture() if fixture is None else fixture
    if name == "campaign":
        return campaign_prompt_ids(n)
    if name == "battery":
        return battery_prompt_ids(n)
    raise ProbeError("prompt_fixture_unknown", f"no prompt fixture named {name!r}")


def campaign_oracle_tokens(n: int = cfg.P3_ORACLE_TOKENS) -> list[int]:
    """The packed-int8 graph driver's `_oracle_token(i)` for i < n: the eight-token window, then
    the seven-token cycle. When its G0 gate says PASS, these are the tokens it generated and
    checked; it prints no other token."""
    window, cycle = cfg.CAMPAIGN_ORACLE_WINDOW, cfg.CAMPAIGN_ORACLE_CYCLE
    return [
        int(window[i]) if i < len(window) else int(cycle[(i - len(window)) % len(cycle)])
        for i in range(int(n))
    ]


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
# Gates: the driver, the device, the kernel, the engine
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
    """The native manifest must declare the published staging tier (it admits both Qwen3
    checkpoints the probe has run: 0.6B-Base needs 3072, 1.7B needs 6144)."""
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


def parse_cuda_target(text: object) -> tuple[int, int, bool]:
    """`sm_90a` -> (9, 0, True): major, minor and whether the target is architecture-specific
    (the `a` suffix: its image loads on that architecture alone, never forward)."""
    match = _CUDA_TARGET_RE.match(str(text or "").strip())
    if not match:
        raise ProbeError("engine_target_unreadable", f"not an sm_NN[a] target: {text!r}")
    major, minor, suffix = match.groups()
    return int(major), int(minor), suffix == "a"


def engine_target_gate(cuda_target: object, cc: Sequence[int]) -> dict[str, Any]:
    """Whether the engine's compile target can load on this device.

    A plain `sm_NN` target carries PTX the driver JIT-compiles for any device at or above it;
    an `sm_NNa` target is architecture-specific and loads on that architecture alone (the
    wheel's `sm_90a` engine is Hopper-only). An engine without a declared target is not
    gated: the run decides. A mismatch is `engine_target_mismatch`, raised before the binary
    is launched, so the lane's code names the fact instead of a CUDA load error.
    """
    device = (int(cc[0]), int(cc[1]))
    if cuda_target is None or cuda_target == "":
        return {
            "checked": False,
            "ok": None,
            "cuda_target": None,
            "architecture_specific": None,
            "device_compute_capability": list(device),
            "note": "no compile target declared for this engine; the run decides",
        }
    major, minor, specific = parse_cuda_target(cuda_target)
    ok = device == (major, minor) if specific else device >= (major, minor)
    facts = {
        "checked": True,
        "ok": ok,
        "cuda_target": str(cuda_target),
        "architecture_specific": specific,
        "device_compute_capability": list(device),
    }
    if not ok:
        kind = (
            f"an architecture-specific image that loads on compute capability {major}.{minor} alone"
            if specific
            else f"a build whose oldest target is compute capability {major}.{minor}"
        )
        raise ProbeError(
            "engine_target_mismatch",
            f"the engine is built for {cuda_target} ({kind}); this device is compute "
            f"capability {device[0]}.{device[1]}",
            facts,
        )
    return facts


# ---------------------------------------------------------------------------
# The engine's and llama.cpp's outputs
# ---------------------------------------------------------------------------

#: The engine's own output literals, in the order they are checked, mapped onto lane codes
#: (`algenta.serve.engine.ENGINE_OUTPUT_REFUSALS` spells the same three).
ENGINE_OUTPUT_CODES: tuple[tuple[str, str], ...] = (
    ("built without -D ALGENTA_GPU -D ALGENTA_CUDA", "engine_binary_not_cuda_build"),
    ("no accelerator on this host", "engine_no_gpu"),
    ("CONFORM_REFUSED:", "engine_refused_model"),
)


def _last_line(text: str, limit: int = 200) -> str:
    rows = [row.strip() for row in str(text or "").splitlines() if row.strip()]
    return rows[-1][:limit] if rows else ""


def parse_engine_output(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    """The engine's `CONFORM_TOKENS:` and `CONFORM_TIMING:` lines as one run's facts.

    The timing line is `CONFORM_TIMING: n_prompt= 256  n_gen= 64  prefill_ms= 39.1
    decode_tok_s= 187.2` (Mojo's print puts a space after each label), read as `key=value`
    pairs whatever the spacing. A refusal or a build/host literal in the output is its own
    code; a non-zero exit without one is `engine_run_failed` with the last output line.
    """
    text = f"{stdout or ''}\n{stderr or ''}"
    for literal, code in ENGINE_OUTPUT_CODES:
        if literal in text:
            line = next((row for row in text.splitlines() if literal in row), literal)
            raise ProbeError(code, line.strip()[:300])
    if returncode != 0:
        raise ProbeError(
            "engine_run_failed",
            f"the engine exited with status {returncode}: {_last_line(text) or 'no output'}",
        )
    tokens: list[int] | None = None
    timing: dict[str, float] = {}
    for row in str(stdout or "").splitlines():
        row = row.strip()
        if row.startswith("CONFORM_TOKENS:"):
            try:
                tokens = [int(t) for t in row.split(":", 1)[1].split()]
            except ValueError as exc:
                raise ProbeError("engine_tokens_unreadable", row[:200]) from exc
        elif row.startswith("CONFORM_TIMING:"):
            timing = {k: float(v) for k, v in _KV_RE.findall(row)}
    if tokens is None:
        raise ProbeError("engine_no_tokens", "the engine printed no CONFORM_TOKENS line")
    for key in ("n_prompt", "n_gen", "prefill_ms", "decode_tok_s"):
        if key not in timing:
            raise ProbeError("engine_no_timing", f"the CONFORM_TIMING line lacks {key}")
    n_prompt = int(timing["n_prompt"])
    prefill_ms = float(timing["prefill_ms"])
    return {
        "tokens": tokens,
        "n_prompt": n_prompt,
        "n_gen": int(timing["n_gen"]),
        "prefill_ms": round(prefill_ms, 3),
        "prefill_tok_per_s": (
            round(n_prompt / (prefill_ms / 1000.0), 2) if prefill_ms > 0 and n_prompt else None
        ),
        "decode_tok_per_s": round(float(timing["decode_tok_s"]), 2),
        "ttft_ms": round(prefill_ms, 3),
        "stdout_tail": _last_line(stdout),
    }


#: The packed-int8 graph driver's own output literals, in the order they are checked, mapped
#: onto lane codes. The driver has no usage path and no `CONFORM_*` lines: it refuses with a
#: sentence, fails a gate with `Gn RESULT: FAIL`, and prints its figures as prose
#: (`benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo`, read end to end). Every one
#: of these is a `print` — stdout — so only stdout is read for them: a warning or a loader
#: message on stderr that happens to quote a verdict is not the driver's verdict.
P3_OUTPUT_CODES: tuple[tuple[str, str], ...] = (
    ("built without -D ALGENTA_GPU -D ALGENTA_CUDA", "engine_binary_not_cuda_build"),
    ("no accelerator on this host", "engine_no_gpu"),
    ("resident_no_accelerator_present", "engine_no_gpu"),
    ("cannot run a resident session here:", "engine_resident_refused"),
    ("ORACLE MISMATCH", "engine_oracle_mismatch"),
    ("G0 RESULT: FAIL", "engine_oracle_mismatch"),
    ("G1 RESULT: FAIL", "engine_gate_failed"),
    ("G2 RESULT: FAIL", "engine_gate_failed"),
)
#: What the Mojo runtime, not the driver, writes on stderr when the host has no NVIDIA driver to
#: open: `Unhandled exception caught during execution: At max/mojo/max/gpu/host/
#: device_context.mojo:...: Failed to open library "libnvidia-ml.so.1"` (the GPU-less smoke's
#: line, `algenta-tooling/cuda-engine-sm89/out-logs/smoke-no-gpu.log`; `libcuda.so.1` is the
#: other host library the driver dlopens), followed by `To get more accurate error information,
#: set MODULAR_DEBUG=device-sync-mode.` up to three times. These two and the no-accelerator
#: sentence are the only stderr lines that are codes; any other stderr line is context for
#: `engine_run_failed`, never a verdict.
P3_STDERR_CODES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Failed to open library \W?(?:libnvidia-ml|libcuda)\b"), "engine_no_gpu"),
    (re.compile(r"no accelerator"), "engine_no_gpu"),
)
_MOJO_EXCEPTION = "Unhandled exception caught during execution:"
_NUM = r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
_P3_HEADER_RE = re.compile(r"^qwen3_p3_graph_cuda: checkpoint = (.+?) \| (.*)$")
_P3_HEADER_KV_RE = re.compile(r"([A-Za-z_]\w*) = (\d+)")
_P3_DEVICE_RE = re.compile(r"^\s*device: (.+?)\s*$")
_P3_LOAD_RE = re.compile(r"^\s*one-time load \(.*?\): " + _NUM + r" ms\s*$")
_P3_NODES_RE = re.compile(
    r"^\s*captured replay nodes per token: (\d+) \(vs (\d+) per-dispatch enqueues per token\)"
)
_P3_KERNELS_RE = re.compile(r"^\s*graph-arm packed3 kernels: (.+?)\s*$")
#: `Gn RESULT: PASS — ...`, `Gn RESULT: FAIL — ...`, or the v3 build's G1 reporting form
#: `G1 RESULT: <n> total flip(s) vs the f32 session across all seeds (reporting gate; G0 16/16
#: remains HARD)` — Mojo's print puts one space between `RESULT:`, the count and `total`.
_P3_GATE_RE = re.compile(r"^(G[012]) RESULT: (?:(PASS|FAIL)|(\d+) total flip(?:\(s\)|s)?)(.*)$")
_P3_G2_ROW_RE = re.compile(
    r"^\s*n_steps= (\d+) : graph-p3 " + _NUM + r" ms/step vs per-dispatch-p3 " + _NUM + r" ms/step"
)
_P3_RUNS_RE = re.compile(r"^Throughput \(.*?\), (\d+) timed runs per cell \((\d+) untimed warmup")
_P3_CELL_RE = re.compile(
    r"^\s*gen (\d+)\s+(graph-p3|f32-graph|per-dispatch-p3)\s*: median "
    + _NUM
    + r" ms \| rel IQR "
    + _NUM
    + r" % \| outliers (\d+) \| "
    + _NUM
    + r" tok/s \((PASS|FLAGGED), frozen"
)
_P3_DONE_RE = re.compile(r"^qwen3_p3_graph_cuda: done \((.+)\)\s*$")
P3_ARMS: dict[str, str] = {
    "graph-p3": "graph_p3",
    "f32-graph": "f32_graph",
    "per-dispatch-p3": "per_dispatch_p3",
}


def parse_p3_engine_output(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    """The packed-int8 graph driver's prints as one launch's facts.

    The driver runs its gates first (G0: 16 greedy tokens against its campaign oracle through one
    async graph chain; G1: 3 seeds x 128 steps, graph == per-dispatch token for token; G2:
    per-step wall flat across 32/64/128/256 replays and faster than per-dispatch), then the
    throughput table: for gen=64 and gen=256, three arms (`graph-p3`, the subject; `f32-graph`;
    `per-dispatch-p3`), each `median <ms> ms | rel IQR <pct> % | outliers <n> | <tok/s> tok/s
    (PASS|FLAGGED, frozen 5%)`, N timed runs after one untimed warm-up, prefill excluded from
    every timed window. It prints the one-time load, the captured node count, the kernel
    generation and the device; it prints no prefill time and, when the oracle passes, no token
    (the 16 it checked are `campaign_oracle_tokens`).

    The driver's refusals and verdicts are read from stdout alone (`P3_OUTPUT_CODES`): a
    refusal, a failed gate, or a G1 reporting line with a non-zero flip count is its own code.
    A gate passes only on the driver's `PASS` form or an explicit zero-flip form. stderr is
    read only on a non-zero exit, for the runtime's no-driver line and the no-accelerator
    sentence (`P3_STDERR_CODES`); a non-zero exit without any of these is `engine_run_failed`
    with the runtime's exception line, else the last stderr line, else the last stdout line.
    """
    out_text, err_text = str(stdout or ""), str(stderr or "")
    for literal, code in P3_OUTPUT_CODES:
        line = next((row for row in out_text.splitlines() if literal in row), None)
        if line is not None:
            raise ProbeError(code, line.strip()[:300])
    if returncode != 0:
        # stderr means something only when the driver failed: the loader refusals first,
        # then the generic failure (Codna on #1173: a clean exit never reads stderr)
        for pattern, code in P3_STDERR_CODES:
            line = next((row for row in err_text.splitlines() if pattern.search(row)), None)
            if line is not None:
                raise ProbeError(code, line.strip()[:300])
        exception = next((row for row in err_text.splitlines() if _MOJO_EXCEPTION in row), "")
        detail = exception.strip()[:200] or _last_line(err_text) or _last_line(out_text)
        raise ProbeError(
            "engine_run_failed",
            f"the engine exited with status {returncode}: {detail or 'no output'}",
        )
    out: dict[str, Any] = {
        "checkpoint": None,
        "n_prompt": None,
        "model": {},
        "device": None,
        "load_ms": None,
        "graph_nodes": None,
        "dispatch_budget": None,
        "kernel_variant": None,
        "gates": {},
        "g2_steps": [],
        "runs": None,
        "warmup": None,
        "cells": {},
        "done": None,
    }
    for raw in str(stdout or "").splitlines():
        row = raw.rstrip()
        if m := _P3_HEADER_RE.match(row):
            out["checkpoint"] = m.group(1)
            out["model"] = {k: int(v) for k, v in _P3_HEADER_KV_RE.findall(m.group(2))}
            out["n_prompt"] = out["model"].get("n_prompt")
        elif m := _P3_DEVICE_RE.match(row):
            out["device"] = m.group(1)
        elif m := _P3_LOAD_RE.match(row):
            out["load_ms"] = round(float(m.group(1)), 3)
        elif m := _P3_NODES_RE.match(row):
            out["graph_nodes"], out["dispatch_budget"] = int(m.group(1)), int(m.group(2))
        elif m := _P3_KERNELS_RE.match(row):
            out["kernel_variant"] = m.group(1)
        elif m := _P3_GATE_RE.match(row):
            gate, verdict, flips, _rest = m.groups()
            count = int(flips) if flips is not None else None
            passed = verdict == "PASS" or count == 0
            out["gates"][gate] = {"passed": passed, "flips": count, "line": row.strip()[:200]}
            if not passed:
                # the FAIL forms are caught above by literal; the v3 build's G1 line with a
                # non-zero count is the driver reporting, not passing, and the lane fails closed
                raise ProbeError(
                    "engine_oracle_mismatch" if gate == "G0" else "engine_gate_failed",
                    (
                        f"{gate} reported {count} total flip(s) against the f32 session: "
                        if count is not None
                        else f"{gate} did not pass: "
                    )
                    + row.strip()[:200],
                )
        elif m := _P3_G2_ROW_RE.match(row):
            out["g2_steps"].append(
                {
                    "n_steps": int(m.group(1)),
                    "graph_p3_ms_per_step": round(float(m.group(2)), 4),
                    "per_dispatch_p3_ms_per_step": round(float(m.group(3)), 4),
                }
            )
        elif m := _P3_RUNS_RE.match(row):
            out["runs"], out["warmup"] = int(m.group(1)), int(m.group(2))
        elif m := _P3_CELL_RE.match(row):
            gen, arm, median, iqr, outliers, rate, verdict = m.groups()
            out["cells"].setdefault(gen, {})[P3_ARMS[arm]] = {
                "median_ms": round(float(median), 3),
                "rel_iqr_pct": round(float(iqr), 4),
                "outliers": int(outliers),
                "decode_tok_per_s": round(float(rate), 2),
                "iqr_verdict": verdict,
            }
        elif m := _P3_DONE_RE.match(row):
            out["done"] = m.group(1)
    if out["n_prompt"] is None:
        raise ProbeError("engine_no_timing", "the driver printed no checkpoint header")
    for gate in ("G0", "G1", "G2"):
        if gate not in out["gates"]:
            raise ProbeError("engine_no_timing", f"the driver printed no {gate} RESULT line")
    for gen in cfg.P3_GEN_LENGTHS:
        if "graph_p3" not in out["cells"].get(str(gen), {}):
            raise ProbeError(
                "engine_no_timing", f"the driver printed no gen {gen} graph-p3 throughput line"
            )
    if out["runs"] is None:
        raise ProbeError("engine_no_timing", "the driver printed no throughput header")
    out["stdout_tail"] = _last_line(stdout)
    return out


def p3_cells(parsed: Mapping[str, Any], *, vram_peak_bytes: int | None) -> dict[str, Any]:
    """The driver's throughput table as lane A's cells (`runs["64"]`, `runs["256"]`): the cell's
    summary carries the `graph-p3` arm's median rate, its rel IQR and outlier census, the 16
    oracle-checked tokens, and the other two arms beside it. The driver prints one median per
    cell, not the runs, so `timed` is empty and the per-run lists are None; the prefill is
    outside every timed window, so prefill and time to first token are None."""
    tokens = campaign_oracle_tokens()
    cells: dict[str, Any] = {}
    for gen in cfg.P3_GEN_LENGTHS:
        arms = dict(parsed["cells"].get(str(gen)) or {})
        subject = arms.pop("graph_p3")
        cells[str(gen)] = {
            "gen": gen,
            "warmup": None,
            "warmup_excluded": True,
            "warmup_runs": parsed.get("warmup"),
            "timed": [],
            "timed_wall_s": None,
            "summary": {
                "n_runs": parsed["runs"],
                "decode_tok_per_s": subject["decode_tok_per_s"],
                "decode_tok_per_s_runs": None,
                "prefill_tok_per_s": None,
                "prefill_tok_per_s_runs": None,
                "ttft_ms": None,
                "ttft_ms_runs": None,
                "tokens": tokens,
                "runs_agree": None,
                "vram_peak_bytes": vram_peak_bytes,
                "median_ms": subject["median_ms"],
                "rel_iqr_pct": subject["rel_iqr_pct"],
                "outliers": subject["outliers"],
                "iqr_verdict": subject["iqr_verdict"],
                "arms": arms,
            },
        }
    return cells


def parse_llama_version(text: str) -> dict[str, Any]:
    """`llama-server --version` prints `version: 10210 (000547513f)`; both parts, when found."""
    match = _LLAMA_VERSION_RE.search(str(text or ""))
    line = next((row.strip() for row in str(text or "").splitlines() if "version:" in row), None)
    return {
        "line": line,
        "build_number": int(match.group(1)) if match else None,
        "commit": match.group(2).lower() if match else None,
    }


def llama_run_from_completion(
    payload: Mapping[str, Any], *, expected_n_prompt: int, gen: int
) -> dict[str, Any]:
    """One `/completion` answer as a run's facts, fail-closed on what the protocol needs.

    `timings.predicted_per_second` is llama.cpp's own decode rate (its `predicted_n` tokens
    over its generation window), `prompt_per_second` its prefill rate and `prompt_ms` the time
    to the first token; the run is refused when the server processed a different number of
    prompt tokens than it was sent (a BOS insertion or a cache hit would change the race) or
    returned no token ids.
    """
    timings = payload.get("timings")
    if not isinstance(timings, Mapping):
        raise ProbeError("llama_timings_missing", "the completion carried no timings block")
    needed = ("prompt_n", "prompt_ms", "prompt_per_second", "predicted_n", "predicted_ms")
    missing = [key for key in needed if not isinstance(timings.get(key), int | float)]
    if missing:
        raise ProbeError("llama_timings_missing", f"timings lack {', '.join(missing)}")
    raw_tokens = payload.get("tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise ProbeError(
            "llama_tokens_missing", "the completion returned no token ids (return_tokens)"
        )
    try:
        tokens = [int(t) for t in raw_tokens]
    except (TypeError, ValueError) as exc:
        raise ProbeError("llama_tokens_missing", "the token ids are not integers") from exc
    n_prompt = int(timings["prompt_n"])
    cached = payload.get("tokens_cached")
    if isinstance(cached, int) and not isinstance(cached, bool) and cached > 0:
        raise ProbeError(
            "llama_prompt_cached", f"{cached} prompt tokens were reused from the server's cache"
        )
    if n_prompt != int(expected_n_prompt):
        raise ProbeError(
            "llama_prompt_mismatch",
            f"llama-server processed {n_prompt} prompt tokens, {expected_n_prompt} were sent",
        )
    stop_type = str(payload.get("stop_type") or "")
    if len(tokens) != int(gen) and stop_type != "eos":
        raise ProbeError(
            "llama_short_generation",
            f"{len(tokens)} tokens returned for n_predict {gen} (stop_type {stop_type or '?'})",
        )
    prompt_ms = float(timings["prompt_ms"])
    predicted_ms = float(timings["predicted_ms"])
    predicted_n = int(timings["predicted_n"])
    rate = timings.get("predicted_per_second")
    if not isinstance(rate, int | float):
        rate = predicted_n / (predicted_ms / 1000.0) if predicted_ms > 0 else None
    return {
        "gen": int(gen),
        "tokens": tokens,
        "n_prompt": n_prompt,
        "n_gen": len(tokens),
        "predicted_n": predicted_n,
        "predicted_ms": round(predicted_ms, 3),
        "prefill_ms": round(prompt_ms, 3),
        "prefill_tok_per_s": round(float(timings["prompt_per_second"]), 2),
        "decode_tok_per_s": None if rate is None else round(float(rate), 2),
        "ttft_ms": round(prompt_ms, 3),
        "stop_type": stop_type or None,
        "stopped_on_eos": stop_type == "eos",
        "timings": {k: timings[k] for k in sorted(timings)},
    }


# ---------------------------------------------------------------------------
# Runs, medians, identity
# ---------------------------------------------------------------------------


def _median(values: Iterable[Any]) -> float | None:
    numbers = [float(v) for v in values if isinstance(v, int | float) and not isinstance(v, bool)]
    return round(statistics.median(numbers), 2) if numbers else None


def run_summary(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The median over a cell's timed runs, in the fields every lane reports.

    `tokens` are the first timed run's; `runs_agree` says whether every run produced the same
    ids (greedy decoding should). Device memory is the largest peak any run saw.
    """
    decode = [r.get("decode_tok_per_s") for r in runs]
    prefill = [r.get("prefill_tok_per_s") for r in runs]
    ttft = [r.get("ttft_ms") for r in runs]
    peaks = [
        r.get("vram_peak_bytes")
        for r in runs
        if isinstance(r.get("vram_peak_bytes"), int)
        and not isinstance(r.get("vram_peak_bytes"), bool)
    ]
    tokens = [list(r.get("tokens") or []) for r in runs]
    return {
        "n_runs": len(runs),
        "decode_tok_per_s": _median(decode),
        "decode_tok_per_s_runs": [None if v is None else round(float(v), 2) for v in decode],
        "prefill_tok_per_s": _median(prefill),
        "prefill_tok_per_s_runs": [None if v is None else round(float(v), 2) for v in prefill],
        "ttft_ms": _median(ttft),
        "ttft_ms_runs": [None if v is None else round(float(v), 3) for v in ttft],
        "tokens": tokens[0] if tokens else [],
        "runs_agree": bool(tokens) and all(t == tokens[0] for t in tokens),
        "vram_peak_bytes": max(peaks) if peaks else None,
    }


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
    oracle_prefix: int = cfg.ORACLE_PREFIX,
) -> dict[str, Any]:
    """`verdict: 64/64`, or the first divergent index with the reference's top-2 logit margin
    there (how confidently the reference chose its token: a near-tie is a different finding
    from a disagreement at a clear margin). `oracle` is the published gate's form, the first
    `oracle_prefix` tokens: `16/16`."""
    cmp = compare_tokens(native, reference)
    n_ref = len(reference)
    n_oracle = min(oracle_prefix, n_ref)
    report: dict[str, Any] = {
        "native_tokens": [int(t) for t in native],
        "reference_tokens": [int(t) for t in reference],
        "native_decoded": native_decoded,
        "reference_decoded": reference_decoded,
        **cmp,
        "verdict": f"{cmp['prefix_match']}/{n_ref}",
        "oracle": f"{min(cmp['prefix_match'], n_oracle)}/{n_oracle}",
        "oracle_match": n_oracle > 0 and cmp["prefix_match"] >= n_oracle,
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
    """Per-step figures defined identically for the Hub and transformers lanes.

    `steady_step_ms` is the mean of steps `steady_from` to n and `steady_tok_per_s` is 1000
    over it: the per-token cost once the lane is past its first step and its warm-up.
    `decode_tok_per_s` is the published definition shared with the engine: the tokens after
    the first over the sum of their steps. `all_steps_tok_per_s` is n tokens over the sum of
    all n steps. Fewer than `steady_from` steps give no steady figure.
    """
    steps = [float(s) for s in step_ms]
    n = len(steps)
    total = sum(steps)
    steady = steps[steady_from - 1 :] if n >= steady_from else []
    steady_mean = sum(steady) / len(steady) if steady else None
    after_first = sum(steps[1:])
    return {
        "n_tokens": n,
        "step_ms": [round(s, 2) for s in steps],
        "first_step_ms": round(steps[0], 2) if steps else None,
        "mean_step_ms": round(total / n, 2) if n else None,
        "steady_steps": f"{steady_from}-{n}" if steady else None,
        "steady_step_ms": None if steady_mean is None else round(steady_mean, 2),
        "steady_tok_per_s": (
            round(1000.0 / steady_mean, 2) if steady_mean is not None and steady_mean > 0 else None
        ),
        "decode_tok_per_s": (
            round((n - 1) / (after_first / 1000.0), 2) if n >= 2 and after_first > 0 else None
        ),
        "all_steps_tok_per_s": round(n / (total / 1000.0), 2) if n and total > 0 else None,
    }


def decode_timings(open_s: float | None, step_ms: Sequence[float]) -> dict[str, Any]:
    """What one Hub `DecodeSession` measured, named for what it is.

    `open_s` is the session open: the f64 blob uploaded to the device as f32 and the prompt
    prefilled, after which the first token is already computed (its step is sub-millisecond, so
    `ttft_s`, open plus the first step, is the session open). `tok_per_s` is the same figure as
    `decode_tok_per_s`, kept under the name earlier records used.
    """
    out = step_timings(step_ms)
    steps = out["step_ms"]
    out["open_s"] = None if open_s is None else round(float(open_s), 2)
    out["ttft_s"] = None
    out["ttft_is_session_open"] = True
    if steps and open_s is not None:
        out["ttft_s"] = round(float(open_s) + float(step_ms[0]) / 1000.0, 2)
    out["tok_per_s"] = out["decode_tok_per_s"]
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
# The lanes: one view for the five columns
# ---------------------------------------------------------------------------

LANE_IDS: tuple[str, ...] = ("engine", "llama", "hub", *cfg.BASELINE_DTYPES)
RACE_LANES: tuple[str, ...] = ("engine", "llama")
SECONDARY_LANES: tuple[str, ...] = ("hub", *cfg.BASELINE_DTYPES)
LANE_TITLES: dict[str, str] = {
    "engine": "Algenta engine",
    "llama": "llama.cpp",
    "hub": "Hub kernels",
    "float32": "transformers CUDA",
    "float16": "transformers CUDA",
}
LANE_PRECISION: dict[str, str] = {
    "engine": "f32 resident weights, per-token dispatch",
    "llama": "F16 GGUF",
    "hub": "f32 resident, uploaded from the f64 blob",
    "float32": "float32",
    "float16": "float16",
}
LANE_PHASE: dict[str, str] = {
    "engine": "engine",
    "llama": "llama",
    "hub": "decode",
    "float32": "baseline",
    "float16": "baseline",
}
OK_LANE, UNAVAILABLE, ABSENT_LANE, PENDING_LANE = "ok", "unavailable", "absent", "pending"
ENGINE_SESSION_NOTE = (
    "the wheel's certified conformance engine; the published cell ran the packed-int8 "
    "captured-graph session"
)
#: Lane A when `ALGENTA_CUDA_ENGINE` selects the packed-int8 graph driver: the column header's
#: precision and the note under it, filled with the engine manifest's build facts.
P3_LANE_PRECISION = "packed-int8 resident weights, captured-graph decode"
P3_SESSION_NOTE = (
    "the published cell's session: packed-int8 captured-graph, {target}, built {date} from "
    "{commit}; gen=64 and gen=256 fixed by the driver, its 16-token oracle gate and 3 x 128-step "
    "graph-vs-per-dispatch identity gate passed before any figure"
)
P3_TTFT_NOTE = (
    "not measured by this driver: the prefill is outside every timed window and it prints no "
    "prefill time"
)
P3_LOAD_LABEL = (
    "one-time load: the f64 blob read, the f32 half and the packed-int8 twins uploaded, paid "
    "once per launch (before the gates and every cell)"
)
P3_VRAM_NOTE = (
    "peak device memory used while the driver ran its gates and cells (nvidia-smi), minus the "
    "idle baseline"
)


def _lane_base(lane_id: str) -> dict[str, Any]:
    return {
        "id": lane_id,
        "title": LANE_TITLES.get(lane_id, lane_id),
        "precision": LANE_PRECISION.get(lane_id, lane_id),
        "status": ABSENT_LANE,
        "code": None,
        "message": None,
    }


def _phase_state(lane: dict[str, Any], rec: Mapping[str, Any] | None) -> dict[str, Any]:
    """A lane without data: unavailable with the phase's code, pending, or absent."""
    if rec is None:
        lane["message"] = "not in this record"
        return lane
    status = rec.get("status")
    if status in (ERROR, SKIPPED):
        lane.update(status=UNAVAILABLE, code=rec.get("code"), message=rec.get("message"))
    elif status in (PENDING, RUNNING):
        lane["status"] = PENDING_LANE
    else:
        lane["message"] = "the phase reported no data"
    return lane


def identity_report(
    tokens: Sequence[int] | None, reference: Mapping[str, Any] | None, decoded: str | None
) -> dict[str, Any] | None:
    if not reference or tokens is None:
        return None
    return parity_report(
        list(tokens),
        list(reference.get("tokens") or []),
        reference_margins=reference.get("top2_margins"),
        native_decoded=decoded,
        reference_decoded=reference.get("decoded"),
    )


def _cell_summary(block: Mapping[str, Any], gen: int) -> dict[str, Any] | None:
    runs = block.get("runs")
    if not isinstance(runs, Mapping):
        return None
    cell = runs.get(str(gen))
    if not isinstance(cell, Mapping):
        return None
    summary = cell.get("summary")
    return dict(summary) if isinstance(summary, Mapping) else None


def _prefix_identity(
    tokens: Sequence[int] | None, reference: Mapping[str, Any] | None, decoded: str | None
) -> dict[str, Any] | None:
    """Identity of a lane that prints only the first tokens it verified: those tokens against
    the reference's first as many, so `full_match` says whether every printed token agrees."""
    if not reference or tokens is None:
        return None
    ref_tokens = list(reference.get("tokens") or [])
    n = min(len(tokens), len(ref_tokens))
    report = parity_report(
        list(tokens)[:n],
        ref_tokens[:n],
        reference_margins=reference.get("top2_margins"),
        native_decoded=decoded,
        reference_decoded=reference.get("decoded"),
    )
    report["reference_tokens_total"] = len(ref_tokens)
    report["note"] = (
        f"the driver checks and prints its first {len(tokens)} tokens (the oracle gate); "
        "the longer streams it times are not printed"
    )
    return report


def _p3_engine_lane(
    lane: dict[str, Any], block: Mapping[str, Any], body: Mapping[str, Any]
) -> dict[str, Any]:
    """Lane A when the packed-int8 graph driver ran: the same fields, filled from its record
    (`probe.run_p3_engine`), with the driver's own definitions named in the notes."""
    engine = block.get("engine") or {}
    hero = _cell_summary(block, cfg.GEN_TOKENS) or {}
    long_cell = _cell_summary(block, cfg.GEN_TOKENS_LONG)
    gates = block.get("gates") or {}
    built = str(engine.get("built_utc") or "")[:10] or "?"
    commit = str(engine.get("source_commit") or "")[:12] or "?"
    tokens = list(block.get("tokens") or [])
    lane["precision"] = P3_LANE_PRECISION
    load_ms = block.get("load_ms")
    iqr = hero.get("rel_iqr_pct")
    lane.update(
        status=OK_LANE,
        protocol=cfg.P3_ENGINE_NAME,
        prompt_fixture=block.get("prompt_fixture"),
        stack=" · ".join(
            part
            for part in (
                f"{cfg.P3_ENGINE_NAME} {str(engine.get('sha256') or '')[:12]}".strip(),
                str(engine.get("cuda_target") or ""),
                f"mojo {engine.get('mojo_version')}" if engine.get("mojo_version") else "",
                f"built {built} from {commit}",
            )
            if part
        ),
        session_note=P3_SESSION_NOTE.format(
            target=engine.get("cuda_target") or "?", date=built, commit=commit
        ),
        tokens=tokens,
        tokens_verified=block.get("tokens_verified"),
        decoded=block.get("decoded"),
        n_gen=len(tokens),
        n_runs=hero.get("n_runs"),
        runs_agree=None,
        iqr_note=(
            None
            if iqr is None
            else f"rel IQR {float(iqr):.2f} % ({hero.get('iqr_verdict')} at the frozen 5 %)"
        ),
        decode_tok_per_s=hero.get("decode_tok_per_s"),
        decode_tok_per_s_long=None if long_cell is None else long_cell.get("decode_tok_per_s"),
        long_gen_skipped=None,
        prefill_tok_per_s=None,
        prefill_note=P3_TTFT_NOTE,
        ttft_ms=None,
        ttft_note=P3_TTFT_NOTE,
        load_s=None if not isinstance(load_ms, int | float) else round(float(load_ms) / 1000.0, 2),
        load_label=P3_LOAD_LABEL,
        vram_bytes=block.get("vram_peak_bytes"),
        vram_note=P3_VRAM_NOTE,
        gates={name: bool(rec.get("passed")) for name, rec in gates.items()},
        arms=hero.get("arms"),
        identity=_prefix_identity(tokens, body.get("reference"), block.get("decoded")),
        build={
            "engine": cfg.P3_ENGINE_NAME,
            "session": engine.get("session") or cfg.P3_ENGINE_SESSION,
            "cuda_target": engine.get("cuda_target"),
            "sha256": engine.get("sha256"),
            "source": engine.get("source"),
            "source_commit": engine.get("source_commit"),
            "built_utc": engine.get("built_utc"),
            "mojo_version": engine.get("mojo_version"),
            "comptime_defines": list(engine.get("comptime_defines") or []),
            "kernel_variant": block.get("kernel_variant"),
            "graph_nodes_per_token": block.get("graph_nodes"),
            "resolved_from": engine.get("resolved_from"),
            "runs_per_cell": hero.get("n_runs"),
        },
    )
    return lane


def engine_lane(body: Mapping[str, Any]) -> dict[str, Any]:
    lane = _lane_base("engine")
    block = body.get("engine")
    if not isinstance(block, Mapping) or not block:
        return _phase_state(lane, (body.get("phases") or {}).get("engine"))
    if block.get("protocol") == cfg.P3_ENGINE_NAME:
        return _p3_engine_lane(lane, block, body)
    engine = block.get("engine") or {}
    long_cell = _cell_summary(block, cfg.GEN_TOKENS_LONG)
    lane.update(
        status=OK_LANE,
        protocol=cfg.ENGINE_NAME,
        prompt_fixture=block.get("prompt_fixture"),
        stack=" · ".join(
            part
            for part in (
                f"{cfg.ENGINE_WHEEL} {engine.get('wheel_version') or ''}".strip(),
                str(engine.get("cuda_target") or ""),
                f"{cfg.ENGINE_NAME} {str(engine.get('sha256') or '')[:12]}".strip(),
            )
            if part
        ),
        session_note=ENGINE_SESSION_NOTE,
        tokens=list(block.get("tokens") or []),
        decoded=block.get("decoded"),
        n_gen=len(block.get("tokens") or []),
        n_runs=(block.get("runs") or {})
        .get(str(cfg.GEN_TOKENS), {})
        .get("summary", {})
        .get("n_runs"),
        runs_agree=block.get("runs_agree"),
        decode_tok_per_s=block.get("decode_tok_per_s"),
        decode_tok_per_s_long=None if long_cell is None else long_cell.get("decode_tok_per_s"),
        long_gen_skipped=block.get("long_gen_skipped"),
        prefill_tok_per_s=block.get("prefill_tok_per_s"),
        ttft_ms=block.get("ttft_ms"),
        ttft_note="the prefill of the prompt; the first token is computed by it",
        load_s=None,
        load_label="weights loaded and uploaded by every run, before the timed prefill",
        vram_bytes=block.get("vram_peak_bytes"),
        vram_note="peak device memory used during the run (nvidia-smi), minus the idle baseline",
        identity=identity_report(block.get("tokens"), body.get("reference"), block.get("decoded")),
        build={
            "wheel": f"{cfg.ENGINE_WHEEL}=={engine.get('wheel_version') or '?'}",
            "cuda_target": engine.get("cuda_target"),
            "sha256": engine.get("sha256"),
            "source": engine.get("source"),
            "comptime_defines": list(engine.get("comptime_defines") or []),
            "resolved_from": engine.get("resolved_from"),
        },
    )
    return lane


def llama_lane(body: Mapping[str, Any]) -> dict[str, Any]:
    lane = _lane_base("llama")
    block = body.get("llama")
    if not isinstance(block, Mapping) or not block:
        return _phase_state(lane, (body.get("phases") or {}).get("llama"))
    version = block.get("version") or {}
    gguf = block.get("gguf") or {}
    long_cell = _cell_summary(block, cfg.GEN_TOKENS_LONG)
    lane.update(
        status=OK_LANE,
        stack=" · ".join(
            part
            for part in (
                f"llama.cpp {str(version.get('commit') or cfg.LLAMA_CPP_COMMIT)[:10]}",
                f"build {version.get('build_number')}" if version.get("build_number") else "",
                f"GGML_CUDA sm_{block.get('cuda_architectures') or cfg.LLAMA_CUDA_ARCHITECTURES}",
                f"{gguf.get('outtype') or cfg.LLAMA_GGUF_OUTTYPE} GGUF",
            )
            if part
        ),
        tokens=list(block.get("tokens") or []),
        decoded=block.get("decoded"),
        n_gen=len(block.get("tokens") or []),
        n_runs=(block.get("runs") or {})
        .get(str(cfg.GEN_TOKENS), {})
        .get("summary", {})
        .get("n_runs"),
        runs_agree=block.get("runs_agree"),
        decode_tok_per_s=block.get("decode_tok_per_s"),
        decode_tok_per_s_long=None if long_cell is None else long_cell.get("decode_tok_per_s"),
        long_gen_skipped=block.get("long_gen_skipped"),
        prefill_tok_per_s=block.get("prefill_tok_per_s"),
        ttft_ms=block.get("ttft_ms"),
        ttft_note="llama-server's prompt_ms: the prompt processed, the first token sampled",
        load_s=block.get("ready_s"),
        load_label="llama-server start to /health ok (the GGUF loaded once, before every run)",
        vram_bytes=block.get("vram_peak_bytes"),
        vram_note=(
            "peak device memory used while the server ran (nvidia-smi), minus the idle baseline"
        ),
        identity=identity_report(block.get("tokens"), body.get("reference"), block.get("decoded")),
        build={
            "commit": version.get("commit") or cfg.LLAMA_CPP_COMMIT,
            "build_number": version.get("build_number"),
            "version_line": version.get("line"),
            "cuda_architectures": block.get("cuda_architectures"),
            "gguf_bytes": gguf.get("bytes"),
            "server_argv": list(block.get("argv") or []),
        },
    )
    return lane


def hub_lane(body: Mapping[str, Any]) -> dict[str, Any]:
    """The Hub kernels' `DecodeSession` lane, from `decode`; earlier records (one session, no
    `runs`) render through the same figures."""
    lane = _lane_base("hub")
    decode = body.get("decode")
    if not isinstance(decode, Mapping) or not decode:
        return _phase_state(lane, (body.get("phases") or {}).get("decode"))
    kernel = body.get("kernel") or decode
    timings = decode_timings(decode.get("open_s"), decode.get("step_ms") or [])
    steps = timings["step_ms"]
    taken = decode.get("device_taken_bytes")
    start, after_open = decode.get("gpu_free_bytes_start"), decode.get("gpu_free_bytes_after_open")
    if taken is None and isinstance(start, int) and isinstance(after_open, int):
        taken = max(0, start - after_open)
    revision = str(kernel.get("revision") or "")
    summary = _cell_summary(decode, cfg.GEN_TOKENS)
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
        n_gen=len(decode.get("tokens") or []),
        n_runs=None if summary is None else summary.get("n_runs"),
        runs_agree=decode.get("runs_agree"),
        parity=body.get("parity"),
        decode_tok_per_s=(
            decode.get("decode_tok_per_s")
            if decode.get("decode_tok_per_s") is not None
            else timings["decode_tok_per_s"]
        ),
        decode_tok_per_s_long=None,
        prefill_tok_per_s=None,
        prefill_note="the prefill runs inside the session open, not timed on its own",
        ttft_ms=(
            decode.get("ttft_ms")
            if decode.get("ttft_ms") is not None
            else _session_ttft_ms(decode.get("open_s"), decode.get("step_ms") or [])
        ),
        ttft_note="= session open: the f64 blob uploaded as f32, then the prompt prefilled",
        load_s=timings["open_s"],
        load_label="session open (upload and prefill), paid by every run",
        first_step_ms=timings["first_step_ms"],
        first_step_note=(
            "prefill done at session open"
            + (f"; step 2 ({steps[1]:.1f} ms) is the warm-up step" if len(steps) > 1 else "")
        ),
        steady_steps=timings["steady_steps"],
        steady_step_ms=timings["steady_step_ms"],
        steady_tok_per_s=timings["steady_tok_per_s"],
        all_steps_tok_per_s=timings["all_steps_tok_per_s"],
        step_ms=steps,
        vram_bytes=taken,
        vram_note="taken on the device at session open (free memory before minus after)",
        identity=identity_report(
            decode.get("tokens"), body.get("reference"), decode.get("decoded")
        ),
        build={
            "kernel_revision": revision or None,
            "mojo_version": kernel.get("mojo_version"),
            "library": kernel.get("selected_library"),
            "backend": kernel.get("backend"),
        },
    )
    return lane


def _session_ttft_ms(open_s: Any, step_ms: Sequence[float]) -> float | None:
    """Session open plus the first step, in milliseconds, from the raw values."""
    if not isinstance(open_s, int | float) or isinstance(open_s, bool):
        return None
    first = float(step_ms[0]) if step_ms else 0.0
    return round(float(open_s) * 1000.0 + first, 1)


def transformers_lane(dtype: str, body: Mapping[str, Any]) -> dict[str, Any]:
    lane = _lane_base(dtype)
    block = body.get("baseline")
    if not isinstance(block, Mapping):
        return _phase_state(lane, (body.get("phases") or {}).get("baseline"))
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
    timings = (
        baseline_timings(data.get("load_s"), data.get("step_ms") or [])
        if data.get("step_ms")
        else (data.get("timings") or {})
    )
    warm = data.get("warmup_timings") or {}
    n_prompt = block.get("n_prompt")
    summary = _cell_summary(data, cfg.GEN_TOKENS)
    warm_note = ""
    if warm.get("ttft_s") is not None:
        warm_note = f"; one warm-up generate excluded (first token {warm['ttft_s']:.3f} s)"
    ttft_ms = data.get("ttft_ms")
    if ttft_ms is None and timings.get("ttft_s") is not None:
        ttft_ms = round(float(timings["ttft_s"]) * 1000.0, 1)
    prefill = data.get("prefill_tok_per_s")
    if prefill is None and ttft_ms and n_prompt:
        prefill = round(float(n_prompt) / (float(ttft_ms) / 1000.0), 2)
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
        n_gen=len(data.get("tokens") or []),
        n_runs=None if summary is None else summary.get("n_runs"),
        runs_agree=data.get("runs_agree"),
        parity=data.get("parity"),
        decode_tok_per_s=(
            data.get("decode_tok_per_s")
            if data.get("decode_tok_per_s") is not None
            else timings.get("decode_tok_per_s")
        ),
        decode_tok_per_s_long=None,
        prefill_tok_per_s=prefill,
        ttft_ms=ttft_ms,
        ttft_note=(
            f"step 1 of the timed generate: the prefill of the {n_prompt} prompt tokens"
            if n_prompt
            else "step 1 of the timed generate: the prefill"
        ),
        load_s=timings.get("load_s"),
        load_label="model load: from_pretrained, then moved to the device (once per lane)",
        first_step_ms=timings.get("first_step_ms"),
        first_step_note="step 1 is the prefill" + warm_note,
        steady_steps=timings.get("steady_steps"),
        steady_step_ms=timings.get("steady_step_ms"),
        steady_tok_per_s=timings.get("steady_tok_per_s"),
        all_steps_tok_per_s=timings.get("all_steps_tok_per_s"),
        step_ms=timings.get("step_ms"),
        vram_bytes=data.get("device_taken_bytes"),
        vram_note=(
            "taken on the device after the load (free memory before minus after); "
            "peak allocated by torch over the load and the generates"
        ),
        peak_allocated_bytes=data.get("peak_allocated_bytes"),
        identity=identity_report(data.get("tokens"), body.get("reference"), data.get("decoded")),
        build={
            "transformers": block.get("transformers"),
            "torch": block.get("torch"),
            "cuda": block.get("cuda"),
            "dtype": data.get("dtype"),
            "model_dtype": data.get("model_dtype"),
        },
    )
    return lane


def _ratio(a: Any, b: Any) -> float | None:
    if isinstance(a, int | float) and isinstance(b, int | float) and a > 0 and b > 0:
        return round(float(a) / float(b), 2)
    return None


def race_view(body: Mapping[str, Any]) -> dict[str, Any]:
    """The page's columns: the race (lanes A and B), the secondary rows (C, D) and the ratio.

    Every figure is the run's own measurement; a lane that could not run carries its code. The
    ratio is Algenta over llama.cpp on the gen=64 decode rate, reported only when both lanes ran
    and decoded the same tokens. `predates` is true for a record without the race stages.
    """
    engine = engine_lane(body)
    llama = llama_lane(body)
    secondary = [hub_lane(body)] + [transformers_lane(d, body) for d in cfg.BASELINE_DTYPES]
    same = None
    compared = None
    if engine["status"] == OK_LANE and llama["status"] == OK_LANE:
        e_tokens, l_tokens = list(engine["tokens"]), list(llama["tokens"])
        verified = engine.get("tokens_verified")
        if isinstance(verified, int) and not isinstance(verified, bool) and verified > 0:
            # the packed-int8 graph driver prints only the tokens its oracle checked: the two
            # lanes agree when llama.cpp's stream starts with exactly those
            compared = min(verified, len(e_tokens), len(l_tokens))
            same = compared > 0 and e_tokens[:compared] == l_tokens[:compared]
        else:
            compared = len(e_tokens)
            same = bool(e_tokens) and e_tokens == l_tokens
    ratio = {
        "same_tokens": same,
        "tokens_compared": compared,
        "decode_gen64": (
            _ratio(engine.get("decode_tok_per_s"), llama.get("decode_tok_per_s")) if same else None
        ),
        "decode_gen256": (
            _ratio(engine.get("decode_tok_per_s_long"), llama.get("decode_tok_per_s_long"))
            if same
            else None
        ),
        "prefill": (
            _ratio(engine.get("prefill_tok_per_s"), llama.get("prefill_tok_per_s"))
            if same
            else None
        ),
    }
    driver = body.get("driver") or {}
    phases = body.get("phases") or {}
    return {
        "gpu": driver.get("device_name") or (driver.get("nvidia_smi") or {}).get("name"),
        "predates": not any(name in phases for name in ("engine", "llama")),
        "reference_tokens": list((body.get("reference") or {}).get("tokens") or []) or None,
        "n_prompt": _record_n_prompt(body),
        "gen_tokens": len((body.get("reference") or {}).get("tokens") or []) or cfg.GEN_TOKENS,
        "gen_tokens_long": cfg.GEN_TOKENS_LONG,
        "runs": cfg.RUNS,
        "warmup_runs": cfg.WARMUP_RUNS,
        "race": [engine, llama],
        "secondary": secondary,
        "ratio": ratio,
        "published": published_facts(),
    }


def _record_n_prompt(body: Mapping[str, Any]) -> int:
    model = body.get("model") or {}
    n_prompt = model.get("n_prompt")
    if isinstance(n_prompt, int) and not isinstance(n_prompt, bool) and n_prompt > 0:
        return n_prompt
    ids = model.get("prompt_ids") or (body.get("decode") or {}).get("prompt_ids") or []
    return len(ids) if isinstance(ids, list) and ids else cfg.PROMPT_TOKENS


def published_facts() -> dict[str, Any]:
    serving = cfg.PUBLISHED_SERVING_L4
    throughput = cfg.PUBLISHED_THROUGHPUT_L4
    return {
        "date": cfg.PUBLISHED_DATE,
        "hardware": cfg.PUBLISHED_HARDWARE,
        "serving": {
            **serving,
            "llama_gen64_implied": round(serving["algenta_gen64"] / serving["ratio_gen64"], 1),
            "llama_gen256_implied": round(serving["algenta_gen256"] / serving["ratio_gen256"], 1),
            "url": cfg.PUBLISHED_SERVING_URL,
        },
        "throughput": {
            **throughput,
            "ratio_gen64": _ratio(throughput["algenta_gen64"], throughput["llama_gen64"]),
            "ratio_gen256": _ratio(throughput["algenta_gen256"], throughput["llama_gen256"]),
            "url": cfg.PUBLISHED_THROUGHPUT_URL,
        },
    }


# ---------------------------------------------------------------------------
# The baseline block (lane D's stage report as `/health` shows it)
# ---------------------------------------------------------------------------


def lane_view(lane: Mapping[str, Any], reference: Mapping[str, Any] | None) -> dict[str, Any]:
    """One transformers lane as `/health` shows it: the stage's facts, its timings and its
    parity against the CPU reference once that has run. A lane that failed keeps only its code."""
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
    out["parity"] = identity_report(lane.get("tokens"), reference, lane.get("decoded"))
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


def _lane_evidence(lane: Mapping[str, Any]) -> dict[str, Any]:
    identity = lane.get("identity") or {}
    return {
        "status": lane.get("status"),
        "code": lane.get("code"),
        "protocol": lane.get("protocol"),
        "prompt_fixture": lane.get("prompt_fixture"),
        "tokens_verified": lane.get("tokens_verified"),
        "stack": lane.get("stack"),
        "decode_tok_per_s_gen64": lane.get("decode_tok_per_s"),
        "decode_tok_per_s_gen256": lane.get("decode_tok_per_s_long"),
        "prefill_tok_per_s": lane.get("prefill_tok_per_s"),
        "ttft_ms": lane.get("ttft_ms"),
        "vram_bytes": lane.get("vram_bytes"),
        "tokens": list(lane.get("tokens") or []),
        "runs_agree": lane.get("runs_agree"),
        "identity": identity.get("verdict"),
        "oracle": identity.get("oracle"),
        "build": lane.get("build"),
    }


def evidence_rows(body: Mapping[str, Any], view: Mapping[str, Any]) -> dict[str, Any]:
    """The evidence rows' fields, in the artifact's names, from this run's data."""
    driver = body.get("driver") or {}
    kernel = body.get("kernel") or {}
    convert = body.get("model") or {}
    decode = body.get("decode") or {}
    parity = body.get("parity") or {}
    engine, llama = view["race"]
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
        "GPU-SPACE-RACE-001": {
            "gpu": view.get("gpu"),
            "model": f"{cfg.MODEL_REPO}@{cfg.MODEL_REVISION[:12]}",
            "prompt_tokens": view.get("n_prompt"),
            "prompt_fixture": (body.get("pins") or {}).get("prompt_fixture"),
            "gen_tokens": cfg.GEN_TOKENS,
            "runs": cfg.RUNS,
            "warmup_runs": cfg.WARMUP_RUNS,
            "engine": _lane_evidence(engine),
            "llama": _lane_evidence(llama),
            "ratio_decode_gen64": (view.get("ratio") or {}).get("decode_gen64"),
            "ratio_decode_gen256": (view.get("ratio") or {}).get("decode_gen256"),
            "secondary": {lane["id"]: _lane_evidence(lane) for lane in view.get("secondary") or []},
            "published": view.get("published"),
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
    `race` is the page's view of the lanes, computed from the same facts.
    """

    def data_if_ok(name: str) -> dict[str, Any]:
        return machine.data(name) if machine.records[name].status == OK else {}

    driver = data_if_ok("driver")
    kernel = data_if_ok("kernel")
    convert = data_if_ok("convert")
    engine = data_if_ok("engine")
    llama = data_if_ok("llama")
    decode = data_if_ok("decode")
    reference = data_if_ok("reference")
    baseline = baseline_block(machine, reference) if "baseline" in machine.records else None
    parity = None
    if decode:
        parity = identity_report(decode.get("tokens"), reference, decode.get("decoded"))
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
            "weights_dtype": cfg.WEIGHTS_DTYPE,
            "prompt_cycle_ids": list(cfg.PROMPT_CYCLE_IDS),
            "prompt_tokens": cfg.PROMPT_TOKENS,
            "gen_tokens": cfg.GEN_TOKENS,
            "gen_tokens_long": cfg.GEN_TOKENS_LONG,
            "runs": cfg.RUNS,
            "warmup_runs": cfg.WARMUP_RUNS,
            "engine": f"{cfg.ENGINE_WHEEL}=={cfg.ENGINE_WHEEL_VERSION}/{cfg.ENGINE_NAME}",
            "engine_selected": selected_engine(),
            "engine_protocol": engine_protocol_of(selected_engine()) or cfg.ENGINE_NAME,
            "prompt_fixture": prompt_fixture_pin(),
            "llama_cpp_commit": cfg.LLAMA_CPP_COMMIT,
            "llama_cpp_build": cfg.LLAMA_CPP_BUILD,
            "llama_cuda_architectures": cfg.LLAMA_CUDA_ARCHITECTURES,
            "driver_floor": cfg.DRIVER_FLOOR_MAJOR,
            "hardware": cfg.HARDWARE,
        },
        "driver": driver or None,
        "kernel": kernel or None,
        "model": convert or None,
        "engine": engine or None,
        "llama": llama or None,
        "decode": (
            {**decode, "timings": decode_timings(decode.get("open_s"), decode.get("step_ms", []))}
            if decode
            else None
        ),
        "baseline": baseline,
        "reference": reference or None,
        "parity": parity,
        "versions": dict(versions or {}),
        "space": dict(space or {}),
        "build": dict(build or {}),
    }
    body["race"] = race_view(body)
    return body


def run_decision(view: Mapping[str, Any]) -> tuple[str, str]:
    """`ok` when every lane that ran decoded the reference's tokens, `parity_failed` when one
    diverged, `no_lane_ran` when none ran."""
    lanes = [*view.get("race", []), *view.get("secondary", [])]
    ran = [lane for lane in lanes if lane.get("status") == OK_LANE]
    if not ran:
        return "no_lane_ran", "no lane produced tokens; every lane carries its code"
    diverged = [
        lane["id"]
        for lane in ran
        if not isinstance(lane.get("identity"), Mapping) or not lane["identity"].get("full_match")
    ]
    if diverged:
        return "parity_failed", f"tokens differ from the reference in: {', '.join(diverged)}"
    names = ", ".join(lane["id"] for lane in ran)
    return "ok", f"{len(ran)} lane(s) decoded the reference's tokens: {names}"


def run_record(body: Mapping[str, Any]) -> dict[str, Any]:
    """`run.json`: the health body plus the evidence rows and the decision.

    Built by the `record` phase while it is the one running, so every phase that can stop the
    run must be `ok` and nothing may have failed; a soft phase (a lane) may be `error`, and its
    block then carries the code. The record says `status: ok`, `phase: done`.
    """
    phases = body.get("phases") or {}
    hard = [name for name in PHASES if name != "record" and name not in SOFT_PHASES]
    not_ok = [name for name in hard if (phases.get(name) or {}).get("status") != OK]
    if not_ok or body.get("failure"):
        raise ProbeError(
            "run_incomplete",
            "run.json is written only for a complete run; not ok: "
            f"{', '.join(not_ok) or 'failure'}",
        )
    view = body.get("race") if isinstance(body.get("race"), Mapping) else race_view(body)
    decision, reason = run_decision(view)
    return {
        **body,
        "status": OK,
        "phase": "done",
        "decision": decision,
        "decision_reason": reason,
        "evidence": evidence_rows(body, view),
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
