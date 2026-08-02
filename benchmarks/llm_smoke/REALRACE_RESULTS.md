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

**Update (2026-08-02, later still again): fused batched dispatch + vectorized GEMV + fp16 weights,
combined for the first time — read "Batched-dispatch + full-stack addendum" for that result
(206.38 tok/s, still short of both opponents), then the "Int8-weight addendum" for a third
precision tier on top of it (241.83 tok/s — closer, still short of both opponents), then the
"Dispatch-fusion + packed-int8-load addendum" for two more levers tried and confirmed dead ends
(no kernel change, no new number).**

**Update (2026-08-02, final for today): the full field was re-raced together — Algenta CPU/fp16/
int8, llama.cpp CPU/GPU, mlx-lm — six interleaved rounds, fresh token verification. Read
"Final real race (2026-08-02): every arm, six rounds, verdict for today" for the closing numbers.
Algenta's best arm (int8, 243.06 tok/s median) still loses to both real opponents on this run
(llama.cpp GPU 256.72, mlx-lm 313.21). No gitbook page ships. That section is the current, correct,
final verdict for today's chain of work.**

**Update (2026-08-02, later still again): speculative/prompt-lookup decoding was investigated as
the next lever on top of the int8 arm above — see "Speculative decoding addendum" for the full
analysis. No-go, at both the Design and an independent Build-phase verification pass, before any
kernel was written: this benchmark's exact text caps accepted-draft-length at 1 token, once, across
all 16 generation steps (the repeating unit is a template, "The capital of", not content — the very
next token is always the varying fill-in-the-blank slot). No mechanism was built, no worktree
survived, no race was run — there is nothing new to race, and the 243.06 tok/s verdict above is
unchanged.**

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

## Kernel-efficiency + fp16 addendum (2026-08-02, later still): vectorized GEMV + additive fp16 weights close ~23% of the gap — still losing everywhere

