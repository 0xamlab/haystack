"""dump_transformers_cpu.py — the transformers fp32 CPU twin of the engine's ALGENTA_7B_DUMP
hook: runs ONE forward pass of Qwen2.5-7B-Instruct on ONE prompts.json prompt (fp32, CPU) and
prints the SAME per-stage checksum rows the `-D ALGENTA_7B_DUMP` engine build prints —

    DUMP{TF,7B}|<layer>|<stage>|<n>|<f64 sum>|<f64 max|x|>|<v0>|<v1>

stages: embed / xn1 / qkv / qrot / attn / post_attn / xn2 / act / post_mlp (the LAST prompt
row only), then final_norm + top-5 logits + token-0 argmax. Diffing the two dumps bisects the
7B-lane forward pass to the first diverging layer/op.

Everything except two DERIVED intermediates comes straight out of transformers' own forward
(via module hooks): `qrot` (the model's rope math applied to the hooked q_proj output, the
split-half/rotate_half convention Qwen2.5 defines — identical to apply_rotary_pos_emb) and
`act` (silu(hooked gate_proj) * hooked up_proj, the SwiGLU the mlp runs). Both are computed
from tensors transformers itself produced, so the reference never re-derives a projection.

Usage (on the VM):
    python3 dump_transformers_cpu.py --model-dir ~/models/Qwen2.5-7B-Instruct \
        --ckpt /tmp/w7b/ckpt --prompt chat_1 --out /tmp/w7b/gate/dump_tf.txt
"""

import argparse
import json
from pathlib import Path


