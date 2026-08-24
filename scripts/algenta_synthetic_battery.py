#!/usr/bin/env python3
"""The fact-space synthetic battery: PROOF that any model whose facts land in
the declared capability table runs with zero per-model code.

The battery spans the cartesian product the capability table claims:

    head_dim  {64, 128}          qk_norm   {0, 1}
    window    {none, 1024}       rope      {plain, dual-theta, llama3-scaled}
    softcap   {none}             activation {silu, gelu-tanh}
    bias      {0, 1}             tie       {0, 1}
    GQA ratio {1, 2, 4}          (288 cells)

Every cell is judged twice, and the two judgments must agree:
  1. the DECLARED table (`algenta.model_capabilities.refusals_for_facts`) --
     the verdict the conform CLI publishes;
  2. the ACTUAL converter (`algenta.inference.prepare_model_checkpoint`) --
     which either converts the checkpoint or raises the typed refusal.
Cells the table claims supported then run end to end: convert -> Metal GPU
engine (the campaign worker binary) -> greedy tokens, compared
token-for-token against an INDEPENDENT Float64 torch reference written from
the HF math (not the engine's kernels, not the converter). Identity there is
the conformance proof; a typed refusal on an out-of-table cell is a correct
outcome and is recorded as the support boundary.

Subcommands:
    matrix      verdict pass only (no GPU): table verdict vs converter behavior
    run         engine pass on the supported cells (needs the Metal worker)
    all         matrix + run
    --out DIR   battery workspace (default /tmp/conform-battery)
    --worker P  gpu worker binary for `run` (default: the campaign build's
                mojo_build/gpu-worker/algenta-gpu-worker-mb-qwen3)
    --cells RE  regex filter on cell names (e.g. 'd64.*rope-llama3')

The checkpoint generator, the safetensors writer, and the reference decoder
are all in this file: one inspectable artifact, no hidden fixtures.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.model_capabilities import (  # noqa: E402
    extract_facts_from_config,
    refusals_for_facts,
    select_paths,
)

# ── the battery's fixed geometry ─────────────────────────────────────────────
# Small enough that 24 engine cells run in minutes; aligned to every kernel
# gate (hidden %32, d_ff %32, h_q*d_head %32, stage_needed <= 3072 tier).

HIDDEN_SIZE = 128
N_LAYERS = 2
H_Q = 4
D_FF = 256
VOCAB = 512
MAX_POSITION_EMBEDDINGS = 2048
ROPE_THETA = 10000.0
RMS_NORM_EPS = 1e-6
PROMPT_IDS = [61, 197, 312, 44, 287, 153, 9, 460, 112, 35, 475, 23]
MAX_NEW_TOKENS = 8
# Top-1 vs top-2 fp64 margin every generated step must hold. Sized for the
# engine's int8 weight quantization: per-row int8 + f32 scales put O(0.1-0.5)
# of noise on the logits relative to the exact fp64 reference, so a cell whose
# reference margins sit below this floor is testing the noise, not the math.
# (Untied cells need the headroom most: their lm_head rows are independent of
# the hidden state, so their logit gaps are intrinsically the smallest.)
MIN_LOGIT_GAP = 2.0

HEAD_DIMS = (64, 128)
QK_NORMS = (0, 1)
WINDOWS = (None, 1024)
ROPES = ("plain", "dual_theta", "llama3")
SOFTCAPS = (None,)
ACTIVATIONS = ("silu", "gelu_tanh")
BIASES = (0, 1)
TIES = (0, 1)
GQA_RATIOS = (1, 2, 4)


def cell_name(cell: dict) -> str:
    return (
        f"d{cell['head_dim']}-qkn{cell['qk_norm']}-win{cell['window'] or 'none'}-"
        f"rope{cell['rope']}-act{cell['activation']}-bias{cell['bias']}-"
        f"tie{cell['tie']}-gqa{cell['gqa']}"
    )


def all_cells() -> list[dict]:
    cells = []
    for head_dim, qk_norm, window, rope, softcap, act, bias, tie, gqa in itertools.product(
        HEAD_DIMS, QK_NORMS, WINDOWS, ROPES, SOFTCAPS, ACTIVATIONS, BIASES, TIES, GQA_RATIOS
    ):
        cells.append(
            {
                "head_dim": head_dim,
                "qk_norm": qk_norm,
                "window": window,
                "rope": rope,
                "softcap": softcap,
                "activation": act,
                "bias": bias,
                "tie": tie,
                "gqa": gqa,
            }
        )
    return cells


def cell_config(cell: dict) -> dict:
    """The HF-style config.json the cell declares."""
    config: dict = {
        "hidden_size": HIDDEN_SIZE,
        "num_hidden_layers": N_LAYERS,
        "num_attention_heads": H_Q,
        "num_key_value_heads": H_Q // cell["gqa"],
        "head_dim": cell["head_dim"],
        "intermediate_size": D_FF,
        "vocab_size": VOCAB,
        "max_position_embeddings": MAX_POSITION_EMBEDDINGS,
        "rope_theta": ROPE_THETA,
        "rms_norm_eps": RMS_NORM_EPS,
        "tie_word_embeddings": cell["tie"] == 1,
        "hidden_act": "silu" if cell["activation"] == "silu" else "gelu_pytorch_tanh",
    }
    if cell["window"] is not None:
        config["sliding_window"] = cell["window"]
    if cell["rope"] == "dual_theta":
        config["rope_local_base"] = 1000.0
    if cell["rope"] == "llama3":
        config["rope_scaling"] = {
            "rope_type": "llama3",
            "factor": 8.0,
            "original_max_position_embeddings": 512,
            "low_freq_factor": 1.0,
            "high_freq_factor": 4.0,
        }
    if cell["softcap"] is not None:
        config["attn_logit_softcapping"] = float(cell["softcap"])
    return config


# ── weights + safetensors (BF16, the converter's own dtype) ──────────────────


def _bf16_bytes(values: np.ndarray) -> bytes:
    """f64 -> f32 -> BF16 (top 16 bits of the f32), the exact bytes the
    converter's `_bf16_bytes_to_f64` widens back losslessly."""
    f32 = values.astype(np.float32)
    u32 = f32.view(np.uint32)
    return (u32 >> 16).astype(np.uint16).tobytes()