The four-way race above named `residentk`'s kernel time as the single largest term in the decode
token (26.77 ms of 49.31 ms, 54.3%, ~5.4x off the measured bandwidth bound) and the submission path
as the second-largest (16.45 ms, 33.4%, a hard 60.79 tok/s ceiling on this toolchain). This project
attacked the first of those two directly. The second — per the raw-Metal-dispatch addendum
immediately above, which ran in parallel on the same `residentk` base and landed on `origin/main`
first (`#504`) — is a **confirmed no-go through any public API on this toolchain**, not merely
unattempted: no live Metal handle is reachable from `DeviceContext`/`DeviceFunction`, and Mojo's own
compiled kernel bytes reloaded through the public `newLibraryWithData:` path lose their buffer
writes to Metal's own dead-code elimination. That addendum's numbers are unchanged by this one; the
16.45 ms submission floor remains fully present under everything measured below, and this section
rebases onto it (`#504` is in this branch's history) rather than duplicating it.

### What changed

- **Vectorized GEMV loads.** All four GEMV-shaped kernels in `residentk.kernels`
  (`_norm_gemv_kernel`, `_gemv_accum_kernel`, `_norm_gemv2_swiglu_kernel`, `_lmhead_argmax_kernel`)
  replaced their scalar, stride-32 inner loop with 4-wide vector loads on both operands (a single
  128-bit instruction per step instead of four scalar ones), plus a scalar tail for the
  non-128-aligned remainder. `_TG` (threadgroup occupancy) was re-measured at 256/512/1024 and left
  at 256 — no measurable difference either way.
- **Additive fp16 weight storage.** A parallel `_ResidentQwen3F16` session plus `_f16` twins of the
  same four kernels resident the weight matrices (and the tied embed/lm_head table) as Float16
  instead of Float32 (2.50 GB -> 1.31 GB measured), widened to Float32 with `.cast[DType.float32]()`
  immediately on load and accumulated in Float32 throughout — mixed precision, not accumulate-in-
  half. `_ResidentQwen3` (Float32) is untouched; this is a third, fully additive arm, exactly like
  the fp32-resident arm was additive over the CPU one. The fp16 kernels' vector width (`_VEC_H`) was
  measured, not assumed: an 8-wide load (byte-matching Float32's 128-bit width) made the arm
  *slower*, because MSL has no native 8-wide `half` vector type; `half4` (a real MSL type) is what
  landed.

### Correctness first, again

Checked position-by-position against a `transformers`-CPU reference regenerated fresh in this
session (`reference_generate.py`, same checkpoint), and cross-checked against each other and against
both real opponents:

| Arm | tokens matching the reference | max per-step logit delta |
|---|---|---|
| Algenta resident GPU, vectorized (float32) | **16 / 16** | **3.81e-06** |
| Algenta resident GPU, fp16 weights | **16 / 16** | **5.72e-06** |
| Algenta CPU (float64, FastGEMV) | **16 / 16** | **3.81e-06** |

`[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]` —
`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."`, identical across all
three Algenta arms. Both real opponents emit the same text in every one of the six rounds below:
llama.cpp (`-ngl 0` and `-ngl 99`) `' Paris. The capital of Germany is Berlin. The capital of Italy
is Rome.'`, mlx-lm `'Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'` (same
leading-space detokenizer difference noted in earlier sections — same token content). **No arm
diverged in any round.** Six implementations across three precisions, one sequence.

The `mojo/tests/libs/test_residentk_session.mojo` golden-vector suite gained a matching fp16 arm:
**33/33 passing**, including the non-128-aligned small model (`D_MODEL=32`, `D_FF=40`) that exercises
the vectorized tail path in both dtypes.

### The numbers

Decode-only tokens/sec, six interleaved rounds (`n = 6` per arm), same prompt/length/methodology as
every section above. Machine: Apple M4 Max, shared dev box; 1-minute load average **9.3 – 10.2**
across the session, with one long-running, unrelated `mojo run` process pegging a full core for the
entire session (present, unkillable from this workflow's permissions, for the whole session) —
noted because it is exactly the kind of shared-core competition that widened llama.cpp CPU's spread
in the four-way race above, and does the same here.

| Arm | Precision | Compute | Range | Median | Median vs Algenta's best |
|---|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV) | float64 | CPU, 12 perf cores | 5.16 – 8.18 | **7.45** | 0.30x |
| Algenta resident GPU, vectorized GEMV | float32 | Apple GPU (Metal, MAX) | 21.65 – 23.51 | **23.37** | 0.94x |
| **Algenta resident GPU, vectorized GEMV + fp16 weights** | mixed (fp16 storage, fp32 compute) | Apple GPU (Metal, MAX) | 21.96 – 25.44 | **24.88** | 1x (Algenta's best) |
| llama.cpp `-ngl 0` | F16 | CPU (ggml) | 18.56 – 56.61 | **27.83** | **1.12x faster** |
| llama.cpp `-ngl 99` | F16 | Apple GPU (Metal) | 239.12 – 258.62 | **256.52** | **10.31x faster** |
| mlx-lm | bf16 | Apple GPU (Metal) | 307.38 – 318.46 | **311.17** | **12.51x faster** |

Per-round values, in round order:

```
algenta_cpu      7.59   7.49   7.42   7.32   8.18   5.16
algenta_gpu32   23.46  23.44  23.30  23.51  21.65  23.14
algenta_gpu16   23.99  24.88  24.87  25.44  25.07  21.96
llama_cpp       33.29  23.93  21.72  56.61  18.56  31.74
llama_gpu      240.74 257.33 255.71 239.12 258.62 257.38
mlx            318.46 311.53 308.67 307.38 310.80 313.88
```

Against the four-way race's baseline (Algenta's best, 20.28 tok/s, same prompt/checkpoint/machine):
the vectorized-fp32 arm measures **23.37** here (+15.3%), and the vectorized-fp32-plus-fp16 arm
measures **24.88** (+22.7%) — both real, reproducible gains, and both still short of even the noisy
llama.cpp CPU arm's median, let alone its GPU arm or mlx-lm. llama.cpp CPU's spread this session
(18.56 – 56.61, wider than the four-way race's 27.23 – 46.36) reflects the same core competing with
the leaked process noted above; even so, its slowest round (18.56) sits inside Algenta's own range
rather than clearly above it, so the CPU comparison should be read as "roughly even, noisily," not
as a clean loss or win either way. The two GPU opponents are unaffected by CPU contention and are
not close: llama.cpp GPU is **10.31x** Algenta's best and mlx-lm is **12.51x**.

### Publication decision: no gitbook page

The standing rule is an outright win against the field's best real installed opponent, measured on
this machine — mlx-lm, median **311.17 tok/s** today. Algenta's best arm today is **24.88 tok/s**,
a **12.51x** loss. **No page ships, and none is drafted.** The kernel-efficiency work is real and
reproducible (+15.3% from vectorization alone, another +6.5% from fp16 weights on top of that,
+22.7% combined vs. the four-way race's baseline) — reported here as exactly that, an incremental
win over the prior Algenta baseline, not a win over the field.

### Where the remaining gap is, updated

The four-way race estimated that closing the kernel term to the bandwidth bound alone (leaving
everything else unchanged) would reach **~44 tok/s**. This session's actual vectorization result
(23.37, then 24.88 with fp16 added) is well short of that estimate, meaning the GEMV kernels are
still measurably above the bandwidth bound after vectorization, not at it — a per-kernel profile
(rather than an end-to-end token rate) is the next diagnostic step, not assumed here. Even the
optimistic **~44 tok/s** estimate would only have passed llama.cpp CPU (27.83 median this session) —
it would not have touched llama.cpp GPU (256.52) or mlx-lm (311.17), both dominated by Metal-native,
batched, async-submission execution this toolchain's public API does not currently expose (see the
raw-Metal addendum above: confirmed no-go, not merely unattempted). The submission ceiling this
design cannot get under with today's public APIs is **60.79 tok/s** — below mlx-lm's number by
**5.2x** even before any kernel time is counted. Outright winning stays a three-part requirement —
near-bandwidth kernels, a submission path this toolchain does not yet expose, and fp16/bf16 weights
(now landed) — and one of those three parts is now confirmed blocked pending upstream Mojo/MAX
support (documented in the raw-Metal addendum above), not merely pending more engineering time here.

### Reproduction

```bash
cd /Users/angel/Developer/decision-engine/mojo_env
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I <worktree>/mojo/engine <worktree>/benchmarks/llm_smoke/qwen3_generate_metal.mojo -o /tmp/race5_gpu32
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I <worktree>/mojo/engine <worktree>/benchmarks/llm_smoke/qwen3_generate_metal_fp16.mojo -o /tmp/race5_gpu16
pixi run mojo build -I <worktree>/mojo/engine \
    <worktree>/benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/race5_cpu

# one round = every arm once, back to back (from benchmarks/llm_smoke/)
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race5_gpu32
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race5_gpu16
/tmp/race5_cpu
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0  --runs 1
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99 --runs 1
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base

# token agreement, against a reference regenerated in the same session
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_race5
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_metal/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_race5/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_metal_fp16/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_race5/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_llmfwd/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_race5/reference_generated.json
```

## Batched-dispatch + full-stack addendum (2026-08-02, later still): the submission ceiling falls AND combines with the landed kernel-efficiency/fp16 track — gap closes from >12x to ~1.25x-1.54x, still losing

Two things happened in this session, in order, and this section reports both combined into one
real measurement — not because they were planned together, but because the second landed on
`origin/main` mid-session and the task standard here is to combine whatever is real and available,
not to under-report.

**First: the raw-Metal dispatch addendum's "no-go" (immediately above) was a misdiagnosis, not a
real limitation.** Its probe bound a Mojo-compiled kernel's pointer argument with
`setBuffer:offset:atIndex:` — the wrong Metal call for Mojo's Metal ABI. Mojo's ABI passes a pointer
argument as the *value* of the target buffer's own 64-bit GPU device address (`MTLBuffer.gpuAddress`)
in its declared slot, bound via `setBytes:length:atIndex:`, with `useResource:` declaring residency
separately — proved bit-exact against MAX's own `enqueue_function` on a real 5-arg GEMV shape in a
follow-up investigation (`.worktrees/metalair`). With the correct recipe, a new package,
`mojo/engine/metaldispatch/` (status range 620-639), collapses `residentk`'s whole 171-dispatch
per-token sequence into ONE C-shim call (`benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m`,
ordinary Objective-C, not the one-signature-per-name `objc_msgSend` shim the earlier probe needed):
one command buffer, one encoder, all 171 dispatches, one commit, one wait, zero Mojo↔C crossings
inside the loop. `residentk.kernels`' eight (now thirteen, with the fp16 twins) compiled functions
are called directly, never rewritten; `residentk`/`gemm`/`accel` are byte-identical to `origin/main`
(freeze-verified).

**Second: the sibling kernel-efficiency + fp16 track landed as `#505` while this was being built.**
`residentk.kernels`' four GEMV-shaped kernels gained vectorized (float4) loads, and a fp16 weight-
storage twin (`_ResidentQwen3F16`, halving 2.50 GB of resident weights to 1.31 GB) was added
alongside the untouched Float32 arm. Because `metaldispatch` calls those SAME kernel names, the
vectorized loads apply to the batched-shim path automatically, from rebasing alone, with zero code
changes. The fp16 arm did not: `metaldispatch`'s pipeline discovery classifies a compiled kernel by
reading its Metal function name back from the shim, and Mojo's Metal AIR name for both a role's
Float32 and Float16 kernel truncates to an IDENTICAL visible prefix before an opaque per-
specialization hash — measured directly while combining the two (`residentk_kernels__norm_gemv_k
6A6A6A6A_<hash>` for both, different hashes, no way to tell them apart by text). Rather than build a
runtime discrimination probe, the fix is architectural: `_MBQwen3F16` is a new struct that compiles
ONLY the fp16-role kernels (never their Float32 counterparts), so its own binary
(`qwen3_generate_batch_f16.mojo`) embeds exactly one pipeline per role — the same invariant
`_MBQwen3`'s binary already relied on — and the existing name-substring classifier needs no changes.
`qk_rope`/`sdpa`/`argmax_reduce` have no fp16 twin and are shared, harmlessly, by both binaries.

### Correctness first — six arms, six rounds, sixteen tokens each

All four Algenta arms (CPU; resident-GPU/MAX vectorized-f32; batched-shim vectorized-f32; batched-
shim vectorized-f32+fp16) were checked position-by-position against a `transformers`-CPU reference
regenerated fresh this session (`reference_generate.py`, same checkpoint):

| Arm | tokens matching reference | max per-step logit delta |
|---|---|---|
| Algenta CPU (float64, FastGEMV) | **16 / 16** | 3.19e-06 |
| Algenta resident GPU, MAX, vectorized (float32) | **16 / 16** | 3.81e-06 |
| Algenta batched-shim GPU, vectorized (float32) | **16 / 16** | 3.81e-06 |
| **Algenta batched-shim GPU, vectorized + fp16 (full stack)** | **16 / 16** | 5.72e-06 |

`[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]` —
`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."` — identical across all
four Algenta arms. Both real opponents emitted the identical text in **every one of the six rounds
below**: llama.cpp `' Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'`,
mlx-lm `'Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'` (same leading-
space detokenizer difference noted throughout this document — same token content). **No arm
diverged in any round.**

The new fp16 golden-vector suite, `mojo/tests/libs/test_metaldispatch_session_f16.mojo` (a separate
file/binary from the Float32 one, per the pipeline-collision finding above): **8/8**, matching the
same small-model reference `test_metaldispatch_session.mojo`'s Float32 suite uses (frozen-CPU-kernel
token 11, fp16 logit delta 1.83e-05 against a Float16-epsilon-scaled bound of 1.26).
`test_metaldispatch_session.mojo` itself: unchanged, still 3/3 default-build / 11/11 real-GPU-build.

### The numbers

Same checkpoint, prompt, 16 greedy tokens, decode-only tok/s — six rounds, every arm run once per
round, interleaved in this fixed order within each round: Algenta CPU → Algenta resident-GPU/MAX
(vectorized) → Algenta batched-shim/vectorized → **Algenta batched-shim/vectorized+fp16 (full
stack)** → llama.cpp CPU → llama.cpp GPU → mlx-lm. Apple M4 Max, shared dev box; 1-minute load
average 9.9 – 22.3 across the six rounds (this session ran hotter than most in this document — one
mlx-lm round below is a visible outlier as a result, called out rather than hidden).

| Arm | Precision | Compute | Range | Median | vs Algenta's best |
|---|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV) | float64 | CPU, 12 perf cores | 5.66 – 7.35 | 6.94 | 0.034x |
| Algenta resident GPU, MAX, vectorized | float32 | Apple GPU (Metal, MAX) | 21.26 – 23.67 | 22.86 | 0.111x |
| Algenta batched-shim GPU, vectorized | float32 | Apple GPU (Metal, raw shim) | 129.01 – 138.78 | 136.08 | 0.660x |
| **Algenta batched-shim GPU, vectorized + fp16 (full stack)** | mixed (fp16 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 195.16 – 209.18 | **206.38** | **1x (best)** |
| llama.cpp `-ngl 0` | F16 | CPU (ggml) | 8.92 – 36.82 | 28.82 | 7.16x faster |
| llama.cpp `-ngl 99` | F16 | Apple GPU (Metal) | 250.51 – 261.03 | 256.88 | **1.25x faster** |
| mlx-lm | bf16 | Apple GPU (Metal) | 69.49 – 319.86 | **317.52** | **1.54x faster** |

Per-round values, in round order (the mlx-lm outlier is round 1, 69.488 — every other round for
every arm is tight; reported, not discarded):

```
algenta_cpu        6.69   5.66   7.35   7.24   6.98   6.90
algenta_gpu_max   21.26  23.67  22.78  22.94  21.84  23.14
algenta_gpu_batch 136.30 138.19 138.78 134.79 129.01 135.86
algenta_gpu_full  201.79 205.45 209.09 209.18 195.16 207.32
llama_cpp_cpu     33.40  14.49  33.03  24.61   8.92  36.82
llama_cpp_gpu    258.23 259.72 255.05 261.03 255.53 250.51
mlx_lm            69.49 319.08 315.97 319.12 319.86 306.46
```

Two ratios, computed from the medians:
- **Batched dispatch alone** (vectorized-f32, shim vs MAX): 136.08 / 22.86 = **5.96x** — the
  dispatch-mechanism win, isolated from the kernel-efficiency track, holds up after rebasing onto
  `#505` (this document's earlier batched-dispatch-only measurement, before the rebase, found
  4.7x-5.9x on an f32-only, pre-vectorization kernel; the ratio is consistent because vectorization
  speeds up BOTH the MAX and the shim arm's kernels equally — it changes the numerator and
  denominator's absolute values, not their ratio, since both dispatch the identical kernel code).
- **fp16 on top of batched dispatch**: 206.38 / 136.08 = **1.52x** — smaller in relative terms than
  the dispatch-mechanism win, but this is the FIRST measurement of fp16's effect where kernel time is
  the dominant (not minority) cost of the token, which is exactly the regime fp16's weight-bandwidth
  halving should matter most in — and it does: fp16 gained +6.5% on the old MAX-submission design
  (where kernel time was a minority term) and +52% here (where kernel time, after batching removes
  submission-dominance, is nearly the whole story).

**Combined, the full stack reaches 206.38 tok/s — 10.2x over the `#503` four-way race's original
Algenta-best baseline (20.28 tok/s), and beats llama.cpp CPU outright (7.16x) for the first time in
this document.** It still loses to both GPU opponents: llama.cpp GPU by **1.25x**, mlx-lm by
**1.54x** — down from the pre-combination gaps of 12.68x and 15.56x in the original four-way race.

### Where the remaining gap is — measured, not guessed

At the median 206.38 tok/s, a token costs 4.845 ms. `submit_floor_batch.mojo` (same no-op-shaped-
dispatch isolation the four-way race used for MAX, run fresh in this session, median of 30, three
repeated invocations for stability: 8.68-8.86 us/dispatch, tight) puts the pure submission cost at
**~1.49 ms/token (30.8% of the token)** — a submission-alone ceiling of ~672 tok/s. (This is lower
than the 2.86 ms this document's earlier, pre-`#505` batched-dispatch measurement found for the
identical shim and dispatch count; the difference is run-to-run host-load variance on this shared
box, the same effect visible in llama.cpp CPU's spread every section of this document reports — not
a change in the design.) The remaining **~3.36 ms/token (69.2%)** is kernel-execution time on the
fp16-narrowed weights, and it is now close to a coherent physical floor: 1.31 GB of resident Float16
weights at this host's previously-measured 411 GB/s streaming ceiling is a 3.19 ms bandwidth floor —
the measured 3.36 ms residual is **5.3% above** that floor, i.e. the vectorized fp16 kernels are
close to bandwidth-bound, not the dominant slack anymore.

That reframes the remaining gap as mostly a submission-mechanism question, not a kernel-efficiency
one: a token with the measured ~3.36 ms kernel time and ZERO submission overhead would run at
**~298 tok/s** — enough to clear llama.cpp GPU (256.88, by 1.16x) but STILL short of mlx-lm (317.52,
by 1.06x) even in that idealized case. mlx-lm's own token time is 3.15 ms — close to Algenta's
kernel-only residual (3.36 ms) even before Algenta's own submission cost is added back in, which is
the real reason this design, as built, cannot cross mlx-lm today: this toolchain's per-command-
buffer submission floor (~1.49 ms for 171 dispatches, itself already collapsed 5.9x from MAX's own
16.45 ms) is now bigger than the remaining kernel-efficiency headroom. Closing it further needs
fusing MORE of the 171 dispatches into fewer, larger kernels (fewer dispatches per token, not a
faster per-dispatch encoder call — not attempted in this session) or a lower per-dispatch encoder
cost than this toolchain's public API exposes today.

### Publication decision: no gitbook page

Standing rule: an outright win against the field's best real installed opponent, mlx-lm, measured
today (317.52 tok/s median), and also against llama.cpp's best (256.88 tok/s median, GPU). Algenta's
best arm — the full combined stack, 206.38 tok/s — loses to both: **1.25x short of llama.cpp GPU,
1.54x short of mlx-lm.** No gitbook page ships, and none is drafted. Everything reported above is a
real, reproducible, three-way-combined engineering result (raw-Metal dispatch correction + vectorized
kernels + fp16 weights, the first time all three have been measured together) — reported as exactly
that, a 10.2x cumulative improvement over the session's starting baseline, not as a field win.

### Gates, rebased onto `origin/main` tip (`4b6d2195`, `#505`), all rerun

- `make inventory-refresh` (zero diff beyond the expected fp16-session addition, no new PUBLIC
  contract surface) + `inventory-check`: clean
- Capability manifest gate: clean, no new undeclared kernels
- `tests/generate_mojo_tests.py --check`: clean (194 hand-written suites protected — one more than
  before this session, `test_metaldispatch_session_f16.mojo` — 466 generated fresh)
- Freeze gate / `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean —
  `accel/`, `gemm/`, `residentk/` byte-identical to `origin/main`; `metaldispatch/` is the only
  package touched, already in the freeze alternation
- `python3 -m scripts.reliability_guards` (all guards): no new violations (pre-existing baselined
  debt only)
- `mojo/tests/libs/test_metaldispatch_session.mojo` (Float32 arm): 3/3 default build, 11/11 real-GPU
  build — unchanged, reverified after the fp16 addition to confirm no regression
- `mojo/tests/libs/test_metaldispatch_session_f16.mojo` (new, fp16 arm): 1/1 default build, 8/8
  real-GPU build
- `mojo/tests/libs/test_metaldispatch_contract.mojo`: 2/2, no device/shim needed
- `pnpm check`: rerun on the rebased tree; same two local-only, CI-invisible pre-existing failures
  this chain's earlier sections already documented and left out of scope ("Mojo libraries A-Z" stale
  `time` import allowlist predating this chain; "Live TypeScript Runtime integration" a no-op skip
  under CI's `ALGENTA_SKIP_MOJO_RUNTIME=1`, reproduces identically on a clean `origin/main` checkout)

### Reproduction

```bash
# build the shim object once
cd /Users/angel/Developer/decision-engine/.worktrees/metalbatch
clang -c -fobjc-arc -O2 benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o

# build all four Algenta arms (rebased onto #505's vectorized/fp16 residentk.kernels)
cd mojo_env
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build \
    -I../mojo/engine ../benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/qwen3_generate_metal.mojo -o /tmp/race_gpu_max
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch.mojo \
    -o /tmp/qwen3_batch -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo \
    -o /tmp/qwen3_batch_f16 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation

# one round = every arm once, back to back (from benchmarks/llm_smoke/)
/tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_max
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_batch
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_batch_f16
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0  --runs 1
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99 --runs 1
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base

# token agreement, against a reference regenerated in the same session
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_metalbatch
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_batch_f16/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_metalbatch/reference_generated.json

# the submission-only floor this addendum's breakdown depends on
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/submit_floor_batch.mojo \
    -o /tmp/submit_floor_batch -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch
```

## Int8-weight addendum (2026-08-02, later still): per-channel int8 quantization narrows the gap further — still losing to both opponents

Same day, same machine, next lever down the "narrow the bytes streamed per token" path the fp16
addendum opened: per-output-row (per-channel) symmetric int8 weights (`scale[row] = max(|row|) /
127`, an all-zero row forced to `scale = 1.0`) on top of the identical batched-shim dispatch plan
(171 dispatches/token, unchanged), dequantized in-register (`char4` load → Float32 cast → per-row
scale multiply → Float32 accumulate) inside the same vectorized GEMV reduction loop the fp16 arm
uses. Six full arms raced together this time — Algenta CPU, Algenta batched-shim fp16 (today's
prior baseline), **Algenta batched-shim int8 (new)**, llama.cpp CPU, llama.cpp GPU, mlx-lm — six
interleaved rounds, back to back. 1-minute load average 9.9 – 11.9 across the six rounds (calmer
than the fp16 addendum's session).

### Correctness first — re-verified on this exact measurement run, not carried over from Quantize

All three Algenta arms produce the identical greedy token sequence, checked position-by-position
against a `transformers`-CPU reference regenerated fresh in this session
(`reference_generate.py`, same checkpoint, written to
`/tmp/bb/qwen3_ckpt/reference_generate_i8race/`):

| Arm | tokens matching reference | max per-step logit delta |
|---|---|---|
| Algenta CPU (float64, FastGEMV) | **16 / 16** | 1.02e-05 |
| Algenta batched-shim GPU, fp16 | **16 / 16** | 9.54e-06 |
| **Algenta batched-shim GPU, int8 (new)** | **16 / 16** | 2.36e-01 |

`[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]` —
`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."` — identical across all
three Algenta arms, on the specific binaries raced below (rebuilt fresh for this session, not the
Quantize phase's binaries). The int8 arm's per-step logit delta is visibly larger than fp16's (as
expected — an 8-bit per-row quant step is a coarser representation than a 16-bit float), but it is
the same order of magnitude the Quantize phase's own controlled-model and real-model checks found,
and every one of the 16 greedy argmax decisions still lands on the reference token: quantization
noise here is well inside the logit-gap-to-runner-up margin at every step, not close to flipping a
decision. Both real opponents emitted the identical text in every one of the six rounds below:
llama.cpp `' Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'`, mlx-lm
`'Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'` (same leading-space
detokenizer difference this document notes throughout — same token content). **No arm diverged in
any round.**

`mojo/tests/libs/test_residentk_session.mojo`: 39/39 (int8 section appended, all pre-existing fp16
and Float32 cases unchanged). `mojo/tests/libs/test_metaldispatch_session_i8.mojo` (new): 1/1
default build, 8/8 real-GPU build. `mojo/tests/libs/test_metaldispatch_session.mojo` (Float32 arm):
11/11 real-GPU build, unchanged. `mojo/tests/libs/test_metaldispatch_session_f16.mojo`: 8/8,
unchanged. `mojo/tests/libs/test_metaldispatch_contract.mojo`: 2/2, unchanged.

### The numbers

Same checkpoint, prompt, 16 greedy tokens, decode-only tok/s — six rounds, every arm run once per
round, interleaved in this fixed order within each round: Algenta CPU → Algenta batched-shim fp16
→ **Algenta batched-shim int8** → llama.cpp CPU → llama.cpp GPU → mlx-lm.

| Arm | Precision | Compute | Range | Median | vs Algenta's best |
|---|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV) | float64 | CPU, 12 perf cores | 7.17 – 8.10 | 7.44 | 0.031x |
| Algenta batched-shim GPU, vectorized + fp16 | mixed (fp16 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 199.71 – 209.63 | 206.86 | 0.855x |
| **Algenta batched-shim GPU, per-channel int8 (new)** | mixed (int8 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 231.01 – 245.30 | **241.83** | **1x (best)** |
| llama.cpp `-ngl 0` | F16 | CPU (ggml) | 30.67 – 53.34 | 39.90 | 6.06x faster |
| llama.cpp `-ngl 99` | F16 | Apple GPU (Metal) | 240.76 – 261.52 | 258.53 | **1.07x faster** |
| mlx-lm | bf16 | Apple GPU (Metal) | 291.99 – 317.32 | **309.83** | **1.28x faster** |

Per-round values, in round order:

```
algenta_cpu        8.10   7.17   7.48   7.41   7.31   7.49
algenta_gpu_f16  207.27 206.44 205.77 208.99 209.63 199.71
algenta_gpu_i8   242.68 239.18 240.98 231.01 244.90 245.30
llama_cpp_cpu     30.67  37.35  42.44  53.34  45.82  31.83
llama_cpp_gpu    258.32 259.13 257.40 258.74 261.52 240.76
mlx_lm           291.99 302.07 315.64 304.02 317.32 317.05
```

**int8 over fp16, on this measurement run**: 241.83 / 206.86 = **1.169x (+16.9%)** — consistent
with the Quantize phase's own isolated figure (+16.9%/+18.4% depending on which fp16 baseline it
compared against). Narrowing the weight bytes streamed per dispatch a second time (fp16 → int8,
half the bytes again) buys real, repeatable throughput, same direction and a similar magnitude to
fp16's own win over float32 batched dispatch.

**int8 vs. the field, on this measurement run**: llama.cpp GPU (258.53) beats Algenta int8 by
**1.07x**; mlx-lm (309.83) beats Algenta int8 by **1.28x**. Both gaps are narrower than fp16's
(1.25x and 1.50x on this same run's fp16 numbers) — int8 closes real ground — but neither closes to
parity or a crossover. **Algenta's best arm today, int8, still loses to both real opponents.**

### Where the remaining gap is — measured, not guessed

At the median 241.83 tok/s, a token costs 4.135 ms. `submit_floor_batch.mojo` (same no-op-shaped-
dispatch isolation every prior addendum in this document uses, run fresh in this session, median of
30, three repeated invocations: 8.80-8.84 us/dispatch, tight) puts the pure submission cost at
**~1.51 ms/token** (unchanged from the fp16 addendum — the dispatch count, 171/token, has not
changed; int8 changes bytes moved per dispatch, not dispatch count). The remaining **~2.63
ms/token** is kernel-execution time on the int8-narrowed weights. This host's resident int8
footprint is ~0.716 GB (0.596 GB int8 weights + 0.002 GB per-row Float32 scales + 0.118 GB
Float32 norm-gains/KV-cache, self-reported by `qwen3_generate_batch_i8.mojo` at session-open); at
this host's previously-measured 411 GB/s streaming ceiling, that is a 1.742 ms naive bandwidth
floor. The measured 2.63 ms kernel residual is **~51% above** that floor — a materially worse ratio
than fp16's own 4.4% (this run's fp16 numbers: 3.33 ms residual against fp16's 1.31 GB / 411 GB/s =
3.19 ms floor). That is the same diagnosis the Quantize phase's report gave, reproduced independently
here: `char4`/`half4`/`float4` all advance the same 128 elements per SIMD step on this toolchain (MSL's
widest native vector for every scalar type at play here is width-4), so int8 shrinks bytes moved per
instruction without shrinking instruction count — below some byte-width, fixed per-instruction
overhead (not bytes moved) starts to dominate, which is exactly why int8's bandwidth-floor ratio is
worse than fp16's even though int8 moves fewer total bytes.

A token with the measured ~2.63 ms int8 kernel time and ZERO submission overhead would run at
**~380 tok/s** — clearing mlx-lm's 309.83 median by a comfortable margin. That reframes today's gap,
as it did for fp16: not a kernel-efficiency ceiling but a submission-mechanism one, now the binding
constraint for a SECOND precision tier in a row. Closing it needs the same lever the fp16 addendum
named and did not attempt: fusing more of the 171 dispatches into fewer, larger kernels per token, or
a lower per-dispatch encoder cost than this toolchain's public API exposes today. Int8 does not
change that diagnosis; it sharpens it, since int8's kernel-only residual is now smaller than its own
submission floor's neighborhood (2.63 ms kernel vs. 1.51 ms submission — submission is 36.5% of the
int8 token, up from 30.8% for fp16), meaning submission cost is now a LARGER fraction of the token
for int8 than for fp16, even though it is the same absolute 1.51 ms in both cases.

### Publication decision: no gitbook page

Standing rule: an outright win against the field's best real installed opponent, mlx-lm, measured
today (309.83 tok/s median on this run), and also against llama.cpp's best (258.53 tok/s median,
GPU). Algenta's best arm — batched-shim int8, 241.83 tok/s — loses to both: **1.07x short of
llama.cpp GPU, 1.28x short of mlx-lm.** No gitbook page ships, and none is drafted. Int8
quantization is a real, verified, +16.9%-over-fp16 engineering result — the third precision tier
raced in this document (float32 → fp16 → int8), each one narrowing the gap to the field
(15.56x → 1.54x → 1.28x against mlx-lm across the three tiers) without ever crossing it — and it is
reported as exactly that, not as a field win.

### Gates, all rerun on this worktree (already at `origin/main` tip `e92065cf`/`#506` — no rebase needed)

- `git fetch origin main` then `git diff --stat e92065cf -- mojo/engine/`: only `residentk/` and
  `metaldispatch/` touched, matching the freeze alternation
- `make inventory-refresh`: zero diff (no new PUBLIC contract surface — every new function is
  `_`-prefixed private) + `make inventory-check`: clean
- Capability manifest gate: clean, no new undeclared kernels (122/655 modules fully declared, 595
  functions still undeclared against the pre-existing 595 ceiling — unchanged)
- `tests/generate_mojo_tests.py --check`: clean (195 hand-written suites protected, 466 generated
  fresh)
- Freeze gate / `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean
- `python3 -m scripts.reliability_guards` (all guards): no new violations (`boundary_imports`,
  `egress_sdk_clients`, `raw_egress` — same pre-existing baselined debt this document's prior
  addenda already carry, unchanged counts)
- `mojo/tests/libs/test_residentk_session.mojo`: 39/39
- `mojo/tests/libs/test_metaldispatch_session_i8.mojo` (new): 1/1 default build, 8/8 real-GPU build
- `mojo/tests/libs/test_metaldispatch_session.mojo` (Float32 arm): 11/11 real-GPU build — unchanged,
  reverified after the int8 addition to confirm no regression
- `mojo/tests/libs/test_metaldispatch_session_f16.mojo`: 8/8 real-GPU build — unchanged
- `mojo/tests/libs/test_metaldispatch_contract.mojo`: 2/2, unchanged
- `pnpm check`: rerun on this worktree; two pre-existing, CI-invisible local failures, neither
  touched by this change (verified by reproducing both identically on a clean `origin/main`
  checkout): a live-network `Live S3 source registration` connectivity flake (`go_live_verify.py`,
  which CI itself skips via `DE_SKIP_GO_LIVE_VERIFY=1` — rerunning with that same flag set locally
  clears it), and a local-environment `GET /mcp/sse` returning 401 instead of the
  `test_openapi.py` integration check's expected `{200, 204, 503}` (an auth-posture mismatch
  between this dev machine's local server config and the check's assumption, present on `main`
  itself, unrelated to residentk/metaldispatch)

### Reproduction

```bash
# build the shim object once
cd /private/tmp/int8quant/benchmarks/llm_smoke
clang -c -fobjc-arc -O2 metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o

cd ../../mojo_env
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build \
    -I../mojo/engine ../benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo \
    -o /tmp/race_gpu_f16 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8.mojo \
    -o /tmp/race_gpu_i8 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation

# one round = every arm once, back to back (from benchmarks/llm_smoke/)
/tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_f16
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_i8
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0  --runs 1
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99 --runs 1
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base

# token agreement, against a reference regenerated in the same session
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_i8race
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_batch_i8/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_i8race/reference_generated.json

# the submission-only floor this addendum's breakdown depends on (unchanged dispatch count from
# the fp16 addendum — int8 does not change dispatches/token)
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/submit_floor_batch.mojo \
    -o /tmp/submit_floor_batch -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch
```

## Dispatch-fusion + packed-int8-load addendum (2026-08-02, later still): both attacked, both confirmed dead ends on this toolchain — 171 stands, char4 stands

The int8 addendum immediately above named two real levers left in a 241.83 tok/s token: the 171-
dispatch submission floor (36.5% of the token, 1.51 ms, unchanged since it does not depend on
weight dtype) and the int8 kernel-execution residual sitting ~51% above its own bandwidth floor
(2.63 ms, worse than fp16's 4.4% because `char4`/`half4`/`float4` all advance the same 128 elements
per SIMD step on this toolchain — narrower dtypes shrink bytes moved without shrinking instruction
count). This project attacked both directly, in a fresh worktree off `origin/main`'s tip
(`f1a99dfb`, `#507`), branch `feat/residentk-dispatch-fusion`. **Both are confirmed dead ends for
this toolchain, not merely unattempted — and unlike the raw-Metal-dispatch addendum's "no-go," this
one required no new correctness-risking code in `residentk`/`metaldispatch` at all: both questions
were answered without changing a single frozen or non-frozen production kernel.**

### Task 1 — further dispatch fusion: every fusion the task asked about is already landed; the rest is a real hardware floor, cited from the code that already says so

Reading `residentk.session._ResidentQwen3I8.step` (and its Float32/Float16 twins — identical
dispatch plan, see each struct's own docstring) against the four fusion opportunities this project
was asked to check, one at a time:

- **RoPE folded into qnorm/knorm?** Already done. `_qk_rope_write_kernel` (`residentk/kernels.mojo`)
  is one dispatch that does q_norm, k_norm, RoPE on both, AND the in-place KV-cache slot write — its
  own docstring: *"Per-head rmsnorm on Q and K, RoPE on both, and the KV-cache slot write — all in
  one dispatch."*
- **Residual-add folded into the preceding projection's epilogue, for o_proj and down_proj?**
  Already done, for both. `_gemv_accum_kernel` (and its `_f16`/`_i8` twins) computes `y += W @ x` in
  the same launch that does the matmul — `session.mojo` calls it identically for `o_proj` (dispatch
  4) and `down_proj` (dispatch 6). Its own docstring: *"`+=` rather than `=` is the whole point...
  Splitting the add into its own elementwise dispatch would cost ~180 us of blocked host time for
  ~1 us of arithmetic."*
- **sdpa's mask folded into the sdpa kernel itself?** There is no separate mask dispatch to fold —
  `_sdpa_kernel`'s own docstring states the mask is not merely fused, it is provably unneeded:
  *"NO MASK IS APPLIED, and that is a claim rather than an omission. A single query at the true
  current position attends to every cached key by construction."*
- **Any elementwise step that is a separate dispatch for code-organization reasons only?** No —
  every dispatch boundary in the six-per-layer plan is a genuine cross-threadgroup data dependency:
  `rmsnorm` needs the FULL vector the previous projection produced, and that vector was written by
  many independent threadgroups (128 for `o_proj`/`down_proj` at this model's `d_model=1024`, more
  for `d_ff=3072`). Metal has no grid-wide barrier, so completing that dependency needs a real
  kernel boundary. This is not this project's own conclusion reached fresh — it is already the
  contract's own stated position, `residentk.contract.RESIDENT_DISPATCH_PER_LAYER`'s docstring,
  verified unchanged in this session: *"Six is a floor imposed by hardware, not a target someone
  stopped at... Fusing further needs a persistent kernel with a device-scope spin barrier —
  possible, high-risk, and deliberately not attempted here."*

So the answer to Task 1, honestly: **there was no further fusion available to attempt.** Every one
of the four opportunities this project was asked to check for was already shipped in #503-507, and
the one remaining lever (a persistent-kernel, device-scope-spin-barrier redesign that would let a
single dispatch survive across what are today six separate kernel launches) is explicitly flagged,
in the code this project was asked to read, as high-risk and deliberately not attempted — a
correctness posture this project agrees with rather than overrides: Metal's public API has no
grid-wide barrier primitive, so a spin-barrier implementation would be racing the GPU's own
scheduler with no language-level guarantee it terminates, which is a materially different risk
class than every other fusion in this file (all of which are ordinary same-kernel accumulation with
no new synchronization primitive). Reported as a negative result rather than forced into a
made-up "further fusion," per the standing instruction not to report a target number without a real
implementation behind it. Dispatch count stands at **171** (`28 * 6 + 3`), unchanged, and
`residentk_dispatch_budget(28)` continues to assert exactly that.

Reconfirming the submission floor this conclusion rests on, fresh on this worktree
(`submit_floor_batch.mojo`, no-op-shaped dispatches at the real 171-dispatch mix, median of 30):

```
   171 no-op-shaped dispatches / ONE shim call, median of 30 : 1507.0 us  == 8.81 us/dispatch
   implied per-token submission floor at this dispatch count: 1.507 ms
   implied tok/s ceiling from submission alone: 663.57
```

8.81 us/dispatch matches the int8 addendum's own 8.80-8.84 us/dispatch (and the fp16 addendum's
8.68-8.86 us/dispatch) within run-to-run noise — the batched-shim submission floor has not moved,
consistent with zero dispatch-count or dispatch-mechanism change this session. This also directly
answers the task's own question about ROI at this overhead level: 8.81 us/dispatch on the batched-
shim path is already ~11x below MAX's own 16.45 ms/171-dispatch floor's ~96 us/dispatch, so even if
the persistent-kernel redesign were attempted and succeeded perfectly at removing every layer
boundary (six dispatches/layer down to one, a 4.2x reduction in count), the submission-time saving
would be at most `(171-1-28-2) * 8.81us ≈ 1.23 ms` of a 4.135 ms token — real, but small next to the
correctness risk a grid-wide spin barrier introduces on a backend with no documented barrier
primitive, and it would still leave the int8 kernel-execution residual (2.63 ms) as the larger term.
The ROI calculus the task asked to check honestly is worse here than it would have been against
MAX's ~96 us/dispatch, exactly as the task anticipated it might be, and this project did not
attempt the redesign.

### Task 2 — packed int8 loads: three variants tried, all three measurably worse than the existing `char4` load

Built `benchmarks/llm_smoke/int8_pack_probe.mojo` — a new, additive, hand-written, unregistered
probe (same convention `decode_metal_probe.mojo` and the `metal_ffi_probe/` files already
established: not in `generate_mojo_tests.py`'s protected/generated suites, because this is a design
probe, not a golden-vector suite). It isolates the int8 GEMV reduction loop from
`residentk.kernels._norm_gemv_kernel_i8` (same threadgroup shape, same one-SIMD-group-per-output-
column structure, same tree reduction; the rmsnorm stage is removed so only the weight-load choice
varies) and runs four variants at real decode shapes:

- **A (baseline)**: `w.load[width=4]` — the existing `char4` vector load, `.cast[DType.float32]()`,
  multiply by the per-row scale.
- **B (`word32`)**: one explicit `UInt32` read via `w.bitcast[UInt32]()`, then a shift/mask/compare/
  subtract unpack to 4 signed lanes — the literal "single 32-bit-word read" the task asked to try.
- **B2 (`word32_bl`)**: the same explicit word read, but a branchless shift-based sign extension
  (`(Int32(raw) << 24) >> 24`) instead of the mask-compare-subtract in B — added to separate "the
  branch is what's slow" from "the extra unpack arithmetic itself is what's slow" before reporting
  B's result as the whole answer.
- **C (`word32x2`)**: two consecutive `UInt32` reads (8 bytes, 8 elements) unpacked together, 8
  elements/step instead of 4 — the "wider packed read" the task asked to check if B showed a win.

**Stage 1 correctness, checked before any timing number was trusted**: all four variants, on a
small (`k=136`, `n=24` — deliberately not a multiple of any vector stride, so every variant's
scalar-tail path is exercised) hand-quantized shape, against an independent pure-host scalar Int8
reference (no vectorization, no packed reads, a plain multiply-accumulate loop):

```
correctness[ char4 ]:     worst |delta| vs scalar host reference = 3.90e-06   OK
correctness[ word32 ]:    worst |delta| vs scalar host reference = 3.90e-06   OK
correctness[ word32_bl ]: worst |delta| vs scalar host reference = 3.90e-06   OK
correctness[ word32x2 ]:  worst |delta| vs scalar host reference = 4.32e-06   OK
```

All four agree with the independent scalar reference to float-rounding noise — the byte-order
assumption in the manual unpack (`shift = 0` is the lowest 8 bits, matching `char4`'s own element
0) is correct on this host, confirmed rather than assumed.

**Timing, median of 200, at three real decode-shaped GEMVs** (gate/up-like, down-proj-like, and an
lm_head-column-block-like shape), all run through `DeviceContext.enqueue_function_unchecked`
directly (not the batched shim — this measures kernel-side cost in isolation, with the ~150-170 us
MAX per-call submission floor as a roughly constant offset that cancels in the relative comparison
below, since `char4`'s own timing is flat across all three shapes and close to that floor, meaning
its own kernel time is small enough to be lost in the noise floor — the packed variants' growth
IS real, shape-proportional kernel time on top of that same floor):

| shape (k, n) | char4 (baseline) | word32 | word32_bl | word32x2 |
|---|---|---|---|---|
| 1024, 3072 (gate/up-like) | 166-167 us | 474-480 us (**+184-188%**) | 481 us (**+188%**) | 315-316 us (**+89-91%**) |
| 3072, 1024 (down-proj-like) | 166-168 us | 555-558 us (**+232-234%**) | 560 us (**+233%**) | 353-358 us (**+109-113%**) |
| 1024, 2048 (lm_head-block-like) | 154-159 us | 365-366 us (**+130-137%**) | 382 us (**+140%**) | 254-260 us (**+64-65%**) |

**Every packed variant is slower than the existing `char4` load, at every shape tried, by a wide
margin.** Removing the branch (B2 vs B) changed nothing measurable — B and B2 track each other
within noise at every shape, which rules out "the branch, specifically, is the cost" and points
instead at the unpack arithmetic itself (four to eight shift/mask/cast operations per step,
scalar, one lane at a time) versus what `char4`'s vector load gets essentially for free: a single
vectorized load instruction plus a fused `int8x4 -> float4` cast the compiler emits without being
asked. Doubling the elements read per step (C) helps relative to the single-word variants (B/B2)
but never closes even half the gap to baseline.

**Answer to the task's precise question**: Metal's compiler does NOT need an explicit packed-word
read to get a 32-bit-wide memory transaction out of `w.load[width=4]` on an `Int8` pointer — the
evidence is that the explicit form is 2-3x SLOWER, which is only possible if the load itself was
never the bottleneck `char4` was paying and the packed form's manual unpack is pure added cost on
top of an equivalent (or better-optimized) load. This is a real, measured, three-variant negative
result, reported as exactly that per the task's own standing allowance for a null result. **No
change was made to `_norm_gemv_kernel_i8`, `_gemv_accum_kernel_i8`, `_norm_gemv2_swiglu_kernel_i8`,
or `_lmhead_argmax_kernel_i8`** — they are byte-identical to `origin/main`'s `#506` versions, and
this measurement is the reason they were left alone rather than "additively" replaced with a slower
path.

### Staged correctness, reconfirmed fresh rather than assumed unchanged

Because neither task changed a production kernel or the dispatch plan, "the new design" bit-for-bit
IS `#506`'s own int8 arm. Reran the full stack anyway, fresh, on this worktree, rather than take
that on faith:

- **Single-token / small-model golden vectors** (Stage 1/2 territory): `test_residentk_session.mojo`
  **39/39**, `test_metaldispatch_session_i8.mojo` **8/8** (int8 logit agrees to `6.644e-3` within an
  int8 bound of `10.19` — this is the "~6.6e-3 logit delta band" this project's own task description
  named), `test_metaldispatch_session.mojo` (Float32) **11/11**,
  `test_metaldispatch_session_f16.mojo` **8/8**, `test_metaldispatch_contract.mojo` **2/2** — every
  count identical to `#506`'s own report, zero regressions.
- **Full 16-token greedy generation** (Stage 3): reran `qwen3_generate_batch_i8.mojo` against a
  `transformers`-CPU reference regenerated fresh in this session
  (`/tmp/bb/qwen3_ckpt/reference_generate_int8dispatch/`):

```
[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]
" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."
```

  **16/16 tokens match**, max per-step logit delta **2.36e-01** — identical to `#506`'s own figure,
  not a new number, because nothing that affects a logit changed. No divergence anywhere; nothing
  to stop and report per the task's Stage 3 instruction, because there is none.

### Measured decode-only tok/s this session

Five fresh runs of `qwen3_generate_batch_i8.mojo` (unchanged binary/kernels, this worktree, load
average 7.89-7.90, calmer than most sessions in this document):

```
236.42  237.31  241.96  243.41  244.83     median 241.96
```

Inside `#506`'s own range (231.01-245.30, median 241.83) — this is the SAME arm, remeasured, not an
improvement or a regression, exactly as expected when zero production code changed. Reported per the
task's own instruction to measure and state the real number rather than carry the old one forward
unchecked.

### Where the gap stands, unchanged, and why both remaining terms are now confirmed harder than "more engineering time"

`#506`'s own framing stands: a token with the measured ~2.63 ms int8 kernel time and zero submission
overhead would run at ~380 tok/s, clearing mlx-lm's 309.83 median — so the gap is a submission-
mechanism and kernel-instruction-density problem, not a bandwidth one. This session closes off both
of the concrete levers named for closing it:

1. **Fewer dispatches** — confirmed already at the fusion floor the hardware (no grid-wide Metal
   barrier) imposes; every fusion this project could check for is already shipped, and the one
   fusion left unshipped (persistent-kernel spin-barrier) is a different, higher-risk class of
   change than anything already in `residentk`, explicitly flagged as such in the code, and not
   attempted here on that basis.
2. **Cheaper per-element int8 unpacking** — confirmed the opposite of a win: the existing `char4`
   load is already faster than every explicit alternative tried, by 64%-234%.

Neither confirmed dead end is "more engineering time would fix it" — one is blocked on Metal's own
public API having no grid-wide barrier (the same class of gap the raw-Metal-dispatch addendum
already named for the submission mechanism itself), and the other is blocked on `char4` already
being at or near what this compiler can do with a 4-byte-aligned vector read, measured three ways.
The honest state of this design, after this session, is: 241.83-244.83 tok/s, 171 dispatches/token,
`char4` int8 loads, unchanged from `#506` — and the next lever, if one exists, is not on this list.

### Publication decision: no gitbook page

No number changed, so the standing verdict does not change: Algenta's best arm (int8, batched-shim,
~242 tok/s) still loses to llama.cpp GPU (~258.53 median, `#506`) and mlx-lm (~309.83 median,
`#506`) — not re-raced this session since neither lever attempted here altered any Algenta number
that would move that comparison. No page ships, and none is drafted. Both explored levers are a
real, reproducible, negative engineering result — confirmed dead ends on this toolchain, not
unattempted ones — and are reported as exactly that.

