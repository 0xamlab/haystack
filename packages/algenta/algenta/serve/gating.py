"""`algenta serve`'s startup gate: declared facts in, typed refusals out.

One rule governs this whole module: **a backend is either accepted with its facts
stated, or refused with a typed reason. It is never silently swapped for another
one.** An operator who asks for `--backend cuda` on a host with no NVIDIA device
gets a refusal naming that fact and the range the backend requires — the same
vocabulary `scripts/algenta_conform.py` already publishes — and a non-zero exit
code. `--backend auto` *detects* (and says which backend it detected, and what
every other candidate answered); detection is not fallback, and the two are kept
distinguishable in the report so a reader can never confuse them.

Three fact classes are judged, in this order, and every refusal in every class is
collected rather than short-circuited on the first one (a caller fixing only the
first refusal and re-running is the exact loop a one-at-a-time gate traps people
in):

* **host** — the machine: platform, and for CUDA the NVIDIA driver interface
  (`nvidia-smi`, or `/proc/driver/nvidia/version` on a headless driver install),
  its version against the declared floor, and each device's compute capability.
* **engine** — the binary that would be launched: resolved, present, executable.
* **model** — the checkpoint's own declared facts, judged by
  `algenta.model_capabilities` (the capability table the conform CLI, the
  converter and the engine's own session-open gates all share), so the refusal
  text is the conformance system's, verbatim, and not a second opinion invented
  here.

Nothing in this module is a hand-maintained list. The backend names come from the
shipped runtime contract's engine-kernel inventory; the host requirements come
from `model_capabilities.BACKEND_HOST_REQUIREMENTS`; the model ranges come from
the capability table. A new backend appearing in the kernel inventory therefore
shows up here without an edit, and a test fails until its host requirements are
declared too.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "BACKEND_AUTO",
    "NvidiaHostFacts",
    "ServeGate",
    "ServeRefusal",
    "detect_backend",
    "gate_serve",
    "host_refusals",
    "model_refusals",
    "parse_version_tuple",
    "probe_nvidia_host",
    "published_backends",
    "serve_backends",
]

BACKEND_AUTO = "auto"

# The NVIDIA driver interface's two probe sources, in order. `nvidia-smi` is the
# full probe (driver version + every device + compute capability);
# `/proc/driver/nvidia/version` is the fallback that keeps a HEADLESS driver
# install gate-able — `ubuntu-drivers install --gpgpu` installs the driver
# without nvidia-smi (gitbook/engine/gpu-support.md says so explicitly), and on
# such a host "nvidia-smi is missing" must not read as "there is no GPU".
_NVIDIA_SMI_NAME = "nvidia-smi"
_NVIDIA_SMI_ENV = "ALGENTA_NVIDIA_SMI"
_PROC_NVIDIA_VERSION = Path("/proc/driver/nvidia/version")
_NVIDIA_QUERY = "--query-gpu=name,driver_version,compute_cap"
_NVIDIA_FORMAT = "--format=csv,noheader"
_PROBE_TIMEOUT_SECONDS = 15.0
# A driver version is a dotted number (580.173.02); matched rather than read by
# column so a differently-worded NVRM banner still yields the fact.
_DRIVER_VERSION_RE = re.compile(r"(\d{2,}(?:\.\d+)+)")


def published_backends() -> tuple[str, ...]:
    """The backends the shipped runtime contract publishes engine kernels for.

    Read from the contract's own engine-kernel inventory rather than declared
    here, so this gate cannot advertise a backend the shipped kernel surface does
    not carry (or hide one it does). Today that is ``("cuda", "metal")``.
    """
    from algenta.runtime_library_contract import engine_kernel_backends

    return tuple(engine_kernel_backends())


def serve_backends() -> tuple[str, ...]:
    """Every value `--backend` accepts: autodetect plus each published backend."""
    return (BACKEND_AUTO,) + published_backends()


def parse_version_tuple(raw: str | None) -> tuple[int, ...] | None:
    """``"580.173.02"`` -> ``(580, 173, 2)``; ``None``/unparsable -> ``None``.

    An unparsable version is reported as ``None``, never coerced to ``0``: a
    driver string this cannot read is an UNKNOWN fact, and guessing a value for
    it would turn "we could not read your driver version" into a refusal that
    names a version the host never reported.
    """
    if not isinstance(raw, str):
        return None
    parts: list[int] = []
    for chunk in raw.strip().split("."):
        if not chunk.isdigit():
            return None
        parts.append(int(chunk))
    return tuple(parts) if parts else None


def _at_least(found: tuple[int, ...] | None, floor: tuple[int, ...]) -> bool | None:
    """Three-valued compare: ``None`` when the found version is unknown.

    Pads to the floor's width so ``(580,)`` and ``(580, 0)`` compare equal — a
    driver that reports a bare major is not thereby older than the floor.
    """
    if found is None:
        return None
    width = max(len(found), len(floor))
    padded_found = found + (0,) * (width - len(found))
    padded_floor = floor + (0,) * (width - len(floor))
    return padded_found >= padded_floor


def _compute_cap_tuple(raw: str | None) -> tuple[int, ...] | None:
    """``"9.0"`` -> ``(9, 0)``. ``nvidia-smi`` prints ``N/A``/blank for a device
    it cannot classify; that is unknown, not zero."""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or text.upper() == "N/A":
        return None
    return parse_version_tuple(text)


@dataclass(frozen=True)
class NvidiaHostFacts:
    """What this host's NVIDIA driver interface declared, and how it was asked.

    ``device_count`` is ``None`` (not ``0``) when the probe source that answered
    cannot enumerate devices — the headless ``/proc/driver/nvidia/version``
    fallback knows the driver and nothing about the devices. An unknown count
    never produces a "no device" refusal: the engine's own ``has_accelerator()``
    is the authority on that, and this gate says so instead of guessing.
    """

    probed: bool
    probe_source: str | None = None
    probe_error: str | None = None
    driver_version: str | None = None
    driver_version_tuple: tuple[int, ...] | None = None
    device_count: int | None = None
    device_names: tuple[str, ...] = ()
    compute_capabilities: tuple[tuple[int, ...] | None, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "probed": self.probed,
            "probe_source": self.probe_source,
            "probe_error": self.probe_error,
            "driver_version": self.driver_version,
            "driver_version_tuple": list(self.driver_version_tuple)
            if self.driver_version_tuple is not None
            else None,
            "device_count": self.device_count,
            "device_names": list(self.device_names),
            "compute_capabilities": [
                list(cap) if cap is not None else None for cap in self.compute_capabilities
            ],
        }


_NO_DEVICE = NvidiaHostFacts(probed=False, probe_error="no NVIDIA driver interface on this host")


def _read_proc_driver_version(path: Path) -> NvidiaHostFacts | None:
    """The headless-driver fallback: the version out of ``/proc/driver/nvidia/version``.

    That file's shape is ``NVRM version: NVIDIA UNIX Open Kernel Module for
    x86_64  580.173.02  <build date>``, so the version is a dotted number
    somewhere on the NVRM line rather than a fixed column — matched, not
    positional, so a differently-worded driver banner still yields the fact.
    Device facts stay UNKNOWN here: this file knows the driver, not the devices.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if "NVRM version" not in line and "Kernel Module" not in line:
            continue
        match = _DRIVER_VERSION_RE.search(line)
        if match is None:
            continue
        version = match.group(1)
        return NvidiaHostFacts(
            probed=True,
            probe_source=str(path),
            driver_version=version,
            driver_version_tuple=parse_version_tuple(version),
        )
    return None


