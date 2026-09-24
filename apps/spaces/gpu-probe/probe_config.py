"""Every pin and every fixed input of the GPU probe, in one place.

The probe runs the published single-stream race live: the CUDA engine that ships in the
`algenta-runtime-native` wheel against llama.cpp built with GGML_CUDA, on the checkpoint, prompt
shape and generation length the benchmark pages measured (`gitbook/benchmarks/
nvidia-llm-serving.md` "Single-stream decode", `gitbook/benchmarks/nvidia-llm-throughput.md`
"L4"). The Hub kernels' f32 parity path and plain transformers on the same GPU run beside it as
secondary rows. The build (`fetch_assets.py`) refuses an image whose kernel snapshot, native
manifest, model snapshot, engine or llama.cpp build disagree with these values; the run
(`probe.py`) records what it measured next to them and never in their place.
"""

from __future__ import annotations

# --- the Hub kernel (lane C, the f32 parity path) ---------------------------------------------
#: The kernel repository, its published v1 revision (REPUBLISH-006, 2026-09-24; the flagship's
#: `hubkernel.FROZEN_CAPPED_V1_SHAS` carries the same sha) and the build variant `kernels`
#: resolves for torch 2.9.1+cu128 on Linux x86_64.
KERNEL_REPO = "thyn-ai/algenta-llm"
KERNEL_REVISION = "8ae3da4a6c33b7484bbff01ca53317e320e06293"
KERNEL_VERSION = 1
KERNEL_BACKEND = "cuda"
EXPECTED_VARIANT = "torch29-cxx11-cu128-x86_64-linux"
#: The resident staging tier the native manifest must declare: the published build carries the
#: 6144 tier (it admits Qwen3-1.7B, d_ff 6144, as well as Qwen3-0.6B-Base, d_ff 3072); the
#: default tier (3072) refused Qwen3-1.7B with `resident_dimension_too_large` (run 11).
EXPECTED_STAGE_TIER = 6144
#: The compute capabilities the published CUDA build carries a library for.
SUPPORTED_COMPUTE_CAPABILITIES: tuple[tuple[int, int], ...] = ((7, 5), (8, 0), (8, 9), (9, 0))
#: The NVIDIA driver major the CUDA build needs (`libcuda.so.1` from driver 580 or later).
DRIVER_FLOOR_MAJOR = 580

# --- the model: the benchmarked checkpoint ----------------------------------------------------
#: `Qwen/Qwen3-0.6B-Base` is the checkpoint of every published single-stream decode cell
#: (A100 455.3, H100 656.1, L4 193.9 tok/s at gen=64). Pinned to the snapshot the local cache
#: and the Hub's `main` both resolve to (2025-07-26); Apache-2.0.
MODEL_REPO = "Qwen/Qwen3-0.6B-Base"
MODEL_REVISION = "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
MODEL_ARCHITECTURE = "Qwen3ForCausalLM"
#: max(hidden_size, num_attention_heads x head_dim, intermediate_size) of the checkpoint; the
#: 6144-tier kernel and the engine's 18944-tier build both admit it.
MODEL_STAGE_NEEDED = 3072
#: The blob element width. Both consumers of the converted checkpoint read Float64 slices and
#: narrow to f32 on upload: the shipped `conform_generate_cuda` (`_read_f64_slice`, no
#: `weights_dtype` reader in `residentk/session_cuda.mojo`) and the Hub kernel's `DecodeSession`
#: ("the f64 blob uploaded as f32"). One f64 conversion (about 4.8 GB) serves lanes A and C.
WEIGHTS_DTYPE = "f64"
CONVERTED_DIRNAME = "qwen3-0.6b-base-f64-cuda"

