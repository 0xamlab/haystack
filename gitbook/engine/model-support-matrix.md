---
icon: table-cells
description: Model support as declared fact ranges — the capability table, the conform CLI, conformance-proven models, and the typed-refusal boundary.
---

# Model support matrix

Model support is a table of **architecture facts**, not a list of model names. A checkpoint runs
when its facts land inside the declared ranges below — any checkpoint, from any source, with no
per-model code. A checkpoint whose facts fall outside is refused with the exact fact, its value,
and the supported range — never silently approximated, never judged by its name.

## How support is decided

1. The checkpoint's own `config.json` is normalized into a fact manifest (implicit fields derived:
   `head_dim` defaults to `hidden_size / num_attention_heads` when a config omits it; an explicit
   `head_dim` is always trusted).
2. Structural facts are checked against the table (shapes, GQA ratio, alignment, rope class,
   activation, window/softcap absence).
3. Weight-level facts are probed from the tensors — tensors are the truth: QK-norm and q/k/v bias
   presence are read from the safetensors headers, never from config keys that may lie or omit.
4. Backend facts are applied: each hardware family wires a different kernel set, so the same model
   facts can be supported on one backend and refused on another.

## Decoder families

The capability table has one profile per decoder **family** — a fact of the file's own
`model_type`, never a brand lookup. The same fact fields are judged against each profile's
declared ranges, so a feature that is a refusal in one family is a supported branch in another:

| Family | Kernel set | Window attention | Rope | Activation | Backend |
| --- | --- | --- | --- | --- | --- |
| `qwen3_llama` | the resident Metal/CUDA paths below | none (a declared window is refused) | plain or llama-3.1 `llama3`, one theta | `silu` | Metal + CUDA |
| `gemma3` | the Gemma 3 CUDA lane (f32/f16) | sliding window + local/global layer pattern | global + local theta (dual-theta), linear global scaling | `gelu_pytorch_tanh` | CUDA |

Within each profile, softcaps, q/k/v projection biases beyond the profile's range, and any
activation outside the profile are refused — never silently adapted.

## Structural fact requirements

The shape gates apply to every family; the activation / rope / window ranges below are the
`qwen3_llama` profile's (the `gemma3` profile's differing ranges are tabled above).

| Fact | Supported range |
| --- | --- |
| `hidden_size` | positive, divisible by 32 (GEMM tile alignment) |
| `intermediate_size` | positive, divisible by 32 |
| `num_attention_heads` | positive, an exact multiple of `num_key_value_heads` (integral GQA ratio) |
| `head_dim` | one of **{32, 64, 128, 256}** — a multiple of 32, a power of two, ≤ 256 |
| `num_attention_heads × head_dim` | divisible by 32 |
| `num_hidden_layers` | 1–128 |
| `vocab_size` | 1–2,097,152 |
| FFN activation | `silu` (the fused SwiGLU FFN is the only FFN implemented) |
| Rope | plain (`rope_theta` only) or the llama-3.1 `llama3` scaling scheme |
| Attention scale | `1/sqrt(head_dim)` (a differing `query_pre_attn_scalar` is refused) |
| Sliding window | none — a declared window is refused, never ignored |
| Attention-logit softcap | none — refused, never ignored |
| Final-logit softcap | none — refused, never ignored |
| Per-layer layer types | none — one uniform decoder stack |
| Rotary coverage | full head dimension (a `partial_rotary_factor` < 1 is refused) |
| Rope bases | one — a second base (dual-theta local/global rope) is refused |
| Embedding/LM-head | tied or untied — both conventions are branches, not refusals |
| Stop token | the checkpoint's own `eos_token_id`; absent means "generate exactly `max_new_tokens`" |

## Kernel path capabilities

Where a kernel path genuinely supports only certain fact values, that is declared data, and path
selection is a lookup from the facts (closest-capability-first, degrading, never a hard error):

