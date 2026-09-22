#!/usr/bin/env python3
"""serve_cell_record.py -- turn `algenta serve --backend cuda --json` output into the per-cell
record that benchmarks/llm_smoke/nvidia_race/vm_harness/lever3/gate_any.py consumes.

WHY THIS MODULE EXISTS, AND WHY IT IS NOT A FLAG ON THE decode() PATH
---------------------------------------------------------------------
`wheel_gate_cells.py` originally drove every cell through `algenta.inference.decode`. That function
is documented, in its own source, as the METAL resident session:

    # This path only ever runs on the metal resident session, so also run the
    # backend-aware gate ...
    _refusals = refusals_for_facts(_facts, backend="metal", probed=True, enforce_backend=True)

and it takes no `backend` argument at all. So for a CUDA wheel it never reaches a CUDA kernel:
measured on r1115-cert-1g (a3-highgpu-1g, 1x H100 80GB, driver 595.71.05) against the certified
1.0.6 cuda wheel sha256 ad2b8527..., the first cell died in 0.6 s at preflight with

    InferenceError: preflight refused this run: metaldispatch_code_out_of_range

because Qwen2.5-7B's intermediate_size 18944 IS a declared CUDA staging tier
((3072, 6144, 8192, 18944) in model_capabilities.py) and is NOT a metal one. That is not a
misconfiguration to be knobbed away; it is the wrong entry point. The CUDA path a user actually
gets is `algenta serve --backend cuda`, which resolves the BUNDLED engine (conform_generate_cuda)
out of the installed wheel -- the binary carrying the race kernels that #1115 put in the artifact.

The metal decode() path is left completely untouched: the gemma3-27b and Metal lanes still use it,
and this module is only reached with `--engine serve`.

THE ONE SEMANTIC DIFFERENCE THAT WOULD SILENTLY CORRUPT A GATE
---------------------------------------------------------------
`decode()` returns `token_ids` = PROMPT TOKENS FOLLOWED BY every generated token, so its caller
slices `all_ids[result.n_prompt:]`. The serve engine does NOT: its ids come from the binary's
`CONFORM_TOKENS` line, documented in serve/engine.py as "a CONFORM_TOKENS line carrying the
GENERATED ids", and are surfaced verbatim as `ServeOutcome.token_ids`. Slicing them by n_prompt
here would throw away the first n_prompt GENERATED tokens and compare the remainder against the
oracle -- a gate that still looks like it ran, still produces numbers, and is wrong for every
prompt longer than its own generation. Hence `generated = list(token_ids)` with no slice, and this
comment, because the two paths differ in exactly the place where a mistake is invisible.

FAILURE IS ALWAYS A RECORD WITHOUT `generated`
----------------------------------------------
gate_any.py treats a cell file whose last JSON line has no `generated` key as NOT-RUN, which fails
the gate. So every refusal path here -- non-zero exit, unparseable JSON, a typed refusal, an empty
token list -- emits a record with no `generated` key and with the serve JSON's own error/refusal
text VERBATIM. A cell that cannot be read must never be readable as a pass, and the reason must be
the engine's, not a paraphrase of it.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

# The serve/engine surface reports GENERATED ids only (see the module docstring). Named, not
# inlined, so the invariant is greppable from the one place it is decided.
SERVE_TOKEN_IDS_ARE_GENERATED_ONLY = True

ARM_LABEL = "cuda_release_wheel_serve"

# A refusal's own text, taken from the serve JSON rather than restated. `error` is
# {"code","message"}; `refusal` is the typed ServeRefusal dict (code/stage/detail/fact/value/
# supported/remedy/message). Both are dumped verbatim so a reader sees the product's words.
_STDOUT_TAIL_CHARS = 1200
_STDERR_TAIL_CHARS = 1200


def build_serve_command(
    *,
    python: str,
    model: str,
    converted_dir: str,
    prompt_token_ids: Sequence[int],
    max_new_tokens: int,
    weights_dtype: str | None = None,
    timeout: float | None = None,
) -> list[str]:
    """The argv for one cell.

    `python -m algenta.cli`, NOT the `algenta` console script: the wheel is unpacked with the stdlib
    zipfile (no pip, no package index on a race box), so no console_script was ever installed. The
    module path is the same entry point pyproject declares (`algenta = "algenta.cli:main"`).

    --model is the HF SNAPSHOT dir (config.json + safetensors) and --converted-dir is the converted
    manifest+weights pair; serve/cli.py documents them that way and reusing the converted pair is
    what stops each cell re-converting a 57 GB blob. --prompt-token-ids feeds the fixture's ids
    directly, so a cell generates from exactly the bytes the oracle was built from and no tokenizer
    sits between them.
    """
    argv = [
        python, "-m", "algenta.cli",
        "serve",
        "--backend", "cuda",
        "--model", model,
        "--converted-dir", converted_dir,
        "--prompt-token-ids", ",".join(str(int(t)) for t in prompt_token_ids),
        "--max-new-tokens", str(int(max_new_tokens)),
        "--json",
    ]
    if weights_dtype:
        argv += ["--weights-dtype", weights_dtype]
    if timeout:
        argv += ["--timeout", str(timeout)]
    return argv


def _tail(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= limit else "..." + text[-limit:]


def _refusal_text(payload: dict[str, Any]) -> str | None:
    """The serve JSON's own refusal/error, verbatim, or None if it carries neither."""
    parts = []
    error = payload.get("error")
    if error:
        parts.append("error=" + json.dumps(error, sort_keys=True))
    refusal = payload.get("refusal")
    if refusal:
        parts.append("refusal=" + json.dumps(refusal, sort_keys=True))
    plan = payload.get("plan") or {}
    gate = plan.get("gate") or {}
    for item in gate.get("refusals") or []:
        parts.append("gate_refusal=" + json.dumps(item, sort_keys=True))
    return " | ".join(parts) if parts else None