# --- the race shape: the published protocol ----------------------------------------------------
#: The fixed prompt of the published cells: `scripts/algenta_bench.py`'s `_prompt_ids` cycle,
#: the same eight ids the engine's `--prompt-len` override generates
#: (`benchmarks/llm_smoke/conform_generate_cuda.mojo`), repeated to 256 tokens.
PROMPT_CYCLE_IDS: tuple[int, ...] = (785, 6722, 315, 9625, 374, 12095, 13, 576)
PROMPT_TOKENS = 256
#: Greedy generation lengths: gen=64 is the hero cell, gen=256 the second published column.
GEN_TOKENS = 64
GEN_TOKENS_LONG = 256
#: Timed runs per cell (median) after the excluded warm-up runs; the pages' fixture cells used
#: 20 runs on a dedicated VM, the probe's budget on a shared Space allows three.
RUNS = 3
WARMUP_RUNS = 1
#: The published gate is a 16/16 greedy oracle before any measurement; the probe checks the
#: first 16 tokens and the whole gen=64 stream of every lane against the CPU reference.
ORACLE_PREFIX = 16
#: The secondary transformers lanes: float32 (the precision of the resident f32 paths) and
#: float16 (what most people run on a GPU). Each lane is its own model load.
BASELINE_DTYPES: tuple[str, ...] = ("float32", "float16")
#: The first step counted in the steady per-token figures of the Hub and transformers lanes:
#: steps 1 and 2 are where those lanes differ (a prefill at session open or as step 1, then
#: a warm-up step), steps 3 onwards are the per-token cost.
STEADY_FROM_STEP = 3
#: Threads for the transformers float32 CPU reference (`l4x1` has 8 vCPU).
REFERENCE_THREADS = 8

# --- lane A: the shipped engine ------------------------------------------------------------------
#: The engine binary bundled in the `algenta-runtime-native` wheel beside the worker; located
#: the way `algenta.serve.engine.resolve_engine` does (env overrides, then the signed bundled
#: runtime, then PATH). The wheel's signed `manifest.json` declares its `cuda_target`, comptime
#: defines and host libraries; the probe reads them and gates on them.
ENGINE_NAME = "conform_generate_cuda"
ENGINE_WHEEL = "algenta-runtime-native"
ENGINE_WHEEL_VERSION = "1.0.7"
ENGINE_MANIFEST = "manifest.json"
#: Host libraries the engine links (the manifest's `host_shared_libraries`); the CUDA runtime
#: image provides them, the wheel ships `libcudart.so.12` beside the binary.
ENGINE_HOST_LIBRARIES: tuple[str, ...] = ("libcublas.so.12", "libcublasLt.so.12")
ENGINE_BUNDLED_LIBRARIES: tuple[str, ...] = ("libcudart.so.12",)
#: The environment variable the resolver honours first (`algenta.serve.engine.CUDA_ENGINE_ENV_VARS`
#: names it first): the Space variable that selects a binary shipped beside the app instead of
#: the wheel's engine.
ENGINE_ENV = "ALGENTA_CUDA_ENGINE"

# --- lane A, the other protocol: the packed-int8 captured-graph driver ------------------------
#: The driver of the published single-stream cells (`benchmarks/llm_smoke/REALRACE_RESULTS.md`,
#: the L4 lane: "p3 graph decode driver: -D ALGENTA_GPU -D ALGENTA_CUDA", plain sm_89 build).
#: It is not in any wheel; built for sm_89 it ships inside the Space folder as `engine/`
#: (see DEPLOY.md) and `ALGENTA_CUDA_ENGINE=/home/user/engine/qwen3_p3_graph_cuda` selects it.
#: Lane A speaks its protocol when the resolved binary carries this name: argv
#: `<checkpoint> --runs N`, one process for the whole battery (three gates, then gen=64 and
#: gen=256 for three arms), the figures read from its prints.
P3_ENGINE_NAME = "qwen3_p3_graph_cuda"
P3_ENGINE_SOURCE = "benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo"
P3_ENGINE_SESSION = "packed-int8 captured-graph session (residentk.session_cuda_p3_graph)"
#: The binary names lane A knows how to drive; anything else is refused before launch.
ENGINE_PROTOCOLS: tuple[str, ...] = (ENGINE_NAME, P3_ENGINE_NAME)
#: The driver's generation lengths are fixed in its source (gen64 and gen256 throughput cells,
#: the published cell's two columns); `--runs` is the only measurement knob. Its oracle gate
#: checks the first 16 greedy tokens; it prints no other token.
P3_GEN_LENGTHS: tuple[int, ...] = (64, 256)
P3_ORACLE_TOKENS = 16
#: One launch runs the gates (G0 oracle, G1 3 seeds x 128 steps, G2 engagement at four depths)
#: and the six throughput cells; with `--runs 3` that is a few minutes on the L4, so the launch
#: gets most of the stage's 600 s budget.
P3_ENGINE_RUN_TIMEOUT_S = 540.0

