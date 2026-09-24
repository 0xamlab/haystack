# The GPU probe — `thyn-ai/algenta-gpu-probe`

Internal notes for `apps/spaces/gpu-probe/`. Module docstrings are the reference; this page is
the runbook view.

## What it is

A private Docker Space on `l4x1` (NVIDIA L4, sm_89, 24 GB; 8 vCPU, 30 GB) that boots and runs
the published single-stream race live: the CUDA engine bundled in the `algenta-runtime-native`
wheel (lane A) against llama.cpp's official prebuilt CUDA server (ggml-org's image at tag
`server-cuda-b10223`, by digest, commit `11924d4c17`; the pages' cell ran `000547513f`, tag
`b10210`, built from source — see "Lane B's binary" below; lane B), on `Qwen/Qwen3-0.6B-Base`, the benchmark battery's
256-token prompt, gen=64 greedy, one warm-up excluded, the median of three timed runs — the
shape of the L4 cell on
`gitbook/benchmarks/nvidia-llm-serving.md` ("Single-stream decode": Algenta 193.9 tok/s at
gen=64, 188.8 at gen=256, llama.cpp F16 1.12× / 1.09× slower) and of the L4 table on
`gitbook/benchmarks/nvidia-llm-throughput.md` (191.1 / 184.8 vs 171.3 / 172.6). The page prints
the measured pair first and the published pair beneath it, marked as published and linked to
the page it comes from. Two secondary rows run on the same GPU with the same prompt: the Hub
kernels' f32 parity path (`thyn-ai/algenta-llm`, `DecodeSession`; lane C) and plain
transformers in float32 and float16 (lane D). Every lane's tokens are checked against a
transformers float32 CPU reference, the first 16 as the published oracle and all 64.

Why the probe changed shape (2026-09-24): runs 12 to 14 showed Qwen3-1.7B through the Hub
kernels' f32 parity path at 37 tok/s on a T4 beside transformers, which is the wrong thing to
put next to the published numbers — those measure the CUDA-native resident session on
Qwen3-0.6B-Base against llama.cpp on the same machine. The probe now runs that race, with the
honest opponent beside it, and keeps the parity path as a secondary row on the same model.

It is not in `apps/spaces/spaces.toml`: the fleet manifest has no `private` key, requires
`api_names`, and its tests assert the fleet is the flagship alone with no GPU stage; a table
would also put a paid GPU on `deploy.py --all`. `apps/spaces/gpu-probe/DEPLOY.md` has the exact
`huggingface_hub` steps instead (create private, upload, `l4x1`, poll, read, pause).

## What the shipped engine is — read before reading the numbers

Lane A is what `pip install algenta` installs: `algenta-runtime-native==1.0.7` bundles
`algenta_runtime_native/conform_generate_cuda` (7.5 MB) beside `libcudart.so.12`, declared in
the wheel's signed `manifest.json`. The probe reads that manifest (`fetch_assets.py --bake`
records it, `probe.py --stage engine` gates on it) rather than assuming anything:

| Manifest fact (wheel 1.0.7) | Value | Consequence |
|---|---|---|
| `engine.cuda_target` | `sm_90a` | An architecture-specific image: it loads on compute capability 9.0 (H100/H200) alone, never forward. On the L4 (8.9) lane A fails closed with `engine_target_mismatch` before launch; on `h100` hardware it runs. |
| `engine.comptime_defines` | `ALGENTA_GPU`, `ALGENTA_CUDA`, `ALGENTA_STAGE_18944`, `ALGENTA_TC_SHIM`, the Gemma-3 prefill flags; no packed3 or graph define | The engine is the f32 conformance session: `benchmarks/llm_smoke/conform_generate_cuda.mojo` constructs `_CudaResidentQwen3` with `skip_f32_projections=0` and decodes with `step()` — "six fused dispatches per layer plus the fixed three, per-dispatch enqueue" (`mojo/engine/residentk/session_cuda.mojo`). The published cells ran the packed-int8 captured-graph session (`residentk/session_cuda_p3_graph.mojo`, driven by `benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo`), which is not in any wheel. |
| `engine.host_shared_libraries` | `libcublas.so.12`, `libcublasLt.so.12` | Provided by the CUDA runtime image; checked with `ctypes` before launch (`engine_host_library_missing`). |
| `engine.sha256` | `c5594028…` | Verified against the file at bake and at run (`engine_sha_mismatch`). |

