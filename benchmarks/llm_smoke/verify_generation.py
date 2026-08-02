"""verify_generation.py — cross-check `qwen3_generate.mojo`'s generated token sequence against
`reference_generate.py`'s independent `transformers`-CPU (float32) greedy decode, on the same
checkpoint and the same prompt.

Both sides hold a REAL KV cache (Mojo's own, and `transformers`' `past_key_values`), so this is not
comparing a cache against a from-scratch recompute -- it is comparing two independently-built decode
loops' actual greedy choices, position by position. Agreement is the pass/fail signal, same as
`verify_forward_pass.py`'s "does argmax(logits) match at every position" gate for the prefill-only
forward pass this file's decode loop extends.
"""

import json
import sys
from pathlib import Path


def main() -> int:
    mojo_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "/tmp/bb/qwen3_ckpt/mojo_generate_llmfwd/generated_ids.txt"
    )
    ref_path = Path(
        sys.argv[2] if len(sys.argv) > 2 else "/tmp/bb/qwen3_ckpt/reference_generate/reference_generated.json"
    )

    lines = mojo_path.read_text().splitlines()
    n_prompt = int(lines[0].split()[1])
    n_generated = int(lines[1].split()[1])
    stopped_on_eos_mojo = lines[2].split()[1] == "1"
    mojo_ids = []
    mojo_logits = []
    for line in lines[3:3 + n_generated]:
        _step, _pos, tok_id, logit, _step_ms = line.split()
        mojo_ids.append(int(tok_id))
        mojo_logits.append(float(logit))

    ref = json.loads(ref_path.read_text())
    ref_ids = ref["new_ids"]
    ref_logits = ref["step_logits"]
    ref_n_prompt = ref["n_prompt"]

    print(f"mojo:      n_prompt={n_prompt} n_generated={n_generated} stopped_on_eos={stopped_on_eos_mojo}")
    print(f"reference: n_prompt={ref_n_prompt} n_generated={len(ref_ids)} stopped_on_eos={ref['stopped_on_eos']}")

    if n_prompt != ref_n_prompt:
        print(f"\nFAIL: prompt length disagrees ({n_prompt} vs {ref_n_prompt}) -- not comparable")
        return 1

    n_compare = min(len(mojo_ids), len(ref_ids))
    agree_positions = []
    for i in range(n_compare):
        agree = mojo_ids[i] == ref_ids[i]
        agree_positions.append(agree)
        delta = abs(mojo_logits[i] - ref_logits[i])
        flag = "OK" if agree else "DIVERGE"
        print(f"  step {i:2d} (pos {n_prompt + i:3d}): mojo={mojo_ids[i]:6d} ref={ref_ids[i]:6d} "
              f"[{flag}]  logit mojo={mojo_logits[i]:.6f} ref={ref_logits[i]:.6f} |delta|={delta:.2e}")

    all_agree = all(agree_positions) and len(mojo_ids) == len(ref_ids)
    if all_agree:
        print(f"\nGENERATION LOOP VERIFIED: all {n_compare} greedy-decoded tokens match the "
              "independent transformers reference, position by position.")
    else:
        first_diverge = next((i for i, a in enumerate(agree_positions) if not a), None)
        print(f"\nGENERATION LOOP DIVERGES: first mismatch at step {first_diverge} "
              f"(absolute position {n_prompt + first_diverge if first_diverge is not None else '?'})"
              if first_diverge is not None else
              "\nGENERATION LOOP DIVERGES: sequences have different lengths")
    return 0 if all_agree else 1


if __name__ == "__main__":
    raise SystemExit(main())