### Gates, on a fresh worktree off `origin/main` tip (`f1a99dfb`, `#507`)

- `git diff --stat origin/main -- mojo/engine/`: **completely empty** — not merely
  alternation-filtered-empty; zero files under `mojo/engine/` were touched, because neither task's
  conclusion required a production-kernel change. `git status --porcelain mojo/engine/`: empty.
  `git status --porcelain` (whole repo): one new untracked file,
  `benchmarks/llm_smoke/int8_pack_probe.mojo`.
- `make inventory-refresh` (unconditional): zero diff. `make inventory-check`: clean.
- `scripts/capability_manifest_gate.py` (run as part of `inventory-check`): clean — "122 of 655
  modules fully declared... 595 still undeclared (ceiling 595)", unchanged from `#506`.
- `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean.
- `python3 -m scripts.reliability_guards` (all guards): same three pre-existing baselined debt
  categories as `#506`, same counts — `boundary_imports` 11, `egress_sdk_clients` 11, `raw_egress`
  35 — no new violations.
- `tests/generate_mojo_tests.py --check`: clean — "195 hand-written suite(s) protected, 466
  generated suite(s) fresh", identical counts to `#506`.
- `mojo/tests/libs/test_residentk_session.mojo`: 39/39. `test_metaldispatch_session_i8.mojo`: 8/8.
  `test_metaldispatch_session.mojo`: 11/11. `test_metaldispatch_session_f16.mojo`: 8/8.
  `test_metaldispatch_contract.mojo`: 2/2. All identical counts to `#506`, rerun fresh rather than
  assumed.
