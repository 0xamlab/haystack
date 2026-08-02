# RealRace: Algenta vs. llama.cpp vs. mlx-lm, on this machine, right now

This is the RealRace phase: install the real opponents, run the **same checkpoint**, the **same
prompt**, the **same generation length**, through all three engines, on this machine, and report
the honest tokens/sec — win or lose.

**Honest headline (superseded — read the final section, "Four-way race (2026-08-02, later the same
day)", for the current, correct verdict): Algenta loses, by a lot, and the bottleneck is named and
quantified below.** The original numbers and diagnosis in this section are kept verbatim as the
historical record the FastGEMV/MetalRoute/residentk phases built on. **No gitbook page ships, then
or now** — the standing rule ("outright win only ships a page") is still not met after the
decode-path optimizations; see the final section for the current gap and what is still missing.

**Update (2026-08-02, later still): the four-way race's own "submission is a hard ceiling"
finding was investigated as a raw-Metal-dispatch project — see the final section, "Raw-Metal
dispatch addendum". No race was run from that project: it concluded no-go before reaching a
correctness-verified kernel, so there is nothing new to race. The verdict above is unchanged.**

Sections below, in the order they were written: the original RealRace, the FastGEMV ReRace
addendum, the resident-GPU addendum, and finally the four-way race in which all five arms were
measured together. **Where two sections disagree, the last one is right** — in particular the
ReRace addendum's "Metal is 8.1x-13.6x slower at decode" was an artifact of a one-shot API call
shape and is corrected in the final section.

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

---

## Resident-GPU addendum (2026-08-02): `residentk` — 171 dispatches, everything on-device, ~3x the CPU arm and still losing

The ReRace addendum above concluded "Metal is the wrong lever for decode" from
`decode_metal_probe.mojo`, which measured `accel.gemm_metal_flat` at the decode shape. That
measurement is correct and its conclusion was wrong, and the reason is worth stating precisely
because it is the whole content of this phase.

`gemm_metal_flat` is a ONE-SHOT call. Decomposed stage by stage at `m=1, k=1024, n=3072`
(compiled binary, median of 9 after 3 warm):

```
    DeviceContext()                        107 us    2.5%
    3x enqueue_create_buffer                18 us    0.4%
    narrow+upload ACTIVATION (1024 f64)    418 us    9.9%
    narrow+upload WEIGHT (3.1M f64)       2239 us   53.3%   <-- reconverted EVERY call
    enqueue_function                      1035 us   24.6%
    synchronize                             52 us    1.2%
    widen+download RESULT (3072 f32)       335 us    8.0%
```

**53% of that call is re-narrowing a weight that never changes between tokens, and another 12% is
opening a context and allocating buffers that are thrown away.** The probe was not measuring the
GPU; it was measuring the API shape. The correct response was residency, not abandonment.

### What was built

`mojo/engine/residentk/` — a new additive namespace (status codes 600-619) owning GPU state that
outlives a call. `accel/`, `gemm/`, `attnk/`, `normk/`, `mlpk/` and `llmk/` are untouched, and
`qwen3_generate.mojo`'s Float64 CPU decode loop is unmodified and still runnable — it is the
baseline below.

- one `DeviceContext` per generation session, opened once;
- every weight converted Float64 -> Float32 **once at load**, transposed to `[out, in]` on the host
  so a 32-lane SIMD group reads one output column's coefficients contiguously, and uploaded to
  device buffers that live for the whole run (2.50 GB resident);
- the **KV cache resident on-device at fixed capacity and written one slot IN PLACE per step**, from
  inside the RoPE kernel;
- per decode step, **one integer in** (the token id — the embedding row is gathered on-device from
  the resident table, so not even the activation vector is uploaded) and **eight bytes out** (the
  winning logit and its id — the 151,936-wide logits row is never materialised off-device);
- **171 dispatches per token**, not ~560: six fused kernels per layer plus three fixed. The count is
  a contract function (`residentk_dispatch_budget`) and the driver hard-fails if the session issues
  a different number.