def probe_nvidia_host(
    *,
    smi_path: str | os.PathLike[str] | None = None,
    runner: Any = None,
    proc_version_path: Path | None = None,
) -> NvidiaHostFacts:
    """Ask this host what NVIDIA driver and devices it has. Never raises.

    ``runner`` and the two path parameters exist so a caller (and the tests) can
    state the facts without owning an NVIDIA device: ``runner`` is anything with
    ``subprocess.run``'s call shape.
    """
    resolved_smi = smi_path if smi_path is not None else os.environ.get(_NVIDIA_SMI_ENV)
    source: str | None
    if resolved_smi:
        smi = str(resolved_smi)
        source = f"{_NVIDIA_SMI_ENV}={smi}"
    else:
        found = shutil.which(_NVIDIA_SMI_NAME)
        smi = found if found else _NVIDIA_SMI_NAME
        source = _NVIDIA_SMI_NAME if found else None

    if source is not None:
        run = runner if runner is not None else subprocess.run
        smi_error: str | None
        try:
            completed = run(  # noqa: S603 - fixed argv, no shell, operator's own driver query
                [smi, _NVIDIA_QUERY, _NVIDIA_FORMAT],
                capture_output=True,
                text=True,
                timeout=_PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            completed = None
            smi_error = f"{type(exc).__name__}: {exc}"
        else:
            smi_error = None
        if completed is not None and completed.returncode == 0:
            return _parse_nvidia_smi_output(completed.stdout, source=source)
        detail = smi_error
        if detail is None and completed is not None:
            stderr = (completed.stderr or "").strip().splitlines()
            detail = f"exit {completed.returncode}" + (f": {stderr[-1][:160]}" if stderr else "")
        fallback = _read_proc_driver_version(proc_version_path or _PROC_NVIDIA_VERSION)
        if fallback is not None:
            return NvidiaHostFacts(
                probed=True,
                probe_source=fallback.probe_source,
                probe_error=f"{source} failed ({detail})",
                driver_version=fallback.driver_version,
                driver_version_tuple=fallback.driver_version_tuple,
            )
        return NvidiaHostFacts(
            probed=False,
            probe_source=source,
            probe_error=f"{source} failed ({detail})" if detail else f"{source} is not present",
        )

    fallback = _read_proc_driver_version(proc_version_path or _PROC_NVIDIA_VERSION)
    if fallback is not None:
        return fallback
    return _NO_DEVICE


def _parse_nvidia_smi_output(stdout: str, *, source: str) -> NvidiaHostFacts:
    """``name, driver_version, compute_cap`` CSV rows -> facts. A blank stdout is
    a driver with zero devices attached, which IS a fact (``device_count == 0``),
    distinct from a probe that could not run (``probed == False``)."""
    names: list[str] = []
    caps: list[tuple[int, ...] | None] = []
    driver_version: str | None = None
    for line in (stdout or "").splitlines():
        row = line.strip()
        if not row:
            continue
        columns = [column.strip() for column in row.split(",")]
        names.append(columns[0])
        if driver_version is None and len(columns) > 1 and columns[1]:
            driver_version = columns[1]
        caps.append(_compute_cap_tuple(columns[2] if len(columns) > 2 else None))
    return NvidiaHostFacts(
        probed=True,
        probe_source=source,
        driver_version=driver_version,
        driver_version_tuple=parse_version_tuple(driver_version),
        device_count=len(names),
        device_names=tuple(names),
        compute_capabilities=tuple(caps),
    )


@dataclass(frozen=True)
class ServeRefusal:
    """One exact reason this serve request cannot run on the requested backend.

    ``code`` is the stable machine-readable identifier (the thing an operator's
    script branches on); ``stage`` says which fact class produced it
    (``backend`` / ``host`` / ``engine`` / ``model``); ``fact``, ``value`` and
    ``supported`` carry the capability table's own vocabulary so a model refusal
    reads identically here and in `scripts/algenta_conform.py`'s output.
    """

    code: str
    stage: str
    detail: str
    fact: str | None = None
    value: Any = None
    supported: str | None = None
    remedy: str | None = None

    def message(self) -> str:
        parts = [f"{self.code}: {self.detail}"]
        if self.fact is not None:
            parts.append(f"fact: {self.fact}={self.value!r}")
        if self.supported:
            parts.append(f"supported: {self.supported}")
        if self.remedy:
            parts.append(f"remedy: {self.remedy}")
        return " | ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": self.stage,
            "detail": self.detail,
            "fact": self.fact,
            "value": self.value,
            "supported": self.supported,
            "remedy": self.remedy,
            "message": self.message(),
        }


