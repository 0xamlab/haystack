"""The probe's stages, one process each: `python probe.py --stage <name> [--out FILE]`.

Each stage does one thing on the GPU host and reports one JSON object as its last stdout line
(`{"ok": true, ...facts}` or `{"ok": false, "code", "message"}`); logs go to stderr. The
orchestrator in `app.py` runs them in order in subprocesses, so a native abort in one stage is
a phase code on `/health` (`stage_crashed`, with the signal) and never the end of the web app,
and the transformers reference's memory is returned to the host before the page is served.

    driver     nvidia-smi, /proc/driver/nvidia/version, libcuda through ctypes, torch.cuda —
               gated on the 580 driver floor and the published compute capabilities.
    kernel     kernels.get_kernel pinned to the published revision and the cuda backend;
               the native manifest must declare the 6144 staging tier and the runtime must have
               loaded the library the device's capability calls for.
    convert    Qwen3-1.7B (the baked snapshot) -> the f64 CUDA blob with
               algenta.inference.prepare_model_checkpoint, timed; reused when already on disk.
    decode     eight greedy tokens for the fixed prompt through the kernel's DecodeSession,
               with the session open time and every step's wall time.
    baseline   the same decode without Algenta: plain transformers on the same GPU, greedy, one
               lane per dtype (float32, float16), each its own model load; a warm-up generate
               excluded, then a timed generate with every token's arrival time.
    reference  the same prompt through transformers in float32 on the CPU, greedy, with each
               step's top-2 logit margin.

The heavy imports (torch, kernels, algenta, transformers) happen inside the stage that needs
them; importing this module needs the standard library only.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import importlib
import importlib.metadata
import json
import logging
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import probe_config as cfg
import probe_core as core

log = logging.getLogger("gpu_probe")

APP_DIR = Path(__file__).resolve().parent
NVIDIA_SMI_FIELDS: tuple[str, ...] = ("name", "driver_version", "compute_cap", "memory.total")
PACKAGES: tuple[str, ...] = (
    "torch",
    "kernels",
    "huggingface_hub",
    "transformers",
    "tokenizers",
    "safetensors",
    "numpy",
    "algenta",
    "algenta-runtime-native",
    "fastapi",
    "uvicorn",
)
SPACE_ENV_KEYS: tuple[str, ...] = (
    "SPACE_ID",
    "SPACE_HOST",
    "SPACE_REPO_NAME",
    "CPU_CORES",
    "MEMORY",
)
#: The f64 blob of Qwen3-1.7B is 13.76 GB (run 12); the conversion is refused below this.
MIN_FREE_BYTES_FOR_CONVERSION = 15 * 1024**3
STAGES: dict[str, Callable[[], dict[str, Any]]] = {}


def stage(fn: Callable[[], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    STAGES[fn.__name__.removeprefix("stage_")] = fn
    return fn


# ---------------------------------------------------------------------------
# Paths and environment facts (stdlib only; `app.py` reads these in-process)
# ---------------------------------------------------------------------------


def work_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    configured = env.get("PROBE_WORK_DIR", "").strip()
    return Path(configured) if configured else Path.home() / "work"


def build_facts_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    configured = env.get("PROBE_BUILD_FACTS", "").strip()
    return Path(configured) if configured else Path.home() / "assets" / "build_facts.json"


def read_build_facts(path: Path | None = None) -> dict[str, Any]:
    target = build_facts_path() if path is None else path
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def package_versions(names: tuple[str, ...] = PACKAGES) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def environment_facts(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if env is None else env
    libc = platform.libc_ver()
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "glibc": libc[1] if libc[0] == "glibc" else None,
        "machine": platform.machine(),
        "system": platform.system(),
        "cpu_count": os.cpu_count(),
        "cuda_version_env": env.get("CUDA_VERSION") or None,
        "nvidia_require_cuda": (env.get("NVIDIA_REQUIRE_CUDA") or "")[:120] or None,
        "nvidia_disable_require": env.get("NVIDIA_DISABLE_REQUIRE") or None,
        "hf_hub_offline": env.get("HF_HUB_OFFLINE") or None,
        "ld_library_path": env.get("LD_LIBRARY_PATH") or None,
        "packages": package_versions(),
    }


def space_facts(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if env is None else env
    facts: dict[str, Any] = {key: env.get(key) or None for key in SPACE_ENV_KEYS}
    facts["hardware_requested"] = cfg.HARDWARE
    return facts


def max_rss_mib() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes, macOS bytes.
    return round(usage / (1024 if sys.platform != "darwin" else 1024 * 1024), 1)


def disk_free_bytes(path: Path) -> int:
    target = path if path.exists() else path.parent
    return shutil.disk_usage(target).free


def apply_ua_shim() -> bool:
    import hf_ua_shim

    return hf_ua_shim.apply()


# ---------------------------------------------------------------------------
# Device facts
# ---------------------------------------------------------------------------


def nvidia_smi_facts() -> dict[str, str]:
    binary = shutil.which("nvidia-smi")
    if binary is None:
        raise core.ProbeError("nvidia_smi_missing", "nvidia-smi is not on PATH; no GPU runtime")
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no user input
            [binary, f"--query-gpu={','.join(NVIDIA_SMI_FIELDS)}", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise core.ProbeError("nvidia_smi_failed", f"nvidia-smi did not run: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise core.ProbeError(
            "nvidia_smi_failed",
            f"nvidia-smi exited {proc.returncode}: {detail[-1] if detail else 'no output'}",
        )
    first = next((row for row in proc.stdout.splitlines() if row.strip()), "")
    facts = core.parse_nvidia_smi(first, NVIDIA_SMI_FIELDS)
    facts["query_fields"] = ",".join(NVIDIA_SMI_FIELDS)
    return facts


def proc_driver_version() -> str | None:
    try:
        return Path("/proc/driver/nvidia/version").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def libcuda_mapped_paths() -> list[str]:
    try:
        rows = Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    paths = {row.split()[-1] for row in rows if "libcuda.so" in row}
    return sorted(paths)


def libcuda_facts() -> dict[str, Any]:
    """Device 0 through the driver library itself, the way the kernel's loader will see it."""
    cuda = None
    for candidate in ("libcuda.so.1", "libcuda.so"):
        try:
            cuda = ctypes.CDLL(candidate)
            break
        except OSError:
            continue
    if cuda is None:
        raise core.ProbeError(
            "libcuda_missing", "libcuda.so.1 was not found; the CUDA build needs the NVIDIA driver"
        )
    rc = int(cuda.cuInit(0))
    if rc != 0:
        raise core.ProbeError("cuinit_failed", f"cuInit returned {rc}: no usable NVIDIA device")
    version = ctypes.c_int(0)
    cuda.cuDriverGetVersion(ctypes.byref(version))
    count = ctypes.c_int(0)
    cuda.cuDeviceGetCount(ctypes.byref(count))
    if count.value < 1:
        raise core.ProbeError("no_gpu", "the driver reports no CUDA device")
    device = ctypes.c_int(0)
    if int(cuda.cuDeviceGet(ctypes.byref(device), 0)) != 0:
        raise core.ProbeError("no_gpu", "cuDeviceGet(0) failed")
    name = ctypes.create_string_buffer(256)
    cuda.cuDeviceGetName(name, 256, device)
    major, minor = ctypes.c_int(0), ctypes.c_int(0)
    cuda.cuDeviceGetAttribute(ctypes.byref(major), 75, device)  # COMPUTE_CAPABILITY_MAJOR
    cuda.cuDeviceGetAttribute(ctypes.byref(minor), 76, device)  # COMPUTE_CAPABILITY_MINOR
    total = ctypes.c_size_t(0)
    total_fn = getattr(cuda, "cuDeviceTotalMem_v2", None) or cuda.cuDeviceTotalMem
    total_fn.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.c_int]
    total_fn(ctypes.byref(total), device)
    api = version.value
    return {
        "cu_init": rc,
        "cu_driver_get_version": api,
        "cuda_driver_api": f"{api // 1000}.{(api % 1000) // 10}",
        "device_count": count.value,
        "device_name": name.value.decode("utf-8", "ignore"),
        "compute_capability": [major.value, minor.value],
        "total_memory_bytes": int(total.value),
        "libcuda_mapped_paths": libcuda_mapped_paths(),
    }