Fusion is a correctness condition here, not an optimization. `ctx.enqueue_function` **BLOCKS until
the kernel completes** on this backend — fed a 20 ms kernel it returns in 20.392 ms and the
following `synchronize()` costs 35 us; `ctx.stream()` raises `"Metal stream not implemented"`. So a
token costs the SUM of submission-plus-kernel over every dispatch with no overlap, and a naive
one-op-per-dispatch port would have been ~100 ms/token of pure host overhead — slower than the CPU
path it replaces. Measured with no-op kernels, this design's 171-dispatch mix costs **17.0 ms/token
of submission alone (58.7 tok/s ceiling)** in a light-load window and 43.9 ms in a heavy one.

### Correctness first: the token ids, then the speed

All 16 greedy tokens match the independent `transformers`-CPU (float32) reference exactly, position
by position — `[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718,
13]`, `" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."` — the same
sequence the Float64 CPU arm, llama.cpp and mlx-lm produce. Max per-step logit delta against the
reference: **1.34e-05**.

Against the Float64 Mojo CPU arm, the number that isolates the precision change:

| | value |
|---|---|
| token divergences | **0 / 16** |
| max absolute per-step logit delta | **6.97e-06** |
| max relative per-step logit delta | **2.73e-07** |

2.73e-07 is a small multiple of Float32's 1.19e-07 epsilon, which is what a correct Float32 path
should look like over 28 layers. **Float32 is sufficient for greedy decoding on this model at this
prompt** — stated as a measured result for this prompt and this checkpoint, not as a general claim:
a base model's argmax margins are sometimes small (the Q4_K_M row in the original RealRace table is
what happens when they are not), and a different prompt could in principle land inside 7e-06.

### The numbers

Decode-only tokens/sec (excludes weight load AND prefill), greedy, 16 tokens, prompt
`"The capital of France is"` — the same definition every row above uses. Interleaved
CPU/GPU pairs on this machine (a busy shared dev box; the two arms were run seconds apart in the
same window so the PAIRED ratio is sound even though the absolute numbers move with load):

| Arm | Precision | Compute | Decode tok/s (range) | Median |
|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV + #501's in-place KV) | float64 | CPU, 12 perf cores | 6.35 – 7.80 | **~7.3** |
| **Algenta resident GPU (`qwen3_generate_metal.mojo`)** | float32 | Apple GPU (Metal) | **19.1 – 20.6** | **~20.1** |
| paired speedup, same window | | | 2.51x – 3.18x | **~2.8x** |

Five interleaved pairs at load 11-12, rebased onto `#501` (which landed the reserved-capacity KV
append on the CPU plane while this work was in flight — see below). Ten earlier pairs against the
pre-`#501` CPU arm at load 14-20 gave CPU 6.36-7.83 and GPU 19.1-30.8, i.e. the same CPU range and
a wider GPU one: `#501` does not measurably change the CPU arm at 15 tokens, and the GPU arm's
spread is load, not variance in the design. An earlier, much heavier window (load 22, cold page
cache) gave CPU 2.9-3.4 and GPU 11.9-15.1 — same story, both arms depressed, ratio 3.5-5.1x. The
GPU arm is markedly LESS load-sensitive, which is expected: it occupies one host thread against the
CPU arm's twelve.

**One-time cost, which a resident design front-loads and must therefore report separately:**

| stage | ms |
|---|---|
| session open (context + 2.50 GB of device allocations + 8 shaders compiled) | 6 – 344 (cold shader cache once) |
| read the Float64 blob from disk | 525 – 1700 (page-cache dependent) |
| narrow to Float32 + transpose + upload | **1311 – 1724** |
| **total** | **1841 – 4595** |

Against the CPU arm's 610-632 ms weight load. The resident arm pays ~1.3 s more, once, and earns it
back after roughly 10 tokens.

