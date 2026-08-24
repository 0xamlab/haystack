"""The onboarding identity gate — engine greedy tokens vs an independent
transformers fp32 CPU reference, reused across models with zero per-model code.

Two backends, both driven by facts/converter output, both reusing the EXISTING
engine doors (never a per-model fork):

* `gate_metal`  — the production SDK path `algenta.inference.decode` (Metal
  resident session), converting the checkpoint with the same model-agnostic
  converter the decode door uses.
* `gate_cuda`   — the fact-driven `conform_generate_cuda` resident binary,
  which reads every fact from the converted manifest itself.

Sampling is pinned in the reference (`do_sample=False`, `repetition_penalty=
1.0`) so the comparison is greedy-vs-greedy, and a flip at a sub-noise top-2
margin is classified as a documented near-tie (the engine computes on narrowed
weights), not a defect.
"""

from __future__ import annotations

from typing import Any

_NEAR_TIE_MARGIN = 0.05
_PROMPT_DEFAULT = "The capital of France is"


def _reference_tokens(checkpoint_dir: str, prompt_ids: list[int], max_new: int) -> list[int]:
    """The independent transformers fp32 CPU greedy continuation."""
    import torch
    from transformers import AutoModelForCausalLM

    reference = AutoModelForCausalLM.from_pretrained(checkpoint_dir, torch_dtype=torch.float32)
    reference.eval()
    input_ids = torch.tensor([prompt_ids], dtype=torch.long)
    with torch.no_grad():
        out = reference.generate(
            input_ids,
            max_new_tokens=max_new,
            do_sample=False,
            repetition_penalty=1.0,  # pinned: never trust generate() defaults
        )
    return [int(t) for t in out[0][len(prompt_ids):].tolist()]


def _classify(engine: list[int], ref: list[int], logits_fn) -> dict[str, Any]:
    """Compare token streams; on a flip, consult the reference logits to decide
    near-tie (documented) vs genuine mismatch."""
    if engine == ref:
        return {"status": "pass", "detail": f"{len(ref)}/{len(ref)} tokens identical"}
    flip = next(
        (i for i in range(min(len(engine), len(ref))) if engine[i] != ref[i]),
        None,
    )
    if flip is not None:
        try:
            margin, rank = logits_fn(flip, engine[flip])
        except Exception:  # noqa: BLE001 - margin probe is best-effort
            margin, rank = None, None
        if margin is not None and margin < _NEAR_TIE_MARGIN and rank == 2:
            return {
                "status": "pass",
                "detail": (
                    f"near-tie at token {flip + 1}: engine took rank-{rank} token at fp32 "
                    f"margin {margin:.4f}; {flip}/{len(ref)} before the flip identical"
                ),
            }
    return {"status": "fail", "detail": f"engine={engine} reference={ref}"}


def gate_metal(checkpoint_dir: str, prompt: str, max_new: int) -> dict[str, Any]:
    """Identity gate through the production Metal SDK path."""
    import os

    import torch
    from transformers import AutoTokenizer

    from algenta import MojoRuntime
    from algenta.inference import decode

    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=True)

    runtime = MojoRuntime(mode="local", timeout=900.0)
    result = decode(
        runtime,
        checkpoint_dir=checkpoint_dir,
        prompt_token_ids=prompt_ids,
        max_new_tokens=max_new,
    )
    engine = list(result.token_ids[result.n_prompt:])

    from transformers import AutoModelForCausalLM

    reference = AutoModelForCausalLM.from_pretrained(checkpoint_dir, torch_dtype=torch.float32)
    reference.eval()
    ref = _reference_tokens(checkpoint_dir, prompt_ids, max_new)

    def logits_fn(flip: int, engine_tok: int):
        ctx = torch.tensor([prompt_ids + ref[:flip]], dtype=torch.long)
        with torch.no_grad():
            flip_logits = reference(ctx).logits[0, -1]
        top2 = flip_logits.topk(2)
        margin = float(top2.values[0] - top2.values[1])
        rank = int((flip_logits > flip_logits[engine_tok]).sum().item()) + 1
        return margin, rank

    return _classify(engine, ref, logits_fn)


def gate_cuda(
    checkpoint_dir: str, driver: str, prompt: str, max_new: int, facts: Any
) -> dict[str, Any]:
    """Identity gate through the fact-driven CUDA conform driver."""
    import subprocess
    import tempfile
    from pathlib import Path

    import torch
    from transformers import AutoTokenizer

    from algenta.inference import prepare_model_checkpoint

    tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=True)

    converted = Path(tempfile.mkdtemp(prefix="onboard-cuda-converted-"))
    prepare_model_checkpoint(checkpoint_dir, prompt_ids, out_dir=str(converted), backend="cuda")

    proc = subprocess.run(
        [driver, str(converted), "--max-new", str(max_new)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    engine = None
    for line in proc.stdout.splitlines():
        if line.startswith("CONFORM_TOKENS:"):
            engine = [int(t) for t in line.split()[1:]]
    if engine is None:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or ["<no output>"]
        return {"status": "error", "detail": f"driver produced no tokens: {tail[0][:160]}"}

    from transformers import AutoModelForCausalLM

    reference = AutoModelForCausalLM.from_pretrained(checkpoint_dir, torch_dtype=torch.float32)
    reference.eval()

    ref = _reference_tokens(checkpoint_dir, prompt_ids, max_new)

    def logits_fn(flip: int, engine_tok: int):
        ctx = torch.tensor([prompt_ids + ref[:flip]], dtype=torch.long)
        with torch.no_grad():
            flip_logits = reference(ctx).logits[0, -1]
        top2 = flip_logits.topk(2)
        margin = float(top2.values[0] - top2.values[1])
        rank = int((flip_logits > flip_logits[engine_tok]).sum().item()) + 1
        return margin, rank

    return _classify(engine, ref, logits_fn)