So on `l4x1` with the wheel's engine alone the honest page reads: lane A unavailable with
`engine_target_mismatch` and the message naming `sm_90a` and 8.9, lane B measured, lanes C and
D measured, and the published pair beneath. Two things restore lane A, in order of value:

1. Ship the engine of the published cell, built for the L4 — done 2026-09-24, the section
   below: the packed-int8 captured-graph driver `qwen3_p3_graph_cuda` compiled
   `--target-accelerator sm_89`, with its runtime closure and a manifest, copied into the
   Space folder as `engine/` at deploy time and selected by the Space variable
   `ALGENTA_CUDA_ENGINE=/home/user/engine/qwen3_p3_graph_cuda` (the resolver's first override,
   exactly as `algenta serve` honours it). Lane A speaks that driver's own protocol; it is not
   `conform_generate_cuda`'s, and the adapter says so on the page.
2. Run the Space on `h100` ($4.50/h, `request_space_hardware(REPO, "h100")`): the wheel's
   `sm_90a` engine loads there and lane A measures the f32 conformance engine — a real number
   for what ships, still not the published packed-int8 graph configuration, and not the L4
   cell. The page's precision cell says which engine ran either way.

`PROBE_ENGINE_TARGET_GATE=off` skips the gate and lets the CUDA loader decide (the lane then
fails with `engine_run_failed` and the loader's last line); it exists for a device the table
does not know. `PROBE_ENGINE_CUDA_TARGET=sm_NN` declares the target of a binary that has no
manifest beside it.

## The sm_89 packed-int8 graph engine (lane A's second protocol)

What was built (2026-09-24, from `6029d6af0`, the staged Mojo tree identical to HEAD):
`benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo` over
`mojo/engine/residentk/session_cuda_p3_graph.mojo` (+ `session_cuda_p3`, `kernels_packed3`),
`mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 -I mojo/engine` — the
L4 ledger's define set verbatim ("p3 graph decode driver: -D ALGENTA_GPU -D ALGENTA_CUDA",
default v4 packed3 kernels, default staging tier 3072 = what Qwen3-0.6B needs, no tensor-core
shim: `TC_SHIM_BUILD` is off without `-D ALGENTA_TC_SHIM` and the driver links no cuBLAS or
cudart). Built in an `ubuntu:22.04` linux/amd64 container (pulled by digest, emulated on the
arm64 Docker host) with the pinned toolchain from `mojo_env/pixi.lock` (Mojo 1.0.0 ed45d567,
MAX 26.5.0), following `.github/scripts/build_cuda_engine_linux_amd64.sh` minus the CUDA
toolkit and the shim, `-Xlinker -rpath -Xlinker '$ORIGIN'`; the runtime closure derived by
`ldd` against the pixi env and bundled beside the binary (`libKGENCompilerRTShared.so`,
`libAsyncRTMojoBindings.so`, `libAsyncRTRuntimeGlobals.so`, `libMSupportGlobals.so`, conda's
`libstdc++.so.6` and `libgcc_s.so.1`; no `libMGPRT`, no `libcuda.so.1` DT_NEEDED — the driver
is dlopen'd on the host), every ELF retagged `RUNPATH $ORIGIN` with the pinned PyPI patchelf
0.19.1 (never apt's 0.14.3) and gated with `scripts/hf_kernels/elf_check.py` (7/7
page-congruent), the embedded PTX carrying `.target sm_89` in every module, the closure
resolving with nothing on `LD_LIBRARY_PATH`. The GPU-less smoke: the binary runs `main()`,
parses a checkpoint header, accepts a 256-id prompt, and stops where a device is needed — the
composed session's constructor, `Failed to open library "libnvidia-ml.so.1"` (exit 1 with the
Mojo "Unhandled exception" line; the driver has no usage path and no exit-2 form; without a
checkpoint it is `Failed to open file '<dir>/manifest.json'`, exit 1). Scripts,
outputs, logs and `BUILD.md` (every command, the ELF check, the sha256 of every file, the
wall time) live in `algenta-tooling/cuda-engine-sm89/` on the SSD; `manifest.json` beside the
binary declares `engine.name`, `sha256`, `cuda_target: sm_89`, `comptime_defines`,
`bundled_shared_libraries`, `source_commit`, `built_utc`, the toolchain and the smoke
results (unsigned: `signed: false`).

The driver's protocol, as read end to end in its source:

- argv: `[<checkpoint dir>] [--checkpoint <dir>] [--runs N]`; default `/tmp/qwen3smoke`,
  default 20 timed runs. The checkpoint is the same `{manifest.json, weights.blob}` f64 dump
  the wheel engine and the Hub `DecodeSession` read; the driver reads the prompt from the
  manifest's `input_ids` (no prompt option). No `--max-new`: gen=64 and gen=256 are fixed in
  the source (the published cell's two columns), as is the 16-token oracle.
- output, in order: the header (`qwen3_p3_graph_cuda: checkpoint = … | d_model = … |
  n_prompt = … | max_ctx = 1024`), `device:`, `one-time load (…): <ms> ms`, `captured replay
  nodes per token: N (vs M per-dispatch enqueues per token)`, `graph-arm packed3 kernels:
  <set>`; then the gates, each ending in `Gn RESULT: PASS —` or `FAIL —` (G0: 16 greedy
  tokens through one graph chain against the oracle, `ORACLE MISMATCH at generated token k :
  got x want y` per miss, exit 1; G1: 3 seeds x 128 steps graph == per-dispatch, exit 1 on a
  flip; G2: `n_steps= 32 : graph-p3 <ms>/step vs per-dispatch-p3 <ms>/step` at 32/64/128/256,
  flat within 10 % and strictly faster, exit 1 otherwise); then `Throughput (decode-only;
  prefill excluded from the timed window), N timed runs per cell (1 untimed warmup each):` and
  for gen 64 and gen 256 three arms (`graph-p3` — the subject, `f32-graph`, `per-dispatch-p3`),
  each `median <ms> ms | rel IQR <pct> % | outliers <n> | <tok/s> tok/s (PASS|FLAGGED, frozen
  5%)`, two `vs ledger` lines against the A100 llama.cpp rows, and `qwen3_p3_graph_cuda: done
  (G0 + G1 + G2 all PASS)`, exit 0. No prefill time, no `CONFORM_*` line, and on success no
  token: the 16 the oracle checked are the driver's `_oracle_token` sequence.
- the oracle is bound to the campaign fixture: `"The capital of France is Paris. " * 36 + "The
  capital of France"`, 256 ids (`785`, the seven-id cycle 36 times, then `6722 315 9625`;
  verified byte-exact with `algenta.tokenizer` on the pinned snapshot), continuation
  `374 12095 13 576 6722 315 9625 374` then the seven-id cycle. The probe's battery prompt (the
  eight-id cycle of `algenta_bench.py`) is a different sequence, so a run that selects this
  driver converts and races every lane on the campaign fixture.

The adapter (`probe.py`, `probe_core.py`, keyed on the resolved binary's name, which the
manifest beside it must repeat):

- `probe_core.engine_protocol_of` / `probe_core.active_prompt_fixture`: `ALGENTA_CUDA_ENGINE`
  naming `qwen3_p3_graph_cuda` selects the protocol and, unless `PROBE_PROMPT_FIXTURE` says
  otherwise, the `campaign` fixture; `race_prompt_ids` serves the active fixture to every
  stage, `convert` bakes it, the pins and the page name it (`prompt_fixture`).
- `probe.checkpoint_fixture_gate`: before launch, the converted manifest's `input_ids` must be
  the active fixture and, for this driver, the fixture must be `campaign`
  (`engine_prompt_fixture_mismatch`); a checkpoint left on a persistent work dir with the other
  fixture (or an unreadable manifest) is removed at `convert` and converted again (logged, and
  recorded as `stale_checkpoint_removed`); `conversion_prompt_mismatch` remains for the one
  case the stage cannot recover from, the directory not going.
- `probe.run_p3_engine_once`: one launch, `<checkpoint> --runs 3` (the probe's discipline; the
  published cell used 20), `LD_LIBRARY_PATH` led by the engine's directory, nvidia-smi sampled
  through the whole launch, 540 s ceiling inside the stage's 600 s;
  `probe_core.parse_p3_engine_output` reads the prints — the driver's refusals and verdicts
  from stdout alone, a gate passing only on its `PASS` form or a `0 total flip(s)` line (any
  other count is `engine_gate_failed` with the count); stderr only for the runtime's
  no-driver line (`Failed to open library "libnvidia-ml.so.1"` / `"libcuda.so.1"`) and the
  no-accelerator sentence, any other non-zero exit being `engine_run_failed` with the
  runtime's exception line or the last stderr line (fail-closed codes:
  `engine_binary_not_cuda_build`, `engine_no_gpu`, `engine_resident_refused`,
  `engine_oracle_mismatch`, `engine_gate_failed`, `engine_run_failed`, `engine_no_timing`,
  `engine_prompt_mismatch`); `probe_core.p3_cells` puts the `graph-p3` arm's medians under
  `runs["64"]` / `runs["256"]` with the other two arms beside them.