def host_refusals(
    backend: str,
    host: NvidiaHostFacts | None = None,
    *,
    platform: str | None = None,
) -> list[ServeRefusal]:
    """Every host fact that stops `backend` from running here.

    ``host`` is only consulted for backends that declare a driver floor, so a
    Metal serve never shells out to nvidia-smi.
    """
    from algenta.model_capabilities import BACKEND_HOST_REQUIREMENTS

    requirements = BACKEND_HOST_REQUIREMENTS.get(backend)
    if requirements is None:
        return [
            ServeRefusal(
                code="unknown_backend",
                stage="backend",
                detail=f"{backend!r} is not a backend this build publishes",
                fact="backend",
                value=backend,
                supported=", ".join(serve_backends()),
            )
        ]

    refusals: list[ServeRefusal] = []
    current_platform = sys.platform if platform is None else platform
    platforms = tuple(requirements.get("platforms") or ())
    if platforms and not any(current_platform.startswith(name) for name in platforms):
        refusals.append(
            ServeRefusal(
                code="unsupported_platform",
                stage="host",
                detail=(
                    f"the {backend} engine binaries are built for "
                    f"{'/'.join(platforms)}; this host is {current_platform!r}"
                ),
                fact="platform",
                value=current_platform,
                supported="/".join(platforms),
            )
        )

    floor = requirements.get("min_driver_version")
    if floor is None:
        return refusals

    facts = _NO_DEVICE if host is None else host
    if not facts.probed:
        reason = facts.probe_error or "nvidia-smi and /proc/driver/nvidia/version both absent"
        refusals.append(
            ServeRefusal(
                code="no_nvidia_gpu",
                stage="host",
                detail=f"no NVIDIA driver interface answered on this host: {reason}",
                fact="nvidia_driver",
                value="absent",
                supported=f"NVIDIA driver >= {'.'.join(str(part) for part in floor)}",
                remedy=(
                    "install an NVIDIA driver and confirm `nvidia-smi` reports it; a headless "
                    "install (`ubuntu-drivers install --gpgpu`) also needs nvidia-utils, or "
                    "/proc/driver/nvidia/version must be readable"
                ),
            )
        )
        return refusals

    if facts.driver_version_tuple is not None:
        ok = _at_least(facts.driver_version_tuple, tuple(floor))
        if ok is False:
            refusals.append(
                ServeRefusal(
                    code="nvidia_driver_too_old",
                    stage="host",
                    detail=(
                        f"this host reports NVIDIA driver {facts.driver_version}, below the "
                        f"{'.'.join(str(part) for part in floor)} the {backend} engine requires"
                    ),
                    fact="driver_version",
                    value=facts.driver_version,
                    supported=f">= {'.'.join(str(part) for part in floor)}",
                    remedy="upgrade the NVIDIA driver; the engine dlopens libcuda.so.1 at runtime",
                )
            )
    elif facts.probe_error:
        # A driver version this could not read is UNKNOWN, not old: say which, and
        # name the source that answered, so the operator can fix the probe.
        refusals.append(
            ServeRefusal(
                code="nvidia_driver_version_unreadable",
                stage="host",
                detail=(
                    f"{facts.probe_source or 'the NVIDIA probe'} answered but reported no "
                    f"parseable driver version ({facts.probe_error})"
                ),
                fact="driver_version",
                value=facts.driver_version,
                supported=f">= {'.'.join(str(part) for part in floor)}",
            )
        )

    if facts.device_count == 0:
        refusals.append(
            ServeRefusal(
                code="no_nvidia_gpu",
                stage="host",
                detail=(
                    f"the NVIDIA driver ({facts.driver_version or 'version unknown'}) reports "
                    "zero devices on this host"
                ),
                fact="nvidia_device_count",
                value=0,
                supported="at least one NVIDIA device visible to the driver",
            )
        )

    cap_floor = requirements.get("min_compute_capability")
    if cap_floor:
        for index, cap in enumerate(facts.compute_capabilities):
            if cap is None:
                continue
            if _at_least(cap, tuple(cap_floor)) is False:
                name = (
                    facts.device_names[index]
                    if index < len(facts.device_names)
                    else f"device {index}"
                )
                refusals.append(
                    ServeRefusal(
                        code="nvidia_compute_capability_unsupported",
                        stage="host",
                        detail=(
                            f"{name} reports compute capability "
                            f"{'.'.join(str(part) for part in cap)}, below the "
                            f"{'.'.join(str(part) for part in cap_floor)} the pinned toolchain "
                            "builds for (it rejects sm_70 at compile time)"
                        ),
                        fact="compute_capability",
                        value=".".join(str(part) for part in cap),
                        supported=(
                            f">= {'.'.join(str(part) for part in cap_floor)} (Turing and newer)"
                        ),
                    )
                )
    return refusals