**The second win — the KV copying that stops existing — was reached independently on both planes.**
`llmk.generate.kv_cache_append_flat` allocates `cache_len + n_new` elements and copies the whole
cache on every call, twice per layer per step: O(N^2) across a generation. Replaying that append
pattern at this run's shapes measures **11.2 – 47.9 ms** of pure copying (10,321,920 Float64
elements) across 15 decode steps. The resident device cache copies **zero**.

Stated honestly: this is **no longer a GPU-versus-CPU difference.** `#501` landed the same fix on
the CPU plane while this work was in flight — `qwen3_generate.mojo` now reserves `max_pos` elements
with `_kv_cache_reserve_flat` and appends in place with `_kv_cache_append_into_flat`, exactly the
shape the resident device cache uses. Two agents reached the same answer on two planes. The number
above is therefore what BOTH arms stopped paying, and the CPU rows in the table are measured AFTER
that fix, so none of the speedup below is attributable to it. It is reported because it is the one
place the cost is quantified, and because at 15 tokens it is a few percent while the growth rate is
quadratic — a 500-token generation is where it would have mattered.

### Verdict, unchanged: still no page

Algenta's best decode arm is now ~20 tok/s (peak 31). llama.cpp CPU-only remeasured at ~41 tok/s in
the ReRace session, llama.cpp GPU at ~261 and mlx-lm at ~307. **The standing rule — an outright win
against BOTH opponents' best measured numbers — is not met, so no gitbook page ships.** A ~3x
decode speedup on top of the FastGEMV chain's ~5x is a real, reproducible engineering result and is
reported as exactly that.

### Where the remaining gap is, named

At 20 tok/s a token is ~49 ms: ~17 ms of MAX submission for 171 dispatches and ~32 ms of kernel
time against a **6.1 ms** bandwidth floor (2.50 GB at this host's measured 411 GB/s streaming
ceiling). So two distinct levers remain, and neither is "the hardware":

1. **The kernels are ~5x off the bandwidth bound.** The GEMV is one SIMD group per output column
   with a scalar inner loop; vectorised loads and more output columns per group are the obvious
   next step. Raw Metal running the same *unfused* split-K GEMVs over the same 2.38 GB measured
   7.198 ms/token (331 GB/s) in the Recon phase, so the headroom is real and measured.
2. **MAX's submission path.** ~100 us per dispatch, blocking, no async. Raw Metal's dispatch floor
   on the same machine is 4.03 us in one command buffer. The only lever that reaches mlx-class
   numbers is driving `MTLCommandBuffer` directly, which would mean Metal Shading Language strings
   instead of Mojo kernels — a trade this phase deliberately did not make.

fp16 weights would halve the 6.1 ms floor and are the largest single kernel-side lever after (1).

### Reproduction

```bash
cd /Users/angel/Developer/decision-engine/mojo_env
# resident GPU arm
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I <worktree>/mojo/engine <worktree>/benchmarks/llm_smoke/qwen3_generate_metal.mojo -o /tmp/qwen3_metal
mkdir -p /tmp/bb/qwen3_ckpt/mojo_generate_metal
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_metal
# CPU arm, unchanged
pixi run mojo build -I <worktree>/mojo/engine <worktree>/benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/qwen3_cpu
/tmp/qwen3_cpu
# reference + cross-check
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_residentk
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_metal/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_residentk/reference_generated.json
```

### Gates

- freeze verification: this change adds ZERO lines to `git diff --stat eea8e045 -- mojo/engine/`
  filtered by the rules-doc alternation (compared before and after — identical file list);
  `git status --porcelain mojo/engine/accel/ mojo/engine/gemm/ mojo/engine/llmk/ mojo/engine/attnk/
  mojo/engine/normk/ mojo/engine/mlpk/` is empty. `residentk/` was added to the alternation in the
  same commit, as `mojo_freeze_namespaces` requires.
- `make inventory-refresh` run unconditionally, then `make inventory-check`: clean. The only
  regenerated-artifact change is `residentk.contract` / `residentk.probe` entering the contract,
  the dispatch, the capability manifest and the catalog.