def torch_cuda_facts() -> dict[str, Any]:
    import torch

    available = bool(torch.cuda.is_available())
    facts: dict[str, Any] = {
        "version": torch.__version__,
        "cuda": torch.version.cuda,
        "cxx11_abi": bool(getattr(torch._C, "_GLIBCXX_USE_CXX11_ABI", True)),
        "cuda_available": available,
    }
    if available:
        facts["device_name"] = torch.cuda.get_device_name(0)
        facts["compute_capability"] = list(torch.cuda.get_device_capability(0))
        free, total = torch.cuda.mem_get_info(0)
        facts["free_bytes"] = int(free)
        facts["total_bytes"] = int(total)
    return facts


@stage
def stage_driver() -> dict[str, Any]:
    smi = nvidia_smi_facts()
    gate = core.driver_gate(smi["driver_version"])
    cuda = libcuda_facts()
    cc = core.compute_capability_gate(cuda["compute_capability"])
    torch_facts = torch_cuda_facts()
    if not torch_facts["cuda_available"]:
        raise core.ProbeError(
            "torch_cuda_unavailable",
            f"torch {torch_facts['version']} sees no CUDA device although the driver does",
        )
    return {
        **gate,
        "nvidia_smi": smi,
        "proc_driver_version": proc_driver_version(),
        **cuda,
        "compute_capability": list(cc),
        "compute_capability_supported": True,
        "torch": torch_facts,
        "ld_library_path": os.environ.get("LD_LIBRARY_PATH") or None,
    }


