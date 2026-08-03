#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BUILD_DIR="${REPO_ROOT}/mojo_build"
MOJO_SRC="${MOJO_SRC:-${REPO_ROOT}/mojo/engine/main.mojo}"
DISPATCH_GENERATOR="${REPO_ROOT}/scripts/generate_runtime_library_dispatch.py"
DISPATCH_OUTPUT_PATH="${DISPATCH_OUTPUT_PATH:-${REPO_ROOT}/mojo/engine/runtime_library_dispatch_generated.mojo}"
PIXI_ENV_DIR="${REPO_ROOT}/mojo_env"
ENV_BIN_DIR="${PIXI_ENV_DIR}/.pixi/envs/default/bin"
LIB_DIR="${PIXI_ENV_DIR}/.pixi/envs/default/lib"
ENGINE_INCLUDE_DIR="${ENGINE_INCLUDE_DIR:-${REPO_ROOT}/mojo/engine}"
PYTHON_BIN="${ENV_BIN_DIR}/python"
BINARY_PATH="${BINARY_PATH:-${DEFAULT_BUILD_DIR}/simulate}"
OBJECT_PATH="${OBJECT_PATH:-${DEFAULT_BUILD_DIR}/simulate.o}"
TEMP_OBJECT_PATH="${TEMP_OBJECT_PATH:-${DEFAULT_BUILD_DIR}/simulate.o.tmp}"
TEMP_BINARY_PATH="${TEMP_BINARY_PATH:-${DEFAULT_BUILD_DIR}/simulate.tmp}"
BUILD_DIR="$(dirname "${BINARY_PATH}")"
MOJO_RUNTIME_MODULE_FILTER_RAW="${MOJO_RUNTIME_MODULE_FILTER:-}"
# Optional portable target CPU. `mojo build` defaults --target-cpu to the BUILD host's CPU, which
# bakes in whatever ISA the builder has (e.g. AVX-512 on an Intel CI runner) — that SIGILLs on a
# host CPU without it (Fly runs AMD EPYC: avx2/fma/bmi2, NO avx512). Set MOJO_BUILD_MCPU (e.g.
# x86-64-v3) for a portable deploy binary; unset (local builds) keeps the fast native default.
MOJO_BUILD_MCPU="${MOJO_BUILD_MCPU:-}"
# Opt-IN Metal GPU build. Default OFF, on every platform, deliberately: `-D ALGENTA_GPU` is what
# compiles accel/residentk/metaldispatch's Metal shaders in at all (see
# docs/mojo/new-kernel-package-rules.md rule 3 and tests/test_accel_gpu_isolation.py), and a
# Linux CI runner has no shader compiler at all -- the DEFAULT build of this script must keep
# working there unchanged. Set MOJO_BUILD_METAL_GPU=1 to additionally pass `-D ALGENTA_GPU`,
# compile the Objective-C batched-dispatch shim `metaldispatch.session`'s FFI layer calls into, and
# link it plus the Metal/Foundation/IOKit frameworks -- producing a worker binary whose
# `metaldispatch.qwen3_decode` (and `accel.gemm_metal`) entry points actually run their GPU kernels
# instead of reporting `shader_toolchain_absent`. Darwin only: there is no Metal on Linux, so this
# is refused rather than silently ignored there (see the platform check below).
MOJO_BUILD_METAL_GPU="${MOJO_BUILD_METAL_GPU:-0}"
METAL_SHIM_SOURCE_PATH="${METAL_SHIM_SOURCE_PATH:-${REPO_ROOT}/benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m}"

PIXI_HOME_EXPLICIT=0
if [[ -n "${PIXI_HOME:-}" ]]; then
    PIXI_HOME_EXPLICIT=1
fi

