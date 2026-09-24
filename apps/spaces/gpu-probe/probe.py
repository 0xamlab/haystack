"""The probe's stages, one process each: `python probe.py --stage <name> [--out FILE]`.

Each stage does one thing on the GPU host and reports one JSON object as its last stdout line
(`{"ok": true, ...facts}` or `{"ok": false, "code", "message"}`); logs go to stderr. The
orchestrator in `app.py` runs them in order in subprocesses, so a native abort in one stage is
a phase code on `/health` (`stage_crashed`, with the signal) and never the end of the web app,
and each lane has the whole GPU to itself.

    driver     nvidia-smi, /proc/driver/nvidia/version, libcuda through ctypes, torch.cuda —
               gated on the 580 driver floor and the published compute capabilities.
    kernel     kernels.get_kernel pinned to the published revision and the cuda backend;
               the native manifest must declare the 6144 staging tier and the runtime must have
               loaded the library the device's capability calls for.
    convert    Qwen3-0.6B-Base (the baked snapshot) -> the f64 CUDA blob with
               algenta.inference.prepare_model_checkpoint, the 256-token race prompt baked into
               the manifest; reused when already on disk.
    engine     lane A, the shipped engine: `conform_generate_cuda` from the installed
               algenta-runtime-native wheel, located as `algenta serve` locates it, gated on
               its manifest's compile target, run as the published battery runs it
               (`<ckpt> --max-new 64 --prompt-len 256`), one warm-up excluded, median of 3;
               gen=256 too when the budget allows. When `ALGENTA_CUDA_ENGINE` names the
               packed-int8 captured-graph driver (`qwen3_p3_graph_cuda`, the published
               cells' session, built for sm_89 and shipped beside the app), the lane speaks
               that driver's protocol instead: `<ckpt> --runs 3`, one process for its gates
               and its gen=64 / gen=256 cells, the figures read from its prints, and the
               whole run on the campaign prompt fixture its oracle is bound to.
    llama      lane B, the published opponent: llama-server (llama.cpp at the pinned commit,
               GGML_CUDA, sm_89) on the F16 GGUF of the same snapshot, `-ngl 99`, the same 256
               ids as a token array, greedy, warm-up excluded, median of 3; llama.cpp's own
               timings are the figures.
    decode     lane C, the Hub kernels' f32 parity path: `DecodeSession` over the same blob,
               one warm-up session excluded, three timed sessions of 64 greedy tokens.
    baseline   lane D, the naive stack: plain transformers on the same GPU, greedy, one lane
               per dtype (float32, float16), each its own model load; a warm-up generate
               excluded, then three timed generates with every token's arrival time.
    reference  the same prompt through transformers in float32 on the CPU, greedy, with each
               step's top-2 logit margin: the oracle every lane's tokens are compared with.

The heavy imports (torch, kernels, algenta, transformers) happen inside the stage that needs
them; importing this module needs the standard library only.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
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
import threading
import time
import urllib.error
import urllib.request
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
#: The f64 blob of Qwen3-0.6B-Base is about 4.8 GB; the conversion is refused below this.
MIN_FREE_BYTES_FOR_CONVERSION = 8 * 1024**3
#: Per-run ceiling for one engine launch or one llama-server request.
ENGINE_RUN_TIMEOUT_S = 240.0
LLAMA_REQUEST_TIMEOUT_S = 240.0
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


def assets_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    configured = env.get("PROBE_ASSETS_DIR", "").strip()
    return Path(configured) if configured else Path.home() / "assets"


def build_facts_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    configured = env.get("PROBE_BUILD_FACTS", "").strip()
    return Path(configured) if configured else assets_dir(env) / "build_facts.json"


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


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def gpu_memory_used_bytes() -> int | None:
    """Device 0's used memory through nvidia-smi, in bytes; None when unreadable."""
    binary = shutil.which("nvidia-smi")
    if binary is None:
        return None
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv
            [binary, "--query-gpu=memory.used", "--format=csv,noheader,nounits", "--id=0"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first = next((row.strip() for row in proc.stdout.splitlines() if row.strip()), "")
    if proc.returncode != 0 or not first.isdigit():
        return None
    return int(first) * 1024 * 1024


class GpuMemorySampler:
    """Peak device memory used while an external process runs, sampled through nvidia-smi.

    The engine and llama-server are separate processes, so torch's allocator sees nothing of
    them; nvidia-smi's `memory.used` is the one common meter. `peak_delta_bytes` is the peak
    sample minus the baseline read before `start`.
    """

    def __init__(self, interval_s: float = 0.25) -> None:
        self.interval_s = interval_s
        self.baseline: int | None = None
        self.peak: int | None = None
        self.samples = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            used = gpu_memory_used_bytes()
            if used is not None:
                self.samples += 1
                self.peak = used if self.peak is None else max(self.peak, used)
            self._stop.wait(self.interval_s)

    def start(self) -> GpuMemorySampler:
        self.baseline = gpu_memory_used_bytes()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="gpu-mem-sampler", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        delta = None
        if self.baseline is not None and self.peak is not None:
            delta = max(0, self.peak - self.baseline)
        return {
            "baseline_bytes": self.baseline,
            "peak_bytes": self.peak,
            "peak_delta_bytes": delta,
            "samples": self.samples,
        }


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
        "gpu_memory_used_bytes_idle": gpu_memory_used_bytes(),
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
        "model_stage_needed": cfg.MODEL_STAGE_NEEDED,
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
    """The baked model snapshot: the path the build recorded, else the offline cache."""
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


def decode_text(snapshot: Path, ids: list[int]) -> str:
    from algenta.tokenizer import load_tokenizer

    return load_tokenizer(snapshot).decode([int(t) for t in ids])


def safe_decode(snapshot: Path, ids: list[int]) -> str | None:
    try:
        return decode_text(snapshot, ids)
    except Exception as exc:  # noqa: BLE001 - the text is a courtesy; the ids are the result
        log.warning("decode text: %s", exc)
        return None


def converted_dir() -> Path:
    return work_dir() / cfg.CONVERTED_DIRNAME


def converted_present(out_dir: Path) -> bool:
    return (out_dir / "manifest.json").is_file() and (out_dir / "weights.blob").is_file()


def read_converted_manifest(out_dir: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def converted_prompt_ids(out_dir: Path) -> list[int] | None:
    """The prompt a converted checkpoint carries (its manifest's `input_ids`), or None when the
    manifest is missing, unreadable or has no id list."""
    baked = read_converted_manifest(out_dir).get("input_ids")
    try:
        return [int(t) for t in baked] if isinstance(baked, list) else None
    except (TypeError, ValueError):
        return None


def prompt_fixture_of(ids: list[int] | None) -> str | None:
    """Which prompt fixture an id list is (`battery`, `campaign`), or None for any other prompt."""
    if not ids:
        return None
    return next(
        (name for name in cfg.PROMPT_FIXTURES if core.race_prompt_ids(len(ids), name) == ids),
        None,
    )


def remove_stale_checkpoint(out_dir: Path, *, fixture: str, ids: list[int]) -> dict[str, Any]:
    """A converted checkpoint whose prompt is not the run's fixture — one left by an earlier boot
    on a persistent work dir, converted with the other fixture (or with an unreadable manifest) —
    is removed so the stage converts again. Every lane reads its prompt from this directory, so
    it is replaced, not raced. `conversion_prompt_mismatch` remains for the one case the stage
    cannot recover from: the directory would not go."""
    baked = converted_prompt_ids(out_dir)
    removed = {
        "path": str(out_dir),
        "baked_fixture": prompt_fixture_of(baked),
        "baked_n_prompt": None if baked is None else len(baked),
        "reason": (
            "the manifest carries no readable input_ids"
            if baked is None
            else f"the manifest's prompt is not the {fixture} fixture ({len(ids)} ids)"
        ),
    }
    log.warning(
        "convert: removing %s (%s: baked fixture %s, %s ids) to convert the %s prompt again",
        out_dir,
        removed["reason"],
        removed["baked_fixture"] or "none",
        removed["baked_n_prompt"],
        fixture,
    )
    try:
        shutil.rmtree(out_dir)
    except OSError as exc:
        raise core.ProbeError(
            "conversion_prompt_mismatch",
            f"{out_dir} carries a prompt that is not the {fixture} fixture and could not be "
            f"removed to convert again: {type(exc).__name__}: {exc}",
            removed,
        ) from exc
    return removed


@stage
def stage_convert() -> dict[str, Any]:
    snapshot = model_snapshot()
    fixture = core.active_prompt_fixture()
    ids = core.race_prompt_ids(fixture=fixture)
    out_dir = converted_dir()
    facts: dict[str, Any] = {
        "repo": cfg.MODEL_REPO,
        "revision": cfg.MODEL_REVISION,
        "snapshot": str(snapshot),
        "out_dir": str(out_dir),
        "weights_dtype": cfg.WEIGHTS_DTYPE,
        "backend": cfg.KERNEL_BACKEND,
        "prompt_fixture": fixture,
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "prompt_cycle_ids": list(cfg.PROMPT_CYCLE_IDS),
        "decoded_prompt_cycle": safe_decode(snapshot, list(cfg.PROMPT_CYCLE_IDS)),
        "decoded_prompt_tail": safe_decode(snapshot, ids[-12:]),
    }
    facts["stale_checkpoint_removed"] = None
    if converted_present(out_dir) and converted_prompt_ids(out_dir) != ids:
        facts["stale_checkpoint_removed"] = remove_stale_checkpoint(
            out_dir, fixture=fixture, ids=ids
        )
    if converted_present(out_dir):
        facts.update(reused=True, wall_s=None)
    else:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        free = disk_free_bytes(out_dir.parent)
        facts["disk_free_before_bytes"] = free
        if free < MIN_FREE_BYTES_FOR_CONVERSION:
            raise core.ProbeError(
                "disk_insufficient",
                f"{free / 1024**3:.1f} GiB free; the f64 blob needs about 4.8 GiB plus headroom",
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
    manifest = read_converted_manifest(out_dir)
    tensors = manifest.get("tensors")
    facts["n_tensors"] = len(tensors) if isinstance(tensors, list | dict) else None
    config = manifest.get("config")
    facts["manifest_config"] = config if isinstance(config, dict) else None
    facts["manifest_prompt_ids_match"] = converted_prompt_ids(out_dir) == ids
    if not facts["manifest_prompt_ids_match"]:
        # a stale checkpoint was replaced above; a manifest that still does not carry the run's
        # prompt was written by this conversion, and every lane would read its prompt from it
        raise core.ProbeError(
            "conversion_incomplete",
            f"{out_dir} was converted for the {fixture} fixture but its manifest's input_ids "
            "are not that prompt",
        )
    facts["max_rss_mib"] = max_rss_mib()
    return facts


# ---------------------------------------------------------------------------
# Runs: the shared cell loop (warm-up excluded, median of RUNS)
# ---------------------------------------------------------------------------


def run_cell(gen: int, one_run: Callable[[int], dict[str, Any]]) -> dict[str, Any]:
    """`WARMUP_RUNS` excluded runs, then `RUNS` timed runs, for one generation length."""
    warmups = [one_run(gen) for _ in range(cfg.WARMUP_RUNS)]
    t0 = time.perf_counter()
    timed = [one_run(gen) for _ in range(cfg.RUNS)]
    return {
        "gen": gen,
        "warmup": warmups[-1] if warmups else None,
        "warmup_excluded": True,
        "timed": timed,
        "timed_wall_s": round(time.perf_counter() - t0, 2),
        "summary": core.run_summary(timed),
    }


def run_cells(one_run: Callable[[int], dict[str, Any]]) -> dict[str, Any]:
    """The gen=64 cell, then the gen=256 cell when the gen=64 cell finished inside the budget."""
    t0 = time.perf_counter()
    cells: dict[str, Any] = {str(cfg.GEN_TOKENS): run_cell(cfg.GEN_TOKENS, one_run)}
    elapsed = time.perf_counter() - t0
    skipped = None
    if elapsed <= cfg.LONG_GEN_BUDGET_S:
        cells[str(cfg.GEN_TOKENS_LONG)] = run_cell(cfg.GEN_TOKENS_LONG, one_run)
    else:
        cells[str(cfg.GEN_TOKENS_LONG)] = None
        skipped = (
            f"gen={cfg.GEN_TOKENS} took {elapsed:.0f} s, over the {cfg.LONG_GEN_BUDGET_S:.0f} s "
            "budget for a second cell"
        )
    return {"runs": cells, "long_gen_skipped": skipped}


def cell_headline(cells: Mapping[str, Any]) -> dict[str, Any]:
    """The lane's top-level figures from its gen=64 summary."""
    summary = (cells.get(str(cfg.GEN_TOKENS)) or {}).get("summary") or {}
    return {
        "tokens": list(summary.get("tokens") or []),
        "runs_agree": summary.get("runs_agree"),
        "decode_tok_per_s": summary.get("decode_tok_per_s"),
        "prefill_tok_per_s": summary.get("prefill_tok_per_s"),
        "ttft_ms": summary.get("ttft_ms"),
        "vram_peak_bytes": summary.get("vram_peak_bytes"),
    }


# ---------------------------------------------------------------------------
# Lane A: the shipped engine
# ---------------------------------------------------------------------------


def engine_facts() -> dict[str, Any]:
    """Locate the engine as `algenta serve` does and read the signed manifest beside it."""
    try:
        from algenta.serve.engine import resolve_engine
    except Exception as exc:  # noqa: BLE001 - an older algenta without the serve module
        raise core.ProbeError(
            "engine_resolver_missing", f"algenta.serve.engine did not import: {exc}"
        ) from exc
    resolution = resolve_engine("cuda")
    if resolution.path is None:
        raise core.ProbeError(
            "engine_binary_missing",
            f"no {cfg.ENGINE_NAME} was found; searched: " + "; ".join(resolution.searched)[:400],
            {"searched": list(resolution.searched)},
        )
    path = Path(resolution.path)
    directory = path.parent
    protocol = core.engine_protocol_of(path.name)
    if protocol is None:
        raise core.ProbeError(
            "engine_protocol_unknown",
            f"{path.name} is not an engine lane A can drive; known: "
            + ", ".join(cfg.ENGINE_PROTOCOLS),
        )
    is_p3 = protocol == cfg.P3_ENGINE_NAME
    facts: dict[str, Any] = {
        "name": path.name,
        "protocol": protocol,
        "path": str(path),
        "dir": str(directory),
        "resolved_from": resolution.source,
        "searched": list(resolution.searched),
        "wheel_version": package_versions((cfg.ENGINE_WHEEL,))[cfg.ENGINE_WHEEL],
        "size_bytes": path.stat().st_size,
        "sha256": sha256_of(path),
        "libcudart_beside": all(
            (directory / name).is_file() for name in cfg.ENGINE_BUNDLED_LIBRARIES
        ),
        "manifest": None,
        "cuda_target": os.environ.get("PROBE_ENGINE_CUDA_TARGET", "").strip() or None,
        "comptime_defines": [],
        # the wheel's engine links cuBLAS through the tensor-core shim; the packed-int8 graph
        # driver links no CUDA library beyond the driver its manifest names
        "host_shared_libraries": [] if is_p3 else list(cfg.ENGINE_HOST_LIBRARIES),
        "bundled_shared_libraries": [],
        "bundled_beside": None,
        "sha256_declared": None,
        "sha256_matches": None,
        "source": None,
        "source_commit": None,
        "built_utc": None,
        "mojo_version": None,
        "session": None,
        "build_variant": None,
    }
    manifest_path = directory / cfg.ENGINE_MANIFEST
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise core.ProbeError("engine_manifest_invalid", f"{manifest_path}: {exc}") from exc
        engine = manifest.get("engine") if isinstance(manifest, dict) else None
        if isinstance(engine, dict) and engine.get("name") == path.name:
            toolchain = engine.get("toolchain") if isinstance(engine.get("toolchain"), dict) else {}
            bundled = [str(n) for n in engine.get("bundled_shared_libraries") or []]
            facts.update(
                manifest=str(manifest_path),
                build_variant=manifest.get("build_variant"),
                cuda_target=engine.get("cuda_target") or facts["cuda_target"],
                comptime_defines=list(engine.get("comptime_defines") or []),
                host_shared_libraries=list(
                    engine.get("host_shared_libraries")
                    or ([] if is_p3 else cfg.ENGINE_HOST_LIBRARIES)
                ),
                bundled_shared_libraries=bundled,
                bundled_beside=all((directory / name).is_file() for name in bundled),
                sha256_declared=engine.get("sha256"),
                source=engine.get("source"),
                source_commit=engine.get("source_commit"),
                built_utc=engine.get("built_utc"),
                mojo_version=toolchain.get("mojo") or engine.get("mojo_version"),
                session=engine.get("session"),
            )
            facts["sha256_matches"] = facts["sha256"] == engine.get("sha256")
            if facts["sha256_matches"] is False:
                raise core.ProbeError(
                    "engine_sha_mismatch",
                    f"{path.name} hashes to {facts['sha256'][:12]}, the manifest declares "
                    f"{str(engine.get('sha256'))[:12]}",
                )
            if facts["bundled_beside"] is False:
                missing = [n for n in bundled if not (directory / n).is_file()]
                raise core.ProbeError(
                    "engine_closure_incomplete",
                    f"{path.name}'s manifest bundles {', '.join(missing)}, not beside it",
                )
    return facts


def host_library_facts(names: list[str]) -> dict[str, str | None]:
    """Each host library the engine links, loadable through the dynamic linker or not."""
    found: dict[str, str | None] = {}
    missing: list[str] = []
    for name in names:
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            found[name] = None
            missing.append(name)
            continue
        found[name] = getattr(lib, "_name", name)
    if missing:
        raise core.ProbeError(
            "engine_host_library_missing",
            f"the engine links {', '.join(missing)}, not loadable on this host",
        )
    return found


def engine_env(engine_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{engine_dir}:{existing}" if existing else str(engine_dir)
    return env


def run_engine_once(
    engine: Path, checkpoint: Path, gen: int, env: Mapping[str, str]
) -> dict[str, Any]:
    argv = [
        str(engine),
        str(checkpoint),
        "--max-new",
        str(gen),
        "--prompt-len",
        str(cfg.PROMPT_TOKENS),
    ]
    sampler = GpuMemorySampler().start()
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv built from constants and paths
            argv,
            capture_output=True,
            text=True,
            timeout=ENGINE_RUN_TIMEOUT_S,
            check=False,
            env=dict(env),
            cwd=str(checkpoint.parent),
        )
    except subprocess.TimeoutExpired as exc:
        sampler.stop()
        raise core.ProbeError(
            "engine_run_timeout", f"the engine ran past {ENGINE_RUN_TIMEOUT_S:.0f} s"
        ) from exc
    except OSError as exc:
        sampler.stop()
        raise core.ProbeError("engine_run_failed", f"{type(exc).__name__}: {exc}") from exc
    wall = time.perf_counter() - t0
    memory = sampler.stop()
    parsed = core.parse_engine_output(proc.stdout, proc.stderr, proc.returncode)
    if parsed["n_prompt"] != cfg.PROMPT_TOKENS:
        raise core.ProbeError(
            "engine_prompt_mismatch",
            f"the engine prefilled {parsed['n_prompt']} tokens, {cfg.PROMPT_TOKENS} were asked",
        )
    return {
        "gen": gen,
        **parsed,
        "stopped_on_eos": len(parsed["tokens"]) < gen,
        "wall_s": round(wall, 2),
        "vram_peak_bytes": memory["peak_delta_bytes"],
        "vram_samples": memory["samples"],
        "argv": argv,
    }


def checkpoint_fixture_gate(checkpoint: Path, protocol: str) -> dict[str, Any]:
    """The converted checkpoint carries the prompt every lane uses (its manifest's `input_ids`);
    the packed-int8 graph driver reads that prompt and checks its continuation against an oracle
    bound to the campaign fixture, so with that driver the converted prompt must be the campaign
    fixture, else `engine_prompt_fixture_mismatch` before launch (a G0 failure would otherwise
    read as a wrong engine). Any engine is refused when the manifest's prompt is not the run's
    active fixture."""
    fixture = core.active_prompt_fixture()
    baked = read_converted_manifest(checkpoint).get("input_ids")
    baked_ids = [int(t) for t in baked] if isinstance(baked, list) else None
    expected = core.race_prompt_ids(fixture=fixture)
    facts = {
        "active_fixture": fixture,
        "manifest_prompt_ids_match": baked_ids == expected,
        "n_prompt_baked": None if baked_ids is None else len(baked_ids),
    }
    if baked_ids != expected:
        raise core.ProbeError(
            "engine_prompt_fixture_mismatch",
            f"the converted checkpoint's prompt is not the {fixture} fixture the run selected",
            facts,
        )
    if protocol == cfg.P3_ENGINE_NAME and fixture != "campaign":
        raise core.ProbeError(
            "engine_prompt_fixture_mismatch",
            f"{cfg.P3_ENGINE_NAME}'s oracle is bound to the campaign fixture; this run "
            f"converted the {fixture} prompt (set {cfg.PROMPT_FIXTURE_ENV}=campaign or unset it)",
            facts,
        )
    return facts


def run_p3_engine_once(engine: Path, checkpoint: Path, env: Mapping[str, str]) -> dict[str, Any]:
    """One launch of the packed-int8 graph driver: `<checkpoint> --runs N`. The driver runs its
    gates, then every throughput cell (gen=64 and gen=256, three arms, one untimed warm-up and
    N timed runs each) inside this one process, and prints medians, so lane A launches it once
    and reads the table; nvidia-smi samples the whole launch for the peak."""
    argv = [str(engine), str(checkpoint), "--runs", str(cfg.RUNS)]
    sampler = GpuMemorySampler().start()
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv built from constants and paths
            argv,
            capture_output=True,
            text=True,
            timeout=cfg.P3_ENGINE_RUN_TIMEOUT_S,
            check=False,
            env=dict(env),
            cwd=str(checkpoint.parent),
        )
    except subprocess.TimeoutExpired as exc:
        sampler.stop()
        raise core.ProbeError(
            "engine_run_timeout", f"the driver ran past {cfg.P3_ENGINE_RUN_TIMEOUT_S:.0f} s"
        ) from exc
    except OSError as exc:
        sampler.stop()
        raise core.ProbeError("engine_run_failed", f"{type(exc).__name__}: {exc}") from exc
    wall = time.perf_counter() - t0
    memory = sampler.stop()
    parsed = core.parse_p3_engine_output(proc.stdout, proc.stderr, proc.returncode)
    if parsed["n_prompt"] != cfg.PROMPT_TOKENS:
        raise core.ProbeError(
            "engine_prompt_mismatch",
            f"the driver prefilled {parsed['n_prompt']} tokens, {cfg.PROMPT_TOKENS} were asked",
        )
    return {
        **parsed,
        "wall_s": round(wall, 2),
        "vram_peak_bytes": memory["peak_delta_bytes"],
        "vram_samples": memory["samples"],
        "argv": argv,
    }


def p3_engine_block(
    launch: Mapping[str, Any], *, snapshot: Path, ids: list[int], fixture: str
) -> dict[str, Any]:
    """The engine stage's record for the packed-int8 graph driver, in the shape lane A already
    reports (cells under `runs`, the headline from the gen=64 cell) plus what only this driver
    says: its gates, the other two arms, the load, the captured node count, the kernel set."""
    cells = core.p3_cells(launch, vram_peak_bytes=launch.get("vram_peak_bytes"))
    headline = cell_headline(cells)
    return {
        "protocol": cfg.P3_ENGINE_NAME,
        "prompt_fixture": fixture,
        "argv": list(launch["argv"]),
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "runs": cells,
        "long_gen_skipped": None,
        "gen_lengths": list(cfg.P3_GEN_LENGTHS),
        "tokens_verified": cfg.P3_ORACLE_TOKENS,
        "gates": dict(launch["gates"]),
        "g2_steps": list(launch["g2_steps"]),
        "load_ms": launch["load_ms"],
        "graph_nodes": launch["graph_nodes"],
        "dispatch_budget": launch["dispatch_budget"],
        "kernel_variant": launch["kernel_variant"],
        "device": launch["device"],
        "model": dict(launch["model"]),
        "runs_per_cell": launch["runs"],
        "warmup_per_cell": launch["warmup"],
        "done": launch["done"],
        "wall_s": launch["wall_s"],
        "vram_samples": launch["vram_samples"],
        "stdout_tail": launch["stdout_tail"],
        **headline,
        "decoded": safe_decode(snapshot, headline["tokens"]),
    }


@stage
def stage_engine() -> dict[str, Any]:
    cc = list(core.compute_capability_gate(libcuda_facts()["compute_capability"]))
    checkpoint = converted_dir()
    if not converted_present(checkpoint):
        raise core.ProbeError("checkpoint_missing", f"{checkpoint} holds no converted checkpoint")
    facts = engine_facts()
    gate_env = os.environ.get("PROBE_ENGINE_TARGET_GATE", "").strip().lower()
    if gate_env in ("off", "0", "false", "no"):
        target_gate = {
            "checked": False,
            "ok": None,
            "cuda_target": facts["cuda_target"],
            "device_compute_capability": cc,
            "note": "gate switched off by PROBE_ENGINE_TARGET_GATE; the run decides",
        }
    else:
        target_gate = core.engine_target_gate(facts["cuda_target"], cc)
    fixture_gate = checkpoint_fixture_gate(checkpoint, facts["protocol"])
    host_libraries = host_library_facts(list(facts["host_shared_libraries"]))
    engine = Path(facts["path"])
    env = engine_env(engine.parent)
    snapshot = model_snapshot()
    ids = core.race_prompt_ids()
    common = {
        "engine": facts,
        "target_gate": target_gate,
        "fixture_gate": fixture_gate,
        "host_libraries": host_libraries,
        "ld_library_path": env["LD_LIBRARY_PATH"],
        "checkpoint_dir": str(checkpoint),
    }
    if facts["protocol"] == cfg.P3_ENGINE_NAME:
        launch = run_p3_engine_once(engine, checkpoint, env)
        block = p3_engine_block(
            launch, snapshot=snapshot, ids=ids, fixture=fixture_gate["active_fixture"]
        )
        return {**common, **block, "max_rss_mib": max_rss_mib()}

    def one_run(gen: int) -> dict[str, Any]:
        return run_engine_once(engine, checkpoint, gen, env)

    cells = run_cells(one_run)
    headline = cell_headline(cells["runs"])
    return {
        **common,
        "protocol": cfg.ENGINE_NAME,
        "prompt_fixture": fixture_gate["active_fixture"],
        "argv": [
            str(engine),
            str(checkpoint),
            "--max-new",
            str(cfg.GEN_TOKENS),
            "--prompt-len",
            str(cfg.PROMPT_TOKENS),
        ],
        "prompt_ids": ids,
        "n_prompt": len(ids),
        **cells,
        **headline,
        "decoded": safe_decode(snapshot, headline["tokens"]),
        "max_rss_mib": max_rss_mib(),
    }


# ---------------------------------------------------------------------------
# Lane B: llama.cpp
# ---------------------------------------------------------------------------


def gguf_path() -> Path:
    recorded = ((read_build_facts().get("llama") or {}).get("gguf") or {}).get("path")
    if recorded and Path(recorded).is_file():
        return Path(recorded)
    return assets_dir() / cfg.GGUF_FILENAME


def llama_version(server: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv
            [str(server), "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise core.ProbeError("llama_server_failed", f"--version did not run: {exc}") from exc
    facts = core.parse_llama_version(f"{proc.stdout}\n{proc.stderr}")
    facts["returncode"] = proc.returncode
    return facts


def http_json(url: str, payload: Mapping[str, Any] | None, timeout_s: float) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - loopback only
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def wait_llama_ready(base_url: str, proc: subprocess.Popen[str], timeout_s: float) -> float:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        if proc.poll() is not None:
            raise core.ProbeError(
                "llama_server_failed", f"llama-server exited with status {proc.returncode} at start"
            )
        try:
            body = http_json(f"{base_url}/health", None, 5.0)
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(0.5)
            continue
        if str(body.get("status", "")).lower() == "ok":
            return round(time.perf_counter() - t0, 2)
        time.sleep(0.5)
    raise core.ProbeError(
        "llama_server_failed", f"llama-server did not answer /health ok within {timeout_s:.0f} s"
    )


def llama_completion(base_url: str, ids: list[int], gen: int) -> dict[str, Any]:
    payload = {
        "prompt": ids,
        "n_predict": gen,
        "temperature": 0,
        "top_k": 1,
        "samplers": ["top_k"],
        "cache_prompt": False,
        "return_tokens": True,
        "n_probs": 0,
        "stream": False,
    }
    t0 = time.perf_counter()
    try:
        body = http_json(f"{base_url}/completion", payload, LLAMA_REQUEST_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200] if exc.fp else ""
        raise core.ProbeError(
            "llama_request_failed", f"/completion HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise core.ProbeError("llama_request_failed", f"/completion: {exc}") from exc
    run = core.llama_run_from_completion(body, expected_n_prompt=len(ids), gen=gen)
    run["wall_s"] = round(time.perf_counter() - t0, 2)
    return run


@stage
def stage_llama() -> dict[str, Any]:
    server = Path(cfg.LLAMA_SERVER)
    if not server.is_file() or not os.access(server, os.X_OK):
        raise core.ProbeError("llama_build_missing", f"{server} is not in the image")
    gguf = gguf_path()
    if not gguf.is_file():
        raise core.ProbeError("llama_gguf_missing", f"{gguf} was not converted at build")
    build_llama = read_build_facts().get("llama") or {}
    version = llama_version(server)
    if version.get("commit") and not cfg.LLAMA_CPP_COMMIT.startswith(version["commit"]):
        raise core.ProbeError(
            "llama_commit_mismatch",
            f"llama-server reports {version['commit']}, the pin is {cfg.LLAMA_CPP_COMMIT[:10]}",
        )
    snapshot = model_snapshot()
    ids = core.race_prompt_ids()
    base_url = f"http://127.0.0.1:{cfg.LLAMA_PORT}"
    argv = [
        str(server),
        "-m",
        str(gguf),
        "--host",
        "127.0.0.1",
        "--port",
        str(cfg.LLAMA_PORT),
        "-ngl",
        str(cfg.LLAMA_GPU_LAYERS),
        "--parallel",
        str(cfg.LLAMA_PARALLEL),
        "-c",
        str(cfg.LLAMA_CTX),
    ]
    logs = work_dir() / "llama-server.log"
    logs.parent.mkdir(parents=True, exist_ok=True)
    sampler = GpuMemorySampler().start()
    with logs.open("w", encoding="utf-8") as handle:
        try:
            proc = subprocess.Popen(  # noqa: S603 - fixed argv
                argv, stdout=handle, stderr=subprocess.STDOUT, text=True
            )
        except OSError as exc:
            sampler.stop()
            raise core.ProbeError("llama_server_failed", f"{type(exc).__name__}: {exc}") from exc
        try:
            ready_s = wait_llama_ready(base_url, proc, cfg.LLAMA_READY_TIMEOUT_S)

            def one_run(gen: int) -> dict[str, Any]:
                return llama_completion(base_url, ids, gen)

            cells = run_cells(one_run)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    memory = sampler.stop()
    headline = cell_headline(cells["runs"])
    try:
        tail = core.log_tail(logs.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        tail = []
    return {
        "server": str(server),
        "argv": argv,
        "version": version,
        "commit_pinned": cfg.LLAMA_CPP_COMMIT,
        "build_tag": cfg.LLAMA_CPP_TAG,
        "cuda_architectures": build_llama.get("cuda_architectures") or cfg.LLAMA_CUDA_ARCHITECTURES,
        "gguf": {
            "path": str(gguf),
            "bytes": gguf.stat().st_size,
            "outtype": build_llama.get("gguf", {}).get("outtype") or cfg.LLAMA_GGUF_OUTTYPE,
            "convert_wall_s": build_llama.get("gguf", {}).get("convert_wall_s"),
        },
        "ready_s": ready_s,
        "prompt_ids": ids,
        "n_prompt": len(ids),
        **cells,
        **headline,
        "vram_peak_bytes": memory["peak_delta_bytes"],
        "vram_baseline_bytes": memory["baseline_bytes"],
        "decoded": safe_decode(snapshot, headline["tokens"]),
        "log_tail": tail,
        "max_rss_mib": max_rss_mib(),
    }


# ---------------------------------------------------------------------------
# Lane C: the Hub kernels' DecodeSession
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


def hub_session_run(
    session_cls: type, checkpoint: Path, ids: list[int], gen: int
) -> dict[str, Any]:
    """One `DecodeSession`: open (upload and prefill), `gen` steps, close; every step timed."""
    import torch

    free_start = int(torch.cuda.mem_get_info(0)[0]) if torch.cuda.is_available() else None
    tokens: list[int] = []
    positions: list[int | None] = []
    step_ms: list[float] = []
    stopped_on_eos = False
    t0 = time.perf_counter()
    try:
        session = session_cls(str(checkpoint), ids, max_new_tokens=gen)
    except Exception as exc:  # noqa: BLE001 - KernelError carries its code
        raise core.public_error(exc) from exc
    open_s = time.perf_counter() - t0
    try:
        free_after_open = int(torch.cuda.mem_get_info(0)[0]) if torch.cuda.is_available() else None
        for _ in range(gen):
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
    timings = core.step_timings(step_ms)
    taken = None
    if isinstance(free_start, int) and isinstance(free_after_open, int):
        taken = max(0, free_start - free_after_open)
    return {
        "gen": gen,
        "tokens": tokens,
        "positions": positions,
        "step_ms": [round(ms, 2) for ms in step_ms],
        "open_s": round(open_s, 2),
        "session_n_prompt": getattr(session, "n_prompt", None),
        "stopped_on_eos": stopped_on_eos,
        "decode_tok_per_s": timings["decode_tok_per_s"],
        "prefill_tok_per_s": None,
        "ttft_ms": round(open_s * 1000.0 + (step_ms[0] if step_ms else 0.0), 1),
        "wall_s": round(time.perf_counter() - t0, 2),
        "gpu_free_bytes_start": free_start,
        "gpu_free_bytes_after_open": free_after_open,
        "gpu_free_bytes_after_close": free_after_close,
        "device_taken_bytes": taken,
        "vram_peak_bytes": taken,
    }


@stage
def stage_decode() -> dict[str, Any]:
    cc = list(core.compute_capability_gate(libcuda_facts()["compute_capability"]))
    kernel, manifest, kernel_facts = load_kernel()
    native_facts = load_native(kernel, manifest, cc)
    checkpoint = converted_dir()
    if not converted_present(checkpoint):
        raise core.ProbeError("checkpoint_missing", f"{checkpoint} holds no converted checkpoint")
    snapshot = model_snapshot()
    ids = core.race_prompt_ids()
    session_cls = decode_session_class(kernel)

    def one_run(gen: int) -> dict[str, Any]:
        return hub_session_run(session_cls, checkpoint, ids, gen)

    cell = run_cell(cfg.GEN_TOKENS, one_run)
    summary = cell["summary"]
    median_run = min(
        cell["timed"],
        key=lambda r: abs(
            float(r.get("decode_tok_per_s") or 0.0) - float(summary["decode_tok_per_s"] or 0.0)
        ),
    )
    return {
        **kernel_facts,
        **native_facts,
        "compute_capability": cc,
        "checkpoint_dir": str(checkpoint),
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "max_new_tokens": cfg.GEN_TOKENS,
        "runs": {str(cfg.GEN_TOKENS): cell, str(cfg.GEN_TOKENS_LONG): None},
        "long_gen_skipped": "the Hub lane runs the gen=64 cell only",
        # the median run's own figures, under the names earlier records used
        "open_s": median_run["open_s"],
        "step_ms": median_run["step_ms"],
        "tokens": summary["tokens"],
        "positions": median_run["positions"],
        "stopped_on_eos": median_run["stopped_on_eos"],
        "session_n_prompt": median_run["session_n_prompt"],
        "gpu_free_bytes_start": median_run["gpu_free_bytes_start"],
        "gpu_free_bytes_after_open": median_run["gpu_free_bytes_after_open"],
        "gpu_free_bytes_after_close": median_run["gpu_free_bytes_after_close"],
        "device_taken_bytes": summary["vram_peak_bytes"],
        "runs_agree": summary["runs_agree"],
        "decode_tok_per_s": summary["decode_tok_per_s"],
        "prefill_tok_per_s": None,
        "ttft_ms": summary["ttft_ms"],
        "decoded": safe_decode(snapshot, summary["tokens"]),
        "max_rss_mib": max_rss_mib(),
    }


# ---------------------------------------------------------------------------
# Lane D: the same decode without Algenta, transformers on the same GPU
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


def timed_generate(model: Any, prompt: Any, n_prompt: int, gen: int) -> dict[str, Any]:
    """One greedy `generate` of `gen` tokens on the device, every token timestamped."""
    import torch

    clock = StepClock()
    torch.cuda.synchronize()
    clock.start()
    out = model.generate(
        prompt,
        max_new_tokens=gen,
        do_sample=False,
        num_beams=1,
        streamer=clock,
    )
    torch.cuda.synchronize()
    generate_s = time.perf_counter() - clock.t0
    sequences = getattr(out, "sequences", out)
    tokens = [int(t) for t in sequences[0, n_prompt:].tolist()]
    streamed, step_ms = clock.token_times()
    if tokens != streamed or not clock.prompt_echoed(n_prompt):
        raise core.ProbeError(
            "baseline_step_count_mismatch",
            f"the streamer saw {streamed[:8]}... for {tokens[:8]}...; the per-step times "
            "cannot be attributed",
        )
    timings = core.step_timings(step_ms)
    ttft_ms = step_ms[0] if step_ms else None
    return {
        "gen": gen,
        "tokens": tokens,
        "step_ms": [round(ms, 3) for ms in step_ms],
        "ttft_s": round(step_ms[0] / 1000.0, 3) if step_ms else None,
        "ttft_ms": None if ttft_ms is None else round(ttft_ms, 3),
        "prefill_tok_per_s": (
            round(n_prompt / (ttft_ms / 1000.0), 2) if ttft_ms and n_prompt else None
        ),
        "decode_tok_per_s": timings["decode_tok_per_s"],
        "generate_s": round(generate_s, 3),
        "stopped_on_eos": len(tokens) < gen,
    }


def _lane_failure(lane: dict[str, Any], code: str, exc: BaseException) -> dict[str, Any]:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    log.error("baseline lane %s: %s — %s", lane.get("dtype"), code, text[:300])
    return {**lane, "ok": False, "code": code, "message": f"{type(exc).__name__}: {text[:300]}"}


def baseline_lane(dtype_name: str, snapshot: Path, ids: list[int]) -> dict[str, Any]:
    """One lane: load the model in `dtype_name` onto the device, one warm-up generate
    (excluded), `RUNS` timed generates; the device is emptied before returning. Fails closed
    with `baseline_oom`, `baseline_load_failed`, `baseline_generate_failed` or
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

        def one_run(gen: int) -> dict[str, Any]:
            with torch.no_grad():
                return timed_generate(model, prompt, len(ids), gen)

        try:
            cell = run_cell(cfg.GEN_TOKENS, one_run)
        except torch.cuda.OutOfMemoryError as exc:
            return _lane_failure(lane, "baseline_oom", exc)
        except core.ProbeError as exc:
            return _lane_failure(lane, exc.code, exc)
        except Exception as exc:  # noqa: BLE001
            return _lane_failure(lane, "baseline_generate_failed", exc)
        lane["peak_allocated_bytes"] = int(torch.cuda.max_memory_allocated(device))
        lane["peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved(device))
        summary = cell["summary"]
        median_run = min(
            cell["timed"],
            key=lambda r: abs(
                float(r.get("decode_tok_per_s") or 0.0) - float(summary["decode_tok_per_s"] or 0.0)
            ),
        )
        warm = cell["warmup"] or {}
        lane.update(
            ok=True,
            runs={str(cfg.GEN_TOKENS): cell, str(cfg.GEN_TOKENS_LONG): None},
            warmup={
                "excluded": True,
                "tokens": warm.get("tokens"),
                "step_ms": warm.get("step_ms"),
                "ttft_s": warm.get("ttft_s"),
                "generate_s": warm.get("generate_s"),
            },
            tokens=summary["tokens"],
            step_ms=median_run["step_ms"],
            ttft_s=median_run["ttft_s"],
            ttft_ms=summary["ttft_ms"],
            generate_s=median_run["generate_s"],
            decode_tok_per_s=summary["decode_tok_per_s"],
            prefill_tok_per_s=summary["prefill_tok_per_s"],
            runs_agree=summary["runs_agree"],
            same_tokens_as_warmup=summary["tokens"] == warm.get("tokens"),
            stopped_on_eos=median_run["stopped_on_eos"],
            decoded=safe_decode(snapshot, summary["tokens"]),
        )
        return lane
    finally:
        model = None  # noqa: F841 - drops the last reference so the device memory is freed
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
    ids = core.race_prompt_ids()
    free_start, total = (int(v) for v in torch.cuda.mem_get_info(0))
    lanes: dict[str, dict[str, Any]] = {}
    for name in cfg.BASELINE_DTYPES:
        lanes[name] = baseline_lane(name, snapshot, ids)
    return {
        "method": (
            f"transformers generate on CUDA, greedy, max_new_tokens {cfg.GEN_TOKENS}; one "
            f"warm-up generate excluded, then {cfg.RUNS} timed generates (median); per-step "
            "times are the gaps between consecutive tokens reaching the host through the "
            "generate streamer"
        ),
        "device_name": torch.cuda.get_device_name(0),
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "transformers": transformers.__version__,
        "snapshot": str(snapshot),
        "prompt_ids": ids,
        "n_prompt": len(ids),
        "max_new_tokens": cfg.GEN_TOKENS,
        "runs_per_lane": cfg.RUNS,
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
    ids = core.race_prompt_ids()
    hf_tokenizer = AutoTokenizer.from_pretrained(str(snapshot))
    cycle_text = hf_tokenizer.decode(list(cfg.PROMPT_CYCLE_IDS))
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
            max_new_tokens=cfg.GEN_TOKENS,
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
        "n_prompt": len(ids),
        "prompt_cycle_text": cycle_text,
        "max_new_tokens": cfg.GEN_TOKENS,
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