def _bf16_roundtrip(values: np.ndarray) -> np.ndarray:
    """The EXACT values the engine sees: widened back from the BF16 bytes this
    tensor writes. The reference decoder must run on THESE values, not the
    pre-rounding f64 -- otherwise reference and engine start from different
    weights and token flips measure the fixture mismatch, not the kernels
    (arbitrated 2026-08-23: transformers + engine agreed, the un-rounded
    reference was the outlier)."""
    f32 = values.astype(np.float32)
    u32 = f32.view(np.uint32)
    bf16 = (u32 >> 16).astype(np.uint16)
    return ((bf16.astype(np.uint32) << 16).view(np.float32)).astype(np.float64)


def generate_weights(cell: dict, seed: int) -> dict[str, np.ndarray]:
    """One cell's weight set as exact f64 arrays (the BF16 write + the
    reference both read these same values, so the comparison is exact-in,
    exact-out modulo the engine's own quantized compute)."""
    rng = np.random.default_rng(seed)
    d_head = cell["head_dim"]
    h_kv = H_Q // cell["gqa"]
    q_dim = H_Q * d_head
    kv_dim = h_kv * d_head

    def matrix(rows: int, cols: int) -> np.ndarray:
        return rng.normal(0.0, 0.5 / np.sqrt(cols), size=(rows, cols))

    def vector(n: int, scale: float = 1.0) -> np.ndarray:
        return np.full(n, scale) + rng.normal(0.0, 0.01, size=n)

    # The embedding/lm-head rows and the final-norm gains run LOUD on purpose:
    # a random small model's logits otherwise cluster into near-ties (top-2 gaps
    # ~1e-3), where the engine's int8 weight quantization could flip an argmax
    # without any math being wrong. Loud logit geometry (gaps O(1)) makes every
    # token comparison a real verdict. This is a fixture choice, not a model
    # claim: the kernels under test are the same either way.
    tensors: dict[str, np.ndarray] = {
        "model.embed_tokens.weight": rng.normal(0.0, 0.30, size=(VOCAB, HIDDEN_SIZE)),
        "model.norm.weight": vector(HIDDEN_SIZE, scale=2.5),
    }
    if cell["tie"] == 0:
        # Louder than the embedding on purpose: an untied lm_head is independent
        # of the hidden state's direction, so its logit gaps are intrinsically
        # the smallest; the extra scale lifts them clear of the quantization-noise
        # floor (see MIN_LOGIT_GAP).
        tensors["lm_head.weight"] = rng.normal(0.0, 0.90, size=(VOCAB, HIDDEN_SIZE))
    for layer in range(N_LAYERS):
        prefix = f"model.layers.{layer}."
        tensors[prefix + "input_layernorm.weight"] = vector(HIDDEN_SIZE)
        tensors[prefix + "post_attention_layernorm.weight"] = vector(HIDDEN_SIZE)
        tensors[prefix + "self_attn.q_proj.weight"] = matrix(q_dim, HIDDEN_SIZE)
        tensors[prefix + "self_attn.k_proj.weight"] = matrix(kv_dim, HIDDEN_SIZE)
        tensors[prefix + "self_attn.v_proj.weight"] = matrix(kv_dim, HIDDEN_SIZE)
        tensors[prefix + "self_attn.o_proj.weight"] = matrix(HIDDEN_SIZE, q_dim)
        tensors[prefix + "mlp.gate_proj.weight"] = matrix(D_FF, HIDDEN_SIZE)
        tensors[prefix + "mlp.up_proj.weight"] = matrix(D_FF, HIDDEN_SIZE)
        tensors[prefix + "mlp.down_proj.weight"] = matrix(HIDDEN_SIZE, D_FF)
        if cell["qk_norm"] == 1:
            tensors[prefix + "self_attn.q_norm.weight"] = vector(d_head)
            tensors[prefix + "self_attn.k_norm.weight"] = vector(d_head)
        if cell["bias"] == 1:
            tensors[prefix + "self_attn.q_proj.bias"] = rng.normal(0.0, 0.02, size=q_dim)
            tensors[prefix + "self_attn.k_proj.bias"] = rng.normal(0.0, 0.02, size=kv_dim)
            tensors[prefix + "self_attn.v_proj.bias"] = rng.normal(0.0, 0.02, size=kv_dim)
    # Every tensor lands in the checkpoint as BF16, so every tensor the
    # reference reads is the BF16-roundtripped value -- identical inputs to
    # the engine's converter-widened stream.
    return {name: _bf16_roundtrip(values) for name, values in tensors.items()}