| Path | head_dim | qk_norm | Notes |
| --- | --- | --- | --- |
| Steel grouped-FA prefill (d128) | {128} | {0, 1} | norm-agnostic; the QK-norm lives in the KV producer |
| Steel grouped-FA prefill (d64) | {64} | {0} | validated pairing is no-QK-norm |
| Parametric prefill | {32, 64, 128, 256} | {0, 1} | power-of-two d_head ≤ 256 |
| Split-K decode partial (f4u2) | {128} | {0, 1} | d_head/4 threads |
| Split-K decode partial (f2s4k, KV-producer-fused) | {64} | {0} | preferred d64 partial when linked |
| Split-K decode partial (f2s4 / f2) | {64} | {0, 1} | norm-agnostic fallbacks |
| Batched decode partial | {128} any qk_norm; {64} qk_norm=0 | as listed | B ≤ 32 sequences |
| KV producer | any | {0, 1} | carries the model's own qk_norm flag |
| Int8-KV mirror decode | {128} | {0, 1} | d128 only |
| GEMM tiers (original / BM64 / vecload4 / MSL parity) | any | any | alignment-gated only, per-role fallback |

## Backend fact ranges

| Backend | q/k/v projection biases | Staging tiers (elements) |
| --- | --- | --- |
| Metal (Apple Silicon) | **0 only** — biases are not applied by the Metal descriptor tables; a bias-carrying checkpoint is refused, never run with them dropped | 3072, 6144 — one build per tier |
| CUDA (NVIDIA) | 0 and 1 — applied in all five 7B-lane paths | 3072, 6144, 8192, 18944 |

Staging is the decode kernels' shared-memory ceiling, derived from the model's own dims:
`stage_needed = max(hidden_size, num_attention_heads × head_dim, intermediate_size)`. A model
whose staged vectors exceed every tier of a backend is refused naming the value and the tiers —
and can be served by a build tiered to its value on a backend with the shared-memory budget.

## Conformance CLI

`scripts/algenta_conform.py` computes the verdict for any checkpoint, at the cheapest possible
point (before any weights are converted or any GPU work is done):

```bash
python3 scripts/algenta_conform.py /path/to/model-dir [--backend metal|cuda] [--json verdict.json]
python3 scripts/algenta_conform.py /path/to/config.json        # config-only verdict
python3 scripts/algenta_conform.py --table                     # print the declared capability table
```

Output: the normalized fact manifest, the per-layer kernel-path assignment, and the verdict.
Exit codes: `0` supported, `3` supported pending the tensor probe (config-only runs: qk_norm/bias
presence are facts of the weights and owe a probe), `2` refused with typed refusals, `1` unusable
input.

A supported verdict, a Qwen3-family example:

```text
verdict: supported
facts:   d_model=2048 layers=28 h_q=16 h_kv=8 d_head=128 d_ff=6144 rope=plain tie=1 qk_norm=1 bias=0 act=silu
plan:    grouped_fa_steel
paths:   prefill_attn=steel_grouped_fa_d128 decode_attn=splitk_flash_decoding splitk=splitk_f4u2 kvprod=kvprod/v2
```

A typed refusal names the exact fact:

```text
verdict: refused
REFUSED: head_dim=96 is not supported (supported: {32, 64, 128, 256} — a multiple of 32, a power of two, and <= 256).
```

## Onboarding a model

`onboard` is the one command that turns a checkpoint into a support-matrix row. It extracts the
facts, runs the capability-table decision for every backend, names the staging tier that would
flip a pure-staging refusal, and emits the row plus a JSON ledger line — no per-model code:

```bash
python3 scripts/algenta_conform.py onboard org/model-name      # fetches config (+weights with the repo HF key)
python3 scripts/algenta_conform.py onboard /path/to/model-dir --gate --ledger ledger.jsonl
```

Onboarded models (verdict per backend, plan in parentheses):