- `int8_pack_probe.mojo` is a hand-written, intentionally-unregistered probe (see its own
  docstring), matching `decode_metal_probe.mojo`'s own precedent — not part of
  `generate_mojo_tests.py`'s protected/generated suites by design; its own in-file Stage-1
  correctness check (against an independent scalar host reference) is what this addendum's timing
  numbers depend on, and it passed before any timing number above was trusted.

### Reproduction

```bash
# the packed-load probe (Task 2's own numbers)
cd /Users/angel/Developer/decision-engine/mojo_env  # or this session's worktree's mojo_env
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/int8_pack_probe.mojo -o /tmp/int8_pack_probe
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/int8_pack_probe

# reconfirm the submission floor (Task 1's own number)
clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/submit_floor_batch.mojo \
    -o /tmp/submit_floor_batch -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch

# the unchanged int8 arm, remeasured, plus the reference cross-check
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8.mojo \
    -o /tmp/race_gpu_i8 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_i8
/tmp/bb/bin/python3 -P ../benchmarks/llm_smoke/reference_generate.py \
    --checkpoint /private/tmp/qwen3-0.6b-base --out /tmp/bb/qwen3_ckpt/reference_generate_int8dispatch
/tmp/bb/bin/python3 -P ../benchmarks/llm_smoke/verify_generation.py \
    /tmp/bb/qwen3_ckpt/mojo_generate_batch_i8/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_int8dispatch/reference_generated.json
```