# --- the prompt fixtures ------------------------------------------------------------------------
#: `battery` is the eight-id cycle above (the wheel engine's `--prompt-len` override and
#: `algenta_bench.py`). `campaign` is the race fixture of the nvidia_race campaign: the text
#: `"The capital of France is Paris. " * 36 + "The capital of France"`
#: (`benchmarks/llm_smoke/nvidia_race/prepare_smoke_checkpoint.py`) tokenized byte-exact by
#: the Qwen3 tokenizer to 256 ids: `785` then the seven-id cycle 36 times, then the first three
#: ids of the cycle (verified with `algenta.tokenizer` on the pinned snapshot, 2026-09-24). The
#: packed-int8 graph driver's oracle gate is bound to that fixture (its expected continuation
#: is hard-coded), so a run that selects it converts and races every lane on the campaign
#: fixture; the record and the page say which fixture ran.
PROMPT_FIXTURE_ENV = "PROBE_PROMPT_FIXTURE"
PROMPT_FIXTURES: tuple[str, ...] = ("battery", "campaign")
CAMPAIGN_PROMPT_TEXT = "The capital of France is Paris. " * 36 + "The capital of France"
CAMPAIGN_PROMPT_HEAD = 785
CAMPAIGN_PROMPT_CYCLE: tuple[int, ...] = (6722, 315, 9625, 374, 12095, 13, 576)
#: The driver's `_oracle_token`: an eight-token window, then the seven-token cycle the model
#: repeats on that prompt (" is Paris. The capital of France is Paris. ...").
CAMPAIGN_ORACLE_WINDOW: tuple[int, ...] = (374, 12095, 13, 576, 6722, 315, 9625, 374)
CAMPAIGN_ORACLE_CYCLE: tuple[int, ...] = (12095, 13, 576, 6722, 315, 9625, 374)

#: The Space hardware names mapped to their compute capability, so the build can say up front
#: whether the bundled engine's target can load on the requested hardware.
HARDWARE_COMPUTE_CAPABILITY: dict[str, tuple[int, int]] = {
    "t4-small": (7, 5),
    "t4-medium": (7, 5),
    "a10g-small": (8, 6),
    "a10g-large": (8, 6),
    "a100-large": (8, 0),
    "l4x1": (8, 9),
    "l40sx1": (8, 9),
    "h100": (9, 0),
}

# --- lane B: the published opponent ------------------------------------------------------------
#: llama.cpp at the pin the throughput page names (`000547513f`), which is tag `b10210`, the
#: "build 10210" the serving page names; built in the image with GGML_CUDA for sm_89.
LLAMA_CPP_REPO = "https://github.com/ggml-org/llama.cpp.git"
LLAMA_CPP_COMMIT = "000547513f1530346ecd163db8b3e13962949961"
LLAMA_CPP_TAG = "b10210"
LLAMA_CPP_BUILD = 10210
LLAMA_CUDA_ARCHITECTURES = "89"
LLAMA_DIR = "/opt/llama"
LLAMA_SERVER = f"{LLAMA_DIR}/bin/llama-server"
LLAMA_CONVERT = f"{LLAMA_DIR}/convert_hf_to_gguf.py"
LLAMA_GGUF_PY = f"{LLAMA_DIR}/gguf-py"
LLAMA_COMMIT_FILE = f"{LLAMA_DIR}/COMMIT"
#: The GGUF the opponent serves: the same snapshot converted with `convert_hf_to_gguf.py
#: --outtype f16` at image build (the published cells' "F16 GGUF").
LLAMA_GGUF_OUTTYPE = "f16"
GGUF_FILENAME = "qwen3-0.6b-base-f16.gguf"
#: `llama-server -ngl 99`, one slot, a context that holds the 256-token prompt plus gen=256.
LLAMA_PORT = 8093
LLAMA_CTX = 1024
LLAMA_GPU_LAYERS = 99
LLAMA_PARALLEL = 1
LLAMA_READY_TIMEOUT_S = 180.0

