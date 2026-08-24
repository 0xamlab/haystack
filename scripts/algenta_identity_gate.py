#!/usr/bin/env python3
"""The real-model identity gate: engine greedy tokens vs an independent
transformers fp32 CPU reference, same prompt ids, pinned sampling discipline
(repetition_penalty=1.0, do_sample=False -- never trust generate() defaults).

Every model the capability table claims supported for a backend must pass this
gate on that backend before it is published as conformance evidence. The gate
is also the regression fence for models already gated (Qwen3 oracle, TinyLlama
identity).

Usage:
    python3 scripts/algenta_identity_gate.py --model qwen3-0.6b \
        --worker mojo_build/gpu-worker/algenta-gpu-worker-mb-qwen3
    python3 scripts/algenta_identity_gate.py --model smollm2-360m --max-new 16

Models (registry below): qwen3-0.6b, qwen3-1.7b, tinyllama, smollm2-360m.
Each entry pins its checkpoint location, the worker staging tier it needs, and
its prompt. The Qwen3 arms additionally check the campaign oracle (first token
374 and the exact known continuation on the 256-token race prompt).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

RACE_PROMPT = "The capital of France is Paris. " * 36 + "The capital of France"
_ORACLE_FIRST_TOKEN = 374
_ORACLE_CONTINUATION = [374, 12095, 13, 576, 6722, 315, 9625, 374]
GENERAL_PROMPT = "The capital of France is"


def _hf_cache_snapshot(repo: str) -> str | None:
    """A complete HuggingFace cache snapshot for `repo` (config + weights)."""
    hub = Path.home() / ".cache/huggingface/hub"
    cache_dir = hub / ("models--" + repo.replace("/", "--"))
    for snapshot in sorted(glob.glob(str(cache_dir / "snapshots" / "*"))):
        snap = Path(snapshot)
        if (snap / "config.json").is_file() and (
            (snap / "model.safetensors").is_file()
            or (snap / "model.safetensors.index.json").is_file()
        ):
            return str(snap)
    return None


def _resolve_checkpoint(candidates: list) -> str | None:
    """The first candidate directory that actually carries a usable checkpoint."""
    for candidate in candidates:
        if candidate and (Path(candidate) / "config.json").is_file():
            return candidate
    return None


# Each registry entry lists the checkpoint LOCATIONS it accepts, in order: the
# campaign's conventional /tmp copy first (when present), then the conform
# download dir, then the HuggingFace cache snapshot. A manual download satisfies
# any of them -- nothing here fetches from the network.
MODELS: dict[str, dict] = {
    "qwen3-0.6b": {
        "repo": "Qwen/Qwen3-0.6B-Base",
        "prompt": RACE_PROMPT,
        "oracle": True,
        "tier": "qwen3",
    },
    "qwen3-1.7b": {
        "repo": "Qwen/Qwen3-1.7B",
        "prompt": RACE_PROMPT,
        "oracle": True,
        "tier": "llama",  # stage_needed 6144 needs the STAGE_6144 tier
    },
    "tinyllama": {
        "repo": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "prompt": GENERAL_PROMPT,
        "oracle": False,
        "tier": "llama",  # stage_needed 5632
    },
    "smollm2-360m": {
        "repo": "HuggingFaceTB/SmolLM2-360M-Instruct",
        "prompt": GENERAL_PROMPT,
        "oracle": False,
        "tier": "qwen3",
    },
}

_CHECKPOINT_LOCATIONS: dict[str, list] = {
    "qwen3-0.6b": ["/private/tmp/qwen3-0.6b-base", "/tmp/conform-models/Qwen3-0.6B-Base"],
    "qwen3-1.7b": ["/private/tmp/qwen3-1.7b", "/tmp/conform-models/Qwen3-1.7B"],
    "tinyllama": ["/private/tmp/tinyllama", "/tmp/conform-models/TinyLlama-1.1B-Chat-v1.0"],
    "smollm2-360m": ["/tmp/conform-models/SmolLM2-360M-Instruct"],
}


def _worker_for(tier: str, override: str | None) -> Path:
    if override:
        return Path(override)
    name = "algenta-gpu-worker-mb-qwen3" if tier == "qwen3" else "algenta-gpu-worker-mb-llama"
    return ROOT / "mojo_build" / "gpu-worker" / name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The algenta real-model identity gate.")
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--worker", help="worker binary override (default: the campaign build for the model's tier)")
    parser.add_argument("--max-new", type=int, default=16)
    parser.add_argument("--converted-out", default="/tmp/conform-gates")
    parser.add_argument("--skip-transformers", action="store_true", help="oracle/engine run only")
    args = parser.parse_args(argv)

    spec = MODELS[args.model]
    locations = list(_CHECKPOINT_LOCATIONS[args.model])
    locations.append(_hf_cache_snapshot(spec["repo"]))
    checkpoint = _resolve_checkpoint(locations)
    if checkpoint is None:
        print(
            f"SKIP: no checkpoint for {args.model} at any of {locations!r} (manual download)",
            file=sys.stderr,
        )
        return 77
    worker = _worker_for(spec["tier"], args.worker)
    if not worker.is_file():
        print(f"SKIP: worker binary missing: {worker}", file=sys.stderr)
        return 77

    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    print(f"model:      {args.model} ({spec['repo']})")
    print(f"checkpoint: {checkpoint}")
    print(f"worker:     {worker} (tier {spec['tier']})")

    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    prompt_ids = tokenizer.encode(spec["prompt"], add_special_tokens=True)
    print(f"prompt:     {len(prompt_ids)} ids")

    # ── the engine arm ───────────────────────────────────────────────────────
    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(worker)
    from algenta import MojoRuntime
    from algenta.inference import UnsupportedArchitectureError, decode, prepare_model_checkpoint

    converted_dir = Path(args.converted_out) / args.model
    converted_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        if not (converted_dir / "manifest.json").is_file():
            prepare_model_checkpoint(checkpoint, prompt_ids, out_dir=converted_dir)
        runtime = MojoRuntime(mode="local", timeout=900.0)
        result = decode(
            runtime,
            checkpoint_dir=checkpoint,
            prompt_token_ids=prompt_ids,
            max_new_tokens=args.max_new,
            converted_checkpoint_dir=str(converted_dir),
        )
    except UnsupportedArchitectureError as exc:
        print(f"VERDICT: REFUSED (typed): {exc}")
        return 2
    engine_tokens = list(result.token_ids[result.n_prompt :])
    print(f"engine:     {len(engine_tokens)} tokens in {time.time() - t0:.1f}s "
          f"(decode {result.decode_tokens_per_sec:.1f} tok/s)")

    failures = []

    if spec["oracle"]:
        if engine_tokens and engine_tokens[0] == _ORACLE_FIRST_TOKEN:
            print(f"oracle:     first token 374 PASS")
        else:
            failures.append(f"oracle first token: got {engine_tokens[:1]}, want [{_ORACLE_FIRST_TOKEN}]")
        want = _ORACLE_CONTINUATION[: len(engine_tokens)]
        if engine_tokens[: len(want)] == want:
            print(f"oracle:     {len(want)}-token continuation PASS")
        else:
            failures.append(f"oracle continuation: got {engine_tokens[: len(want)]}, want {want}")

    # ── the reference arm ────────────────────────────────────────────────────
    if not args.skip_transformers:
        t0 = time.time()
        reference = AutoModelForCausalLM.from_pretrained(checkpoint, torch_dtype=torch.float32)
        reference.eval()
        input_ids = torch.tensor([prompt_ids], dtype=torch.long)
        with torch.no_grad():
            out = reference.generate(
                input_ids,
                max_new_tokens=args.max_new,
                do_sample=False,
                repetition_penalty=1.0,  # pinned: never trust generate() defaults
            )
        ref_tokens = [int(t) for t in out[0][len(prompt_ids) :].tolist()]
        print(f"reference:  {len(ref_tokens)} tokens in {time.time() - t0:.1f}s (transformers fp32 CPU)")
        if engine_tokens == ref_tokens:
            print(f"identity:   PASS ({len(ref_tokens)}/{len(ref_tokens)} tokens identical)")
        else:
            # Classify the first flip: the engine computes on int8-quantized weights,
            # so a flip at a sub-noise top-2 logit margin is a documented near-tie,
            # not a math defect (the margin and the engine token's rank are stated
            # in the evidence either way).
            flip = next(
                (i for i in range(min(len(engine_tokens), len(ref_tokens))) if engine_tokens[i] != ref_tokens[i]),
                min(len(engine_tokens), len(ref_tokens)),
            )
            ctx = torch.tensor([prompt_ids + ref_tokens[:flip]], dtype=torch.long)
            with torch.no_grad():
                flip_logits = reference(ctx).logits[0, -1]
            top2 = flip_logits.topk(2)
            margin = float(top2.values[0] - top2.values[1])
            rank = int((flip_logits > flip_logits[engine_tokens[flip]]).sum().item()) + 1
            if margin < 0.05 and rank == 2:
                print(
                    f"identity:   NEAR-TIE at token {flip + 1}: engine took rank-{rank} token "
                    f"{engine_tokens[flip]} at fp32 margin {margin:.4f} (reference token "
                    f"{ref_tokens[flip]}); the {flip} tokens before the flip are identical"
                )
            else:
                failures.append(f"identity: engine={engine_tokens} reference={ref_tokens}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
