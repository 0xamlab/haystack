"""Independent fp32 torch reference for Gemma 3 (Gemma 3 lane, 2026-08-23).

The correctness oracle every gemma3 engine arm must match token-for-token (greedy). Written
STRAIGHT from the verified architecture facts (transformers 5.15.1 configuration_gemma3.py +
modeling_gemma3.py and the shipped google/gemma-3-27b-it config.json), NOT from the engine:

  * every RMSNorm (four per layer + q/k per-head + final) computes in fp32 and applies Gemma's
    `(1.0 + weight)` gain convention;
  * input embeddings are scaled by sqrt(hidden_size); the tied lm_head is the RAW table;
  * per-head q/k RMSNorm BEFORE RoPE; attention scale = query_pre_attn_scalar ** -0.5;
  * dual RoPE: full-attention layers use theta_global with the config's linear factor dividing
    the inverse frequencies; sliding layers use theta_local unscaled; full head_dim rotated,
    split-half (rotate_half) pairing;
  * sliding layers attend only keys with (q_pos - k_pos) < sliding_window (plus causal);
  * MLP is GeGLU with gelu_pytorch_tanh; gemma2-style four-norm residual layout.

Pure greedy: argmax at every step, no penalties, no temperature -- the campaign oracle rule.

CLI:
  python3 ref_gemma3_torch.py --ckpt /tmp/g3syn --tokens 1,5,10 --max-new 8
  python3 ref_gemma3_torch.py --ckpt /tmp/g3syn --tokens 1,5,10 --max-new 8 --out tokens.json
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

try:
    import torch
except ImportError:  # pragma: no cover
    print("ref_gemma3_torch.py needs torch (pip install torch)", file=sys.stderr)
    raise


def _read_safetensors(path: Path) -> dict[str, Any]:
    """Dependency-free safetensors load: header parse + per-tensor BF16/F32 widening to fp32
    numpy, returned as {name: ndarray}."""
    import numpy as np

    with path.open("rb") as handle:
        (header_len,) = struct.unpack("<Q", handle.read(8))
        header = json.loads(handle.read(header_len))
        data_start = 8 + header_len
        out: dict[str, Any] = {}
        for name, info in header.items():
            if name == "__metadata__":
                continue
            start, end = info["data_offsets"]
            handle.seek(data_start + start)
            raw = handle.read(end - start)
            if info["dtype"] == "BF16":
                u16 = np.frombuffer(raw, dtype="<u2")
                values = (u16.astype(np.uint32) << 16).view(np.float32)
            elif info["dtype"] == "F32":
                values = np.frombuffer(raw, dtype="<f4")
            elif info["dtype"] == "F16":
                values = np.frombuffer(raw, dtype="<f2").astype(np.float32)
            else:
                raise ValueError(f"unsupported dtype {info['dtype']} for {name}")
            out[name] = values.astype(np.float64).reshape(info["shape"]).copy()
    return out


def _probe_prefix(tensors: dict[str, Any]) -> str:
    for prefix in ("language_model.", "model.language_model.", ""):
        if f"{prefix}model.embed_tokens.weight" in tensors:
            return prefix
    raise ValueError("no recognizable gemma3 text-tensor prefix in the safetensors")


class Gemma3Reference:
    """The whole text model as plain fp32 math, layer-by-layer in torch."""

    def __init__(self, checkpoint_dir: str | Path) -> None:
        import torch

        checkpoint_dir = Path(checkpoint_dir)
        config = json.loads((checkpoint_dir / "config.json").read_text(encoding="utf-8"))
        if config.get("model_type") == "gemma3":
            self.eos_ids = list(config.get("eos_token_id") or [1])
            config = config["text_config"]
        else:
            self.eos_ids = list(config.get("eos_token_id") or [1])
            if isinstance(self.eos_ids, int):
                self.eos_ids = [self.eos_ids]

        self.hidden = config["hidden_size"]
        self.n_layers = config["num_hidden_layers"]
        self.h_q = config["num_attention_heads"]
        self.h_kv = config["num_key_value_heads"]
        self.d_head = config["head_dim"]
        self.vocab = config["vocab_size"]
        self.eps = config.get("rms_norm_eps", 1e-6)
        self.sliding_window = config["sliding_window"]
        pattern = config.get("sliding_window_pattern", 6)
        explicit = config.get("layer_types")
        self.layer_types = list(explicit) if explicit else [
            "full_attention" if (i + 1) % pattern == 0 else "sliding_attention"
            for i in range(self.n_layers)
        ]
        self.scale = float(config.get("query_pre_attn_scalar", 256)) ** -0.5
        theta_global = config.get("rope_theta", 1_000_000.0)
        theta_local = config.get("rope_local_theta", 10_000.0)
        factor = 1.0
        rope_scaling = config.get("rope_scaling")
        if isinstance(rope_scaling, dict) and str(rope_scaling.get("rope_type", "")).lower() == "linear":
            factor = float(rope_scaling["factor"])
        # Inverse frequencies EXACTLY as transformers builds them per layer class:
        # global = 1 / (theta_global^(2i/d) * factor); local = 1 / theta_local^(2i/d).
        pairs = self.d_head // 2
        idx = 2.0 * torch.arange(pairs, dtype=torch.float64) / self.d_head
        self.inv_freq_global = 1.0 / ((theta_global ** idx) * factor)
        self.inv_freq_local = 1.0 / (theta_local ** idx)
        self.embed_scale = math.sqrt(self.hidden)

        tensors = _read_safetensors(checkpoint_dir / "model.safetensors")
        p = _probe_prefix(tensors)

        def t(name: str) -> Any:
            return torch.from_numpy(tensors[f"{p}{name}"]).to(torch.float64)

        self.embed = t("model.embed_tokens.weight")
        self.final_norm_w = t("model.norm.weight")
        lm_name = f"{p}lm_head.weight" if f"{p}lm_head.weight" in tensors else None
        self.lm_head = torch.from_numpy(tensors[lm_name]).to(torch.float64) if lm_name else self.embed
        self.layers: list[dict[str, Any]] = []
        for layer in range(self.n_layers):
            base = f"model.layers.{layer}."
            self.layers.append({
                "ln1": t(base + "input_layernorm.weight"),
                "ln2": t(base + "post_attention_layernorm.weight"),
                "ln3": t(base + "pre_feedforward_layernorm.weight"),
                "ln4": t(base + "post_feedforward_layernorm.weight"),
                "qn": t(base + "self_attn.q_norm.weight"),
                "kn": t(base + "self_attn.k_norm.weight"),
                "wq": t(base + "self_attn.q_proj.weight"),
                "wk": t(base + "self_attn.k_proj.weight"),
                "wv": t(base + "self_attn.v_proj.weight"),
                "wo": t(base + "self_attn.o_proj.weight"),
                "wg": t(base + "mlp.gate_proj.weight"),
                "wu": t(base + "mlp.up_proj.weight"),
                "wd": t(base + "mlp.down_proj.weight"),
            })

    @staticmethod
    def _norm(x: Any, w: Any, eps: float) -> Any:
        """Gemma3RMSNorm verbatim: fp32-style norm, gain = (1.0 + weight)."""
        variance = (x * x).mean(-1, keepdim=True)
        return x * torch.rsqrt(variance + eps) * (1.0 + w)

    def _rope(self, inv_freq: Any, positions: Any) -> tuple[Any, Any]:
        """cos/sin [L, d_head] with rotate_half (split-half) pairing: cat(freqs, freqs)."""

        freqs = positions[:, None].to(torch.float64) * inv_freq[None, :]  # [L, pairs]
        emb = torch.cat((freqs, freqs), dim=-1)
        return emb.cos(), emb.sin()

    @staticmethod
    def _rotate(x: Any, cos: Any, sin: Any) -> Any:
        """apply_rotary_pos_emb for one [L, heads, d_head] tensor: x*cos + rotate_half(x)*sin."""
        half = x.shape[-1] // 2
        x1, x2 = x[..., :half], x[..., half:]
        rotate_half = torch.cat((-x2, x1), dim=-1)
        return x * cos[:, None, :] + rotate_half * sin[:, None, :]

    def prefill_logits(self, token_ids: list[int]) -> Any:
        """One full prefill; returns the LAST position's logits [vocab] (fp64 = the fp32-oracle's
        accumulation-true values; an fp32 engine matches these within fp32 rounding)."""
        positions = torch.arange(len(token_ids), dtype=torch.float64)
        rope_global = self._rope(self.inv_freq_global, positions)
        rope_local = self._rope(self.inv_freq_local, positions)

        h = self.embed[token_ids] * self.embed_scale  # [L, hidden]
        L = h.shape[0]
        for layer, weights in zip(self.layer_types, self.layers):
            attn_in = self._norm(h, weights["ln1"], self.eps)
            q = (attn_in @ weights["wq"].T).view(L, self.h_q, self.d_head)
            k = (attn_in @ weights["wk"].T).view(L, self.h_kv, self.d_head)
            v = (attn_in @ weights["wv"].T).view(L, self.h_kv, self.d_head)
            q = self._norm(q, weights["qn"], self.eps)
            k = self._norm(k, weights["kn"], self.eps)
            cos, sin = rope_global if layer == "full_attention" else rope_local
            q = self._rotate(q, cos, sin)
            k = self._rotate(k, cos, sin)

            # GQA expand: [L, h_q, d_head]
            rep = self.h_q // self.h_kv
            k_full = k.repeat_interleave(rep, dim=1)
            v_full = v.repeat_interleave(rep, dim=1)
            scores = torch.einsum("lhd,mhd->hlm", q, k_full) * self.scale
            causal = positions[:, None] >= positions[None, :]
            if layer == "sliding_attention":
                window_ok = (positions[:, None] - positions[None, :]) < self.sliding_window
                mask = causal & window_ok
            else:
                mask = causal
            scores = scores.masked_fill(~mask[None, :, :], float("-inf"))
            probs = torch.softmax(scores, dim=-1)
            attn_out = torch.einsum("hlm,mhd->lhd", probs, v_full).reshape(L, -1)

            h = h + self._norm(attn_out @ weights["wo"].T, weights["ln2"], self.eps)
            mlp_in = self._norm(h, weights["ln3"], self.eps)
            gate = mlp_in @ weights["wg"].T
            up = mlp_in @ weights["wu"].T
            gelu = torch.nn.functional.gelu(gate.to(torch.float64), approximate="tanh")
            down = (gelu * up) @ weights["wd"].T
            h = h + self._norm(down, weights["ln4"], self.eps)

        h = self._norm(h, self.final_norm_w, self.eps)
        return h[-1] @ self.lm_head.T

    def generate(self, token_ids: list[int], max_new: int) -> list[int]:
        """Pure greedy: prefill once, then one forward per new token over the FULL growing
        sequence (no KV cache -- the simplest correct thing; the sequence is short)."""
        tokens = list(token_ids)
        for _ in range(max_new):
            logits = self.prefill_logits(tokens)
            next_token = int(torch.argmax(logits, dim=-1).item())
            tokens.append(next_token)
            if next_token in self.eos_ids:
                break
        return tokens


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--tokens", required=True, help="comma-separated prompt token ids; "
                        "multiple prompts separated by ';'")
    parser.add_argument("--max-new", type=int, default=8)
    parser.add_argument("--out", default=None, help="optional JSON output path")
    parser.add_argument(
        "--dump-logits", action="store_true",
        help="instead of generating: dump the FULL final logits vector of one prefill per "
             "prompt (the engine gate compares these logit-for-logit; random-weight synthetic "
             "models collapse to token attractors, so logits are the stronger identity proof)",
    )
    args = parser.parse_args()

    prompts = [
        [int(part) for part in group.split(",") if part.strip()]
        for group in args.tokens.split(";")
    ]
    reference = Gemma3Reference(args.ckpt)

    if args.dump_logits:
        dumps = []
        for prompt in prompts:
            logits = reference.prefill_logits(prompt)
            dumps.append({
                "prompt": prompt,
                "logits": [float(value) for value in logits],
                "argmax": int(logits.argmax(dim=-1).item()),
            })
        result = {"logit_dumps": dumps, "eos_ids": reference.eos_ids}
        text = json.dumps(result)
        print(text if not args.out else text[:200] + "...")
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        return

    results = []
    for prompt in prompts:
        tokens = reference.generate(prompt, args.max_new)
        results.append({
            "prompt": prompt,
            "all_token_ids": tokens,
            "generated": tokens[len(prompt):],
        })
    result = {"runs": results, "max_new": args.max_new, "eos_ids": reference.eos_ids}
    print(json.dumps(result))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