def _timing_fields(timing: Any, n_prompt: int, n_generated: int) -> tuple[float | None, float | None]:
    """(ttft_ms, decode_tok_s) from the serve timing block, or (None, None).

    Reported, never gated on: gate_any.py reads these two only to print them. Deriving a rate from a
    key whose spelling this module does not control would be a guess dressed as a measurement, so an
    unrecognised block yields None and the raw dict is carried in the record instead.
    """
    if not isinstance(timing, dict):
        return None, None
    ttft = None
    for key in ("ttft_ms", "time_to_first_token_ms", "prefill_ms"):
        if isinstance(timing.get(key), (int, float)):
            ttft = round(float(timing[key]), 3)
            break
    rate = None
    for key in ("decode_tokens_per_sec", "decode_tok_s", "tokens_per_sec"):
        if isinstance(timing.get(key), (int, float)):
            rate = round(float(timing[key]), 3)
            break
    return ttft, rate


def _failure_record(
    *,
    label: str,
    error: str,
    returncode: int | None,
    worker_sha256_16: str,
    wheel_sha256_16: str,
    cell_seconds: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A record with NO `generated` key -- which is what makes gate_any.py score it NOT-RUN."""
    record: dict[str, Any] = {
        "label": label,
        "error": error,
        "ran": False,
        "serve_rc": returncode,
        "arm": ARM_LABEL,
        "worker_sha256_16": worker_sha256_16,
        "wheel_sha256_16": wheel_sha256_16,
        "cell_seconds": round(cell_seconds, 1),
    }
    if extra:
        record.update(extra)
    return record


def parse_serve_output(
    *,
    label: str,
    prompt: str,
    n_prompt: int,
    requested: int,
    returncode: int,
    stdout: str | None,
    stderr: str | None,
    worker_sha256_16: str,
    wheel_sha256_16: str,
    cell_seconds: float,
    eos_tokens: Iterable[int] = (),
) -> tuple[dict[str, Any], str | None]:
    """Parse one cell's serve invocation into (record, error).

    `error` is None exactly when the record carries a non-empty `generated` list. Anything else --
    non-zero exit, unparseable or truncated JSON, a typed refusal, exit 0 with no tokens -- is a
    refusal whose text is the serve JSON's own, verbatim, falling back to the process's stderr tail
    only when the JSON has nothing to say.
    """
    eos = frozenset(int(t) for t in eos_tokens)
    common = dict(
        label=label,
        returncode=returncode,
        worker_sha256_16=worker_sha256_16,
        wheel_sha256_16=wheel_sha256_16,
        cell_seconds=cell_seconds,
    )

    payload: dict[str, Any] | None = None
    parse_error: str | None = None
    text = (stdout or "").strip()
    if text:
        try:
            loaded = json.loads(text)
            payload = loaded if isinstance(loaded, dict) else None
            if payload is None:
                parse_error = "serve --json emitted a %s, not an object" % type(loaded).__name__
        except Exception as exc:  # noqa: BLE001 - truncated JSON is a refusal, not a crash
            parse_error = "serve --json was not parseable: %s: %s" % (type(exc).__name__, exc)

    # A non-zero exit is a refusal even when the JSON parsed: the CLI's exit codes ARE the contract
    # (0 ok, 1 error, 2 REFUSED, 3 pending), so rc!=0 with a well-formed payload still means the
    # engine did not serve these tokens.
    if returncode != 0:
        reason = _refusal_text(payload) if payload else None
        if reason is None:
            reason = parse_error or _tail(stderr, _STDERR_TAIL_CHARS) or _tail(text, _STDOUT_TAIL_CHARS)
        detail = "serve exited %d" % returncode
        if parse_error and payload is not None:
            detail += "; %s" % parse_error
        return _failure_record(
            error="%s: %s" % (detail, reason),
            extra={"serve_refusal": (payload or {}).get("refusal"),
                   "serve_error": (payload or {}).get("error"),
                   "stderr_tail": _tail(stderr, _STDERR_TAIL_CHARS)},
            **common,
        ), "%s: %s" % (detail, reason)

    if payload is None:
        reason = parse_error or "serve produced no parseable JSON on stdout"
        return _failure_record(
            error=reason,
            extra={"stdout_tail": _tail(text, _STDOUT_TAIL_CHARS),
                   "stderr_tail": _tail(stderr, _STDERR_TAIL_CHARS)},
            **common,
        ), reason

    # Exit 0 but a typed refusal/error in the payload: still a refusal, with the product's own words.
    refusal_reason = _refusal_text(payload)
    raw_ids = payload.get("token_ids")
    if not isinstance(raw_ids, list):
        reason = refusal_reason or "serve exited 0 but its JSON carries no token_ids list"
        return _failure_record(
            error=reason,
            extra={"serve_refusal": payload.get("refusal"), "serve_error": payload.get("error"),
                   "stderr_tail": _tail(stderr, _STDERR_TAIL_CHARS)},
            **common,
        ), reason

    generated = [int(t) for t in raw_ids]
    if not generated:
        reason = refusal_reason or "serve exited 0 but generated ZERO tokens"
        return _failure_record(
            error=reason,
            extra={"serve_refusal": payload.get("refusal"), "serve_error": payload.get("error"),
                   "serve_text": payload.get("text")},
            **common,
        ), reason

    # NO n_prompt SLICE HERE -- see the module docstring. These ids are already generated-only.
    ttft_ms, decode_tok_s = _timing_fields(payload.get("timing"), n_prompt, len(generated))
    last = generated[-1]
    stopped_early = len(generated) < requested
    record = {
        "label": label,
        "prompt": prompt,
        "n_prompt": n_prompt,
        "requested": requested,
        "generated": generated,
        "n_generated": len(generated),
        # The serve surface reports no stopped_on_eos flag, so this is DERIVED and says only "the
        # engine stopped before the requested width". `eos_stop` below adds the part that matters to
        # the gate -- that the token it stopped on is an eos of THIS tokenizer.
        "stopped_on_eos": bool(stopped_early),
        "last_token": last,
        "eos_stop": bool(stopped_early) and last in eos,
        "ttft_ms": ttft_ms,
        "decode_tok_s": decode_tok_s,
        # Not exposed by the serve surface. Present as None rather than absent so the record's key
        # set matches the decode() path's and a reader diffing two cells sees the same shape.
        "dispatches_per_token": None,
        "arm": ARM_LABEL,
        "path": "algenta serve --backend cuda (bundled conform_generate_cuda engine)",
        "serve_rc": returncode,
        "serve_ok": payload.get("ok"),
        "serve_timing": payload.get("timing"),
        "worker_sha256_16": worker_sha256_16,
        "wheel_sha256_16": wheel_sha256_16,
        "cell_seconds": round(cell_seconds, 1),
    }
    return record, None
