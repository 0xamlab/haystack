"""`algenta serve` — one supported entry point onto the engine, on either backend.

This is the door an operator runs. It exists because the engine's GPU kernels were
certified and published as capability long before they were launchable: the
contract declared 199 racing kernels (142 CUDA / 57 Metal) while the only
run-verified serve path was the Metal SDK door. `algenta serve` makes the choice
of backend an explicit, gated, reported decision instead of an accident of which
Python function you happened to call.

    algenta serve --model ~/models/Qwen3-0.6B-Base --prompt "The capital of France is"
    algenta serve --backend cuda --model ~/models/gemma-3-27b-it --prompt-file p.txt \\
        --max-new-tokens 64 --json
    algenta serve --backend cuda --model ~/models/Qwen3-0.6B-Base --dry-run

Grammar: `--backend auto|<published backend>` (default `auto` = detect and SAY
which), exactly one prompt source (`--prompt`, `--prompt-file`,
`--prompt-token-ids`), `--max-new-tokens`, `--json` for the machine-readable
report, `--dry-run` to resolve and gate and print the launch plan without
converting weights or spawning an engine.

What each backend actually launches
-----------------------------------
* **metal** — `algenta.inference.decode`, the existing production door, through
  the bundled runtime worker. Nothing here duplicates or replaces it.
* **cuda** — the standalone CUDA-lane engine binary, resolved by
  `algenta.serve.engine` and composed of the existing `residentk.session_cuda*`
  session modules. The prompt is tokenized HERE by `algenta.tokenizer` (the
  production, oracle-validated tokenizer) and the generated ids are detokenized
  HERE, so the engine only ever does token math — the same division of labour the
  fact-driven conform battery uses, which is why its output is token-identical to
  an independent fp64 reference.

No kernel is forked, re-implemented or re-tuned by this package: it resolves,
gates, converts, launches and renders.

Refusals, and the one rule that is not negotiable
-------------------------------------------------
`algenta.serve.gating` judges host facts (platform, NVIDIA driver version and
compute capability against the declared floor), engine facts (a binary was
resolved and is executable) and model facts (the capability table's own typed
refusals, verbatim). A refusal is loud (stderr, non-zero exit) and
machine-readable (`--json`, plus a stable `code` per refusal). **There is no
silent fallback**: `--backend cuda` on a host with no NVIDIA device exits 2 with
`no_nvidia_gpu`, it does not quietly serve on Metal.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from algenta.serve.engine import (
    CUDA_ENGINE_BINARY_NAME,
    EngineLaunch,
    EngineResult,
    engine_stage,
    run_engine,
)
from algenta.serve.gating import (
    BACKEND_AUTO,
    NvidiaHostFacts,
    ServeGate,
    ServeRefusal,
    gate_serve,
    published_backends,
    serve_backends,
)

__all__ = [
    "BACKEND_AUTO",
    "CUDA_ENGINE_BINARY_NAME",
    "ServeError",
    "ServeOutcome",
    "ServePlan",
    "ServeRequest",
    "ServeGate",
    "ServeRefusal",
    "NvidiaHostFacts",
    "plan_serve",
    "published_backends",
    "serve",
    "serve_backends",
]

_DEFAULT_MAX_NEW_TOKENS = 64
_DEFAULT_TIMEOUT_SECONDS = 1800.0
# The CUDA engine reads its prompt from the converted manifest's `input_ids`, so
# the converted directory is prompt-bearing even though the weights blob is not.
# Keyed by the checkpoint's identity + the conversion parameters (never by the
# prompt) and re-stamped per request: one blob on disk per checkpoint, one
# manifest rewrite per serve, and a stale prompt can never be served by accident.
_CUDA_CACHE_DIRNAME = ".algenta-serve-cuda"


class ServeError(RuntimeError):
    """A serve request failed for a reason that is not a backend/model refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ServeRequest:
    """One serve request, as the CLI or an SDK caller stated it.

    Exactly one of `prompt_text` / `prompt_token_ids` must be set — the same rule
    `algenta.inference.decode` enforces, so the two doors cannot disagree about
    what a prompt is.
    """

    model: str | os.PathLike[str]
    backend: str = BACKEND_AUTO
    prompt_text: str | None = None
    prompt_token_ids: tuple[int, ...] | None = None
    max_new_tokens: int = _DEFAULT_MAX_NEW_TOKENS
    engine_binary: str | os.PathLike[str] | None = None
    weights_dtype: str = "f64"
    converted_dir: str | os.PathLike[str] | None = None
    allow_unprobed: bool = False
    timeout: float = _DEFAULT_TIMEOUT_SECONDS

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": str(self.model),
            "backend": self.backend,
            "prompt_text": self.prompt_text,
            "prompt_token_ids": list(self.prompt_token_ids)
            if self.prompt_token_ids is not None
            else None,
            "max_new_tokens": self.max_new_tokens,
            "engine_binary": str(self.engine_binary) if self.engine_binary else None,
            "weights_dtype": self.weights_dtype,
            "converted_dir": str(self.converted_dir) if self.converted_dir else None,
            "allow_unprobed": self.allow_unprobed,
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class ServePlan:
    """Everything a launch would do, computed without doing any of it.

    `--dry-run` returns exactly this and nothing else: no weights converted, no
    process spawned. It is also the artifact a reviewer or an operator reads to
    see which binary, with which argv, on which backend, for which facts.
    """

    request: ServeRequest
    gate: ServeGate
    launch: EngineLaunch | None = None
    prompt_token_ids: tuple[int, ...] | None = None
    converted_dir: str | None = None

    @property
    def accepted(self) -> bool:
        return self.gate.accepted

    @property
    def prompt_token_count(self) -> int | None:
        return None if self.prompt_token_ids is None else len(self.prompt_token_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.as_dict(),
            "gate": self.gate.as_dict(),
            "launch": self.launch.as_dict() if self.launch is not None else None,
            "prompt_token_ids": list(self.prompt_token_ids)
            if self.prompt_token_ids is not None
            else None,
            "prompt_token_count": self.prompt_token_count,
            "converted_dir": self.converted_dir,
        }