# ---------------------------------------------------------------------------
# The kernel
# ---------------------------------------------------------------------------


def native_of(kernel: ModuleType) -> tuple[ModuleType, Path]:
    """The kernel's `_native` loader module and directory, found from the package itself."""
    execute_fn = getattr(kernel, "execute", None)
    defining = sys.modules.get(getattr(execute_fn, "__module__", "") or "")
    if defining is None:
        defining = getattr(kernel, "algenta_llm", None)
    if defining is None:
        raise core.ProbeError("kernel_native_missing", "the kernel package exposes no _native half")
    try:
        native = importlib.import_module(f"{defining.__name__}._native")
    except Exception as exc:  # noqa: BLE001 - reported as a typed phase code
        raise core.ProbeError("kernel_native_missing", f"_native did not import: {exc}") from exc
    # the snapshot path, not `.resolve()`: the Hub cache holds symlinks into blobs/
    native_dir = Path(getattr(defining, "__file__", "")).parent / "_native"
    return native, native_dir


def read_native_manifest(native_dir: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((native_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise core.ProbeError(
            "kernel_manifest_missing", f"{native_dir / 'manifest.json'} is unreadable: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise core.ProbeError("kernel_manifest_invalid", "the native manifest is not an object")
    return manifest


def load_kernel() -> tuple[ModuleType, dict[str, Any], dict[str, Any]]:
    """`get_kernel` pinned to the published revision; returns (module, manifest, facts)."""
    apply_ua_shim()
    from kernels import get_kernel

    t0 = time.perf_counter()
    kernel = get_kernel(
        cfg.KERNEL_REPO,
        revision=cfg.KERNEL_REVISION,
        backend=cfg.KERNEL_BACKEND,
        trust_remote_code=[cfg.KERNEL_REPO],
    )
    get_kernel_s = time.perf_counter() - t0
    path = getattr(kernel, "__file__", "")
    revision = core.revision_gate(path)
    variant = core.variant_gate(path)
    _, native_dir = native_of(kernel)
    manifest = read_native_manifest(native_dir)
    tier = core.tier_gate(manifest)
    facts = {
        "repo": cfg.KERNEL_REPO,
        "revision": revision,
        "variant": variant,
        "expected_variant": cfg.EXPECTED_VARIANT,
        "backend": cfg.KERNEL_BACKEND,
        "file": str(path),
        "get_kernel_s": round(get_kernel_s, 2),
        "resident_stage_tier": tier,
        "cuda_targets": core.cuda_targets_of(manifest),
        "cuda_libraries": dict(manifest.get("cuda_libraries") or {}),
        "primary_library": manifest.get("library"),
        "abi_version": manifest.get("abi_version"),
        "mojo_version": manifest.get("mojo_version"),
        "source_commit": manifest.get("source_commit"),
        "arch_check": "passed",
    }
    return kernel, manifest, facts


def load_native(kernel: ModuleType, manifest: Mapping[str, Any], cc: list[int]) -> dict[str, Any]:
    """Initialise the native runtime and check it picked the library for this device."""
    native, _ = native_of(kernel)
    t0 = time.perf_counter()
    try:
        rt = native.runtime()
    except Exception as exc:  # noqa: BLE001 - the glue raises KernelError with a code
        raise core.public_error(exc) from exc
    native_init_s = time.perf_counter() - t0
    selected = getattr(rt, "library", None)
    core.library_gate(selected, manifest, cc)
    version_fn = getattr(getattr(rt, "_lib", None), "algenta_runtime_version", None)
    answered = int(version_fn()) if callable(version_fn) else None
    return {
        "selected_library": selected,
        "native_init_s": round(native_init_s, 2),
        "abi_answered": answered,
        "loaded": answered is not None and answered == manifest.get("abi_version"),
    }


@stage
def stage_kernel() -> dict[str, Any]:
    cc = list(core.compute_capability_gate(libcuda_facts()["compute_capability"]))
    kernel, manifest, facts = load_kernel()
    facts.update(load_native(kernel, manifest, cc))
    facts["compute_capability"] = cc
    return facts


# ---------------------------------------------------------------------------
# The model: snapshot, tokenizer, conversion
# ---------------------------------------------------------------------------


def model_snapshot() -> Path:
    """The baked Qwen3-1.7B snapshot: the path the build recorded, else the offline cache."""
    facts = read_build_facts()
    recorded = ((facts.get("model") or {}).get("path") or "").strip()
    if recorded and (Path(recorded) / "config.json").is_file():
        return Path(recorded)
    apply_ua_shim()
    from huggingface_hub import snapshot_download

    try:
        path = snapshot_download(cfg.MODEL_REPO, revision=cfg.MODEL_REVISION, local_files_only=True)
    except Exception as exc:  # noqa: BLE001 - any cache error means the bake did not happen
        raise core.ProbeError(
            "model_snapshot_missing",
            f"{cfg.MODEL_REPO}@{cfg.MODEL_REVISION[:12]} is not in the image's cache: "
            f"{type(exc).__name__}",
        ) from exc
    return Path(path)


def prompt_token_ids(snapshot: Path) -> list[int]:
    from algenta.tokenizer import load_tokenizer

    return [int(t) for t in load_tokenizer(snapshot).encode(cfg.PROMPT, add_special_tokens=False)]


def decode_text(snapshot: Path, ids: list[int]) -> str:
    from algenta.tokenizer import load_tokenizer

    return load_tokenizer(snapshot).decode([int(t) for t in ids])


def converted_dir() -> Path:
    return work_dir() / cfg.CONVERTED_DIRNAME


def converted_present(out_dir: Path) -> bool:
    return (out_dir / "manifest.json").is_file() and (out_dir / "weights.blob").is_file()


@stage
def stage_convert() -> dict[str, Any]:
    snapshot = model_snapshot()
    ids = prompt_token_ids(snapshot)
    out_dir = converted_dir()
    facts: dict[str, Any] = {
        "repo": cfg.MODEL_REPO,
        "revision": cfg.MODEL_REVISION,
        "snapshot": str(snapshot),
        "out_dir": str(out_dir),
        "weights_dtype": cfg.WEIGHTS_DTYPE,
        "backend": cfg.KERNEL_BACKEND,
        "prompt_ids": ids,
        "prompt_ids_match_run12": ids == list(cfg.RUN12_PROMPT_IDS),
    }
    if converted_present(out_dir):
        facts.update(reused=True, wall_s=None)
    else:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        free = disk_free_bytes(out_dir.parent)
        facts["disk_free_before_bytes"] = free
        if free < MIN_FREE_BYTES_FOR_CONVERSION:
            raise core.ProbeError(
                "disk_insufficient",
                f"{free / 1024**3:.1f} GiB free; the f64 blob needs about 13 GiB plus headroom",
            )
        from algenta.inference import prepare_model_checkpoint

        t0 = time.perf_counter()
        try:
            returned = prepare_model_checkpoint(
                snapshot,
                ids,
                out_dir=out_dir,
                weights_dtype=cfg.WEIGHTS_DTYPE,
                backend=cfg.KERNEL_BACKEND,
            )
        except Exception as exc:  # noqa: BLE001 - InferenceError carries its code
            raise core.public_error(exc) from exc
        facts.update(
            reused=False,
            wall_s=round(time.perf_counter() - t0, 2),
            returned_dir=str(returned),
            disk_free_after_bytes=disk_free_bytes(out_dir.parent),
        )
    if not converted_present(out_dir):
        raise core.ProbeError(
            "conversion_incomplete", f"{out_dir} lacks manifest.json or weights.blob"
        )
    facts["blob_bytes"] = (out_dir / "weights.blob").stat().st_size
    try:
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    tensors = manifest.get("tensors")
    facts["n_tensors"] = len(tensors) if isinstance(tensors, list | dict) else None
    config = manifest.get("config")
    facts["manifest_config"] = config if isinstance(config, dict) else None
    facts["max_rss_mib"] = max_rss_mib()
    return facts


# ---------------------------------------------------------------------------
# The decode on the GPU
# ---------------------------------------------------------------------------


def decode_session_class(kernel: ModuleType) -> type:
    cls = getattr(kernel, "DecodeSession", None)
    if cls is None:
        cls = getattr(getattr(kernel, "algenta_llm", None), "DecodeSession", None)
    if cls is None:
        raise core.ProbeError(
            "decode_session_missing", "the kernel package exposes no DecodeSession"
        )
    return cls


@stage
def stage_decode() -> dict[str, Any]:
    cc = list(core.compute_capability_gate(libcuda_facts()["compute_capability"]))
    kernel, manifest, kernel_facts = load_kernel()
    native_facts = load_native(kernel, manifest, cc)
    checkpoint = converted_dir()
    if not converted_present(checkpoint):
        raise core.ProbeError("checkpoint_missing", f"{checkpoint} holds no converted checkpoint")
    snapshot = model_snapshot()
    ids = prompt_token_ids(snapshot)
    import torch

    free_start = int(torch.cuda.mem_get_info(0)[0]) if torch.cuda.is_available() else None
    session_cls = decode_session_class(kernel)
    tokens: list[int] = []
    positions: list[int | None] = []
    step_ms: list[float] = []
    stopped_on_eos = False
    t0 = time.perf_counter()
    try:
        session = session_cls(str(checkpoint), ids, max_new_tokens=cfg.MAX_NEW_TOKENS)
    except Exception as exc:  # noqa: BLE001 - KernelError carries its code (run 11's refusal)
        raise core.public_error(exc) from exc
    open_s = time.perf_counter() - t0
    try:
        free_after_open = int(torch.cuda.mem_get_info(0)[0]) if torch.cuda.is_available() else None
        for _ in range(cfg.MAX_NEW_TOKENS):
            t1 = time.perf_counter()
            try:
                step = session.step()
            except Exception as exc:  # noqa: BLE001
                raise core.public_error(exc) from exc
            step_ms.append((time.perf_counter() - t1) * 1000.0)
            tokens.append(int(step["token_id"]))
            positions.append(step.get("position"))
            if step.get("stopped_on_eos"):
                stopped_on_eos = True
            if step.get("done"):
                break
    finally:
        try:
            session.close()
        except Exception as exc:  # noqa: BLE001 - a close error is a note, the tokens are the result
            log.warning("session close: %s", exc)
    free_after_close = int(torch.cuda.mem_get_info(0)[0]) if torch.cuda.is_available() else None
    return {
        **kernel_facts,
        **native_facts,
        "compute_capability": cc,
        "checkpoint_dir": str(checkpoint),
        "prompt": cfg.PROMPT,
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "session_n_prompt": getattr(session, "n_prompt", None),
        "max_new_tokens": cfg.MAX_NEW_TOKENS,
        "open_s": round(open_s, 2),
        "step_ms": [round(ms, 2) for ms in step_ms],
        "tokens": tokens,
        "positions": positions,
        "stopped_on_eos": stopped_on_eos,
        "decoded": decode_text(snapshot, tokens),
        "gpu_free_bytes_start": free_start,
        "gpu_free_bytes_after_open": free_after_open,
        "gpu_free_bytes_after_close": free_after_close,
        "max_rss_mib": max_rss_mib(),
    }


# ---------------------------------------------------------------------------
# The baseline: the same decode without Algenta, transformers on the same GPU
# ---------------------------------------------------------------------------


class StepClock:
    """A `generate` streamer that timestamps every token as it reaches the host.

    transformers calls `put(input_ids.cpu())` once with the prompt before the prefill and
    `put(next_tokens.cpu())` after each token is chosen; `.cpu()` synchronises the device, so
    a timestamp is the moment that token is on the host. Step 1 is measured from `t0` (set
    right before the timed call) and is the prefill: generate's setup, the forward pass over
    the prompt, the argmax and the copy. Every later step is the gap between two consecutive
    tokens: the stopping check, the cache update, one forward pass over one token, the argmax
    and the copy — the whole per-token cost as a caller of `generate` sees it.
    """

    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.puts: list[tuple[float, list[int]]] = []
        self.ended_at: float | None = None

    def start(self) -> None:
        self.t0 = time.perf_counter()

    def put(self, value: Any) -> None:
        stamp = time.perf_counter()
        flat = value.reshape(-1).tolist()
        self.puts.append((stamp, [int(t) for t in flat]))

    def end(self) -> None:
        self.ended_at = time.perf_counter()

    def prompt_echoed(self, n_prompt: int) -> bool:
        return bool(self.puts) and len(self.puts[0][1]) == n_prompt

    def token_times(self) -> tuple[list[int], list[float]]:
        """(token ids, per-step ms) from the single-token puts; the prompt echo is skipped."""
        tokens: list[int] = []
        step_ms: list[float] = []
        prev = self.t0
        for stamp, values in self.puts:
            if len(values) != 1:
                continue
            tokens.append(values[0])
            step_ms.append((stamp - prev) * 1000.0)
            prev = stamp
        return tokens, step_ms


def timed_generate(model: Any, prompt: Any, n_prompt: int) -> dict[str, Any]:
    """One greedy `generate` of `MAX_NEW_TOKENS` on the device, every token timestamped."""
    import torch

    clock = StepClock()
    torch.cuda.synchronize()
    clock.start()
    out = model.generate(
        prompt,
        max_new_tokens=cfg.MAX_NEW_TOKENS,
        do_sample=False,
        num_beams=1,
        streamer=clock,
    )
    torch.cuda.synchronize()
    generate_s = time.perf_counter() - clock.t0
    sequences = getattr(out, "sequences", out)
    tokens = [int(t) for t in sequences[0, n_prompt:].tolist()]
    streamed, step_ms = clock.token_times()
    return {
        "tokens": tokens,
        "streamed_tokens": streamed,
        "step_ms": [round(ms, 3) for ms in step_ms],
        "ttft_s": round(step_ms[0] / 1000.0, 3) if step_ms else None,
        "generate_s": round(generate_s, 3),
        "prompt_echoed": clock.prompt_echoed(n_prompt),
    }


def _lane_failure(lane: dict[str, Any], code: str, exc: BaseException) -> dict[str, Any]:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    log.error("baseline lane %s: %s — %s", lane.get("dtype"), code, text[:300])
    return {**lane, "ok": False, "code": code, "message": f"{type(exc).__name__}: {text[:300]}"}


def baseline_lane(dtype_name: str, snapshot: Path, ids: list[int]) -> dict[str, Any]:
    """One lane: load the model in `dtype_name` onto the device, one warm-up generate
    (excluded), one timed generate; the device is emptied before returning. Fails closed with
    `baseline_oom`, `baseline_load_failed`, `baseline_generate_failed` or
    `baseline_step_count_mismatch`; a failed lane carries no timing."""
    import torch
    from transformers import AutoModelForCausalLM

    device = torch.device("cuda", 0)
    dtype = getattr(torch, dtype_name)
    lane: dict[str, Any] = {"ok": False, "dtype": dtype_name, "torch_dtype": str(dtype)}
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats(device)
    free_before = int(torch.cuda.mem_get_info(0)[0])
    lane["gpu_free_bytes_before"] = free_before
    model = None
    try:
        t0 = time.perf_counter()
        try:
            try:
                model = AutoModelForCausalLM.from_pretrained(str(snapshot), dtype=dtype)
            except TypeError:
                model = AutoModelForCausalLM.from_pretrained(str(snapshot), torch_dtype=dtype)
            model.to(device)
            model.eval()
            torch.cuda.synchronize()
        except torch.cuda.OutOfMemoryError as exc:
            return _lane_failure(lane, "baseline_oom", exc)
        except Exception as exc:  # noqa: BLE001 - reported as the lane's code
            return _lane_failure(lane, "baseline_load_failed", exc)
        lane["load_s"] = round(time.perf_counter() - t0, 2)
        free_after_load = int(torch.cuda.mem_get_info(0)[0])
        lane["gpu_free_bytes_after_load"] = free_after_load
        lane["device_taken_bytes"] = max(0, free_before - free_after_load)
        lane["weights_allocated_bytes"] = int(torch.cuda.memory_allocated(device))
        lane["model_dtype"] = str(next(model.parameters()).dtype)
        lane["eos_token_id"] = getattr(model.generation_config, "eos_token_id", None)
        prompt = torch.tensor([ids], dtype=torch.long, device=device)
        try:
            with torch.no_grad():
                warm = timed_generate(model, prompt, len(ids))
                timed = timed_generate(model, prompt, len(ids))
        except torch.cuda.OutOfMemoryError as exc:
            return _lane_failure(lane, "baseline_oom", exc)
        except Exception as exc:  # noqa: BLE001
            return _lane_failure(lane, "baseline_generate_failed", exc)
        lane["peak_allocated_bytes"] = int(torch.cuda.max_memory_allocated(device))
        lane["peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved(device))
        if timed["tokens"] != timed["streamed_tokens"] or not timed["prompt_echoed"]:
            return _lane_failure(
                lane,
                "baseline_step_count_mismatch",
                RuntimeError(
                    f"the streamer saw {timed['streamed_tokens']} for {timed['tokens']}; "
                    "the per-step times cannot be attributed"
                ),
            )
        eos = lane["eos_token_id"]
        eos_ids = {int(e) for e in (eos if isinstance(eos, list) else [eos]) if e is not None}
        tokens = timed["tokens"]
        short = bool(tokens) and len(tokens) < cfg.MAX_NEW_TOKENS
        lane.update(
            ok=True,
            warmup={
                "excluded": True,
                "tokens": warm["tokens"],
                "step_ms": warm["step_ms"],
                "ttft_s": warm["ttft_s"],
                "generate_s": warm["generate_s"],
            },
            tokens=tokens,
            step_ms=timed["step_ms"],
            ttft_s=timed["ttft_s"],
            generate_s=timed["generate_s"],
            same_tokens_as_warmup=tokens == warm["tokens"],
            stopped_on_eos=short and tokens[-1] in eos_ids,
            decoded=decode_text(snapshot, tokens),
        )
        return lane
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()


@stage
def stage_baseline() -> dict[str, Any]:
    import torch
    import transformers

    if not torch.cuda.is_available():
        raise core.ProbeError(
            "torch_cuda_unavailable", f"torch {torch.__version__} sees no CUDA device"
        )
    torch.manual_seed(0)
    snapshot = model_snapshot()
    ids = prompt_token_ids(snapshot)
    free_start, total = (int(v) for v in torch.cuda.mem_get_info(0))
    lanes: dict[str, dict[str, Any]] = {}
    for name in cfg.BASELINE_DTYPES:
        lanes[name] = baseline_lane(name, snapshot, ids)
    return {
        "method": (
            "transformers generate on CUDA, greedy, max_new_tokens 8; one warm-up generate "
            "excluded; per-step times are the gaps between consecutive tokens reaching the host "
            "through the generate streamer"
        ),
        "device_name": torch.cuda.get_device_name(0),
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "transformers": transformers.__version__,
        "snapshot": str(snapshot),
        "prompt": cfg.PROMPT,
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "max_new_tokens": cfg.MAX_NEW_TOKENS,
        "dtypes": list(cfg.BASELINE_DTYPES),
        "gpu_total_bytes": total,
        "gpu_free_bytes_start": free_start,
        "gpu_free_bytes_end": int(torch.cuda.mem_get_info(0)[0]),
        "lanes": lanes,
        "max_rss_mib": max_rss_mib(),
    }


# ---------------------------------------------------------------------------
# The transformers reference on the CPU
# ---------------------------------------------------------------------------


def top2_margins(logits: list[Any]) -> list[float]:
    """For each generation step, the gap between the best and the second-best logit."""
    import torch

    margins: list[float] = []
    for row in logits:
        values = torch.topk(row[0].float(), 2).values
        margins.append(float(values[0] - values[1]))
    return margins


@stage
def stage_reference() -> dict[str, Any]:
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    threads = max(1, min(cfg.REFERENCE_THREADS, os.cpu_count() or 1))
    torch.set_num_threads(threads)
    torch.manual_seed(0)
    snapshot = model_snapshot()
    ids = prompt_token_ids(snapshot)
    hf_tokenizer = AutoTokenizer.from_pretrained(str(snapshot))
    hf_ids = [int(t) for t in hf_tokenizer(cfg.PROMPT, add_special_tokens=False)["input_ids"]]
    t0 = time.perf_counter()
    try:
        model = AutoModelForCausalLM.from_pretrained(str(snapshot), dtype=torch.float32)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(str(snapshot), torch_dtype=torch.float32)
    model.eval()
    load_s = time.perf_counter() - t0
    prompt = torch.tensor([ids], dtype=torch.long)
    t1 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(
            prompt,
            max_new_tokens=cfg.MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=1,
            output_logits=True,
            return_dict_in_generate=True,
        )
    generate_s = time.perf_counter() - t1
    tokens = [int(t) for t in out.sequences[0, prompt.shape[1] :].tolist()]
    margins = top2_margins(list(out.logits)) if getattr(out, "logits", None) else []
    eos = getattr(model.generation_config, "eos_token_id", None)
    return {
        "reference": "transformers float32 greedy, CPU",
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "threads": threads,
        "snapshot": str(snapshot),
        "prompt_ids": ids,
        "transformers_prompt_ids": hf_ids,
        "prompt_ids_agree_with_algenta_tokenizer": hf_ids == ids,
        "load_s": round(load_s, 2),
        "generate_s": round(generate_s, 2),
        "tokens": tokens,
        "top2_margins": [round(m, 6) for m in margins],
        "decoded": hf_tokenizer.decode(tokens),
        "eos_token_id": eos,
        "max_rss_mib": max_rss_mib(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_stage(name: str) -> dict[str, Any]:
    """One stage's report, `ok` either way; the exception becomes its code and message."""
    fn = STAGES.get(name)
    if fn is None:
        return {
            "ok": False,
            "stage": name,
            "code": "unknown_stage",
            "message": f"known stages: {', '.join(STAGES)}",
        }
    started = core.utc_now()
    t0 = time.perf_counter()
    try:
        data = fn()
    except core.ProbeError as exc:
        report: dict[str, Any] = {"ok": False, "stage": name, **exc.as_dict()}
    except Exception as exc:  # noqa: BLE001 - the last line must still be one JSON object
        log.exception("stage %s raised", name)
        report = {"ok": False, "stage": name, **core.public_error(exc).as_dict()}
    else:
        report = {"ok": True, "stage": name, **data}
    report["started_utc"] = started
    report["finished_utc"] = core.utc_now()
    report["stage_wall_s"] = round(time.perf_counter() - t0, 2)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="run one GPU probe stage and report JSON")
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    ap.add_argument("--out", type=Path, default=None, help="also write the report here")
    a = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    report = run_stage(a.stage)
    text = json.dumps(report, sort_keys=True)
    if a.out is not None:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n", encoding="utf-8")
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