- the record and the page: `decode_tok_per_s` is the driver's gen tokens over the replay
  window's median (the published definition); `prefill_tok_per_s` and `ttft_ms` are None with
  the note that the driver prints no prefill time; `load_s` is the one-time load; `tokens` are
  the 16 oracle-checked ids (`tokens_verified: 16`), the identity compares them with the CPU
  reference's first 16 (`16/16, oracle 16/16`) and the ratio is printed when llama.cpp's stream
  starts with them (`ratio.tokens_compared`); `gates`, the G2 table, the captured node count,
  the kernel set and the build facts (`built <date> from <commit>`, Mojo version, sha256) are
  on the page under "Algenta engine"; the lane's precision reads "packed-int8 resident
  weights, captured-graph decode". `engine_protocol_unknown` refuses any other binary name,
  `engine_closure_incomplete` a manifest whose bundled libraries are not all beside the binary.

Tests (`tests/spaces/test_gpu_probe.py`): the parser against the driver's real lines, the
launch against a fake driver script that prints them, the fixture selection and the two
fixtures' ids against the derivation above, the gates, the lane view, the ratio over the
verified prefix, the page copy, the Dockerfile and `.gitignore` conventions, the deploy notes.

Not verifiable without a GPU: that the sm_89 image loads on the L4 and the driver's three gates
pass there (they did on the L4 of the campaign at `f9bfda32`; this build is from `6029d6af0`),
the measured figures, the nvidia-smi peak, the Space's LFS handling of the closure, and the
symlink at `/home/user/engine` inside the built image.

## Files

