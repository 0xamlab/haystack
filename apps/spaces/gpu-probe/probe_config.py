"""Every pin and every fixed input of the GPU probe, in one place.

The values here are the ones run 12 of the original probe recorded
(`docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json`, 2026-09-22,
`GPU-SPACE-PARITY-001`), brought forward to the kernel revision published since. The build
(`fetch_assets.py`) refuses an image whose kernel snapshot or native manifest disagrees with
them; the run (`probe.py`) records what it measured next to them and never in their place.
"""

from __future__ import annotations

#: The kernel repository, its published v1 revision (REPUBLISH-006, 2026-09-24; the flagship's
#: `hubkernel.FROZEN_CAPPED_V1_SHAS` carries the same sha) and the build variant `kernels`
#: resolves for torch 2.9.1+cu128 on Linux x86_64.
KERNEL_REPO = "thyn-ai/algenta-llm"
KERNEL_REVISION = "8ae3da4a6c33b7484bbff01ca53317e320e06293"
KERNEL_VERSION = 1
KERNEL_BACKEND = "cuda"
EXPECTED_VARIANT = "torch29-cxx11-cu128-x86_64-linux"
#: The resident staging tier the native manifest must declare. The default tier (3072) refused
#: Qwen3-1.7B with `resident_dimension_too_large` (run 11, the negative control); 6144 admits
#: its feed-forward width.
EXPECTED_STAGE_TIER = 6144
#: The compute capabilities the published CUDA build carries a library for.
SUPPORTED_COMPUTE_CAPABILITIES: tuple[tuple[int, int], ...] = ((7, 5), (8, 0), (8, 9), (9, 0))
#: The NVIDIA driver major the CUDA build needs (`libcuda.so.1` from driver 580 or later).
DRIVER_FLOOR_MAJOR = 580

#: The model, pinned to the snapshot run 12 converted (Apache-2.0).
MODEL_REPO = "Qwen/Qwen3-1.7B"
MODEL_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
MODEL_ARCHITECTURE = "Qwen3ForCausalLM"
WEIGHTS_DTYPE = "f64"
CONVERTED_DIRNAME = "qwen3-1.7b-f64-cuda"

#: The fixed prompt and generation length of the parity check.
PROMPT = "Paris is the capital of France. Berlin is the capital of"
MAX_NEW_TOKENS = 8
#: Threads for the transformers float32 CPU reference (run 12 used four on the 3-vCPU tier).
REFERENCE_THREADS = 4

#: What run 12 recorded on a Tesla T4 (kernel v1 92ef06d7, tier 6144). The page shows these only
#: as "run 12 recorded", next to what this run measured; they never stand in for a measurement.
RUN12_PROMPT_IDS: tuple[int, ...] = (
    59604,
    374,
    279,
    6722,
    315,
    9625,
    13,
    19846,
    374,
    279,
    6722,
    315,
)
RUN12_TOKENS: tuple[int, ...] = (9856, 13, 15920, 315, 279, 2701, 374, 830)
RUN12_DECODED = " Germany. Which of the following is true"
RUN12_ARTIFACT = "docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json"

#: Per-stage wall-clock budgets (seconds) for the orchestrator; a stage past its budget is
#: recorded as `stage_timeout` and the run stops there.
STAGE_TIMEOUTS_S: dict[str, float] = {
    "driver": 120.0,
    "kernel": 600.0,
    "convert": 1800.0,
    "decode": 1800.0,
    "reference": 1500.0,
}

SPACE_REPO_ID = "thyn-ai/algenta-gpu-probe"
HARDWARE = "t4-small"
APP_PORT = 7860

DOCS_URL = "https://docs.algenta.ai"
PRICING_URL = "https://algenta.ai/pricing"
DISCORD_URL = "https://discord.gg/w8NDsph9an"
KERNEL_HUB_URL = f"https://huggingface.co/{KERNEL_REPO}"
MODEL_HUB_URL = f"https://huggingface.co/{MODEL_REPO}"
