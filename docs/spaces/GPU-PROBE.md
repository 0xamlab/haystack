# The GPU probe — `thyn-ai/algenta-gpu-probe`

Internal notes for `apps/spaces/gpu-probe/`. Module docstrings are the reference; this page is
the runbook view.

## What it is

A private Docker Space on `t4-small` (Tesla T4, sm_75, 15 GB) that boots, runs Qwen3-1.7B
through the published CUDA decode kernels of `thyn-ai/algenta-llm`, compares eight greedy
tokens with a transformers float32 CPU reference, runs the same decode without Algenta (plain
transformers on the same GPU, float32 and float16) and serves the record with the lanes side
by side. It is the tracked
rebuild of the probe that produced `GPU-SPACE-DRIVER-001` and `GPU-SPACE-PARITY-001` on
2026-09-22 (run 12, artifact
`docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json`): that Space's
source lived in a scratch directory and was lost, and the Space itself was deleted by mistake on
2026-09-24. Everything the rebuild pins comes from the artifact and the evidence rows; the one
value brought forward is the kernel revision, which moved from `92ef06d7` (REPUBLISH-004) to
`8ae3da4a` (REPUBLISH-006, 2026-09-24) and is asserted equal to the flagship's
`hubkernel.FROZEN_CAPPED_V1_SHAS` by `tests/spaces/test_gpu_probe.py`.

It is not in `apps/spaces/spaces.toml`: the fleet manifest has no `private` key, requires
`api_names`, and its tests assert the fleet is the flagship alone with no GPU stage; a table
would also put a paid GPU on `deploy.py --all`. `apps/spaces/gpu-probe/DEPLOY.md` has the exact
`huggingface_hub` steps instead (create private, upload, `t4-small`, poll, read, pause).

## Files

| File | Purpose |
|---|---|
| `README.md` | Hub card (`sdk: docker`, `hardware: t4-small`, `app_port: 7860`) and what the probe proves. |
| `Dockerfile` | `nvidia/cuda:12.8.1-runtime-ubuntu24.04` by digest, `NVIDIA_DISABLE_REQUIRE=1`, uv by digest, CPython 3.14, exact pins, bake and offline verify as uid 1000, `HF_HUB_OFFLINE=1`. |
| `requirements.txt` | torch 2.9.1+cu128, kernels 0.17.1, huggingface_hub 1.26.1, transformers 5.17.0, safetensors 0.8.0, tokenizers 0.23.2, numpy 2.5.3, algenta 1.0.28, fastapi, uvicorn. |
| `probe_config.py` | Every pin and fixed input: kernel repo/revision/variant/tier, model repo/revision, prompt, `max_new_tokens = 8`, run 12's recorded ids, stage budgets. |
| `probe_core.py` | Stdlib-only logic: phase machine (with the soft `baseline` phase), driver/capability gates, revision/variant/tier/library gates, parity comparison, the shared step timings, the baseline block and the side-by-side lanes, the `/health` and `run.json` shapes. |
| `probe.py` | The six stages, one subprocess each: `driver`, `kernel`, `convert`, `decode`, `baseline`, `reference`. |
| `app.py` | FastAPI on 7860: `/` (plain page), `/health`, `/run.json`; the orchestrator thread. |
| `fetch_assets.py` | `--bake` (kernel snapshot at the pinned revision + model snapshot into `HF_HOME`, tier asserted, tree listing pruned) and `--verify` (offline resolution). |
| `hf_ua_shim.py` | The flagship's user-agent fix for kernels 0.17.1 on huggingface_hub 1.x, carried verbatim. |
| `DEPLOY.md` | The by-hand deploy. |

## How the phases map to run 12

