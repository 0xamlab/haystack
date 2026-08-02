# RealRace: Algenta vs. llama.cpp vs. mlx-lm, on this machine, right now

This is the RealRace phase: install the real opponents, run the **same checkpoint**, the **same
prompt**, the **same generation length**, through all three engines, on this machine, and report
the honest tokens/sec — win or lose.

**Honest headline (superseded by the 2026-08-02 ReRace addendum below — read that section for the
current, correct verdict): Algenta loses, by a lot, and the bottleneck is named and quantified
below.** The original numbers and diagnosis in this section are kept verbatim as the historical
record the FastGEMV/MetalRoute phases built on. **No gitbook page ships, then or now** — the
standing rule ("outright win only ships a page") is still not met after the decode-path
optimization; see the addendum for the current gap and what is still missing.

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

---

## ReRace addendum (2026-08-02): FastGEMV shipped, Metal-decode measured and rejected — still losing

This is the ReRace phase, closing out the FastGEMV -> MetalRoute -> ReRace chain that started from
the "bottleneck, named and quantified" section above. Same machine (Apple M4 Max, 16 physical
cores, macOS), same checkpoint (`Qwen/Qwen3-0.6B-Base`, `/private/tmp/qwen3-0.6b-base`), same
prompt (`"The capital of France is"`), same 16-token greedy generation, same decode-only tok/s
definition (excludes weight load and prefill), same llama.cpp (`brew`, F16 GGUF at
`/tmp/bb/qwen3-0.6b-base-f16.gguf`) and mlx-lm (`/tmp/bb/bin/python`, mlx-lm against the original
safetensors) installs already present from the original RealRace phase — reinstalled nothing,
reconverted nothing.

### What changed in the decode path since the original numbers above

1. **FastGEMV (shipped, wired in):** `llmk.gemv_fast.gemv_transposed_parallel_flat` replaces all 7
   per-layer `gemv_flat(..., trans=True)` calls in `qwen3_generate.mojo`'s decode step with a
   parallel column-band path over the same frozen-kernel shape (see that module's docstring above
   this section's file). `gemm/blocked.mojo` itself is untouched.
2. **MetalRoute (measured, not wired in):** `benchmarks/llm_smoke/decode_metal_probe.mojo` measures
   `accel.gemm_metal_flat` at the exact decode shapes (`m=1`, `k`/`n` in {1024, 2048, 3072}) against
   both the new FastGEMV CPU-parallel path and the old scalar path. Reconfirmed today: the GPU path
   is **8.1x–13.6x slower** than FastGEMV's CPU-parallel path at every shape tested (q_proj 11.4x,
   kv_proj 8.1x, o_proj 8.5x, gate/up 13.6x, down 11.8x slower), and often slower than even the old
   scalar path — a single-token matmul is too small to amortize Metal's fixed per-call overhead
   (buffer allocation, Float64<->Float32 conversion, launch, sync). The same weight shapes batched
   like prefill instead (`m=16/64/256`) show the GPU **winning** (0.40x, 0.74x, 0.34x of CPU time —
   under 1 means GPU wins), confirming the crossover is real and that Metal routing belongs at
   *prefill*, not decode, on this model/host. Per the task's explicit instruction not to fake a
   pointless wrapper, this was **not** wired into `qwen3_generate.mojo` — there is no second,
   "Metal-routed" Algenta decode arm to race, because it would be a regression, not an improvement.
   Only one Algenta row appears in the table below.

### Correctness, reverified a final time, three ways

All three re-run just now, independently, from a clean rebase onto `origin/main`'s current tip:

