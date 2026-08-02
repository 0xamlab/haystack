# llm_smoke — a real Qwen3 checkpoint through the real Mojo kernels

Smoke test / conformance probe for the Algenta Enterprise LLM Kernel Plane's phase-1 question: do
`attnk`/`normk`/`mlpk`/`gemm` (all merged, all frozen) reproduce a real, unmodified model's forward
pass when fed real weights? **Not** the full cross-framework Tensor ABI, **not** a PyTorch operator
pack, **not** a benchmark result — infrastructure validation for the plan at
`docs/mojo/new-kernel-package-rules.md`'s LLM-plane packages.

Checkpoint: `Qwen/Qwen3-0.6B-Base` (Apache-2.0, ungated) — the smallest real dense checkpoint in the
Qwen3 family, at 1/13th the scale of the plan's eventual Qwen3-8B-Base certification target.

## Pipeline

```bash
# 1. Download the checkpoint (~1.1 GiB, BF16 safetensors + tokenizer). Anywhere with room; /tmp is
#    fine for the weights themselves, just don't run python FROM /tmp (see repo CLAUDE.md).
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='Qwen/Qwen3-0.6B-Base', local_dir='/tmp/qwen3-0.6b-base',
                   allow_patterns=['*.json','*.safetensors','tokenizer*','vocab*','merges*'])
"

# 2. Loading glue (Python, explicitly permitted for parsing/orchestration — zero forward-pass
#    compute happens here): parse the safetensors header byte-for-byte, upcast BF16 -> Float64
#    (exact zero-extension), pre-transpose projection weights to the layout `sgemm_flat`'s fast path
#    wants, write manifest.json + weights.blob.
mkdir -p /tmp/qwen3smoke/mojo_dump
python3 benchmarks/llm_smoke/generate_manifest.py

# 3. The real forward pass, through the real kernels. Every matmul is gemm.blocked.sgemm_flat, every
#    RMSNorm (including Qwen3's QK-Norm) is normk.rmsnorm.rmsnorm_fwd_flat, every RoPE is
#    attnk.rope.rope_table/rope_apply_flat, every attention is attnk.sdpa.sdpa_forward_flat, every
#    gated-FFN activation is mlpk.activation.gated_ffn_fwd_flat, every embedding gather is
#    mlpk.embedding.embedding_fwd_flat. The one new kernel is llmk.residual.residual_add_flat.
cd mojo_env && pixi run mojo run -I../mojo/engine ../benchmarks/llm_smoke/qwen3_forward.mojo

# 4. Real reference, same checkpoint, same input, via `transformers` (CPU).
python3 benchmarks/llm_smoke/run_reference.py

# 5. Compare, stage by stage, with a stated tolerance -- not a bare pass/fail on the final token.
python3 benchmarks/llm_smoke/compare.py

# 5b. Precision-isolating sibling: same driver dump against a reference computed ENTIRELY in
#     float64, to separate "the float32-default reference's own precision floor" from "a Mojo bug".
python3 benchmarks/llm_smoke/run_reference_fp64.py
python3 benchmarks/llm_smoke/compare_fp64.py
```

## Result (2026-08-01, this machine)

Embedding output: bit-identical (max|delta| = 0). Every layer output, the final norm, and the
logits agree with the float32-default reference to within a few `1e-3` to `1e-4` absolute at
activation magnitudes in the hundreds to thousands (i.e. `~1e-6` relative) — **except** at token 0
(a documented "attention sink" position) and a handful of high-magnitude ("massive activation")
channels, where the divergence is larger in absolute terms but still small relative to the channel's
own magnitude. Argmax(logits) agrees at every one of the 5 positions. Final logits max|delta| =
2.0e-4 (float32 reference) / 2.4e-5 (float64 reference).

**Where the residual divergence comes from, diagnosed rather than hand-waved** (see
`compare_fp64.py`'s module docstring for the full trace): an independent from-scratch numpy
recompute of one layer, fed the reference's own real intermediate values, reproduces the exact same
discrepancy against PyTorch's own kernels — ruling out a Mojo-specific bug. Reading
`Qwen3RotaryEmbedding.forward`'s source shows it forces its cos/sin table through `float32` via
`.float()` regardless of the model's overall dtype (`with maybe_autocast(..., enabled=False):`),
while `attnk.rope.rope_table` computes the same table entirely in `Float64`. For that one
sub-computation the Mojo kernel is measurably MORE precise than even the float64 reference; the
residual gap is attributable to the reference's own forced-float32 RoPE table, amplified through
later layers by token-0's disproportionate attention weight — not a kernel defect.

First speed data point (prefill, 5 tokens, this machine, single-shot, **not** a finished benchmark):
the `transformers` reference (float32, forward-pass only, model already loaded) ran in
~210-250 ms (~20-24 tok/s). The Mojo driver's own kernel-compute time (excluding cold weight load
from `/tmp`, which varied 0.76-1.4 s across runs depending on OS page-cache warmth) was ~1.5-1.6 s
for the same 5 tokens (~3.1-3.3 tok/s) — the reference arm is roughly 6-7x faster on this single
tiny-batch measurement. Expected and not a finished claim: this driver reloads every weight from
disk per invocation (no resident model, no batching, no thread-pool reuse across the ~320 small
kernel calls a 28-layer/5-token forward pass makes), while `transformers` runs one already-loaded,
highly optimized (MKL/vectorized) CPU kernel per operation. A same-hardware-class LLM-serving
comparison needs a resident-model driver and a longer generation, which is future work, not this
smoke test's job.

## What is genuinely new here (vs. what was reused)

Two of three candidate gaps were closed by packages already merged in this plane, and calling them
(rather than writing a second copy) was correct — see `mojo/engine/llmk/__init__.mojo`:

- Embedding gather: `mlpk.embedding.embedding_fwd_flat` already existed.
- Half-split RoPE: `attnk.rope.rope_apply_flat(..., interleaved=False)` already existed and is
  exactly Qwen3/Llama's `rotate_half` convention.
- Elementwise residual-add-of-two-whole-buffers: genuinely absent (`transformer_blocks` and
  `fused_kernels` only had scalar, one-`Float64`-at-a-time versions). `llmk.residual.residual_add_flat`
  supplies it.

No existing kernel signature changed. No kernel was reimplemented in Python.