# --- the published figures the page shows beside the live ones ---------------------------------
PUBLISHED_DATE = "2026-08"
PUBLISHED_HARDWARE = "NVIDIA L4 (g2-standard-8, driver 595.71.05)"
#: The serving page's "Single-stream decode" L4 row and the throughput page's L4 table. The two
#: pages report the same cell from two sessions; both are shown, each with its source.
PUBLISHED_SERVING_URL = "https://docs.algenta.ai/benchmarks/nvidia-llm-serving"
PUBLISHED_THROUGHPUT_URL = "https://docs.algenta.ai/benchmarks/nvidia-llm-throughput"
PUBLISHED_SERVING_L4 = {
    "algenta_gen64": 193.9,
    "algenta_gen256": 188.8,
    "ratio_gen64": 1.12,
    "ratio_gen256": 1.09,
    "opponent": "llama.cpp F16 (GGML_CUDA, build 10210)",
    "session": "arithmetic-packed-int8 weights (1.58 B/weight), captured-graph decode",
}
PUBLISHED_THROUGHPUT_L4 = {
    "algenta_gen64": 191.1,
    "algenta_gen256": 184.8,
    "llama_gen64": 171.3,
    "llama_gen256": 172.6,
    "session": "packed3, CUDA-graph decode",
}

# --- budgets -----------------------------------------------------------------------------------
#: Per-stage wall-clock budgets (seconds) for the orchestrator; a stage past its budget is
#: recorded as `stage_timeout` (a lane stage is then unavailable, a hard stage stops the run).
STAGE_TIMEOUTS_S: dict[str, float] = {
    "driver": 120.0,
    "kernel": 600.0,
    "convert": 900.0,
    "engine": 600.0,
    "llama": 600.0,
    "decode": 900.0,
    "baseline": 600.0,
    "reference": 900.0,
}
#: The whole run's budget on the L4: a lane stage that would start after it is recorded as
#: `run_budget_exhausted` instead of running; the reference and the record still run.
RUN_BUDGET_S = 1200.0
#: A lane runs its gen=256 cells only when its gen=64 cells finished inside this many seconds.
LONG_GEN_BUDGET_S = 240.0

SPACE_REPO_ID = "thyn-ai/algenta-gpu-probe"
#: The published L4 cell needs an L4 (`l4x1`: NVIDIA L4, sm_89, 24 GB, 8 vCPU, 30 GB, $0.80/h on
#: 2026-09-24). `t4-small` is the fallback hardware for the secondary rows only: the llama.cpp
#: build targets sm_89 and the bundled engine's target is what its manifest declares.
HARDWARE = "l4x1"
HARDWARE_FALLBACK = "t4-small"
HARDWARE_PRICE_USD_H = 0.80
APP_PORT = 7860

#: Earlier records of this Space, kept for replay tests and the docs; none stands in for a
#: measurement of this run.
PRIOR_ARTIFACTS: tuple[str, ...] = (
    "docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json",
    "docs/hf-kernels/evidence/artifacts/gpu-probe-run13-t4-small-qwen3-1p7b.json",
    "docs/hf-kernels/evidence/artifacts/gpu-probe-run14-t4-small-qwen3-1p7b-side-by-side.json",
)

DOCS_URL = "https://docs.algenta.ai"
PRICING_URL = "https://algenta.ai/pricing"
DISCORD_URL = "https://discord.gg/w8NDsph9an"
KERNEL_HUB_URL = f"https://huggingface.co/{KERNEL_REPO}"
MODEL_HUB_URL = f"https://huggingface.co/{MODEL_REPO}"
LLAMA_CPP_URL = f"https://github.com/ggml-org/llama.cpp/tree/{LLAMA_CPP_COMMIT}"