- **Algenta** (`qwen3_generate.mojo`, this chain's FastGEMV-optimized decode path): token ids
  `[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]`
  (`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."`), identical across
  every repeated run today (5 runs total, including the pre-optimization scalar-path baseline rerun
  below).
- **`transformers`-CPU reference** (`reference_generate.py` on `/tmp/bb/bin/python3`, transformers
  5.14.1, run independently just now against the same checkpoint): the exact same 16 token ids,
  byte-for-byte, with per-step logits matching Algenta's own reported per-step logit to 5+ decimal
  places (e.g. step 0: both report `21.039467`).
- **llama.cpp** (`realrace_llama_cpp.py`, both `-ngl 0` and `-ngl 99`, F16 GGUF, run independently
  just now): generated text `" Paris. The capital of Germany is Berlin. The capital of Italy is
  Rome."` — identical to Algenta and the reference.
- **mlx-lm** (`realrace_mlx_lm.py`, run independently just now against the original safetensors):
  generated text `"Paris. The capital of Germany is Berlin. The capital of Italy is Rome."`
  (mlx-lm's tokenizer does not re-emit the leading space consumed by the prompt's own trailing
  space; the token content is identical) — identical to Algenta and the reference.

Four independent implementations, greedy-decoding the same base model from the same prompt, still
agree token-for-token after the decode-path change. No speed number below is reported without this
having been checked first.

### The numbers: old vs. new Algenta, and both real opponents, remeasured today

Decode-only tokens/sec, greedy, 16 generated tokens, repeated runs on this machine just now (load
average ~13-15 throughout this session — lighter than the original RealRace session's ~20, noted
because it means llama.cpp's CPU numbers below are not directly comparable across sessions; the
Algenta old-vs-new comparison IS directly comparable, since both were measured in the same session
minutes apart):

| Engine | Precision | Compute | Decode tok/s (range) | Typical | vs. Algenta (new) |
|---|---|---|---|---|---|
| **Algenta, pre-FastGEMV** (`gemv_flat(...,trans=True)` scalar path, re-run today for a same-session baseline) | float64 | CPU (1 core) | 1.32 – 1.38 | ~1.35 | 0.20x (i.e. new is ~5.0x faster) |
| **Algenta, FastGEMV** (`gemv_transposed_parallel_flat`, this chain's shipped decode path) | float64 | CPU (parallel, up to 12 perf cores) | 4.94 – 8.00 | **~6.7** | 1x (baseline) |
| llama.cpp, CPU-only (`-ngl 0`), remeasured today | F16 | CPU (ggml, SIMD + multi-threaded) | 38.8 – 43.5 | ~41 | **~6.1x faster** |
| llama.cpp, GPU (`-ngl 99`), remeasured today | F16 | Apple GPU (Metal) | 256.9 – 265.8 | ~261 | **~39x faster** |
| mlx-lm, remeasured today | bf16/fp16 (native MLX) | Apple GPU (Metal) | 302.9 – 310.2 | ~307 | **~46x faster** |
| Algenta, hypothetical Metal-routed decode (measured via the probe, NOT wired in — not a real arm) | float64 vs float32 | Apple GPU (Metal) | n/a | 8.1x–13.6x SLOWER than the FastGEMV row | would be a regression, not a contender |

FastGEMV delivered a real, reproducible **~5.0x** decode speedup on this exact checkpoint/prompt
(typical 6.7 tok/s vs. the same-session pre-change baseline's 1.35 tok/s) purely from the CPU
parallel-path fix — no precision change, no GPU. That is the honest, full effect of the lever this
chain shipped. It is not enough: Algenta's *own best* now-optimized number, ~6.7 tok/s, still loses
to llama.cpp's *CPU-only* number (~41 tok/s) by ~6.1x, before either opponent's GPU number is even
considered — and loses to both opponents' GPU numbers by ~39x and ~46x.

### Why the gap is ~6x now instead of ~19x, and why ~6x is still a loss, named precisely

The original doc's point 1 (7-of-8 decode matmuls hitting a single-threaded scalar branch, 15 of 16
cores idle) is fixed — that was the dominant term, and closing it recovered most of what a
naive "just parallelize it" fix could realistically recover. Two terms remain, both already named
in the original doc's points 2-3 and neither touched by this chain on purpose (rule 3: additive
only, no frozen-kernel rewrite):

1. **Parallel fan-out is not linear speedup.** ~12 available performance cores times the old
   ~1.35 tok/s would predict something over 10x if the fix were free; the measured ~5.0x is roughly
   half that. `parallelize`'s per-call fan-out/join cost, plus this being a genuinely shared
   machine (load average ~13-15 during these very runs, sibling-agent Mojo processes in other
   worktrees), both eat into the theoretical ceiling — this is the same caveat the original doc
   made about its own numbers, still true here, and it is why the range (4.94-8.00 tok/s) is wide
   rather than a tight cluster.
2. **float64 is still the wire type**, still 2-wide SIMD (128-bit NEON) on this host versus fp16's
   4-wide or bf16's 8-wide lanes that both opponents use for this same comparison. This is exactly
   `llmk.gemv_fast`'s own docstring's stated reason for staying float64-only and leaving precision
   as a separate, later lever — mixing it into this chain's number would have conflated two fixes
   into one, unattributable result. It was not pursued this chain, and remains unfixed.
3. **Compute placement for decode remains CPU-only, correctly** — MetalRoute's probe (reconfirmed
   above) shows GPU is the wrong lever for a single-token matmul on this host; the placement
   opponents get "for free" is not free for Algenta's decode step at float64, on this host, at
   this batch size. GPU is real head-room for *prefill* (0.34x-0.74x, GPU winning) on this exact
   model — a distinct, unstarted future item, not a decode fix.

