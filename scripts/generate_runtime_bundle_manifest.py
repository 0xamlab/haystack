#!/usr/bin/env python3
"""Generate the signed bundled-runtime manifest payload for one staged runtime directory.

This is the manifest ``.github/scripts/build_runtime_linux_amd64.sh`` signs with the release key
and that ``algenta.native.verify.verify_manifest`` checks on every user's machine before a single
bundled byte is executed. It used to be an inline ``python3 - <<PY`` heredoc in that shell script;
it lives here because the payload now carries release-critical *variant* facts that have to be
asserted by tests on a machine with no GPU, no CUDA toolkit and no Linux:

* ``build_variant`` — ``"cpu"`` or ``"cuda"``. This is the ONLY machine-readable statement in the
  shipped wheel about which accelerator tier the binaries inside were compiled for. Before it
  existed, a CPU-built worker and a CUDA-built worker were indistinguishable once unpacked: both
  are named ``algenta-runtime-worker*``, both sit in ``algenta_runtime_native/``, and the wheel
  filename is identical for the two variants (``build-runtime.yml``'s publish job relies on the
  release-verify gate, not on the name, to keep them apart). ``algenta serve --backend cuda``
  reads this field to decide whether the engine binary sitting beside the worker is one it may
  launch — see ``packages/algenta/algenta/serve/engine.py``.
* ``engine`` — the bundled CUDA engine artifact: its name, the Mojo source it was built from, the
  ``--target-accelerator`` it was compiled for, the exact comptime define stack, and the shared
  libraries it needs FROM THE HOST rather than from the wheel.

The engine block exists because of a hard packaging fact, not a preference: the certified CUDA
engine links the tensor-core shim (``benchmarks/llm_smoke/nvidia_race/tc_shim.cu``), which calls
cuBLAS directly, so the binary carries ``DT_NEEDED libcublas.so.12``. cuBLAS is ~580 MB
(``nvidia-cublas-cu12`` on PyPI ships 581,240,110 bytes for linux x86_64) against a 42 MB wheel,
and it is not in any manylinux allowlist, so it can be neither bundled nor silently external. It is
therefore DECLARED here, in the signed manifest, as a host requirement — the same posture the
runtime already takes for ``libcuda.so.1`` (dlopen'd, never linked) — and
``scripts/release/audit_runtime_wheel_abi.py`` fails the build closed on any *undeclared* external
library.

Determinism: the payload is emitted as canonical JSON (``sort_keys=True``, ``separators=(",",":")``)
because the release signature covers these EXACT bytes and a re-serialization would invalidate it.

Usage (from the container build script)::

    python3 scripts/generate_runtime_bundle_manifest.py \\
        --artifact-dir /work/mojo_build/runtime-wheel \\
        --platform linux-x86_64 \\
        --build-variant cuda \\
        --output /work/mojo_build/runtime-wheel/manifest.json \\
        --engine conform_generate_cuda \\
        --engine-source benchmarks/llm_smoke/conform_generate_cuda.mojo \\
        --cuda-target sm_90a \\
        --comptime-define ALGENTA_GPU --comptime-define ALGENTA_CUDA \\
        --host-shared-library libcublas.so.12
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "BUILD_VARIANTS",
    "CUDA_BUILD_VARIANT",
    "CPU_BUILD_VARIANT",
    "MANIFEST_FORMAT_VERSION",
    "BundleManifestError",
    "build_bundle_manifest",
    "render_bundle_manifest",
    "validate_bundle_manifest",
]

MANIFEST_FORMAT_VERSION = 1

CPU_BUILD_VARIANT = "cpu"
CUDA_BUILD_VARIANT = "cuda"
BUILD_VARIANTS: tuple[str, ...] = (CPU_BUILD_VARIANT, CUDA_BUILD_VARIANT)

# Files the generator itself (or the signing step) writes into the staged directory. They are part
# of the release but not part of the hashed artifact set: the manifest cannot contain its own hash.
_NON_ARTIFACT_NAMES = frozenset({"manifest.json", "manifest.sig", "algenta_release_pub.pem"})

DEFAULT_WORKER_NAME = "algenta-runtime-worker"
SHARD_MAP_NAME = "runtime-shards.json"

# `sm_90`, `sm_90a`, `sm_100a`, ... — Mojo's own `--target-accelerator` spelling for NVIDIA.
_CUDA_TARGET_RE = re.compile(r"^sm_\d+[a-z]?$")
# A soname, never a path: this list is a declaration of what the HOST must provide.
_SONAME_RE = re.compile(r"^[A-Za-z0-9_.+-]+\.so(\.[A-Za-z0-9_.+-]+)*$")
_COMPTIME_DEFINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BundleManifestError(ValueError):
    """The staged directory cannot produce a valid signed runtime manifest. Fail closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_entries(artifact_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name in _NON_ARTIFACT_NAMES:
            continue
        entries.append(
            {
                "name": path.name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return entries


def _require_worker_shards(names: set[str]) -> None:
    """The invariant the heredoc this replaced asserted, kept verbatim in intent."""
    workers = {
        name
        for name in names
        if name == DEFAULT_WORKER_NAME or name.startswith(f"{DEFAULT_WORKER_NAME}-")
    }
    if DEFAULT_WORKER_NAME not in workers or len(workers) < 2:
        raise BundleManifestError("bounded runtime worker shards missing from staged artifacts")
    if SHARD_MAP_NAME not in names:
        raise BundleManifestError("runtime-shards.json missing from staged artifacts")


def build_engine_block(
    *,
    name: str,
    sha256: str,
    size_bytes: int,
    source: str,
    cuda_target: str,
    comptime_defines: Iterable[str],
    host_shared_libraries: Iterable[str],
    shim_object: str | None = None,
) -> dict[str, Any]:
    """The manifest's ``engine`` block, validated as it is built."""
    if Path(name).name != name or not name:
        raise BundleManifestError(f"engine name is not a bare file name: {name!r}")
    if not _CUDA_TARGET_RE.match(cuda_target):
        raise BundleManifestError(f"engine cuda_target is not an sm_NN[a] target: {cuda_target!r}")
    defines = list(dict.fromkeys(comptime_defines))
    for define in defines:
        if not _COMPTIME_DEFINE_RE.match(define):
            raise BundleManifestError(f"engine comptime define is not an identifier: {define!r}")
    libs = list(dict.fromkeys(host_shared_libraries))
    for lib in libs:
        if not _SONAME_RE.match(lib):
            raise BundleManifestError(f"engine host shared library is not a soname: {lib!r}")
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        raise BundleManifestError(f"engine sha256 is malformed: {sha256!r}")
    block: dict[str, Any] = {
        "name": name,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "source": source,
        "cuda_target": cuda_target,
        "comptime_defines": defines,
        "host_shared_libraries": libs,
    }
    if shim_object:
        block["shim_object"] = shim_object
    return block


def build_bundle_manifest(
    *,
    artifact_dir: str | Path,
    platform: str,
    build_variant: str,
    engine: dict[str, Any] | None = None,
    cuda_target: str | None = None,
) -> dict[str, Any]:
    """Hash every staged artifact and assemble the (unsigned) manifest payload."""
    directory = Path(artifact_dir)
    if not directory.is_dir():
        raise BundleManifestError(f"staged runtime directory does not exist: {directory}")
    if build_variant not in BUILD_VARIANTS:
        raise BundleManifestError(
            f"unknown build variant {build_variant!r} (expected one of {', '.join(BUILD_VARIANTS)})"
        )
    entries = _artifact_entries(directory)
    names = {entry["name"] for entry in entries}
    _require_worker_shards(names)

    payload: dict[str, Any] = {
        "format_version": MANIFEST_FORMAT_VERSION,
        "platform": platform,
        "build_variant": build_variant,
        "artifacts": entries,
    }
    if cuda_target is not None:
        if build_variant != CUDA_BUILD_VARIANT:
            raise BundleManifestError(
                f"a {build_variant!r} runtime manifest must not declare cuda_target {cuda_target!r}"
            )
        if not _CUDA_TARGET_RE.match(cuda_target):
            raise BundleManifestError(f"cuda_target is not an sm_NN[a] target: {cuda_target!r}")
        payload["cuda_target"] = cuda_target
    if engine is not None:
        if build_variant != CUDA_BUILD_VARIANT:
            raise BundleManifestError(
                f"a bundled CUDA engine cannot be declared in a {build_variant!r} runtime manifest"
            )
        listed = next(
            (entry for entry in entries if entry["name"] == engine["name"]),
            None,
        )
        if listed is None:
            raise BundleManifestError(
                f"engine artifact {engine['name']!r} is not present in the staged directory"
            )
        if listed["sha256"] != engine["sha256"] or listed["size_bytes"] != engine["size_bytes"]:
            raise BundleManifestError(
                f"engine artifact {engine['name']!r} does not match its declared digest"
            )
        payload["engine"] = engine
    return payload


def validate_bundle_manifest(payload: Any) -> dict[str, Any]:
    """Re-validate a manifest payload read back from disk. Raises ``BundleManifestError``.

    This is the read-side twin of :func:`build_bundle_manifest`: the same invariants, checked
    against bytes this process did not produce, so ``scripts/validate_runtime_release.py`` and any
    test can round-trip a manifest without trusting the generator.
    """
    if not isinstance(payload, dict):
        raise BundleManifestError("runtime bundle manifest is not a JSON object")
    if payload.get("format_version") != MANIFEST_FORMAT_VERSION:
        raise BundleManifestError(
            f"unsupported runtime bundle manifest format_version: {payload.get('format_version')!r}"
        )
    if not isinstance(payload.get("platform"), str) or not payload["platform"]:
        raise BundleManifestError("runtime bundle manifest is missing a platform")
    variant = payload.get("build_variant")
    if variant not in BUILD_VARIANTS:
        raise BundleManifestError(
            "runtime bundle manifest build_variant must be one of "
            f"{', '.join(BUILD_VARIANTS)}, got {variant!r}"
        )
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise BundleManifestError("runtime bundle manifest has no artifact list")
    names: set[str] = set()
    for entry in artifacts:
        if not isinstance(entry, dict):
            raise BundleManifestError(f"manifest artifact entry is not an object: {entry!r}")
        name = entry.get("name")
        digest = entry.get("sha256")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise BundleManifestError(f"manifest artifact name is unsafe: {name!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise BundleManifestError(f"artifact {name!r} has a malformed sha256")
        if name in names:
            raise BundleManifestError(f"manifest artifact is listed twice: {name!r}")
        names.add(name)
    _require_worker_shards(names)

    cuda_target = payload.get("cuda_target")
    if cuda_target is not None:
        if variant != CUDA_BUILD_VARIANT:
            raise BundleManifestError(
                f"a {variant!r} runtime manifest must not declare cuda_target {cuda_target!r}"
            )
        if not isinstance(cuda_target, str) or not _CUDA_TARGET_RE.match(cuda_target):
            raise BundleManifestError(f"cuda_target is not an sm_NN[a] target: {cuda_target!r}")
    elif variant == CUDA_BUILD_VARIANT and payload.get("engine") is not None:
        raise BundleManifestError(
            "a cuda runtime manifest declaring an engine must also declare its cuda_target"
        )

    engine = payload.get("engine")
    if engine is None:
        return payload
    if variant != CUDA_BUILD_VARIANT:
        raise BundleManifestError(
            f"a bundled CUDA engine cannot be declared in a {variant!r} runtime manifest"
        )
    if not isinstance(engine, dict):
        raise BundleManifestError("manifest engine block is not a JSON object")
    for field in ("name", "sha256", "size_bytes", "source", "cuda_target"):
        if engine.get(field) in (None, ""):
            raise BundleManifestError(f"manifest engine block is missing {field!r}")
    if engine["name"] not in names:
        raise BundleManifestError(
            f"manifest engine {engine['name']!r} is not listed among the signed artifacts"
        )
    listed = next(entry for entry in artifacts if entry["name"] == engine["name"])
    if listed["sha256"] != engine["sha256"] or listed["size_bytes"] != engine["size_bytes"]:
        raise BundleManifestError(
            f"manifest engine {engine['name']!r} does not match its signed artifact entry"
        )
    defines = engine.get("comptime_defines")
    if not isinstance(defines, list) or not defines:
        raise BundleManifestError("manifest engine block declares no comptime_defines")
    for define in defines:
        if not isinstance(define, str) or not _COMPTIME_DEFINE_RE.match(define):
            raise BundleManifestError(f"engine comptime define is not an identifier: {define!r}")
    libs = engine.get("host_shared_libraries")
    if not isinstance(libs, list):
        raise BundleManifestError("manifest engine block has no host_shared_libraries list")
    for lib in libs:
        if not isinstance(lib, str) or not _SONAME_RE.match(lib):
            raise BundleManifestError(f"engine host shared library is not a soname: {lib!r}")
    return payload


def render_bundle_manifest(payload: dict[str, Any]) -> bytes:
    """The EXACT bytes the release signature covers. Never re-serialize these."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--build-variant", required=True, choices=BUILD_VARIANTS)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cuda-target", default=None)
    parser.add_argument("--engine", default=None, help="bare file name of the bundled engine")
    parser.add_argument("--engine-source", default=None)
    parser.add_argument("--engine-shim-object", default=None)
    parser.add_argument("--comptime-define", action="append", default=[])
    parser.add_argument("--host-shared-library", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        engine: dict[str, Any] | None = None
        if args.engine:
            if not args.engine_source or not args.cuda_target:
                raise BundleManifestError("--engine requires --engine-source and --cuda-target")
            path = args.artifact_dir / args.engine
            if not path.is_file():
                raise BundleManifestError(f"engine artifact is not staged: {path}")
            engine = build_engine_block(
                name=args.engine,
                sha256=_sha256(path),
                size_bytes=path.stat().st_size,
                source=args.engine_source,
                cuda_target=args.cuda_target,
                comptime_defines=args.comptime_define,
                host_shared_libraries=args.host_shared_library,
                shim_object=args.engine_shim_object,
            )
        payload = build_bundle_manifest(
            artifact_dir=args.artifact_dir,
            platform=args.platform,
            build_variant=args.build_variant,
            engine=engine,
            cuda_target=args.cuda_target,
        )
        validate_bundle_manifest(payload)
    except BundleManifestError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(render_bundle_manifest(payload))
    sys.stdout.write(
        f"runtime bundle manifest: {args.output} "
        f"variant={payload['build_variant']} artifacts={len(payload['artifacts'])} "
        f"engine={payload['engine']['name'] if engine else '<none>'}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