def model_refusals(backend: str, model: str | os.PathLike[str] | None) -> list[ServeRefusal]:
    """The capability table's own verdict on `model`, re-worded into nothing.

    Delegates to `model_capabilities.verdict_for_checkpoint` — the same call
    `scripts/algenta_conform.py` makes — so a checkpoint refused here is refused
    with the conformance system's exact fact/value/range, and a checkpoint that
    passes here passes the conform CLI too. No model is called by name and no
    family string is matched: two checkpoints with identical facts get identical
    verdicts.
    """
    if model is None:
        return []
    from algenta.model_capabilities import verdict_for_checkpoint

    path = Path(model)
    verdict = verdict_for_checkpoint(path, backend=backend)
    refusals: list[ServeRefusal] = []
    for entry in verdict.get("refusals") or ():
        if isinstance(entry, dict):
            refusals.append(
                ServeRefusal(
                    code="unsupported_model",
                    stage="model",
                    detail=str(entry.get("message") or entry.get("detail") or "unsupported model"),
                    fact=entry.get("fact"),
                    value=entry.get("value"),
                    supported=entry.get("supported"),
                )
            )
        else:
            # verdict_for_checkpoint's missing-config case carries pre-rendered
            # strings rather than structured refusals.
            refusals.append(
                ServeRefusal(
                    code="checkpoint_not_found",
                    stage="model",
                    detail=str(entry),
                    fact="config.json",
                    value="missing",
                    supported="a HuggingFace checkpoint snapshot (config.json + safetensors)",
                )
            )
    if verdict.get("status") == "supported_pending_probe":
        pending = verdict.get("pending_probe") or ()
        refusals.append(
            ServeRefusal(
                code="model_facts_unprobed",
                stage="model",
                detail=(
                    f"{path} declares supported facts but the tensor-level facts "
                    f"({', '.join(str(name) for name in pending)}) were never probed, because "
                    "no weights are present to probe"
                ),
                fact="probed",
                value=False,
                supported="a checkpoint directory carrying its safetensors weights",
                remedy="point --model at the full snapshot, or pass --allow-unprobed to accept "
                "the config-only verdict",
            )
        )
    return refusals