@dataclass(frozen=True)
class ServeOutcome:
    """A serve request's whole result: the plan, and what the engine produced."""

    plan: ServePlan
    token_ids: tuple[int, ...] = ()
    text: str | None = None
    timing: dict[str, float] | None = None
    engine: EngineResult | None = None
    refusal: ServeRefusal | None = None
    error: ServeError | None = None

    @property
    def ok(self) -> bool:
        return self.refusal is None and self.error is None and bool(self.token_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan": self.plan.as_dict(),
            "token_ids": list(self.token_ids),
            "text": self.text,
            "timing": dict(self.timing) if self.timing else None,
            "engine": self.engine.as_dict() if self.engine is not None else None,
            "refusal": self.refusal.as_dict() if self.refusal is not None else None,
            "error": {"code": self.error.code, "message": str(self.error)}
            if self.error is not None
            else None,
        }


def _validate_request(request: ServeRequest) -> None:
    provided = sum(value is not None for value in (request.prompt_text, request.prompt_token_ids))
    if provided != 1:
        raise ServeError(
            "invalid_arguments",
            "pass exactly one of prompt_text or prompt_token_ids "
            f"(got {provided}); a chat-template turn belongs to the API surface, not this door",
        )
    if request.prompt_text is not None and not str(request.prompt_text):
        raise ServeError("invalid_arguments", "prompt_text must be a non-empty string")
    if isinstance(request.max_new_tokens, bool) or request.max_new_tokens < 1:
        raise ServeError(
            "invalid_arguments",
            f"max_new_tokens must be a positive int, got {request.max_new_tokens!r}",
        )
    if request.weights_dtype not in ("f32", "f64"):
        raise ServeError(
            "invalid_arguments",
            f"weights_dtype must be 'f32' or 'f64', got {request.weights_dtype!r}",
        )
    if request.backend not in serve_backends():
        raise ServeError(
            "invalid_arguments",
            f"backend must be one of {', '.join(serve_backends())}, got {request.backend!r}",
        )


def _prompt_token_ids(request: ServeRequest, *, tokenizer: Any = None) -> tuple[int, ...]:
    """The request's prompt as token ids, tokenized by the checkpoint's OWN tokenizer.

    `add_special_tokens=True` is the transformers default-encode convention, the
    same one `algenta.inference.decode` uses, so the two doors tokenize a prompt
    identically.
    """
    if request.prompt_token_ids is not None:
        ids = tuple(int(token) for token in request.prompt_token_ids)
        if not ids:
            raise ServeError("invalid_arguments", "prompt_token_ids must not be empty")
        if any(token < 0 for token in ids):
            raise ServeError("invalid_arguments", "prompt_token_ids must be non-negative ints")
        return ids
    if tokenizer is None:
        from algenta.tokenizer import load_tokenizer

        tokenizer = load_tokenizer(str(request.model))
    return tuple(tokenizer.encode(str(request.prompt_text), add_special_tokens=True))