The next lever, if pursued, is precision (an additive fp16/bf16 GEMV kernel, per `gemv_fast.mojo`'s
own docstring) measured against this now-improved baseline rather than the original scalar one —
that is the honest "what's still missing" this addendum owes, not a vaguer "needs to be faster."

### Publication decision

**No gitbook page ships.** The standing rule is an outright win against BOTH opponents' best
measured numbers on this machine, real installs, no proximity claims, no cap-ties counted as wins.
Algenta's optimized decode path (~6.7 tok/s typical) loses to llama.cpp's CPU-only number (~41
tok/s, ~6.1x) and to both GPU numbers (~39x, ~46x). A ~5x internal speedup is a real, measured,
reproducible engineering result — and is reported as exactly that, a lever that mattered, not a
win. It does not change the win/loss verdict, and no page is written or published for it.

### Gates, all clean, on the rebased tree

- Rebased `feat/llmk-decode-parallel-gemv` onto `origin/main`'s tip (`8fbc86c6`) — clean, no
  conflicts (main's concurrent changes, e.g. `#495`'s `optmodel/formulation.mojo` fix, do not
  overlap this chain's files).
- `make inventory-refresh` (unconditional) after the rebase: zero diff — the previously-generated
  artifacts (`runtime_library_dispatch_generated.mojo`, `runtime_library_contract.json`,
  `runtime_capability_manifest.json`, `runtime-library-catalog.md`) were already current against
  the rebased tree.
- `make inventory-check`: clean.
- `python3 -m scripts.reliability_guards` (includes the `mojo_freeze_namespaces` guard): clean, no
  new violations (only the pre-existing, already-baselined wave B10/D/E debt).
- `./scripts/run_repo_python.sh scripts/capability_manifest_gate.py`: "no new undeclared kernels."
- `git diff HEAD -- mojo/engine/accel/ mojo/engine/gemm/ mojo/engine/llmk/`: **empty** for
  `accel/` and `gemm/` (frozen, including `accel/gemm_metal.mojo` and `gemm/blocked.mojo`
  specifically) — `llmk/` shows only this chain's own additive files (`gemv_fast.mojo`, new; a
  4-status-code addition to `contract.mojo`).
- `tests/generate_mojo_tests.py --check`: "191 hand-written suite(s) protected, 463 generated
  suite(s) fresh."
- `mojo/tests/libs/test_llmk_gemv_fast.mojo` (FastGEMV's suite): 7/7 assertions pass, including the
  300x300 and 128x1536 decode-projection-shaped cases against the frozen `gemv_flat`, worst abs
  delta `0.0`.
- `mojo/tests/libs/test_llmk_contract.mojo` (regenerated A-Z suite covering `llmk.contract`,
  including the new `llmk_gemv_dims_check`): 5/5 pass.
- `decode_metal_probe.mojo` is a hand-written, intentionally-unregistered probe (see its own
  docstring) — not part of `generate_mojo_tests.py`'s protected/generated suites by design; its
  output is the measurement reported above, reconfirmed stable.

### Reproduction (this addendum)

```bash
# Old (pre-FastGEMV) baseline, same-session comparison:
git show 9f82eac5:benchmarks/llm_smoke/qwen3_generate.mojo > /tmp/qwen3_generate_old_baseline.mojo
cd /Users/angel/Developer/decision-engine/mojo_env && pixi run mojo run \
    -I <worktree>/mojo/engine /tmp/qwen3_generate_old_baseline.mojo

# New (FastGEMV) decode path:
pixi run mojo run -I <worktree>/mojo/engine <worktree>/benchmarks/llm_smoke/qwen3_generate.mojo

# Metal-decode probe (requires the GPU build flag + a shader compiler):
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo run -D ALGENTA_GPU \
    -I <worktree>/mojo/engine -I <worktree>/benchmarks <worktree>/benchmarks/llm_smoke/decode_metal_probe.mojo

# Opponents (already installed/converted from the original RealRace phase — not reinstalled):
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base

# Reference cross-check:
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base
```