| Model | Facts of note | metal | cuda |
| --- | --- | --- | --- |
| Qwen3-1.7B | d128, qk_norm, tied, stage 6144 | supported (grouped_fa_steel) | supported (grouped_fa_steel) |
| TinyLlama-1.1B | d64, untied, GQA 8, stage 5632 | supported (parametric_native_decode) | supported (parametric_native_decode) |
| SmolLM2-360M-Instruct | d64, tied, GQA 3, 15 heads | supported (parametric_native_decode) | supported (parametric_native_decode) |
| Llama-3.2-1B-Instruct | d64, tied, GQA 4, llama3 rope, stage 8192 | refused: staging above Metal ceiling | supported (CUDA STAGE_8192) |
| Llama-3.2-3B-Instruct | d128, tied, GQA 3, llama3 rope, stage 8192 | refused: staging above Metal ceiling | supported (CUDA STAGE_8192) |
| Qwen2.5-7B-Instruct | d128, qkv bias, untied, stage 18944 | refused: staging above Metal ceiling | supported (CUDA STAGE_18944) |
| Mistral-7B-Instruct-v0.3 | d128, untied, stage 14336 | refused: staging above Metal ceiling | supported (CUDA STAGE_18944) |
| Phi-3.5-mini-instruct | head_dim 96, longrope | refused: head_dim 96 | refused: head_dim 96 |
| Gemma-2-2B-it | gelu_pytorch_tanh, window, softcaps | refused: activation/window/softcap | refused: activation/window/softcap |

## Throughput battery (model-agnostic)

One fact-driven entry point benches any onboarded model through the existing resident doors —
no per-model harness, no forked drivers. The Metal arm drives the production SDK path
(`decode` single-stream TTFT+decode, `decode_batched` concurrent aggregate); the CUDA arm drives
the fact-driven `conform_generate_cuda` resident binary across the canonical prefill shapes:

```bash
python3 scripts/algenta_bench.py metal /path/to/model --shapes 160,256,550 --concurrency 1,8
python3 scripts/algenta_bench.py cuda  /path/to/model --driver "./conform_generate_cuda_<tier>"
```

Representative measurements on hardware (the battery withstands models it was never developed
against — each below was onboarded and benched by facts alone):

| Model | Backend | TTFT @160/256/550 (ms) | decode @160/256/550 (tok/s) |
| --- | --- | --- | --- |
| SmolLM2-360M-Instruct | Metal | 35.7 / 40.6 / 84.5 | 413 / 205 / 331 |
| TinyLlama-1.1B | Metal | 59.1 / 108.2 / 137.9 | 245 / 140 / 263 |
| Llama-3.2-1B-Instruct | CUDA (H100, STAGE_8192) | 50.8 / 55.7 / 149.5 | 176 / 136 / 81 |
| Llama-3.2-3B-Instruct | CUDA (H100, STAGE_8192) | 110.7 / 127.1 / 343.6 | 84.5 / 67.1 / 41.2 |
| Qwen2.5-7B-Instruct | CUDA (H100, STAGE_18944) | 248.2 / 274.0 / 693.9 | 57.9 / 50.4 / 34.3 |
| Mistral-7B-Instruct-v0.3 | CUDA (H100, STAGE_18944) | 220.1 / 264.1 / 671.3 | 54.8 / 45.9 / 31.6 |

Concurrent serving runs the same fact-generalized batched resident session (chat mix,
in 1024 / out 256, greedy, warmup excluded). Aggregate decode throughput scales with
concurrency; qk_norm=0 and qk_norm=1 models both run the same driver with no per-model code:

| Model | Facts | agg tok/s @C=1 | agg tok/s @C=8 | scaling |
| --- | --- | --- | --- | --- |
| Qwen3-1.7B-Base | qk_norm=1, tied | 28.7 | 145.5 | 5.07x |
| Llama-3.2-1B-Instruct | qk_norm=0, tied | 44.6 | 230.3 | 5.16x |

Qwen2/Qwen2.5-family checkpoints (q/k/v projection biases) are served by the single-stream CUDA
lane: the batched driver returns a typed refusal for `attention_bias=1` (the bias add is not yet
correct in the batched chain — an attempt produced corrupted tokens, so it is refused loudly rather
than shipped wrong). Their single-stream measurements are tabled above and are the served-path
numbers for bias-carrying checkpoints.

Throughput is reported here as conformance evidence (the battery runs on every onboarded model),
not as a race claim; race comparisons against named external baselines live in
[Benchmarks](../benchmarks/) where they beat the baseline.

## Conformance evidence