def _checksum(tag: str, layer: int, stage: str, row: "torch.Tensor", lines: list):
    """row: 1-D float tensor; append the shared-format checksum line (f64 arithmetic)."""
    import torch

    r = row.detach().to(torch.float64)
    s = float(r.sum())
    mx = float(r.abs().max())
    lines.append(
        f"{tag}|{layer}|{stage}|{r.numel()}|{s!r}|{mx!r}|{float(r[0])!r}|{float(r[1])!r}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ckpt", default="/tmp/w7b/ckpt")
    ap.add_argument("--prompt", default="chat_1",
                    help="'fixture' or 'chat_<i>' (index into prompts.json chat_prompts)")
    ap.add_argument("--out", default="/tmp/w7b/gate/dump_tf.txt")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM

    prompts = json.loads((Path(args.ckpt) / "prompts.json").read_text())
    if args.prompt == "fixture":
        ids = prompts["fixture"]["ids"]
    else:
        idx = int(args.prompt.split("_")[1])
        ids = prompts["chat_prompts"][idx]["ids"]
    n_pos = len(ids)
    print(f"[dump_tf] prompt={args.prompt} n_tokens={n_pos}", flush=True)

    model = AutoModelForCausalLM.from_pretrained(args.model_dir, torch_dtype=torch.float32)
    model = model.to("cpu").eval()
    base = model.model  # Qwen2Model

    h_in = {}       # layer idx -> residual INTO the layer
    xn1 = {}        # layer idx -> input_layernorm output
    q_out, k_out, v_out = {}, {}, {}
    cos_sin = {}    # rotary_emb output (cos, sin)
    attn_pre_o = {}  # layer idx -> o_proj INPUT (attention output, pre o_proj)
    attn_post_o = {} # layer idx -> self_attn OUTPUT[0] (post o_proj)
    xn2 = {}        # layer idx -> post_attention_layernorm output
    g_out, u_out = {}, {}
    layer_out = {}  # layer idx -> layer OUTPUT[0] (post mlp residual)
    embed_out = {}

    handles = []

    def _save(store, key):
        """Hook bodies must return None — a non-None return from a forward_hook REPLACES the
        module's output (first version of this script returned setdefault's value and broke
        the decoder layer's `hidden_states, _ = self.self_attn(...)` unpack)."""
        def _hook(m, inp, out):
            store.setdefault(key, out.detach().clone())
            return None
        return _hook

    def _save_tuple01(store, key):
        def _hook(m, inp, out):
            store.setdefault(key, (out[0].detach().clone(), out[1].detach().clone()))
            return None
        return _hook

    def _save_out0(store, key):
        def _hook(m, inp, out):
            # transformers 5.x decoder layers return a BARE tensor unless attention weights
            # were requested; self_attn still returns (output, weights). Handle both shapes.
            t = out[0] if isinstance(out, (tuple, list)) else out
            store.setdefault(key, t.detach().clone())
            return None
        return _hook

    def _save_pre(store, key):
        def _hook(m, inp):
            store.setdefault(key, inp[0].detach().clone())
            return None
        return _hook

    handles.append(base.embed_tokens.register_forward_hook(_save(embed_out, 0)))
    handles.append(base.rotary_emb.register_forward_hook(_save_tuple01(cos_sin, 0)))
    for i, layer in enumerate(base.layers):
        handles.append(layer.register_forward_pre_hook(_save_pre(h_in, i)))
        handles.append(layer.input_layernorm.register_forward_hook(_save(xn1, i)))
        handles.append(layer.self_attn.q_proj.register_forward_hook(_save(q_out, i)))
        handles.append(layer.self_attn.k_proj.register_forward_hook(_save(k_out, i)))
        handles.append(layer.self_attn.v_proj.register_forward_hook(_save(v_out, i)))
        handles.append(layer.self_attn.o_proj.register_forward_pre_hook(_save_pre(attn_pre_o, i)))
        handles.append(layer.self_attn.register_forward_hook(_save_out0(attn_post_o, i)))
        handles.append(layer.post_attention_layernorm.register_forward_hook(_save(xn2, i)))
        handles.append(layer.mlp.gate_proj.register_forward_hook(_save(g_out, i)))
        handles.append(layer.mlp.up_proj.register_forward_hook(_save(u_out, i)))
        handles.append(layer.register_forward_hook(_save_out0(layer_out, i)))

    inp = torch.tensor([ids], dtype=torch.long)
    with torch.no_grad():
        res = base(input_ids=inp)
    final_normed = res.last_hidden_state  # Qwen2Model applies the final norm itself
    for h in handles:
        h.remove()

    n_layers = len(base.layers)
    h_q = model.config.num_attention_heads
    h_kv = model.config.num_key_value_heads
    # transformers 5.x does not surface `head_dim` as a Qwen2Config attribute; derive it.
    d_head = getattr(model.config, "head_dim", None)
    if d_head is None:
        d_head = model.config.hidden_size // h_q
    lines = []

    # ── embed (the final prompt row) ──
    _checksum("DUMPTF", -1, "embed", embed_out[0][0, n_pos - 1], lines)

    cos, sin = cos_sin[0]  # [1, S, d_head] each (transformers 5.x rope convention)

    for i in range(n_layers):
        _checksum("DUMPTF", i, "xn1", xn1[i][0, n_pos - 1], lines)

        # qkv row, the engine's [Q | K | V] head-major concat
        qkv_row = torch.cat(
            [q_out[i][0, n_pos - 1], k_out[i][0, n_pos - 1], v_out[i][0, n_pos - 1]], dim=0
        )
        _checksum("DUMPTF", i, "qkv", qkv_row, lines)

        # qrot: the model's OWN rope math on the hooked q — apply_rotary_pos_emb's exact form
        # (q * cos + rotate_half(q) * sin, split-half pairing), cos/sin taken from the hooked
        # rotary_emb output (cat(freqs, freqs) with attention_scaling=1.0 for Qwen2.5).
        q = q_out[i][0, n_pos - 1].view(h_q, d_head).to(torch.float64)
        c = cos[0, n_pos - 1].to(torch.float64)      # [d_head], repeated pair halves
        s = sin[0, n_pos - 1].to(torch.float64)      # [d_head]
        half = d_head // 2
        q1, q2 = q[:, :half], q[:, half:]
        o1 = q1 * c[:half] - q2 * s[:half]
        o2 = q2 * c[half:] + q1 * s[half:]
        qrot_row = torch.cat([o1, o2], dim=1).reshape(h_q * d_head).to(torch.float32)
        _checksum("DUMPTF", i, "qrot", qrot_row, lines)

        _checksum("DUMPTF", i, "attn", attn_pre_o[i][0, n_pos - 1], lines)

        # post_attn = residual in + attn-out-after-o_proj (the layer's own residual add)
        post_attn = h_in[i][0, n_pos - 1] + attn_post_o[i][0, n_pos - 1]
        _checksum("DUMPTF", i, "post_attn", post_attn, lines)

        _checksum("DUMPTF", i, "xn2", xn2[i][0, n_pos - 1], lines)

        # act = SwiGLU: silu(gate) * up, on the hooked projections
        act_row = torch.nn.functional.silu(g_out[i][0, n_pos - 1]) * u_out[i][0, n_pos - 1]
        _checksum("DUMPTF", i, "act", act_row, lines)

        _checksum("DUMPTF", i, "post_mlp", layer_out[i][0, n_pos - 1], lines)

    # ── final norm + logits + token 0 ──
    _checksum("DUMPTF", -2, "final_norm", final_normed[0, n_pos - 1], lines)
    h_final = final_normed[0, n_pos - 1].to(torch.float64)
    lm = model.lm_head.weight.detach().to(torch.float64)  # [vocab, d_model]
    logits = lm @ h_final
    top5 = torch.topk(logits, 5)
    top5_str = ",".join(f"{int(idx)}:{float(val):.6f}"
                        for val, idx in zip(top5.values, top5.indices))
    lines.append(f"DUMPTF|-2|logits_top|5|{top5_str}")
    token0 = int(logits.argmax())
    lines.append(f"DUMPTF|-2|token0|1|{token0}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"[dump_tf] wrote {len(lines)} checksum lines to {out_path}")
    print(f"[dump_tf] token0 (fp32 greedy) = {token0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
