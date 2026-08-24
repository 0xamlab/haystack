#!/usr/bin/env python3
"""algenta conform — the model support verdict, computed from facts.

Input: a HuggingFace checkpoint directory (config.json + optional safetensors
probe) or a bare config.json path. Output: the normalized fact manifest, the
per-layer kernel-path assignment, and the SUPPORT VERDICT — `supported`,
`supported_pending_probe` (config-only: the tensor-level facts still owe a
probe), or `refused` with TYPED refusals naming the exact unsupported fact and
the range the capability table supports ("head_dim=96 is not in {32, 64, 128,
256}"). A refusal is never silent and never by family name: two checkpoints
with identical facts get identical verdicts.

Usage:
    python3 scripts/algenta_conform.py /path/to/model-dir [--backend metal|cuda]
    python3 scripts/algenta_conform.py /path/to/config.json --json verdict.json
    python3 scripts/algenta_conform.py /path/to/model-dir --quiet; echo $?

Exit codes: 0 = supported, 3 = supported pending the tensor probe, 2 = refused,
1 = the input was not a usable checkpoint/config.

The capability table the verdict looks up is declared in
`packages/algenta/algenta/model_capabilities.py` (kernel path -> supported fact
ranges); the same table gates the converter and mirrors the engine's own
session-open gates, so this verdict is the cheapest possible point of refusal —
before any weights are converted or any GPU work is done.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = _ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.model_capabilities import (  # noqa: E402
    BACKEND_FACT_RANGES,
    KERNEL_PATH_CAPABILITIES,
    STRUCTURAL_FACT_RANGES,
    verdict_for_checkpoint,
)

EXIT_SUPPORTED = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2
EXIT_PENDING = 3


def _verdict_for_config_file(config_path: Path, backend: str) -> dict:
    """The config-only verdict for a bare config.json: the structural facts are
    judged, the tensor-level facts (qk_norm/bias presence) are reported as the
    probe they still owe — never guessed."""
    from algenta.model_capabilities import (
        extract_facts_from_config,
        refusals_for_facts,
        select_paths,
        stage_needed,
        unverified_facts,
    )
    from algenta.inference import _normalize_config

    config = _normalize_config(json.loads(config_path.read_text(encoding="utf-8")))
    facts = extract_facts_from_config(config)
    refusal_list = refusals_for_facts(facts, backend=backend)
    result: dict = {"model": str(config_path), "backend": backend, "facts": facts.as_dict()}
    if refusal_list:
        result["status"] = "refused"
        result["refusals"] = [
            {
                "fact": refusal.fact,
                "value": refusal.value,
                "supported": refusal.supported,
                "detail": refusal.detail,
                "message": refusal.message(),
            }
            for refusal in refusal_list
        ]
        return result
    pending = unverified_facts(facts)
    if pending:
        result["status"] = "supported_pending_probe"
        result["pending_probe"] = pending
    else:
        result["status"] = "supported"
    assignment = select_paths(facts)
    result["assignment"] = {
        "plan": assignment.plan,
        "prefill_attention": assignment.prefill_attention,
        "decode_attention": assignment.decode_attention,
        "decode_splitk_partial": assignment.decode_splitk_partial,
        "kv_producer": assignment.kv_producer,
        "gemm_tiers": list(assignment.gemm_tiers),
        "batched_decode": assignment.batched_decode,
        "layers": assignment.per_layer(facts.num_hidden_layers or 0),
    }
    result["stage_needed"] = stage_needed(facts)
    return result


def _run_onboard(rest: list[str]) -> int:
    """The onboarding loop: `algenta_conform.py onboard <hf-repo-or-local-config>`.

    (a) extract facts via the converter gate, (b) capability-table decision per
    backend, (c) name the staging tier that would flip a pure-staging refusal,
    (d) emit a support-matrix row + a JSON ledger line. Zero per-model
    hardcoding: everything is a function of the normalized fact manifest. With
    `--gate` and an available backend, also run the identity gate (engine greedy
    vs transformers fp32 reference) and fold the result into the ledger."""
    from algenta.onboarding import (
        backend_staging_ceiling,
        backend_verdicts,
        emit_ledger,
        emit_support_row,
        onboard_facts,
        resolve_config,
        staging_tier_gap,
    )

    parser = argparse.ArgumentParser(
        prog="algenta_conform onboard",
        description="Fact-driven model onboarding: facts -> capability verdict -> ledger row.",
    )
    parser.add_argument("source", help="an HF repo id (org/name) or a local checkpoint dir / config.json")
    parser.add_argument("--name", help="display name for the ledger row (defaults to the source)")
    parser.add_argument("--gate", action="store_true", help="also run the identity gate where a backend is available")
    parser.add_argument("--ledger", metavar="FILE", help="append the JSON ledger line to FILE")
    args = parser.parse_args(rest)

    config, source_desc, weights_dir = resolve_config(args.source)
    facts = onboard_facts(config)
    verdicts = backend_verdicts(facts)
    name = args.name or source_desc

    print(f"onboard: {name}  (source: {source_desc}, weights: {'present' if weights_dir else 'absent'})")
    for backend in sorted(verdicts):
        v = verdicts[backend]
        if v.supported:
            line = f"  [{backend}] {v.status}" + (f" plan={v.plan}" if v.plan else "")
            if v.pending_probe:
                line += f" (pending probe: {', '.join(v.pending_probe)})"
            print(line)
        else:
            for refusal in v.refusals:
                print(f"  [{backend}] REFUSED: {refusal.message()}")
        gap = staging_tier_gap(facts, backend)
        if gap is not None:
            ceiling = backend_staging_ceiling(backend)
            if gap <= ceiling:
                print(
                    f"  [{backend}] staging-tier gap ONLY: add ALGENTA_STAGE_{gap} "
                    f"(stage_needed={gap}) to flip this model to supported on {backend}"
                )
            else:
                print(
                    f"  [{backend}] stage_needed={gap} exceeds {backend}'s buildable staging "
                    f"ceiling ({ceiling}, set by its shared-memory budget) — a hardware limit, "
                    "not a missing build; this backend cannot run the model at any tier"
                )

    gates: dict = {}
    if args.gate:
        gates = _run_onboard_gates(name, facts, verdicts, weights_dir)

    print("support-matrix row:")
    print(emit_support_row(name, facts, verdicts))
    ledger = emit_ledger(name, facts, verdicts, gates)
    if args.ledger:
        with open(args.ledger, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(ledger) + "\n")
        print(f"ledger appended: {args.ledger}")
    print("ledger json:")
    print(json.dumps(ledger, indent=2))

    # Exit code reflects whether ANY backend supports the model.
    return EXIT_SUPPORTED if any(v.supported for v in verdicts.values()) else EXIT_REFUSED


def _run_onboard_gates(name, facts, verdicts, weights_dir) -> dict:
    """Identity gate per supported backend whose engine is available on this
    host. Reuses the existing doors (Metal SDK decode; CUDA conform driver);
    never forks a per-model harness. Returns {backend: gate-record}."""
    gates: dict = {}
    prompt = "The capital of France is"
    max_new = 16

    # Metal arm: production SDK path, when a Metal worker is configured.
    metal = verdicts.get("metal")
    worker = os.environ.get("ALGENTA_NATIVE_WORKER")
    if metal and metal.supported and weights_dir and worker and Path(worker).is_file():
        try:
            from algenta.onboarding_gate import gate_metal

            gates["metal"] = gate_metal(str(weights_dir), prompt, max_new)
        except Exception as exc:  # noqa: BLE001 - a gate failure is recorded, not fatal
            gates["metal"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    # CUDA arm: fact-driven conform driver, when one is on PATH/override.
    cuda = verdicts.get("cuda")
    cuda_driver = os.environ.get("ALGENTA_CONFORM_CUDA_DRIVER")
    if cuda and cuda.supported and weights_dir and cuda_driver and Path(cuda_driver).is_file():
        try:
            from algenta.onboarding_gate import gate_cuda

            gates["cuda"] = gate_cuda(str(weights_dir), cuda_driver, prompt, max_new, facts)
        except Exception as exc:  # noqa: BLE001
            gates["cuda"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    for backend, record in gates.items():
        print(f"  gate[{backend}]: {record.get('status')} {record.get('detail', '')}")
    return gates


def main(argv: list[str] | None = None) -> int:
    # Subcommand dispatch: `onboard` runs the onboarding loop; anything else is
    # the existing single-checkpoint verdict path (unchanged).
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "onboard":
        return _run_onboard(argv[1:])
    parser = argparse.ArgumentParser(
        prog="algenta_conform",
        description="The algenta model support verdict, computed from declared facts.",
    )
    parser.add_argument(
        "path",
        help="a HuggingFace checkpoint directory (config.json + optional safetensors) or a bare config.json",
    )
    parser.add_argument(
        "--backend",
        default="metal",
        choices=sorted(BACKEND_FACT_RANGES),
        help="the hardware family whose kernel set would run the model (default: metal)",
    )
    parser.add_argument("--json", metavar="FILE", help="also write the full verdict JSON to FILE")
    parser.add_argument("--quiet", action="store_true", help="print nothing; exit code only")
    parser.add_argument(
        "--table",
        action="store_true",
        help="print the declared capability table and exit (ignores the path)",
    )
    args = parser.parse_args(argv)

    if args.table:
        print("structural fact ranges:")
        for fact, supported in STRUCTURAL_FACT_RANGES.items():
            print(f"  {fact}: {supported}")
        print("backend fact ranges:")
        for backend, ranges in BACKEND_FACT_RANGES.items():
            bias = ", ".join(str(b) for b in ranges["attention_bias"])
            tiers = ", ".join(str(t) for t in ranges["staging_tiers"])
            print(f"  {backend}: attention_bias {{{bias}}}; staging tiers {{{tiers}}}")
        print("kernel path capabilities:")
        for path, caps in KERNEL_PATH_CAPABILITIES.items():
            head_dim = caps.get("head_dim")
            qk_norm = caps.get("qk_norm")
            print(
                f"  {path}: head_dim={'any' if head_dim is None else set(head_dim)} "
                f"qk_norm={'any' if qk_norm is None else set(qk_norm)}"
            )
        return EXIT_SUPPORTED

    path = Path(args.path).expanduser()
    if path.is_file() and path.name.endswith(".json"):
        verdict = _verdict_for_config_file(path, args.backend)
    elif path.is_dir():
        verdict = verdict_for_checkpoint(path, backend=args.backend)
    else:
        if not args.quiet:
            print(f"error: {path} is neither a directory nor a .json file", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        Path(args.json).write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    status = verdict["status"]
    if not args.quiet:
        print(f"model:   {verdict['model']}")
        print(f"backend: {verdict['backend']}")
        print(f"verdict: {status}")
        if status == "refused":
            for refusal in verdict["refusals"]:
                print(f"  REFUSED: {refusal['message']}")
        else:
            facts = verdict["facts"]
            print(
                "facts:   "
                f"d_model={facts['hidden_size']} layers={facts['num_hidden_layers']} "
                f"h_q={facts['num_attention_heads']} h_kv={facts['num_key_value_heads']} "
                f"d_head={facts['head_dim']} d_ff={facts['intermediate_size']} "
                f"vocab={facts['vocab_size']} rope={facts['rope_class']} "
                f"tie={facts['tie_word_embeddings']} qk_norm={facts['has_qk_norm']} "
                f"bias={facts['attention_bias']} act={facts['activation']} "
                f"window={facts['sliding_window']} softcap={facts['attention_softcap']}"
            )
            if status == "supported_pending_probe":
                print(f"  pending probe: {', '.join(verdict['pending_probe'])}")
            assignment = verdict["assignment"]
            print(f"plan:    {assignment['plan']}")
            print(
                "paths:   "
                f"prefill_attn={assignment['prefill_attention']} "
                f"decode_attn={assignment['decode_attention']} "
                f"splitk={assignment['decode_splitk_partial']} "
                f"kvprod={assignment['kv_producer']} "
                f"batched={assignment['batched_decode']}"
            )
            if assignment["layers"]:
                print(f"per-layer assignment: {len(assignment['layers'])} layers, uniform")

    if status == "supported":
        return EXIT_SUPPORTED
    if status == "supported_pending_probe":
        return EXIT_PENDING
    return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