| Phase | What runs | Run-12 counterpart (`steps.*`) | Fail-closed codes |
|---|---|---|---|
| `driver` | `nvidia-smi`, `/proc/driver/nvidia/version`, libcuda via ctypes (`cuInit`, `cuDriverGetVersion`, device name, capability, memory), `torch.cuda` | `driver` (580.178.04, CUDA API 13.0, cc 7.5, 15.8 GB) | `nvidia_smi_missing`, `libcuda_missing`, `no_gpu`, `driver_below_floor`, `compute_capability_unsupported`, `torch_cuda_unavailable` |
| `kernel` | `get_kernel(revision=<pinned>, backend="cuda")`; snapshot sha, variant, native manifest tier 6144, `runtime()` and the library it chose vs the device's capability | `gpu.kernel` (variant resolved in 0.22 s, `sm_75` selected, init 0.11 s) and `image.build_facts.kernel` (tier 6144) | `kernel_revision_mismatch`, `kernel_variant_mismatch`, `kernel_tier_mismatch` (run 11's negative control), `kernel_library_mismatch`, the glue's own `KernelError` codes |
| `convert` | `prepare_model_checkpoint(snapshot, prompt_ids, weights_dtype="f64", backend="cuda")`, timed; reused when the blob is on disk | `convert` (81.7 s, 13,764,599,808 bytes, 310 tensors) | `model_snapshot_missing`, `disk_insufficient`, algenta's `InferenceError` codes |
| `decode` | `DecodeSession(checkpoint, ids, max_new_tokens=8)`: open time, per-step ms, tokens, positions, EOS flag, device memory before/after | `gpu.decode` (open 41.67 s, steps 0.24 / 177.22 / 26.7… ms, `[9856, 13, 15920, 315, 279, 2701, 374, 830]`) | `checkpoint_missing`, `decode_session_missing`, `resident_dimension_too_large` and the other `KernelError` codes |
| `baseline` | The same decode without Algenta: `AutoModelForCausalLM.from_pretrained(snapshot, dtype=…)` moved to the device with `.to("cuda")`, `generate(max_new_tokens=8, do_sample=False, num_beams=1)` with the same ids and the model's own EOS handling; one lane per dtype (`float32`, then `float16`), each its own load, one warm-up generate (excluded), then the timed generate through the `StepClock` streamer; the model deleted and the cache emptied between lanes | none: run 13 predates the stage (its record renders with the section saying so) | per lane: `baseline_oom`, `baseline_load_failed`, `baseline_generate_failed`, `baseline_step_count_mismatch`, `baseline_lane_missing`; the phase is soft, so a crash or timeout is `stage_crashed` / `stage_timeout` on its block and the run goes on |
| `reference` | transformers float32 greedy on the CPU, 4 threads, same ids; per-step top-2 logit margins; tokenizer agreement | `reference` (load 5.6 s, generate 4.1 s, same eight ids, tokenizers agree) | transformers' exceptions as their class name |
| `record` | `run.json`: the health body (the `baseline` block included) plus `decision` and the two evidence rows' fields | the artifact's `parity`, `decision`, `evidence` | `run_incomplete` |

Stages run in subprocesses so a native abort is `stage_crashed` with the signal on `/health`
and the reference's 11 GB RSS is returned before the page is served (run 12 measured 11.2 GB
for the reference and 4.5 GB for the decode on a 16 GB host). Budgets are in
`probe_config.STAGE_TIMEOUTS_S`; a stage past its budget is `stage_timeout`.

### The lanes, side by side

The page's first section under the verdict, "Side by side on the same Tesla T4", is one column
per lane and the same rows for each: tokens decoded (marked when they differ from the Algenta
lane), parity vs the CPU reference, load / session open, time to first token, steady per-token
time, tokens per second (steady and over all steps), first step and warm-up, device memory,
precision, stack. `/health` and `/run.json` carry the same facts in the `baseline` block (the
stage's report with each lane's `timings` and `parity` added); `probe_core.side_by_side` is the
view the page renders and is unit-tested.

| Lane | What runs | Precision | Load | Time to first token | Warm-up |
|---|---|---|---|---|---|
| Algenta CUDA kernels | `DecodeSession` over the f64 blob | f32 resident, uploaded from the f64 blob | session open (`open_s`): the upload and the prompt prefill | = session open; step 1 is sub-millisecond because the prefill ran at open | step 2, inside the timed steps (about 190 ms in run 13) |
| transformers CUDA · float32 | `generate` on the device, greedy | float32 (like for like with the resident f32) | `from_pretrained` + `.to("cuda")` | step 1 of the timed generate: the prefill of the 12 prompt tokens | one generate before the timed one, excluded; its own figures are recorded under `warmup` |
| transformers CUDA · float16 | the same | float16 (what a T4 is usually run at; no bfloat16 on sm_75) | the same | the same | the same |

The fairness rule: same prompt ids, the same eight greedy tokens requested, the same GPU in the
same run, each lane's precision printed next to its numbers, and never a number that was not
measured in that run — a lane that could not run is shown as unavailable with its code. The
only ratio the page prints is the ratio of steady per-token times, and only for a lane that
decoded the same tokens as the Algenta lane.

What each timing is (`probe_core.step_timings` is the one definition for every lane):

- per-step ms for transformers: the `StepClock` streamer timestamps every `put` from
  `generate`. transformers calls `put(input_ids.cpu())` once with the prompt before the prefill
  and `put(next_tokens.cpu())` after each token is chosen; `.cpu()` synchronises the device, so a
  timestamp is the moment that token is on the host. Step 1 is measured from the timed call's
  start and is the prefill (generate's setup, the forward pass over the prompt, the argmax, the
  copy); every later step is the gap between two consecutive tokens (the stopping check, the
  cache update, one forward pass over one token, the argmax, the copy) — the per-token cost a
  caller of `generate` sees. The tokens the streamer saw must equal the returned sequence, or
  the lane fails with `baseline_step_count_mismatch`;
- per-step ms for Algenta: each `session.step()` call's wall time, as before;
- `steady_step_ms`: the mean of steps 3 to n (`STEADY_FROM_STEP = 3`), past the first step and
  the warm-up of either lane; `steady_tok_per_s` = 1000 / `steady_step_ms`, the headline;
