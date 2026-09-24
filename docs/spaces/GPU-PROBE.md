# The GPU probe — `thyn-ai/algenta-gpu-probe`

Internal notes for `apps/spaces/gpu-probe/`. Module docstrings are the reference; this page is
the runbook view.

## What it is

A private Docker Space on `t4-small` (Tesla T4, sm_75, 15 GB) that boots, runs Qwen3-1.7B
through the published CUDA decode kernels of `thyn-ai/algenta-llm` and compares eight greedy
tokens with a transformers float32 CPU reference, then serves the record. It is the tracked
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
| `probe_core.py` | Stdlib-only logic: phase machine, driver/capability gates, revision/variant/tier/library gates, parity comparison, timings, the `/health` and `run.json` shapes. |
| `probe.py` | The five stages, one subprocess each: `driver`, `kernel`, `convert`, `decode`, `reference`. |
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
| `reference` | transformers float32 greedy on the CPU, 4 threads, same ids; per-step top-2 logit margins; tokenizer agreement | `reference` (load 5.6 s, generate 4.1 s, same eight ids, tokenizers agree) | transformers' exceptions as their class name |
| `record` | `run.json`: the health body plus `decision` and the two evidence rows' fields | the artifact's `parity`, `decision`, `evidence` | `run_incomplete` |

Stages run in subprocesses so a native abort is `stage_crashed` with the signal on `/health`
and the reference's 11 GB RSS is returned before the page is served (run 12 measured 11.2 GB
for the reference and 4.5 GB for the decode on a 16 GB host). Budgets are in
`probe_config.STAGE_TIMEOUTS_S`; a stage past its budget is `stage_timeout`.

Timings the page reports and what they are: `open_s` is the session open (weight upload and
prefill; the first token is computed by then), `ttft_s` is open plus the first step,
`tok_per_s` counts the steps after the first. Run 12 recorded 41.67 s open and about 30 ms per
step on the T4; the page prints what its own run measured and shows run 12's token ids only
under the label "run 12 recorded".

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

The CUDA path (driver gate, `get_kernel(backend="cuda")`, the native load, the decode) and the
image build itself run only on the Space: the Mac is arm64 and the image targets x86_64 CUDA.
What the Mac verified is everything the Space decides with (the gates, the parity rule, the
timings, the health and record shapes) against run 12's data, the routes and the page against a
fake stage runner, and the packaging (pins, frontmatter, copy lint, ruff).

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