- `scripts/capability_manifest_gate.py`: no new undeclared kernels.
- `python3 -m scripts.reliability_guards`: no new violations.
- `tests/generate_mojo_tests.py --check`: 192 hand-written suites protected, 465 generated fresh.
- `mojo/tests/libs/test_residentk_session.mojo`: 29/29 with `-D ALGENTA_GPU`, 22/22 without it and
  22/22 under `--target-accelerator=none`.
- `tests/test_accel_gpu_isolation.py`: 15 passed, after generalising it beyond `accel.` — see that
  file for the two holes this phase found in it.

---

## Four-way race (2026-08-02, later the same day): every arm remeasured together — Algenta still loses

The addenda above were written from paired CPU-vs-GPU runs, with the opponents' numbers carried
forward from the earlier ReRace session. This section replaces that: **all five arms were run
interleaved, one after another inside the same round, six rounds**, so every number below comes
from the same machine in the same load window and the cross-arm ratios are measured rather than
assembled from separate sessions.

Same everything as every section above: `Qwen/Qwen3-0.6B-Base` at `/private/tmp/qwen3-0.6b-base`,
prompt `"The capital of France is"`, 16 greedy tokens, decode-only tok/s (excludes weight load and
prefill). Opponents are the installs already on this machine — llama.cpp `10210` (brew,
AppleClang, Metal) on the F16 GGUF at `/tmp/bb/qwen3-0.6b-base-f16.gguf`, and mlx-lm `0.31.3` on
mlx `0.32.0` against the original safetensors. Nothing was reinstalled or reconverted.

Machine: Apple M4 Max, 16 physical cores (12 performance + 4 efficiency), macOS. Shared dev box;
1-minute load average **10.87 – 12.91** across the six rounds, recorded at the top of each round.

### Correctness first, again

Both Algenta arms were checked **position by position against a `transformers`-CPU reference
generated fresh in this session** (`reference_generate.py`, same checkpoint), not against a stored
one:

| Arm | tokens matching the reference | max per-step logit delta |
|---|---|---|
| Algenta resident GPU (float32) | **16 / 16** | **1.34e-05** |
| Algenta CPU (float64, FastGEMV) | **16 / 16** | **8.89e-06** |

`[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]` —
`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."`

Both opponents emit the same text in every one of the six rounds: llama.cpp (`-ngl 0` and
`-ngl 99`) `' Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'`, mlx-lm
`'Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'` (mlx-lm's detokenizer
does not re-emit the leading space the prompt's trailing space consumed; the token content is the
same). **No arm diverged in any round.** Five implementations, one sequence.

### The numbers

Decode-only tokens/sec. Six interleaved rounds; `n = 6` per arm.