def _cache_key(request: ServeRequest) -> str:
    """The converted directory's identity: the checkpoint and the conversion
    parameters. Deliberately NOT the prompt — the blob is prompt-independent and
    re-converting a 27B checkpoint per request would be unusable; the prompt is
    re-stamped into the manifest instead (see `_stamp_prompt`)."""
    material = json.dumps(
        {
            "model": str(Path(str(request.model)).resolve()),
            "weights_dtype": request.weights_dtype,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _converted_dir_for(request: ServeRequest) -> Path:
    if request.converted_dir is not None:
        return Path(str(request.converted_dir)).expanduser()
    return Path(str(request.model)).expanduser() / _CUDA_CACHE_DIRNAME / _cache_key(request)


def _stamp_prompt(manifest_path: Path, prompt_token_ids: tuple[int, ...]) -> None:
    """Re-point an existing converted manifest at a new prompt.

    The converted pair is `manifest.json` + `weights.blob`; only `input_ids` and
    `config.n_tokens` are prompt-derived (every other config value is a fact of
    the checkpoint, and every tensor offset is a fact of the blob). Rewriting
    those two keys is what lets one conversion serve many prompts without a
    second multi-gigabyte blob — the same property `scripts/algenta_bench.py`'s
    CUDA arm relies on when it sweeps prefill shapes over one converted checkpoint.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = manifest.get("config")
    if not isinstance(config, dict):
        raise ServeError(
            "converted_manifest_invalid",
            f"{manifest_path} carries no config object; delete the converted directory and "
            "let serve reconvert it",
        )
    manifest["input_ids"] = list(prompt_token_ids)
    config["n_tokens"] = len(prompt_token_ids)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _ensure_converted(request: ServeRequest, prompt_token_ids: tuple[int, ...]) -> Path:
    """Convert once per (checkpoint, dtype), then stamp this request's prompt."""
    from algenta.inference import prepare_model_checkpoint

    target = _converted_dir_for(request)
    manifest_path = target / "manifest.json"
    blob_path = target / "weights.blob"
    if manifest_path.is_file() and blob_path.is_file():
        _stamp_prompt(manifest_path, prompt_token_ids)
        return target
    target.mkdir(parents=True, exist_ok=True)
    try:
        return Path(
            prepare_model_checkpoint(
                str(request.model),
                list(prompt_token_ids),
                out_dir=target,
                weights_dtype=request.weights_dtype,
                backend="cuda",
            )
        )
    except BaseException:
        # Same contract the converter itself keeps: a failed conversion leaves no
        # partial pair behind for a later run to mistake for a valid cache.
        manifest_path.unlink(missing_ok=True)
        blob_path.unlink(missing_ok=True)
        raise


def plan_serve(
    request: ServeRequest,
    *,
    platform: str | None = None,
    host: NvidiaHostFacts | None = None,
    environ: os._Environ[str] | dict[str, str] | None = None,
    tokenizer: Any = None,
    resolve_prompt: bool = True,
) -> ServePlan:
    """Resolve and gate a serve request, and declare the launch — without launching.

    `resolve_prompt=False` skips tokenization (and so needs no checkpoint on disk),
    which is what a grammar-level caller wants; the gate still runs in full.
    """
    _validate_request(request)
    # `host` is handed to the engine stage as well as to the gate: admitting the
    # engine binary BUNDLED IN THE WHEEL is the one resolution step that consults
    # host facts (it requires a signed manifest declaring build_variant='cuda' AND
    # a cuda-capable host), and the gate has usually already probed. Passing the
    # same facts in means one probe per serve, not two that could disagree.
    stage = engine_stage(
        override=request.engine_binary, environ=environ, host=host, platform=platform
    )
    gate = gate_serve(
        request.backend,
        model=request.model,
        engine=stage,
        platform=platform,
        host=host,
        allow_unprobed=request.allow_unprobed,
    )
    if not gate.accepted or gate.resolved_backend is None:
        return ServePlan(request=request, gate=gate)

    backend = gate.resolved_backend
    prompt_ids: tuple[int, ...] | None = None
    if resolve_prompt:
        prompt_ids = _prompt_token_ids(request, tokenizer=tokenizer)

    resolution = stage.resolve(backend)
    if backend == "cuda":
        converted = _converted_dir_for(request)
        launch = EngineLaunch(
            backend=backend,
            kind="subprocess",
            argv=(
                str(resolution.path),
                str(converted),
                "--max-new",
                str(request.max_new_tokens),
            ),
            engine_path=str(resolution.path) if resolution.path else None,
            engine_source=resolution.source,
        )
        return ServePlan(
            request=request,
            gate=gate,
            launch=launch,
            prompt_token_ids=prompt_ids,
            converted_dir=str(converted),
        )

    launch = EngineLaunch(
        backend=backend,
        kind="in-process",
        argv=("algenta.inference.decode",),
        engine_path=str(resolution.path) if resolution.path else None,
        engine_source=resolution.source,
    )
    return ServePlan(
        request=request,
        gate=gate,
        launch=launch,
        prompt_token_ids=prompt_ids,
    )


def _run_metal(plan: ServePlan, prompt_ids: tuple[int, ...]) -> ServeOutcome:
    from algenta import MojoRuntime
    from algenta.inference import InferenceError, decode

    request = plan.request
    try:
        runtime = MojoRuntime(mode="local", timeout=request.timeout)
        result = decode(
            runtime,
            checkpoint_dir=str(request.model),
            prompt_token_ids=list(prompt_ids),
            max_new_tokens=request.max_new_tokens,
        )
    except InferenceError as exc:
        return ServeOutcome(
            plan=plan,
            refusal=ServeRefusal(
                code=str(exc.code),
                stage="engine",
                detail=str(exc),
                fact="engine",
                value=str(exc.code),
                supported="a Metal serve the engine can actually run",
            ),
        )
    text = getattr(result, "generated_text", None)
    if text is None:
        tokenizer = _load_tokenizer_or_none(request)
        if tokenizer is not None:
            text = tokenizer.decode(list(result.token_ids))
    timing = {
        key: value
        for key, value in (
            ("prefill_tokens_per_sec", getattr(result, "prefill_tokens_per_sec", None)),
            ("decode_tokens_per_sec", getattr(result, "decode_tokens_per_sec", None)),
        )
        if value is not None
    }
    return ServeOutcome(
        plan=plan,
        token_ids=tuple(int(token) for token in result.token_ids),
        text=text,
        timing=timing or None,
    )


def _load_tokenizer_or_none(request: ServeRequest) -> Any:
    if request.prompt_text is None:
        return None
    try:
        from algenta.tokenizer import load_tokenizer

        return load_tokenizer(str(request.model))
    except Exception:  # noqa: BLE001 - detokenizing is a convenience, not a contract
        return None


def _run_cuda(
    plan: ServePlan,
    prompt_ids: tuple[int, ...],
    *,
    runner: Any = None,
) -> ServeOutcome:
    request = plan.request
    launch = plan.launch
    if launch is None:
        return ServeOutcome(
            plan=plan,
            error=ServeError("no_launch_plan", "the serve plan carries no launch to run"),
        )
    try:
        converted = _ensure_converted(request, prompt_ids)
    except ServeError as exc:
        return ServeOutcome(plan=plan, error=exc)
    except Exception as exc:  # noqa: BLE001 - the converter raises its own typed errors
        code = getattr(exc, "code", None)
        return ServeOutcome(
            plan=plan,
            error=ServeError(
                str(code) if isinstance(code, str) else type(exc).__name__,
                f"checkpoint conversion failed: {exc}",
            ),
        )

    argv = [str(launch.argv[0]), str(converted), "--max-new", str(request.max_new_tokens)]
    result = run_engine(
        EngineLaunch(
            backend=launch.backend,
            kind=launch.kind,
            argv=tuple(argv),
            engine_path=launch.engine_path,
            engine_source=launch.engine_source,
        ),
        timeout=request.timeout,
        runner=runner,
    )
    if result.refusal is not None:
        return ServeOutcome(plan=plan, engine=result, refusal=result.refusal)

    text: str | None = None
    tokenizer = _load_tokenizer_or_none(request)
    if tokenizer is not None:
        try:
            text = tokenizer.decode(list(result.token_ids))
        except Exception:  # noqa: BLE001 - ids are the contract; text is a convenience
            text = None
    return ServeOutcome(
        plan=plan,
        token_ids=result.token_ids,
        text=text,
        timing=result.timing,
        engine=result,
    )


def serve(
    request: ServeRequest,
    *,
    platform: str | None = None,
    host: NvidiaHostFacts | None = None,
    environ: os._Environ[str] | dict[str, str] | None = None,
    tokenizer: Any = None,
    dry_run: bool = False,
    runner: Any = None,
) -> ServeOutcome:
    """Gate, then launch. A refused request never reaches a launch.

    `dry_run=True` returns the plan alone. `runner` and `tokenizer` are injectable
    so the whole launch path is exercisable on a host with no accelerator.
    """
    plan = plan_serve(
        request,
        platform=platform,
        host=host,
        environ=environ,
        tokenizer=tokenizer,
        resolve_prompt=True,
    )
    if dry_run or not plan.accepted:
        return ServeOutcome(
            plan=plan, refusal=plan.gate.refusals[0] if plan.gate.refusals else None
        )

    prompt_ids = plan.prompt_token_ids
    if prompt_ids is None:  # pragma: no cover - an accepted plan always resolved its prompt
        return ServeOutcome(
            plan=plan,
            error=ServeError("prompt_unresolved", "the accepted plan carries no prompt token ids"),
        )

    backend = plan.gate.resolved_backend
    if backend == "cuda":
        return _run_cuda(plan, prompt_ids, runner=runner)
    return _run_metal(plan, prompt_ids)
