"""The engine half of `algenta serve`: which binary runs, and what it said.

Two backends, two very different engine shapes, and this module is where the
difference is contained so the gate and the CLI never have to reason about it:

* **metal** — the engine is the bundled runtime worker the SDK already resolves
  (`algenta.native.worker`), reached in-process through
  `algenta.inference.decode`. There is no separate binary for a caller to point
  at, so resolution here means "the SDK can find a worker at all".
* **cuda** — the engine is a standalone resident-session binary compiled against
  the CUDA session modules (`residentk.session_cuda*`). The in-tree fact-driven
  arm is `benchmarks/llm_smoke/conform_generate_cuda.mojo`: model-agnostic (every
  fact read from the converted manifest, nothing hardcoded to a shape), and the
  driver half of the synthetic battery's token-identity proof against an
  independent fp64 reference. Its machine-readable output contract is what
  `EngineResult` parses:

      CONFORM_TOKENS: <id> <id> ...          generated ids only, prompt excluded
      CONFORM_TIMING: n_prompt=N n_gen=N prefill_ms=F decode_tok_s=F
      CONFORM_REFUSED: <residentk status>    the engine's OWN typed refusal (exit 3)
      exit 4 + "built without -D ALGENTA_GPU -D ALGENTA_CUDA"   not a CUDA build
      exit 4 + "no accelerator on this host"                    no device

  Those literals are mapped back onto the gate's refusal vocabulary
  (`ENGINE_OUTPUT_REFUSALS`) rather than surfaced as a bare non-zero exit, so a
  launch that fails inside the engine still produces a typed, machine-readable
  reason — the whole point of the gate, applied at the last possible moment too.

Resolution order is declared, not incidental, and ends beside the bundled runtime
artifact so that packaging the CUDA engine into the runtime wheel (a separate
workstream) makes it resolvable with no edit here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "CUDA_ENGINE_BINARY_NAME",
    "CUDA_ENGINE_ENV_VARS",
    "ENGINE_OUTPUT_REFUSALS",
    "EngineLaunch",
    "EngineResolution",
    "EngineResult",
    "engine_refusals",
    "engine_stage",
    "parse_engine_output",
    "resolve_engine",
]

CUDA_ENGINE_BINARY_NAME = "conform_generate_cuda"

# Operator overrides, most explicit first. `ALGENTA_CONFORM_CUDA_DRIVER` is the
# name `scripts/algenta_conform.py` and `scripts/algenta_bench.py` already use for
# this same binary, so an operator's existing environment keeps working.
CUDA_ENGINE_ENV_VARS: tuple[str, ...] = ("ALGENTA_CUDA_ENGINE", "ALGENTA_CONFORM_CUDA_DRIVER")

# Where locally built engine binaries live, per `benchmarks/bench_tools.py`.
_BIN_DIR_ENV_VAR = "BENCH_BIN_DIR"

# The engine's own output literals, mapped onto gate refusal codes. Keyed on a
# substring of the engine's stdout/stderr because the engine prints them inside a
# longer diagnostic line.
ENGINE_OUTPUT_REFUSALS: tuple[tuple[str, str, str], ...] = (
    (
        "built without -D ALGENTA_GPU -D ALGENTA_CUDA",
        "engine_binary_not_cuda_build",
        "the resolved binary was compiled without the CUDA lane; rebuild it with "
        "-D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN",
    ),
    (
        "no accelerator on this host",
        "no_nvidia_gpu",
        "the engine binary is a CUDA build but this host exposes no accelerator to it",
    ),
    (
        "CONFORM_REFUSED:",
        "engine_refused_model",
        "the engine's own resident preflight refused this shape; the status name it printed "
        "is residentk.contract's",
    ),
)

_ENGINE_TIMEOUT_SECONDS = 1800.0


@dataclass(frozen=True)
class EngineResolution:
    """Where the engine binary came from, or every place it was looked for.

    ``searched`` is carried on the failure path deliberately: a refusal that says
    "not found" without the chain is a support ticket, and the chain is already
    computed.
    """

    path: Path | None
    source: str | None
    searched: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path) if self.path is not None else None,
            "source": self.source,
            "searched": list(self.searched),
        }


def _bundled_artifact_dirs() -> list[Path]:
    """The directories the SDK's own runtime resolution would accept an artifact from.

    Reused rather than re-derived so the CUDA engine is looked for in exactly the
    places a packaged runtime lands, including beside the bundled worker.
    """
    dirs: list[Path] = []
    try:
        from algenta.native import worker as _worker

        candidates = list(_worker._candidate_paths(None))
    except Exception:  # noqa: BLE001 - resolution is best-effort; the chain continues
        # No bundled runtime to look beside. That is not an error here: the rest
        # of the chain (env overrides, $BENCH_BIN_DIR, $PATH) still runs, and an
        # unresolved binary becomes a typed refusal naming the whole chain.
        return dirs
    for _source, path, _must_verify, _error in candidates:
        parent = Path(path).parent
        if parent not in dirs:
            dirs.append(parent)
    return dirs


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def resolve_engine(
    backend: str,
    *,
    override: str | os.PathLike[str] | None = None,
    environ: os._Environ[str] | dict[str, str] | None = None,
) -> EngineResolution:
    """Resolve the engine binary for `backend`. Never raises, never guesses.

    ``environ`` is injectable so the resolution chain is testable without mutating
    the process environment.
    """
    env = os.environ if environ is None else environ
    if backend == "metal":
        return _resolve_metal_worker()
    if backend != "cuda":
        return EngineResolution(
            None, None, searched=(f"no engine chain is declared for {backend!r}",)
        )

    searched: list[str] = []

    if override:
        candidate = Path(str(override)).expanduser()
        searched.append(f"--engine-binary={candidate}")
        if _executable(candidate):
            return EngineResolution(candidate, "--engine-binary")
        return EngineResolution(None, None, searched=tuple(searched))

    for name in CUDA_ENGINE_ENV_VARS:
        raw = env.get(name)
        searched.append(f"${name}")
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if _executable(candidate):
            return EngineResolution(candidate, f"${name}")
        searched[-1] = f"${name}={candidate} (not executable)"

    bin_dirs = [entry for entry in str(env.get(_BIN_DIR_ENV_VAR, "")).split(os.pathsep) if entry]
    searched.append(f"${_BIN_DIR_ENV_VAR}")
    for directory in bin_dirs:
        candidate = Path(directory).expanduser() / CUDA_ENGINE_BINARY_NAME
        if _executable(candidate):
            return EngineResolution(candidate, f"${_BIN_DIR_ENV_VAR}")

    for artifact_dir in _bundled_artifact_dirs():
        candidate = artifact_dir / CUDA_ENGINE_BINARY_NAME
        searched.append(str(candidate))
        if _executable(candidate):
            return EngineResolution(candidate, "bundled runtime")

    searched.append(f"$PATH/{CUDA_ENGINE_BINARY_NAME}")
    found = shutil.which(CUDA_ENGINE_BINARY_NAME)
    if found:
        return EngineResolution(Path(found), "$PATH")
    return EngineResolution(None, None, searched=tuple(searched))


def _resolve_metal_worker() -> EngineResolution:
    try:
        from algenta.native import worker as _worker

        resolution = _worker.resolve_worker()
    except Exception as exc:  # noqa: BLE001 - an unresolvable worker is a refusal, not a crash
        return EngineResolution(
            None,
            None,
            searched=(f"algenta.native.worker raised {type(exc).__name__}: {exc}",),
        )
    if resolution is None:
        return EngineResolution(None, None, searched=("algenta.native.worker found no runtime",))
    if resolution.public_error:
        return EngineResolution(None, None, searched=(resolution.public_error,))
    return EngineResolution(Path(resolution.path), resolution.source)


def engine_refusals(
    backend: str,
    *,
    override: str | os.PathLike[str] | None = None,
    environ: os._Environ[str] | dict[str, str] | None = None,
    resolution: EngineResolution | None = None,
) -> list[Any]:
    """The engine-stage refusals for `backend`, in the gate's own vocabulary.

    Shaped to be handed to `gating.gate_serve(engine=...)` — the gate calls
    ``engine_refusals(resolved_backend)`` with one positional argument, so this
    module also exposes that arity through `_EngineStage` below.
    """
    from algenta.serve.gating import ServeRefusal

    resolved = (
        resolution
        if resolution is not None
        else resolve_engine(backend, override=override, environ=environ)
    )
    if resolved.path is None:
        if backend == "cuda":
            return [
                ServeRefusal(
                    code="cuda_engine_binary_unresolved",
                    stage="engine",
                    detail=(
                        f"no {CUDA_ENGINE_BINARY_NAME} engine binary was found; searched: "
                        + ", ".join(resolved.searched)
                    ),
                    fact="engine_binary",
                    value=None,
                    supported=(
                        "an executable CUDA-lane engine binary, named by --engine-binary, "
                        "$ALGENTA_CUDA_ENGINE, $ALGENTA_CONFORM_CUDA_DRIVER, $BENCH_BIN_DIR, "
                        "the bundled runtime, or $PATH"
                    ),
                    remedy=(
                        "build it with the CUDA lane recipe (-D ALGENTA_GPU -D ALGENTA_CUDA "
                        "--target-accelerator sm_NN) from "
                        "benchmarks/llm_smoke/conform_generate_cuda.mojo, or install a runtime "
                        "wheel that packages it"
                    ),
                )
            ]
        return [
            ServeRefusal(
                code="runtime_worker_unavailable",
                stage="engine",
                detail=(
                    "the bundled Algenta runtime worker is not available on this host: "
                    + ", ".join(resolved.searched)
                ),
                fact="engine_binary",
                value=None,
                supported="an installed, verified algenta-runtime-native worker for this platform",
                remedy="run `algenta runtime doctor` to see exactly which check failed",
            )
        ]
    if not _executable(resolved.path):
        return [
            ServeRefusal(
                code="engine_binary_not_executable",
                stage="engine",
                detail=f"{resolved.path} exists but is not executable",
                fact="engine_binary",
                value=str(resolved.path),
                supported="an executable file",
                remedy=f"chmod +x {resolved.path}",
            )
        ]
    return []


class _EngineStage:
    """The one-method adapter `gating.gate_serve(engine=...)` expects.

    Carries the operator's override and environment so the gate resolves the SAME
    binary the launch will, instead of resolving twice and risking two answers.
    """

    def __init__(
        self,
        *,
        override: str | os.PathLike[str] | None = None,
        environ: os._Environ[str] | dict[str, str] | None = None,
    ) -> None:
        self.override = override
        self.environ = environ
        self._cache: dict[str, tuple[EngineResolution, list[Any]]] = {}

    def resolve(self, backend: str) -> EngineResolution:
        return self.refusals(backend)[0]

    def refusals(self, backend: str) -> tuple[EngineResolution, list[Any]]:
        cached = self._cache.get(backend)
        if cached is not None:
            return cached
        resolution = resolve_engine(backend, override=self.override, environ=self.environ)
        result = (resolution, engine_refusals(backend, resolution=resolution))
        self._cache[backend] = result
        return result

    def engine_refusals(self, backend: str) -> list[Any]:
        return self.refusals(backend)[1]


def engine_stage(
    *,
    override: str | os.PathLike[str] | None = None,
    environ: os._Environ[str] | dict[str, str] | None = None,
) -> _EngineStage:
    """Build the injectable engine-stage object for `gating.gate_serve`."""
    return _EngineStage(override=override, environ=environ)


@dataclass(frozen=True)
class EngineLaunch:
    """The exact launch a serve will perform, declared before anything is spawned.

    Printed by `algenta serve --dry-run` and carried in `--json`, so an operator
    (and a reviewer) can see the command the entry point would execute without
    owning the hardware to execute it. `kind` distinguishes the two engine
    shapes: ``"subprocess"`` (the CUDA lane's standalone binary, whose `argv` is
    a real command line) from ``"in-process"`` (the Metal door, whose `argv`
    names the Python entry point it calls through the bundled worker and is a
    declaration, not a command line).
    """

    backend: str
    kind: str
    argv: tuple[str, ...]
    engine_path: str | None
    engine_source: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "kind": self.kind,
            "argv": list(self.argv),
            "engine_path": self.engine_path,
            "engine_source": self.engine_source,
        }


@dataclass(frozen=True)
class EngineResult:
    """What the engine binary said, parsed from its machine-readable lines.

    ``refusal`` is set when the engine itself refused (its own preflight, a
    non-CUDA build, no device); ``token_ids`` is the generated tail only, in the
    reference battery's coordinate system (prompt excluded).
    """

    returncode: int
    token_ids: tuple[int, ...] = ()
    timing: dict[str, float] | None = None
    refused_status: str | None = None
    refusal: Any | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.refusal is None and bool(self.token_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "returncode": self.returncode,
            "token_ids": list(self.token_ids),
            "timing": dict(self.timing) if self.timing else None,
            "refused_status": self.refused_status,
            "refusal": self.refusal.as_dict() if self.refusal is not None else None,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def _tail(text: str, lines: int = 6) -> str:
    kept = [line for line in (text or "").splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def _parse_timing(line: str) -> dict[str, float]:
    """``CONFORM_TIMING: n_prompt=2 n_gen=3 prefill_ms=12.5 decode_tok_s=640.2`` -> floats.

    Tolerates a space either side of the ``=`` as well. Mojo's ``print`` joins its
    arguments with NO separator, so the engine emits ``prefill_ms=12.5``; the
    spaced form is accepted too rather than silently yielding an empty timing
    record, because a dropped metric reads as "the engine reported nothing" and
    not as "the parser disagreed about a space".
    """
    timing: dict[str, float] = {}
    tokens = line.split()[1:]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        key, separator, raw = token.partition("=")
        if separator and not raw:
            # `key=` with the value in the NEXT token.
            if index + 1 < len(tokens):
                raw = tokens[index + 1]
                index += 1
            else:
                break
        if separator and key:
            try:
                timing[key] = float(raw)
            except ValueError:
                pass
        index += 1
    return timing


def parse_engine_output(returncode: int, stdout: str, stderr: str) -> EngineResult:
    """Parse the engine's declared machine-readable contract out of its output.

    Tolerant of the diagnostic prose the engine interleaves (it prints its facts
    and its per-stage timings as human lines): only the `CONFORM_*` lines are
    load-bearing, and an unrecognized non-zero exit still yields a typed refusal
    rather than a bare code.
    """
    from algenta.serve.gating import ServeRefusal

    combined = f"{stdout or ''}\n{stderr or ''}"
    token_ids: list[int] = []
    timing: dict[str, float] | None = None
    refused_status: str | None = None

    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("CONFORM_TOKENS:"):
            token_ids = [int(item) for item in stripped.split()[1:] if item.lstrip("-").isdigit()]
        elif stripped.startswith("CONFORM_TIMING:"):
            timing = _parse_timing(stripped)
        elif stripped.startswith("CONFORM_REFUSED:"):
            refused_status = stripped.split(":", 1)[1].strip() or None

    refusal = None
    for literal, code, detail in ENGINE_OUTPUT_REFUSALS:
        if literal in combined:
            refusal = ServeRefusal(
                code=code,
                stage="engine",
                detail=(detail + (f" (engine status: {refused_status})" if refused_status else "")),
                fact="engine_output",
                value=refused_status if refused_status else literal,
                supported="an engine launch that reaches CONFORM_TOKENS",
            )
            break

    if refusal is None and returncode != 0:
        refusal = ServeRefusal(
            code="engine_launch_failed",
            stage="engine",
            detail=f"the engine binary exited {returncode} without producing tokens",
            fact="returncode",
            value=returncode,
            supported="exit 0 with a CONFORM_TOKENS line",
            remedy=_tail(combined) or "inspect the engine's own diagnostics above",
        )
    if refusal is None and returncode == 0 and not token_ids:
        refusal = ServeRefusal(
            code="engine_produced_no_tokens",
            stage="engine",
            detail="the engine binary exited 0 but printed no CONFORM_TOKENS line",
            fact="engine_output",
            value=None,
            supported="a CONFORM_TOKENS line carrying the generated ids",
        )

    return EngineResult(
        returncode=returncode,
        token_ids=tuple(token_ids),
        timing=timing,
        refused_status=refused_status,
        refusal=refusal,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
    )


def run_engine(
    launch: EngineLaunch,
    *,
    timeout: float = _ENGINE_TIMEOUT_SECONDS,
    runner: Any = None,
) -> EngineResult:
    """Spawn `launch.argv` and parse what it said. Never raises on engine failure."""
    run = runner if runner is not None else subprocess.run
    try:
        completed = run(  # noqa: S603 - fixed argv resolved by this module, no shell
            list(launch.argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return parse_engine_output(
            -1,
            (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            f"engine timed out after {timeout:.0f}s",
        )
    except OSError as exc:
        return parse_engine_output(
            -1, "", f"engine could not be spawned: {type(exc).__name__}: {exc}"
        )
    return parse_engine_output(completed.returncode, completed.stdout, completed.stderr)
