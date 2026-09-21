# ruff: noqa: T201
"""`algenta serve` — the CLI grammar, and the exit codes an operator scripts against.

Exit codes are the conformance CLI's, deliberately: `scripts/algenta_conform.py`
already publishes 0/1/2/3 for supported / unusable input / refused / pending the
tensor probe, and a serve entry that invented its own numbers would make an
operator's wrapper branch twice on the same idea.

    0  the request was served (or `--dry-run` / `--backends` resolved cleanly)
    1  the input was not a usable serve request (bad flag combination, unreadable
       prompt file, a conversion or launch that errored rather than refused)
    2  REFUSED — a typed refusal from the startup gate or from the engine itself
    3  the model's facts are supported but the tensor-level probe was never run
       (config-only checkpoint); pass `--allow-unprobed` to serve it anyway

A refusal is printed to stderr AND is machine-readable through `--json` on
stdout, so a pipeline can read the code without scraping prose. Nothing here
falls back to another backend: `--backend cuda` on a host with no NVIDIA device
exits 2 saying exactly that.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from algenta.serve import (
    ServeError,
    ServeOutcome,
    ServePlan,
    ServeRequest,
    plan_serve,
    published_backends,
    serve,
    serve_backends,
)

__all__ = ["EXIT_ERROR", "EXIT_OK", "EXIT_PENDING", "EXIT_REFUSED", "build_parser", "main"]

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2
EXIT_PENDING = 3

_PENDING_CODE = "model_facts_unprobed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algenta serve",
        description=(
            "Serve one prompt through the Algenta engine on an explicitly gated backend. "
            "Refusals are typed and never fall back to another backend."
        ),
    )
    parser.add_argument(
        "--model",
        help="a HuggingFace checkpoint snapshot directory (config.json + safetensors)",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=list(serve_backends()),
        help=(
            "which engine to serve on. 'auto' DETECTS from this host's facts and reports "
            "every candidate's verdict; an explicit backend is gated absolutely and refuses "
            "rather than falling back (default: auto)"
        ),
    )
    prompt = parser.add_argument_group("prompt (exactly one)")
    prompt.add_argument(
        "--prompt", help="prompt text, tokenized with the checkpoint's own tokenizer"
    )
    prompt.add_argument("--prompt-file", help="read the prompt text from this file")
    prompt.add_argument(
        "--prompt-token-ids",
        help="comma-separated token ids; skips the tokenizer entirely",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
        help="tokens to generate (default: 64)",
    )
    parser.add_argument(
        "--weights-dtype",
        choices=("f32", "f64"),
        default="f64",
        help=(
            "converted weight width: f64 is the historical format, f32 is exact for "
            "BF16-origin checkpoints at half the disk (default: f64)"
        ),
    )
    parser.add_argument(
        "--engine-binary",
        help=(
            "the CUDA-lane engine binary to launch; overrides $ALGENTA_CUDA_ENGINE, "
            "$ALGENTA_CONFORM_CUDA_DRIVER, $BENCH_BIN_DIR, the bundled runtime and $PATH"
        ),
    )
    parser.add_argument(
        "--converted-dir",
        help="where to write/read the converted manifest+weights pair "
        "(default: beside the checkpoint)",
    )
    parser.add_argument(
        "--allow-unprobed",
        action="store_true",
        help="serve a config-only checkpoint whose tensor-level facts were never probed",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="seconds to wait for the engine (default: 1800)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the full machine-readable report (plan, gate, refusals, tokens) as JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve and gate, print the launch plan, convert nothing and spawn nothing",
    )
    parser.add_argument(
        "--backends",
        action="store_true",
        help="print the published backends and their declared host requirements, then exit",
    )
    return parser


def _print_backends() -> int:
    from algenta.model_capabilities import BACKEND_FACT_RANGES, BACKEND_HOST_REQUIREMENTS

    print(
        f"published backends (from the runtime contract's engine-kernel inventory): "
        f"{', '.join(published_backends())}"
    )
    print(f"--backend accepts: {', '.join(serve_backends())}")
    for backend in published_backends():
        requirements = BACKEND_HOST_REQUIREMENTS.get(backend, {})
        ranges = BACKEND_FACT_RANGES.get(backend, {})
        driver = requirements.get("min_driver_version")
        capability = requirements.get("min_compute_capability")
        print(f"  {backend}:")
        print(f"    platforms:          {'/'.join(requirements.get('platforms') or ()) or 'any'}")
        print(
            "    min driver:         "
            + (".".join(str(part) for part in driver) if driver else "none declared")
        )
        print(
            "    min compute cap:    "
            + (".".join(str(part) for part in capability) if capability else "none declared")
        )
        print(
            f"    model families:     {', '.join(ranges.get('families') or ()) or 'none declared'}"
        )
        tiers = ", ".join(str(tier) for tier in ranges.get("staging_tiers") or ())
        print(f"    staging tiers:      {tiers or 'none declared'}")
    return EXIT_OK


def _parse_prompt_token_ids(raw: str) -> tuple[int, ...]:
    ids: list[int] = []
    for chunk in raw.replace(" ", ",").split(","):
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError as exc:
            raise ServeError(
                "invalid_arguments",
                f"--prompt-token-ids must be comma-separated ints, got {chunk!r}",
            ) from exc
    if not ids:
        raise ServeError("invalid_arguments", "--prompt-token-ids produced no token ids")
    return tuple(ids)


def _build_request(args: argparse.Namespace) -> ServeRequest:
    sources = [
        value is not None for value in (args.prompt, args.prompt_file, args.prompt_token_ids)
    ]
    if sum(sources) != 1:
        raise ServeError(
            "invalid_arguments",
            "pass exactly one of --prompt, --prompt-file or --prompt-token-ids "
            f"(got {sum(sources)})",
        )
    prompt_text: str | None = args.prompt
    if args.prompt_file is not None:
        path = Path(args.prompt_file).expanduser()
        if not path.is_file():
            raise ServeError("invalid_arguments", f"--prompt-file is not a readable file: {path}")
        prompt_text = path.read_text(encoding="utf-8")
    prompt_token_ids = (
        _parse_prompt_token_ids(args.prompt_token_ids)
        if args.prompt_token_ids is not None
        else None
    )
    if not args.model:
        raise ServeError("invalid_arguments", "--model is required")
    return ServeRequest(
        model=args.model,
        backend=args.backend,
        prompt_text=prompt_text if prompt_token_ids is None else None,
        prompt_token_ids=prompt_token_ids,
        max_new_tokens=args.max_new_tokens,
        engine_binary=args.engine_binary,
        weights_dtype=args.weights_dtype,
        converted_dir=args.converted_dir,
        allow_unprobed=args.allow_unprobed,
        timeout=args.timeout,
    )


def _render_human(outcome: ServeOutcome, *, dry_run: bool) -> None:
    plan = outcome.plan
    gate = plan.gate
    print(f"model:   {plan.request.model}")
    requested = plan.request.backend
    resolved = gate.resolved_backend
    if resolved is None:
        print(f"backend: {requested} (unresolved)")
    elif requested == "auto":
        print(f"backend: {resolved} (auto-detected; requested: {requested})")
        for name in sorted(gate.detection):
            codes = ", ".join(refusal.code for refusal in gate.detection[name]) or "ok"
            print(f"  detect[{name}]: {codes}")
    else:
        print(f"backend: {resolved} (explicit)")
    if plan.launch is not None:
        print(
            f"engine:  {plan.launch.engine_path or '(in-process)'}"
            f" [{plan.launch.engine_source or plan.launch.kind}]"
        )
        print(f"launch:  {' '.join(plan.launch.argv)}")
    if plan.prompt_token_count is not None:
        print(
            f"prompt:  {plan.prompt_token_count} token(s) -> max {plan.request.max_new_tokens} new"
        )
    if plan.converted_dir:
        print(f"convert: {plan.converted_dir}")

    if not gate.accepted:
        # Flush first: stdout is block-buffered when piped, and a refusal that
        # reaches the terminal ahead of the plan it belongs to reads as though it
        # came from a different command.
        sys.stdout.flush()
        for refusal in gate.refusals:
            print(f"REFUSED: {refusal.message()}", file=sys.stderr)
        return
    if dry_run:
        print("dry-run: gated and resolved; nothing was converted or launched")
        return
    if outcome.error is not None:
        sys.stdout.flush()
        print(f"ERROR: {outcome.error.code}: {outcome.error}", file=sys.stderr)
        return
    if outcome.refusal is not None:
        sys.stdout.flush()
        print(f"REFUSED: {outcome.refusal.message()}", file=sys.stderr)
        return
    if outcome.timing:
        rendered = " ".join(f"{key}={value:g}" for key, value in sorted(outcome.timing.items()))
        print(f"timing:  {rendered}")
    print(f"tokens:  {len(outcome.token_ids)} generated")
    if outcome.text is not None:
        print("text:    " + outcome.text.replace("\n", "\n         "))


def _exit_code(outcome: ServeOutcome, *, dry_run: bool) -> int:
    if outcome.error is not None:
        return EXIT_ERROR
    refusals = list(outcome.plan.gate.refusals)
    if outcome.refusal is not None and outcome.refusal not in refusals:
        refusals.append(outcome.refusal)
    if refusals:
        codes = {refusal.code for refusal in refusals}
        if codes == {_PENDING_CODE}:
            return EXIT_PENDING
        return EXIT_REFUSED
    if dry_run:
        return EXIT_OK
    return EXIT_OK if outcome.ok else EXIT_ERROR


def _dry_run_plan(request: ServeRequest) -> ServePlan:
    """The plan a dry run reports: fully gated, with the prompt resolved when it can be.

    A dry run must never fail on something only a real launch needs, so a prompt
    that cannot be tokenized here (no tokenizer.json beside the config, say)
    degrades to a plan without a token count instead of an error — the gate has
    already judged everything it is the gate's job to judge.
    """
    try:
        return plan_serve(request, resolve_prompt=True)
    except ServeError:
        return plan_serve(request, resolve_prompt=False)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.backends:
        return _print_backends()

    try:
        request = _build_request(args)
    except ServeError as exc:
        print(f"error: {exc.code}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        if args.dry_run:
            outcome = ServeOutcome(plan=_dry_run_plan(request))
        else:
            outcome = serve(request, dry_run=False)
    except ServeError as exc:
        print(f"error: {exc.code}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(outcome.as_dict(), indent=2, default=str))
    else:
        _render_human(outcome, dry_run=args.dry_run)
    return _exit_code(outcome, dry_run=args.dry_run)