| File | Purpose |
|---|---|
| `README.md` | Hub card (`sdk: docker`, `hardware: l4x1`, `app_port: 7860`) and what the probe measures. |
| `Dockerfile` | Three stages, nothing compiled. `ghcr.io/ggml-org/llama.cpp@sha256:11b26418…` (tag `server-cuda-b10223`, the multi-arch index by digest) is stage `llama`: its `/app` — `llama-server`, the `libllama*` / `libggml*` closure, the `libggml-cuda.so` and `libggml-cpu-*` backends — is copied to `/opt/llama/bin`. Stage `converter` (the runtime base again) shallow-fetches commit `11924d4c17` for `convert_hf_to_gguf.py`, `conversion/` and `gguf-py` and writes `COMMIT`, `BUILD`, `IMAGE_DIGEST`; git lives there only. `nvidia/cuda:12.8.1-runtime-ubuntu24.04` (by digest), `NVIDIA_DISABLE_REQUIRE=1`, `libgomp1` + `libssl3t64`, uv by digest, CPython 3.14, exact pins (the converter's `sentencepiece` and `protobuf` among them), `llama-server --version` checked against the build argument before torch installs — with no `load_backend: failed` line, `GGML_BACKEND_PATH` unset — then `ARG ALGENTA_CUDA_ENGINE` (the Space variable reaches the build only as a build argument; kept as `ENV`) declared after the `/home/user/engine` symlink and `USER user`, so the bake inspects the engine lane A will resolve; bake and offline verify as uid 1000, `HF_HUB_OFFLINE=1`. |
| `requirements.txt` | torch 2.9.1+cu128, kernels 0.17.1, huggingface_hub 1.26.1, transformers 5.17.0, safetensors 0.8.0, tokenizers 0.23.2, numpy 2.5.3, algenta 1.0.28, algenta-runtime-native 1.0.7 (pinned on its own), tqdm / pyyaml / requests (gguf-py), fastapi, uvicorn. |
| `probe_config.py` | Every pin and fixed input: kernel repo/revision/variant/tier, model repo/revision, the prompt cycle and 256-token length, gen=64 / gen=256, runs and warm-ups, the engine wheel facts, the llama.cpp image (tag, index digest, amd64 digest), build, commit and the architectures it carries next to the published cell's own build/commit/architecture, the published figures with their pages, stage budgets, the run budget, hardware and price. |
| `probe_core.py` | Stdlib-only logic: phase machine (soft lanes, the `decode` → `kernel` dependency), driver/capability gates, revision/variant/tier/library gates, the engine compile-target gate, the `CONFORM_*` and `/completion` parsers, medians (`run_summary`), identity with the 16-token oracle, the lane views (`race_view`), the `/health` and `run.json` shapes. |
| `probe.py` | The eight stages, one subprocess each: `driver`, `kernel`, `convert`, `engine`, `llama`, `decode`, `baseline`, `reference`; the nvidia-smi memory sampler; the run/cell loop. |
| `app.py` | FastAPI on 7860: `/` (plain page), `/health`, `/run.json`; the orchestrator thread with the run budget. |
| `fetch_assets.py` | `--bake` (kernel snapshot + model snapshot into `HF_HOME`, the wheel's engine manifest read and judged against the requested hardware, the F16 GGUF converted) and `--verify` (offline resolution of all of it). |
| `hf_ua_shim.py` | The flagship's user-agent fix for kernels 0.17.1 on huggingface_hub 1.x, carried verbatim. |
| `DEPLOY.md` | The by-hand deploy, and how the sm_89 engine is shipped beside the app (`engine/`, copied in at deploy time, `ALGENTA_CUDA_ENGINE` set as a Space variable). |
| `.gitignore` | `engine/`: the packed-int8 graph engine and its closure are proprietary and above the 500 KB commit ceiling; they travel with the upload, never with git. |

## The phases and their codes

| Phase | What runs | Fail-closed codes | Stops the run? |
|---|---|---|---|
| `driver` | `nvidia-smi`, `/proc/driver/nvidia/version`, libcuda via ctypes (`cuInit`, `cuDriverGetVersion`, device name, capability, memory), `torch.cuda`, the idle `memory.used` | `nvidia_smi_missing`, `libcuda_missing`, `no_gpu`, `driver_below_floor`, `compute_capability_unsupported`, `torch_cuda_unavailable` | yes |
| `kernel` | `get_kernel(revision=<pinned>, backend="cuda")`; snapshot sha, variant, native manifest tier 6144, `runtime()` and the library it chose vs the device's capability | `kernel_revision_mismatch`, `kernel_variant_mismatch`, `kernel_tier_mismatch`, `kernel_library_mismatch`, the glue's own `KernelError` codes | no (lane C becomes `upstream_failed`) |
| `convert` | `prepare_model_checkpoint(snapshot, race_prompt_ids(256), weights_dtype="f64", backend="cuda")`, timed; reused when the blob on disk carries the run's prompt (its manifest's `input_ids`), a checkpoint carrying the other fixture removed and converted again | `model_snapshot_missing`, `disk_insufficient`, `conversion_incomplete`, `conversion_prompt_mismatch` (a stale checkpoint that could not be removed), `prompt_fixture_unknown`, algenta's `InferenceError` codes | yes |
| `engine` | Lane A: `resolve_engine("cuda")` → the binary; manifest read, sha256 checked, `engine_target_gate(cuda_target, cc)`, host libraries loaded; then `<engine> <ckpt> --max-new 64 --prompt-len 256` with `LD_LIBRARY_PATH` led by the wheel's directory, 1 warm-up + 3 timed, then the same at `--max-new 256` when the gen=64 cell took under 240 s; nvidia-smi sampled at 4 Hz for the peak | `engine_resolver_missing`, `engine_binary_missing`, `engine_manifest_invalid`, `engine_sha_mismatch`, `engine_target_mismatch`, `engine_host_library_missing`, `engine_binary_not_cuda_build`, `engine_no_gpu`, `engine_refused_model`, `engine_run_failed`, `engine_run_timeout`, `engine_no_tokens`, `engine_no_timing`, `engine_prompt_mismatch`; with the packed-int8 graph driver selected (`ALGENTA_CUDA_ENGINE`): `<engine> <ckpt> --runs 3` once, and `engine_protocol_unknown`, `engine_closure_incomplete`, `engine_prompt_fixture_mismatch`, `engine_resident_refused`, `engine_oracle_mismatch`, `engine_gate_failed` | no |
| `llama` | Lane B: `llama-server --version` (build and commit checked against the pins, fail-closed; every launch with `LD_LIBRARY_PATH` led by `/opt/llama/bin` and `GGML_BACKEND_PATH` unset — ggml's registry finds the backends beside the launcher, and a refusal line from it is `llama_backend_load_failed`), then `llama-server --verbose --list-devices` must enumerate a `CUDA` device (`llama_cuda_backend_missing` otherwise: lane B never races `-ngl 99` on the CPU), then `llama-server -m <gguf> --host 127.0.0.1 --port 8093 -ngl 99 --parallel 1 -c 1024`, `/health` until ok, `/completion` with `{"prompt": <256 ids>, "n_predict": N, "temperature": 0, "top_k": 1, "samplers": ["top_k"], "cache_prompt": false, "return_tokens": true}`; `prompt_n` must be 256 and `tokens_cached` 0; 1 warm-up + 3 timed at 64, then 256 under the same budget rule; the server killed after | `llama_build_missing`, `llama_gguf_missing`, `llama_version_mismatch`, `llama_backend_load_failed`, `llama_cuda_backend_missing`, `llama_server_failed`, `llama_request_failed`, `llama_timings_missing`, `llama_tokens_missing`, `llama_prompt_mismatch`, `llama_prompt_cached`, `llama_short_generation` | no |
| `decode` | Lane C: `DecodeSession(checkpoint, ids, max_new_tokens=64)` opened, stepped and closed; 1 warm-up session + 3 timed | `checkpoint_missing`, `decode_session_missing`, `upstream_failed`, the `KernelError` codes | no |
| `baseline` | Lane D: `from_pretrained(snapshot, dtype=…)` on the device, `generate(max_new_tokens=64, do_sample=False, num_beams=1)` through the `StepClock` streamer, one lane per dtype, 1 warm-up + 3 timed | per lane `baseline_oom`, `baseline_load_failed`, `baseline_generate_failed`, `baseline_step_count_mismatch`, `baseline_lane_missing` | no |
| `reference` | transformers float32 greedy on the CPU, 8 threads, the same 256 ids, 64 tokens, per-step top-2 logit margins | transformers' exceptions as their class name | yes |
| `record` | `run.json`: the health body plus `decision` and the three evidence rows | `run_incomplete` | — |

Two orchestrator codes apply to lanes without running them: `upstream_failed` (`decode` when
`kernel` is not ok) and `run_budget_exhausted` (a lane that would start more than
`RUN_BUDGET_S` = 1200 s into the run). A lane stage that crashes or overruns its own budget is
`stage_crashed` / `stage_timeout` on its block. The reference and the record always run.

## The figures, defined once

`probe_core.run_summary` is the median over the timed runs of a cell; `race_view` is what the
page renders and `/health.race` carries.

- decode tokens per second, the hero pair: each engine's own definition, the one the published
  cells used. Algenta: `CONFORM_TIMING decode_tok_s` = the tokens after the first over the
  time of their steps. llama.cpp: `timings.predicted_per_second`. The Hub and transformers
  lanes use the Algenta definition over their per-step times (`step_timings.decode_tok_per_s`).
- prefill tokens per second: the 256 prompt tokens over the prefill time (`prefill_ms` /
  `prompt_ms`); time to first token is that prefill, since the first token is computed by it.
  The Hub lane pays its prefill inside the session open with the f64→f32 upload, so its time to
  first token is the session open and it has no prefill rate of its own.
- device memory: for lanes A and B the peak `nvidia-smi memory.used` while the lane's process
  ran, minus the idle baseline (`GpuMemorySampler`); for C and D `mem_get_info` before minus
  after the load or open, plus torch's `max_memory_allocated` for D.
- identity: every lane's gen=64 tokens against the CPU reference (`parity_report`): `64/64`,
  the first divergent index and the reference's top-2 margin there, and the published gate's
  form, `oracle 16/16`. The record's `decision` is `ok` when every lane that ran matched,
  `parity_failed` when one diverged, `no_lane_ran` when none ran.
- the ratio: Algenta over llama.cpp on the gen=64 decode rate, printed only when both lanes ran
  and decoded the same tokens; gen=256 and prefill ratios beside it when available.
- steady per-token (lanes C and D only): the mean of steps 3 onwards, kept from the earlier
  runs; `steady_tok_per_s` is None when that mean is not above zero (an explicit guard, not a
  falsy one — Codna's finding on #1172).

## Budget on the L4

Expected: driver ~5 s, kernel ~7 s, convert ~30 s (4.8 GB f64 blob), engine ~1–2 min when it
runs (each launch reads the blob and uploads it; on `l4x1` with wheel 1.0.7 the gate refuses in
under a second), llama ~1 min (server load ~10 s, 8 requests), decode ~1–2 min (4 session
opens), baseline ~1 min, reference ~30 s: about 6–8 minutes from boot to `run.json`, inside the
20-minute run budget; stage ceilings are in `STAGE_TIMEOUTS_S`. The Space is paused after the
read. The image build is not GPU time and compiles nothing: `llama-server` is copied from the
prebuilt image and the converter is a shallow checkout (minutes); the 1.2 GB model snapshot
plus torch cu128 (10–20 min) are the cost. Run 15 built llama.cpp from source and the Hub's
builder cut the compile off after 62 minutes at step 310 of 442 (`BUILD_ERROR`, no error
line: its time limit), which is why lane B comes prebuilt.

`t4-small` stays the fallback hardware: the prebuilt image carries PTX for the T4's sm_75 so
lane B runs there, lane A only when the selected engine's target loads there (the wheel's
`sm_90a` and the shipped `sm_89` build do not), and the published L4 cell needs an L4.

## Lane B's binary

`ghcr.io/ggml-org/llama.cpp` at tag `server-cuda-b10223`, the multi-arch index
`sha256:11b2641870148c90fa99353f91aab7572c6f0e6c66e96aca49af88dd9c26a00b` (its linux/amd64
manifest `sha256:46e98996dc99f01079018769dd7531707c206c261584525474e92a343143a001`), build
10223, commit `11924d4c17abc27383376a1ac6a24fa3e36c1c0c` (2026-08-01; resolved through the tag
ref `b10223` on GitHub). The rule that chose it: the versioned `server-cuda-b<build>` tag
closest to and not below the published `b10210` — the registry's full tag list (11,952 tags,
paginated) has no `b10210` server image, `b10223` is the next one, 13 builds later; the moving
`server-cuda` tag was b11151 on 2026-09-24 and is not used. The image is built by
`.devops/cuda.Dockerfile` at that commit on `nvidia/cuda:12.8.1-devel-ubuntu24.04` with
`-DGGML_NATIVE=OFF -DGGML_CUDA=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON` and ggml's
default architecture list for CUDA 12.8, and runs on `nvidia/cuda:12.8.1-runtime-ubuntu24.04`,
the probe's own base: `libggml-cuda.so` links `libcudart.so.12` (12.8.90), `libcublas.so.12` /
`libcublasLt.so.12` (12.8.4.1), `libnccl.so.2` (2.25.1), `libgomp.so.1` and the driver's
`libcuda.so.1`; `llama-server` links `libllama-server-impl.so`, `libllama-common.so.0`,
`libmtmd.so.0`, `libllama.so.0`, `libggml.so.0`, `libggml-base.so.0`, `libssl.so.3` /
`libcrypto.so.3` and `libgomp.so.1`. All of those but `libgomp1` are in the base image;
`libgomp1` and `libssl3t64` are installed by name. Its fatbins carry PTX for sm_50, 61, 70,
75, 80 and 90 and cubins for sm_86, 89 and 120a (read from the file, 2026-09-24): the L4 runs
an sm_89 cubin as the published source build did, the T4 runs sm_75 from PTX.

Not the published cell's build. The pages' opponent was `b10210` (`000547513f`) compiled from
source for sm_89 alone; the page and the record name build 10223 and the image, and never
claim the identical build. `probe_config.py` keeps both sets of values
(`PUBLISHED_LLAMA_CPP_*` next to `LLAMA_CPP_*` / `LLAMA_IMAGE_*`).

Two quirks the Dockerfile and the launch handle. The image's launcher and libraries carry
RUNPATH `/app/build/bin:` — the build tree, then an empty element, i.e. the working directory —
so they load only from `/app` of that image (`cd / && /app/llama-server --version` fails with
`libllama-server-impl.so: cannot open shared object file`); the probe copies `/app` to
`/opt/llama/bin` and launches every lane-B process, `--version` included, with
`LD_LIBRARY_PATH=/opt/llama/bin:…` and nothing else: ggml's registry (`GGML_BACKEND_DL`)
searches the launcher's own directory and the working directory for `libggml-cuda.so` and the
CPU variants (`ggml_backend_load_best`, `ggml/src/ggml-backend-reg.cpp` at the commit).
`GGML_BACKEND_PATH` is not a search path but ONE out-of-tree backend library, loaded out loud
after the search (`ggml_backend_load_all_from_path`, lines 588-592 of that file): set to the
directory it printed `load_backend: failed to load /opt/llama/bin: … Is a directory` on every
start (run 16), so no launch sets it and an inherited value is dropped. The bake sets it once,
to `/opt/llama/bin/libggml-cuda.so`, so that backend's loader says why it will not load on the
Hub's GPU-less builder — `libcuda.so.1: cannot open shared object file` (`libggml-cuda.so` links
the driver), tolerated and recorded; any other reason is `llama_cuda_backend_unloadable`. The
registry's `loaded … backend from` lines are INFO and show only with `--verbose` before
`--list-devices`. On the Space the check that matters runs before every launch: `--verbose
--list-devices` must enumerate a `CUDA` device, else lane B fails closed with
`llama_cuda_backend_missing` instead of racing `-ngl 99` on the CPU. And `--version` has two shapes across builds
(`version: 10223 (11924d4c1)` here, `version: 0.5.0-dev (build 11151, commit bd4f514db)` from
later builds); `parse_llama_version` reads both, `verify_llama_version` fails closed on
anything but the pinned build and a prefix of the pinned commit.