- `all_steps_tok_per_s`: n tokens over the sum of all n steps, first step and warm-up included;
- `tok_per_s` (Algenta only): the older headline, 7 tokens over steps 2 to 8 (the warm-up
  included) — 19.67 on the run-13 rerun where the steady figure is 37.2 — kept under its own
  name so earlier records read the same;
- `ttft_s`: for Algenta, open plus the first step, which is the session open; for transformers,
  step 1 of the timed generate;
- device memory: for Algenta, the device's free memory before the session minus after the open
  (`mem_get_info`); for transformers, the same before-minus-after around the load, plus torch's
  `max_memory_allocated` over the load and both generates. The two methods are named on the
  page.

Phase order and why `baseline` sits between `decode` and `reference`: every stage is its own
process, so the GPU is empty at every stage start and the peak device memory is the same in any
order (the f32 lane's weights, about 7 GB, under the T4's 15 GB); what the stage boundary buys
is that the Algenta runtime keeps its resident arena after `close()` (run 13: 7.2 GB still taken
after the session closed) and only the process exit returns it, so the baseline never shares
the device with the session. Running it right after `decode` keeps the two GPU stages back to
back, leaves the CPU reference (11.9 GB RSS, the heaviest host-memory stage) last before
`record` so the page is served with that memory returned, and gives the baseline's safetensors
read a page cache as cold as the session open had (the 13.8 GB blob was written and read
between the two), so the load column is measured under like conditions. Lanes run f32 first
(the like-for-like row), then f16, with `del model`, `gc.collect()` and
`torch.cuda.empty_cache()` between them. The phase is soft: its failure is recorded on its own
block and `reference` and `record` still run, because the comparison beside the verdict is not
the verdict.

The page prints what its own run measured and shows run 12's token ids only under the label
"run 12 recorded". Identifiers (token ids, the staging tier) print plain; quantities (bytes,
MiB) with thousands separators.

## Run, read, pause

`DEPLOY.md` in the Space directory is the full sequence. In short: `create_repo(private=True)`,
`upload_folder(delete_patterns=["**"])`, `request_space_hardware("t4-small", sleep_time=900)`,
poll `get_space_runtime` until the new revision is `RUNNING`, read `/health` with the token until
`status` is `ok` or `error`, save `/run.json` under `docs/hf-kernels/evidence/artifacts/`,
`pause_space`. A paused Space is resumed with `restart_space`, which reruns the probe from boot.

Locally, without a GPU, the helpers and the routes are tested by
`python -m pytest tests/spaces/test_gpu_probe.py`; the driver stage on a GPU-less host answers
`nvidia_smi_missing`, never a traceback. The image cannot be built or run on the build Mac (the
image targets x86_64 CUDA).

## Cost

`t4-small` at $0.60 per hour (Hub price read 2026-09-22), paused between runs. One run is
about 10 minutes of GPU time from `RUNNING` to pause (conversion 82 s, session open 42 s,
reference 20 s, the rest is the Hub scheduling and the read); the image build is not GPU time.
Run 12 billed about $0.02; runs 1 to 9 on `l4x1` about $0.06. Paused, the Space costs nothing.
The fleet budget line for the probe stays the one-off in `docs/spaces/README.md`.

## Not verified on the build Mac

The CUDA path (driver gate, `get_kernel(backend="cuda")`, the native load, the decode, the
transformers baseline on the device) and the image build itself run only on the Space: the Mac
is arm64 and the image targets x86_64 CUDA. What the Mac verified is everything the Space
decides with (the gates, the parity rule, the timings, the baseline block, the side-by-side
lanes, the health and record shapes) against run 12's data and the run-13 record, the routes
and the page against a fake stage runner (the baseline's report is a shape-only fixture there:
no figure of it is a measurement), the `StepClock` arithmetic, and the packaging (pins,
frontmatter, copy lint, ruff). The baseline lanes' first real numbers come from the next run.

## The M3.1 path

This probe is the GPU stage's smallest ancestor: one prompt, one session, one parity check.
M3.1 (`docs/spaces` plan, "M3.1 GPU stage") grows it into the governed-agent Space on `l4x1`:
the same `get_kernel(backend="cuda")` and `DecodeSession`, a boot parity badge over 8 prompts x
64 tokens with the near-tie rule, `/api/status` in the shape the flagship's `gpu_status.py`
already reads (`tok_per_s`, `measured_utc`, `hardware`, `model`, `lane`, `ttft_ms`, `online`),
lanes A/B/C, the grounding tool and refusals, abuse controls and the cost policy. The gates in
`probe_core.py` (driver floor, capability, revision, variant, tier, library) are what that
stage's boot runs first; `test_gpu_probe.py` is where they are already tested without a GPU.
Before M3.1 the probe also answers the two open items from run 12: execution on `l4x1`
(sm_89; run 12 stayed on the T4 after L4 capacity stalled) and the first throughput numbers.