def write_safetensors(path: Path, tensors: dict[str, np.ndarray]) -> None:
    """A single-shard safetensors file, BF16, in the exact container format the
    converter's byte-level reader parses."""
    header: dict = {"__metadata__": {"format": "pt"}}
    chunks: list[bytes] = []
    cursor = 0
    for name in sorted(tensors):
        raw = _bf16_bytes(tensors[name])
        header[name] = {
            "dtype": "BF16",
            "shape": list(tensors[name].shape),
            "data_offsets": [cursor, cursor + len(raw)],
        }
        chunks.append(raw)
        cursor += len(raw)
    header_bytes = json.dumps(header).encode("utf-8")
    with path.open("wb") as handle:
        handle.write(len(header_bytes).to_bytes(8, "little"))
        handle.write(header_bytes)
        for chunk in chunks:
            handle.write(chunk)


# ── the independent Float64 reference decoder ────────────────────────────────


def _llama3_inv_freqs(head_dim: int, theta: float, scaling: dict) -> np.ndarray:
    """HF transformers' exact llama3 scheme (_compute_llama3_inv_freq)."""
    inv_freq = 1.0 / (theta ** (np.arange(0, head_dim, 2, dtype=np.float64) / head_dim))
    factor = float(scaling["factor"])
    orig = float(scaling["original_max_position_embeddings"])
    low = float(scaling.get("low_freq_factor", 1.0))
    high = float(scaling.get("high_freq_factor", 4.0))
    low_wavelen = orig / low
    high_wavelen = orig / high
    out = np.empty_like(inv_freq)
    for i, freq in enumerate(inv_freq):
        wavelen = 2.0 * np.pi / freq
        if wavelen < high_wavelen:
            out[i] = freq
        elif wavelen > low_wavelen:
            out[i] = freq / factor
        else:
            smooth = (orig / wavelen - low) / (high - low)
            out[i] = (1.0 - smooth) * freq / factor + smooth * freq
    return out


