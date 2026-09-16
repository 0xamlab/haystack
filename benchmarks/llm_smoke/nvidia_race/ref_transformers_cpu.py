"""ref_transformers_cpu.py — the transformers CPU fp32 reference for gate (a) part 2.

Loads Qwen2.5-7B-Instruct in FLOAT32 on the CPU and greedily decodes the first 16 generated
tokens for each of the 5 chat prompts (and the 256-token fixture) from prompts.json, using the
SAME pre-tokenized prompt ids the CUDA driver and llama.cpp consume. This is the ground-truth
reference the campaign's gates price our engine against — it is slow (fp32 CPU), so it is run
once, offline, and its token streams are written to ref_tokens.json for the harness to diff.

PURE-GREEDY DISCIPLINE (2026-08-23 bisection finding): Qwen2.5-7B-Instruct ships a
generation_config.json with `repetition_penalty: 1.05` (and temperature 0.7 / top-k 20 /
top-p 0.8), and `model.generate()` silently applies ANY generation-config value the call does
not override. The first reference file was produced with the 1.05 penalty active — it flipped
the chat_1 step-6 near-tie (raw-logit argmax 323 @ 27.202 vs 374 @ 26.163; 27.202/1.05 =
25.907 < 26.163) and disagreed with the model's OWN plain-forward argmax, verified bit-for-bit
via the lm_head-input hidden probe (probe_generate_vs_manual.py). Our engine and llama.cpp
both run penalty-free argmax, so the oracle MUST too: this script pins repetition_penalty=1.0
(and the rest of the sampling knobs to greedy no-ops) explicitly.

Usage (on the VM):
    python3 ref_transformers_cpu.py --model-dir ~/models/Qwen2.5-7B-Instruct \
        --ckpt /tmp/w7b/ckpt --n-tokens 16 --out /tmp/w7b/gate/ref_tokens.json

RAG-4096 CASES (FRONT 6, 2026-09-16). `--cases rag` adds the three token-exact 4096-token RAG
prompts as oracle cases, which closes a hole every previous round had: the RAG-4096 cell was
gated ONLY by G1 (64/64 self-consistency), because G0's oracle covered the 256-token fixture
and the five chat prompts but no long prompt. Self-consistency cannot detect a lever that is
deterministically WRONG, and FRONT 6's lever (`ALGENTA_PF_PASS4096`) only activates above 1024
prompt rows — so the fixture oracle proves literally nothing about it. The driver's G0 IS valid
under `--prompt-ids` (it sets `n_prompt = len(race_ids)`, so the decode positions are the RAG
prompt's own); it was only ever fed the wrong oracle. Pass the matching `rag_N` stream and G0
becomes a real 16/16 gate on the raced prompt.

The default `--cases fixture,chat` reproduces the existing artifact byte-for-byte (verified
against the 2026-08-26 record in FRONT 5), so writing a rag oracle to its OWN file leaves the
shipped gate untouched. `--prompts` overrides where the ids are read from, because the RAG
prompts live in ~/trtllm/prompts.json rather than in the checkpoint's own prompts.json.
"""

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ckpt", default="/tmp/w7b/ckpt")
    ap.add_argument("--n-tokens", type=int, default=16)
    ap.add_argument("--out", default="/tmp/w7b/gate/ref_tokens.json")
    ap.add_argument("--prompts", default="",
                    help="prompts.json to read ids from (default: <ckpt>/prompts.json)")
    ap.add_argument("--cases", default="fixture,chat",
                    help="comma list of fixture,chat,rag (default reproduces the shipped artifact)")
    ap.add_argument("--no-eos-stop", action="store_true",
                    help="decode the full n_tokens by pure argmax, never stopping "
                         "at EOS (matches the CUDA driver G0; needed for long prompts)")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    want = {c.strip() for c in args.cases.split(",") if c.strip()}
    prompts_path = Path(args.prompts) if args.prompts else (Path(args.ckpt) / "prompts.json")
    prompts = json.loads(prompts_path.read_text())
    cases = []
    if "fixture" in want:
        cases.append({"name": "fixture", "ids": prompts["fixture"]["ids"]})
    if "chat" in want:
        for idx, entry in enumerate(prompts["chat_prompts"]):
            cases.append({"name": f"chat_{idx}", "ids": entry["ids"]})
    if "rag" in want:
        for idx, entry in enumerate(prompts["rag"]):
            cases.append({"name": f"rag_{idx}", "ids": entry["ids"]})
    print(f"[ref] prompts from {prompts_path}; cases: {[c['name'] for c in cases]}", flush=True)

    print(f"[ref] loading {args.model_dir} in fp32 on CPU ...", flush=True)
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(args.model_dir)
    # No device_map (that pulls in `accelerate`); from_pretrained defaults to CPU weights.
    model = AutoModelForCausalLM.from_pretrained(args.model_dir, torch_dtype=torch.float32)
    model = model.to("cpu")
    model.eval()
    print(f"[ref] loaded in {time.time()-t0:.1f}s", flush=True)

    results = {}
    for case in cases:
        ids = case["ids"]
        inp = torch.tensor([ids], dtype=torch.long)
        t1 = time.time()
        with torch.no_grad():
            out = model.generate(
                inp,
                max_new_tokens=args.n_tokens,
                # --no-eos-stop drops EOS from the stopping criteria so generate() runs
                # the full n_tokens PURE ARGMAX steps, which is what the engine G0 does.
                # min_new_tokens is the WRONG way to get that: it forces the EOS logit
                # to -inf until the minimum is reached, so it does not merely keep
                # decoding past EOS, it CHANGES which token is the argmax at the step
                # where EOS won. Measured (FRONT 6): on RAG-4096 the greedy argmax at
                # step 4 IS the EOS token 151645 and all three arms emit it, while a
                # min_new_tokens oracle emits 11 instead and then diverges for 12 more
                # tokens -- reading as a catastrophic engine failure that was in fact a
                # defective reference. Default off, so the shipped fixture/chat artifact
                # is reproduced by construction rather than by verification.
                eos_token_id=(None if args.no_eos_stop else tok.eos_token_id),
                do_sample=False,           # greedy
                temperature=0.0,
                repetition_penalty=1.0,    # PURE GREEDY: override the model's own
                top_k=0,                   # generation_config.json (penalty 1.05,
                top_p=1.0,                 # temp 0.7, top_k 20, top_p 0.8) — see the
                min_p=0.0,                 # module docstring's 2026-08-23 finding.
                pad_token_id=tok.eos_token_id,
                return_dict_in_generate=True,
            )
        gen = out.sequences[0][len(ids):].tolist()
        results[case["name"]] = {
            "prompt_tokens": len(ids),
            "generated_ids": [int(t) for t in gen],
            "text": tok.decode(gen, skip_special_tokens=False),
        }
        print(f"[ref] {case['name']}: {len(gen)} tokens in {time.time()-t1:.1f}s "
              f"-> {results[case['name']]['text'][:60]!r}", flush=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=1))
    print(f"[ref] wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