The converter (`convert_hf_to_gguf.py`, `conversion/`, `gguf-py`) is a shallow checkout of the
same commit `11924d4c17` in a stage of its own (`git rev-parse HEAD` asserted), so the F16 GGUF
matches the server; the bake checks the stage's `COMMIT`, `BUILD` and `IMAGE_DIGEST` files
against the pins before converting. To move to another build: pick the tag, resolve the index
digest (`HEAD /v2/ggml-org/llama.cpp/manifests/<tag>` on ghcr.io with a pull token) and the
commit (`/repos/ggml-org/llama.cpp/git/ref/tags/b<build>`), set the three values in the
Dockerfile's `ARG`s and `FROM`, `LLAMA_IMAGE_*` and `LLAMA_CPP_*` in `probe_config.py`, and
re-read the fatbin architectures if the CUDA base changed.

The Qwen3-1.7B Hub-kernel parity run of runs 12–14 is not kept as a second section: the same
kernel and the same path run on the 0.6B as lane C, and the 1.7B would add 4 GB of image, 14 GB
of disk and about three minutes for no new comparison.

## Run, read, pause

`DEPLOY.md` in the Space directory is the full sequence. In short: `create_repo(private=True)`,
`upload_folder(delete_patterns=["**"])`, `request_space_hardware("l4x1", sleep_time=900)`,
poll `get_space_runtime` until the new revision is `RUNNING` (an L4 stalled 31 minutes without
capacity on 2026-09-22; allow an hour), read `/health` with the token until `status` is `ok` or
`error`, save `/run.json` under `docs/hf-kernels/evidence/artifacts/`, `pause_space`. The
scripts `deploy_gpu_probe*.py` in `algenta-tooling/scripts` do exactly this; for the race, change
their `request_space_hardware(REPO, "t4-small", sleep_time=900)` to `"l4x1"` and the output
directory to `gpu-probe-run15`.