def reference_generate(cell: dict, tensors: dict[str, np.ndarray]) -> tuple[list[int], float]:
    """Greedy tokens from the HF math, end to end in Float64. Returns the
    generated ids and the smallest top-1-vs-top-2 logit gap seen (the margin
    gate)."""
    import torch

    torch.manual_seed(0)
    d_head = cell["head_dim"]
    h_kv = H_Q // cell["gqa"]

    def T(name: str) -> torch.Tensor:
        return torch.from_numpy(np.ascontiguousarray(tensors[name])).to(torch.float64)

    def rms_norm(x: torch.Tensor, w: torch.Tensor) -> torch.Tensor:
        variance = x.pow(2).mean(-1, keepdim=True)
        return x * torch.rsqrt(variance + RMS_NORM_EPS) * w

    if cell["rope"] == "llama3":
        config = cell_config(cell)
        inv_freq = _llama3_inv_freqs(d_head, ROPE_THETA, config["rope_scaling"])
    else:
        inv_freq = 1.0 / (ROPE_THETA ** (np.arange(0, d_head, 2, dtype=np.float64) / d_head))
    inv_freq_t = torch.from_numpy(inv_freq)

    def rope(x: torch.Tensor, position: int) -> torch.Tensor:
        # x: [n_heads, d_head]; rotate_pair on (i, i+d_head/2) pairs.
        freqs = inv_freq_t * float(position)
        cos = freqs.cos().repeat(2)  # [d_head]
        sin = freqs.sin().repeat(2)
        half = d_head // 2
        x1 = x[..., :half]
        x2 = x[..., half:]
        rotated = torch.cat((-x2, x1), dim=-1)
        return x * cos + rotated * sin

    def step(input_ids: list[int], kv_cache: list) -> torch.Tensor:
        x = T("model.embed_tokens.weight")[torch.tensor(input_ids)]  # [n, H]
        # Positions already cached = the k-cache's sequence length (kv_cache[0]
        # is the layer-0 (k, v) PAIR -- len() of the pair is always 2, so the
        # position count is the tensor's own first dim).
        pos0 = kv_cache[0][0].shape[0] if kv_cache else 0
        for layer in range(N_LAYERS):
            prefix = f"model.layers.{layer}."
            hidden = rms_norm(x, T(prefix + "input_layernorm.weight"))
            q = hidden @ T(prefix + "self_attn.q_proj.weight").T
            k = hidden @ T(prefix + "self_attn.k_proj.weight").T
            v = hidden @ T(prefix + "self_attn.v_proj.weight").T
            if cell["bias"] == 1:
                q = q + T(prefix + "self_attn.q_proj.bias")
                k = k + T(prefix + "self_attn.k_proj.bias")
                v = v + T(prefix + "self_attn.v_proj.bias")
            n = q.shape[0]
            q = q.view(n, H_Q, d_head)
            k = k.view(n, h_kv, d_head)
            v = v.view(n, h_kv, d_head)
            if cell["qk_norm"] == 1:
                q = rms_norm(q, T(prefix + "self_attn.q_norm.weight"))
                k = rms_norm(k, T(prefix + "self_attn.k_norm.weight"))
            for p in range(n):
                for h in range(H_Q):
                    q[p, h] = rope(q[p, h], pos0 + p)
                for h in range(h_kv):
                    k[p, h] = rope(k[p, h], pos0 + p)
            k_cache, v_cache = kv_cache[layer]
            k_all = torch.cat([k_cache, k], dim=0)  # [L, h_kv, d]
            v_all = torch.cat([v_cache, v], dim=0)
            kv_cache[layer] = (k_all, v_all)
            seq_len = k_all.shape[0]
            rep = H_Q // h_kv
            k_full = k_all.repeat_interleave(rep, dim=1)  # [L, H_Q, d]
            v_full = v_all.repeat_interleave(rep, dim=1)
            scale = 1.0 / np.sqrt(d_head)
            scores = torch.einsum("nhd,shd->nhs", q, k_full) * scale
            causal = torch.triu(
                torch.ones(n, seq_len, dtype=torch.bool), diagonal=seq_len - n + 1
            )
            scores = scores.masked_fill(causal[:, None, :], float("-inf"))
            attn = scores.softmax(dim=-1)
            out = torch.einsum("nhs,shd->nhd", attn, v_full)
            out = out.reshape(n, H_Q * d_head)
            x = x + out @ T(prefix + "self_attn.o_proj.weight").T
            ffn_hidden = rms_norm(x, T(prefix + "post_attention_layernorm.weight"))
            gate = ffn_hidden @ T(prefix + "mlp.gate_proj.weight").T
            up = ffn_hidden @ T(prefix + "mlp.up_proj.weight").T
            act = torch.nn.functional.silu(gate) * up
            x = x + act @ T(prefix + "mlp.down_proj.weight").T
        x = rms_norm(x, T("model.norm.weight"))
        lm_head = (
            T("model.embed_tokens.weight") if cell["tie"] == 1 else T("lm_head.weight")
        )
        return x @ lm_head.T  # [n, VOCAB]

    kv_cache = [(torch.zeros(0, h_kv, d_head, dtype=torch.float64),
                 torch.zeros(0, h_kv, d_head, dtype=torch.float64)) for _ in range(N_LAYERS)]
    ids = list(PROMPT_IDS)
    logits = step(ids, kv_cache)
    generated: list[int] = []
    min_gap = float("inf")
    for _ in range(MAX_NEW_TOKENS):
        last = logits[-1]
        top2 = last.topk(2).values
        min_gap = min(min_gap, float(top2[0] - top2[1]))
        next_id = int(last.argmax().item())
        generated.append(next_id)
        logits = step([next_id], kv_cache)
    return generated, min_gap


