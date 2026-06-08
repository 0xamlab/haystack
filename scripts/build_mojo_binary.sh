#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/mojo_build"
MOJO_SRC="${REPO_ROOT}/mojo/engine/main.mojo"
DISPATCH_GENERATOR="${REPO_ROOT}/scripts/generate_runtime_library_dispatch.py"
PIXI_ENV_DIR="${REPO_ROOT}/mojo_env"
LIB_DIR="${PIXI_ENV_DIR}/.pixi/envs/default/lib"
OBJECT_PATH="${BUILD_DIR}/simulate.o"
BINARY_PATH="${BUILD_DIR}/simulate"
TEMP_OBJECT_PATH="${BUILD_DIR}/simulate.o.tmp"
TEMP_BINARY_PATH="${BUILD_DIR}/simulate.tmp"

PIXI_BIN="${PIXI_BIN:-}"
if [[ -z "${PIXI_BIN}" ]]; then
    PIXI_BIN="$(command -v pixi 2>/dev/null || true)"
fi
if [[ -z "${PIXI_BIN}" && -x "${REPO_ROOT}/.pixi/bin/pixi" ]]; then
    PIXI_BIN="${REPO_ROOT}/.pixi/bin/pixi"
fi
if [[ -z "${PIXI_BIN}" || ! -x "${PIXI_BIN}" ]]; then
    echo "pixi not found. Run: make setup-mojo" >&2
    exit 1
fi

if [[ ! -f "${MOJO_SRC}" ]]; then
    echo "Mojo entrypoint not found at ${MOJO_SRC}" >&2
    exit 1
fi

if [[ ! -f "${DISPATCH_GENERATOR}" ]]; then
    echo "Runtime library dispatch generator not found at ${DISPATCH_GENERATOR}" >&2
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

CLANG_BIN="${CLANG_BIN:-}"
if [[ -z "${CLANG_BIN}" ]]; then
    CLANG_BIN="$(xcrun --find clang 2>/dev/null || command -v clang 2>/dev/null || true)"
fi
if [[ -z "${CLANG_BIN}" || ! -x "${CLANG_BIN}" ]]; then
    echo "clang not found; cannot link Mojo object into an executable" >&2
    exit 1
fi

SDKROOT_PATH="${SDKROOT:-}"
if [[ -z "${SDKROOT_PATH}" ]]; then
    SDKROOT_PATH="$(xcrun --show-sdk-path 2>/dev/null || true)"
fi

mkdir -p "${BUILD_DIR}"
rm -f "${TEMP_OBJECT_PATH}" "${TEMP_BINARY_PATH}"

python3 "${DISPATCH_GENERATOR}" >/dev/null

(
    cd "${PIXI_ENV_DIR}"
    "${PIXI_BIN}" run mojo build "${MOJO_SRC}" --emit object -o "${TEMP_OBJECT_PATH}"
)

RPATH_RELATIVE='@executable_path/../mojo_env/.pixi/envs/default/lib'

case "$(uname -s)" in
    Darwin)
        if [[ -z "${SDKROOT_PATH}" || ! -d "${SDKROOT_PATH}" ]]; then
            echo "macOS SDK not found; cannot link Mojo executable" >&2
            exit 1
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
            -lpython3.14 \
            -lc++
        ;;
    Linux)
        "${CLANG_BIN}" "${TEMP_OBJECT_PATH}" -o "${TEMP_BINARY_PATH}" \
            -L "${LIB_DIR}" \
            -Wl,-rpath,'$ORIGIN/../mojo_env/.pixi/envs/default/lib' \
            -Wl,-rpath,"${LIB_DIR}" \
            -lKGENCompilerRTShared \
            -lAsyncRTRuntimeGlobals \
            -lAsyncRTMojoBindings \
            -lMSupportGlobals \
            -lpython3.14 \
            -lc++ \
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

echo "${BINARY_PATH}"