## Final real race (2026-08-02, later still): every arm, six rounds, verdict for today

The dispatch-fusion/packed-int8-load addendum immediately above changed no production kernel — both
of its levers were confirmed dead ends. This section re-races the full field anyway, fresh, on the
same worktree (`/tmp/int8dispatch`, branch `feat/residentk-dispatch-fusion`, at `origin/main` tip
`f1a99dfb`/#507, no rebase needed — the tree was already current), rather than carry forward a
prior session's opponent numbers. Six full arms, six interleaved rounds, back to back, in the fixed
order Algenta CPU → Algenta batched-shim fp16 → Algenta batched-shim int8 → llama.cpp CPU →
llama.cpp GPU → mlx-lm. 1-minute load average 7.79 – 9.47 across the six rounds.

**"Algenta batched-GPU int8 + this phase's fusion/packing improvements" is not a separate arm to
build.** `git diff --stat origin/main -- mojo/engine/ benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8.mojo`
is empty — the fusion/packing project concluded with zero kernel changes, so the "+fusion" arm and
the "#507 baseline" arm are the literal same binary. One int8 measurement series stands for both
labels below; this is reported plainly rather than run twice for the appearance of two data points.

### Correctness first, on this exact run

A `transformers`-CPU reference was regenerated fresh in this session
(`reference_generate.py` → `/tmp/bb/qwen3_ckpt/reference_generate_realrace_final/`) and every
Algenta arm's generated-ids file from this run's binaries was checked against it position-by-position
with `verify_generation.py`:

| Arm | tokens matching reference | max per-step logit delta |
|---|---|---|
| Algenta CPU (float64, FastGEMV) | **16 / 16** | 3.19e-06 |
| Algenta batched-shim GPU, fp16 | **16 / 16** | 5.72e-06 |
| Algenta batched-shim GPU, int8 | **16 / 16** | 1.35e-01 |

`[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]` —
`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."` — identical across all
three Algenta arms. Both real opponents printed the identical text in every one of the six rounds:
llama.cpp `' Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'`, mlx-lm
`'Paris. The capital of Germany is Berlin. The capital of Italy is Rome.'` (same leading-space
detokenizer difference this document notes throughout — same token content). **No arm diverged in
any round, on this run.**

`mojo/tests/libs/test_residentk_session.mojo`: 39/39. `test_metaldispatch_session_i8.mojo`: 8/8
(real-GPU build). `test_metaldispatch_session.mojo` (Float32): 11/11. `test_metaldispatch_session_f16.mojo`:
8/8. `test_metaldispatch_contract.mojo`: 2/2. All identical counts to every prior addendum in this
document — rerun fresh on this worktree, not assumed.

### The numbers

Same checkpoint, prompt, 16 greedy tokens, decode-only tok/s, six rounds:

| Arm | Precision | Compute | Range | Median | vs Algenta's best |
|---|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV) | float64 | CPU, 12 perf cores | 6.47 – 7.93 | 7.31 | 0.030x |
| Algenta batched-shim GPU, fp16 | mixed (fp16 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 202.97 – 210.93¹ | 209.39¹ | 0.862x |
| **Algenta batched-shim GPU, int8 (#507 baseline == this phase's "+fusion" arm, byte-identical)** | mixed (int8 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 223.65 – 246.29 | **243.06** | **1x (best)** |
| llama.cpp `-ngl 0` | F16 | CPU (ggml) | 14.20 – 63.06² | 47.90² | 6.55x faster |
| llama.cpp `-ngl 99` | F16 | Apple GPU (Metal) | 250.54 – 260.82 | 256.72 | **1.056x faster** |
| mlx-lm | bf16 | Apple GPU (Metal) | 304.60 – 319.09 | **313.21** | **1.289x faster** |

¹ Round 1's fp16 value (147.57 tok/s) is excluded from this row's range/median as a known,
previously-documented artifact: it was the very first GPU-binary invocation of the session, and this
document's own earlier "session open... 8 shaders compiled" note already names a one-time cold
Metal-shader-cache cost on the first GPU call of a run. Included, the full six-value range is
147.57 – 210.93, median 208.55 — the conclusion below is unchanged either way (the int8 arm beats
fp16 regardless, and neither arm beats the field). The raw six values, unedited:
`147.57 210.23 210.93 208.55 210.49 202.97`.

² llama.cpp CPU is inherently noisy on this host (this session's spread, 14.20 – 63.06, is wider
than any GPU arm's) — server warm-up plus this machine's other load sharing the same 12 performance
cores llama.cpp's CPU path uses. It is not this race's binding comparison (both GPU opponents beat
it by a wide margin) and the spread does not change the verdict.

Per-round values, in round order:

```
algenta_cpu        6.999   7.930   6.468   7.735   7.627   6.712
algenta_gpu_f16  147.567 210.225 210.935 208.553 210.491 202.974
algenta_gpu_i8   223.650 245.254 242.707 246.289 241.779 243.416
llama_cpp_cpu     14.201  46.429  56.591  49.380  63.058  35.708
llama_cpp_gpu    252.872 259.732 250.544 255.407 258.035 260.824
mlx_lm           308.347 311.401 315.009 319.092 315.441 304.598
```

**int8 over fp16, on this run** (fp16 excluding the cold-start round): 243.06 / 210.23 = **1.156x
(+15.6%)** — consistent with every prior measurement of this same gap in this document (+16.9% in
the Int8-weight addendum, same order of magnitude, run-to-run noise accounts for the rest).

**int8 vs. the field, on this run**: llama.cpp GPU (256.72) beats Algenta int8 by **1.056x**;
mlx-lm (313.21) beats Algenta int8 by **1.289x**. Both figures match the Dispatch-fusion addendum's
own carried-forward numbers (1.07x, 1.28x) to within normal day-long measurement noise — because
nothing changed in the int8 arm's kernels since that addendum, this is exactly the outcome a fresh
remeasurement should produce, and it is what happened.

### Where the gap stands, and why: unchanged, confirmed one more time

The token-cost breakdown this document has built up all day still holds, reconfirmed fresh:
`submit_floor_batch.mojo` (median of 30, run fresh in this session) measured **8.71 us/dispatch**,
implying a **1.49 ms/token, 671 tok/s submission-alone ceiling** at the unchanged 171-dispatch
budget — matching every prior session's 8.68 – 8.86 us/dispatch band. At the median 243.06 tok/s,
a token costs 4.114 ms; subtracting the ~1.49 ms submission floor leaves **~2.62 ms** of
kernel-execution time, matching the Int8-weight and Dispatch-fusion addenda's own ~2.63 ms figure.
Both concrete levers this document identified for shrinking that number were tried this session
(fewer dispatches, cheaper per-element int8 unpacking) and both came back negative, for the reasons
already given in the addendum immediately above this one: Metal's public API has no grid-wide
barrier to fuse the remaining per-layer dispatch boundaries, and the existing `char4` load already
beats every explicit packed-word alternative measured, by 64%-234%.

### Publication decision: no gitbook page

**Standing rule: an outright win against BOTH llama.cpp's best (256.72 tok/s median, GPU, measured
on this run) AND mlx-lm's real number (313.21 tok/s median, measured on this run).** Algenta's best
arm — batched-shim int8, 243.06 tok/s median — loses to both: **1.056x short of llama.cpp GPU,
1.289x short of mlx-lm.** No gitbook page ships, and none is drafted.

This closes out today's entire chain (Qwen3 forward pass → KV-cache decode → parallel GEMV →
resident GPU → kernel efficiency + fp16 → batched raw-Metal dispatch → int8 → deeper fusion) with an
honest, consistent verdict at every stage: real, cumulative, verified engineering progress — a
15.56x-to-1.29x closing of the gap to mlx-lm across five precision/dispatch tiers (float32 one-shot
→ fp16 → batched dispatch → int8 → fusion-floor-confirmed) — and a genuine, named remaining
bottleneck, not a crossing of the line. The two levers left in the 243.06 tok/s token
(submission-mechanism cost, and per-instruction overhead below the byte-width where narrower dtypes
stop helping) are both now confirmed dead ends *for this toolchain, today* rather than merely
untried:

- **More dispatch fusion**: blocked on Metal's public API exposing no grid-wide barrier; the one
  remaining redesign (persistent kernel + device-scope spin barrier) is explicitly flagged in the
  code itself as high-risk and was correctly not attempted.
- **Cheaper int8 unpacking**: measured, three ways, to be a regression, not a win — the compiler's
  own `char4` lowering already beats hand-written alternatives.

**Honest assessment: further optimization within this toolchain's public API is very unlikely to
close the remaining ~1.06x-1.29x gap today.** Both concrete levers this session's own task named are
now spent, not merely tried-and-abandoned for lack of time. Closing the gap for real would need
either (a) a Modular/Mojo toolchain capability this public API does not currently expose (a
grid-wide barrier, or a lower per-dispatch submission cost than the batched shim already achieves),
or (b) an algorithmic change outside the scope of today's chain (e.g., true persistent-kernel decode
that never returns to the host between tokens, which is the same "high-risk, deliberately not
attempted" redesign named above, or a different attention/GEMV formulation entirely). Neither is a
same-day lever. Today's honest stopping point is **243.06 tok/s**, 171 dispatches/token, int8
weights, `char4` loads — a real, 33.2x improvement over this session's original CPU baseline
(7.31 tok/s), still short of the field.

### Gates, rerun on this worktree (already at `origin/main` tip `f1a99dfb`/#507 — no rebase needed)

- `git fetch origin main` then `git merge-base --is-ancestor origin/main HEAD`: true — this worktree
  was already at the current tip.
- `git diff --stat origin/main -- mojo/engine/`: empty, unchanged from every gate check this session.
- `make inventory-refresh`: zero diff. `make inventory-check`: clean (runtime contract OK,
  capability manifest OK, runtime-library-catalog OK, 122/655 modules fully declared, 595 undeclared
  against the unchanged 595 ceiling).
- `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean.
- `python3 -m scripts.reliability_guards` (all guards): the same three pre-existing baselined debt
  categories as every prior addendum (`boundary_imports` 11, `egress_sdk_clients` 11, `raw_egress`
  35) — no new violations.
- `tests/generate_mojo_tests.py --check`: clean (195 hand-written suites protected, 466 generated
  fresh) — **after fixing one real, pre-existing gap found while verifying this**: PR #507 added
  `mojo/tests/libs/test_metaldispatch_session_i8.mojo` (a hand-written golden-vector suite, sibling
  to the already-registered `test_metaldispatch_session.mojo`/`test_metaldispatch_session_f16.mojo`)
  but never added it to `tests/generate_mojo_tests.py`'s `HANDWRITTEN_TESTS` registry. This is
  invisible to `generate_mojo_tests.py --check` itself (which only checks registered-but-missing,
  not present-but-unregistered) and invisible to CI (`DE_SKIP_GO_LIVE_VERIFY=1` skips the one caller
  that does check the stricter symmetric-difference condition,
  `tests/integration/test_mojo_libraries_az.py`'s preflight) — but it is a real, reproducible local
  gap, caught here by running `pnpm check` in full rather than only the narrower gate script. Fixed
  with a one-line registry addition (test-inventory bookkeeping only, zero kernel/production code
  touched); `pnpm check`'s "Mojo libraries A-Z" step failed before the fix and passed after it,
  confirming the fix at the same tool that found the gap.
- `pnpm check`: full run, all suites green after the fix above (24 → 25 passed suites; see prior
  addenda for the two other pre-existing, already-documented, CI-invisible local quirks this
  worktree also carries — the go-live S3 connectivity flake and the `/mcp/sse` 401 mismatch — which
  did not reproduce as failures in this run's environment).
- `mojo/tests/libs/test_residentk_session.mojo`: 39/39. `test_metaldispatch_session_i8.mojo`: 8/8.
  `test_metaldispatch_session.mojo`: 11/11. `test_metaldispatch_session_f16.mojo`: 8/8.
  `test_metaldispatch_contract.mojo`: 2/2. All rerun fresh, all identical counts to every prior
  addendum.

### Reproduction

```bash
# build the shim object + all three Algenta arms (from mojo_env/)
clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build \
    -I../mojo/engine ../benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo \
    -o /tmp/race_gpu_f16 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8.mojo \
    -o /tmp/race_gpu_i8 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation

# one round = every arm once, back to back, interleaved (from benchmarks/llm_smoke/)
/tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_f16
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_i8
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0  --runs 1
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99 --runs 1
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base
# repeat this block 6x for six rounds

# token agreement, against a reference regenerated in the same session
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_realrace_final
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_llmfwd/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_realrace_final/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_batch_f16/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_realrace_final/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_batch_i8/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_realrace_final/reference_generated.json

# the submission-only floor this section's breakdown depends on
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch
```

## Speculative decoding addendum (2026-08-02, later still again): no-go before any kernel, no race run

The final real race above closed today's dispatch/precision chain at 243.06 tok/s int8, still short
of both real opponents (llama.cpp GPU 256.72, mlx-lm 313.21). Speculative / prompt-lookup decoding
was investigated next, as the field's standard lever for exactly this regime (small model, greedy
decoding, memory-bandwidth-bound single-token GEMV steps). **No race was run.** Both the Design
phase and an independent Build-phase verification pass concluded no-go before a single kernel line
was written, and no worktree or code change from either phase survived — there is nothing to diff,
nothing to rebase, nothing new to race. This section records why, so the technique is not
re-investigated from scratch next session.

### What was checked, and how

**Kernel-level feasibility** (`mojo/engine/metaldispatch/session.mojo`, `mojo/engine/residentk/kernels.mojo`,
`mojo/engine/residentk/contract.mojo`, all read fresh against `origin/main` — the Design phase's own
inspection worktree, `/tmp/speculative-decode-eval`, had already been deleted, so the Build phase
re-verified every load-bearing claim against the real tip, `610cd54a`, the same commit this
document's own final-race numbers came from):

- 171 dispatches/token (`n_layers*6 + 3`, `n_layers=28` for Qwen3-0.6B) is confirmed exact. Every
  one of the 6 per-layer kernel roles (`_norm_gemv_kernel`, `_gemv_accum_kernel`,
  `_norm_gemv2_swiglu_kernel`, ×3 dtype variants each where present) stages exactly **one** row into
  a single-row `_STAGE` shared-memory buffer — there is no K-rows parameter anywhere to reuse.
  Verified directly in the kernel bodies, not inferred.
- `_sdpa_kernel`'s own docstring states, verbatim: attention is for **one** new query token over
  the cached keys, unmasked, because "a single query at the true current position attends to every
  cached key by construction." A K-draft-position verification pass needs each position to see a
  *different* causal window — a new, masked, batched SDPA kernel, not a parameter tweak.
- The KV cache (`RESIDENT_MAX_CONTEXT=512`, absolute-position-indexed flat buffer, no length field
  — the #501 O(N²) fix's design) makes speculative rollback **free**: writing K speculative
  positions straight into the real cache slots and later accepting only `m` of them needs no
  truncation code at all, because `n_keys = pos+1` on every future step already guarantees the
  rejected slots are never read. This part is a genuine, verified win of the existing architecture
  — it is the KV-cache design, not the speculative-decoding project, that gets credit for it.
- `gemm.blocked` (the frozen CPU/Float64 GEMM used elsewhere in this codebase) is confirmed
  irrelevant — disjoint host-side module, no path to the Metal-resident GEMV world.
- Getting a **real** win (not just K× the residual GPU compute with zero new kernels) needs new
  batched-K variants of all 6 per-layer roles plus the lm-head argmax — **8 new kernel roles**,
  correctly scoped by Design as multi-day kernel-engineering effort, not a wrapper. The
  zero-new-kernel "naive" version (K duplicate 171-dispatch descriptor groups in one command
  buffer) was also modeled and found **not worth building either** — see the cost model below.

**Hit-rate, on this exact benchmark's known token sequence**
(`[12095,13,576,6722,315,9856,374,19846,13,576,6722,315,15344,374,21718,13]`, i.e.
`"The capital of France is Paris. The capital of Germany is Berlin. The capital of Italy is Rome."`),
simulated independently twice (Design's `/tmp/pl_sim.py`, Build's separate `/tmp/pl_verify.py`,
both throwaway, neither committed): with the correct n-gram window for this text (`N=3`, matching
the real repeating unit "The capital of"), there is **exactly one point** across all 16 generation
steps where a draft is both found and correct — position 11, drafted token `315` ("of") — and it is
correct for exactly **one** token before the very next drafted token (copied from the first
template occurrence, "Germany") mismatches the real next token ("Italy"). Zero additional benefit
for any draft length K>1, on this text, ever. Both independent simulations reproduced this decisive
result exactly (the two runs' raw "draft-available-steps" counts differed slightly on a
methodology detail — whether prompt tokens count toward the lookup history — but the number that
drives the go/no-go decision, one accepted draft token in the whole generation, was identical).

**Cost model**, anchored to this document's own measured numbers rather than a hypothetical
(1.49ms submission floor + 2.62ms kernel residual = 4.114ms/token, reproducing the 243.06 tok/s
median measured in the final-race section above): a naive zero-new-kernel K-position reuse costs
`1.49ms + K*2.62ms` per round; an idealized, perfectly-amortized 8-new-kernel build costs
`1.49ms + 2.62ms` flat regardless of K (a generous upper bound that ignores SDPA/lm-head's likely
inability to amortize fully). Plugging in the one-accepted-token result above:

| Config | naive reuse (0 new kernels) | idealized full 8-kernel build |
|---|---|---|
| N=3, K=2 (best-tuned for this text) | 249.6 tok/s (+2.3%) | 260.2 tok/s (+6.7%) |
| N=3, K=4/5 (typical fixed draft length) | 222–231 tok/s (**worse than baseline**) | 260.2 tok/s (ceiling — K beyond 2 wastes verification, no extra accept) |

Even the idealized, best-case, full-multi-day-build ceiling (**260.2 tok/s**) edges past
llama.cpp GPU's 256.72 by 1.4% but stays **16.9% behind mlx-lm's 313.21** — it does not clear the
standing rule's "both opponents" bar even in the best case that assumes the hard kernel work lands
perfectly. The realistic near-term version (naive reuse, no new kernels) nets at most +2.3%, and
a poorly-tuned draft length (K>2, the common off-the-shelf default) is **net negative**.

### Why this benchmark specifically, not the technique generally

Speculative/prompt-lookup decoding is real and is the field's correct answer for this regime in
general. It fails here because this run's fixed 16-token generation
("The capital of France is Paris. The capital of Germany is Berlin. The capital of Italy is Rome.")
repeats a 3-token *template* twice but never repeats *content* — the token immediately after every
template match is always the newly-varying country/capital slot. Longer or more genuinely
repetitive generations (long-form code, structured/templated text, multi-turn agreement) would give
prompt-lookup a real, different hit-rate profile. This addendum is a verdict on tonight's specific
16-token prompt-continuation benchmark, not a general claim that speculative decoding never helps
Algenta.

### Verification: two independent passes agree, no code survives either

- **Design phase**: read `session.mojo` (1873 lines) and `kernels.mojo` (1410 lines) in a scratch
  worktree (`/tmp/speculative-decode-eval`), ran the hit-rate simulation, concluded no-go, removed
  the worktree. Nothing merged, nothing to diff.
- **Build phase**: independently re-read the same three files against the real `origin/main` tip
  (`610cd54a`) rather than trust the deleted worktree's transcript, independently re-ran the
  hit-rate simulation against the same known token sequence, and independently reproduced the
  decisive one-accepted-token result and the cost-model numbers derived from it. No worktree was
  created for the Build pass; no code was written.
- **This addendum**: no further kernel work was attempted — both independent passes already agree,
  and the cost-model ceiling (+6.7% best case) does not clear mlx-lm even under the most generous
  assumptions, so there was nothing left to verify by building.

### Publication decision: no gitbook page, no race run

**Standing rule: a gitbook page ships only on an outright win against both llama.cpp's best
(256.72 tok/s median, GPU) and mlx-lm's real number (313.21 tok/s median), on a measurement run.**
No mechanism exists to measure — no kernel was built, on either phase's independent recommendation
— so there is no new arm to race, and the prior "Algenta batched-shim int8, 243.06 tok/s" verdict
from the final-race section above stands unchanged as today's number. No gitbook page ships.

This closes today's speculative-decoding lever honestly: the technique is real, the KV-cache
rollback design already in place is free and correct for it, and the kernel-engineering path to try
it (8 new batched-K Metal kernels) is well-scoped for a future session on a benchmark text where
prompt-lookup's hit rate would actually be favorable — but building it against *this* run's
template-not-content 16-token generation would, at best, buy +6.7% and still lose to mlx-lm, so it
was correctly not built.

### Gates, on a fresh worktree off `origin/main` tip (`610cd54a`, `#508`)

- `git fetch origin main`: no new commits — this worktree opened at the current tip.
- `git diff --stat origin/main`: empty except this document.
- `make inventory-refresh`: zero diff. `make inventory-check`: clean.
- `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean — no kernel or
  namespace change in this addendum.
- `tests/generate_mojo_tests.py --check`: clean — no new or changed Mojo test files.
- No decode driver was rerun in this addendum: no new binary exists to run one against. The
  final-race section's own numbers (243.06 tok/s int8, full token-agreement table) are the current,
  unchanged, correct measurement for today.

## GPU-counter timing addendum (2026-08-02, later still): real per-role attribution, `lm_head` and SDPA investigated, both cleared — no single-role fix, no kernel change

The "Final real race" section immediately above named a token-level split (~1.49 ms submission
floor + ~2.62 ms kernel-execution residual) inferred by *subtraction* — an isolated no-op-shaped
dispatch benchmark (`submit_floor_batch.mojo`) versus the real token's wall clock. This addendum
replaces that inference with **direct measurement**: a Metal hardware-counter probe
(`benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m` +
`qwen3_probe_counters_i8.mojo`, both new, diagnostic-only, zero changes to `batch_shim.m`,
`qwen3_generate_batch_i8.mojo`, or anything under `mojo/engine/`) that samples a GPU timestamp
immediately before/after every one of the 171 real `dispatchThreadgroups:` calls in the SAME single
command buffer/encoder/commit/`waitUntilCompleted` production uses, and attributes every
microsecond to the dispatch's real kernel role. Built fresh in this worktree
(`.worktrees/metalcounters`, branch `feat/metal-gpu-counter-timing`, off `origin/main` tip
`947539f4`) and reproduced independently before anything below was trusted — see "Verification"
below.

### Two real API findings on this machine, confirmed against the installed Xcode 26.6.0 headers

- `MTLDevice.supportsCounterSampling(.atDispatchBoundary)` is **NO** on this hardware/driver; only
  `.atStageBoundary` (per-encoder) is supported. Per-dispatch granularity therefore needs one
  `MTLComputeCommandEncoder` per dispatch (171 encoders, still one command buffer/commit/wait) —
  pure CPU-side command-stream construction between dispatches, not a host/GPU sync point, so the
  "no host sync between dispatches" invariant every prior addendum in this document relies on still
  holds.
- `MTLDevice.queryTimestampFrequency` reports **24,000,000 ticks/sec**; a direct calibration
  bracket (GPU tick delta over a `perf_counter_ns`-measured wall interval) measures the real rate at
  **~998,000,000 ticks/sec — off by ~41.6x**. Every ns conversion below uses the calibrated rate.
  This is a real, reportable API-reliability finding for this OS/hardware combination, independent
  of anything else in this addendum.

### Verification: the probe's own headline numbers, reproduced independently in this session

Built and ran the probe fresh (not trusting the numbers as reported):

```
OFF (no counters, plain step()): 4.4795 ms/token   ON (with counters): 7.8587 ms/token  (+75.4% overhead)
lmhead_argmax : count=30 avg= 566.5 us   pct_of_residual_sum= 12.80%
sdpa          : count=840 avg= 44.05 us  pct_of_residual_sum= 27.86%  (range 23-66 us, grows with position)
sum of per-dispatch GPU deltas/token: 4.426 ms  vs OFF wall-clock: 4.480 ms  (98.8% match)
```

This matches the prior report's numbers to within run-to-run noise (556-567 us for `lm_head`,
23-68 us range for `sdpa`, ~97-99% reconciliation) — the instrumentation and its headline breakdown
are real, not an artifact of one run.

**This reconciliation also corrects the "Final real race" section's subtractive model, not just
confirms the report.** If ~4.43 ms of real, per-dispatch-attributed GPU time already accounts for
~99% of a 4.48 ms token, there is no separate ~1.49 ms "submission floor" sitting *additively* on
top of kernel execution — most of what `submit_floor_batch.mojo`'s no-op-dispatch isolation
attributed to "pure submission cost" is in fact ordinary per-dispatch fixed overhead that is
already *inside* the 4.43 ms of real, counter-measured kernel time above, not a second tax layered
on top of it. This does not change today's bottom-line tok/s (nothing here is a kernel change) but
it does mean the "~2.62 ms kernel residual, ~1.49 ms submission floor" split in every prior addendum
should be read as an approximation, not a literal additive decomposition — worth flagging before
any future session leans on that split to size a fusion project.

### `lm_head` investigated directly — not a bug, already near this toolchain's floor

The report recommended `_lmhead_argmax_kernel_i8` as "the single best isolated target" (one
dispatch, 12.8% of the token, 12-37x any per-layer dispatch's average). Investigated all three
angles the task named, before touching anything:

1. **Already using the same vectorized+int8 techniques as the per-layer kernels** — confirmed by
   reading the kernel (`mojo/engine/residentk/kernels.mojo:1273-1370`): identical `_VEC_I8=4`
   (`char4`) vectorized load, identical in-register `Float32(w) * wscale[row]` dequant-then-multiply
   pattern, identical 32-lane tree reduction. Nothing about `lm_head`'s inner loop differs from
   `_gemv_accum_kernel_i8`/`_norm_gemv_kernel_i8`.
2. **Reduction strategy for a 151,936-wide argmax** — a two-pass design: a grid-stride loop over
   `_LM_BLOCKS = 2048` threadgroups (chosen, per the code's own comment, to keep MAX's per-dispatch
   host cost near its floor rather than launching one threadgroup per 8 columns, ~19,000 of them),
   each producing one partial `(max, argmax)`, collapsed by a second, tiny `_argmax_reduce_kernel`
   dispatch (14.1 us, 0.3% of the token). This is a standard, appropriately-sized two-pass reduction
   for this width, not a naive single-pass design.
3. **Grid/threadgroup sizing** — the one knob in (2) never revisited since it was chosen against a
   Float32-era measurement, before fp16/int8 landed. Swept directly, rebuilding and rerunning the
   counter probe at each value (`_LM_BLOCKS` = 512, 1024, 1536, 2048, 3072, 4096, 6144 — a 12x
   range), everything else unchanged:

   | `_LM_BLOCKS` | `lm_head` avg (us) | OFF wall-clock avg (ms/token) |
   |---|---|---|
   | 512 | 564.4 | 4.523 |
   | 1024 | 598.9 | 4.563 |
   | 1536 | 576.8 | 4.485 |
   | **2048 (current)** | **555.7** | **4.483** |
   | 3072 | 555.7 | 4.498 |
   | 4096 | 554.7 | 4.534 |
   | 6144 | 576.7 | 4.556 |

   No trend: every value lands in a 555-599 us band with no monotonic relationship to grid size,
   and the current 2048 is at or near the best of the seven values tried, not a compromise leaving
   free performance on the table. (A build at `_LM_BLOCKS = 8192` was attempted but the run
   timed out on this shared, multi-agent-loaded machine and was not retried — the 12x range already
   sampled is sufficient to see there is no exploitable slope.) Session file restored byte-identical
   to `origin/main` after the sweep (`diff` clean) before drawing any conclusion.

**Why the "disproportion" is real but not a bug**: `lm_head` reads the entire tied
`[vocab, d_model]` = 151,936 x 1024 int8 matrix once per token — 155,582,464 bytes (148.4 MiB) — the
*only* dispatch that touches this whole matrix, versus every per-layer dispatch touching a
1-6 MiB slice of a much smaller matrix 28 times. At the measured 555.7 us baseline that is
**~280 GB/s** — 68% of this host's own previously-measured 411 GB/s streaming ceiling (cited
throughout this document), and only **1.47x above the 378.6 us naive bandwidth floor**
(155.58 MB / 411 GB/s). That ratio is *better than*, not worse than, the aggregate int8-arm ratio
the Int8-weight addendum already reported for the whole token (2.63 ms measured against a 1.742 ms
floor — 1.51x, "~51% above floor"). In other words: `lm_head` is not an inefficient outlier in the
breakdown table — it is the single dispatch doing the most real memory-bound work, running at
least as close to this machine's bandwidth ceiling as everything else in the same int8 arm, and it
*looks* disproportionate in the per-dispatch table purely because it is ~130x bigger than a typical
per-layer dispatch, not because anything is being done inefficiently inside it.

### SDPA re-verified independently, by reading the code, not by re-trusting the report

Confirmed directly, independent of the report's own measurement: `_sdpa_kernel`
(`mojo/engine/residentk/kernels.mojo:1046`) loops `for j in range(n_keys)` — `n_keys` is a runtime
kernel argument, not `RESIDENT_MAX_CONTEXT`. At the call site
(`mojo/engine/metaldispatch/session.mojo:885-888` and the identical residentk/f16/i8 twins),
`n_keys = pos + 1` is patched into that dispatch's descriptor fresh every step. There is no fixed
512-wide scan hiding anywhere in this path — the report's falsification of that hypothesis is
correct, confirmed by reading the source, not merely by re-running its own probe.

### Conclusion: no worthwhile single-role fix found — reported honestly, nothing landed

Every angle the task asked to investigate for `lm_head` came back clean: same vectorization as its
siblings, an appropriately-sized two-pass reduction, and a grid-size sweep across a 12x range with
no measurable effect. SDPA is legitimate real per-key work, re-confirmed from the source. The
GEMV-shaped per-layer kernels have "no fresh lever without a new idea (e.g., int4)" per the report
— and int4 is a new precision tier applying to every weight matrix, not a `lm_head`-specific fix,
and out of scope for a narrow same-day change (every prior precision tier in this document —
float32 → fp16 → int8 — was its own multi-gate addendum). **This is a genuine null result: the
per-role timing breakdown is real and correctly attributed, but nothing in it is a fixable
inefficiency at this toolchain's current ceiling.** No kernel, session, or contract file changed;
`git diff --stat origin/main -- mojo/engine/` stays empty. Decode-only tok/s is therefore unchanged
from the "Final real race" section above (best arm: batched-shim int8, 243.06 tok/s median) — no
before/after speed claim is made here because no fix was made to measure one against.

### Gates, on this worktree (`.worktrees/metalcounters`, branch `feat/metal-gpu-counter-timing`, off `origin/main` tip `947539f4`)

- `git diff --stat origin/main -- mojo/engine/`: empty.
- `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean, no new violations.
- `make inventory-refresh`: zero diff (both new files are diagnostic-only with no new public
  contract surface). `make inventory-check`: clean (runtime contract OK, capability manifest OK,
  runtime-library-catalog OK).
- `python3 scripts/capability_manifest_gate.py` (via `make inventory-check`): clean, no new
  undeclared kernels (122/655 modules fully declared, 595 undeclared against the unchanged 595
  ceiling).
- `tests/generate_mojo_tests.py --check`: clean (195 hand-written suites protected, 466 generated
  fresh).
- `mojo/tests/libs/test_metaldispatch_session_i8.mojo`: 8/8 (real-GPU build) — rerun fresh, unchanged.
- `mojo/tests/libs/test_residentk_session.mojo`: 22/22 (default, no-GPU build) — rerun fresh,
  unchanged.
- `mojo/tests/libs/test_metaldispatch_contract.mojo`: 2/2 — rerun fresh, unchanged.
- No golden-vector test added: no function's behavior changed, so there is nothing new to pin.

### Reproduction

```bash
# build the diagnostic shim + probe (from this worktree)
clang -c -fobjc-arc -O2 benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
    -o /tmp/batch_shim_counters.o
cd mojo_env
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8.mojo \
    -o /tmp/qwen3_probe_counters_i8 \
    -Xlinker /tmp/batch_shim_counters.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_probe_counters_i8

# the _LM_BLOCKS sweep (each value: edit mojo/engine/metaldispatch/session.mojo's
# `comptime _LM_BLOCKS: Int = 2048` line, rebuild the probe under a distinct -o path, run, restore)
```

## Final race + permanent per-role artifact (2026-08-02, later still again): every arm re-raced fresh, GPU-counter breakdown reconfirmed, still no gitbook page

The GPU-counter timing addendum immediately above found a genuine null result: `lm_head` and
SDPA were both investigated and both cleared, no kernel changed. This section closes the loop the
task asked for: rebase onto the current `origin/main` tip, re-race every arm fresh (there is no
"+fix" arm to add — the Optimize phase's own conclusion was that nothing landed), verify token
agreement fresh, and fold the per-role GPU timing table into this document as a standing artifact
so it is not re-derived next session regardless of whether it produces a speed win today.

Rebased this worktree (`.worktrees/metalcounters`, branch `feat/metal-gpu-counter-timing`) onto
`origin/main` tip `aee75f6f` (#509, speculative-decoding no-go, docs-only) — one content conflict
in this file itself (both branches appended a new section after the same "Final real race"
section); resolved by keeping both addenda, in chronological order. `git diff --stat origin/main --
mojo/engine/` stays empty after the rebase.

### Correctness first, on this exact run

A `transformers`-CPU reference was regenerated fresh in this session
(`reference_generate.py` → `/tmp/bb/qwen3_ckpt/reference_generate_realrace_final2/`) and every
Algenta arm's generated-ids file from this run's binaries was checked against it position-by-position
with `verify_generation.py`, all 16/16:

| Arm | tokens matching reference | max per-step logit delta |
|---|---|---|
| Algenta CPU (float64, FastGEMV) | **16 / 16** | 1.02e-05 |
| Algenta batched-shim GPU, fp16 | **16 / 16** | 1.14e-05 |
| Algenta batched-shim GPU, int8 | **16 / 16** | 2.36e-01 |

`[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374, 21718, 13]` —
`" Paris. The capital of Germany is Berlin. The capital of Italy is Rome."` — additionally verified
identical, token-by-token, across **all six rounds** of the race below for all three Algenta arms
(not just the round used for the reference check), and both real opponents printed the identical
text in every one of the six rounds too: llama.cpp `' Paris. The capital of Germany is Berlin. The
capital of Italy is Rome.'`, mlx-lm `'Paris. The capital of Germany is Berlin. The capital of Italy
is Rome.'` (same leading-space detokenizer difference this document notes throughout — same token
content). **No arm diverged in any round, on this run.**

### The numbers

Same checkpoint, prompt, 16 greedy tokens, decode-only tok/s, six interleaved rounds, fixed order
Algenta CPU → Algenta batched-shim GPU fp16 → Algenta batched-shim GPU int8 → llama.cpp CPU →
llama.cpp GPU → mlx-lm:

| Arm | Precision | Compute | Range | Median | vs Algenta's best |
|---|---|---|---|---|---|
| Algenta CPU (`qwen3_generate.mojo`, FastGEMV) | float64 | CPU, 12 perf cores | 6.53 – 7.06 | 6.73 | 0.029x |
| Algenta batched-shim GPU, fp16 | mixed (fp16 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 197.14 – 203.86 | 198.69 | 0.845x |
| **Algenta batched-shim GPU, int8 ("+this chain's fix" == the #507/#508/#509 baseline, byte-identical — see below)** | mixed (int8 storage, fp32 compute) | Apple GPU (Metal, raw shim) | 178.14¹ – 238.90 | **235.05** | **1x (best)** |
| llama.cpp `-ngl 0` | F16 | CPU (ggml) | 6.65 – 46.01² | 7.63² | 1.13x faster |
| llama.cpp `-ngl 99` | F16 | Apple GPU (Metal) | 245.82 – 253.68 | 247.88 | **1.055x faster** |
| mlx-lm | bf16 | Apple GPU (Metal) | 299.60 – 312.49 | **307.04** | **1.306x faster** |

¹ Round 1's int8 value (178.14 tok/s) sits well below the other five rounds' tight 231.5–238.9 band.
Unlike the fp16 cold-start artifact this document noted in the "Final real race" section, this is
*not* a first-GPU-call-of-the-session effect — both the fp16 and int8 binaries had already been
invoked once each, warm, immediately before round 1 (as part of this session's own pre-race sanity
check, 200.6 and 235.1 tok/s respectively, both already in the normal band). No cause was found
beyond ordinary host contention on this shared, multi-agent-loaded machine; it is reported plainly
rather than excluded, since the median (235.05) is barely affected by one outlier of six and the
conclusion below is unchanged either way. **"Algenta batched-shim GPU int8 + this chain's fix" is
not a separate arm to build**: the Optimize phase concluded with zero kernel changes (every angle
investigated — vectorization, reduction strategy, grid sizing, SDPA — came back clean), so there is
nothing to add on top of the standing int8 baseline; one measurement series stands for both labels.

² llama.cpp CPU remains inherently noisy on this host (14.20–63.06 in the prior session's six
rounds; 6.65–46.01 in this one) — this is not this race's binding comparison and does not change
the verdict.

Per-round values, in round order:

```
algenta_cpu        6.838   7.062   6.525   6.579   6.788   6.680
algenta_gpu_f16  198.085 199.298 197.138 197.545 203.857 200.776
algenta_gpu_i8   178.143 238.899 237.967 231.506 237.827 232.277
llama_cpp_cpu      6.653  46.010   7.535  25.657   7.597   7.660
llama_cpp_gpu    248.807 253.678 246.959 246.887 245.821 251.323
mlx_lm           312.373 312.493 299.604 306.888 299.858 307.200
```

**int8 vs. the field, on this run**: llama.cpp GPU (247.88) beats Algenta int8 by **1.055x**;
mlx-lm (307.04) beats Algenta int8 by **1.306x**. Both figures match the "Final real race"
section's own numbers (1.056x, 1.289x) to within normal day-long measurement noise — because
nothing changed in the int8 arm's kernels since that section (the Instrument/Optimize chain's own
honest null result), this is exactly the outcome a fresh remeasurement should produce, and it is
what happened.

### Real per-role GPU timing breakdown — permanent artifact, reconfirmed fresh on this run

Rebuilt and reran the hardware-counter probe
(`benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m` +
`qwen3_probe_counters_i8.mojo`, diagnostic-only, zero production files touched) three times fresh
on this run, averaged, to fold this into the permanent record regardless of today's speed
verdict:

| Role | Count/token | Avg µs/dispatch | % of summed residual |
|---|---|---|---|
| sdpa | 28 | 45.08 | **26.85%** |
| gemv_accum (o_proj+down_proj) | 56 | 17.32 | 20.59% |
| norm_gemv2_swiglu (gate-up) | 28 | 32.11 | 19.12% |
| norm_gemv (QKV-proj) | 28 | 25.91 | 15.41% |
| lmhead_argmax | **1** | **575.22** | 12.24% |
| qk_rope_write | 28 | 8.91 | 5.29% |
| argmax_reduce | 1 | 19.31 | 0.41% |
| embed_row | 1 | 4.55 | 0.10% |
| — gemv_accum / o_proj | 28 | 14.93 | (within gemv_accum) |
| — gemv_accum / down_proj | 28 | 19.71 | (within gemv_accum) |

Reconciliation, averaged over the same three runs: sum of per-dispatch GPU time **4.705 ms/token**
vs. OFF-phase (single-encoder, production-shaped) wall-clock **4.778 ms/token** — a **98.5% match**,
consistent with the Instrument/Optimize sessions' own 97–99% figures earlier today. Instrumentation
overhead (171-separate-encoders technique itself): ON averaged 8.099 ms/token vs OFF 4.778 ms/token
— **+69.5%**, in the same band as every prior measurement of this overhead today (+71.6% to +79.9%
across the three probe runs individually). This table is the same real, source-verified attribution
the Instrument and Optimize phases already established (`lm_head` disproportionate but not
inefficient — 68% of this host's 411 GB/s streaming ceiling; SDPA's cost grows with position,
confirmed from `_sdpa_kernel`'s `n_keys = pos + 1` argument, not a fixed-512 scan) — reconfirmed
here, unaltered, as the standing reference for any future session that wants per-role GPU cost
without re-deriving it.

### Publication decision: no gitbook page

**Standing rule: an outright win against BOTH llama.cpp's best (247.88 tok/s median, GPU, measured
on this run) AND mlx-lm's real number (307.04 tok/s median, measured on this run).** Algenta's best
arm — batched-shim int8, 235.05 tok/s median — loses to both: **1.055x short of llama.cpp GPU,
1.306x short of mlx-lm.** No gitbook page ships, and none is drafted. This is the same verdict, to
within normal measurement noise, as every prior race today.

### Is today's optimization space exhausted for this architecture? Yes, as far as this chain went

Today's full chain, in order: Qwen3 forward pass → KV-cache decode → parallel GEMV → resident GPU
→ kernel efficiency + fp16 → batched raw-Metal dispatch → int8 → dispatch-fusion/packed-load
investigation (dead end) → GPU hardware-counter per-role attribution (`lm_head`/SDPA investigated,
dead end) → speculative decoding (dead end, no-go before a kernel was written) → this final,
fresh, fully-reconfirmed race. Every concrete lever named anywhere in this document has now been
either landed (float32 → fp16 → int8, batched dispatch, per-channel quantization) or tried and
confirmed dead for *this specific 16-token, single-request, Qwen3-0.6B benchmark on this toolchain*:

- **More dispatch fusion**: blocked on Metal's public API exposing no grid-wide barrier (Dispatch-
  fusion addendum).
- **Cheaper int8 unpacking**: measured worse than the existing `char4` load, three ways (Dispatch-
  fusion addendum).
- **`lm_head`/SDPA-specific fixes**: vectorization, reduction strategy, and a 12x grid-size sweep
  all came back clean; SDPA's cost is legitimate per-key work (GPU-counter addendum).
- **Speculative/prompt-lookup decoding**: this exact prompt's repeating unit is template, not
  content — hit-rate caps the idealized best case at +6.7%, still short of mlx-lm (Speculative
  decoding addendum).

**Honest assessment, unchanged from every prior addendum today: closing the remaining ~1.06x–1.31x
gap is very unlikely within this toolchain's current public API and this benchmark's shape.** The
per-role table above does suggest one avenue this chain did not attempt because it is out of scope
for a same-day change: **int4 weights** for the three GEMV-shaped per-layer roles (54% of the
summed residual combined) — a new precision tier, not a `lm_head`- or SDPA-specific fix, requiring
its own multi-gate addendum the way float32→fp16 and fp16→int8 each got one. Beyond that, the two
structural levers this document already named (a lower-per-dispatch-cost submission mechanism, or
a genuinely persistent-kernel decode loop that never returns to the host between tokens) remain the
only paths to a different regime, and both are explicitly flagged elsewhere in this document as
multi-day, high-risk redesigns outside today's scope. **Today's honest stopping point, reconfirmed
fresh: 235.05 tok/s median, 171 dispatches/token, int8 weights, `char4` loads** — a real, 34.9x
improvement over this session's original CPU baseline (6.73 tok/s today), still short of the field.

### Gates, rebased onto `origin/main` tip (`aee75f6f`, `#509`), all rerun after the rebase

- `git fetch origin main` then rebase: one content conflict in this file (both branches appended a
  new section after "Final real race"); resolved by keeping both addenda in order, no other file
  touched.
- `git diff --stat origin/main -- mojo/engine/`: empty.
- `make inventory-refresh`: zero diff. `make inventory-check`: clean (runtime contract OK,
  capability manifest OK, runtime-library-catalog OK, 122/655 modules fully declared, 595
  undeclared against the unchanged 595 ceiling).
- `python3 -m scripts.reliability_guards --guard mojo_freeze_namespaces`: clean, no new violations.
- `tests/generate_mojo_tests.py --check`: clean (195 hand-written suites protected, 466 generated
  fresh).
- `mojo/tests/libs/test_metaldispatch_session_i8.mojo`: 8/8 (real-GPU build). `test_residentk_session.mojo`:
  22/22 (default, no-GPU build). `test_metaldispatch_contract.mojo`: 2/2. All rerun fresh on this
  worktree, post-rebase, identical counts to every prior addendum.

### Reproduction

```bash
# rebase
git fetch origin main
git rebase origin/main

# build the shim object + all three Algenta arms (from mojo_env/)
clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build \
    -I../mojo/engine ../benchmarks/llm_smoke/qwen3_generate.mojo -o /tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo \
    -o /tmp/race_gpu_f16 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8.mojo \
    -o /tmp/race_gpu_i8 -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation

# one round = every arm once, back to back, interleaved (from benchmarks/llm_smoke/)
/tmp/race_cpu
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_f16
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/race_gpu_i8
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0  --runs 1
/tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99 --runs 1
/tmp/bb/bin/python -P realrace_mlx_lm.py --checkpoint /private/tmp/qwen3-0.6b-base
# repeat this block 6x for six rounds

# token agreement, against a reference regenerated in the same session
/tmp/bb/bin/python3 -P reference_generate.py --checkpoint /private/tmp/qwen3-0.6b-base \
    --out /tmp/bb/qwen3_ckpt/reference_generate_realrace_final2
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_llmfwd/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_realrace_final2/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_batch_f16/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_realrace_final2/reference_generated.json
/tmp/bb/bin/python3 -P verify_generation.py /tmp/bb/qwen3_ckpt/mojo_generate_batch_i8/generated_ids.txt \
    /tmp/bb/qwen3_ckpt/reference_generate_realrace_final2/reference_generated.json

# the per-role GPU counter probe (from mojo_env/)
clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
    -o /tmp/batch_shim_counters.o
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run mojo build -D ALGENTA_GPU \
    -I../mojo/engine ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8.mojo \
    -o /tmp/qwen3_probe_counters_i8 \
    -Xlinker /tmp/batch_shim_counters.o -Xlinker -framework -Xlinker Metal \
    -Xlinker -framework -Xlinker Foundation
DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_probe_counters_i8
```
