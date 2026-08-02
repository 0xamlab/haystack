"""Reference forward pass through the REAL Qwen3-0.6B-Base checkpoint via `transformers`.

Dumps embedding output, every layer's hidden state, and final logits for a fixed short prompt, to a
.npz file `compare.py` reads. This is the ground truth most users would actually get: a real,
unmodified Qwen3ForCausalLM, real weights, CPU, `torch.float32` (transformers' own default compute
dtype -- the checkpoint's native storage is BF16). See `run_reference_fp64.py` for the float64
sibling used to isolate whether a divergence comes from THIS reference's own float32 precision floor
or from the Mojo kernels.
"""
import json
import time

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = "/tmp/qwen3-0.6b-base"
OUT_PATH = "/tmp/qwen3smoke/reference_dump.npz"
PROMPT = "The capital of France is"

torch.manual_seed(0)


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, torch_dtype=torch.float32, attn_implementation="eager"
    )
    model.eval()

    enc = tok(PROMPT, return_tensors="pt")
    input_ids = enc["input_ids"]
    print("token ids:", input_ids.tolist())
    print("tokens:", tok.convert_ids_to_tokens(input_ids[0].tolist()))

    with torch.no_grad():
        t0 = time.perf_counter()
        out = model(
            input_ids=input_ids,
            output_hidden_states=True,
            use_cache=False,
        )
        t1 = time.perf_counter()

    # hidden_states: tuple of (n_layers + 1) tensors. Verified against transformers' own source
    # (Qwen3Model.forward): hidden_states[0] is the embedding output; hidden_states[i] for
    # i in [1, n_layers) is the RAW output of decoder layer (i - 1); hidden_states[n_layers] is
    # norm(raw output of the LAST layer) -- the model's final RMSNorm is applied to hidden_states
    # BEFORE that last entry is captured, not after. A raw-vs-raw comparison at the last index
    # looks like a huge divergence; it is a comparison-methodology bug, not a forward-pass one.
    hs = [h[0].detach().numpy().astype(np.float64) for h in out.hidden_states]
    logits = out.logits[0].detach().numpy().astype(np.float64)

    # Also grab the tied embedding table + final norm weight, so the Mojo driver's OWN norm +
    # lm_head projection can be checked as a separate stage from "the whole model agrees".
    embed_w = model.get_input_embeddings().weight.detach().numpy().astype(np.float64)
    final_norm_w = model.model.norm.weight.detach().numpy().astype(np.float64)

    save_kwargs = {"logits": logits, "input_ids": input_ids[0].numpy(), "embed_w": embed_w,
                    "final_norm_w": final_norm_w}
    for i, h in enumerate(hs):
        save_kwargs[f"hidden_{i}"] = h
    np.savez(OUT_PATH, **save_kwargs)

    latency_s = t1 - t0
    n_tokens = input_ids.shape[1]
    print(f"forward pass latency: {latency_s * 1000:.2f} ms for {n_tokens} tokens "
          f"({n_tokens / latency_s:.1f} tok/s, prefill)")
    print("n hidden_states:", len(hs), "shape each:", hs[0].shape)
    print("logits shape:", logits.shape)
    print("saved:", OUT_PATH)

    meta = {
        "prompt": PROMPT,
        "input_ids": input_ids[0].tolist(),
        "latency_ms": latency_s * 1000.0,
        "n_tokens": n_tokens,
        "tokens_per_sec_prefill": n_tokens / latency_s,
    }
    with open("/tmp/qwen3smoke/reference_meta.json", "w") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    main()