| Arm | Precision | Compute | Range | Median | Median vs Algenta's best |
|---|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV) | float64 | CPU, 12 perf cores | 6.66 – 7.23 | **6.88** | 0.34x |
| **Algenta resident GPU (`qwen3_generate_metal.mojo`)** | float32 | Apple GPU (Metal, MAX) | 20.08 – 20.41 | **20.28** | 1x (Algenta's best) |
| llama.cpp `-ngl 0` | F16 | CPU (ggml) | 27.23 – 46.36 | **41.91** | **2.07x faster** |
| llama.cpp `-ngl 99` | F16 | Apple GPU (Metal) | 253.81 – 258.42 | **257.11** | **12.68x faster** |
| mlx-lm | bf16 | Apple GPU (Metal) | 299.17 – 320.77 | **315.51** | **15.56x faster** |

Per-round values, in round order, so nothing is hidden behind a median:

```
algenta_gpu   20.15  20.08  20.28  20.13  20.41  20.41
algenta_cpu    7.23   7.23   6.86   6.66   6.79   6.88
llama_cpu     46.36  44.28  41.91  27.70  27.23  35.84
llama_gpu    257.11 258.32 254.38 254.02 258.42 253.81
mlx          320.77 299.17 313.19 319.60 315.51 309.80
```

The resident GPU arm's paired speedup over the CPU arm, computed per round rather than from the
medians: **2.78x, 2.78x, 2.96x, 3.02x, 3.01x, 2.97x** — median **2.96x**. That is the result this
chain produced, and it reproduces tightly.

The llama.cpp CPU arm has by far the widest spread (27.23 – 46.36, ±26% about its midpoint) because
it is the other arm competing for the same 12 performance cores on a shared box; the three GPU arms
vary by under 4%. That spread does not rescue Algenta: **llama.cpp's slowest CPU round (27.23) is
still 1.33x faster than Algenta's fastest round of any kind (20.41).** There is no load window in
this session in which Algenta wins.

### Publication decision: no gitbook page

The standing rule is an outright win against the field's best real installed opponent, measured on
this machine. Algenta's best arm is 20.28 tok/s. It loses to llama.cpp CPU-only by **2.07x**, to
llama.cpp GPU by **12.68x**, and to mlx-lm by **15.56x**. **No page ships, and none is drafted.**
A 2.96x decode speedup over the CPU arm — on top of the FastGEMV chain's ~5x — is a real,
reproducible engineering result, and it is reported here as exactly that, not as a win.

### The resident-versus-one-shot correction, stated plainly

This is worth recording independently of the ranking, because it reversed a conclusion this
document previously published.

The ReRace addendum concluded, from `decode_metal_probe.mojo`, that **"Metal is 8.1x–13.6x slower
than the CPU path at decode"** and that Metal was therefore the wrong lever for decode. That
measurement was accurate and the conclusion drawn from it was wrong. The probe measured
`accel.gemm_metal_flat`, a **one-shot** call that reopens a `DeviceContext`, reallocates buffers and
re-narrows the weight matrix from Float64 to Float32 on **every invocation**. Decomposed at the
decode shape (`m=1, k=1024, n=3072`), **53% of that call is re-narrowing a weight that does not
change between tokens and a further 12% is opening and discarding a context.** The probe was
measuring the API's call shape, not the GPU.

What the resident design measures instead, with the same kernels on the same hardware and the
conversion hoisted out of the per-token path: **20.28 tok/s versus the CPU arm's 6.88 — the GPU is
2.96x FASTER at decode, not 8-13x slower.** The sign of the comparison flips entirely. The correct
response to the original probe was residency, not abandonment, and "the GPU is slow at this shape"
should have been read as "this API is being called in the wrong shape."

### Where the remaining 49.3 ms/token goes — measured, not apportioned by guess

At the median 20.28 tok/s a token is **49.31 ms**. Three terms, two of them measured directly in
this session:

| term | ms | share | how it was obtained |
|---|---|---|---|
| MAX dispatch submission, 171 dispatches | **16.45** | 33.4% | measured: 171 **no-op** kernels at this design's exact grid mix, best of 7, `/tmp/race4/submit_floor.mojo` |
| irreducible weight reads | **6.09** | 12.3% | 2.5016 GB of resident Float32 at this host's measured 411 GB/s streaming ceiling |
| kernel time above the bandwidth bound | **26.77** | 54.3% | the residual |

Two consequences, both hard:

1. **The kernels are the largest single term, and they are ~5.4x off the bandwidth bound.** The
   GEMV is one SIMD group per output column with a scalar inner loop. This is ordinary Mojo work
   inside `residentk`, with no toolchain risk.
2. **Submission is a hard ceiling on this toolchain.** With *zero* kernel time, 171 blocking
   dispatches cost 16.45 ms — a ceiling of **60.79 tok/s**. `ctx.enqueue_function` blocks until
   completion on the Metal backend and `ctx.stream()` raises `"Metal stream not implemented"`, so
   there is no async path to hide it behind. Raw Metal's dispatch floor on this same machine is
   4.03 us in one command buffer, i.e. 0.69 ms for 171 — the cost is MAX's submission path, not
   the hardware.

So even a perfect-kernel version of this exact design tops out at 60.79 tok/s: it would beat
llama.cpp CPU-only (41.91) and would still lose to llama.cpp GPU by 4.2x and to mlx-lm by 5.2x.
**Winning outright requires all three of** near-bandwidth kernels, raw-Metal command-buffer
submission, and fp16/bf16 weights (which halves the 6.09 ms floor — and note that both GPU
opponents already read half the bytes Algenta does). mlx-lm's 315.51 tok/s is 3.17 ms/token, which
for ~1.25 GB of bf16 weights is ~394 GB/s: **mlx-lm is running at 96% of this machine's measured
streaming ceiling.** Beating it is a bandwidth-bound problem with no slack left in it, and that
should be stated before anyone plans to.

### The single highest-value next lever

**Kernel efficiency inside `residentk.kernels`** — 26.77 ms of a 49.31 ms token, the largest term,
and the only one of the three that needs neither a new toolchain path nor a precision change.
Vectorised loads and more output columns per SIMD group are the obvious next step. Expected
magnitude if the GEMV reaches the bandwidth bound: 49.31 ms -> 22.54 ms, i.e. **20.28 -> ~44 tok/s,
about 2.2x**, which would move Algenta past llama.cpp CPU-only (41.91) and no further. It does not
by itself produce a publishable win, and it should not be started under the impression that it
would.

### Reproduction

```bash
# build both Algenta arms from this worktree
cd /Users/angel/Developer/decision-engine/mojo_env
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I <worktree>/mojo/engine <worktree>/benchmarks/llm_smoke/qwen3_generate_metal.mojo -o /tmp/race4_gpu
pixi run mojo build -I <worktree>/mojo/engine \
    <worktree>/benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/race4_cpu

# one round = every arm once, back to back (from benchmarks/llm_smoke/)
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race4_gpu
/tmp/race4_cpu
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0  --runs 1
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99 --runs 1
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base

# token agreement, against a reference regenerated in the same session
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_race4
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_metal/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_race4/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_llmfwd/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_race4/reference_generated.json
```

One-time costs measured in this session, for completeness: the resident arm pays 4.74 ms session
open + 1131.9 ms blob read + 1345.5 ms narrow/transpose/upload = **2482.5 ms**, against the CPU
arm's **1233.0 ms** weight load. The ~1250 ms difference is earned back after **13 tokens**.

## Raw-Metal dispatch addendum (2026-08-02): tried to attack the submission ceiling directly — no-go, no race run

The four-way race above named MAX's dispatch submission path as the single largest fixed cost at
this decode shape: 171 blocking `ctx.enqueue_function` calls cost 16.45 ms/token (33.4% of the
49.31 ms token, a 60.79 tok/s ceiling even with zero kernel time), while raw Metal's own
command-buffer dispatch floor on this same machine is 4.03 us/dispatch — roughly 250x less. This
project asked the direct question: can Algenta keep its kernels **Mojo-authored** (compiled by
`mojo build`, never hand-written MSL) and swap only the *submission* mechanism — hand-rolled
`MTLCommandBuffer`/`MTLComputeCommandEncoder` dispatch via `external_call` to the Objective-C
runtime, bypassing `DeviceContext.enqueue_function` — to remove that ceiling? Two sourcing routes
for a live, dispatchable kernel were tried, in a new, fully additive worktree
(`.worktrees/metalffi`, branch `feat/metal-ffi-dispatch-probe`; new-namespace-only, nothing under
`mojo/engine/accel/`, `mojo/engine/gemm/`, or `mojo/engine/residentk/` touched).

**Route A — borrow MAX's own live Metal handle.** `DeviceFunction._handle` / `DeviceContext._handle`
are directly readable (Mojo does not enforce field privacy) but point at `_DeviceFunctionCpp` /
`_DeviceContextCpp` — zero-field placeholder structs; Mojo's own type model carries no knowledge of
the underlying AsyncRT object's C++ layout, so there is nothing to read *from* Mojo's perspective.
A byte-level heap scan around both handles (enumerate all 9,754 loaded Objective-C classes via
`objc_getClassList`, read candidate memory crash-safely via the `mach_vm_read_overwrite` Mach trap,
match isa-pointers, follow one further hop) is proven methodologically sound — it found real,
unrelated live Objective-C objects at depth 2 elsewhere in the process — but found **zero** `MTL*`/
`AGX*` objects among 1,884 total class matches / 80 unique classes near either handle. **Not real:**
no Metal object is reachable as a near/shallow member of what Mojo exposes.

**Route B — extract Mojo's own compiled kernel binary and dispatch it by hand.** This one is real
up to, and breaks exactly at, execution. Mojo embeds a complete, standalone, well-formed
`.metallib` container (magic `MTLB`, a real `air64-apple-macosx26.0.0` compile) directly in the
compiled binary's `__TEXT,__const` section. Extracting those exact bytes (self-declared length at
offset +16) and loading them through the fully public Metal API —
`dispatch_data_create` -> `-newLibraryWithData:error:` -> `newFunctionWithName:` ->
`newComputePipelineStateWithFunction:error:` — **succeeds**: the mangled kernel name resolves,
`MTLComputePipelineReflection` shows the declared arguments as sequential buffer indices in
declaration order, exactly as expected. A full hand-rolled dispatch path was built from Mojo
(`MTLCommandBuffer`/`MTLComputeCommandEncoder`, `setBuffer:offset:atIndex:`,
`dispatchThreadgroups:threadsPerThreadgroup:`, `commit`/`waitUntilCompleted`, all reached via
`external_call` to `objc_msgSend`/`sel_registerName`) and it completes with `status=4 (completed)`,
no error — **but the kernel's buffer write never lands.** `MTLComputePipelineReflection` shows the
written buffer's access as `MTLBindingAccessReadOnly` even for a kernel that only ever writes it —
working theory: Mojo's Metal codegen marks buffer arguments read-only in the compiled AIR
regardless of actual use, and Metal's own optimizer, reached through the public
`newLibraryWithData:` load path, treats the store as dead code against a declared-read-only binding
and drops it. This reproduces identically in a from-scratch, pure Objective-C program driving the
same extracted bytes (ruling out the Mojo FFI layer as the cause) and in a from-scratch, pure
Objective-C program against a completely independent (non-Mojo) `.metallib` built to the same
minimal 1-arg shape, i.e. this is a property of how Metal's public load path treats this codegen
pattern, not a bug in the probe. MAX's own internal loading/dispatch path evidently avoids or
corrects this — the identical compiled kernel runs correctly through `DeviceContext.enqueue_function`
(every number in every section above depends on that being true).

