"""apps/spaces/gpu-probe — the GPU probe Space, tested without a GPU.

Everything the Space decides on the L4 is a pure helper in `probe_core.py`: the phase machine,
the driver and compute-capability gates, the kernel revision/variant/tier/library gates, the
engine's compile-target gate, the engine and llama.cpp output parsers, the medians, the
identity comparison and the lane views. Those run here on the build Mac. The orchestrator and
the FastAPI routes run against a fake stage runner: the run-12 artifact's data for the phases
that existed then (`docs/hf-kernels/evidence/artifacts/gpu-probe-run12-*.json`) plus
shape-only reports for the race lanes, and the run-13 / run-14 records (schemas 2 and 3) are
replayed through today's views so a record from before the race still renders as it was
measured. The engine and llama-server protocols run end to end against a fake engine script
and a fake HTTP server on the loopback. No figure of any fixture is a measurement, and none is
asserted as one. torch, kernels, transformers and algenta are never imported.
"""

from __future__ import annotations

import http.server
import importlib
import importlib.util
import json
import re
import shutil
import stat
import sys
import threading
import types
from pathlib import Path
from types import ModuleType

import copy_lint
import pytest
from _rules import _assert_clean_copy
from manifest import load_manifest

REPO = Path(__file__).resolve().parents[2]
PROBE_DIR = REPO / "apps" / "spaces" / "gpu-probe"
ARTIFACT = REPO / "docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json"
ARTIFACT_RUN13 = (
    REPO / "docs/hf-kernels/evidence/artifacts/gpu-probe-run13-t4-small-qwen3-1p7b.json"
)
ARTIFACT_RUN14 = (
    REPO
    / "docs/hf-kernels/evidence/artifacts/gpu-probe-run14-t4-small-qwen3-1p7b-side-by-side.json"
)
#: The step times of the run-13 rerun (2026-09-24 18:19Z, Tesla T4), as the page printed them.
RUN13_STEP_MS = [0.1, 194.7, 26.7, 26.8, 26.9, 26.9, 27.0, 27.0]
RUN13_OPEN_S = 42.64
FLAGSHIP_DIR = REPO / "apps" / "spaces" / "algenta"
SERVING_PAGE = REPO / "gitbook/benchmarks/nvidia-llm-serving.md"
THROUGHPUT_PAGE = REPO / "gitbook/benchmarks/nvidia-llm-throughput.md"
ENGINE_SHA = "c5594028327c5f1fd41cce3a5524271443a4a39368f5a340eb4a71548ad17ad3"

# Appended, not inserted: the flagship's tests import their own `app` and `hf_ua_shim` from
# apps/spaces/algenta at sys.path[0]; the probe's modules with unique names (probe, probe_core,
# probe_config) resolve from the end of the path, and its `app` is loaded by file under an alias.
if str(PROBE_DIR) not in sys.path:
    sys.path.append(str(PROBE_DIR))

cfg = importlib.import_module("probe_config")
core = importlib.import_module("probe_core")
probe = importlib.import_module("probe")