def detect_backend(
    *,
    platform: str | None = None,
    host: NvidiaHostFacts | None = None,
) -> tuple[str | None, dict[str, list[ServeRefusal]]]:
    """Pick the backend this host actually has, and report every candidate's verdict.

    Detection order is the published backend order, so a host that has both an
    NVIDIA device and Apple silicon resolves to whichever the contract lists
    first — and the report carries the other candidate's refusals, which is what
    makes `auto` detection rather than silent fallback: the choice is printed,
    never inferred by the reader.
    """
    current_platform = sys.platform if platform is None else platform
    report: dict[str, list[ServeRefusal]] = {}
    selected: str | None = None
    for backend in published_backends():
        facts = host
        if facts is None and _declares_driver_floor(backend):
            facts = probe_nvidia_host()
        refusals = host_refusals(backend, facts, platform=current_platform)
        report[backend] = refusals
        # Every candidate is judged, not just the ones up to the first success: a
        # report that stops early cannot show WHY the others were not chosen, and
        # "we picked this one" without "and that one answered X" is the shape a
        # silent fallback would have.
        if selected is None and not refusals:
            selected = backend
    return selected, report


def _declares_driver_floor(backend: str) -> bool:
    from algenta.model_capabilities import BACKEND_HOST_REQUIREMENTS

    return BACKEND_HOST_REQUIREMENTS.get(backend, {}).get("min_driver_version") is not None