**Independent re-verification, not taken on faith.** A second pass rebuilt
`metal_ffi_dispatch_probe.mojo` from scratch in the same worktree and reran it cold: identical
central numbers (`max |hand_rolled[i] - max_enqueued[i]|` over 3072 outputs = **1084.7439** both
times; `y[0]` hand-rolled stuck at the `-999.0` pre-dispatch sentinel both times). The dispatch-cost
side numbers were in the same ballpark across the two runs (hand-rolled single dispatch/commit+wait
median 839-925 us vs. MAX's 350-362 us; MAX wins single-dispatch on this toolchain) — batching 20
dispatches into one command buffer got to 713-760 us/dispatch, still worse than MAX's per-call cost,
so the Mojo<->C `external_call` crossing overhead (~8 crossings/dispatch in this implementation)
would need designing away even before the correctness bug, for this specific hand-rolled
implementation to be a submission-cost win at all.

**Verdict: no-go, as specified.** The owner's constraint — kernel stays Mojo-authored, only
dispatch/submission may change — is not satisfiable today. There is no live Metal handle to borrow
(Route A) and Mojo's own compiled kernel bytes do not execute correctly once loaded through the
public Metal API outside MAX's runtime (Route B), confirmed independent of the FFI mechanism in
pure Objective-C. Per the standing instruction for this exact situation — a no-go with no viable
path does not get forced into a race — **no speed number is reported for a raw-Metal-dispatch decode
path, no arm was added to any race, and no gitbook page is affected.** The four-way race's verdict
above (Algenta's best, 20.28 tok/s, loses to llama.cpp CPU 2.07x / llama.cpp GPU 12.68x / mlx-lm
15.56x) stands unchanged; the submission-ceiling term it named (16.45 ms, 33.4%) remains
unaddressed.

**What would unblock this, concretely — an upstream Mojo/MAX gap, not a probe bug:**

1. A documented way to mark a GPU kernel's pointer/buffer argument as read-write (vs. Mojo's
   apparent default of read-only) in the AIR Metal codegen emits — e.g. an access-hint on the
   parameter type or a `compile_function` flag — so that a kernel extracted and reloaded through
   the public `newLibraryWithData:` path is not dead-code-eliminated by Metal's own optimizer. This
   is the one, narrow, verifiable fix that would flip Route B from broken back to viable; it was
   flagged as unexplored by the Build phase and remains unexplored here too — this toolchain
   install ships no bundled `.mojo` stdlib source to check compile-time flags against, and chasing
   that further is new investigation, not verification of an existing claim, so it is reported as
   an open question rather than attempted.