def _load_by_file(alias: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(alias, PROBE_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


app = _load_by_file("gpu_probe_app", "app.py")
fetch_assets = _load_by_file("gpu_probe_fetch_assets", "fetch_assets.py")


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artifact13() -> dict:
    return json.loads(ARTIFACT_RUN13.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artifact14() -> dict:
    return json.loads(ARTIFACT_RUN14.read_text(encoding="utf-8"))


# --- shape-only fixtures for the lanes the artifacts predate ---------------------------------


def _run(
    gen: int, tokens: list[int], rate: float, prefill: float, ttft_ms: float, vram: int
) -> dict:
    return {
        "gen": gen,
        "tokens": list(tokens[:gen]),
        "n_prompt": 256,
        "n_gen": min(gen, len(tokens)),
        "prefill_ms": ttft_ms,
        "prefill_tok_per_s": prefill,
        "decode_tok_per_s": rate,
        "ttft_ms": ttft_ms,
        "wall_s": 3.0,
        "vram_peak_bytes": vram,
        "stopped_on_eos": False,
    }


def _cell(
    gen: int, tokens: list[int], rate: float, prefill: float, ttft_ms: float, vram: int
) -> dict:
    timed = [_run(gen, tokens, rate + d, prefill, ttft_ms, vram) for d in (-1.0, 0.0, 1.0)]
    return {
        "gen": gen,
        "warmup": _run(gen, tokens, rate * 0.9, prefill, ttft_ms, vram),
        "warmup_excluded": True,
        "timed": timed,
        "timed_wall_s": 9.0,
        "summary": core.run_summary(timed),
    }


def _cells(tokens: list[int], rate: float, prefill: float, ttft_ms: float, vram: int) -> dict:
    cells = {
        str(cfg.GEN_TOKENS): _cell(cfg.GEN_TOKENS, tokens, rate, prefill, ttft_ms, vram),
        str(cfg.GEN_TOKENS_LONG): _cell(
            cfg.GEN_TOKENS_LONG, tokens, rate * 0.97, prefill, ttft_ms, vram
        ),
    }
    summary = cells[str(cfg.GEN_TOKENS)]["summary"]
    return {
        "runs": cells,
        "long_gen_skipped": None,
        "tokens": summary["tokens"],
        "runs_agree": summary["runs_agree"],
        "decode_tok_per_s": summary["decode_tok_per_s"],
        "prefill_tok_per_s": summary["prefill_tok_per_s"],
        "ttft_ms": summary["ttft_ms"],
        "vram_peak_bytes": summary["vram_peak_bytes"],
    }


def _fixture_engine(tokens: list[int], *, cuda_target: str = "sm_89") -> dict:
    """Lane A's stage report in shape only; every figure is invented."""
    ids = core.race_prompt_ids()
    return {
        "engine": {
            "path": "/opt/venv/lib/python3.14/site-packages/algenta_runtime_native/conform_generate_cuda",
            "dir": "/opt/venv/lib/python3.14/site-packages/algenta_runtime_native",
            "resolved_from": "bundled runtime",
            "searched": [],
            "wheel_version": cfg.ENGINE_WHEEL_VERSION,
            "size_bytes": 7477504,
            "sha256": ENGINE_SHA,
            "libcudart_beside": True,
            "manifest": "manifest.json",
            "cuda_target": cuda_target,
            "comptime_defines": ["ALGENTA_GPU", "ALGENTA_CUDA", "ALGENTA_STAGE_18944"],
            "host_shared_libraries": list(cfg.ENGINE_HOST_LIBRARIES),
            "sha256_declared": ENGINE_SHA,
            "sha256_matches": True,
            "source": "benchmarks/llm_smoke/conform_generate_cuda.mojo",
            "build_variant": "cuda",
        },
        "target_gate": core.engine_target_gate(cuda_target, (8, 9)),
        "host_libraries": {name: name for name in cfg.ENGINE_HOST_LIBRARIES},
        "ld_library_path": "/opt/venv/lib/python3.14/site-packages/algenta_runtime_native",
        "argv": ["conform_generate_cuda", "ckpt", "--max-new", "64", "--prompt-len", "256"],
        "checkpoint_dir": "ckpt",
        "prompt_ids": ids,
        "n_prompt": len(ids),
        **_cells(tokens, 190.0, 3100.0, 82.0, 2_400_000_000),
        "decoded": " Germany. Which of the following is true",
        "max_rss_mib": 100.0,
    }


def _fixture_llama(tokens: list[int]) -> dict:
    ids = core.race_prompt_ids()
    return {
        "server": cfg.LLAMA_SERVER,
        "argv": [cfg.LLAMA_SERVER, "-m", "x.gguf", "-ngl", "99"],
        "env": {
            cfg.LLAMA_LIBRARY_PATH_ENV: f"{cfg.LLAMA_BIN_DIR}:/usr/local/cuda/lib64",
            cfg.LLAMA_BACKEND_PATH_ENV: cfg.LLAMA_BIN_DIR,
        },
        "version": {
            "line": f"version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})",
            "build_number": cfg.LLAMA_CPP_BUILD,
            "commit": cfg.LLAMA_CPP_COMMIT[:9],
        },
        "commit_pinned": cfg.LLAMA_CPP_COMMIT,
        "build_tag": cfg.LLAMA_CPP_TAG,
        "image": {
            "ref": cfg.LLAMA_IMAGE_REF,
            "tag": cfg.LLAMA_IMAGE_TAG,
            "digest": cfg.LLAMA_IMAGE_DIGEST,
            "amd64_digest": cfg.LLAMA_IMAGE_AMD64_DIGEST,
            "kind": cfg.LLAMA_IMAGE_KIND,
            "cuda_runtime": cfg.LLAMA_CUDA_RUNTIME,
        },
        "cuda_architectures": cfg.LLAMA_CUDA_ARCHITECTURES,
        "gguf": {
            "path": "/home/user/assets/x.gguf",
            "bytes": 1_200_000_000,
            "outtype": "f16",
            "convert_wall_s": 40.0,
        },
        "ready_s": 6.0,
        "prompt_ids": ids,
        "n_prompt": len(ids),
        **_cells(tokens, 171.0, 2500.0, 100.0, 1_600_000_000),
        "vram_baseline_bytes": 0,
        "decoded": " Germany. Which of the following is true",
        "log_tail": ["srv  log_server_r: request: POST /completion"],
        "max_rss_mib": 50.0,
    }


def _fixture_baseline(tokens: list[int], *, float16_code: str | None = None) -> dict:
    """Lane D's stage report in shape only. `float16_code` makes that lane fail closed."""

    def lane(dtype: str, load_s: float, ttft_s: float, step: float, taken: int) -> dict:
        n = len(tokens)
        steps = [ttft_s * 1000.0, *([step] * (n - 1))]
        timings = core.step_timings(steps)
        run = {
            "gen": n,
            "tokens": list(tokens),
            "step_ms": steps,
            "ttft_s": ttft_s,
            "ttft_ms": ttft_s * 1000.0,
            "prefill_tok_per_s": round(256 / ttft_s, 2),
            "decode_tok_per_s": timings["decode_tok_per_s"],
            "generate_s": round(sum(steps) / 1000.0, 3),
            "stopped_on_eos": False,
        }
        timed = [dict(run) for _ in range(cfg.RUNS)]
        cell = {
            "gen": n,
            "warmup": {**run, "step_ms": [ttft_s * 3000.0, *([step * 2] * (n - 1))]},
            "warmup_excluded": True,
            "timed": timed,
            "timed_wall_s": 3.0,
            "summary": core.run_summary(timed),
        }
        return {
            "ok": True,
            "dtype": dtype,
            "torch_dtype": f"torch.{dtype}",
            "model_dtype": f"torch.{dtype}",
            "load_s": load_s,
            "ttft_s": ttft_s,
            "ttft_ms": ttft_s * 1000.0,
            "step_ms": steps,
            "generate_s": round(sum(steps) / 1000.0, 3),
            "tokens": list(tokens),
            "decoded": " Germany. Which of the following is true",
            "stopped_on_eos": False,
            "eos_token_id": [151645, 151643],
            "gpu_free_bytes_before": 24_000_000_000,
            "gpu_free_bytes_after_load": 24_000_000_000 - taken,
            "device_taken_bytes": taken,
            "weights_allocated_bytes": taken,
            "peak_allocated_bytes": taken + 300_000_000,
            "peak_reserved_bytes": taken + 500_000_000,
            "runs": {str(cfg.GEN_TOKENS): cell, str(cfg.GEN_TOKENS_LONG): None},
            "decode_tok_per_s": cell["summary"]["decode_tok_per_s"],
            "prefill_tok_per_s": cell["summary"]["prefill_tok_per_s"],
            "runs_agree": True,
            "same_tokens_as_warmup": True,
            "warmup": {
                "excluded": True,
                "tokens": list(tokens),
                "step_ms": [ttft_s * 3000.0, *([step * 2] * (n - 1))],
                "ttft_s": ttft_s * 3,
                "generate_s": 1.0,
            },
        }

    lanes = {
        "float32": lane("float32", 4.0, 0.045, 25.0, 2_600_000_000),
        "float16": lane("float16", 3.0, 0.040, 20.0, 1_400_000_000),
    }
    if float16_code:
        lanes["float16"] = {
            "ok": False,
            "dtype": "float16",
            "code": float16_code,
            "message": "OutOfMemoryError: CUDA out of memory",
        }
    ids = core.race_prompt_ids()
    return {
        "method": "transformers generate on CUDA (fixture)",
        "device_name": "NVIDIA L4",
        "compute_capability": [8, 9],
        "torch": "2.9.1+cu128",
        "cuda": "12.8",
        "transformers": "5.17.0",
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "max_new_tokens": len(tokens),
        "runs_per_lane": cfg.RUNS,
        "dtypes": list(cfg.BASELINE_DTYPES),
        "gpu_total_bytes": 25_000_000_000,
        "gpu_free_bytes_start": 24_000_000_000,
        "gpu_free_bytes_end": 24_000_000_000,
        "lanes": lanes,
        "max_rss_mib": 1.0,
    }


def _run12_stage_data(artifact: dict) -> dict[str, dict]:
    """The run-12 artifact's stage outputs in the shape `probe.py` reports today, plus
    shape-only reports for the stages run 12 did not have (engine, llama, baseline)."""
    driver = artifact["steps"]["driver"]["data"]
    gpu = artifact["steps"]["gpu"]["data"]
    convert = artifact["steps"]["convert"]["data"]
    reference = artifact["steps"]["reference"]["data"]
    build_kernel = artifact["image"]["build_facts"]["kernel"]
    kernel = {
        "repo": build_kernel["repo"],
        "revision": build_kernel["v1_sha"],
        "variant": gpu["kernel"]["variant"],
        "resident_stage_tier": build_kernel["resident_stage_tier"],
        "cuda_targets": build_kernel["cuda_targets"],
        "cuda_libraries": build_kernel["cuda_libraries"],
        "selected_library": gpu["kernel"]["selected_library"],
        "mojo_version": build_kernel["mojo_version"],
        "get_kernel_s": gpu["kernel"]["get_kernel_s"],
        "native_init_s": gpu["kernel"]["native_init_s"],
        "compute_capability": gpu["torch"]["compute_capability"],
    }
    tokens = reference["tokens"]
    return {
        "driver": {
            **core.driver_gate(driver["nvidia_smi"]["driver_version"]),
            "nvidia_smi": driver["nvidia_smi"],
            "device_name": driver["libcuda"]["device_name"],
            "compute_capability": driver["libcuda"]["compute_capability"],
            "cu_driver_get_version": driver["libcuda"]["cu_driver_get_version"],
            "cuda_driver_api": driver["libcuda"]["cuda_driver_api"],
            "libcuda_mapped_paths": driver["libcuda"]["mapped_paths"],
            "torch": gpu["torch"],
        },
        "kernel": kernel,
        "convert": {
            "reused": convert["reused"],
            "wall_s": convert["wall_s"],
            "blob_bytes": convert["blob_bytes"],
            "weights_dtype": convert["weights_dtype"],
            "prompt_ids": artifact["prompt"]["token_ids"],
            "n_prompt": len(artifact["prompt"]["token_ids"]),
        },
        "engine": _fixture_engine(tokens),
        "llama": _fixture_llama(tokens),
        "decode": {
            **kernel,
            "prompt_ids": artifact["prompt"]["token_ids"],
            "tokens": gpu["decode"]["tokens"],
            "step_ms": gpu["decode"]["step_ms"],
            "open_s": gpu["decode"]["open_s"],
            "decoded": artifact["parity"]["native"]["decoded"],
        },
        "baseline": _fixture_baseline(tokens),
        "reference": {
            "reference": reference["reference"],
            "transformers": reference["transformers"],
            "threads": reference["threads"],
            "tokens": tokens,
            "decoded": reference["decoded"],
            "load_s": reference["load_s"],
            "generate_s": reference["generate_s"],
            "prompt_ids_agree_with_algenta_tokenizer": reference[
                "prompt_ids_agree_with_algenta_tokenizer"
            ],
        },
    }


def _fake_runner(stage_data: dict[str, dict], failures: dict[str, dict] | None = None):
    """A stage runner that answers from data instead of a subprocess; `failures` override."""
    calls: list[str] = []

    def runner(name: str, timeout_s: float) -> app.StageOutcome:
        calls.append(name)
        assert timeout_s > 0
        if failures and name in failures:
            spec = failures[name]
            return app.StageOutcome(
                stdout=spec.get("stdout", ""),
                stderr=spec.get("stderr", ""),
                returncode=spec.get("returncode", 1),
                timed_out=spec.get("timed_out", False),
                wall_s=0.5,
            )
        payload = {"ok": True, "stage": name, **stage_data[name]}
        return app.StageOutcome(
            stdout="INFO noise line\n" + json.dumps(payload) + "\n",
            stderr="log line\n",
            returncode=0,
            timed_out=False,
            wall_s=1.5,
        )

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def _failure(code: str, message: str = "m") -> dict:
    return {"stdout": json.dumps({"ok": False, "code": code, "message": message}), "returncode": 1}


def _page_text(page: str) -> str:
    """The page's rendered words: tags and the stylesheet stripped, whitespace collapsed."""
    import html as _html

    without_css = re.sub(r"<style>.*?</style>", " ", page, flags=re.DOTALL)
    return _html.unescape(" ".join(re.sub(r"<[^>]+>", " ", without_css).split()))


# --- the pins are the published methodology's facts ------------------------------------------


def test_model_and_prompt_are_the_published_cells() -> None:
    assert cfg.MODEL_REPO == "Qwen/Qwen3-0.6B-Base" and core.is_sha(cfg.MODEL_REVISION)
    serving = SERVING_PAGE.read_text(encoding="utf-8")
    throughput = THROUGHPUT_PAGE.read_text(encoding="utf-8")
    assert "Qwen3-0.6B-Base" in serving and "`Qwen/Qwen3-0.6B-Base`" in throughput
    assert "256-token prompt" in throughput and "gen=64" in serving
    # the prompt is the battery's cycle: scripts/algenta_bench.py and the engine's own override
    spec = importlib.util.spec_from_file_location(
        "algenta_bench", REPO / "scripts/algenta_bench.py"
    )
    assert spec is not None and spec.loader is not None
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    assert bench._prompt_ids(cfg.PROMPT_TOKENS) == core.race_prompt_ids()
    assert bench._prompt_ids(8) == list(cfg.PROMPT_CYCLE_IDS)
    mojo = (REPO / "benchmarks/llm_smoke/conform_generate_cuda.mojo").read_text(encoding="utf-8")
    appended = [int(m) for m in re.findall(r"base\.append\((\d+)\)", mojo)]
    assert appended == list(cfg.PROMPT_CYCLE_IDS)
    assert "--prompt-len" in mojo and "--max-new" in mojo and "CONFORM_TIMING:" in mojo
    assert "_read_f64_slice" in mojo and cfg.WEIGHTS_DTYPE == "f64"
    assert cfg.PROMPT_TOKENS == 256 and cfg.GEN_TOKENS == 64 and cfg.GEN_TOKENS_LONG == 256
    assert cfg.RUNS == 3 and cfg.WARMUP_RUNS == 1 and cfg.ORACLE_PREFIX == 16


def test_published_figures_and_the_llama_pin_come_from_the_pages() -> None:
    serving = SERVING_PAGE.read_text(encoding="utf-8")
    throughput = THROUGHPUT_PAGE.read_text(encoding="utf-8")
    s = cfg.PUBLISHED_SERVING_L4
    assert (
        f"| L4 | {s['algenta_gen64']} | {s['algenta_gen256']} | {s['ratio_gen64']}x / {s['ratio_gen256']}x |"
        in serving
    )
    t = cfg.PUBLISHED_THROUGHPUT_L4
    assert f"| {t['algenta_gen64']} | {t['algenta_gen256']} |" in throughput
    assert f"| llama.cpp F16 | {t['llama_gen64']} | {t['llama_gen256']} |" in throughput
    assert cfg.PUBLISHED_LLAMA_CPP_COMMIT[:10] in throughput, "the throughput page names the pin"
    assert f"build {cfg.PUBLISHED_LLAMA_CPP_BUILD}" in serving, "the serving page names the build"
    assert cfg.PUBLISHED_LLAMA_CPP_TAG == f"b{cfg.PUBLISHED_LLAMA_CPP_BUILD}"
    assert cfg.PUBLISHED_LLAMA_CUDA_ARCHITECTURES == "89" and cfg.HARDWARE == "l4x1"
    published = core.published_facts()
    assert published["serving"]["llama_gen64_implied"] == round(193.9 / 1.12, 1)
    assert published["throughput"]["ratio_gen64"] == round(191.1 / 171.3, 2)
    assert published["serving"]["url"].startswith("https://docs.algenta.ai/benchmarks/")


def test_kernel_revision_pin_is_the_flagships_frozen_sha() -> None:
    hubkernel = importlib.import_module("algenta_spaces.hubkernel")
    assert cfg.KERNEL_REVISION == hubkernel.FROZEN_CAPPED_V1_SHAS[cfg.KERNEL_REPO]
    assert cfg.EXPECTED_STAGE_TIER == 6144 >= cfg.MODEL_STAGE_NEEDED == 3072


def test_engine_wheel_pin_agrees_with_the_sdk() -> None:
    pyproject = (REPO / "packages/algenta/pyproject.toml").read_text(encoding="utf-8")
    assert f'"{cfg.ENGINE_WHEEL}=={cfg.ENGINE_WHEEL_VERSION}"' in pyproject
    engine = (REPO / "packages/algenta/algenta/serve/engine.py").read_text(encoding="utf-8")
    assert f'CUDA_ENGINE_BINARY_NAME = "{cfg.ENGINE_NAME}"' in engine
    for literal, _code in core.ENGINE_OUTPUT_CODES:
        assert literal in engine, literal


# --- phase machine ---------------------------------------------------------------------------


def test_phase_order_soft_lanes_and_dependencies() -> None:
    assert list(core.PHASES) == [
        "driver",
        "kernel",
        "convert",
        "engine",
        "llama",
        "decode",
        "baseline",
        "reference",
        "record",
    ]
    assert core.SOFT_PHASES == frozenset({"kernel", "engine", "llama", "decode", "baseline"})
    assert core.DEPENDS == {"decode": "kernel"}
    assert set(cfg.STAGE_TIMEOUTS_S) == set(app.STAGE_PHASES) == set(probe.STAGES)
    m = core.PhaseMachine()
    assert m.status == core.PENDING and m.phase == "driver"
    with pytest.raises(ValueError, match="predecessors"):
        m.start("kernel")
    m.start("driver")
    with pytest.raises(ValueError, match="only start once"):
        m.start("driver")
    m.finish("driver", {"device_name": "NVIDIA L4"}, wall_s=0.5234)
    assert m.records["driver"].wall_s == 0.52
    for name in core.PHASES[1:]:
        m.start(name)
        m.finish(name, {})
    assert m.status == core.OK and m.phase == "done" and m.finished_utc
    assert list(m.snapshot()) == list(core.PHASES)


def test_hard_failure_skips_the_rest_and_a_lane_failure_does_not() -> None:
    m = core.PhaseMachine()
    m.start("driver")
    m.fail("driver", "no_gpu", "none")
    assert m.status == core.ERROR and m.failure is not None and m.failure.code == "no_gpu"
    for later in core.PHASES[1:]:
        assert m.records[later].status == core.SKIPPED
        assert m.records[later].code == "upstream_failed"
    n = core.PhaseMachine()
    n.start("driver")
    n.finish("driver", {})
    n.start("kernel")
    n.fail("kernel", "kernel_tier_mismatch", "tier 3072")
    assert n.status == core.RUNNING and n.failure is None and n.phase == "convert"
    for name in ("convert", "engine", "llama", "decode", "baseline", "reference", "record"):
        n.start(name)
        n.finish(name, {})
    assert n.status == core.OK and n.records["kernel"].status == core.ERROR
    with pytest.raises(ValueError, match="distinct"):
        core.PhaseMachine(["a", "a"])


# --- gates -----------------------------------------------------------------------------------


def test_driver_gate_accepts_580_and_refuses_below() -> None:
    assert core.driver_gate("580.178.04") == {
        "driver_version": "580.178.4",
        "base_driver_major": 580,
        "driver_floor": 580,
        "meets_driver_floor": True,
    }
    with pytest.raises(core.ProbeError) as exc:
        core.driver_gate("570.124.06")
    assert exc.value.code == "driver_below_floor"
    with pytest.raises(core.ProbeError) as exc:
        core.driver_gate("")
    assert exc.value.code == "driver_version_unreadable"


def test_compute_capability_gate() -> None:
    assert core.compute_capability_gate([7, 5]) == (7, 5)
    assert core.compute_capability_gate((8, 9)) == (8, 9)
    assert core.compute_capability_gate((8, 6)) == (8, 6)  # PTX forward compatibility
    with pytest.raises(core.ProbeError) as exc:
        core.compute_capability_gate((6, 1))
    assert exc.value.code == "compute_capability_unsupported"
    with pytest.raises(core.ProbeError) as exc:
        core.compute_capability_gate(("x",))
    assert exc.value.code == "compute_capability_unreadable"


def test_parse_nvidia_smi_row() -> None:
    fields = probe.NVIDIA_SMI_FIELDS
    row = "NVIDIA L4, 580.178.04, 8.9, 23034 MiB"
    assert core.parse_nvidia_smi(row, fields) == {
        "name": "NVIDIA L4",
        "driver_version": "580.178.04",
        "compute_cap": "8.9",
        "memory.total": "23034 MiB",
    }
    with pytest.raises(core.ProbeError) as exc:
        core.parse_nvidia_smi("No devices were found", fields)
    assert exc.value.code == "nvidia_smi_unreadable"


def test_revision_variant_tier_and_library_gates(artifact: dict) -> None:
    path = (
        f"/home/user/hf/hub/kernels--thyn-ai--algenta-llm/snapshots/{cfg.KERNEL_REVISION}"
        f"/build/{cfg.EXPECTED_VARIANT}/__init__.py"
    )
    assert core.revision_gate(path) == cfg.KERNEL_REVISION
    assert core.variant_gate(path) == cfg.EXPECTED_VARIANT
    with pytest.raises(core.ProbeError) as exc:
        core.revision_gate(
            path.replace(cfg.KERNEL_REVISION, "92ef06d7b01116a70d8a8a6179c492aac5462146")
        )
    assert exc.value.code == "kernel_revision_mismatch"
    with pytest.raises(core.ProbeError) as exc:
        core.variant_gate(path.replace("cu128", "cpu"))
    assert exc.value.code == "kernel_variant_mismatch"
    assert core.tier_gate({"resident_stage_tier": 6144}) == 6144
    with pytest.raises(core.ProbeError) as exc:
        core.tier_gate({"resident_stage_tier": 3072})
    assert exc.value.code == "kernel_tier_mismatch"
    with pytest.raises(core.ProbeError) as exc:
        core.tier_gate({})
    assert exc.value.code == "kernel_tier_missing"
    manifest = {"cuda_libraries": artifact["image"]["build_facts"]["kernel"]["cuda_libraries"]}
    assert core.expected_library(manifest, (8, 9)) == "libalgenta_algenta_llm.sm_89.so"
    assert core.expected_library(manifest, (8, 6)) == "libalgenta_algenta_llm.sm_80.so"
    assert core.expected_library(manifest, (12, 0)) == "libalgenta_algenta_llm.sm_90.so"
    with pytest.raises(core.ProbeError) as exc:
        core.expected_library(manifest, (7, 0))
    assert exc.value.code == "gpu_unsupported"
    with pytest.raises(core.ProbeError) as exc:
        core.library_gate("libalgenta_algenta_llm.sm_90.so", manifest, [7, 5])
    assert exc.value.code == "kernel_library_mismatch"


def test_engine_target_gate_is_architecture_aware() -> None:
    """The wheel's engine is `sm_90a`: an architecture-specific image that loads on Hopper alone,
    so the L4 (8.9) is refused before launch with the fact in the message; a plain `sm_NN`
    target admits any device at or above it (PTX forward compatibility)."""
    assert core.parse_cuda_target("sm_90a") == (9, 0, True)
    assert core.parse_cuda_target("sm_75") == (7, 5, False)
    assert core.parse_cuda_target("sm_100a") == (10, 0, True)
    with pytest.raises(core.ProbeError) as exc:
        core.parse_cuda_target("cuda")
    assert exc.value.code == "engine_target_unreadable"
    with pytest.raises(core.ProbeError) as exc:
        core.engine_target_gate("sm_90a", (8, 9))
    assert exc.value.code == "engine_target_mismatch"
    assert "sm_90a" in exc.value.message and "8.9" in exc.value.message
    assert exc.value.details["architecture_specific"] is True
    assert core.engine_target_gate("sm_90a", (9, 0))["ok"] is True
    with pytest.raises(core.ProbeError) as exc:
        core.engine_target_gate("sm_90a", (10, 0))
    assert exc.value.code == "engine_target_mismatch"
    assert core.engine_target_gate("sm_89", (8, 9))["ok"] is True
    assert core.engine_target_gate("sm_75", (8, 9))["ok"] is True
    with pytest.raises(core.ProbeError):
        core.engine_target_gate("sm_90", (8, 9))
    unchecked = core.engine_target_gate(None, (8, 9))
    assert unchecked["checked"] is False and unchecked["ok"] is None
    assert cfg.HARDWARE_COMPUTE_CAPABILITY["l4x1"] == (8, 9)
    assert cfg.HARDWARE_COMPUTE_CAPABILITY["h100"] == (9, 0)


# --- the engine's and llama.cpp's outputs ---------------------------------------------------


def test_parse_engine_output_reads_both_spacings_and_names_refusals() -> None:
    spaced = (
        "conform_generate_cuda: d_model= 1024 n_layers= 28\n"
        "CONFORM_TOKENS: 12095 13 576 6722\n"
        "CONFORM_TIMING: n_prompt= 256  n_gen= 64  prefill_ms= 39.125  decode_tok_s= 187.25\n"
        "conform_generate_cuda: done. stopped_on_eos= False\n"
    )
    run = core.parse_engine_output(spaced, "", 0)
    assert run["tokens"] == [12095, 13, 576, 6722] and run["n_prompt"] == 256
    assert run["n_gen"] == 64 and run["prefill_ms"] == 39.125 and run["ttft_ms"] == 39.125
    assert run["decode_tok_per_s"] == 187.25
    assert run["prefill_tok_per_s"] == round(256 / (39.125 / 1000.0), 2)
    compact = (
        "CONFORM_TOKENS: 1 2\nCONFORM_TIMING: n_prompt=8 n_gen=2 prefill_ms=1.5 decode_tok_s=50\n"
    )
    assert core.parse_engine_output(compact, "", 0)["decode_tok_per_s"] == 50.0
    for literal, code in core.ENGINE_OUTPUT_CODES:
        with pytest.raises(core.ProbeError) as exc:
            core.parse_engine_output(f"x\n{literal} something\n", "", 3)
        assert exc.value.code == code, literal
    with pytest.raises(core.ProbeError) as exc:
        core.parse_engine_output("", "CUDA error: no kernel image is available\n", 1)
    assert exc.value.code == "engine_run_failed" and "no kernel image" in exc.value.message
    with pytest.raises(core.ProbeError) as exc:
        core.parse_engine_output(
            "CONFORM_TIMING: n_prompt=1 n_gen=1 prefill_ms=1 decode_tok_s=1\n", "", 0
        )
    assert exc.value.code == "engine_no_tokens"
    with pytest.raises(core.ProbeError) as exc:
        core.parse_engine_output("CONFORM_TOKENS: 1\nCONFORM_TIMING: n_prompt=1\n", "", 0)
    assert exc.value.code == "engine_no_timing"


def test_llama_completion_is_read_fail_closed() -> None:
    timings = {
        "prompt_n": 256,
        "prompt_ms": 101.5,
        "prompt_per_second": 2522.1,
        "predicted_n": 64,
        "predicted_ms": 372.0,
        "predicted_per_second": 172.04,
    }
    payload = {"tokens": [1, 2, 3, 4], "timings": timings, "stop_type": "limit", "tokens_cached": 0}
    run = core.llama_run_from_completion(payload, expected_n_prompt=256, gen=4)
    assert run["tokens"] == [1, 2, 3, 4] and run["decode_tok_per_s"] == 172.04
    assert run["prefill_tok_per_s"] == 2522.1 and run["ttft_ms"] == 101.5 and run["n_prompt"] == 256
    assert run["stopped_on_eos"] is False and run["timings"]["predicted_n"] == 64
    with pytest.raises(core.ProbeError) as exc:
        core.llama_run_from_completion(
            {**payload, "timings": {**timings, "prompt_n": 257}}, expected_n_prompt=256, gen=4
        )
    assert exc.value.code == "llama_prompt_mismatch"
    with pytest.raises(core.ProbeError) as exc:
        core.llama_run_from_completion(
            {**payload, "tokens_cached": 12}, expected_n_prompt=256, gen=4
        )
    assert exc.value.code == "llama_prompt_cached"
    with pytest.raises(core.ProbeError) as exc:
        core.llama_run_from_completion({**payload, "tokens": []}, expected_n_prompt=256, gen=4)
    assert exc.value.code == "llama_tokens_missing"
    with pytest.raises(core.ProbeError) as exc:
        core.llama_run_from_completion({**payload, "timings": {}}, expected_n_prompt=256, gen=4)
    assert exc.value.code == "llama_timings_missing"
    with pytest.raises(core.ProbeError) as exc:
        core.llama_run_from_completion(payload, expected_n_prompt=256, gen=64)
    assert exc.value.code == "llama_short_generation"
    eos = core.llama_run_from_completion(
        {**payload, "stop_type": "eos"}, expected_n_prompt=256, gen=64
    )
    assert eos["stopped_on_eos"] is True and eos["n_gen"] == 4
    version = core.parse_llama_version(
        "load_backend: loaded CUDA backend from /opt/llama/bin/libggml-cuda.so\n"
        "version: 10210 (000547513f)\nbuilt with gcc\n"
    )
    assert version == {
        "line": "version: 10210 (000547513f)",
        "build_number": 10210,
        "commit": "000547513f",
        "backends_loaded": {"CUDA": "/opt/llama/bin/libggml-cuda.so"},
        "loader_errors": [],
    }
    assert core.parse_llama_version("")["build_number"] is None
    # the later builds' shape (the moving server-cuda tag printed it on 2026-09-24)
    newer = core.parse_llama_version(
        "0.00.004.531 I srv  llama_server: initializing ...\n"
        "version: 0.5.0-dev (build 11151, commit bd4f514db)\nbuilt with GNU 14.2.0\n"
    )
    assert newer == {
        "line": "version: 0.5.0-dev (build 11151, commit bd4f514db)",
        "build_number": 11151,
        "commit": "bd4f514db",
        "backends_loaded": {},
        "loader_errors": [],
    }


# --- medians, identity, timings --------------------------------------------------------------


def test_run_summary_takes_the_median_and_checks_agreement() -> None:
    runs = [
        {
            "decode_tok_per_s": 190.0,
            "prefill_tok_per_s": 3000.0,
            "ttft_ms": 80.0,
            "tokens": [1, 2],
            "vram_peak_bytes": 10,
        },
        {
            "decode_tok_per_s": 170.0,
            "prefill_tok_per_s": 3100.0,
            "ttft_ms": 90.0,
            "tokens": [1, 2],
            "vram_peak_bytes": 12,
        },
        {
            "decode_tok_per_s": 200.0,
            "prefill_tok_per_s": None,
            "ttft_ms": 85.0,
            "tokens": [1, 3],
            "vram_peak_bytes": None,
        },
    ]
    summary = core.run_summary(runs)
    assert summary["n_runs"] == 3 and summary["decode_tok_per_s"] == 190.0
    assert summary["decode_tok_per_s_runs"] == [190.0, 170.0, 200.0]
    assert summary["prefill_tok_per_s"] == 3050.0 and summary["ttft_ms"] == 85.0
    assert summary["tokens"] == [1, 2] and summary["runs_agree"] is False
    assert summary["vram_peak_bytes"] == 12
    assert core.run_summary([])["decode_tok_per_s"] is None
    assert core.run_summary(runs[:2])["runs_agree"] is True


def test_identity_report_carries_the_published_oracle_form() -> None:
    reference = list(range(64))
    full = core.parity_report(reference, reference, reference_margins=[1.0] * 64)
    assert full["verdict"] == "64/64" and full["oracle"] == "16/16" and full["oracle_match"] is True
    assert full["full_match"] is True and full["first_divergence"] is None
    late = [*reference[:40], 999, *reference[41:]]
    report = core.parity_report(
        late, reference, reference_margins=[0.5] * 40 + [0.031251] + [1.0] * 23
    )
    assert (
        report["verdict"] == "40/64"
        and report["oracle"] == "16/16"
        and report["oracle_match"] is True
    )
    assert report["first_divergence"] == {"index": 40, "native": 999, "reference": 40}
    assert report["reference_top2_margin_at_divergence"] == 0.031251
    early = [*reference[:3], 999, *reference[4:]]
    assert core.parity_report(early, reference)["oracle"] == "3/16"
    eight = core.parity_report(reference[:8], reference[:8])
    assert eight["verdict"] == "8/8" and eight["oracle"] == "8/8"
    short = core.compare_tokens(reference[:5], reference)
    assert short["first_divergence"]["length_only"] is True and short["full_match"] is False


def test_step_timings_share_one_definition_and_guard_a_zero_mean() -> None:
    """The decode rate is the race's definition (tokens after the first over their steps); the
    steady figure is the mean of steps 3 onwards. A steady mean of exactly 0.0 yields
    `steady_step_ms` 0.0 with no rate (Codna, #1172): the guard is explicit, not falsy."""
    t = core.step_timings(RUN13_STEP_MS)
    steady = RUN13_STEP_MS[2:]
    assert (
        t["steady_steps"] == "3-8"
        and t["steady_step_ms"] == round(sum(steady) / len(steady), 2) == 26.88
    )
    assert t["steady_tok_per_s"] == 37.2
    assert t["decode_tok_per_s"] == round(7 / (sum(RUN13_STEP_MS[1:]) / 1000.0), 2) == 19.66
    assert t["all_steps_tok_per_s"] == 22.47
    zero = core.step_timings([0.0, 0.0, 0.0, 0.0])
    assert zero["steady_step_ms"] == 0.0 and zero["steady_tok_per_s"] is None
    assert zero["decode_tok_per_s"] is None and zero["all_steps_tok_per_s"] is None
    d = core.decode_timings(RUN13_OPEN_S, RUN13_STEP_MS)
    assert d["ttft_s"] == 42.64 == d["open_s"] and d["tok_per_s"] == d["decode_tok_per_s"]
    b = core.baseline_timings(9.0, [90.0, 40.0, 40.0, 40.0])
    assert b["ttft_s"] == 0.09 and b["decode_tok_per_s"] == 25.0 and b["steady_step_ms"] == 40.0
    assert core.step_timings([50.0, 40.0])["steady_steps"] is None
    assert core.step_timings([])["decode_tok_per_s"] is None


# --- the stage protocol ----------------------------------------------------------------------


def test_stage_result_reads_the_last_json_line() -> None:
    out = 'INFO something\n{"ok": true, "stage": "driver", "x": 1}\n'
    assert core.stage_result_from_output(out, 0) == {"ok": True, "stage": "driver", "x": 1}
    failed = core.stage_result_from_output('{"ok": false, "code": "no_gpu", "message": "m"}', 1)
    assert failed["code"] == "no_gpu"
    assert core.stage_result_from_output('{"ok": false}', 1)["code"] == "stage_failed"
    crashed = core.stage_result_from_output("Fatal Python error\n", -11)
    assert crashed["code"] == "stage_crashed" and "signal 11" in crashed["message"]
    assert core.stage_result_from_output("", 0, timed_out=True)["code"] == "stage_timeout"
    assert core.log_tail("a\n\nb\nc\n", 2) == ["b", "c"]


def test_public_error_keeps_a_typed_code() -> None:
    class KernelError(RuntimeError):
        def __init__(self, code: str, message: str) -> None:
            super().__init__(message)
            self.code = code

    err = core.public_error(KernelError("resident_dimension_too_large", "d_ff 6144 > 3072"))
    assert err.code == "resident_dimension_too_large"
    assert core.public_error(ValueError("bad\nsecond line")).message == "bad"


@pytest.mark.skipif(shutil.which("nvidia-smi") is not None, reason="a GPU host runs the stage")
def test_driver_stage_fails_closed_without_a_gpu() -> None:
    report = probe.run_stage("driver")
    assert report["ok"] is False and report["code"] == "nvidia_smi_missing"
    assert "Traceback" not in json.dumps(report)
    assert probe.run_stage("nope")["code"] == "unknown_stage"
    assert probe.gpu_memory_used_bytes() is None
    sampler = probe.GpuMemorySampler(interval_s=0.01).start()
    assert sampler.stop()["peak_delta_bytes"] is None


def test_environment_facts_are_stdlib_only() -> None:
    facts = probe.environment_facts({"CUDA_VERSION": "12.8.1", "NVIDIA_DISABLE_REQUIRE": "1"})
    assert facts["cuda_version_env"] == "12.8.1" and facts["nvidia_disable_require"] == "1"
    assert set(facts["packages"]) == set(probe.PACKAGES)
    space = probe.space_facts({"SPACE_ID": cfg.SPACE_REPO_ID})
    assert space["SPACE_ID"] == cfg.SPACE_REPO_ID and space["hardware_requested"] == "l4x1"
    assert probe.work_dir({"PROBE_WORK_DIR": "/w"}) == Path("/w")
    assert probe.assets_dir({"PROBE_ASSETS_DIR": "/a"}) == Path("/a")
    assert probe.build_facts_path({"PROBE_ASSETS_DIR": "/a"}) == Path("/a/build_facts.json")
    assert probe.build_facts_path({"PROBE_BUILD_FACTS": "/b.json"}) == Path("/b.json")
    assert probe.read_build_facts(Path("/nonexistent/build_facts.json")) == {}


def test_engine_runs_end_to_end_against_a_fake_engine(tmp_path: Path) -> None:
    """The subprocess protocol as lane A drives it: argv, environment, the two CONFORM lines,
    the prompt-length check, and the run's fields. The engine here is a script that answers
    like the real one; no figure it prints is a measurement."""
    engine = tmp_path / "conform_generate_cuda"
    engine.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "ckpt, args = sys.argv[1], sys.argv[2:]\n"
        "gen = int(args[args.index('--max-new') + 1]); n = int(args[args.index('--prompt-len') + 1])\n"
        "assert os.environ['LD_LIBRARY_PATH'].split(':')[0] == os.path.dirname(os.path.abspath(sys.argv[0]))\n"
        "print('conform_generate_cuda: d_model= 1024')\n"
        "print('CONFORM_TOKENS: ' + ' '.join(str(12095 + i) for i in range(gen)))\n"
        "print('CONFORM_TIMING: n_prompt=', n, ' n_gen=', gen, ' prefill_ms=', 40.5, ' decode_tok_s=', 180.25)\n",
        encoding="utf-8",
    )
    engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
    checkpoint = tmp_path / "ckpt"
    checkpoint.mkdir()
    env = probe.engine_env(engine.parent)
    env["PATH"] = str(Path(sys.executable).parent) + ":" + env.get("PATH", "")
    run = probe.run_engine_once(engine, checkpoint, 64, env)
    assert run["gen"] == 64 and len(run["tokens"]) == 64 and run["n_prompt"] == 256
    assert run["decode_tok_per_s"] == 180.25 and run["ttft_ms"] == 40.5
    assert run["argv"][2:] == ["--max-new", "64", "--prompt-len", "256"]
    assert run["stopped_on_eos"] is False
    cell = probe.run_cell(64, lambda gen: probe.run_engine_once(engine, checkpoint, gen, env))
    assert len(cell["timed"]) == cfg.RUNS and cell["warmup_excluded"] is True
    assert cell["summary"]["decode_tok_per_s"] == 180.25 and cell["summary"]["runs_agree"] is True
    cells = probe.run_cells(lambda gen: probe.run_engine_once(engine, checkpoint, gen, env))
    assert set(cells["runs"]) == {"64", "256"} and cells["long_gen_skipped"] is None
    assert cells["runs"]["256"]["summary"]["tokens"][:3] == [12095, 12096, 12097]
    headline = probe.cell_headline(cells["runs"])
    assert (
        headline["decode_tok_per_s"] == 180.25 and headline["tokens"] == cell["summary"]["tokens"]
    )


def test_llama_protocol_runs_against_a_fake_server(tmp_path: Path) -> None:
    """`/health` then `/completion` on the loopback, the request as lane B sends it (the ids as
    a token array, greedy, no prompt cache, token ids returned), llama.cpp's timings read back."""
    seen: list[dict] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # noqa: ANN002 - silence
            return

        def do_GET(self) -> None:  # noqa: N802 - http.server's spelling
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            seen.append(request)
            n = len(request["prompt"])
            gen = request["n_predict"]
            body = json.dumps(
                {
                    "content": " Paris.",
                    "tokens": [12095 + i for i in range(gen)],
                    "stop_type": "limit",
                    "tokens_cached": 0,
                    "timings": {
                        "prompt_n": n,
                        "prompt_ms": 100.0,
                        "prompt_per_second": n / 0.1,
                        "predicted_n": gen,
                        "predicted_ms": gen * 5.0,
                        "predicted_per_second": 200.0,
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"

        class Alive:
            returncode = None

            def poll(self) -> None:
                return None

        assert probe.wait_llama_ready(base, Alive(), 5.0) >= 0.0
        ids = core.race_prompt_ids()
        run = probe.llama_completion(base, ids, 64)
        assert run["tokens"][0] == 12095 and run["n_gen"] == 64 and run["decode_tok_per_s"] == 200.0
        assert run["prefill_tok_per_s"] == 2560.0 and run["ttft_ms"] == 100.0 and run["wall_s"] >= 0
        request = seen[-1]
        assert request["prompt"] == ids and request["n_predict"] == 64
        assert (
            request["temperature"] == 0
            and request["top_k"] == 1
            and request["samplers"] == ["top_k"]
        )
        assert request["cache_prompt"] is False and request["return_tokens"] is True

        class Dead:
            returncode = 1

            def poll(self) -> int:
                return 1

        with pytest.raises(core.ProbeError) as exc:
            probe.wait_llama_ready(base, Dead(), 5.0)
        assert exc.value.code == "llama_server_failed"
    finally:
        server.shutdown()
        server.server_close()


# --- the bake's engine facts ---------------------------------------------------------------------


def test_bake_engine_reads_the_signed_manifest_and_records_the_hardware_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The build reads the wheel's manifest for the engine block, checks the sha256, and judges
    the compile target against the requested hardware: `sm_90a` on `l4x1` is recorded as
    `engine_target_mismatch` (the lane's run-time code), never a build failure; a binary whose
    hash differs from the manifest fails the build."""
    engine = tmp_path / cfg.ENGINE_NAME
    engine.write_bytes(b"not an ELF, a fixture")
    sha = probe.sha256_of(engine)
    manifest = {
        "build_variant": "cuda",
        "platform": "linux-x86_64",
        "engine": {
            "name": cfg.ENGINE_NAME,
            "sha256": sha,
            "cuda_target": "sm_90a",
            "comptime_defines": ["ALGENTA_GPU", "ALGENTA_CUDA", "ALGENTA_STAGE_18944"],
            "host_shared_libraries": ["libcublas.so.12", "libcublasLt.so.12"],
            "source": "benchmarks/llm_smoke/conform_generate_cuda.mojo",
        },
    }
    (tmp_path / cfg.ENGINE_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "libcudart.so.12").write_bytes(b"")
    monkeypatch.delenv(cfg.ENGINE_ENV, raising=False)
    monkeypatch.setattr(fetch_assets, "runtime_native_dir", lambda: tmp_path)
    monkeypatch.setattr(
        fetch_assets.probe,
        "package_versions",
        lambda names: {cfg.ENGINE_WHEEL: cfg.ENGINE_WHEEL_VERSION},
    )
    facts = fetch_assets.bake_engine()
    assert facts["sha256"] == sha and facts["cuda_target"] == "sm_90a"
    assert facts["bundled_libraries"] == {"libcudart.so.12": True}
    assert facts["selected_by"] is None and facts["selected_path"] is None
    assert facts["resolved_from"] == "bundled runtime" and "unset" in facts["inspected_because"]
    assert facts["wheel_version"] == cfg.ENGINE_WHEEL_VERSION
    verdict = facts["expected_hardware_gate"]
    assert verdict["hardware"] == "l4x1" and verdict["ok"] is False
    assert verdict["code"] == "engine_target_mismatch" and "8.9" in verdict["message"]
    manifest["engine"]["cuda_target"] = "sm_89"
    (tmp_path / cfg.ENGINE_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    assert fetch_assets.bake_engine()["expected_hardware_gate"]["ok"] is True
    manifest["engine"]["sha256"] = "0" * 64
    (tmp_path / cfg.ENGINE_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_engine()
    assert exc.value.code == "engine_sha_mismatch"
    engine.unlink()
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_engine()
    assert exc.value.code == "engine_binary_missing"


def test_bake_engine_inspects_the_engine_the_build_argument_selects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `ALGENTA_CUDA_ENGINE` set (the Dockerfile's build argument, the Space variable at
    build time) the bake inspects that binary through the manifest beside it and judges its
    target — the sm_89 driver loads on l4x1 — and says which file it inspected and why; run 16
    inspected the wheel's sm_90a engine because the variable never reached the build. A name
    that is not an executable file in the image fails the build (`engine_selected_missing`),
    the resolver would fall through to the wheel; a manifest without a target is invalid."""
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    engine = engine_dir / cfg.P3_ENGINE_NAME
    engine.write_bytes(b"fixture")
    engine.chmod(engine.stat().st_mode | stat.S_IEXEC)
    sha = probe.sha256_of(engine)
    for name in P3_CLOSURE:
        (engine_dir / name).write_bytes(b"")
    (engine_dir / cfg.ENGINE_MANIFEST).write_text(json.dumps(_p3_manifest(sha)), encoding="utf-8")
    monkeypatch.setenv(cfg.ENGINE_ENV, str(engine))
    monkeypatch.setattr(
        fetch_assets, "runtime_native_dir", lambda: (_ for _ in ()).throw(AssertionError("wheel"))
    )
    monkeypatch.setattr(
        probe, "package_versions", lambda names: {cfg.ENGINE_WHEEL: cfg.ENGINE_WHEEL_VERSION}
    )
    facts = fetch_assets.bake_engine()
    assert facts["path"] == str(engine) and facts["selected_path"] == str(engine)
    assert facts["selected_by"] == f"${cfg.ENGINE_ENV}" == facts["resolved_from"]
    assert facts["protocol"] == cfg.P3_ENGINE_NAME and facts["cuda_target"] == "sm_89"
    assert facts["sha256"] == sha and facts["sha256_matches"] is True and facts["bundled_beside"]
    assert facts["expected_hardware_gate"]["ok"] is True
    assert facts["expected_hardware_gate"]["hardware"] == "l4x1"
    assert (
        str(engine) in facts["inspected_because"] and "build argument" in facts["inspected_because"]
    )
    assert facts["wheel_version"] == cfg.ENGINE_WHEEL_VERSION

    monkeypatch.setenv(cfg.ENGINE_ENV, str(engine_dir / "missing"))
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_engine()
    assert exc.value.code == "engine_selected_missing" and "fall through" in exc.value.message
    engine.chmod(0o644)
    monkeypatch.setenv(cfg.ENGINE_ENV, str(engine))
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_engine()
    assert exc.value.code == "engine_selected_missing"
    engine.chmod(engine.stat().st_mode | stat.S_IEXEC)
    manifest = _p3_manifest(sha)
    del manifest["engine"]["cuda_target"]
    (engine_dir / cfg.ENGINE_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_engine()
    assert exc.value.code == "engine_manifest_invalid" and "cuda_target" in exc.value.message
    (engine_dir / cfg.ENGINE_MANIFEST).unlink()
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_engine()
    assert exc.value.code == "engine_manifest_invalid"


def test_engine_facts_locate_the_engine_as_serve_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`probe.engine_facts` asks `algenta.serve.engine.resolve_engine`, then reads the manifest
    beside the binary; a manifest whose sha256 disagrees with the file is `engine_sha_mismatch`,
    no binary is `engine_binary_missing` with the searched chain."""
    engine = tmp_path / cfg.ENGINE_NAME
    engine.write_bytes(b"fixture")
    sha = probe.sha256_of(engine)
    (tmp_path / cfg.ENGINE_MANIFEST).write_text(
        json.dumps(
            {
                "build_variant": "cuda",
                "engine": {
                    "name": cfg.ENGINE_NAME,
                    "sha256": sha,
                    "cuda_target": "sm_90a",
                    "comptime_defines": ["ALGENTA_CUDA"],
                    "host_shared_libraries": ["libcublas.so.12"],
                },
            }
        ),
        encoding="utf-8",
    )
    resolution = types.SimpleNamespace(
        path=engine, source="bundled runtime", searched=("$ALGENTA_CUDA_ENGINE",)
    )
    fake = types.ModuleType("algenta.serve.engine")
    fake.resolve_engine = lambda backend: resolution  # type: ignore[attr-defined]
    if importlib.util.find_spec("algenta") is None:
        package = types.ModuleType("algenta")
        package.__path__ = []  # type: ignore[attr-defined]
        serve = types.ModuleType("algenta.serve")
        serve.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "algenta", package)
        monkeypatch.setitem(sys.modules, "algenta.serve", serve)
    monkeypatch.setitem(sys.modules, "algenta.serve.engine", fake)
    monkeypatch.setattr(probe, "package_versions", lambda names: {cfg.ENGINE_WHEEL: "1.0.7"})
    facts = probe.engine_facts()
    assert facts["path"] == str(engine) and facts["resolved_from"] == "bundled runtime"
    assert facts["cuda_target"] == "sm_90a" and facts["sha256_matches"] is True
    assert (
        facts["host_shared_libraries"] == ["libcublas.so.12"] and facts["libcudart_beside"] is False
    )
    engine.write_bytes(b"changed")
    with pytest.raises(core.ProbeError) as exc:
        probe.engine_facts()
    assert exc.value.code == "engine_sha_mismatch"
    resolution.path = None
    with pytest.raises(core.ProbeError) as exc:
        probe.engine_facts()
    assert exc.value.code == "engine_binary_missing" and "$ALGENTA_CUDA_ENGINE" in exc.value.message


# --- health, run.json and the page ------------------------------------------------------------


def test_health_body_before_the_run_shows_pins_and_no_facts() -> None:
    body = core.health_body(core.PhaseMachine(), versions={"python": "3.14.7"}, space={})
    assert body["schema"] == core.SCHEMA == "algenta-gpu-probe/4"
    assert body["status"] == core.PENDING and body["phase"] == "driver"
    assert body["pins"]["model_repo"] == cfg.MODEL_REPO and body["pins"]["hardware"] == "l4x1"
    assert body["pins"]["llama_cpp_commit"] == cfg.LLAMA_CPP_COMMIT
    for key in ("driver", "kernel", "model", "engine", "llama", "decode", "reference", "parity"):
        assert body[key] is None, key
    view = body["race"]
    assert [lane["status"] for lane in view["race"]] == [core.PENDING_LANE, core.PENDING_LANE]
    assert view["published"]["serving"]["algenta_gen64"] == 193.9
    with pytest.raises(core.ProbeError) as exc:
        core.run_record(body)
    assert exc.value.code == "run_incomplete"


def test_full_run_writes_the_record_with_the_race_and_the_parity_rows(
    tmp_path: Path, artifact: dict
) -> None:
    state = app.ProbeState(work=tmp_path, versions={"python": "3.14.7"}, space={}, build={})
    runner = _fake_runner(_run12_stage_data(artifact))
    app.run_probe(state, runner)
    assert runner.calls == list(app.STAGE_PHASES)
    body = state.health()
    assert body["status"] == core.OK and body["phase"] == "done" and body["run_json"] is True
    assert body["parity"]["verdict"] == "8/8" and body["parity"]["full_match"] is True
    view = body["race"]
    engine, llama = view["race"]
    assert engine["status"] == llama["status"] == core.OK_LANE
    assert engine["decode_tok_per_s"] == 190.0 and llama["decode_tok_per_s"] == 171.0
    assert engine["identity"]["verdict"] == "8/8" and llama["identity"]["oracle"] == "8/8"
    assert view["ratio"] == {
        "same_tokens": True,
        "tokens_compared": 8,
        "decode_gen64": 1.11,
        "decode_gen256": 1.11,
        "prefill": 1.24,
    }
    hub, f32, f16 = view["secondary"]
    assert hub["status"] == core.OK_LANE and hub["ttft_ms"] == round(41.67 * 1000 + 0.24, 1)
    assert hub["identity"]["verdict"] == "8/8" and f32["identity"]["verdict"] == "8/8"
    assert body["kernel"]["selected_library"] == "libalgenta_algenta_llm.sm_75.so"
    record = json.loads(state.run_json.read_text(encoding="utf-8"))
    assert record["schema"] == "algenta-gpu-probe/4" and record["decision"] == "ok"
    assert "engine, llama, hub, float32, float16" in record["decision_reason"]
    row = record["evidence"]["GPU-SPACE-PARITY-001"]
    expected = artifact["evidence"]["GPU-SPACE-PARITY-001"]
    for key in ("native_tokens", "reference_tokens", "step_ms", "open_s", "blob_bytes"):
        assert row[key] == expected[key], key
    assert row["conversion_wall_s"] == expected["conversion_wall_s"] == 81.73
    driver_row = record["evidence"]["GPU-SPACE-DRIVER-001"]
    assert driver_row["gpu"] == "Tesla T4" and driver_row["cuDriverGetVersion"] == 13000
    race = record["evidence"]["GPU-SPACE-RACE-001"]
    assert race["engine"]["decode_tok_per_s_gen64"] == 190.0 and race["llama"]["identity"] == "8/8"
    assert (
        race["ratio_decode_gen64"] == 1.11
        and race["published"]["serving"]["algenta_gen64"] == 193.9
    )
    assert (
        race["engine"]["build"]["cuda_target"] == "sm_89"
        and race["llama"]["build"]["build_number"] == cfg.LLAMA_CPP_BUILD
        and race["llama"]["build"]["image_tag"] == cfg.LLAMA_IMAGE_TAG
        and race["llama"]["build"]["image"] == cfg.LLAMA_IMAGE_REF
    )
    assert set(race["secondary"]) == {"hub", "float32", "float16"}


def test_hard_failure_stops_the_run_and_lane_failures_carry_codes(
    tmp_path: Path, artifact: dict
) -> None:
    data = _run12_stage_data(artifact)
    stopped = app.ProbeState(work=tmp_path / "a", versions={}, space={}, build={})
    runner = _fake_runner(data, {"convert": _failure("disk_insufficient", "3.1 GiB free")})
    app.run_probe(stopped, runner)
    assert runner.calls == ["driver", "kernel", "convert"]
    body = stopped.health()
    assert body["status"] == core.ERROR and body["failure"]["code"] == "disk_insufficient"
    assert body["phases"]["engine"]["status"] == core.SKIPPED and not stopped.run_json.exists()
    # every lane fails closed with its code; the run is still complete and recorded
    failures = {
        "kernel": _failure("kernel_tier_mismatch"),
        "engine": _failure("engine_target_mismatch", "the engine is built for sm_90a"),
        "llama": _failure("llama_server_failed"),
        "baseline": {"stdout": "", "returncode": -11},
    }
    lanes_down = app.ProbeState(work=tmp_path / "b", versions={}, space={}, build={})
    runner = _fake_runner(data, failures)
    app.run_probe(lanes_down, runner)
    assert "decode" not in runner.calls, "the Hub lane is not run when the kernel failed"
    body = lanes_down.health()
    assert body["status"] == core.OK and body["failure"] is None and body["run_json"] is True
    assert body["phases"]["decode"]["code"] == "upstream_failed"
    assert "kernel is error (kernel_tier_mismatch)" in body["phases"]["decode"]["message"]
    view = body["race"]
    assert [(lane["status"], lane["code"]) for lane in view["race"]] == [
        (core.UNAVAILABLE, "engine_target_mismatch"),
        (core.UNAVAILABLE, "llama_server_failed"),
    ]
    assert [(lane["status"], lane["code"]) for lane in view["secondary"]] == [
        (core.UNAVAILABLE, "upstream_failed"),
        (core.UNAVAILABLE, "stage_crashed"),
        (core.UNAVAILABLE, "stage_crashed"),
    ]
    assert view["ratio"]["decode_gen64"] is None
    record = json.loads(lanes_down.run_json.read_text(encoding="utf-8"))
    assert record["decision"] == "no_lane_ran"
    text = _page_text(app.render_page(body))
    assert "Algenta engine unavailable (engine_target_mismatch)" in text
    assert (
        "Algenta engine: unavailable, engine_target_mismatch — the engine is built for sm_90a."
        in text
    )
    assert text.count("unavailable (stage_crashed)") >= 2 and "Traceback" not in text
    _assert_clean_copy(app.render_page(body))


def test_crash_timeout_and_budget_are_lane_codes(tmp_path: Path, artifact: dict) -> None:
    data = _run12_stage_data(artifact)
    crashed = app.ProbeState(work=tmp_path / "a", versions={}, space={}, build={})
    app.run_probe(crashed, _fake_runner(data, {"engine": {"stdout": "", "returncode": -11}}))
    body = crashed.health()
    assert body["status"] == core.OK and body["phases"]["engine"]["code"] == "stage_crashed"
    assert "signal 11" in body["phases"]["engine"]["message"]
    slow = app.ProbeState(work=tmp_path / "b", versions={}, space={}, build={})
    app.run_probe(slow, _fake_runner(data, {"llama": {"timed_out": True}}))
    assert slow.health()["race"]["race"][1]["code"] == "stage_timeout"
    # the run budget: lanes that would start after it are not run, the reference still is
    budget = app.ProbeState(work=tmp_path / "c", versions={}, space={}, build={})
    runner = _fake_runner(data)
    app.run_probe(budget, runner, budget_s=0.0)
    assert runner.calls == ["driver", "convert", "reference"]
    body = budget.health()
    assert body["status"] == core.OK and body["run_json"] is True
    for name in ("kernel", "engine", "llama", "baseline"):
        assert body["phases"][name]["code"] == "run_budget_exhausted", name
    assert body["phases"]["decode"]["code"] == "upstream_failed"
    assert json.loads(budget.run_json.read_text(encoding="utf-8"))["decision"] == "no_lane_ran"

    def exploding(name: str, timeout_s: float) -> app.StageOutcome:
        raise OSError("no interpreter")

    broken = app.ProbeState(work=tmp_path / "d", versions={}, space={}, build={})
    app.run_probe(broken, exploding)
    assert broken.health()["failure"]["code"] == "stage_crashed"
    with pytest.raises(core.ProbeError, match="run.json is written only"):
        core.run_record(broken.health())


def test_routes_and_page(tmp_path: Path, artifact: dict) -> None:
    testclient = pytest.importorskip("starlette.testclient")
    state = app.ProbeState(work=tmp_path, versions={"python": "3.14.7"}, space={}, build={})
    client = testclient.TestClient(app.build_app(state))
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["status"] == core.PENDING
    missing = client.get("/run.json")
    assert missing.status_code == 404 and missing.json()["error"] == "run_not_recorded"
    page = client.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert app.TITLE in page.text and "Waiting to start." in page.text
    _assert_clean_copy(page.text)

    app.run_probe(state, _fake_runner(_run12_stage_data(artifact)))
    run = client.get("/run.json")
    assert run.status_code == 200 and run.json()["decision"] == "ok"
    assert client.get("/health").json()["race"]["ratio"]["decode_gen64"] == 1.11
    page = client.get("/")
    assert (
        "Run complete. Algenta engine 190.0 tok/s (identity 8/8); llama.cpp 171.0 tok/s"
        in page.text
    )
    assert "libalgenta_algenta_llm.sm_75.so" in page.text and "Traceback" not in page.text
    _assert_clean_copy(page.text)
    for url in (cfg.PRICING_URL, cfg.DISCORD_URL, cfg.DOCS_URL, cfg.LLAMA_CPP_URL):
        assert url in page.text

    failed = app.ProbeState(work=tmp_path / "f", versions={}, space={}, build={})
    app.run_probe(
        failed, _fake_runner(_run12_stage_data(artifact), {"driver": _failure("no_gpu", "none")})
    )
    client = testclient.TestClient(app.build_app(failed))
    assert client.get("/health").status_code == 503
    text = client.get("/").text
    assert "Stopped at driver: no_gpu" in text and "Traceback" not in text
    _assert_clean_copy(text)


def test_page_headline_pair_published_rows_and_secondary_rows(
    tmp_path: Path, artifact: dict
) -> None:
    data = _run12_stage_data(artifact)
    tokens = artifact["parity"]["reference_tokens"]
    data["baseline"] = _fixture_baseline(tokens, float16_code="baseline_oom")
    state = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    app.run_probe(state, _fake_runner(data))
    body = state.health()
    page = app.render_page(body)
    text = _page_text(page)
    _assert_clean_copy(page)
    status = text.index("Run complete.")
    race = text.index("The published race, live on this Tesla T4")
    secondary = text.index("Secondary rows on the same Tesla T4")
    assert status < race < secondary < text.index("Phases driver ok")
    assert "Algenta engine · f32 resident weights, per-token dispatch" in text
    assert "llama.cpp · F16 GGUF" in text
    assert "Decode tokens per second (gen=8) 190.0 tok/s 171.0 tok/s" in text
    assert "Decode tokens per second (gen=256) 184.3 tok/s 165.9 tok/s" in text
    assert "Prefill tokens per second (12 tokens) 3,100.0 tok/s 2,500.0 tok/s" in text
    assert "Prompt 59604, 374, 279, 6722" in text and "repeated" not in text
    assert "Identity vs the CPU reference 8/8, oracle 8/8 8/8, oracle 8/8" in text
    assert "Runs 3 timed, 1 warm-up excluded; identical tokens in every run" in text
    assert (
        "the wheel's certified conformance engine; the published cell ran the packed-int8 captured-graph session"
        in text
    )
    assert (
        "Measured ratio, Algenta engine over llama.cpp, decode at gen=8: 1.11; at gen=256: 1.11; prefill: 1.24 (both lanes decoded the same tokens)."
        in text
    )
    # the published rows: marked, both pages linked, never a measurement of this run
    assert (
        "Published 2026-08, same cell (L4), NVIDIA LLM serving 193.9 tok/s at gen=64, 188.8 at gen=256"
        in text
    )
    assert "1.12× slower at gen=64 (173.1 tok/s implied)" in text
    assert "NVIDIA LLM throughput 191.1 tok/s at gen=64, 184.8 at gen=256" in text
    assert "171.3 tok/s at gen=64, 172.6 at gen=256 (ratio 1.12 / 1.07)" in text
    assert page.count('class="published"') == 2 and page.count('class="hero"') == 2
    assert cfg.PUBLISHED_SERVING_URL in page and cfg.PUBLISHED_THROUGHPUT_URL in page
    # the secondary rows
    assert "Hub kernels · f32 resident, uploaded from the f64 blob" in text
    assert "transformers CUDA · float32" in text and "transformers CUDA · float16" in text
    assert "unavailable (baseline_oom)" in text
    assert (
        "transformers CUDA float16: unavailable, baseline_oom — OutOfMemoryError: CUDA out of memory."
        in text
    )
    assert (
        "41.67 s (= session open: the f64 blob uploaded as f32, then the prompt prefilled)" in text
    )
    assert "45.0 ms (step 1 of the timed generate: the prefill of the 256 prompt tokens)" in text
    for needle in (
        "Load / session open",
        "Steady per-token",
        "Tokens per second (steady)",
        "Device memory",
        "Precision",
        "Stack",
        "transformers 5.17.0 · torch 2.9.1+cu128 · CUDA 12.8",
        "Algenta engine Wheel algenta-runtime-native==1.0.7/conform_generate_cuda",
        "Compile target sm_89 Target gate compute capability 8.9: passed",
        f"llama.cpp Image {cfg.LLAMA_IMAGE_REF} Image tag {cfg.LLAMA_IMAGE_TAG} "
        f"Pinned build b{cfg.LLAMA_CPP_BUILD} Pinned commit {cfg.LLAMA_CPP_COMMIT}",
        f"Reported version version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})",
        f"CUDA architectures {cfg.LLAMA_CUDA_ARCHITECTURES}",
        "Published cell's build b10210 (000547513f), built from source for sm_89 only; "
        "not this build",
        f"Launch environment {cfg.LLAMA_LIBRARY_PATH_ENV}={cfg.LLAMA_BIN_DIR}:/usr/local/cuda/lib64 "
        f"{cfg.LLAMA_BACKEND_PATH_ENV}={cfg.LLAMA_BIN_DIR}",
        f"llama.cpp b{cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_IMAGE_KIND}) · "
        f"commit {cfg.LLAMA_CPP_COMMIT[:9]} · f16 GGUF",
        "The published cell's opponent was llama.cpp build 10210 compiled from source for sm_89 "
        f"alone; this run's is build {cfg.LLAMA_CPP_BUILD} from ggml-org's official CUDA image "
        f"({cfg.LLAMA_IMAGE_TAG}, by digest), which carries the common architectures — a build "
        f"{cfg.LLAMA_CPP_BUILD - 10210} tags later, not the identical one.",
        f"build {cfg.LLAMA_CPP_TAG} from ggml-org's official CUDA image, by digest.",
        "Identity Algenta engine · f32 resident weights, per-token dispatch 8/8, oracle 8/8",
        "warm-up run excluded, then 3 timed runs, each figure the median",
    ):
        assert needle in text, needle
    # tokens that differ: marked, no ratio
    other = [*tokens[:4], 100, *tokens[5:]]
    data["engine"] = _fixture_engine(other)
    diverged = app.ProbeState(work=tmp_path / "d", versions={}, space={}, build={})
    app.run_probe(diverged, _fake_runner(data))
    body = diverged.health()
    assert (
        body["race"]["ratio"]["same_tokens"] is False
        and body["race"]["ratio"]["decode_gen64"] is None
    )
    text = _page_text(app.render_page(body))
    assert "No ratio: the two lanes decoded different tokens." in text
    assert "4/8, oracle 4/8, first divergence at index 4" in text
    assert "(8 tokens, differ from the reference)" in text
    record = json.loads(diverged.run_json.read_text(encoding="utf-8"))
    assert record["decision"] == "parity_failed" and "engine" in record["decision_reason"]


def test_earlier_records_replay_through_the_race_view(
    tmp_path: Path, artifact13: dict, artifact14: dict
) -> None:
    """Run 13 (schema 2: no baseline) and run 14 (schema 3: baseline, no race) render as they
    were measured: the race lanes say the record predates them, the Hub lane and (for run 14)
    the transformers lanes carry their own figures, and nothing reads as a failure."""
    assert artifact13["schema"] == "algenta-gpu-probe/2" and "baseline" not in artifact13
    assert artifact14["schema"] == "algenta-gpu-probe/3" and "engine" not in artifact14
    for record in (artifact13, artifact14):
        view = core.race_view(record)
        assert view["predates"] is True and view["gpu"] == "Tesla T4"
        assert view["n_prompt"] == 12 and view["gen_tokens"] == 8
        engine, llama = view["race"]
        assert engine["status"] == llama["status"] == core.ABSENT_LANE
        assert engine["message"] == "not in this record"
        hub = view["secondary"][0]
        assert hub["status"] == core.OK_LANE and hub["identity"]["verdict"] == "8/8"
        assert hub["load_s"] == record["decode"]["open_s"]
        assert (
            hub["decode_tok_per_s"]
            == core.step_timings(record["decode"]["step_ms"])["decode_tok_per_s"]
        )
        page = app.render_page(record)
        text = _page_text(page)
        _assert_clean_copy(page)
        assert app.RACE_PREDATES in text and "Decode tokens per second (gen=8)" in text
        assert "unavailable" not in text and "Stopped at" not in text and " error" not in text
        assert (
            "Tokens (8 greedy) Germany. Which of the following is true (8 tokens, the reference's)"
            in text
        )
        assert "Published 2026-08, same cell (L4)" in text
    view13 = core.race_view(artifact13)
    assert [lane["status"] for lane in view13["secondary"][1:]] == [
        core.ABSENT_LANE,
        core.ABSENT_LANE,
    ]
    assert _page_text(app.render_page(artifact13)).count("not measured in this run") >= 4
    view14 = core.race_view(artifact14)
    f32, f16 = view14["secondary"][1:]
    assert f32["status"] == f16["status"] == core.OK_LANE
    assert (
        f32["decode_tok_per_s"]
        == core.step_timings(artifact14["baseline"]["lanes"]["float32"]["step_ms"])[
            "decode_tok_per_s"
        ]
    )
    assert f32["load_s"] == artifact14["baseline"]["lanes"]["float32"]["load_s"]
    assert f16["vram_bytes"] == artifact14["baseline"]["lanes"]["float16"]["device_taken_bytes"]
    text14 = _page_text(app.render_page(artifact14))
    assert "Tokens per second (steady)" in text14 and "peak allocated by torch" in text14
    # the two race cells and the two identity rows; the transformers lanes are measured
    assert text14.count("not measured in this run") == 4


def test_identifiers_render_plain_and_quantities_with_separators(artifact13: dict) -> None:
    text = _page_text(app.render_page(artifact13))
    assert "9856, 13, 15920" in text and "9,856" not in text and "15,920" not in text
    assert "Staging tier 6144" in text and "6,144" not in text
    assert "Memory 15,360 MiB (15,828,320,256 bytes)" in text
    assert "12.82 GiB (13,764,599,808 bytes)" in text
    assert app._fmt([59604, 374], plain=True) == "59604, 374"
    assert app._fmt(13764599808) == "13,764,599,808"
    assert app._memory("15360 MiB", 15828320256) == "15,360 MiB (15,828,320,256 bytes)"
    assert app._memory("n/a", None) == "n/a" and app._memory(None, None) == app.ABSENT
    assert app._tok_s(193.94) == "193.9 tok/s" and app._tok_s(None) is None
    assert app._ms_value(82.04) == "82.0 ms" and app._ms_value(43820.0) == "43.82 s"


def test_step_clock_times_tokens_as_they_reach_the_host(monkeypatch: pytest.MonkeyPatch) -> None:
    class Tensor:
        def __init__(self, values: list[int]) -> None:
            self.values = values

        def reshape(self, _shape: int) -> Tensor:
            return self

        def tolist(self) -> list[int]:
            return list(self.values)

    ticks = iter([100.0, 100.0, 100.09, 100.13, 100.17, 100.21])
    monkeypatch.setattr(probe.time, "perf_counter", lambda: next(ticks))
    clock = probe.StepClock()
    clock.start()
    clock.put(Tensor([59604, 374, 279]))
    clock.put(Tensor([9856]))
    clock.put(Tensor([13]))
    clock.put(Tensor([15920]))
    assert clock.prompt_echoed(3) and not clock.prompt_echoed(4)
    tokens, step_ms = clock.token_times()
    assert tokens == [9856, 13, 15920]
    assert [round(ms, 3) for ms in step_ms] == [130.0, 40.0, 40.0]
    assert probe.STAGES["baseline"] is probe.stage_baseline
    assert cfg.BASELINE_DTYPES == ("float32", "float16")


def test_page_copy_has_no_banned_words_or_exclamations() -> None:
    for text in (
        app.TITLE,
        app.HEADLINE,
        app.SUBLINE,
        app.PAGE_TEMPLATE,
        app.RACE_CAPTION,
        app.SECONDARY_CAPTION,
        app.RACE_PREDATES,
        core.ENGINE_SESSION_NOTE,
    ):
        _assert_clean_copy(text)
    assert copy_lint.word_count(app.HEADLINE) <= copy_lint.HEADLINE_MAX_WORDS
    assert copy_lint.word_count(app.SUBLINE) <= copy_lint.SUBLINE_MAX_WORDS
    assert "!important" not in app.PAGE_CSS


# --- the Space directory: README, Dockerfile, requirements, manifest decision ---------------


def _frontmatter(readme: Path) -> dict[str, str]:
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if line.startswith((" ", "\t", "-")):
            continue
        key, _, raw = line.partition(":")
        fields[key.strip()] = raw.strip().strip("\"'")
    return fields


def test_readme_card_and_copy_lint() -> None:
    front = _frontmatter(PROBE_DIR / "README.md")
    assert front["title"] == "Algenta GPU probe"
    assert front["sdk"] == "docker" and front["hardware"] == cfg.HARDWARE == "l4x1"
    assert front["suggested_hardware"] == "l4x1"
    assert front["pinned"] == "false" and front["app_port"] == str(cfg.APP_PORT)
    assert front["short_description"] == "Qwen3-0.6B-Base: the published CUDA race, live on an L4"
    assert len(front["short_description"]) <= 60
    body = (PROBE_DIR / "README.md").read_text(encoding="utf-8")
    for url in (cfg.DOCS_URL, cfg.PRICING_URL, cfg.DISCORD_URL, cfg.MODEL_HUB_URL):
        assert url in body, url
    assert "licensing@" not in body and "decision engine" not in body.lower()
    assert "Apache-2.0" in body and "private" in body and "paused" in body and "MIT" in body
    joined = " ".join(body.split())
    assert "the median of three timed runs, exactly the shape of the published L4 cell." in joined
    assert "engine_target_mismatch" in joined and "llama-server -ngl 99" in joined
    assert copy_lint.lint_space(PROBE_DIR) == []


def test_dockerfile_pins_and_conventions() -> None:
    """Lane B comes prebuilt: ggml-org's official CUDA server image by digest, nothing compiled
    (the Hub's builder cut the source build off at 62 minutes); the converter is a shallow
    checkout of the same commit in a stage of its own, git never reaches the runtime image."""
    text = (PROBE_DIR / "Dockerfile").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    runtime_base = (
        "nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:"
        "ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867"
    )
    froms = [line for line in lines if line.startswith("FROM ")]
    assert froms == [
        f"FROM {cfg.LLAMA_IMAGE}@{cfg.LLAMA_IMAGE_DIGEST} AS llama",
        f"FROM {runtime_base} AS converter",
        f"FROM {runtime_base}",
    ]
    copies = [line for line in lines if line.startswith("COPY --from=")]
    assert len(copies) == 3
    assert re.search(r"uv:\d+\.\d+\.\d+@sha256:[0-9a-f]{64} ", copies[0])
    assert copies[1] == f"COPY --from=llama /app/ {cfg.LLAMA_BIN_DIR}/"
    assert copies[2] == f"COPY --from=converter {cfg.LLAMA_DIR} {cfg.LLAMA_DIR}"
    joined = "\n".join(lines)
    assert not re.search(r"(?<=[\w}./-]):-?latest\b", joined, re.IGNORECASE)
    # the three pins as build arguments; the digest repeated literally in FROM, nowhere else
    assert f"ARG LLAMA_CPP_COMMIT={cfg.LLAMA_CPP_COMMIT}" in text
    assert f"ARG LLAMA_CPP_BUILD={cfg.LLAMA_CPP_BUILD}" in text
    assert f"ARG LLAMA_IMAGE_DIGEST={cfg.LLAMA_IMAGE_DIGEST}" in text
    assert joined.count(cfg.LLAMA_IMAGE_DIGEST) == 2
    assert f"{cfg.LLAMA_IMAGE}:{cfg.LLAMA_IMAGE_TAG}" in text, "the tag is named for the reader"
    # no compiler, no build system, no source build, no devel image anywhere
    for token in (
        "cmake",
        "ninja",
        "build-essential",
        "-DGGML_CUDA",
        "devel-ubuntu",
        "LLAMA_CUDA_ARCHITECTURES",
        "llama-build",
    ):
        assert token not in joined, token
    # git in the converter stage only, fetching exactly the pinned commit, writing the pin files
    stages = re.split(r"^FROM .*$", joined, flags=re.M)
    assert len(stages) == 4
    converter, runtime = stages[2], stages[3]
    assert 'git fetch -q --depth 1 origin "${LLAMA_CPP_COMMIT}"' in converter
    assert 'test "$(git rev-parse HEAD)" = "${LLAMA_CPP_COMMIT}"' in converter
    assert "git" not in runtime
    for needle in (
        "convert_hf_to_gguf.py",
        "gguf-py",
        f"{cfg.LLAMA_DIR}/conversion",
        f'echo "${{LLAMA_CPP_COMMIT}}" > {cfg.LLAMA_COMMIT_FILE}',
        f'echo "${{LLAMA_CPP_BUILD}}" > {cfg.LLAMA_BUILD_FILE}',
        f'echo "${{LLAMA_IMAGE_DIGEST}}" > {cfg.LLAMA_IMAGE_DIGEST_FILE}',
    ):
        assert needle in converter, needle
    # the runtime stage: the loader variable (and only that one: GGML_BACKEND_PATH names a single
    # out-of-tree backend library, run 16 set it to the directory), the fail-fast version check
    # before torch with no registry refusal allowed, the host libraries by name
    version_check = f'LD_LIBRARY_PATH="{cfg.LLAMA_BIN_DIR}:${{LD_LIBRARY_PATH}}" \\'
    assert version_check in runtime and f"{cfg.LLAMA_SERVER} --version" in runtime
    assert "GGML_BACKEND_PATH" not in joined, "no launch names a backend library"
    assert 'grep -qE "^version: ${LLAMA_CPP_BUILD} \\("' in runtime
    assert (
        '! grep -qE "load_backend: failed|ggml_backend_load_best: failed" /opt/llama/VERSION'
        in runtime
    )
    assert runtime.index(version_check) < runtime.index("uv pip install")
    assert "libgomp1 libssl3t64" in runtime
    assert "NVIDIA_DISABLE_REQUIRE=1" in text
    assert re.findall(r"^EXPOSE\s+(\d+)", text, re.M) == [str(cfg.APP_PORT)]
    assert "useradd --create-home --uid 1000" in text
    bake = text.index("python fetch_assets.py --bake")
    assert text.index("USER user") < bake, "the bake runs as the runtime user"
    assert "HF_HUB_OFFLINE=1 python fetch_assets.py --verify" in text
    assert text.index("ENV HF_HUB_OFFLINE=1") > bake, "offline is set after the bake"
    assert "uv python install 3.14" in text and "--index-strategy unsafe-best-match" in text
    assert "PROBE_ASSETS_DIR=/home/user/assets" in text
    assert text.rstrip().endswith('CMD ["python", "app.py"]')


def _pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name, _, version = line.partition("==")
        pins[name.strip().split("[", 1)[0].lower().replace("-", "_")] = version.strip()
    return pins


def test_requirements_are_exact_and_agree_with_the_flagship() -> None:
    text = (PROBE_DIR / "requirements.txt").read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            assert re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[A-Za-z0-9_.+\-]+", line), line
    assert "--extra-index-url https://download.pytorch.org/whl/cu128" in text
    pins = _pins(PROBE_DIR / "requirements.txt")
    assert pins["torch"] == "2.9.1+cu128"
    assert pins["kernels"] == "0.17.1" and pins["huggingface_hub"] == "1.26.1"
    assert pins["transformers"] == "5.17.0" and pins["safetensors"] == "0.8.0"
    assert pins["algenta"] == "1.0.28"
    assert pins["algenta_runtime_native"] == cfg.ENGINE_WHEEL_VERSION == "1.0.7"
    for name in ("tqdm", "pyyaml", "requests"):
        assert name in pins, f"{name}: gguf-py's dependency for the GGUF conversion"
    # the converter's own imports on the Qwen3 path (run 16: ModuleNotFoundError sentencepiece),
    # every one an exact pin with a CPython 3.14 linux x86_64 wheel; protobuf above the
    # converter's <5.0.0 cap because 4.25.8's abi3 extension does not import on 3.14
    for name in cfg.LLAMA_CONVERTER_PACKAGES:
        assert name.lower() in pins, f"{name}: the converter imports it"
    assert pins["sentencepiece"] == "0.2.2" and pins["protobuf"] == "7.36.2"
    assert "sentencepiece" in cfg.LLAMA_CONVERTER_PACKAGES
    assert "protobuf" in cfg.LLAMA_CONVERTER_PACKAGES
    assert "Metaclasses with custom tp_new" in text, "why protobuf is not the converter's range"
    flagship = _pins(FLAGSHIP_DIR / "requirements.txt")
    for name in ("kernels", "huggingface_hub", "algenta", "numpy", "fastapi", "uvicorn"):
        if name in flagship:
            assert pins[name] == flagship[name], f"{name} disagrees with the flagship"
    assert probe.PACKAGES[0] == "torch"


def test_probe_is_not_in_the_fleet_manifest_and_deploys_by_hand() -> None:
    manifest = load_manifest()
    assert "gpu-probe" not in manifest.spaces
    assert all(s.repo_id != cfg.SPACE_REPO_ID for s in manifest.spaces.values())
    deploy_md = (PROBE_DIR / "DEPLOY.md").read_text(encoding="utf-8")
    for needle in (
        "private=True",
        "upload_folder",
        "request_space_hardware",
        '"l4x1"',
        "pause_space",
        "restart_space",
        "get_space_runtime",
        cfg.SPACE_REPO_ID,
        "t4-small",
    ):
        assert needle in deploy_md, needle
    assert "licensing@" not in deploy_md
    assert cfg.LLAMA_IMAGE_TAG in deploy_md and "62 minutes" in deploy_md
    readme = (PROBE_DIR / "README.md").read_text(encoding="utf-8")
    assert f"`{cfg.LLAMA_IMAGE_TAG}`" in readme and "by digest" in readme
    assert "build 10210 compiled from source for sm_89 alone" in readme
    doc = (REPO / "docs/spaces/GPU-PROBE.md").read_text(encoding="utf-8")
    for needle in (
        "l4x1",
        "t4-small",
        "sm_90a",
        "engine_target_mismatch",
        "conform_generate_cuda",
        "llama-server",
        "convert_hf_to_gguf.py",
        cfg.LLAMA_CPP_COMMIT[:10],
        cfg.PUBLISHED_LLAMA_CPP_COMMIT[:10],
        f"`{cfg.LLAMA_IMAGE_TAG}`",
        cfg.LLAMA_IMAGE_DIGEST,
        cfg.LLAMA_IMAGE_AMD64_DIGEST,
        "Lane B's binary",
        "llama_version_mismatch",
        "GGML_BACKEND_PATH",
        "62 minutes",
        "193.9",
        "`engine`",
        "`llama`",
        "baseline_oom",
        "run_budget_exhausted",
        "$0.80",
    ):
        assert needle in doc, needle
    for name in cfg.PRIOR_ARTIFACTS:
        assert (REPO / name).is_file(), name
    fleet = (REPO / "docs/spaces/README.md").read_text(encoding="utf-8")
    assert "`l4x1`" in fleet and "apps/spaces/gpu-probe/" in fleet


def test_stage_ignore_patterns_keep_tests_and_caches_out_of_the_upload() -> None:
    stage = importlib.import_module("stage")
    files = sorted(p.name for p in PROBE_DIR.iterdir() if p.is_file())
    assert {
        "README.md",
        "Dockerfile",
        "requirements.txt",
        "app.py",
        "probe.py",
        "probe_core.py",
        "probe_config.py",
        "fetch_assets.py",
        "hf_ua_shim.py",
        "DEPLOY.md",
        "ruff.toml",
        ".gitignore",
    } <= set(files)
    for rel in stage.iter_files(PROBE_DIR):
        if rel.parts[0] == "engine":
            # the sm_89 engine is copied in at deploy time only (git-ignored, DEPLOY.md)
            continue
        assert not stage.is_ignored(rel)
        assert (PROBE_DIR / rel).stat().st_size <= stage.MAX_FILE_BYTES
    assert stage.frontmatter_sdk((PROBE_DIR / "README.md").read_text(encoding="utf-8")) == "docker"


def test_user_agent_shim_removes_every_trailing_separator_and_space() -> None:
    """The header is refused by h11 for trailing whitespace, whatever produced it: one `"; "`
    (kernels' empty user_agent), a doubled separator, or a bare trailing space all come back
    legal. `rstrip("; ")` is the intended semantics — a token that legitimately ended in `;` or a
    space would itself be the illegal form (Codna review on #1169)."""
    shim = _load_by_file("hf_ua_shim_probe", "hf_ua_shim.py")
    for raw in ("kernels/0.17.1; ", "kernels/0.17.1;; ", "foo/1.0 ", "kernels/0.17.1"):
        cleaned = shim.clean_user_agent(raw)
        assert cleaned == cleaned.rstrip(), raw
        assert not cleaned.endswith(";"), raw
    assert shim.clean_user_agent("kernels/0.17.1; torch/2.9.1; ") == "kernels/0.17.1; torch/2.9.1"


# --- lane A's second protocol: the packed-int8 captured-graph driver ---------------------------

#: The driver's prints, line for line as `benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo`
#: spells them (Mojo's `print` joins its arguments with one space, hence `n_steps= 32 :` and
#: `0.69 %`). The figures are the L4 ledger's shape; none is a measurement of this run.
P3_DRIVER_OUTPUT = (
    "qwen3_p3_graph_cuda: checkpoint = /home/user/work/qwen3-0.6b-base-f64-cuda | d_model = 1024"
    " | n_layers = 28 | h_q = 16 | h_kv = 8 | d_head = 128 | d_ff = 3072 | vocab = 151936"
    " | n_prompt = 256 | max_ctx = 1024\n"
    "  device: NVIDIA L4\n"
    "  one-time load (f32 half + packed3 twins + upload): 21873.4 ms\n"
    "  captured replay nodes per token: 200 (vs 171 per-dispatch enqueues per token)\n"
    "  graph-arm packed3 kernels: v4 (int32 unpack + fused gate/up swiglu)\n"
    "G0 — packed3 graph arm, 16 greedy tokens on the race fixture\n"
    "G0 RESULT: PASS — 16 greedy tokens match the campaign oracle through one async chain\n"
    "G1 — graph-p3 vs per-dispatch-p3, 3 seeds x 128 steps\n"
    "  seed 0 (offset 0 ): 128 / 128 tokens identical — graph == per-dispatch\n"
    "G1 RESULT: PASS — 3 seeds x 128 steps token-for-token identical"
    " (graph == per-dispatch == oracle via G0)\n"
    "G2 — engagement: graph-p3 per-step wall at n_steps 32/64/128/256 vs per-dispatch-p3"
    " ( 7 -run medians, 2 warmup)\n"
    "  n_steps= 32 : graph-p3 5.07 ms/step vs per-dispatch-p3 13.43 ms/step\n"
    "  n_steps= 64 : graph-p3 5.1 ms/step vs per-dispatch-p3 13.4 ms/step\n"
    "  n_steps= 128 : graph-p3 5.2 ms/step vs per-dispatch-p3 13.45 ms/step\n"
    "  n_steps= 256 : graph-p3 5.31 ms/step vs per-dispatch-p3 13.5 ms/step\n"
    "G2 RESULT: PASS — per-step wall flat (spread 4.24 % <=  10.0 %) and strictly faster than"
    " per-dispatch at all four depths\n"
    "\n"
    "Throughput (decode-only; prefill excluded from the timed window), {runs} timed runs per"
    " cell (1 untimed warmup each):\n"
    "  gen 64  graph-p3       : median 330.01 ms | rel IQR 0.69 % | outliers 0 | 193.93 tok/s"
    " (PASS, frozen 5%)\n"
    "  gen 64  f32-graph      : median 654.7 ms | rel IQR 0.2 % | outliers 0 | 97.76 tok/s"
    " (PASS, frozen 5%)\n"
    "  gen 64  per-dispatch-p3: median 860.2 ms | rel IQR 6.1 % | outliers 1 | 74.4 tok/s"
    " (FLAGGED, frozen 5%)\n"
    "  gen 64  graph-p3 vs ledger:  0.479 x llama.cpp Q8_0 ( 404.8 tok/s ) | 0.543 x llama.cpp"
    " F16 ( 356.9 tok/s )\n"
    "  gen 64  f32-graph vs ledger: 0.24 x Q8_0 | 0.27 x F16 | graph-p3 / f32-graph: 1.98\n"
    "  gen 256  graph-p3       : median 1355.9 ms | rel IQR 0.11 % | outliers 0 | 188.81 tok/s"
    " (PASS, frozen 5%)\n"
    "  gen 256  f32-graph      : median 2643.5 ms | rel IQR 0.1 % | outliers 0 | 96.84 tok/s"
    " (PASS, frozen 5%)\n"
    "  gen 256  per-dispatch-p3: median 3440.0 ms | rel IQR 0.3 % | outliers 0 | 74.42 tok/s"
    " (PASS, frozen 5%)\n"
    "\n"
    "qwen3_p3_graph_cuda: done (G0 + G1 + G2 all PASS)\n"
)
P3_ENGINE_SHA = "af92012a45c587cf625ed75e4eaecb823bcf8528cdbc1563abe05d5cc90bd82b"
P3_CLOSURE = (
    "libKGENCompilerRTShared.so",
    "libAsyncRTMojoBindings.so",
    "libstdc++.so.6",
    "libMSupportGlobals.so",
    "libAsyncRTRuntimeGlobals.so",
    "libgcc_s.so.1",
)


def _p3_manifest(sha: str, *, name: str = cfg.P3_ENGINE_NAME) -> dict:
    """The manifest the sm_89 build writes beside the binary (cuda-engine-sm89/out/manifest.json),
    in shape; the sha is the fixture file's."""
    return {
        "format_version": 1,
        "kind": "algenta-gpu-probe-engine",
        "platform": "linux-x86_64",
        "build_variant": "cuda",
        "cuda_target": "sm_89",
        "artifacts": [{"name": name, "sha256": sha, "size_bytes": 7}],
        "engine": {
            "name": name,
            "source": cfg.P3_ENGINE_SOURCE,
            "session": cfg.P3_ENGINE_SESSION,
            "sha256": sha,
            "size_bytes": 7,
            "cuda_target": "sm_89",
            "comptime_defines": ["ALGENTA_GPU", "ALGENTA_CUDA"],
            "host_shared_libraries": [],
            "runtime_dlopen_libraries": ["libcuda.so.1"],
            "bundled_shared_libraries": list(P3_CLOSURE),
            "source_commit": "6029d6af0085838141e8076650e1e5784499ed18",
            "source_dirty": False,
            "built_utc": "2026-09-24T20:38:58Z",
            "toolchain": {"mojo": "Mojo 1.0.0 (ed45d567)", "max": "max-26.5.0-3.14release"},
            "signed": False,
        },
    }


def _fixture_p3_engine(*, runs: int = cfg.RUNS) -> dict:
    """Lane A's stage report when the packed-int8 graph driver ran, built the way
    `probe.stage_engine` builds it from one parsed launch; every figure is the ledger-shaped
    fixture above, none a measurement."""
    launch = core.parse_p3_engine_output(P3_DRIVER_OUTPUT.format(runs=runs), "", 0)
    launch.update(
        wall_s=140.2,
        vram_peak_bytes=1_900_000_000,
        vram_samples=560,
        argv=["/home/user/engine/qwen3_p3_graph_cuda", "ckpt", "--runs", str(runs)],
    )
    block = probe.p3_engine_block(
        launch, snapshot=Path("/nonexistent"), ids=core.campaign_prompt_ids(), fixture="campaign"
    )
    manifest = _p3_manifest(P3_ENGINE_SHA)["engine"]
    return {
        "engine": {
            "name": cfg.P3_ENGINE_NAME,
            "protocol": cfg.P3_ENGINE_NAME,
            "path": "/home/user/engine/qwen3_p3_graph_cuda",
            "dir": "/home/user/engine",
            "resolved_from": "$ALGENTA_CUDA_ENGINE",
            "searched": ["$ALGENTA_CUDA_ENGINE"],
            "wheel_version": cfg.ENGINE_WHEEL_VERSION,
            "size_bytes": 966464,
            "sha256": P3_ENGINE_SHA,
            "libcudart_beside": False,
            "manifest": "/home/user/engine/manifest.json",
            "cuda_target": "sm_89",
            "comptime_defines": manifest["comptime_defines"],
            "host_shared_libraries": [],
            "bundled_shared_libraries": list(P3_CLOSURE),
            "bundled_beside": True,
            "sha256_declared": P3_ENGINE_SHA,
            "sha256_matches": True,
            "source": cfg.P3_ENGINE_SOURCE,
            "source_commit": manifest["source_commit"],
            "built_utc": manifest["built_utc"],
            "mojo_version": manifest["toolchain"]["mojo"],
            "session": manifest["session"],
            "build_variant": "cuda",
        },
        "target_gate": core.engine_target_gate("sm_89", (8, 9)),
        "fixture_gate": {
            "active_fixture": "campaign",
            "manifest_prompt_ids_match": True,
            "n_prompt_baked": 256,
        },
        "host_libraries": {},
        "ld_library_path": "/home/user/engine",
        "checkpoint_dir": "ckpt",
        **block,
        "max_rss_mib": 120.0,
    }


def test_p3_driver_pins_agree_with_its_source_and_the_ledger() -> None:
    """The pins are read off the driver's source (its gate lengths, its fixed gen lengths, its
    argv, its oracle), the campaign fixture off `prepare_smoke_checkpoint.py`, the build's
    define set off the L4 ledger, and the override variable off the SDK's resolver."""
    mojo = (REPO / cfg.P3_ENGINE_SOURCE).read_text(encoding="utf-8")
    assert "comptime G0_TOKENS: Int = 16" in mojo and cfg.P3_ORACLE_TOKENS == 16
    assert "gen_lengths.append(64)" in mojo and "gen_lengths.append(256)" in mojo
    assert cfg.P3_GEN_LENGTHS == (64, 256)
    assert "comptime WARMUP: Int = 1" in mojo and cfg.WARMUP_RUNS == 1
    assert 'a == "--runs"' in mojo and 'a == "--checkpoint"' in mojo
    for absent in ("--max-new", "--prompt-len", "CONFORM_TIMING", "CONFORM_TOKENS"):
        assert absent not in mojo, absent
    for literal, _code in core.P3_OUTPUT_CODES:
        assert literal in mojo or literal == "resident_no_accelerator_present", literal
    contract = (REPO / "mojo/engine/residentk/contract.mojo").read_text(encoding="utf-8")
    assert '"resident_no_accelerator_present"' in contract
    # the oracle: the window and the cycle are `_oracle_token`'s literals, in its order
    window = re.findall(r"if i == (\d):\n\s+return (\d+)", mojo)
    assert [int(t) for _i, t in window] == list(cfg.CAMPAIGN_ORACLE_WINDOW)
    cycle = re.findall(r"if cycle_pos == (\d):\n\s+return (\d+)", mojo)
    assert [int(t) for _i, t in cycle] + [374] == list(cfg.CAMPAIGN_ORACLE_CYCLE)
    assert core.campaign_oracle_tokens(8) == list(cfg.CAMPAIGN_ORACLE_WINDOW)
    assert core.campaign_oracle_tokens(15)[8:] == list(cfg.CAMPAIGN_ORACLE_CYCLE)
    assert core.campaign_oracle_tokens()[:4] == [374, 12095, 13, 576]
    # the campaign fixture: 785, the seven-id cycle 36 times, then its first three ids
    prep = (REPO / "benchmarks/llm_smoke/nvidia_race/prepare_smoke_checkpoint.py").read_text(
        encoding="utf-8"
    )
    assert '"The capital of France is Paris. " * 36 + "The capital of France"' in prep
    assert (
        cfg.CAMPAIGN_PROMPT_TEXT
        == "The capital of France is Paris. " * 36 + "The capital of France"
    )
    assert "_EXPECTED_FIRST_GENERATED = 374" in prep and core.campaign_oracle_tokens(1) == [374]
    ids = core.campaign_prompt_ids()
    assert len(ids) == 256 == cfg.PROMPT_TOKENS
    assert ids == [785] + [6722, 315, 9625, 374, 12095, 13, 576] * 36 + [6722, 315, 9625]
    assert ids != core.battery_prompt_ids() and set(ids) == set(cfg.PROMPT_CYCLE_IDS)
    assert core.campaign_prompt_ids(1) == [785] and core.campaign_prompt_ids(0) == []
    # the L4 ledger's build line for this driver, verbatim
    ledger = (REPO / "benchmarks/llm_smoke/REALRACE_RESULTS.md").read_text(encoding="utf-8")
    assert "p3 graph decode driver: -D ALGENTA_GPU -D ALGENTA_CUDA" in ledger
    assert "| decode gen64 @256     | 193.93 (IQR 0.69%)" in ledger
    # the resolver's first override
    engine_py = (REPO / "packages/algenta/algenta/serve/engine.py").read_text(encoding="utf-8")
    assert f'CUDA_ENGINE_ENV_VARS: tuple[str, ...] = ("{cfg.ENGINE_ENV}"' in engine_py
    assert cfg.ENGINE_PROTOCOLS == ("conform_generate_cuda", "qwen3_p3_graph_cuda")
    assert cfg.P3_ENGINE_RUN_TIMEOUT_S < cfg.STAGE_TIMEOUTS_S["engine"]


def test_prompt_fixture_follows_the_selected_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    p3 = "/home/user/engine/qwen3_p3_graph_cuda"
    assert core.engine_protocol_of(p3) == cfg.P3_ENGINE_NAME
    assert core.engine_protocol_of("conform_generate_cuda") == cfg.ENGINE_NAME
    assert core.engine_protocol_of("/opt/x/other_engine") is None
    assert core.engine_protocol_of(None) is None
    assert core.selected_engine({}) is None and core.selected_engine({cfg.ENGINE_ENV: " "}) is None
    assert core.active_prompt_fixture({}) == "battery"
    assert core.active_prompt_fixture({cfg.ENGINE_ENV: p3}) == "campaign"
    assert core.active_prompt_fixture({cfg.ENGINE_ENV: "/opt/x/conform_generate_cuda"}) == "battery"
    assert core.active_prompt_fixture({cfg.ENGINE_ENV: p3, cfg.PROMPT_FIXTURE_ENV: "battery"}) == (
        "battery"
    )
    assert core.active_prompt_fixture({cfg.PROMPT_FIXTURE_ENV: "CAMPAIGN"}) == "campaign"
    with pytest.raises(core.ProbeError) as exc:
        core.active_prompt_fixture({cfg.PROMPT_FIXTURE_ENV: "other"})
    assert exc.value.code == "prompt_fixture_unknown"
    assert core.prompt_fixture_pin({cfg.PROMPT_FIXTURE_ENV: "other"}).startswith("unknown (")
    assert core.race_prompt_ids(fixture="campaign") == core.campaign_prompt_ids()
    assert core.race_prompt_ids(fixture="battery") == core.battery_prompt_ids()
    assert core.race_prompt_ids(8, fixture="battery") == list(cfg.PROMPT_CYCLE_IDS)
    with pytest.raises(core.ProbeError):
        core.race_prompt_ids(fixture="other")
    monkeypatch.delenv(cfg.PROMPT_FIXTURE_ENV, raising=False)
    monkeypatch.setenv(cfg.ENGINE_ENV, p3)
    assert core.race_prompt_ids() == core.campaign_prompt_ids()
    pins = core.health_body(core.PhaseMachine())["pins"]
    assert pins["prompt_fixture"] == "campaign" and pins["engine_selected"] == p3
    assert pins["engine_protocol"] == cfg.P3_ENGINE_NAME
    monkeypatch.delenv(cfg.ENGINE_ENV)
    pins = core.health_body(core.PhaseMachine())["pins"]
    assert pins["prompt_fixture"] == "battery" and pins["engine_selected"] is None
    assert pins["engine_protocol"] == cfg.ENGINE_NAME


def test_parse_p3_driver_output_reads_the_real_lines_and_names_refusals() -> None:
    parsed = core.parse_p3_engine_output(P3_DRIVER_OUTPUT.format(runs=3), "", 0)
    assert parsed["n_prompt"] == 256 and parsed["model"]["d_ff"] == 3072
    assert parsed["device"] == "NVIDIA L4" and parsed["load_ms"] == 21873.4
    assert parsed["graph_nodes"] == 200 and parsed["dispatch_budget"] == 171
    assert parsed["kernel_variant"] == "v4 (int32 unpack + fused gate/up swiglu)"
    assert {k: v["passed"] for k, v in parsed["gates"].items()} == {
        "G0": True,
        "G1": True,
        "G2": True,
    }
    assert [s["n_steps"] for s in parsed["g2_steps"]] == [32, 64, 128, 256]
    assert parsed["g2_steps"][0] == {
        "n_steps": 32,
        "graph_p3_ms_per_step": 5.07,
        "per_dispatch_p3_ms_per_step": 13.43,
    }
    assert parsed["runs"] == 3 and parsed["warmup"] == 1
    assert parsed["cells"]["64"]["graph_p3"] == {
        "median_ms": 330.01,
        "rel_iqr_pct": 0.69,
        "outliers": 0,
        "decode_tok_per_s": 193.93,
        "iqr_verdict": "PASS",
    }
    assert parsed["cells"]["64"]["per_dispatch_p3"]["iqr_verdict"] == "FLAGGED"
    assert parsed["cells"]["256"]["graph_p3"]["decode_tok_per_s"] == 188.81
    assert parsed["done"] == "G0 + G1 + G2 all PASS"
    cells = core.p3_cells(parsed, vram_peak_bytes=1_900_000_000)
    assert set(cells) == {"64", "256"}
    hero = cells["64"]["summary"]
    assert hero["decode_tok_per_s"] == 193.93 and hero["n_runs"] == 3
    assert hero["prefill_tok_per_s"] is None and hero["ttft_ms"] is None
    assert hero["tokens"] == core.campaign_oracle_tokens() and hero["runs_agree"] is None
    assert hero["vram_peak_bytes"] == 1_900_000_000 and hero["iqr_verdict"] == "PASS"
    assert set(hero["arms"]) == {"f32_graph", "per_dispatch_p3"}
    assert cells["256"]["summary"]["decode_tok_per_s"] == 188.81 and cells["64"]["timed"] == []
    # the v3 build's G1 form is a reporting gate, not a failure
    v3 = P3_DRIVER_OUTPUT.format(runs=3).replace(
        "G1 RESULT: PASS — 3 seeds x 128 steps token-for-token identical"
        " (graph == per-dispatch == oracle via G0)",
        "G1 RESULT: 0 total flip(s) vs the f32 session across all seeds (reporting gate;"
        " G0 16/16 remains HARD)",
    )
    assert core.parse_p3_engine_output(v3, "", 0)["gates"]["G1"]["passed"] is True
    # refusals and failed gates, each its own code
    cases = [
        (
            "qwen3_p3_graph_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA",
            0,
            "engine_binary_not_cuda_build",
        ),
        ("qwen3_p3_graph_cuda: no accelerator on this host", 1, "engine_no_gpu"),
        (
            "qwen3_p3_graph_cuda: cannot run a resident session here: resident_no_accelerator_present",
            1,
            "engine_no_gpu",
        ),
        (
            "qwen3_p3_graph_cuda: cannot run a resident session here: resident_dimension_too_large",
            1,
            "engine_resident_refused",
        ),
        (
            "x\n  ORACLE MISMATCH at generated token 3 : got 100 want 576\nG0 RESULT: FAIL — 1 mismatched tokens",
            1,
            "engine_oracle_mismatch",
        ),
        ("G0 RESULT: FAIL — 2 mismatched tokens", 1, "engine_oracle_mismatch"),
        ("G1 RESULT: FAIL — graph-p3 disagrees with per-dispatch-p3", 1, "engine_gate_failed"),
        ("G2 RESULT: FAIL — full table:", 1, "engine_gate_failed"),
    ]
    for text, rc, code in cases:
        with pytest.raises(core.ProbeError) as exc:
            core.parse_p3_engine_output(text, "", rc)
        assert exc.value.code == code, text
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output(
            "", "Unhandled exception caught during execution: Failed to open library x\n", 1
        )
    assert exc.value.code == "engine_run_failed" and "Failed to open library" in exc.value.message
    full = P3_DRIVER_OUTPUT.format(runs=3)
    for cut, needle in (
        ("qwen3_p3_graph_cuda: checkpoint =", "checkpoint header"),
        ("G2 RESULT: PASS", "G2 RESULT"),
        ("  gen 256  graph-p3       :", "gen 256 graph-p3"),
        ("Throughput (decode-only", "throughput header"),
    ):
        without = "\n".join(row for row in full.splitlines() if not row.startswith(cut))
        with pytest.raises(core.ProbeError) as exc:
            core.parse_p3_engine_output(without, "", 0)
        assert exc.value.code == "engine_no_timing" and needle in exc.value.message, cut


_P3_G1_PASS_LINE = (
    "G1 RESULT: PASS — 3 seeds x 128 steps token-for-token identical"
    " (graph == per-dispatch == oracle via G0)"
)


def _p3_output_with_g1(line: str) -> str:
    return P3_DRIVER_OUTPUT.format(runs=3).replace(_P3_G1_PASS_LINE, line)


def test_p3_gate_passes_only_on_pass_or_an_explicit_zero_flip_count() -> None:
    """The driver's G1 verdict forms, as `qwen3_p3_graph_cuda.mojo` prints them: `G1 RESULT:
    PASS — ...` / `G1 RESULT: FAIL — graph-p3 disagrees with per-dispatch-p3` for the v1/v2
    builds, and for the v3 build `G1 RESULT: <n> total flip(s) vs the f32 session across all
    seeds (reporting gate; G0 16/16 remains HARD)` — the driver reports that count and exits 0.
    The probe passes the gate on PASS or on zero flips only; any other count is the gate's
    failure, named with the count."""
    parsed = core.parse_p3_engine_output(_p3_output_with_g1(_P3_G1_PASS_LINE), "", 0)
    assert parsed["gates"]["G1"] == {"passed": True, "flips": None, "line": _P3_G1_PASS_LINE}
    for zero in (
        "G1 RESULT: 0 total flip(s) vs the f32 session across all seeds (reporting gate;"
        " G0 16/16 remains HARD)",
        "G1 RESULT: 0 total flips vs the f32 session across all seeds",
    ):
        gate = core.parse_p3_engine_output(_p3_output_with_g1(zero), "", 0)["gates"]["G1"]
        assert gate["passed"] is True and gate["flips"] == 0, zero
    three = (
        "G1 RESULT: 3 total flip(s) vs the f32 session across all seeds (reporting gate;"
        " G0 16/16 remains HARD)"
    )
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output(_p3_output_with_g1(three), "", 0)
    assert exc.value.code == "engine_gate_failed"
    assert (
        exc.value.message.startswith("G1 reported 3 total flip(s)") and three in exc.value.message
    )
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output(
            _p3_output_with_g1("G1 RESULT: FAIL — graph-p3 disagrees with per-dispatch-p3"), "", 1
        )
    assert exc.value.code == "engine_gate_failed" and "disagrees" in exc.value.message
    # a count that is not a number is not a verdict at all: the gate line is then missing
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output(_p3_output_with_g1("G1 RESULT: some total flip(s)"), "", 0)
    assert exc.value.code == "engine_no_timing" and "G1 RESULT" in exc.value.message


def test_p3_failure_literals_are_read_from_stdout_and_stderr_only_for_the_loader() -> None:
    """The driver's verdicts are `print`s (stdout). A stderr line that quotes one — a warning,
    a loader's message echoing a gate name — is not the driver's verdict: with a clean stdout and
    exit 0 the launch parses; with a non-zero exit it is `engine_run_failed` carrying the
    runtime's exception line, else the last stderr line. Only the runtime's no-driver line
    (`Failed to open library "libnvidia-ml.so.1"`, the GPU-less smoke's) and the no-accelerator
    sentence are codes on stderr."""
    clean = P3_DRIVER_OUTPUT.format(runs=3)
    noise = "warning: G1 RESULT: FAIL text seen in a log line\nORACLE MISMATCH quoted here\n"
    parsed = core.parse_p3_engine_output(clean, noise, 0)
    assert {k: v["passed"] for k, v in parsed["gates"].items()} == {
        "G0": True,
        "G1": True,
        "G2": True,
    }
    assert parsed["cells"]["64"]["graph_p3"]["decode_tok_per_s"] == 193.93
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output(clean, noise + "last line of stderr\n", 1)
    assert exc.value.code == "engine_run_failed"
    assert exc.value.message == "the engine exited with status 1: last line of stderr"
    # the real no-driver stderr, with the runtime's hint lines after the exception line
    no_driver = (
        "Unhandled exception caught during execution: At max/mojo/max/gpu/host/"
        'device_context.mojo:3825:17: Failed to open library "libnvidia-ml.so.1"\n'
        "To get more accurate error information, set MODULAR_DEBUG=device-sync-mode.\n"
        "To get more accurate error information, set MODULAR_DEBUG=device-sync-mode.\n"
    )
    for text, code, needle in (
        (no_driver, "engine_no_gpu", "libnvidia-ml.so.1"),
        (
            'Unhandled exception caught during execution: Failed to open library "libcuda.so.1"\n',
            "engine_no_gpu",
            "libcuda.so.1",
        ),
        ("qwen3_p3_graph_cuda: no accelerator on this host\n", "engine_no_gpu", "no accelerator"),
        (
            "Unhandled exception caught during execution: Failed to open library "
            '"libKGENCompilerRTShared.so"\n'
            "To get more accurate error information, set MODULAR_DEBUG=device-sync-mode.\n",
            "engine_run_failed",
            "libKGENCompilerRTShared.so",
        ),
        ('Failed to open library "libcudart.so.12"\n', "engine_run_failed", "libcudart.so.12"),
    ):
        with pytest.raises(core.ProbeError) as exc:
            core.parse_p3_engine_output(
                "qwen3_p3_graph_cuda: checkpoint = x | n_prompt = 256", text, 1
            )
        assert exc.value.code == code and needle in exc.value.message, text
    # stdout's own verdicts are still read from stdout, whatever stderr says
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output("G2 RESULT: FAIL — full table:", "unrelated warning", 1)
    assert exc.value.code == "engine_gate_failed"
    with pytest.raises(core.ProbeError) as exc:
        core.parse_p3_engine_output("", "", 1)
    assert exc.value.message == "the engine exited with status 1: no output"


def _fake_prepare_model_checkpoint(calls: list[dict]) -> ModuleType:
    """`algenta.inference.prepare_model_checkpoint` as the convert stage calls it, writing the
    manifest and an empty blob; algenta itself is never imported here."""
    module = types.ModuleType("algenta.inference")

    def prepare_model_checkpoint(snapshot, ids, *, out_dir, weights_dtype, backend):  # noqa: ANN001
        calls.append({"ids": list(ids), "out_dir": Path(out_dir)})
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / "manifest.json").write_text(
            json.dumps(
                {"input_ids": list(ids), "config": {"n_tokens": len(ids)}, "tensors": ["a", "b"]}
            ),
            encoding="utf-8",
        )
        (Path(out_dir) / "weights.blob").write_bytes(b"\0" * 8)
        return Path(out_dir)

    module.prepare_model_checkpoint = prepare_model_checkpoint  # type: ignore[attr-defined]
    return module


def test_stage_convert_replaces_a_stale_checkpoint_from_the_other_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A persistent work dir holding a checkpoint converted with the other prompt fixture (or an
    unreadable manifest) is removed and converted again — logged, recorded, not fatal. The
    matching checkpoint is reused. `conversion_prompt_mismatch` remains only when the stale
    directory cannot be removed."""
    work = tmp_path / "work"
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    monkeypatch.setenv("PROBE_WORK_DIR", str(work))
    monkeypatch.setenv(cfg.PROMPT_FIXTURE_ENV, "campaign")
    monkeypatch.setattr(probe, "model_snapshot", lambda: snapshot)
    monkeypatch.setattr(probe, "safe_decode", lambda snapshot, ids: None)
    monkeypatch.setattr(probe, "disk_free_bytes", lambda path: 64 * 1024**3)
    monkeypatch.setattr(probe, "max_rss_mib", lambda: 1.0)
    calls: list[dict] = []
    if importlib.util.find_spec("algenta") is None:
        package = types.ModuleType("algenta")
        package.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "algenta", package)
    monkeypatch.setitem(sys.modules, "algenta.inference", _fake_prepare_model_checkpoint(calls))
    out_dir = probe.converted_dir()
    battery, campaign = core.battery_prompt_ids(), core.campaign_prompt_ids()
    out_dir.mkdir(parents=True)
    (out_dir / "manifest.json").write_text(
        json.dumps({"input_ids": battery, "config": {}}), encoding="utf-8"
    )
    (out_dir / "weights.blob").write_bytes(b"stale")
    (out_dir / "leftover.tmp").write_bytes(b"x")
    with caplog.at_level("WARNING", logger="gpu_probe"):
        facts = probe.stage_convert()
    assert facts["reused"] is False and facts["manifest_prompt_ids_match"] is True
    assert facts["stale_checkpoint_removed"] == {
        "path": str(out_dir),
        "baked_fixture": "battery",
        "baked_n_prompt": 256,
        "reason": "the manifest's prompt is not the campaign fixture (256 ids)",
    }
    assert [c["ids"] for c in calls] == [campaign] and calls[0]["out_dir"] == out_dir
    assert (
        probe.converted_prompt_ids(out_dir) == campaign and not (out_dir / "leftover.tmp").exists()
    )
    assert facts["blob_bytes"] == 8 and facts["n_tensors"] == 2 and facts["wall_s"] is not None
    assert any(
        "removing" in rec.message and "battery" in rec.message and "campaign" in rec.message
        for rec in caplog.records
    )
    # the matching checkpoint is reused, nothing removed
    facts = probe.stage_convert()
    assert facts["reused"] is True and facts["stale_checkpoint_removed"] is None
    assert len(calls) == 1
    # an unreadable manifest is stale too
    (out_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    facts = probe.stage_convert()
    assert facts["reused"] is False and len(calls) == 2
    assert facts["stale_checkpoint_removed"]["baked_fixture"] is None
    assert (
        facts["stale_checkpoint_removed"]["reason"] == "the manifest carries no readable input_ids"
    )
    # a prompt of neither fixture names no fixture; the two fixtures are told apart at their
    # converted length (they share the first eight ids)
    assert probe.prompt_fixture_of([1, 2, 3]) is None and probe.prompt_fixture_of(None) is None
    assert probe.prompt_fixture_of(campaign) == "campaign"
    assert probe.prompt_fixture_of(battery) == "battery"
    # the one unrecoverable case: the stale directory will not go
    (out_dir / "manifest.json").write_text(json.dumps({"input_ids": battery}), encoding="utf-8")

    def refuse(path, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(probe.shutil, "rmtree", refuse)
    with pytest.raises(core.ProbeError) as exc:
        probe.stage_convert()
    assert exc.value.code == "conversion_prompt_mismatch"
    assert "could not be removed" in exc.value.message and "PermissionError" in exc.value.message
    assert exc.value.details["baked_fixture"] == "battery" and len(calls) == 2


def test_p3_engine_runs_end_to_end_against_a_fake_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The subprocess protocol as lane A drives the packed-int8 graph driver: argv
    `<checkpoint> --runs 3`, the engine's directory first on LD_LIBRARY_PATH, the prompt read
    from the checkpoint manifest, one launch parsed into the cells, and the fixture gate before
    it. The driver here is a script that prints the real lines; no figure is a measurement."""
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    engine = engine_dir / cfg.P3_ENGINE_NAME
    engine.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "ckpt, args = sys.argv[1], sys.argv[2:]\n"
        "assert args[0] == '--runs', args\n"
        "runs = int(args[1])\n"
        "assert os.environ['LD_LIBRARY_PATH'].split(':')[0] == os.path.dirname(os.path.abspath(sys.argv[0]))\n"
        "ids = json.load(open(os.path.join(ckpt, 'manifest.json')))['input_ids']\n"
        "if os.environ.get('FAKE_P3') == 'oracle':\n"
        "    print('G0 — packed3 graph arm, 16 greedy tokens on the race fixture')\n"
        "    print('  ORACLE MISMATCH at generated token 0 (prefill): got 6722 want 374')\n"
        "    print('G0 RESULT: FAIL — 1 mismatched tokens'); sys.exit(1)\n"
        "text = open(os.environ['FAKE_P3_OUTPUT']).read().format(runs=runs)\n"
        "print(text.replace('n_prompt = 256', 'n_prompt = %d' % len(ids)), end='')\n",
        encoding="utf-8",
    )
    engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
    output_file = tmp_path / "driver_output.txt"
    output_file.write_text(P3_DRIVER_OUTPUT, encoding="utf-8")
    checkpoint = tmp_path / "ckpt"
    checkpoint.mkdir()
    (checkpoint / "manifest.json").write_text(
        json.dumps({"input_ids": core.campaign_prompt_ids(), "config": {"n_tokens": 256}}),
        encoding="utf-8",
    )
    (checkpoint / "weights.blob").write_bytes(b"")
    env = probe.engine_env(engine.parent)
    env["PATH"] = str(Path(sys.executable).parent) + ":" + env.get("PATH", "")
    env["FAKE_P3_OUTPUT"] = str(output_file)
    launch = probe.run_p3_engine_once(engine, checkpoint, env)
    assert launch["argv"] == [str(engine), str(checkpoint), "--runs", str(cfg.RUNS)]
    assert launch["n_prompt"] == 256 and launch["runs"] == cfg.RUNS
    assert launch["cells"]["64"]["graph_p3"]["decode_tok_per_s"] == 193.93
    assert launch["wall_s"] >= 0 and "vram_peak_bytes" in launch and "vram_samples" in launch
    block = probe.p3_engine_block(
        launch, snapshot=Path("/nonexistent"), ids=core.campaign_prompt_ids(), fixture="campaign"
    )
    assert block["protocol"] == cfg.P3_ENGINE_NAME and block["prompt_fixture"] == "campaign"
    assert block["tokens"] == core.campaign_oracle_tokens() and block["tokens_verified"] == 16
    assert (
        block["decode_tok_per_s"] == 193.93
        and block["runs"]["256"]["summary"]["decode_tok_per_s"] == 188.81
    )
    assert block["prefill_tok_per_s"] is None and block["ttft_ms"] is None
    assert block["load_ms"] == 21873.4 and block["graph_nodes"] == 200
    assert block["gates"]["G0"]["passed"] and block["gen_lengths"] == [64, 256]
    assert block["long_gen_skipped"] is None and block["decoded"] is None
    # a prompt the driver did not prefill in full is refused
    (checkpoint / "manifest.json").write_text(
        json.dumps({"input_ids": core.campaign_prompt_ids(255)}), encoding="utf-8"
    )
    with pytest.raises(core.ProbeError) as exc:
        probe.run_p3_engine_once(engine, checkpoint, env)
    assert exc.value.code == "engine_prompt_mismatch"
    # the driver's oracle failure is the lane's code, with its line
    (checkpoint / "manifest.json").write_text(
        json.dumps({"input_ids": core.campaign_prompt_ids()}), encoding="utf-8"
    )
    env["FAKE_P3"] = "oracle"
    with pytest.raises(core.ProbeError) as exc:
        probe.run_p3_engine_once(engine, checkpoint, env)
    assert exc.value.code == "engine_oracle_mismatch" and "want 374" in exc.value.message
    # the fixture gate: the converted prompt must be the active fixture, and campaign for
    # this driver
    monkeypatch.delenv(cfg.PROMPT_FIXTURE_ENV, raising=False)
    monkeypatch.setenv(cfg.ENGINE_ENV, str(engine))
    gate = probe.checkpoint_fixture_gate(checkpoint, cfg.P3_ENGINE_NAME)
    assert gate == {
        "active_fixture": "campaign",
        "manifest_prompt_ids_match": True,
        "n_prompt_baked": 256,
    }
    monkeypatch.setenv(cfg.PROMPT_FIXTURE_ENV, "battery")
    with pytest.raises(core.ProbeError) as exc:
        probe.checkpoint_fixture_gate(checkpoint, cfg.P3_ENGINE_NAME)
    assert exc.value.code == "engine_prompt_fixture_mismatch"
    assert "not the battery fixture" in exc.value.message
    (checkpoint / "manifest.json").write_text(
        json.dumps({"input_ids": core.battery_prompt_ids()}), encoding="utf-8"
    )
    with pytest.raises(core.ProbeError) as exc:
        probe.checkpoint_fixture_gate(checkpoint, cfg.P3_ENGINE_NAME)
    assert exc.value.code == "engine_prompt_fixture_mismatch"
    assert "oracle is bound to the campaign fixture" in exc.value.message
    assert probe.checkpoint_fixture_gate(checkpoint, cfg.ENGINE_NAME)["active_fixture"] == "battery"


def test_engine_facts_read_the_p3_manifest_and_refuse_a_broken_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = tmp_path / cfg.P3_ENGINE_NAME
    engine.write_bytes(b"fixture")
    sha = probe.sha256_of(engine)
    for name in P3_CLOSURE:
        (tmp_path / name).write_bytes(b"")
    (tmp_path / cfg.ENGINE_MANIFEST).write_text(json.dumps(_p3_manifest(sha)), encoding="utf-8")
    resolution = types.SimpleNamespace(
        path=engine, source="$ALGENTA_CUDA_ENGINE", searched=("$ALGENTA_CUDA_ENGINE",)
    )
    fake = types.ModuleType("algenta.serve.engine")
    fake.resolve_engine = lambda backend: resolution  # type: ignore[attr-defined]
    if importlib.util.find_spec("algenta") is None:
        package = types.ModuleType("algenta")
        package.__path__ = []  # type: ignore[attr-defined]
        serve = types.ModuleType("algenta.serve")
        serve.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "algenta", package)
        monkeypatch.setitem(sys.modules, "algenta.serve", serve)
    monkeypatch.setitem(sys.modules, "algenta.serve.engine", fake)
    monkeypatch.setattr(probe, "package_versions", lambda names: {cfg.ENGINE_WHEEL: "1.0.7"})
    facts = probe.engine_facts()
    assert facts["protocol"] == cfg.P3_ENGINE_NAME and facts["name"] == cfg.P3_ENGINE_NAME
    assert facts["cuda_target"] == "sm_89" and facts["sha256_matches"] is True
    assert facts["host_shared_libraries"] == [] and facts["libcudart_beside"] is False
    assert facts["bundled_shared_libraries"] == list(P3_CLOSURE) and facts["bundled_beside"]
    assert facts["source_commit"].startswith("6029d6af0") and facts["built_utc"].startswith("2026")
    assert facts["mojo_version"] == "Mojo 1.0.0 (ed45d567)" and facts["session"]
    assert core.engine_target_gate(facts["cuda_target"], (8, 9))["ok"] is True
    with pytest.raises(core.ProbeError):
        core.engine_target_gate(facts["cuda_target"], (7, 5))
    (tmp_path / "libMSupportGlobals.so").unlink()
    with pytest.raises(core.ProbeError) as exc:
        probe.engine_facts()
    assert (
        exc.value.code == "engine_closure_incomplete"
        and "libMSupportGlobals.so" in exc.value.message
    )
    other = tmp_path / "other_engine"
    other.write_bytes(b"x")
    resolution.path = other
    with pytest.raises(core.ProbeError) as exc:
        probe.engine_facts()
    assert exc.value.code == "engine_protocol_unknown"


def test_p3_lane_view_ratio_record_and_page(
    tmp_path: Path, artifact: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete run with the packed-int8 graph driver as lane A: every lane on the campaign
    fixture, the reference decoding the driver's oracle continuation. The engine lane carries
    the driver's figures and gates, its identity is the 16 oracle-checked tokens against the
    reference's first 16, the ratio compares the same 16, the decision is ok, and the page names
    the engine's build and the fixture."""
    oracle64 = core.campaign_oracle_tokens(64)
    data = _run12_stage_data(artifact)
    data["engine"] = _fixture_p3_engine()
    data["llama"] = _fixture_llama(oracle64)
    data["decode"] = {
        **data["decode"],
        "tokens": oracle64,
        "prompt_ids": core.campaign_prompt_ids(),
    }
    data["baseline"] = _fixture_baseline(oracle64)
    data["reference"] = {
        **data["reference"],
        "tokens": oracle64,
        "top2_margins": [4.0] * 64,
        "decoded": " is Paris. The capital of France is Paris.",
    }
    data["convert"] = {
        **data["convert"],
        "prompt_fixture": "campaign",
        "prompt_ids": core.campaign_prompt_ids(),
        "n_prompt": 256,
    }
    monkeypatch.delenv(cfg.PROMPT_FIXTURE_ENV, raising=False)
    monkeypatch.setenv(cfg.ENGINE_ENV, "/home/user/engine/qwen3_p3_graph_cuda")
    state = app.ProbeState(work=tmp_path, versions={"python": "3.14.7"}, space={}, build={})
    app.run_probe(state, _fake_runner(data))
    body = state.health()
    assert body["status"] == core.OK and body["pins"]["prompt_fixture"] == "campaign"
    view = body["race"]
    engine, llama = view["race"]
    assert engine["status"] == core.OK_LANE and engine["protocol"] == cfg.P3_ENGINE_NAME
    assert engine["precision"] == core.P3_LANE_PRECISION
    assert engine["decode_tok_per_s"] == 193.93 and engine["decode_tok_per_s_long"] == 188.81
    assert engine["prefill_tok_per_s"] is None and engine["ttft_ms"] is None
    assert engine["load_s"] == 21.87 and engine["vram_bytes"] == 1_900_000_000
    assert engine["tokens"] == core.campaign_oracle_tokens() and engine["tokens_verified"] == 16
    assert engine["gates"] == {"G0": True, "G1": True, "G2": True}
    assert engine["identity"]["verdict"] == "16/16" and engine["identity"]["oracle"] == "16/16"
    assert engine["identity"]["full_match"] is True
    assert engine["identity"]["reference_tokens_total"] == 64
    assert engine["n_runs"] == 3 and engine["iqr_note"] == "rel IQR 0.69 % (PASS at the frozen 5 %)"
    assert engine["build"]["cuda_target"] == "sm_89" and engine["build"]["kernel_variant"]
    assert "built 2026-09-24 from 6029d6af0085" in engine["session_note"]
    assert engine["stack"].startswith("qwen3_p3_graph_cuda af92012a45c5 · sm_89 · mojo Mojo 1.0.0")
    assert view["ratio"] == {
        "same_tokens": True,
        "tokens_compared": 16,
        "decode_gen64": round(193.93 / 171.0, 2),
        "decode_gen256": round(188.81 / llama["decode_tok_per_s_long"], 2),
        "prefill": None,
    }
    record = json.loads(state.run_json.read_text(encoding="utf-8"))
    assert record["decision"] == "ok"
    race = record["evidence"]["GPU-SPACE-RACE-001"]
    assert race["prompt_fixture"] == "campaign"
    assert race["engine"]["protocol"] == cfg.P3_ENGINE_NAME
    assert race["engine"]["tokens_verified"] == 16 and race["engine"]["identity"] == "16/16"
    assert race["engine"]["prefill_tok_per_s"] is None and race["ratio_decode_gen64"] == 1.13
    page = app.render_page(body)
    _assert_clean_copy(page)
    text = _page_text(page)
    assert "Algenta engine · packed-int8 resident weights, captured-graph decode" in text
    assert "Decode tokens per second (gen=64) 193.9 tok/s 171.0 tok/s" in text
    assert "Decode tokens per second (gen=256) 188.8 tok/s" in text
    assert "built 2026-09-24 from 6029d6af0085" in text
    assert "16 tokens checked by the driver's oracle gate, the reference's first" in text
    assert "Identity vs the CPU reference 16/16, oracle 16/16 64/64, oracle 16/16" in text
    assert "Runs 3 timed, 1 warm-up excluded; rel IQR 0.69 % (PASS at the frozen 5 %)" in text
    assert "both lanes decoded the same first 16 tokens, the ones the Algenta driver prints" in text
    assert "Prompt fixture campaign" in text and "Gates G0 passed, G1 passed, G2 passed" in text
    assert "Captured nodes per token 200 (vs 171 per-dispatch enqueues)" in text
    assert "One-time load 21.87 s" in text and "Protocol qwen3_p3_graph_cuda" in text
    assert "Kernel set v4 (int32 unpack + fused gate/up swiglu)" in text
    assert app.P3_LANE_NOTE.format(runs=3)[:60] in text
    assert "Run complete. Algenta engine 193.9 tok/s (identity 16/16)" in text
    for copy in (app.P3_LANE_NOTE, core.P3_SESSION_NOTE, core.P3_TTFT_NOTE, core.P3_LOAD_LABEL):
        _assert_clean_copy(copy)
    # the wheel engine's page is unchanged by the new fields
    plain = _run12_stage_data(artifact)
    monkeypatch.delenv(cfg.ENGINE_ENV)
    state2 = app.ProbeState(work=tmp_path / "b", versions={}, space={}, build={})
    app.run_probe(state2, _fake_runner(plain))
    text2 = _page_text(app.render_page(state2.health()))
    assert "Algenta engine · f32 resident weights, per-token dispatch" in text2
    assert "Prompt fixture battery" in text2 and "Gates" not in text2.split("Argv")[1][:40]


# --- Codna findings on #1173 (app.py) ---------------------------------------------------------


def test_published_rows_omit_the_ratio_parenthetical_when_a_ratio_is_missing() -> None:
    """`_ratio` answers None for a non-positive operand and an older replayed record can carry
    None: the throughput row then prints both rates without the ratio, instead of raising."""
    published = core.published_facts()
    rows = app._published_rows(published)
    assert len(rows) == 2 and "(ratio 1.12 / 1.07)" in rows[1]
    for missing in ("ratio_gen64", "ratio_gen256"):
        broken = json.loads(json.dumps(published))
        broken["throughput"][missing] = None
        rows = app._published_rows(broken)
        assert len(rows) == 2 and "(ratio" not in rows[1] and "171.3 tok/s at gen=64" in rows[1]
    assert app._published_rows({}) == []


def test_race_section_tolerates_a_race_block_with_other_than_two_lanes(
    tmp_path: Path, artifact: dict
) -> None:
    """A stored `race` block is data: zero, one or three lanes render as columns and never
    raise on the unpack that assumed exactly two."""
    state = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    app.run_probe(state, _fake_runner(_run12_stage_data(artifact)))
    body = state.health()
    engine, llama = body["race"]["race"]
    for lanes in ([], [engine], [engine, llama, dict(llama, id="extra", title="third")]):
        body["race"]["race"] = lanes
        text = _page_text(app.race_section(body))
        assert "The published race, live on this Tesla T4" in text
        assert text.count("190.0 tok/s") == (1 if lanes else 0)
        # the ratio is the view's own figure; the titles fall back when a lane is missing
        assert "Measured ratio, Algenta engine over llama.cpp" in text
    body["race"]["race"] = [engine, llama, dict(llama, id="extra", title="third")]
    assert _page_text(app.race_section(body)).count("171.0 tok/s") == 2
    body["race"]["race"] = []
    body["race"]["ratio"] = {"same_tokens": None, "decode_gen64": None}
    assert "Measured ratio" not in _page_text(app.race_section(body))


def test_lanes_table_extra_rows_default_is_an_immutable_sequence() -> None:
    import inspect

    parameter = inspect.signature(app._lanes_table).parameters["extra_rows"]
    assert parameter.default == () and isinstance(parameter.default, tuple)
    assert "Sequence" in str(parameter.annotation)
    assert app._lanes_table([], [], []).startswith('<div class="lanes-wrap">')


def test_dockerfile_gitignore_and_deploy_notes_ship_the_sm89_engine() -> None:
    dockerfile = (PROBE_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "ln -sfn /app/engine /home/user/engine" in dockerfile
    assert "COPY --chown=user:user . ." in dockerfile
    assert dockerfile.index("COPY --chown=user:user . .") < dockerfile.index("ln -sfn /app/engine")
    assert dockerfile.index("ln -sfn /app/engine") < dockerfile.index("USER user")
    gitignore = (PROBE_DIR / ".gitignore").read_text(encoding="utf-8")
    assert "engine/" in [line.strip() for line in gitignore.splitlines()]
    deploy_md = (PROBE_DIR / "DEPLOY.md").read_text(encoding="utf-8")
    for needle in (
        "ALGENTA_CUDA_ENGINE",
        "ARG ALGENTA_CUDA_ENGINE",
        "engine_selected_missing",
        "/home/user/engine/qwen3_p3_graph_cuda",
        "add_space_variable",
        "cuda-engine-sm89/out",
        "elf_check.py",
        "PROBE_PROMPT_FIXTURE",
        "engine_prompt_fixture_mismatch",
    ):
        assert needle in deploy_md, needle
    assert '"*.so"' not in deploy_md.split("IGNORE_WITH_ENGINE")[1].split("]")[0]
    readme = (PROBE_DIR / "README.md").read_text(encoding="utf-8")
    assert "qwen3_p3_graph_cuda" in readme and "sm_89" in readme
    doc = (REPO / "docs/spaces/GPU-PROBE.md").read_text(encoding="utf-8")
    for needle in (
        "qwen3_p3_graph_cuda",
        "PROBE_PROMPT_FIXTURE",
        "engine_prompt_fixture_mismatch",
        "engine_oracle_mismatch",
        "engine_protocol_unknown",
        "campaign",
        "sm_89",
        "libnvidia-ml.so.1",
    ):
        assert needle in doc, needle
    assert copy_lint.lint_space(PROBE_DIR) == []


def test_dockerfile_declares_the_engine_build_argument_before_the_bake() -> None:
    """Hugging Face hands a Space variable to the image build only as a build argument: the
    Dockerfile declares `ARG ALGENTA_CUDA_ENGINE` inside the runtime stage, after the
    `/home/user/engine` symlink exists and after `USER user`, before the bake that inspects it,
    and keeps it as ENV so a container without the variable injected resolves the same binary."""
    text = (PROBE_DIR / "Dockerfile").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    joined = "\n".join(lines)
    arg = f"ARG {cfg.ENGINE_ENV}\n"
    env = f"ENV {cfg.ENGINE_ENV}=${{{cfg.ENGINE_ENV}}}\n"
    assert joined.count(f"ARG {cfg.ENGINE_ENV}") == 1
    assert arg + env in joined + "\n", "the ENV follows the ARG, empty when the argument is unset"
    last_from = joined.rindex("\nFROM ")
    symlink = joined.index("ln -sfn /app/engine /home/user/engine")
    user = joined.index("USER user")
    declared = joined.index(arg)
    bake = joined.index("python fetch_assets.py --bake")
    assert last_from < symlink < user < declared < bake
    assert joined.index("HF_HUB_OFFLINE=1 python fetch_assets.py --verify") > declared
    doc = (REPO / "docs/spaces/GPU-PROBE.md").read_text(encoding="utf-8")
    for needle in (
        f"ARG {cfg.ENGINE_ENV}",
        "llama_backend_load_failed",
        "llama_cuda_backend_missing",
        "llama_cuda_backend_unloadable",
        "libggml-cuda.so",
        "ggml_backend_load_all_from_path",
        "--verbose",
    ):
        assert needle in doc, needle


def test_p3_stderr_refusals_are_read_only_when_the_driver_failed() -> None:
    """A clean exit never reads stderr: a wrapper's debug line quoting the no-accelerator
    sentence or the no-driver line must not turn a passed run into `engine_no_gpu`
    (Codna on #1173)."""
    stdout = _p3_output_with_g1("G1 RESULT: PASS — 3 seeds x 128 steps token-for-token identical")
    noisy_stderr = (
        "wrapper: no accelerator sentence quoted in a debug line\n"
        'wrapper: Failed to open library "libnvidia-ml.so.1" quoted in a debug line\n'
    )
    parsed = core.parse_p3_engine_output(stdout, noisy_stderr, 0)
    assert all(g["passed"] for g in parsed["gates"].values())
    with pytest.raises(core.ProbeError) as excinfo:
        core.parse_p3_engine_output(stdout, noisy_stderr, 1)
    assert excinfo.value.code == "engine_no_gpu"


# --- lane B: the prebuilt opponent, its pins and its gate ---------------------------------------


def test_lane_b_pins_name_the_official_image_by_digest() -> None:
    """The published cell's build (b10210, from source, sm_89 only) stays recorded beside the
    image lane B runs: the versioned server-cuda tag closest to and not below it, by digest."""
    assert cfg.LLAMA_IMAGE == "ghcr.io/ggml-org/llama.cpp"
    assert cfg.LLAMA_IMAGE_TAG == f"server-cuda-b{cfg.LLAMA_CPP_BUILD}"
    assert cfg.LLAMA_CPP_TAG == f"b{cfg.LLAMA_CPP_BUILD}"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", cfg.LLAMA_IMAGE_DIGEST)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", cfg.LLAMA_IMAGE_AMD64_DIGEST)
    assert cfg.LLAMA_IMAGE_AMD64_DIGEST != cfg.LLAMA_IMAGE_DIGEST
    assert cfg.LLAMA_IMAGE_REF == f"{cfg.LLAMA_IMAGE}@{cfg.LLAMA_IMAGE_DIGEST}"
    assert cfg.LLAMA_IMAGE_KIND == "official ggml-org CUDA image, by digest"
    assert core.is_sha(cfg.LLAMA_CPP_COMMIT) and core.is_sha(cfg.PUBLISHED_LLAMA_CPP_COMMIT)
    assert cfg.LLAMA_CPP_COMMIT != cfg.PUBLISHED_LLAMA_CPP_COMMIT
    assert cfg.LLAMA_CPP_BUILD >= cfg.PUBLISHED_LLAMA_CPP_BUILD == 10210
    assert cfg.PUBLISHED_LLAMA_CPP_TAG == "b10210"
    assert cfg.LLAMA_CPP_URL.endswith(cfg.LLAMA_CPP_COMMIT)
    archs = cfg.LLAMA_CUDA_ARCHITECTURES.split(";")
    assert "89-real" in archs, "the L4 runs a cubin, as the published source build did"
    assert "75-virtual" in archs, "the T4 fallback runs from PTX"
    assert cfg.PUBLISHED_LLAMA_CUDA_ARCHITECTURES == "89" and "89" not in archs
    assert cfg.LLAMA_CUDA_RUNTIME == "12.8.1"
    assert cfg.LLAMA_SERVER == f"{cfg.LLAMA_BIN_DIR}/llama-server"
    assert cfg.LLAMA_BIN_DIR.startswith(cfg.LLAMA_DIR + "/")
    for path in (cfg.LLAMA_COMMIT_FILE, cfg.LLAMA_BUILD_FILE, cfg.LLAMA_IMAGE_DIGEST_FILE):
        assert path.startswith(cfg.LLAMA_DIR + "/")
    assert (cfg.LLAMA_LIBRARY_PATH_ENV, cfg.LLAMA_BACKEND_PATH_ENV) == (
        "LD_LIBRARY_PATH",
        "GGML_BACKEND_PATH",
    )
    assert cfg.LLAMA_CUDA_BACKEND == f"{cfg.LLAMA_BIN_DIR}/libggml-cuda.so"
    assert cfg.LLAMA_CUDA_BACKEND_NAME == "CUDA" and cfg.LLAMA_DRIVER_LIBRARY == "libcuda.so.1"
    assert cfg.LLAMA_CONVERT_EXPORTED_MARK == "Model successfully exported to"


RUN16_LOADER_LINE = (
    "0.00.028.775 E load_backend: failed to load /opt/llama/bin: /opt/llama/bin: "
    "cannot read file data: Is a directory"
)


def test_llama_version_gate_accepts_the_pin_and_fails_closed() -> None:
    ok = core.parse_llama_version(
        f"version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})\nbuilt with GNU 14.2.0\n"
    )
    core.verify_llama_version(ok)
    assert ok["loader_errors"] == [] and ok["backends_loaded"] == {}
    # run 16: the pinned version behind a registry refusal (GGML_BACKEND_PATH was a directory)
    run16 = core.parse_llama_version(
        f"{RUN16_LOADER_LINE}\nversion: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})\n"
        "built with GNU 14.2.0 for Linux x86_64\n"
    )
    assert run16["build_number"] == cfg.LLAMA_CPP_BUILD
    assert run16["loader_errors"] == [RUN16_LOADER_LINE]
    with pytest.raises(core.ProbeError) as loader_exc:
        core.verify_llama_version(run16)
    assert loader_exc.value.code == "llama_backend_load_failed"
    assert "Is a directory" in loader_exc.value.message
    assert loader_exc.value.details["loader_errors"] == [RUN16_LOADER_LINE]
    loaded = core.parse_llama_version(
        "0.00.030.747 I load_backend: loaded CUDA backend from /opt/llama/bin/libggml-cuda.so\n"
        f"version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})\n"
    )
    assert loaded["backends_loaded"] == {"CUDA": "/opt/llama/bin/libggml-cuda.so"}
    core.verify_llama_version(loaded)
    for refusal in (
        "load_backend: failed to initialize backend from /x/libggml-cuda.so: "
        "ggml_backend_init returned NULL",
        "load_backend: failed to find ggml_backend_init in /x/libggml-cuda.so",
        "load_backend: backend /x/libggml-cuda.so is not supported on this system",
        "ggml_backend_load_best: failed to load /x/libggml-cpu-zen4.so: some dlerror",
    ):
        assert core.llama_loader_lines(refusal)["loader_errors"] == [refusal], refusal
    core.verify_llama_version(
        core.parse_llama_version("version: 0.5.0-dev (build 11151, commit bd4f514db)"),
        build=11151,
        commit="bd4f514db14d87fded667787a7a963bfbaa98e89",
    )
    cases = {
        "the published build": {
            "build_number": cfg.PUBLISHED_LLAMA_CPP_BUILD,
            "commit": cfg.LLAMA_CPP_COMMIT[:9],
        },
        "the published commit": {
            "build_number": cfg.LLAMA_CPP_BUILD,
            "commit": cfg.PUBLISHED_LLAMA_CPP_COMMIT[:9],
        },
        "a commit too short to pin": {
            "build_number": cfg.LLAMA_CPP_BUILD,
            "commit": cfg.LLAMA_CPP_COMMIT[:6],
        },
        "the moving tag": core.parse_llama_version(
            "version: 0.5.0-dev (build 11151, commit bd4f514db)"
        ),
        "no version line": core.parse_llama_version("built with GNU 14.2.0 for Linux x86_64\n"),
        "nothing": {},
    }
    for label, facts in cases.items():
        with pytest.raises(core.ProbeError) as exc:
            core.verify_llama_version(facts)
        assert exc.value.code == "llama_version_mismatch", label
        assert str(cfg.LLAMA_CPP_BUILD) in str(exc.value), label


def test_llama_launch_env_points_the_loader_at_the_prebuilt_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The image's files carry RUNPATH `/app/build/bin:` (the build tree, then the working
    directory): every lane-B launch leads LD_LIBRARY_PATH with their directory, keeping the
    inherited value, and never sets GGML_BACKEND_PATH — ggml's registry finds the backends
    beside the launcher and that variable names one extra library, loaded out loud (run 16
    named the directory); an inherited value is dropped, the bake's probe sets the one file."""
    monkeypatch.setenv(cfg.LLAMA_LIBRARY_PATH_ENV, "/usr/local/cuda/lib64")
    monkeypatch.setenv(cfg.LLAMA_BACKEND_PATH_ENV, cfg.LLAMA_BIN_DIR)
    env = probe.llama_env()
    assert env[cfg.LLAMA_LIBRARY_PATH_ENV] == f"{cfg.LLAMA_BIN_DIR}:/usr/local/cuda/lib64"
    assert cfg.LLAMA_BACKEND_PATH_ENV not in env
    assert env["PATH"] == probe.os.environ["PATH"]
    assert probe.llama_env(cfg.LLAMA_CUDA_BACKEND)[cfg.LLAMA_BACKEND_PATH_ENV] == (
        cfg.LLAMA_CUDA_BACKEND
    )
    monkeypatch.delenv(cfg.LLAMA_LIBRARY_PATH_ENV)
    monkeypatch.delenv(cfg.LLAMA_BACKEND_PATH_ENV)
    assert probe.llama_env()[cfg.LLAMA_LIBRARY_PATH_ENV] == cfg.LLAMA_BIN_DIR
    assert probe.llama_launch_env() == {cfg.LLAMA_LIBRARY_PATH_ENV: cfg.LLAMA_BIN_DIR}
    facts = probe.llama_image_facts()
    assert facts["ref"] == cfg.LLAMA_IMAGE_REF and facts["tag"] == cfg.LLAMA_IMAGE_TAG
    assert facts["digest"] == cfg.LLAMA_IMAGE_DIGEST and facts["kind"] == cfg.LLAMA_IMAGE_KIND


def test_bake_checks_the_prebuilt_server_against_the_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fetch_assets.llama_server_version`, against a fake llama-server: the pinned version with
    the pin files in place passes and the launch variables reach the binary; a pin file that
    disagrees, another build (the moving tag's newer shape) or no version line fail closed with
    llama_version_mismatch; an absent binary is llama_build_missing."""
    server = tmp_path / "bin" / "llama-server"
    server.parent.mkdir()

    def write_server(line: str) -> None:
        server.write_text(
            "#!/bin/sh\n"
            f'echo "{line}" >&2\n'
            'echo "built with GNU 14.2.0 for Linux x86_64" >&2\n'
            'echo "LD=$LD_LIBRARY_PATH GGML=$GGML_BACKEND_PATH" > "$(dirname "$0")/env.txt"\n',
            encoding="utf-8",
        )
        server.chmod(server.stat().st_mode | stat.S_IEXEC)

    write_server(f"version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})")
    pins = {
        "COMMIT": cfg.LLAMA_CPP_COMMIT,
        "BUILD": str(cfg.LLAMA_CPP_BUILD),
        "IMAGE_DIGEST": cfg.LLAMA_IMAGE_DIGEST,
    }
    for name, value in pins.items():
        (tmp_path / name).write_text(value + "\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "LLAMA_SERVER", str(server))
    monkeypatch.setattr(cfg, "LLAMA_BIN_DIR", str(server.parent))
    monkeypatch.setattr(cfg, "LLAMA_COMMIT_FILE", str(tmp_path / "COMMIT"))
    monkeypatch.setattr(cfg, "LLAMA_BUILD_FILE", str(tmp_path / "BUILD"))
    monkeypatch.setattr(cfg, "LLAMA_IMAGE_DIGEST_FILE", str(tmp_path / "IMAGE_DIGEST"))
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/local/cuda/lib64")
    monkeypatch.setenv("GGML_BACKEND_PATH", str(server.parent))
    facts = fetch_assets.llama_server_version()
    assert facts["build_number"] == cfg.LLAMA_CPP_BUILD
    assert facts["commit"] == cfg.LLAMA_CPP_COMMIT[:9] and facts["returncode"] == 0
    assert facts["commit_file"] == cfg.LLAMA_CPP_COMMIT
    assert facts["build_file"] == str(cfg.LLAMA_CPP_BUILD)
    assert facts["image_digest_file"] == cfg.LLAMA_IMAGE_DIGEST
    assert facts["loader_errors"] == []
    env_line = (server.parent / "env.txt").read_text(encoding="utf-8").strip()
    assert env_line == f"LD={server.parent}:/usr/local/cuda/lib64 GGML=", "the variable is dropped"

    def refused() -> core.ProbeError:
        with pytest.raises(core.ProbeError) as exc:
            fetch_assets.llama_server_version()
        return exc.value

    write_server(
        f"{RUN16_LOADER_LINE}\nversion: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})"
    )
    error = refused()
    assert error.code == "llama_backend_load_failed" and "Is a directory" in str(error)
    write_server(f"version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})")
    (tmp_path / "IMAGE_DIGEST").write_text("sha256:" + "0" * 64, encoding="utf-8")
    error = refused()
    assert error.code == "llama_version_mismatch" and "image digest" in str(error)
    (tmp_path / "IMAGE_DIGEST").write_text(cfg.LLAMA_IMAGE_DIGEST, encoding="utf-8")
    (tmp_path / "COMMIT").write_text(cfg.PUBLISHED_LLAMA_CPP_COMMIT, encoding="utf-8")
    error = refused()
    assert error.code == "llama_version_mismatch" and "converter commit" in str(error)
    (tmp_path / "COMMIT").write_text(cfg.LLAMA_CPP_COMMIT, encoding="utf-8")
    write_server("version: 0.5.0-dev (build 11151, commit bd4f514db)")
    error = refused()
    assert error.code == "llama_version_mismatch" and "11151" in str(error)
    write_server("llama_server: initializing ...")
    error = refused()
    assert error.code == "llama_version_mismatch" and "not readable" in str(error)
    monkeypatch.setattr(cfg, "LLAMA_SERVER", str(tmp_path / "missing"))
    assert refused().code == "llama_build_missing"


#: `llama-server --verbose --list-devices` as the check image printed it on 2026-09-24 (amd64,
#: no driver): the registry loaded the best CPU variant and enumerated nothing.
LIST_DEVICES_NO_GPU = (
    "0.00.037.593 I load_backend: loaded CPU backend from /opt/llama/bin/libggml-cpu-sse42.so\n"
    "Available devices:\n"
    "  (none)\n"
)
#: The same with GGML_BACKEND_PATH naming the CUDA backend file: its loader speaks, twice (arg
#: parsing and the device printer each load all backends).
LIST_DEVICES_CUDA_PROBE_NO_DRIVER = (
    "0.00.020.740 E load_backend: failed to load /opt/llama/bin/libggml-cuda.so: libcuda.so.1: "
    "cannot open shared object file: No such file or directory\n"
    "0.00.030.747 I load_backend: loaded CPU backend from /opt/llama/bin/libggml-cpu-sse42.so\n"
    "0.00.030.890 E load_backend: failed to load /opt/llama/bin/libggml-cuda.so: libcuda.so.1: "
    "cannot open shared object file: No such file or directory\n"
    "Available devices:\n"
    "  (none)\n"
)
#: The shape on the Space (the L4 row from the same printer).
LIST_DEVICES_L4 = (
    "0.00.041.002 I load_backend: loaded CUDA backend from /opt/llama/bin/libggml-cuda.so\n"
    "0.00.052.110 I load_backend: loaded CPU backend from /opt/llama/bin/libggml-cpu-icelake.so\n"
    "Available devices:\n"
    "  CUDA0: NVIDIA L4 (22491 MiB, 22001 MiB free)\n"
)


def test_parse_llama_devices_and_the_cuda_requirement() -> None:
    """The device listing read as the printer writes it; lane B requires a CUDA device
    (`llama_cuda_backend_missing`), a registry refusal is `llama_backend_load_failed`."""
    none = core.parse_llama_devices(LIST_DEVICES_NO_GPU)
    assert none["listed"] is True and none["devices"] == [] and none["loader_errors"] == []
    assert none["backends_loaded"] == {"CPU": "/opt/llama/bin/libggml-cpu-sse42.so"}
    assert core.cuda_devices_of(none) == []
    with pytest.raises(core.ProbeError) as exc:
        core.require_cuda_device(none)
    assert exc.value.code == "llama_cuda_backend_missing" and "CPU" in exc.value.message
    probe_out = core.parse_llama_devices(LIST_DEVICES_CUDA_PROBE_NO_DRIVER)
    assert len(probe_out["loader_errors"]) == 2 and "libcuda.so.1" in probe_out["loader_errors"][0]
    assert probe_out["backends_loaded"] == {"CPU": "/opt/llama/bin/libggml-cpu-sse42.so"}
    with pytest.raises(core.ProbeError) as exc:
        core.require_cuda_device(probe_out)
    assert exc.value.code == "llama_backend_load_failed"
    l4 = core.parse_llama_devices(LIST_DEVICES_L4)
    assert l4["devices"] == [
        {"name": "CUDA0", "description": "NVIDIA L4 (22491 MiB, 22001 MiB free)"}
    ]
    assert l4["backends_loaded"]["CUDA"] == "/opt/llama/bin/libggml-cuda.so"
    assert core.require_cuda_device(l4) == l4["devices"]
    unlisted = core.parse_llama_devices("version: 10223 (11924d4c1)\n")
    assert unlisted["listed"] is False and unlisted["devices"] == []
    with pytest.raises(core.ProbeError) as exc:
        core.require_cuda_device(unlisted)
    assert exc.value.code == "llama_cuda_backend_missing" and "no device listing" in str(exc.value)


def _fake_list_devices_server(directory: Path) -> Path:
    """A llama-server that answers `--version` and `--verbose --list-devices`: `plain.txt` when
    GGML_BACKEND_PATH is unset, `loud.txt` when it names a file; every call and the variable's
    state (unset, or its value) appended to `calls.txt`."""
    server = directory / "llama-server"
    server.write_text(
        "#!/bin/sh\n"
        'here="$(dirname "$0")"\n'
        'echo "ARGS=$* GGML=${GGML_BACKEND_PATH-unset}" >> "$here/calls.txt"\n'
        'case "$*" in\n'
        f'  *--version*) echo "version: {cfg.LLAMA_CPP_BUILD} ({cfg.LLAMA_CPP_COMMIT[:9]})" >&2 ;;\n'
        '  *--list-devices*) if [ -n "${GGML_BACKEND_PATH-}" ]; then cat "$here/loud.txt"; '
        'else cat "$here/plain.txt"; fi ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    server.chmod(server.stat().st_mode | stat.S_IEXEC)
    return server


def test_bake_lists_the_backends_and_makes_the_cuda_loader_speak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fetch_assets.llama_server_backends`: the launch listing runs with GGML_BACKEND_PATH unset
    and may carry no refusal; the CUDA probe names the backend file and its loader's answer
    decides — the missing driver is the build host (recorded, tolerated), a loaded backend is
    recorded with its devices, any other refusal fails the build, a plain-run refusal fails it,
    and a backend file that is not in the image fails it before anything runs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    server = _fake_list_devices_server(bin_dir)
    backend = bin_dir / "libggml-cuda.so"
    backend.write_bytes(b"")
    monkeypatch.setattr(cfg, "LLAMA_SERVER", str(server))
    monkeypatch.setattr(cfg, "LLAMA_BIN_DIR", str(bin_dir))
    monkeypatch.setattr(cfg, "LLAMA_CUDA_BACKEND", str(backend))
    monkeypatch.setenv("GGML_BACKEND_PATH", str(bin_dir))
    (bin_dir / "plain.txt").write_text(LIST_DEVICES_NO_GPU, encoding="utf-8")
    (bin_dir / "loud.txt").write_text(
        LIST_DEVICES_CUDA_PROBE_NO_DRIVER.replace("/opt/llama/bin/libggml-cuda.so", str(backend)),
        encoding="utf-8",
    )
    facts = fetch_assets.llama_server_backends()
    assert facts["search"].startswith("beside the executable")
    assert facts["launch"]["backends_loaded"] == {"CPU": "/opt/llama/bin/libggml-cpu-sse42.so"}
    assert facts["launch"]["devices"] == [] and facts["launch"]["loader_errors"] == []
    verdict = facts["cuda_backend"]
    assert verdict["file"] == str(backend) and verdict["loadable"] is None
    assert "libcuda.so.1" in verdict["skipped"] and "libcuda.so.1" in verdict["reason"]
    assert facts["cuda_probe"]["backend_path"] == str(backend)
    calls = (bin_dir / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == [
        "ARGS=--verbose --list-devices GGML=unset",
        f"ARGS=--verbose --list-devices GGML={backend}",
    ]

    (bin_dir / "loud.txt").write_text(
        LIST_DEVICES_L4.replace("/opt/llama/bin/libggml-cuda.so", str(backend)), encoding="utf-8"
    )
    loaded = fetch_assets.llama_server_backends()["cuda_backend"]
    assert loaded["loadable"] is True and loaded["loaded_from"] == str(backend)
    assert loaded["devices"][0]["name"] == "CUDA0"

    def refused() -> core.ProbeError:
        with pytest.raises(core.ProbeError) as exc:
            fetch_assets.llama_server_backends()
        return exc.value

    (bin_dir / "loud.txt").write_text(
        f"0.00.020.740 E load_backend: failed to load {backend}: libcublasLt.so.12: cannot open "
        "shared object file: No such file or directory\nAvailable devices:\n  (none)\n",
        encoding="utf-8",
    )
    error = refused()
    assert error.code == "llama_cuda_backend_unloadable" and "libcublasLt.so.12" in str(error)
    (bin_dir / "loud.txt").write_text("Available devices:\n  (none)\n", encoding="utf-8")
    error = refused()
    assert error.code == "llama_cuda_backend_unloadable" and "no refusal line" in str(error)
    (bin_dir / "plain.txt").write_text(
        f"{RUN16_LOADER_LINE}\nAvailable devices:\n  (none)\n", encoding="utf-8"
    )
    assert refused().code == "llama_backend_load_failed"
    (bin_dir / "plain.txt").write_text("srv    main: nothing listed\n", encoding="utf-8")
    error = refused()
    assert error.code == "llama_server_failed" and "no listing" in str(error)
    backend.unlink()
    assert refused().code == "llama_build_missing"


def test_converter_dependencies_are_checked_before_the_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every distribution the pinned converter imports on the Qwen3 path must be installed, or
    the bake says which before converting (`llama_convert_dependency_missing`); gguf-py's
    declared version is read from its pyproject for the record."""
    present = dict.fromkeys(cfg.LLAMA_CONVERTER_PACKAGES, "1.0")
    monkeypatch.setattr(probe, "package_versions", lambda names: dict(present))
    assert fetch_assets.converter_dependencies() == present
    absent = dict(present, sentencepiece=None, protobuf=None)
    monkeypatch.setattr(probe, "package_versions", lambda names: dict(absent))
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.converter_dependencies()
    assert exc.value.code == "llama_convert_dependency_missing"
    assert "protobuf, sentencepiece" in exc.value.message and "requirements.txt" in str(exc.value)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "gguf"\nversion = "0.19.0"\n', encoding="utf-8"
    )
    assert fetch_assets.gguf_py_version(tmp_path) == "0.19.0"
    assert fetch_assets.gguf_py_version(tmp_path / "absent") is None


def test_bake_gguf_requires_the_export_line_and_records_the_converter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fetch_assets.bake_gguf` against a fake converter: a clean run must write the file and
    print `Model successfully exported to`, and the facts carry the converter's commit, gguf-py's
    version, the dependency versions and the export line; run 16's traceback line is the
    message of `llama_convert_failed`, the log tail its details; a file without the line fails."""
    llama = tmp_path / "llama"
    (llama / "gguf-py").mkdir(parents=True)
    (llama / "gguf-py" / "pyproject.toml").write_text('version = "0.19.0"\n', encoding="utf-8")
    (llama / "COMMIT").write_text(cfg.LLAMA_CPP_COMMIT + "\n", encoding="utf-8")
    convert = llama / "convert_hf_to_gguf.py"
    convert.write_text(
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "out = pathlib.Path(args[args.index('--outfile') + 1])\n"
        "mode = pathlib.Path(__file__).with_name('mode.txt').read_text().strip()\n"
        "print('INFO:hf-to-gguf:Loading model: ' + pathlib.Path(args[-1]).name, file=sys.stderr)\n"
        "print('INFO:hf-to-gguf:gguf: file type = 1', file=sys.stderr)\n"
        "if mode == 'import':\n"
        "    print(\"ModuleNotFoundError: No module named 'sentencepiece'\", file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "out.write_bytes(b'GGUF' * 4)\n"
        "if mode == 'ok':\n"
        "    print(f'INFO:hf-to-gguf:Model successfully exported to {out}', file=sys.stderr)\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    assets = tmp_path / "assets"
    monkeypatch.setenv("PROBE_ASSETS_DIR", str(assets))
    monkeypatch.setattr(cfg, "LLAMA_CONVERT", str(convert))
    monkeypatch.setattr(cfg, "LLAMA_GGUF_PY", str(llama / "gguf-py"))
    monkeypatch.setattr(cfg, "LLAMA_COMMIT_FILE", str(llama / "COMMIT"))
    versions = dict.fromkeys(cfg.LLAMA_CONVERTER_PACKAGES, "x")
    monkeypatch.setattr(probe, "package_versions", lambda names: dict(versions))

    (llama / "mode.txt").write_text("ok\n", encoding="utf-8")
    facts = fetch_assets.bake_gguf(snapshot)
    assert facts["path"] == str(assets / cfg.GGUF_FILENAME) and facts["bytes"] == 16
    assert facts["outtype"] == "f16" and facts["converter"] == str(convert)
    assert facts["converter_commit"] == cfg.LLAMA_CPP_COMMIT
    assert facts["gguf_py_version"] == "0.19.0" and facts["dependencies"] == versions
    assert facts["exported_line"].startswith("INFO:hf-to-gguf:Model successfully exported to ")
    assert facts["log_head"][0] == "INFO:hf-to-gguf:Loading model: snapshot"
    assert facts["log_tail"][-1] == facts["exported_line"] and facts["convert_wall_s"] >= 0

    (llama / "mode.txt").write_text("import\n", encoding="utf-8")
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_gguf(snapshot)
    assert exc.value.code == "llama_convert_failed"
    assert exc.value.message.endswith(
        "exited 1: ModuleNotFoundError: No module named 'sentencepiece'"
    )
    assert exc.value.details["log_tail"][-1].startswith("ModuleNotFoundError")

    (llama / "mode.txt").write_text("silent\n", encoding="utf-8")
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_gguf(snapshot)
    assert exc.value.code == "llama_convert_failed" and "without printing" in exc.value.message

    monkeypatch.setattr(probe, "package_versions", lambda names: dict(versions, protobuf=None))
    with pytest.raises(core.ProbeError) as exc:
        fetch_assets.bake_gguf(snapshot)
    assert exc.value.code == "llama_convert_dependency_missing"
