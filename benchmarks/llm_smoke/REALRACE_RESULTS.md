# RealRace: Algenta vs. llama.cpp vs. mlx-lm, on this machine, right now

This is the RealRace phase: install the real opponents, run the **same checkpoint**, the **same
prompt**, the **same generation length**, through all three engines, on this machine, and report
the honest tokens/sec — win or lose.

**Honest headline: Algenta loses, by a lot, and the bottleneck is named and quantified below.**
No gitbook page ships for this — the standing rule ("outright win only ships a page") is not met.
This document is the honest capability report the RealRace phase produces either way.

## Setup

- Machine: Apple M4 Max, 16 physical cores (12 performance + 4 efficiency), macOS.
- Checkpoint: `Qwen/Qwen3-0.6B-Base`, real HF safetensors snapshot at `/private/tmp/qwen3-0.6b-base`
  (the SAME checkpoint the Prerequisite/GenerationLoop phases verified the Mojo forward pass and
  decode loop against).
- Prompt: `"The capital of France is"` (5 tokens). Generation length: 16 tokens. Greedy decoding
  (temperature 0 / argmax) everywhere — the only decoding strategy comparable across engines
  without a matched RNG (this repeats the GenerationLoop phase's own reasoning for why greedy, not
  top-k/top-p, is what's compared).
- "Decode-only tokens/sec" means: time to generate the N decode-step tokens, excluding weight load
  and prefill — the standard steady-state throughput number, and the same definition
  `qwen3_generate.mojo` already reports.
- Opponents installed for real, on this machine, for this phase (neither was present before):
  - **llama.cpp**: `brew install llama.cpp` (10210, AppleClang, Metal support built in).
  - **mlx-lm**: `pip install mlx-lm` into `/tmp/bb/bin/python` (mlx 0.32.0, `mx.default_device()` ==
    `Device(gpu, 0)` — genuinely Apple-Silicon-native, matching the MLX-LM plan's own target).
- GGUF conversion: the brew bottle does not ship `convert_hf_to_gguf.py`, so a shallow
  (`--depth 1`) clone of `ggml-org/llama.cpp` at `/tmp/bb/src/llama.cpp` supplied it (its own
  `gguf-py`, imported via `PYTHONPATH`, since `-P` disables the script-directory sys.path
  insertion this repo's Python invocations require). Converted to F16 GGUF — same precision family
  as mlx-lm's bf16/fp16, so the primary comparison is not "Algenta vs. a quantized opponent."
  `Q4_K_M` was also produced as a bonus/informational data point (see caveat below).
- This is a busy shared dev machine (load average ~20 during these runs, several sibling-agent
  Mojo processes running in other worktrees concurrently). CPU-bound numbers below are reported as
  a repeated-run range for that reason; the order-of-magnitude story does not change across the
  range.

## Correctness first: all three agree

Before racing speed, the sequences have to match — an autoregressive loop compounds any per-step
error, so a speed number on a wrong sequence would be worthless. All three engines, run
independently just now, greedy-decode the **exact same text** from the same prompt:

```
Paris. The capital of Germany is Berlin. The capital of Italy is Rome.
```

- Algenta (`qwen3_generate.mojo`): token ids `[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13,
  576, 6722, 315, 15344, 374, 21718, 13]`, already cross-checked byte-for-byte against an
  independent `transformers`-CPU reference in the GenerationLoop phase.
- llama.cpp (`llama-server` on the F16 GGUF, `-ngl 99` and `-ngl 0`, via
  `realrace_llama_cpp.py`): identical text, both GPU- and CPU-only.
- mlx-lm (`mlx_lm.generate`/`stream_generate` on the original safetensors, via
  `realrace_mlx_lm.py`): identical text.

Three independently-implemented engines (one hand-built in this repo on frozen float64 Mojo
kernels, two mature real-world C++/MLX projects) agreeing token-for-token on the same base model
and prompt is strong external validation of the Prerequisite/GenerationLoop phases' own
`transformers`-CPU cross-check — this is not a self-check anymore, it is three-way agreement.

## The numbers

Decode-only tokens/sec, greedy, 16 generated tokens, repeated runs on this machine just now:

| Engine | Precision | Compute | Decode tok/s (range) | Typical | vs. Algenta |
|---|---|---|---|---|---|
| **Algenta** (`qwen3_generate.mojo`) | float64 | CPU (mostly 1 core — see below) | 1.35 – 1.36 | **~1.35** | 1x (baseline) |
| llama.cpp, CPU-only (`-ngl 0`) | F16 | CPU (ggml, SIMD + multi-threaded) | 22.4 – 29.0 | ~26 | **~19x faster** |
| llama.cpp, GPU (`-ngl 99`) | F16 | Apple GPU (Metal) | 221 – 267 | ~245 | **~180x faster** |
| mlx-lm | bf16/fp16 (native MLX) | Apple GPU (Metal) | 302 – 318 | ~308 | **~228x faster** |
| llama.cpp, GPU, Q4_K_M (bonus, see caveat) | int4/int6 (K-quant) | Apple GPU (Metal) | 338 – 367 | ~350 | ~257x faster (not sequence-verified) |

Prefill (5-token prompt) numbers, for completeness — not the focus of this phase, and too short a
prompt for a meaningful trend either way: Algenta ~594-769ms wall for the 5-token prefill (not a
per-token rate the driver reports directly); llama.cpp GPU ~75-284 tok/s; mlx-lm ~79-90 tok/s.
llama.cpp CPU-only prefill was ~76-118 tok/s, i.e. faster than its own CPU decode — expected, since
prefill batches all 5 prompt tokens through one wide multi-row matmul while decode is one row at a
time.

**Q4_K_M caveat, stated honestly**: the Q4_K_M row is a realistic-deployment data point, not part
of the correctness-verified three-way race. Quantizing this same checkpoint to Q4_K_M changes its
greedy continuation (`" ____.\nA. Paris\nB. Rome\nC. London\nD."` instead of `" Paris. The capital
of..."`) — quantization error on a 0.6B *base* model is large enough to flip which token wins an
already-close argmax. That is a real, known effect of aggressive quantization on small models, not
a bug in the conversion or the comparison; it is reported as a speed data point only, explicitly
flagged as not sequence-matched to the reference.

## The bottleneck, named and quantified, not vague

Algenta is not merely "slower" — the CPU-vs-CPU row above (llama.cpp `-ngl 0`, same hardware,
same host, no GPU on either side) isolates that **GPU-vs-CPU placement is only a ~9-10x factor**
(llama.cpp CPU ~26 tok/s -> llama.cpp GPU ~245 tok/s). The other ~19x, on the *identical* CPU, comes
from the kernel path, and it is traceable to one specific, frozen-kernel-documented design choice:

1. **7 of 8 per-decode-step matrix-vector multiplies hit `gemm.blocked.gemv_flat`'s
   single-threaded, unvectorized scalar branch — by the frozen kernel's own stated design.**
   `qwen3_generate.mojo` calls `gemv_flat(..., trans=True)` for every per-layer Q/K/V/O/gate/up/down
   projection (see `benchmarks/llm_smoke/qwen3_generate.mojo` lines calling `gemv_flat(...,
   True)`), because `prepare_qwen3_checkpoint.py` pre-transposes every weight so *prefill's*
   `sgemm_flat` hits its fast SIMD path (documented in that file's own docstring). That same
   pre-transposition means every decode-step `gemv_flat` call lands on the `trans=True` branch in
   `mojo/engine/gemm/blocked.mojo`, which is a plain indexed loop with **no `parallelize` call
   anywhere in that branch** — `gemm.blocked`'s own module docstring says this outright:
   *"Transposed operands take the scalar path, on purpose... trans_a/trans_b route to a
   straightforward indexed triple loop... A caller who cares about speed transposes once up front
   instead."* Only the 8th call per step — the tied `lm_head` projection over the full 151,936-word
   vocabulary, which is *not* transposed — hits the parallelized `gemv_band` branch and fans out
   across this machine's physical cores. So on a 16-core machine, **15 of those cores sit idle for
   7 of every 8 matmuls in every decode step**, without an external profiler needed to see it: it's
   in the frozen kernel's own docstring plus the call sites.
2. **float64 is the wire type everywhere, halving-to-quartering available SIMD width even where
   parallelism does apply.** `gemm.blocked`'s own docstring states it measured
   `simd_width_of[float64]() == 2` (128-bit NEON) on this exact host — f32 would be 4-wide, bf16
   8-wide. Both opponents run this comparison's arm in fp16/bf16 (mlx-lm) or F16 (llama.cpp), so
   even Algenta's *parallel* branch (the lm_head call) is working with a quarter of the per-lane
   throughput fp16 SIMD gets on the same silicon, before core-count is even considered.
3. **Compute placement**: mlx-lm and llama.cpp's GPU run put the whole decode step on the Apple
   GPU's thousands of ALUs; Algenta's decode loop is pure CPU. Row 2 above shows this is real but
   secondary (~9-10x) next to point 1.

None of this required rewriting a frozen kernel to diagnose — `gemm.blocked.gemv_flat`'s two
branches, and which one 7-of-8 decode calls land on, is exactly what the numbers above predict:
the non-parallel branch's own per-layer work (~440M multiply-adds across 28 layers) divided by the
observed ~730ms/step implies roughly 1.2 GFLOP/s of *effective* single-core scalar float64
throughput, which is the right order of magnitude for an unvectorized double-precision loop on one
M4 Max core — consistent with, not contradicting, points 1 and 2.

## What this does NOT mean

This is not evidence the KV cache, the GEMV routing, or the generation loop itself are wrong —
correctness was verified three ways (`transformers` CPU reference in the GenerationLoop phase, plus
now llama.cpp and mlx-lm agreeing token-for-token here). The loop is real, the cache is real, the
sequence is right. The loss is a precision/kernel-routing/compute-placement story on top of a
correct implementation, and the frozen-kernel discipline (`gemm.blocked` was not modified to chase
this number — see the freeze-verification note below) means the fix, if ever pursued, is either a
new additive fp16/bf16 GEMV kernel or an additive parallel path for the transposed-operand case —
not a change to what's frozen today.

## Reproduction

```bash
# 1. llama.cpp (brew) + mlx-lm (pip), once:
brew install llama.cpp
/tmp/bb/bin/python -P -m pip install mlx-lm gguf

# 2. GGUF conversion, once (needs a llama.cpp source checkout for convert_hf_to_gguf.py):
git clone --depth 1 https://github.com/ggml-org/llama.cpp.git /tmp/bb/src/llama.cpp
cd /tmp/bb/src/llama.cpp
PYTHONPATH="$PWD:$PWD/gguf-py" /tmp/bb/bin/python -P convert_hf_to_gguf.py \
    --outfile /tmp/bb/qwen3-0.6b-base-f16.gguf --outtype f16 /private/tmp/qwen3-0.6b-base
llama-quantize /tmp/bb/qwen3-0.6b-base-f16.gguf /tmp/bb/qwen3-0.6b-base-q4_k_m.gguf Q4_K_M  # bonus

# 3. Run each arm (from this directory):
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base
cd /Users/angel/Developer/decision-engine/mojo_env && pixi run mojo run \
    -I<this worktree>/mojo/engine <this worktree>/benchmarks/llm_smoke/qwen3_generate.mojo
```