2. Failing that, an officially-supported (non-reflection, non-heap-scan) accessor from
   `DeviceContext`/`DeviceFunction` to the underlying live `id<MTLLibrary>`/`id<MTLFunction>` (or
   an async submission primitive — `ctx.stream()` currently raises `"Metal stream not
   implemented"` on this backend) would remove the need for Route B/extraction entirely.
3. Two smaller, real Mojo-toolchain frictions worth an upstream report regardless of the above:
   `external_call["objc_msgSend", ...]` registers one global extern per **name**, so a second call
   site with a different signature under the same name fails to compile; and the natural
   workaround (`dlsym` + an indirect call through a Mojo function-pointer value) compiles but
   crashes inside `libKGENCompilerRTShared.dylib` at the point of the indirect call, on this exact
   toolchain (both reproduced with minimal repros; worked around here with a one-signature-per-name
   C shim, `objc_shim.c`, containing zero kernel logic).

Absent (1) or (2), the only path left to move past the submission ceiling with today's public APIs
is hand-porting `residentk`'s kernels to hand-written MSL — which trades the "kernel stays
Mojo-authored" constraint for the ceiling, is a real two-stage-verified build (each ported kernel
checked against the existing Mojo-compiled version before trusting it) rather than an extension of
this probe, and needs explicit sign-off that hand-written MSL satisfies "Mojo-authored" before
anyone spends the time, since under a literal reading it plainly does not.

**Files (all new, additive-only, under `benchmarks/llm_smoke/metal_ffi_probe/`):**
`objc_link_probe.mojo` (FFI reachability), `handle_probe.mojo`/`handle_int_probe.mojo`
(private-field readability), `heap_scan_probe.mojo` (Route A), `gemv_metallib_dump.mojo` /
`trace_target.mojo` / `minimal_write_probe.mojo` (Route B extraction + the isolated write-bug
repro), `metal_ffi_dispatch_probe.mojo` (the full pipeline, this section's numbers),
`objc_shim.c` (the one-signature-per-symbol C shim). No file under `mojo/engine/` was added,
removed, or modified by this project.

**Gates:** `git status --short` in the worktree shows only this one new, untracked directory —
`accel/`, `gemm/`, `residentk/`, and every other frozen/existing kernel file are byte-identical to
`origin/main`. Nothing here changes the runtime library contract, the capability manifest, or any
generated-test suite, so `inventory-refresh`/`inventory-check`/the capability gate/
`generate_mojo_tests.py --check` all report zero diff against the rebased tree (rerun and confirmed
after rebasing onto `origin/main`, see the PR this section ships with).