**Synthetic fact-space battery.** A parametric generator builds small checkpoints spanning the full
cartesian product the table claims — head_dim {64, 128} × qk_norm {0, 1} × window {none, 1024} ×
rope {plain, dual-theta, llama3-scaled} × activation {silu, gelu-tanh} × bias {0, 1} ×
tie {0, 1} × GQA {1, 2, 4} (576 cells) — then judges every cell twice: the declared table and the
converter agree on the verdict for **576/576 cells**, and every cell the table claims supported
runs **token-identical to an independent Float64 reference — 48/48 cells — on both hardware arms**:
the Metal GPU path and the CUDA-native resident session (`conform_generate_cuda`, the fact-driven
CUDA arm), on identical inputs (same BF16 weights in, greedy tokens out, top-2 logit margins
floored above the quantization noise). Out-of-table cells are refused with the exact fact (that is
a correct outcome). The battery spans the `qwen3_llama` profile's fact space; the Gemma 3 CUDA
lane carries its own correctness gates. The battery is `scripts/algenta_synthetic_battery.py`; its
report ships with every run.

**Real-model gates.** Each model below passes the identity gate: engine greedy tokens are
token-identical to an independent transformers fp32 CPU reference on the same prompt ids
(`scripts/algenta_identity_gate.py`, sampling pinned: `do_sample=False`, `repetition_penalty=1.0`).

| Model | Facts of note | Verdict | Gate |
| --- | --- | --- | --- |
| Qwen3-0.6B-Base | d128, qk_norm, tied | supported (metal) | oracle token 374 + continuation; 8/8 fp32 identity |
| Qwen3-1.7B | d128, qk_norm, tied, stage 6144 | supported (metal) | oracle token 374 + continuation; 16/16 fp32 identity |
| TinyLlama-1.1B | d64, untied, GQA 8 | supported (metal) | 16 tokens: 11 identical + one documented near-tie (engine took the rank-2 token at an fp32 margin of 0.039 — below the int8 quantization floor) |
| SmolLM2-360M-Instruct | d64, tied, GQA 3, 15 heads | supported (metal) | 16/16 fp32 identity |
| Llama-3.2-1B-Instruct | d64, tied, GQA 4, llama3 rope, stage 8192 | supported (cuda) | 16/16 fp32 identity on the CUDA STAGE_8192 build (`conform_generate_cuda`); refused on Metal over staging, as tabled |

Qwen2/Qwen2.5-convention checkpoints (q/k/v projection biases) are proven on the CUDA lane, where
the bias kernels are wired into all five 7B paths (Qwen2.5-7B: 12/12 prompts token-identical to the
fp32 oracle plus cross-engine identity); on Metal the same facts are refused, as tabled above.

**Typed-refusal boundary.** Refusals are correct outcomes; they are the support boundary, published:

| Model | Refusal (exact fact) |
| --- | --- |
| Qwen2.5-1.5B-Instruct | `attention_bias=1` not applied on the Metal path (CUDA lane supports it); `stage_needed=8960` above the Metal tiers |
| Phi-3.5-mini-instruct | `head_dim=96` not in {32, 64, 128, 256}; `rope_scaling=longrope` unimplemented; `stage_needed=8192` |
| Mistral-7B-Instruct-v0.3 | `stage_needed=14336` above the Metal tiers |
| Llama-3.2-1B-Instruct | on Metal: `stage_needed=8192` above the Metal tiers — supported and identity-gated on the CUDA lane's 8192 tier (tabled above) |
| Llama-3.2-3B-Instruct | on Metal: `stage_needed=8192` above the Metal tiers (within the CUDA lane's tiers) |
| Gemma-2-2B-it | `hidden_act=gelu_pytorch_tanh`, `sliding_window=4096`, `attn_logit_softcapping=50`, `final_logit_softcapping=30`, `stage_needed=9216` — each refused, never ignored |

## Adding support

A new model needs no code when its facts are already inside the table — convert and run. Extending
the table (a new head_dim for a steel path, a new staging tier, a new rope scheme) is a declared
capability change plus battery cells spanning the new range, so the proof grows with the support.

Related: [Metal LLM decode](qwen3-metal-decode.md) · [GPU support](gpu-support.md) ·
[Model-agnostic LLM inference](../guides/run-qwen3-family-inference.md)
