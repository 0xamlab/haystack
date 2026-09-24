"""Image build: bake the kernel, the model, the engine facts and the GGUF; prove the boot needs
no Hub.

    python fetch_assets.py --bake                      # network: kernel + model; GGUF converted
    HF_HUB_OFFLINE=1 python fetch_assets.py --verify   # no network: everything resolves locally

`--bake` installs `thyn-ai/algenta-llm` at the pinned revision for the cuda backend
(`kernels.install_kernel`; no GPU is needed to download a variant), refuses the image when the
snapshot is not the pinned sha, the variant is not the torch29/cu128 one or the native manifest
does not declare the 6144 staging tier, prunes the repository's cached tree listing (kernels
0.17.1 would otherwise refuse the variant-only cache offline, see the flagship's
`boot_sequence.prune_tree_listings`), downloads the pinned Qwen3-0.6B-Base snapshot, reads the
installed `algenta-runtime-native` wheel's signed manifest for its bundled `conform_generate_cuda`
(path, sha256, compile target, comptime defines; the target is judged against the requested
hardware and the verdict recorded, the lane fails closed at run time with the same code),
converts the snapshot to the F16 GGUF with the pinned llama.cpp's `convert_hf_to_gguf.py`
(timed), records `llama-server --version`, and writes `build_facts.json` where `probe.py` reads
it.

`--verify` runs with `HF_HUB_OFFLINE=1`: the model resolves from the cache alone, the kernel
snapshot and its pruned listing are in place, `algenta`'s tokenizer imports on this interpreter
and decodes the race prompt's cycle, the engine binary is where the bake found it with the
same sha256, the GGUF is on disk with the recorded size, and `kernels.get_kernel` imports the
cuda package from the cache with the architecture check off (the build host has no GPU; a
refusal that names the missing device is recorded and tolerated, any other refusal fails the
build). Its findings join `build_facts.json` under `verify`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import hf_ua_shim
import probe
import probe_config as cfg
import probe_core as core

log = logging.getLogger("gpu_probe.build")

GPU_ABSENT_MARKERS = ("gpu_unavailable", "libcuda", "cuinit", "cuda device", "compute capability")
CONVERT_TIMEOUT_S = 1800.0


def hub_cache_dir() -> Path:
    configured = os.environ.get("KERNELS_CACHE", "").strip()
    if configured:
        return Path(configured)
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def repo_folder(repo_id: str) -> str:
    return "kernels--" + repo_id.replace("/", "--")


def prune_tree_listings(repo_id: str = cfg.KERNEL_REPO) -> list[str]:
    trees = hub_cache_dir() / repo_folder(repo_id) / "trees"
    removed: list[str] = []
    if trees.is_dir():
        for listing in sorted(trees.glob("*.json")):
            listing.unlink()
            removed.append(listing.name)
    return removed


def native_manifest_under(variant_path: Path) -> tuple[Path, dict[str, Any]]:
    candidates = sorted(variant_path.glob("*/_native/manifest.json"))
    if len(candidates) != 1:
        raise core.ProbeError(
            "kernel_manifest_missing",
            f"expected one */_native/manifest.json under {variant_path}, found {len(candidates)}",
        )
    return candidates[0], probe.read_native_manifest(candidates[0].parent)


def bake_kernel() -> dict[str, Any]:
    from kernels import install_kernel

    t0 = time.perf_counter()
    variant_path = Path(
        install_kernel(
            cfg.KERNEL_REPO,
            revision=cfg.KERNEL_REVISION,
            backend=cfg.KERNEL_BACKEND,
            trust_remote_code=[cfg.KERNEL_REPO],
        )
    )
    install_s = time.perf_counter() - t0
    revision = core.revision_gate(variant_path)
    variant = core.variant_gate(variant_path)
    manifest_path, manifest = native_manifest_under(variant_path)
    tier = core.tier_gate(manifest)
    files = manifest.get("files") or {}
    native_bytes = sum(
        (manifest_path.parent / name).stat().st_size
        for name in files
        if (manifest_path.parent / name).is_file()
    )
    pruned = prune_tree_listings()
    log.info(
        "%s @ %s: %s, tier %s, %d native files (%.1f MB) in %.1f s; %d tree listing(s) pruned",
        cfg.KERNEL_REPO,
        revision[:12],
        variant,
        tier,
        len(files),
        native_bytes / 1e6,
        install_s,
        len(pruned),
    )
    return {
        "repo": cfg.KERNEL_REPO,
        "revision": revision,
        "variant": variant,
        "expected_variant": cfg.EXPECTED_VARIANT,
        "backend": cfg.KERNEL_BACKEND,
        "path": str(variant_path),
        "native_manifest": str(manifest_path),
        "install_s": round(install_s, 2),
        "resident_stage_tier": tier,
        "cuda_targets": core.cuda_targets_of(manifest),
        "cuda_libraries": dict(manifest.get("cuda_libraries") or {}),
        "primary_library": manifest.get("library"),
        "load_order": list(manifest.get("load_order") or []),
        "native_bytes": native_bytes,
        "mojo_version": manifest.get("mojo_version"),
        "source_commit": manifest.get("source_commit"),
        "abi_version": manifest.get("abi_version"),
        "tree_listings_pruned": pruned,
    }


def bake_model() -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    t0 = time.perf_counter()
    path = Path(snapshot_download(cfg.MODEL_REPO, revision=cfg.MODEL_REVISION))
    download_s = time.perf_counter() - t0
    if core.snapshot_sha_of(path) != cfg.MODEL_REVISION:
        raise core.ProbeError(
            "model_revision_mismatch",
            f"snapshot at {path} is not {cfg.MODEL_REVISION[:12]}",
        )
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    architectures = config.get("architectures") or []
    if cfg.MODEL_ARCHITECTURE not in architectures:
        raise core.ProbeError(
            "model_architecture_mismatch",
            f"{cfg.MODEL_REPO} declares {architectures}, expected {cfg.MODEL_ARCHITECTURE}",
        )
    files = sorted((p.name, p.stat().st_size) for p in path.iterdir() if p.is_file())
    log.info(
        "%s @ %s: %d files, %.2f GB in %.1f s",
        cfg.MODEL_REPO,
        cfg.MODEL_REVISION[:12],
        len(files),
        sum(size for _, size in files) / 1e9,
        download_s,
    )
    return {
        "repo": cfg.MODEL_REPO,
        "revision": cfg.MODEL_REVISION,
        "path": str(path),
        "download_s": round(download_s, 2),
        "files": files,
        "total_bytes": sum(size for _, size in files),
        "architectures": architectures,
        "tie_word_embeddings": config.get("tie_word_embeddings"),
        "torch_dtype": config.get("torch_dtype") or config.get("dtype"),
        "num_hidden_layers": config.get("num_hidden_layers"),
        "hidden_size": config.get("hidden_size"),
        "intermediate_size": config.get("intermediate_size"),
        "vocab_size": config.get("vocab_size"),
        "eos_token_id": config.get("eos_token_id"),
    }


def runtime_native_dir() -> Path:
    from importlib import resources

    try:
        return Path(str(resources.files(cfg.ENGINE_WHEEL.replace("-", "_"))))
    except ModuleNotFoundError as exc:
        raise core.ProbeError(
            "engine_wheel_missing", f"{cfg.ENGINE_WHEEL} is not installed: {exc}"
        ) from exc


def bake_engine() -> dict[str, Any]:
    """The bundled engine as the wheel's signed manifest declares it, plus what the requested
    hardware makes of its compile target (recorded, never a build failure: the lane fails
    closed at run time with the same code and the other lanes still run)."""
    directory = runtime_native_dir()
    engine = directory / cfg.ENGINE_NAME
    if not engine.is_file():
        raise core.ProbeError(
            "engine_binary_missing", f"{engine} is not in the installed {cfg.ENGINE_WHEEL} wheel"
        )
    manifest_path = directory / cfg.ENGINE_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise core.ProbeError("engine_manifest_invalid", f"{manifest_path}: {exc}") from exc
    block = manifest.get("engine") if isinstance(manifest, dict) else None
    if not isinstance(block, dict) or block.get("name") != cfg.ENGINE_NAME:
        raise core.ProbeError(
            "engine_manifest_invalid", f"{manifest_path} declares no engine {cfg.ENGINE_NAME}"
        )
    sha = probe.sha256_of(engine)
    if sha != block.get("sha256"):
        raise core.ProbeError(
            "engine_sha_mismatch",
            f"{engine.name} hashes to {sha[:12]}, the manifest declares "
            f"{str(block.get('sha256'))[:12]}",
        )
    wheel_version = probe.package_versions((cfg.ENGINE_WHEEL,))[cfg.ENGINE_WHEEL]
    if wheel_version != cfg.ENGINE_WHEEL_VERSION:
        raise core.ProbeError(
            "engine_wheel_version_mismatch",
            f"{cfg.ENGINE_WHEEL} {wheel_version} is installed, {cfg.ENGINE_WHEEL_VERSION} pinned",
        )
    cc = cfg.HARDWARE_COMPUTE_CAPABILITY.get(cfg.HARDWARE)
    verdict: dict[str, Any]
    if cc is None:
        verdict = {"hardware": cfg.HARDWARE, "checked": False, "note": "hardware not in the table"}
    else:
        try:
            verdict = {
                "hardware": cfg.HARDWARE,
                **core.engine_target_gate(block.get("cuda_target"), cc),
            }
        except core.ProbeError as exc:
            verdict = {"hardware": cfg.HARDWARE, "checked": True, "ok": False, **exc.as_dict()}
            log.warning("engine target on %s: %s — %s", cfg.HARDWARE, exc.code, exc.message)
    facts = {
        "name": cfg.ENGINE_NAME,
        "wheel": cfg.ENGINE_WHEEL,
        "wheel_version": wheel_version,
        "dir": str(directory),
        "path": str(engine),
        "size_bytes": engine.stat().st_size,
        "sha256": sha,
        "manifest": str(manifest_path),
        "build_variant": manifest.get("build_variant"),
        "platform": manifest.get("platform"),
        "cuda_target": block.get("cuda_target"),
        "comptime_defines": list(block.get("comptime_defines") or []),
        "host_shared_libraries": list(block.get("host_shared_libraries") or []),
        "source": block.get("source"),
        "shim_object": block.get("shim_object"),
        "bundled_libraries": {
            name: (directory / name).is_file() for name in cfg.ENGINE_BUNDLED_LIBRARIES
        },
        "expected_hardware_gate": verdict,
    }
    log.info(
        "%s %s: %s, target %s, %d defines; %s on %s",
        cfg.ENGINE_WHEEL,
        wheel_version,
        engine.name,
        facts["cuda_target"],
        len(facts["comptime_defines"]),
        "loads" if verdict.get("ok") else f"{verdict.get('code') or 'unchecked'}",
        cfg.HARDWARE,
    )
    return facts


def llama_server_version() -> dict[str, Any]:
    server = Path(cfg.LLAMA_SERVER)
    if not server.is_file() or not os.access(server, os.X_OK):
        raise core.ProbeError("llama_build_missing", f"{server} is not in the image")
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv
            [str(server), "--version"], capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise core.ProbeError("llama_server_failed", f"--version did not run: {exc}") from exc
    facts = core.parse_llama_version(f"{proc.stdout}\n{proc.stderr}")
    facts["returncode"] = proc.returncode
    commit_file = Path(cfg.LLAMA_COMMIT_FILE)
    facts["commit_file"] = (
        commit_file.read_text(encoding="utf-8").strip() if commit_file.is_file() else None
    )
    if facts["commit_file"] and facts["commit_file"] != cfg.LLAMA_CPP_COMMIT:
        raise core.ProbeError(
            "llama_commit_mismatch",
            f"the image built llama.cpp {facts['commit_file'][:10]}, "
            f"pinned {cfg.LLAMA_CPP_COMMIT[:10]}",
        )
    return facts


def bake_gguf(snapshot: Path) -> dict[str, Any]:
    """`convert_hf_to_gguf.py --outtype f16` on the baked snapshot, into the assets directory."""
    convert = Path(cfg.LLAMA_CONVERT)
    gguf_py = Path(cfg.LLAMA_GGUF_PY)
    if not convert.is_file() or not gguf_py.is_dir():
        raise core.ProbeError("llama_build_missing", f"{convert} or {gguf_py} is not in the image")
    out = probe.assets_dir() / cfg.GGUF_FILENAME
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{gguf_py}:{env.get('PYTHONPATH', '')}".rstrip(":")
    argv = [
        sys.executable,
        str(convert),
        "--outtype",
        cfg.LLAMA_GGUF_OUTTYPE,
        "--outfile",
        str(out),
        str(snapshot),
    ]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv
            argv,
            capture_output=True,
            text=True,
            timeout=CONVERT_TIMEOUT_S,
            check=False,
            env=env,
            cwd=str(convert.parent),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise core.ProbeError("llama_convert_failed", f"{type(exc).__name__}: {exc}") from exc
    wall = time.perf_counter() - t0
    tail = core.log_tail(f"{proc.stdout}\n{proc.stderr}", 5)
    if proc.returncode != 0 or not out.is_file():
        raise core.ProbeError(
            "llama_convert_failed",
            f"convert_hf_to_gguf.py exited {proc.returncode}: {tail[-1] if tail else 'no output'}",
        )
    log.info("%s: %.2f GB in %.1f s", out.name, out.stat().st_size / 1e9, wall)
    return {
        "path": str(out),
        "bytes": out.stat().st_size,
        "outtype": cfg.LLAMA_GGUF_OUTTYPE,
        "convert_wall_s": round(wall, 2),
        "converter": str(convert),
        "log_tail": tail,
    }


def bake_llama(snapshot: Path) -> dict[str, Any]:
    return {
        "server": cfg.LLAMA_SERVER,
        "commit_pinned": cfg.LLAMA_CPP_COMMIT,
        "tag": cfg.LLAMA_CPP_TAG,
        "cuda_architectures": cfg.LLAMA_CUDA_ARCHITECTURES,
        "version": llama_server_version(),
        "gguf": bake_gguf(snapshot),
    }


def write_facts(facts: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(facts, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def bake(path: Path) -> dict[str, Any]:
    if not hf_ua_shim.apply():
        raise core.ProbeError("huggingface_hub_missing", "huggingface_hub is not installed")
    facts = {
        "schema": "algenta-gpu-probe-build/2",
        "built_utc": core.utc_now(),
        **probe.environment_facts(),
        "hf_home": os.environ.get("HF_HOME"),
        "hub_cache": str(hub_cache_dir()),
        "hardware": cfg.HARDWARE,
        "kernel": bake_kernel(),
        "model": bake_model(),
        "engine": bake_engine(),
    }
    facts["llama"] = bake_llama(Path(facts["model"]["path"]))
    write_facts(facts, path)
    log.info("build facts written: %s", path)
    return facts


def gpu_absent(exc: BaseException) -> bool:
    text = f"{getattr(exc, 'code', '')} {exc}".lower()
    return any(marker in text for marker in GPU_ABSENT_MARKERS)


def verify(path: Path) -> dict[str, Any]:
    from huggingface_hub import constants

    if not constants.HF_HUB_OFFLINE:
        raise core.ProbeError(
            "verify_needs_offline",
            "run the verification with HF_HUB_OFFLINE=1 or it proves nothing",
        )
    hf_ua_shim.apply()
    facts = probe.read_build_facts(path)
    if not facts:
        raise core.ProbeError("build_facts_missing", f"{path} was not written by --bake")
    report: dict[str, Any] = {"verified_utc": core.utc_now(), "offline": True}

    # the model, from the cache alone
    from huggingface_hub import snapshot_download

    model_path = Path(
        snapshot_download(cfg.MODEL_REPO, revision=cfg.MODEL_REVISION, local_files_only=True)
    )
    if str(model_path) != facts["model"]["path"]:
        raise core.ProbeError(
            "model_snapshot_moved",
            f"offline resolves {model_path}, bake recorded {facts['model']['path']}",
        )
    report["model_path"] = str(model_path)

    # the kernel snapshot and its pruned listing
    kernel_path = Path(facts["kernel"]["path"])
    if not (kernel_path / "__init__.py").is_file() and not any(kernel_path.glob("*/__init__.py")):
        raise core.ProbeError("kernel_snapshot_missing", f"{kernel_path} holds no package")
    trees = hub_cache_dir() / repo_folder(cfg.KERNEL_REPO) / "trees"
    leftover = sorted(p.name for p in trees.glob("*.json")) if trees.is_dir() else []
    if leftover:
        raise core.ProbeError("tree_listings_present", f"unpruned listings: {leftover}")
    report["kernel_path"] = str(kernel_path)

    # the tokenizer on this interpreter (algenta requires CPython 3.14): the race prompt's cycle
    cycle = probe.decode_text(model_path, list(cfg.PROMPT_CYCLE_IDS))
    report["prompt_cycle_text"] = cycle
    report["prompt_ids"] = core.race_prompt_ids()
    log.info("race prompt: %r x %d", cycle, cfg.PROMPT_TOKENS // len(cfg.PROMPT_CYCLE_IDS))

    # the engine where the bake found it, unchanged
    engine = Path(facts["engine"]["path"])
    if not engine.is_file():
        raise core.ProbeError("engine_binary_missing", f"{engine} vanished after the bake")
    sha = probe.sha256_of(engine)
    if sha != facts["engine"]["sha256"]:
        raise core.ProbeError("engine_sha_mismatch", f"{engine.name} changed since the bake")
    report["engine"] = {
        "path": str(engine),
        "sha256": sha,
        "cuda_target": facts["engine"]["cuda_target"],
    }

    # the opponent's binary and its GGUF
    server = Path(cfg.LLAMA_SERVER)
    if not server.is_file():
        raise core.ProbeError("llama_build_missing", f"{server} is not in the image")
    gguf = Path(facts["llama"]["gguf"]["path"])
    if not gguf.is_file() or gguf.stat().st_size != facts["llama"]["gguf"]["bytes"]:
        raise core.ProbeError("llama_gguf_missing", f"{gguf} is absent or changed since the bake")
    report["llama"] = {"server": str(server), "gguf": str(gguf), "gguf_bytes": gguf.stat().st_size}

    # the kernel package imports from the cache; the device check is the runtime's job
    from kernels import get_kernel

    try:
        kernel = get_kernel(
            cfg.KERNEL_REPO,
            revision=cfg.KERNEL_REVISION,
            backend=cfg.KERNEL_BACKEND,
            trust_remote_code=[cfg.KERNEL_REPO],
            check_arch=False,
        )
    except Exception as exc:  # noqa: BLE001 - the reason decides pass or fail
        if gpu_absent(exc):
            report["offline_import"] = {"ok": None, "skipped": f"no GPU on the build host: {exc}"}
            log.warning("offline import skipped: %s", exc)
        else:
            raise core.ProbeError(
                "kernel_offline_import_failed", f"{type(exc).__name__}: {str(exc)[:200]}"
            ) from exc
    else:
        core.revision_gate(getattr(kernel, "__file__", ""))
        core.variant_gate(getattr(kernel, "__file__", ""))
        probe.decode_session_class(kernel)
        report["offline_import"] = {"ok": True, "file": getattr(kernel, "__file__", "")}
        log.info("offline import ok: %s", getattr(kernel, "__file__", ""))
    facts["verify"] = report
    write_facts(facts, path)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="bake the probe's assets into the image")
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--bake", action="store_true")
    action.add_argument("--verify", action="store_true")
    ap.add_argument("--facts", type=Path, default=None, help="build_facts.json location")
    a = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    path = a.facts or probe.build_facts_path()
    try:
        if a.bake:
            bake(path)
        else:
            verify(path)
    except core.ProbeError as exc:
        log.error("%s: %s", exc.code, exc.message)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
