"""ref_transformers_gemma3.py — HF-transformers CPU fp32 reference for the REAL-weights gate.

For the real-weights correctness gate the oracle is HuggingFace transformers' OWN Gemma 3
implementation (not the hand-rolled ref_gemma3_torch.py, which is the synthetic-gate oracle and is
itself already cross-validated against transformers). This loads the text model from a downloaded
gemma3 snapshot, runs it in float32 on CPU, and dumps the greedy token(s) and the full final
logits for a prompt so the engine arm can be diffed logit-for-logit.

Usage:
  python3 ref_transformers_gemma3.py --ckpt ~/models/gemma-3-4b-it --tokens 2,1756,3402,762 \
      --max-new 4 [--out ref.json]
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def _load_safetensors_index(ckpt: Path) -> dict:
    idx_path = ckpt / "model.safetensors.index.json"
    if idx_path.is_file():
        return json.loads(idx_path.read_text())
    # single shard: synthesize a weight_map from the header
    single = ckpt / "model.safetensors"
    with single.open("rb") as h:
        (hlen,) = struct.unpack("<Q", h.read(8))
        header = json.loads(h.read(hlen))
    return {"weight_map": {k: "model.safetensors" for k in header if k != "__metadata__"}}


def _read_tensor(ckpt: Path, weight_map: dict, name: str):
    import numpy as np

    shard = ckpt / weight_map[name]
    with shard.open("rb") as h:
        (hlen,) = struct.unpack("<Q", h.read(8))
        header = json.loads(h.read(hlen))
        data_start = 8 + hlen
        info = header[name]
        start, end = info["data_offsets"]
        h.seek(data_start + start)
        raw = h.read(end - start)
    dtype = info["dtype"]
    if dtype == "BF16":
        u16 = np.frombuffer(raw, dtype="<u2")
        arr = (u16.astype(np.uint32) << 16).view(np.float32)
    elif dtype == "F32":
        arr = np.frombuffer(raw, dtype="<f4")
    elif dtype == "F16":
        arr = np.frombuffer(raw, dtype="<f2").astype(np.float32)
    else:
        raise ValueError(f"unsupported dtype {dtype} for {name}")
    return arr.astype(np.float64).reshape(info["shape"]).copy()


def main() -> None:
    import torch

    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--tokens", required=True)
    parser.add_argument("--max-new", type=int, default=4)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    ckpt = Path(args.ckpt).expanduser()
    prompt = [int(p) for p in args.tokens.split(",") if p.strip()]

    config = json.loads((ckpt / "config.json").read_text())
    text_cfg = config.get("text_config", config)

    from transformers import Gemma3TextConfig
    from transformers.models.gemma3.modeling_gemma3 import Gemma3ForCausalLM

    # Build the text config from the snapshot's text_config dict (fills class defaults).
    tc = Gemma3TextConfig(**{k: v for k, v in text_cfg.items() if k != "model_type"})
    # Carry the wrapper's eos if present.
    if isinstance(config.get("eos_token_id"), list):
        tc.eos_token_id = config["eos_token_id"]

    weight_map = _load_safetensors_index(ckpt)["weight_map"]

    model = Gemma3ForCausalLM(tc)
    # Remap language_model.model.* -> model.* ; language_model.lm_head.* -> lm_head.*
    sd = {}
    for name in weight_map:
        if name.startswith("vision_tower.") or name.startswith("multi_modal_projector"):
            continue
        key = name
        if key.startswith("language_model."):
            key = key[len("language_model."):]
        sd[key] = name
    missing, unexpected = [], []
    own_sd = model.state_dict()
    loaded = {}
    for key, src in sd.items():
        if key in own_sd:
            loaded[key] = torch.from_numpy(_read_tensor(ckpt, weight_map, src)).to(torch.float32)
    miss, unexp = model.load_state_dict(loaded, strict=False)
    print("loaded:", len(loaded), "| missing:", [m for m in miss if 'lm_head' not in m],
          "| unexpected:", unexp)

    model.eval()
    model.to(torch.float32)  # the parent-task "CPU fp32 reference"

    tokens = list(prompt)
    generated = []
    for _ in range(args.max_new):
        input_ids = torch.tensor([tokens], dtype=torch.long)
        with torch.no_grad():
            out = model(input_ids=input_ids)
            logits = out.logits[0, -1]
        next_tok = int(logits.argmax().item())
        generated.append(next_tok)
        tokens.append(next_tok)
        eos = tc.eos_token_id if isinstance(tc.eos_token_id, list) else [tc.eos_token_id]
        if next_tok in eos:
            break

    # Final-position logits for the ORIGINAL prompt (what the engine's dump_logits compares).
    with torch.no_grad():
        out = model(input_ids=torch.tensor([prompt], dtype=torch.long))
        final_logits = out.logits[0, -1]

    result = {
        "prompt": prompt,
        "generated": generated,
        "argmax": int(final_logits.argmax().item()),
        "logits": [float(v) for v in final_logits],
        "eos": tc.eos_token_id if isinstance(tc.eos_token_id, list) else [tc.eos_token_id],
    }
    text = json.dumps(result)
    print(text if not args.out else text[:200] + "...")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