# ── the battery passes ────────────────────────────────────────────────────────


def table_verdict(cell: dict) -> tuple[str, list[str]]:
    """The declared table's own verdict for the cell's facts (probed facts set
    from the cell: the battery KNOWS the weights it generates)."""
    facts = extract_facts_from_config(cell_config(cell))
    from dataclasses import replace as _replace

    facts = _replace(
        facts,
        has_qk_norm=cell["qk_norm"],
        attention_bias=cell["bias"],
        probed=True,
    )
    refusals = refusals_for_facts(facts, backend="metal")
    if refusals:
        return "refused", [f"{r.fact}={r.value!r}" for r in refusals]
    return "supported", [select_paths(facts).plan]


def _config_stage_refused(cell: dict) -> bool:
    """Whether the converter refuses this cell at the CONFIG stage (facts the
    config declaration alone settles -- `_validate_architecture`'s own gate,
    which judges the config-derived facts with the probe facts still unknown)."""
    from dataclasses import replace as _replace

    facts = extract_facts_from_config(cell_config(cell))
    facts = _replace(facts, probed=True)  # probe facts None -> judged later, not here
    return bool(refusals_for_facts(facts, backend="metal", probed=True))


def run_matrix(cells: list[dict], out_dir: Path) -> dict:
    """Verdict pass: the table's verdict vs the converter's ACTUAL behavior.
    Supported cells convert; refused cells raise the typed refusal. Any
    disagreement is a battery failure of the table or the converter."""
    from algenta.inference import InferenceError, prepare_model_checkpoint

    report: dict[str, dict] = {}
    for cell in cells:
        name = cell_name(cell)
        cell_dir = out_dir / "cells" / name
        cell_dir.mkdir(parents=True, exist_ok=True)
        (cell_dir / "config.json").write_text(json.dumps(cell_config(cell)), encoding="utf-8")
        expected, detail = table_verdict(cell)

        # Weights are generated whenever the config stage passes, so probe-stage
        # gates (attention_bias on metal, the unsupported-tensor sweep) are
        # exercised against real tensors. Config-stage refusals never read them.
        # Supported cells get a SEED SEARCH: the first seed whose fp64 reference
        # run holds the top-2 logit margin at every generated step, so a token
        # difference against the (int8-quantized) engine is a real finding,
        # never a near-tie artifact. Deterministic: same cell, same seed, every
        # battery run.
        if not _config_stage_refused(cell):
            seed = _cell_seed(cell)
            if expected == "supported":
                found = None
                for candidate in range(400):
                    tensors = generate_weights(cell, seed=candidate)
                    ref_tokens, gap = reference_generate(cell, tensors)
                    if gap >= MIN_LOGIT_GAP:
                        found = (candidate, tensors, ref_tokens, gap)
                        break
                if found is None:
                    raise SystemExit(
                        f"battery cell {name}: no seed in 0..399 holds the {MIN_LOGIT_GAP} "
                        "logit margin -- widen the search before trusting this cell"
                    )
                seed, tensors, ref_tokens, gap = found
            else:
                tensors = generate_weights(cell, seed=seed)
            write_safetensors(cell_dir / "model.safetensors", tensors)

        actual = "unknown"
        actual_detail = ""
        try:
            converted = prepare_model_checkpoint(cell_dir, PROMPT_IDS, out_dir=cell_dir / "converted")
            actual = "supported"
            manifest = json.loads((converted / "manifest.json").read_text(encoding="utf-8"))
            actual_detail = f"converted {len(manifest['tensors'])} tensors"
        except InferenceError as exc:
            actual = "refused"
            actual_detail = str(exc)

        match = expected == actual
        entry = {
            "facts": cell,
            "expected": expected,
            "expected_detail": detail,
            "actual": actual,
            "actual_detail": actual_detail,
            "match": match,
        }
        if not _config_stage_refused(cell):
            entry["seed"] = seed
            if expected == "supported":
                entry["reference_tokens"] = ref_tokens
                entry["min_logit_gap"] = gap
        report[name] = entry
        if not match:
            print(f"  MISMATCH {name}: table={expected} converter={actual}: {actual_detail}")
    return report