PIXI_HOME_DIR="${PIXI_HOME:-${REPO_ROOT}/.pixi}"
case "${PIXI_HOME_DIR}" in
    '~' | '~'/*) PIXI_HOME_DIR="${HOME-}${PIXI_HOME_DIR#\~}" ;;
esac

RATTLER_CACHE_DIR_VALUE="${RATTLER_CACHE_DIR:-${REPO_ROOT}/.cache/rattler/cache}"
RATTLER_AUTH_FILE_VALUE="${RATTLER_AUTH_FILE:-${REPO_ROOT}/.cache/rattler/credentials.json}"
export PIXI_HOME="${PIXI_HOME_DIR}"
export RATTLER_CACHE_DIR="${RATTLER_CACHE_DIR_VALUE}"
export RATTLER_AUTH_FILE="${RATTLER_AUTH_FILE_VALUE}"

mkdir -p "${PIXI_HOME}" "${RATTLER_CACHE_DIR}" "$(dirname "${RATTLER_AUTH_FILE}")"

resolve_pixi_bin() {
    local candidates=()
    local candidate

    if [[ -n "${PIXI_BIN:-}" ]]; then
        candidates+=("${PIXI_BIN}")
    fi
    if [[ "${PIXI_HOME_EXPLICIT}" == "1" ]]; then
        candidates+=("${PIXI_HOME}/bin/pixi")
    fi
    if command -v pixi >/dev/null 2>&1; then
        candidates+=("$(command -v pixi)")
    fi
    if [[ "${PIXI_HOME_EXPLICIT}" == "0" ]]; then
        candidates+=("${PIXI_HOME}/bin/pixi")
    fi

    for candidate in "${candidates[@]}"; do
        if [[ -n "${candidate}" && -x "${candidate}" ]]; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done

    return 1
}

if [[ ! -f "${MOJO_SRC}" ]]; then
    echo "Mojo entrypoint not found at ${MOJO_SRC}" >&2
    exit 1
fi

if [[ ! -f "${DISPATCH_GENERATOR}" ]]; then
    echo "Runtime library dispatch generator not found at ${DISPATCH_GENERATOR}" >&2
    exit 1
fi

if [[ ! -d "${ENGINE_INCLUDE_DIR}" ]]; then
    echo "Mojo engine include directory not found at ${ENGINE_INCLUDE_DIR}" >&2
    exit 1
fi

if [[ ! -d "${PIXI_ENV_DIR}" ]]; then
    echo "Mojo environment not found at ${PIXI_ENV_DIR}. Run: make setup-mojo" >&2
    exit 1
fi

if [[ ! -d "${LIB_DIR}" ]]; then
    echo "Mojo runtime library directory missing at ${LIB_DIR}. Run: make setup-mojo" >&2
    exit 1
fi

PIXI_BIN_RESOLVED="$(resolve_pixi_bin || true)"
if [[ -z "${PIXI_BIN_RESOLVED}" || ! -x "${PIXI_BIN_RESOLVED}" ]]; then
    echo "pixi not found. Run: make setup-mojo" >&2
    exit 1
fi

if [[ -x "${PYTHON_BIN}" ]]; then
    PYTHON_RUNTIME_STEM="$("${PYTHON_BIN}" - <<'PY'
import sys
print(f"python{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
else
    PYTHON_RUNTIME_STEM="$(
        (
            cd "${PIXI_ENV_DIR}"
            "${PIXI_BIN_RESOLVED}" run python - <<'PY'
import sys
print(f"python{sys.version_info.major}.{sys.version_info.minor}")
PY
        )
    )"
fi
if [[ -z "${PYTHON_RUNTIME_STEM}" ]]; then
    echo "Failed to detect the Python runtime version from ${PIXI_ENV_DIR}" >&2
    exit 1
fi

CLANG_BIN="${CLANG_BIN:-}"
if [[ -z "${CLANG_BIN}" ]]; then
    CLANG_BIN="$(xcrun --find clang 2>/dev/null || command -v clang 2>/dev/null || true)"
fi
if [[ -z "${CLANG_BIN}" || ! -x "${CLANG_BIN}" ]]; then
    echo "clang not found; cannot link Mojo object into an executable" >&2
    exit 1
fi

METAL_GPU_BUILD=0
case "${MOJO_BUILD_METAL_GPU}" in
    1 | true | TRUE | yes | YES) METAL_GPU_BUILD=1 ;;
esac
if [[ "${METAL_GPU_BUILD}" == "1" && "$(uname -s)" != "Darwin" ]]; then
    # Refused, not silently downgraded to a non-GPU build: a caller who set this expects a binary
    # that runs Metal kernels, and Linux has no Metal at all -- reporting that loudly here is cheaper
    # than a build that "succeeds" and then answers shader_toolchain_absent forever on every host.
    echo "MOJO_BUILD_METAL_GPU=1 requested on $(uname -s); Metal is Darwin-only. Unset it for a" \
        "portable build, or build on a Mac." >&2
    exit 1
fi
if [[ "${METAL_GPU_BUILD}" == "1" && ! -f "${METAL_SHIM_SOURCE_PATH}" ]]; then
    echo "METAL_SHIM_SOURCE_PATH not found: ${METAL_SHIM_SOURCE_PATH}" >&2
    exit 1
fi

SDKROOT_PATH="${SDKROOT:-}"
if [[ -z "${SDKROOT_PATH}" ]]; then
    SDKROOT_PATH="$(xcrun --show-sdk-path 2>/dev/null || true)"
fi

mkdir -p \
    "${BUILD_DIR}" \
    "$(dirname "${OBJECT_PATH}")" \
    "$(dirname "${TEMP_OBJECT_PATH}")" \
    "$(dirname "${TEMP_BINARY_PATH}")" \
    "$(dirname "${DISPATCH_OUTPUT_PATH}")"
rm -f "${TEMP_OBJECT_PATH}" "${TEMP_BINARY_PATH}"

METAL_SHIM_OBJECT_PATH="${BUILD_DIR}/metal_batch_shim.o"
if [[ "${METAL_GPU_BUILD}" == "1" ]]; then
    if [[ -z "${SDKROOT_PATH}" || ! -d "${SDKROOT_PATH}" ]]; then
        echo "macOS SDK not found; cannot compile the Metal batch-dispatch shim" >&2
        exit 1
    fi
    echo "[build_mojo_binary] Metal GPU build: compiling ${METAL_SHIM_SOURCE_PATH}" >&2
    "${CLANG_BIN}" -c -fobjc-arc -O2 -isysroot "${SDKROOT_PATH}" \
        "${METAL_SHIM_SOURCE_PATH}" -o "${METAL_SHIM_OBJECT_PATH}"
fi

# A module-FILTERED build must not write its dispatch over the tracked artifact. Left alone, the
# lines below hand the generator `--output <tracked> --modules <subset>`, which replaces the whole
# ~114k-line runtime contract with the few hundred lines that subset needs. It still compiles and
# the filtered build still passes, so nothing notices until a kernel whose dispatch arm is gone
# answers `module_not_registered`. Measured: 114,002 lines -> 397.
#
# Redirecting into the build directory is the fix rather than refusing, because a filtered build is
# a legitimate and common thing to want -- it is how a single shard gets built in seconds instead of
# compiling the monolith. The generator ALSO refuses this combination outright as a backstop, so if
# this redirect is ever removed the result is a loud failure and not a silent truncation.
if [[ -n "${MOJO_RUNTIME_MODULE_FILTER_RAW}" \
   && "${DISPATCH_OUTPUT_PATH}" == "${REPO_ROOT}/mojo/engine/runtime_library_dispatch_generated.mojo" ]]; then
    DISPATCH_OUTPUT_PATH="${BUILD_DIR}/runtime_library_dispatch_generated.mojo"
fi

DISPATCH_GENERATOR_ARGS=(--output "${DISPATCH_OUTPUT_PATH}")
if [[ -n "${MOJO_RUNTIME_MODULE_FILTER_RAW}" ]]; then
    IFS=',' read -r -a RAW_MODULE_FILTER <<< "${MOJO_RUNTIME_MODULE_FILTER_RAW}"
    MODULE_FILTER=()
    for module_name in "${RAW_MODULE_FILTER[@]}"; do
        module_name="${module_name//[[:space:]]/}"
        if [[ -n "${module_name}" ]]; then
            MODULE_FILTER+=("${module_name}")
        fi
    done
    if [[ "${#MODULE_FILTER[@]}" -gt 0 ]]; then
        DISPATCH_GENERATOR_ARGS+=(--modules "${MODULE_FILTER[@]}")
    fi
fi

python3 "${DISPATCH_GENERATOR}" "${DISPATCH_GENERATOR_ARGS[@]}" >/dev/null

# Mojo compile must run inside the pixi-managed environment so std/package
# roots resolve exactly as they do for runtime-owned test and server invocations.
MOJO_TARGET_ARGS=()
if [[ -n "${MOJO_BUILD_MCPU}" ]]; then
    MOJO_TARGET_ARGS+=(--mcpu "${MOJO_BUILD_MCPU}")
    echo "[build_mojo_binary] target CPU: ${MOJO_BUILD_MCPU} (portable; not host-native)" >&2
fi
if [[ "${METAL_GPU_BUILD}" == "1" ]]; then
    MOJO_TARGET_ARGS+=(-D ALGENTA_GPU)
fi
(
    cd "${PIXI_ENV_DIR}"
    "${PIXI_BIN_RESOLVED}" run mojo build \
        -I "${ENGINE_INCLUDE_DIR}" \
        "${MOJO_SRC}" \
        --emit object \
        "${MOJO_TARGET_ARGS[@]+"${MOJO_TARGET_ARGS[@]}"}" \
        -o "${TEMP_OBJECT_PATH}"
)

RPATH_RELATIVE='@executable_path/../mojo_env/.pixi/envs/default/lib'

case "$(uname -s)" in
    Darwin)
        PYTHON_RUNTIME_LIB="${LIB_DIR}/lib${PYTHON_RUNTIME_STEM}.dylib"
        if [[ -z "${SDKROOT_PATH}" || ! -d "${SDKROOT_PATH}" ]]; then
            echo "macOS SDK not found; cannot link Mojo executable" >&2
            exit 1
        fi
        if [[ ! -f "${PYTHON_RUNTIME_LIB}" ]]; then
            echo "Python runtime library not found at ${PYTHON_RUNTIME_LIB}" >&2
            exit 1
        fi
        DARWIN_METAL_LINK_ARGS=()
        if [[ "${METAL_GPU_BUILD}" == "1" ]]; then
            DARWIN_METAL_LINK_ARGS+=(
                "${METAL_SHIM_OBJECT_PATH}"
                -framework Metal -framework Foundation -framework IOKit
            )
        fi
        "${CLANG_BIN}" "${TEMP_OBJECT_PATH}" -o "${TEMP_BINARY_PATH}" \
            -isysroot "${SDKROOT_PATH}" \
            -L "${LIB_DIR}" \
            -Wl,-syslibroot,"${SDKROOT_PATH}" \
            -Wl,-rpath,"${RPATH_RELATIVE}" \
            -Wl,-rpath,"${LIB_DIR}" \
            -lKGENCompilerRTShared \
            -lAsyncRTRuntimeGlobals \
            -lAsyncRTMojoBindings \
            -lMSupportGlobals \
            "${PYTHON_RUNTIME_LIB}" \
            -lc++ \
            "${DARWIN_METAL_LINK_ARGS[@]+"${DARWIN_METAL_LINK_ARGS[@]}"}"
        ;;
    Linux)
        PYTHON_RUNTIME_LIB="$(find "${LIB_DIR}" -maxdepth 1 -name "lib${PYTHON_RUNTIME_STEM}.so*" | sort | head -n 1)"
        if [[ -z "${PYTHON_RUNTIME_LIB}" ]]; then
            echo "Python runtime library not found under ${LIB_DIR} for ${PYTHON_RUNTIME_STEM}" >&2
            exit 1
        fi
        # The linux pixi env ships GNU libstdc++ (libstdcxx in pixi.lock), NOT libc++ — so the
        # Mojo runtime libs are built against libstdc++ and we link -lstdc++ (the macOS branch
        # uses -lc++, its system C++ runtime). conda runtime packages ship only the versioned
        # libstdc++.so.N, so create the unversioned linker symlink in LIB_DIR — the link then
        # binds the SAME libstdc++ the $ORIGIN rpath loads at runtime (no system/ABI skew).
        if ! [[ -e "${LIB_DIR}/libstdc++.so" ]]; then
            stdcxx_versioned="$(find "${LIB_DIR}" -maxdepth 1 -name "libstdc++.so.*" | sort -V | tail -n 1)"
            if [[ -n "${stdcxx_versioned}" ]]; then
                ln -sf "$(basename "${stdcxx_versioned}")" "${LIB_DIR}/libstdc++.so"
            fi
        fi
        echo "[build_mojo_binary] C++ runtime libs in ${LIB_DIR}:" >&2
        ls -la "${LIB_DIR}"/libstdc++* "${LIB_DIR}"/libc++* >&2 2>&1 || true
        "${CLANG_BIN}" "${TEMP_OBJECT_PATH}" -o "${TEMP_BINARY_PATH}" \
            -L "${LIB_DIR}" \
            -Wl,-rpath,'$ORIGIN/../mojo_env/.pixi/envs/default/lib' \
            -Wl,-rpath,"${LIB_DIR}" \
            -lKGENCompilerRTShared \
            -lAsyncRTRuntimeGlobals \
            -lAsyncRTMojoBindings \
            -lMSupportGlobals \
            "${PYTHON_RUNTIME_LIB}" \
            -lstdc++ \
            -ldl \
            -lpthread \
            -lm
        ;;
    *)
        echo "Unsupported platform for native Mojo link: $(uname -s)" >&2
        exit 1
        ;;
esac

chmod +x "${TEMP_BINARY_PATH}"
mv "${TEMP_BINARY_PATH}" "${BINARY_PATH}"
rm -f "${TEMP_OBJECT_PATH}" "${OBJECT_PATH}"

MANIFEST_PATH="${BINARY_PATH}.manifest.json"
TEMP_MANIFEST_PATH="${MANIFEST_PATH}.tmp"
REPO_ROOT_FOR_MANIFEST="${REPO_ROOT}" \
BINARY_PATH_FOR_MANIFEST="${BINARY_PATH}" \
MANIFEST_PATH_FOR_MANIFEST="${MANIFEST_PATH}" \
TEMP_MANIFEST_PATH_FOR_MANIFEST="${TEMP_MANIFEST_PATH}" \
MOJO_RUNTIME_MODULE_FILTER_FOR_MANIFEST="${MOJO_RUNTIME_MODULE_FILTER_RAW}" \
python3 - <<'PYMANIFEST'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root)).replace(os.sep, "/")


repo_root = Path(os.environ["REPO_ROOT_FOR_MANIFEST"]).resolve()
binary_path = Path(os.environ["BINARY_PATH_FOR_MANIFEST"]).resolve()
manifest_path = Path(os.environ["MANIFEST_PATH_FOR_MANIFEST"]).resolve()
temp_manifest_path = Path(os.environ["TEMP_MANIFEST_PATH_FOR_MANIFEST"]).resolve()
raw_filter = os.environ.get("MOJO_RUNTIME_MODULE_FILTER_FOR_MANIFEST", "")
module_filter = tuple(item.strip() for item in raw_filter.split(",") if item.strip())

source_paths: set[Path] = {
    repo_root / "apps" / "runtime" / "mojo_inventory.py",
    repo_root / "mojo" / "engine" / "main.mojo",
    repo_root / "mojo_env" / "pixi.lock",
    repo_root / "mojo_env" / "pixi.toml",
    repo_root / "scripts" / "build_mojo_binary.sh",
    repo_root / "scripts" / "generate_runtime_library_dispatch.py",
}
for mojo_source in (repo_root / "mojo" / "engine").rglob("*.mojo"):
    if mojo_source.name == "runtime_library_dispatch_generated.mojo":
        if not module_filter:
            source_paths.add(mojo_source)
        continue
    source_paths.add(mojo_source)

ordered_sources = tuple(sorted(path for path in source_paths if path.exists()))
source_hashes = {_relative(path, repo_root): _sha256_file(path) for path in ordered_sources}
payload = {
    "schema_version": 1,
    "build_mode": "filtered" if module_filter else "full",
    "module_filter": list(module_filter),
    "binary_path": (
        _relative(binary_path, repo_root)
        if binary_path.is_relative_to(repo_root)
        else binary_path.name
    ),
    "binary_sha256": _sha256_file(binary_path),
    "source_paths": list(source_hashes),
    "source_sha256": source_hashes,
}
temp_manifest_path.write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
temp_manifest_path.replace(manifest_path)
PYMANIFEST

echo "${BINARY_PATH}"