@dataclass(frozen=True)
class ServeGate:
    """The whole startup verdict for one serve request.

    ``backend`` is what was ASKED for, ``resolved_backend`` what will actually be
    launched (identical unless ``backend == "auto"``), ``detection`` the
    per-candidate report `auto` produced, and ``refusals`` every reason this
    request cannot run. ``accepted`` is exactly ``not refusals`` — there is no
    third state and no warning-only path.
    """

    backend: str
    resolved_backend: str | None
    refusals: tuple[ServeRefusal, ...] = ()
    host: NvidiaHostFacts | None = None
    detection: dict[str, list[ServeRefusal]] = field(default_factory=dict)
    model: str | None = None
    model_verdict_status: str | None = None

    @property
    def accepted(self) -> bool:
        return not self.refusals

    def refusal_codes(self) -> tuple[str, ...]:
        return tuple(refusal.code for refusal in self.refusals)

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "resolved_backend": self.resolved_backend,
            "accepted": self.accepted,
            "refusals": [refusal.as_dict() for refusal in self.refusals],
            "host": self.host.as_dict() if self.host is not None else None,
            "detection": {
                name: [refusal.as_dict() for refusal in refusals]
                for name, refusals in sorted(self.detection.items())
            },
            "model": self.model,
            "model_verdict_status": self.model_verdict_status,
        }


def gate_serve(
    backend: str = BACKEND_AUTO,
    *,
    model: str | os.PathLike[str] | None = None,
    engine: Any = None,
    platform: str | None = None,
    host: NvidiaHostFacts | None = None,
    check_model: bool = True,
    allow_unprobed: bool = False,
) -> ServeGate:
    """Run the whole startup gate for one serve request. Pure: no launch, no conversion.

    ``engine`` is an object with ``engine_refusals(resolved_backend)`` (see
    `algenta.serve.engine`); it is injected so the gate stays testable with no
    binary on disk.
    """
    requested = backend if isinstance(backend, str) and backend else BACKEND_AUTO
    known = serve_backends()
    if requested not in known:
        return ServeGate(
            backend=requested,
            resolved_backend=None,
            refusals=(
                ServeRefusal(
                    code="unknown_backend",
                    stage="backend",
                    detail=f"--backend {requested!r} is not a value this build accepts",
                    fact="backend",
                    value=requested,
                    supported=", ".join(known),
                ),
            ),
        )

    detection: dict[str, list[ServeRefusal]] = {}
    if requested == BACKEND_AUTO:
        resolved, detection = detect_backend(platform=platform, host=host)
        if resolved is None:
            no_backend: list[ServeRefusal] = [
                ServeRefusal(
                    code="no_supported_backend",
                    stage="host",
                    detail=(
                        "no published backend's host requirements are met on this machine: "
                        + "; ".join(
                            f"{name}: {', '.join(r.code for r in items) or 'ok'}"
                            for name, items in sorted(detection.items())
                        )
                    ),
                    fact="backend",
                    value=None,
                    supported=", ".join(sorted(detection)),
                )
            ]
            for items in detection.values():
                no_backend.extend(items)
            return ServeGate(
                backend=requested,
                resolved_backend=None,
                refusals=tuple(no_backend),
                host=host,
                detection=detection,
                model=str(model) if model is not None else None,
            )
    else:
        resolved = requested

    probed_host = host
    if probed_host is None and _declares_driver_floor(resolved):
        probed_host = probe_nvidia_host()
    refusals: list[ServeRefusal] = []
    refusals.extend(host_refusals(resolved, probed_host, platform=platform))

    if engine is not None:
        refusals.extend(engine.engine_refusals(resolved))

    verdict_status: str | None = None
    if check_model and model is not None:
        found = model_refusals(resolved, model)
        if allow_unprobed:
            found = [r for r in found if r.code != "model_facts_unprobed"]
        refusals.extend(found)
        verdict_status = "refused" if found else "supported"

    return ServeGate(
        backend=requested,
        resolved_backend=resolved,
        refusals=tuple(refusals),
        host=probed_host,
        detection=detection,
        model=str(model) if model is not None else None,
        model_verdict_status=verdict_status,
    )