def _cell_seed(cell: dict) -> int:
    """Deterministic per-cell seed: the same cell always generates the same
    weights, battery run to battery run, interpreter to interpreter (crc32 --
    the builtin `hash` is salted per process)."""
    import zlib

    return zlib.crc32(cell_name(cell).encode("utf-8"))


def run_engine(cells: list[dict], out_dir: Path, worker: Path, report: dict) -> dict:
    """Engine pass: every cell the table claims supported runs the Metal GPU
    path and must match the independent fp64 reference token for token. The
    seed + reference tokens come from the matrix pass (the seed search), so
    the weights on disk, the reference, and the engine all agree on the SAME
    generated checkpoint."""
    import os

    supported = [cell for cell in cells if report[cell_name(cell)]["expected"] == "supported"]
    if not supported:
        return report
    if not worker.is_file():
        print(f"error: worker binary not found: {worker}", file=sys.stderr)
        return report

    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(worker)
    from algenta import MojoRuntime
    from algenta.inference import decode

    runtime = MojoRuntime(mode="local", timeout=600.0)
    for cell in supported:
        name = cell_name(cell)
        cell_dir = out_dir / "cells" / name
        entry = report[name]
        ref_tokens = entry.get("reference_tokens")
        if ref_tokens is None:
            entry["engine_match"] = False
            entry["engine_detail"] = "no reference tokens (run the matrix pass first)"
            print(f"  ENGINE-SKIP {name}: {entry['engine_detail']}")
            continue
        start = time.time()
        try:
            result = decode(
                runtime,
                checkpoint_dir=str(cell_dir),
                prompt_token_ids=PROMPT_IDS,
                max_new_tokens=MAX_NEW_TOKENS,
                converted_checkpoint_dir=str(cell_dir / "converted"),
            )
            engine_tokens = list(result.token_ids[result.n_prompt :])
            entry["engine_tokens"] = engine_tokens
            entry["engine_wall_sec"] = round(time.time() - start, 2)
            entry["engine_match"] = engine_tokens == ref_tokens
            if not entry["engine_match"]:
                print(f"  ENGINE-DIFF {name}: ref={ref_tokens} engine={engine_tokens}")
        except Exception as exc:  # noqa: BLE001 -- the battery records, never dies mid-run
            entry["engine_tokens"] = None
            entry["engine_match"] = False
            entry["engine_detail"] = f"{type(exc).__name__}: {exc}"
            print(f"  ENGINE-FAIL {name}: {entry['engine_detail']}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The algenta fact-space synthetic battery.")
    parser.add_argument("command", choices=("matrix", "run", "all"))
    parser.add_argument("--out", default="/tmp/conform-battery")
    parser.add_argument(
        "--worker",
        default=str(ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker-mb-qwen3"),
    )
    parser.add_argument("--cells", help="regex filter on cell names")
    parser.add_argument("--report", help="report JSON path (default <out>/battery_report.json)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = all_cells()
    if args.cells:
        pattern = re.compile(args.cells)
        cells = [cell for cell in cells if pattern.search(cell_name(cell))]
    print(f"battery: {len(cells)} cells "
          f"({sum(1 for c in cells if table_verdict(c)[0] == 'supported')} claimed supported)")

    report: dict = {}
    if args.command in ("matrix", "all"):
        print("── verdict pass: declared table vs converter behavior ──")
        report = run_matrix(cells, out_dir)
        agreed = sum(1 for entry in report.values() if entry["expected"] == entry["actual"])
        print(f"verdict pass: {agreed}/{len(report)} cells agree with the declared table")
    if args.command in ("run", "all"):
        if args.command == "run" and not report:
            # A bare `run` still needs the matrix pass: it generates the
            # checkpoints (with the seed-searched weights), converts them, and
            # computes the fp64 references the engine results are compared to.
            report = run_matrix(cells, out_dir)
        print(f"── engine pass: Metal GPU vs fp64 reference (worker: {args.worker}) ──")
        report = run_engine(cells, out_dir, Path(args.worker), report)
        ran = [e for e in report.values() if "engine_tokens" in e]
        matched = [e for e in ran if e.get("engine_match")]
        print(f"engine pass: {len(matched)}/{len(ran)} supported cells token-identical to fp64")

    report_path = Path(args.report) if args.report else out_dir / "battery_report.json"
    summary = {
        "cells_total": len(cells),
        "supported_claimed": sum(1 for e in report.values() if e["expected"] == "supported"),
        "refused_claimed": sum(1 for e in report.values() if e["expected"] == "refused"),
        "verdict_agreement": sum(1 for e in report.values() if e["expected"] == e.get("actual")),
        "engine_token_identical": sum(1 for e in report.values() if e.get("engine_match")),
        "cells": report,
    }
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"report: {report_path}")

    if summary["supported_claimed"] and summary["verdict_agreement"] != len(cells):
        return 2
    if args.command in ("run", "all") and summary["engine_token_identical"] != summary["supported_claimed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