Locally, without a GPU, the helpers, the routes, the engine subprocess protocol (against a fake
engine script) and the llama-server protocol (against a fake loopback server) are tested by
`python -m pytest tests/spaces/test_gpu_probe.py`; the driver stage on a GPU-less host answers
`nvidia_smi_missing`, never a traceback. The image cannot be built or run on the build Mac (the
image targets x86_64 CUDA).

## Cost

`l4x1` at $0.80 per hour (Hub price read 2026-09-24), paused between runs. One run is about
10 minutes of GPU time from `RUNNING` to pause, about $0.15; paused, the Space costs nothing.
The fleet budget line for the probe stays the one-off in `docs/spaces/README.md`.

## Not verified on the build Mac

Everything CUDA: the driver gate, the engine launch (and whether the `sm_90a` refusal is the
only obstacle on an L4), the prebuilt llama-server's run on the device (its load without a GPU,
from any working directory with the launch variables, was verified in the runtime base on the
Mac: `--version` reports build 10223, every library but the driver's `libcuda.so.1` resolves),
the GGUF conversion inside the image, `get_kernel(backend="cuda")`, the native load, the Hub decode, the
transformers lanes on the device, and the image build itself: the Mac is arm64 and the image
targets x86_64 CUDA. What the Mac verified is everything the Space decides with (the gates
including the engine target gate against the wheel's real manifest values, the parsers against
the engine's and llama-server's documented output, the medians, the identity rule, the lane
views, the health and record shapes) against the run-12 data and the run-13/14 records, the
routes and the page against a fake stage runner, the engine and llama protocols against fakes,
the wheel's manifest facts (read from the 1.0.7 wheel on the SSD), and the packaging (pins,
frontmatter, copy lint, ruff). The first real race numbers come from the next run.

## Earlier runs

`docs/hf-kernels/evidence/artifacts/gpu-probe-run12-*.json` (2026-09-22, T4, Qwen3-1.7B,
`GPU-SPACE-DRIVER-001` / `GPU-SPACE-PARITY-001`), `gpu-probe-run13-*.json`
(`GPU-SPACE-PARITY-002`) and `gpu-probe-run14-*-side-by-side.json` (`GPU-SPACE-SIDE-BY-SIDE-001`)
still replay through today's views and are what `test_gpu_probe.py` renders: the race lanes say
the record predates them, the secondary rows carry their own figures.
